"""
Inference & Latency Benchmark — Toxicity Detection
====================================================
Measures single-sample and batch latency against the SLA defined in config.yaml.

Usage
-----
    python inference.py --config config.yaml --model_dir artifacts/toxicity_model
    python inference.py --config config.yaml --text "Hello world"
    python inference.py --config config.yaml --benchmark          # latency report
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import yaml
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("toxicity.inference")


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

def load_config(path: str) -> Dict[str, Any]:
    with open(path) as fh:
        return yaml.safe_load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# ToxicityClassifier  — production-ready wrapper
# ─────────────────────────────────────────────────────────────────────────────

class ToxicityClassifier:
    """Thin wrapper around HuggingFace pipeline with SLA enforcement."""

    SAMPLE_TEXTS = [
        "You are a fantastic person and I really appreciate you.",
        "I hate everything about this disgusting world.",
        "The sunset looks beautiful today.",
        "Go kill yourself, you worthless idiot.",
        "I'm looking forward to our meeting tomorrow.",
        "This is utter garbage and you should be ashamed.",
        "Great job on the presentation!",
        "You're a disgrace to humanity.",
        "The project is coming along nicely.",
        "Shut up, nobody cares what you think.",
    ]

    def __init__(
        self,
        model_dir: str,
        sla_ms: float = 100.0,
        threshold: float = 0.5,
    ) -> None:
        self.sla_ms = sla_ms
        self.threshold = threshold
        self._load_model(model_dir)

    def _load_model(self, model_dir: str) -> None:
        logger.info("Loading model from %s …", model_dir)
        device = 0 if torch.cuda.is_available() else -1
        self.pipe = pipeline(
            "text-classification",
            model=model_dir,
            tokenizer=model_dir,
            device=device,
            return_all_scores=False,
        )
        # Warm-up: discard first inference (JIT, CUDA init)
        _ = self.pipe("warm up text")
        logger.info("Model ready on %s", "GPU" if device == 0 else "CPU")

    # ── Single prediction ──────────────────────────────────────────────────────
    def predict(self, text: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        out = self.pipe(text, truncation=True, max_length=128)[0]
        latency_ms = (time.perf_counter() - t0) * 1000

        label = out["label"].lower()
        score = out["score"]
        toxic_prob = score if ("1" in label or "toxic" in label) else 1.0 - score
        is_toxic = toxic_prob >= self.threshold

        result = {
            "text": text[:120],
            "is_toxic": bool(is_toxic),
            "toxic_probability": round(float(toxic_prob), 4),
            "latency_ms": round(latency_ms, 2),
            "sla_met": latency_ms <= self.sla_ms,
        }
        if not result["sla_met"]:
            logger.warning("SLA breach: %.1f ms > %.1f ms SLA", latency_ms, self.sla_ms)
        return result

    # ── Batch prediction ──────────────────────────────────────────────────────
    def predict_batch(self, texts: List[str]) -> List[Dict[str, Any]]:
        t0 = time.perf_counter()
        outputs = self.pipe(texts, truncation=True, max_length=128, batch_size=32)
        total_ms = (time.perf_counter() - t0) * 1000
        per_sample_ms = total_ms / len(texts)

        results = []
        for text, out in zip(texts, outputs):
            label = out["label"].lower()
            score = out["score"]
            toxic_prob = score if ("1" in label or "toxic" in label) else 1.0 - score
            results.append({
                "text": text[:120],
                "is_toxic": bool(toxic_prob >= self.threshold),
                "toxic_probability": round(float(toxic_prob), 4),
            })

        logger.info(
            "Batch inference: %d samples in %.1f ms (%.2f ms/sample)",
            len(texts), total_ms, per_sample_ms,
        )
        return results

    # ── Latency benchmark ──────────────────────────────────────────────────────
    def benchmark(
        self,
        warmup_runs: int = 5,
        benchmark_runs: int = 100,
    ) -> Dict[str, Any]:
        """Measure single-sample latency over N runs."""
        import random
        texts = [random.choice(self.SAMPLE_TEXTS) for _ in range(benchmark_runs + warmup_runs)]

        # Warm-up (not counted)
        for t in texts[:warmup_runs]:
            self.pipe(t, truncation=True, max_length=128)

        latencies: List[float] = []
        for t in texts[warmup_runs:]:
            t0 = time.perf_counter()
            self.pipe(t, truncation=True, max_length=128)
            latencies.append((time.perf_counter() - t0) * 1000)

        sla_violations = sum(1 for l in latencies if l > self.sla_ms)

        report = {
            "runs": benchmark_runs,
            "sla_ms": self.sla_ms,
            "min_ms":    round(min(latencies), 2),
            "max_ms":    round(max(latencies), 2),
            "mean_ms":   round(statistics.mean(latencies), 2),
            "median_ms": round(statistics.median(latencies), 2),
            "p95_ms":    round(sorted(latencies)[int(0.95 * len(latencies))], 2),
            "p99_ms":    round(sorted(latencies)[int(0.99 * len(latencies))], 2),
            "sla_violations": sla_violations,
            "sla_violation_rate": round(sla_violations / benchmark_runs, 4),
            "sla_passed": sla_violations == 0,
        }

        logger.info(
            "Latency benchmark — mean=%.2f ms  p95=%.2f ms  p99=%.2f ms  "
            "SLA violations=%d/%d",
            report["mean_ms"], report["p95_ms"], report["p99_ms"],
            sla_violations, benchmark_runs,
        )
        return report


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Toxicity model inference & benchmark")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model_dir", default="artifacts/toxicity_model")
    parser.add_argument("--text", type=str, default=None, help="Single text to classify")
    parser.add_argument("--benchmark", action="store_true", help="Run latency benchmark")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    cfg = load_config(args.config)
    inf_cfg = cfg["inference"]

    clf = ToxicityClassifier(
        model_dir=args.model_dir,
        sla_ms=inf_cfg["sla_ms"],
        threshold=args.threshold,
    )

    if args.text:
        result = clf.predict(args.text)
        print(json.dumps(result, indent=2))

    elif args.benchmark:
        report = clf.benchmark(
            warmup_runs=inf_cfg["warmup_runs"],
            benchmark_runs=inf_cfg["benchmark_runs"],
        )
        print(json.dumps(report, indent=2))

        out = Path("artifacts/latency_report.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as fh:
            json.dump(report, fh, indent=2)
        logger.info("Latency report saved to %s", out)

    else:
        # Demo: classify a few examples
        examples = [
            "Have a wonderful day!",
            "You are absolute garbage.",
            "I disagree with your opinion but respect your right to hold it.",
            "I will destroy you for this.",
        ]
        print("\n=== Demo Predictions ===")
        for ex in examples:
            r = clf.predict(ex)
            flag = "TOXIC" if r["is_toxic"] else "CLEAN"
            print(f"  [{flag}] p={r['toxic_probability']:.3f}  {r['latency_ms']}ms  |  {ex[:60]}")


if __name__ == "__main__":
    main()
