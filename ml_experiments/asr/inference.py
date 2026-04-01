"""
ASR Inference Pipeline — Production Grade
Benchmarks p95 latency against SLA and optionally exports to ONNX.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    latency_ms: float
    rtf: float
    within_sla: bool
    audio_duration_sec: float


class ASRPipeline:
    """Production inference wrapper with latency SLA enforcement."""

    def __init__(self, model_dir: str, config_path: str = "config.yaml"):
        with open(config_path) as f:
            cfg = yaml.safe_load(f)

        self.cfg = cfg
        self.infer_cfg = cfg["inference"]
        self.sampling_rate: int = cfg["data"]["sampling_rate"]
        self.latency_sla_ms: float = self.infer_cfg["latency_sla_ms"]
        self.rtf_threshold: float = cfg["evaluation"]["rtf_sla_threshold"]

        device_str = self.infer_cfg.get("device", "cpu")
        if device_str == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but unavailable — falling back to CPU")
            device_str = "cpu"
        self.device = torch.device(device_str)

        logger.info("Loading model from %s on %s", model_dir, self.device)
        # Lazy import to avoid circular dependency during testing
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        self.processor = Wav2Vec2Processor.from_pretrained(model_dir)
        self.model = Wav2Vec2ForCTC.from_pretrained(model_dir).to(self.device)
        self.model.eval()

        if self.infer_cfg.get("use_onnx"):
            self._export_onnx(model_dir)

    def transcribe(self, audio: np.ndarray) -> TranscriptionResult:
        """Transcribe a single audio array (float32, mono, 16 kHz)."""
        duration_sec = len(audio) / self.sampling_rate

        inputs = self.processor(
            audio,
            sampling_rate=self.sampling_rate,
            return_tensors="pt",
            padding=True,
        ).to(self.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(**inputs).logits
        latency_sec = time.perf_counter() - t0

        pred_ids = torch.argmax(logits, dim=-1)
        text = self.processor.decode(pred_ids[0])

        latency_ms = latency_sec * 1000
        rtf = latency_sec / duration_sec if duration_sec > 0 else float("inf")
        within_sla = latency_ms <= self.latency_sla_ms

        return TranscriptionResult(
            text=text,
            latency_ms=round(latency_ms, 2),
            rtf=round(rtf, 4),
            within_sla=within_sla,
            audio_duration_sec=round(duration_sec, 3),
        )

    def benchmark(
        self,
        audio_duration_sec: float = 10.0,
        n_runs: int | None = None,
    ) -> dict:
        """Warm-up + benchmark on synthetic audio. Returns latency statistics."""
        n_runs = n_runs or self.infer_cfg["benchmark_runs"]
        n_samples = int(audio_duration_sec * self.sampling_rate)

        logger.info(
            "Benchmarking: %d runs × %.1f-second clips on %s",
            n_runs, audio_duration_sec, self.device,
        )

        # Warm-up (3 runs excluded from stats)
        for _ in range(3):
            audio = np.random.randn(n_samples).astype(np.float32)
            self.transcribe(audio)

        latencies_ms = []
        rtfs = []
        for i in range(n_runs):
            audio = np.random.randn(n_samples).astype(np.float32)
            result = self.transcribe(audio)
            latencies_ms.append(result.latency_ms)
            rtfs.append(result.rtf)
            if (i + 1) % 20 == 0:
                logger.info("  Run %d/%d — p50=%.1f ms", i + 1, n_runs, np.median(latencies_ms))

        stats = {
            "audio_duration_sec": audio_duration_sec,
            "n_runs": n_runs,
            "device": str(self.device),
            "latency_ms": {
                "mean": round(float(np.mean(latencies_ms)), 2),
                "std": round(float(np.std(latencies_ms)), 2),
                "p50": round(float(np.percentile(latencies_ms, 50)), 2),
                "p90": round(float(np.percentile(latencies_ms, 90)), 2),
                "p95": round(float(np.percentile(latencies_ms, 95)), 2),
                "p99": round(float(np.percentile(latencies_ms, 99)), 2),
                "max": round(float(np.max(latencies_ms)), 2),
            },
            "rtf": {
                "mean": round(float(np.mean(rtfs)), 4),
                "p95": round(float(np.percentile(rtfs, 95)), 4),
            },
            "sla": {
                "latency_sla_ms": self.latency_sla_ms,
                "rtf_threshold": self.rtf_threshold,
                "latency_p95_pass": float(np.percentile(latencies_ms, 95)) <= self.latency_sla_ms,
                "rtf_p95_pass": float(np.percentile(rtfs, 95)) <= self.rtf_threshold,
                "fraction_within_sla": round(
                    sum(l <= self.latency_sla_ms for l in latencies_ms) / n_runs, 4
                ),
            },
        }

        logger.info("Benchmark complete:")
        logger.info("  p50=%.1f ms | p95=%.1f ms | p99=%.1f ms", stats["latency_ms"]["p50"], stats["latency_ms"]["p95"], stats["latency_ms"]["p99"])
        logger.info("  RTF p95=%.4f (SLA=%.2f) → %s", stats["rtf"]["p95"], self.rtf_threshold, "PASS" if stats["sla"]["rtf_p95_pass"] else "FAIL")
        logger.info("  Latency p95=%.1f ms (SLA=%d ms) → %s", stats["latency_ms"]["p95"], int(self.latency_sla_ms), "PASS" if stats["sla"]["latency_p95_pass"] else "FAIL")

        return stats

    def _export_onnx(self, model_dir: str):
        """Export model to ONNX for lower-latency serving."""
        onnx_path = Path(model_dir) / "model.onnx"
        if onnx_path.exists():
            logger.info("ONNX model already exists: %s", onnx_path)
            return

        logger.info("Exporting to ONNX: %s", onnx_path)
        n_samples = int(5.0 * self.sampling_rate)
        dummy_input = torch.randn(1, n_samples).to(self.device)

        torch.onnx.export(
            self.model,
            (dummy_input,),
            str(onnx_path),
            input_names=["input_values"],
            output_names=["logits"],
            dynamic_axes={"input_values": {0: "batch", 1: "sequence"}},
            opset_version=14,
        )
        logger.info("ONNX export complete: %s", onnx_path)


def main(config_path: str = "config.yaml", model_dir: str | None = None):
    import json

    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    model_dir = model_dir or str(Path(cfg["experiment"]["output_dir"]) / "best_model")
    pipeline = ASRPipeline(model_dir=model_dir, config_path=config_path)

    # Benchmark
    stats = pipeline.benchmark(audio_duration_sec=10.0)

    # Save results
    out = Path(cfg["experiment"]["output_dir"]) / "benchmark_results.json"
    with open(out, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info("Benchmark saved: %s", out)

    # Demo transcription
    demo_audio = np.random.randn(int(3.0 * cfg["data"]["sampling_rate"])).astype(np.float32)
    result = pipeline.transcribe(demo_audio)
    logger.info(
        "Demo transcription — text=%r | latency=%.1f ms | rtf=%.3f | sla=%s",
        result.text,
        result.latency_ms,
        result.rtf,
        "PASS" if result.within_sla else "FAIL",
    )

    return stats


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="ASR Inference Benchmark")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model_dir", default=None)
    args = parser.parse_args()
    stats = main(args.config, args.model_dir)
    print(json.dumps(stats, indent=2))
