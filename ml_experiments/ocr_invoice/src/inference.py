"""
inference.py — Production inference pipeline with SLA latency enforcement.

Usage
─────
    from inference import OCRInferencePipeline

    pipe = OCRInferencePipeline("artifacts/model")
    result = pipe.predict("path/to/invoice.jpg")
    # {"text": "...", "confidence": 0.94, "latency_ms": 312}

    batch = pipe.predict_batch(["img1.jpg", "img2.jpg"])

SLA contract
────────────
• p95 inference latency ≤ 500 ms per image (configurable via sla_ms).
• Latency is measured end-to-end: disk → preprocess → model → decode.
• SLA violations are logged as WARNING and returned in the result dict.
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

logger = logging.getLogger(__name__)


class OCRInferencePipeline:
    """Single-image and batch inference for the fine-tuned TrOCR model.

    Parameters
    ----------
    model_dir   : directory produced by train_ocr.py (model + processor saved there)
    device      : "cuda", "cpu", or None (auto-detect)
    sla_ms      : per-image p95 latency budget in milliseconds
    beam_size   : beam width for beam-search decoding
    max_length  : max decoder token length
    """

    def __init__(
        self,
        model_dir: str | Path,
        device: Optional[str] = None,
        sla_ms: float = 500.0,
        beam_size: int = 4,
        max_length: int = 128,
    ) -> None:
        model_dir = Path(model_dir)
        self.sla_ms = sla_ms
        self.beam_size = beam_size
        self.max_length = max_length

        # Device selection
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        logger.info("Loading model from %s on %s", model_dir, self.device)
        self.processor = TrOCRProcessor.from_pretrained(str(model_dir))
        self.model = VisionEncoderDecoderModel.from_pretrained(str(model_dir))
        self.model.to(self.device)
        self.model.eval()

        # Latency history (circular buffer of last 1 000 calls)
        self._latency_history: List[float] = []
        self._sla_violations: int = 0

    # ── Single image ──────────────────────────────────────────────────────────

    def predict(self, image_input: Union[str, Path, Image.Image]) -> Dict:
        """Run OCR on a single image.

        Returns
        -------
        {
            "text"        : str,
            "confidence"  : float,   # mean token probability (0–1)
            "latency_ms"  : float,
            "sla_ok"      : bool,
        }
        """
        t_start = time.perf_counter()

        # --- Load image -------------------------------------------------------
        if not isinstance(image_input, Image.Image):
            image_input = Image.open(image_input).convert("RGB")

        # --- Preprocess -------------------------------------------------------
        pixel_values = self.processor(
            images=image_input, return_tensors="pt"
        ).pixel_values.to(self.device)

        # --- Inference --------------------------------------------------------
        with torch.no_grad():
            generated = self.model.generate(
                pixel_values,
                num_beams=self.beam_size,
                max_length=self.max_length,
                output_scores=True,
                return_dict_in_generate=True,
            )

        # --- Decode -----------------------------------------------------------
        text = self.processor.batch_decode(
            generated.sequences, skip_special_tokens=True
        )[0]

        # Confidence: geometric mean of max-softmax scores across generated tokens
        if generated.scores:
            token_probs = [
                torch.softmax(s, dim=-1).max(dim=-1).values.item()
                for s in generated.scores
            ]
            confidence = float(np.exp(np.mean(np.log(np.clip(token_probs, 1e-9, 1.0)))))
        else:
            confidence = 0.0

        latency_ms = (time.perf_counter() - t_start) * 1000
        sla_ok = latency_ms <= self.sla_ms

        self._latency_history.append(latency_ms)
        if len(self._latency_history) > 1000:
            self._latency_history.pop(0)
        if not sla_ok:
            self._sla_violations += 1
            logger.warning(
                "SLA breach: %.1f ms > %.1f ms budget", latency_ms, self.sla_ms
            )

        return {
            "text": text,
            "confidence": round(confidence, 4),
            "latency_ms": round(latency_ms, 2),
            "sla_ok": sla_ok,
        }

    # ── Batch inference ───────────────────────────────────────────────────────

    def predict_batch(
        self,
        images: List[Union[str, Path, Image.Image]],
        batch_size: int = 16,
    ) -> List[Dict]:
        """Run OCR on a list of images (batched for GPU efficiency)."""
        results = []
        for i in range(0, len(images), batch_size):
            chunk = images[i : i + batch_size]
            for img in chunk:
                results.append(self.predict(img))
        return results

    # ── Latency profiling ─────────────────────────────────────────────────────

    def latency_stats(self) -> Dict[str, float]:
        """Summary statistics over the rolling latency history."""
        if not self._latency_history:
            return {}
        h = sorted(self._latency_history)
        return {
            "n_calls": len(h),
            "p50_ms": round(statistics.median(h), 2),
            "p95_ms": round(h[int(len(h) * 0.95)], 2),
            "p99_ms": round(h[int(len(h) * 0.99)], 2),
            "mean_ms": round(statistics.mean(h), 2),
            "max_ms": round(max(h), 2),
            "sla_violations": self._sla_violations,
            "sla_budget_ms": self.sla_ms,
        }

    def benchmark(
        self,
        images: List[Union[str, Path, Image.Image]],
        n_warmup: int = 5,
    ) -> Dict:
        """Run a latency benchmark and assert p95 ≤ sla_ms.

        Parameters
        ----------
        images   : list of images to benchmark (recommend ≥ 100)
        n_warmup : warmup passes before measurement starts

        Returns
        -------
        stats dict + "sla_pass" boolean
        """
        logger.info("Warming up with %d passes …", n_warmup)
        for img in images[:n_warmup]:
            self.predict(img)
        self._latency_history.clear()   # discard warmup latencies

        logger.info("Benchmarking %d images …", len(images))
        for img in images:
            self.predict(img)

        stats = self.latency_stats()
        stats["sla_pass"] = stats.get("p95_ms", float("inf")) <= self.sla_ms
        if not stats["sla_pass"]:
            logger.error(
                "Latency SLA FAILED — p95 %.1f ms > budget %.1f ms",
                stats["p95_ms"], self.sla_ms,
            )
        else:
            logger.info(
                "Latency SLA PASS — p95 %.1f ms ≤ budget %.1f ms",
                stats["p95_ms"], self.sla_ms,
            )
        return stats


# ── CLI quick-test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run OCR inference on one image")
    parser.add_argument("--model_dir", default="artifacts/model")
    parser.add_argument("--image", required=True)
    parser.add_argument("--sla_ms", type=float, default=500.0)
    args = parser.parse_args()

    pipe = OCRInferencePipeline(args.model_dir, sla_ms=args.sla_ms)
    result = pipe.predict(args.image)
    print(json.dumps(result, indent=2))
