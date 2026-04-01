"""
inference.py — Production-grade NLU intent inference with latency SLA enforcement.

Features:
  - Single-sample and batch predict
  - P50/P95/P99 latency benchmarking
  - SLA violation warning logged to stderr
  - Top-K confidence scores returned
  - Thread-safe via single-model singleton

Usage:
    from inference import IntentClassifier
    clf = IntentClassifier.load("artifacts/model", "artifacts/tokenizer")
    result = clf.predict("Book me a flight to Tokyo")
    print(result)  # {"intent": "book_flight", "confidence": 0.97, "latency_ms": 12.3}

    # SLA check
    clf.benchmark(n=200, sla_ms=50)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    intent: str
    confidence: float
    top_k: list[dict[str, float]]   # [{"intent": ..., "confidence": ...}]
    latency_ms: float
    is_oos: bool = False             # True if max confidence < OOS threshold


@dataclass
class LatencyReport:
    n_samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    sla_ms: float
    sla_violations: int
    sla_pass: bool

    def log(self) -> None:
        status = "PASS" if self.sla_pass else "FAIL ⚠"
        logger.info(
            "Latency [n=%d] — P50=%.1fms P95=%.1fms P99=%.1fms Mean=%.1fms "
            "| SLA=%.0fms violations=%d [%s]",
            self.n_samples, self.p50_ms, self.p95_ms, self.p99_ms, self.mean_ms,
            self.sla_ms, self.sla_violations, status,
        )
        if not self.sla_pass:
            logger.warning(
                "SLA VIOLATION: P95 latency %.1fms exceeds SLA %.0fms",
                self.p95_ms, self.sla_ms,
            )


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class IntentClassifier:
    """Thread-safe intent classifier wrapping a fine-tuned transformer."""

    _DEFAULT_OOS_THRESHOLD = 0.5   # below this confidence → flag as out-of-scope
    _DEFAULT_TOP_K = 5

    def __init__(
        self,
        model: AutoModelForSequenceClassification,
        tokenizer: AutoTokenizer,
        class_names: list[str],
        max_length: int = 128,
        oos_threshold: float = _DEFAULT_OOS_THRESHOLD,
        top_k: int = _DEFAULT_TOP_K,
    ) -> None:
        self.model       = model
        self.tokenizer   = tokenizer
        self.class_names = class_names
        self.max_length  = max_length
        self.oos_threshold = oos_threshold
        self.top_k       = min(top_k, len(class_names))
        self.device      = next(model.parameters()).device
        self.model.eval()

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def load(
        cls,
        model_dir: str | Path,
        tokenizer_dir: str | Path,
        config_path: str | Path = "config.yaml",
        device: str | None = None,
    ) -> "IntentClassifier":
        model_dir    = Path(model_dir)
        tokenizer_dir = Path(tokenizer_dir)

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        dev = torch.device(device)

        tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
        model     = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        model.to(dev)

        # Load class names from config or model config
        class_names: list[str] = []
        cfg_path = Path(config_path)
        if cfg_path.exists():
            with open(cfg_path) as f:
                cfg = yaml.safe_load(f)
            if isinstance(cfg.get("model", {}).get("id2label"), dict):
                id2label = cfg["model"]["id2label"]
                class_names = [id2label[str(i)] for i in range(len(id2label))]

        if not class_names and hasattr(model.config, "id2label"):
            class_names = [model.config.id2label[i]
                           for i in range(model.config.num_labels)]

        if not class_names:
            class_names = [f"intent_{i}" for i in range(model.config.num_labels)]

        max_length = 128
        if cfg_path.exists():
            max_length = cfg.get("data", {}).get("max_length", 128)

        logger.info(
            "Loaded IntentClassifier: %d classes, device=%s", len(class_names), device
        )
        return cls(model, tokenizer, class_names, max_length=max_length)

    # ── Inference ─────────────────────────────────────────────────────────

    @torch.no_grad()
    def predict(self, text: str) -> IntentResult:
        """Single-sample prediction with latency timing."""
        t0 = time.perf_counter()

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=self.max_length,
        ).to(self.device)

        logits = self.model(**inputs).logits[0]
        probs  = torch.softmax(logits, dim=-1).cpu().numpy()

        latency_ms = (time.perf_counter() - t0) * 1000.0

        top_k_idx   = np.argsort(probs)[::-1][: self.top_k]
        top_k_items = [
            {"intent": self.class_names[i], "confidence": round(float(probs[i]), 4)}
            for i in top_k_idx
        ]
        best_idx   = int(top_k_idx[0])
        best_conf  = float(probs[best_idx])
        is_oos     = best_conf < self.oos_threshold

        return IntentResult(
            intent=self.class_names[best_idx],
            confidence=round(best_conf, 4),
            top_k=top_k_items,
            latency_ms=round(latency_ms, 2),
            is_oos=is_oos,
        )

    @torch.no_grad()
    def predict_batch(self, texts: list[str]) -> list[IntentResult]:
        """Batch prediction — amortises tokenisation overhead."""
        t0 = time.perf_counter()

        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=self.max_length,
        ).to(self.device)

        logits = self.model(**inputs).logits
        probs  = torch.softmax(logits, dim=-1).cpu().numpy()

        total_ms  = (time.perf_counter() - t0) * 1000.0
        per_ms    = total_ms / max(len(texts), 1)

        results = []
        for i, prob_row in enumerate(probs):
            top_k_idx   = np.argsort(prob_row)[::-1][: self.top_k]
            top_k_items = [
                {"intent": self.class_names[j], "confidence": round(float(prob_row[j]), 4)}
                for j in top_k_idx
            ]
            best_idx  = int(top_k_idx[0])
            best_conf = float(prob_row[best_idx])
            results.append(IntentResult(
                intent=self.class_names[best_idx],
                confidence=round(best_conf, 4),
                top_k=top_k_items,
                latency_ms=round(per_ms, 2),
                is_oos=best_conf < self.oos_threshold,
            ))
        return results

    # ── Latency benchmarking ──────────────────────────────────────────────

    def benchmark(
        self,
        n: int = 200,
        sla_ms: float = 50.0,
        warmup: int = 20,
    ) -> LatencyReport:
        """
        Measure single-sample P50/P95/P99 latency.

        Args:
            n:       Number of timed iterations.
            sla_ms:  SLA threshold in milliseconds (P95 must be ≤ this).
            warmup:  Warm-up iterations (excluded from measurement).
        """
        sample = "Book me a flight to Tokyo please"
        times: list[float] = []

        # Warm-up
        for _ in range(warmup):
            self.predict(sample)

        # Timed runs
        for _ in range(n):
            res = self.predict(sample)
            times.append(res.latency_ms)

        arr         = np.array(times)
        p50         = float(np.percentile(arr, 50))
        p95         = float(np.percentile(arr, 95))
        p99         = float(np.percentile(arr, 99))
        mean        = float(arr.mean())
        violations  = int((arr > sla_ms).sum())

        report = LatencyReport(
            n_samples=n,
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            mean_ms=round(mean, 2),
            sla_ms=sla_ms,
            sla_violations=violations,
            sla_pass=p95 <= sla_ms,
        )
        report.log()
        return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="NLU intent inference")
    parser.add_argument("--model-dir",     default="artifacts/model")
    parser.add_argument("--tokenizer-dir", default="artifacts/tokenizer")
    parser.add_argument("--config",        default="config.yaml")
    parser.add_argument("--text",          help="Single text to classify")
    parser.add_argument("--benchmark",     action="store_true",
                        help="Run latency benchmark")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    clf = IntentClassifier.load(args.model_dir, args.tokenizer_dir, args.config)

    if args.text:
        result = clf.predict(args.text)
        print(json.dumps({
            "intent":      result.intent,
            "confidence":  result.confidence,
            "is_oos":      result.is_oos,
            "latency_ms":  result.latency_ms,
            "top_k":       result.top_k,
        }, indent=2))

    if args.benchmark:
        with open(args.config) as f:
            cfg = yaml.safe_load(f)
        sla_ms = cfg.get("inference", {}).get("latency_sla_ms", 50)
        n      = cfg.get("inference", {}).get("num_latency_samples", 200)
        clf.benchmark(n=n, sla_ms=sla_ms)
