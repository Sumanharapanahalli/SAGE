"""
receipt_classifier/inference.py
────────────────────────────────
Production inference module with latency measurement and SLA enforcement.

Usage
─────
Single prediction (CLI):
    python inference.py --amount 42.50 --merchant-type restaurant \\
                        --payment-method credit --currency USD

Batch prediction:
    python inference.py --csv-path receipts_to_classify.csv

Module usage:
    from inference import ReceiptClassifier
    clf = ReceiptClassifier()
    result = clf.predict_one({"amount_usd": 42.5, "merchant_type": "restaurant", ...})
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml
from joblib import load

from data import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    RECEIPT_CATEGORIES,
)

logger = logging.getLogger(__name__)
CONFIG_PATH = Path(__file__).parent / "config.yaml"


# ── Result types ───────────────────────────────────────────────────────────────

@dataclass
class Prediction:
    predicted_category: str
    confidence: float                    # max class probability
    top_3: List[Dict[str, Any]]          # top-3 categories + probabilities
    latency_ms: float
    sla_met: bool


@dataclass
class BatchPrediction:
    predictions: List[Prediction]
    mean_latency_ms: float
    p95_latency_ms: float
    sla_violations: int


# ── Classifier wrapper ─────────────────────────────────────────────────────────

class ReceiptClassifier:
    """
    Thin wrapper around the persisted Pipeline + LabelEncoder artefacts.

    Thread-safety: predict_one / predict_batch are read-only after __init__.
    Suitable for use in a FastAPI application with concurrent requests.
    """

    def __init__(
        self,
        model_dir: str = "models/",
        config_path: str = str(CONFIG_PATH),
    ) -> None:
        model_dir = Path(model_dir)
        with open(config_path) as fh:
            config = yaml.safe_load(fh)

        self._sla_ms: float = config["inference"]["latency_sla_ms"]
        self._pipeline = load(model_dir / "pipeline.joblib")
        self._label_enc = load(model_dir / "label_encoder.joblib")
        self._classes: List[str] = list(self._label_enc.classes_)

        logger.info(
            "ReceiptClassifier loaded — %d classes, SLA=%.0fms",
            len(self._classes), self._sla_ms,
        )

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _to_dataframe(self, raw: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert a single raw dict to a properly typed one-row DataFrame.
        Missing numeric features default to 0; missing categoricals to 'unknown'.
        """
        row: Dict[str, Any] = {}
        for feat in NUMERIC_FEATURES:
            row[feat] = float(raw.get(feat, 0.0))
        for feat in CATEGORICAL_FEATURES:
            row[feat] = str(raw.get(feat, "unknown"))
        return pd.DataFrame([row])

    def _make_prediction(self, X: pd.DataFrame) -> Prediction:
        t0 = time.perf_counter()
        y_pred = self._pipeline.predict(X)
        y_prob = self._pipeline.predict_proba(X)
        latency_ms = (time.perf_counter() - t0) * 1000

        predicted_label = self._label_enc.inverse_transform(y_pred)[0]
        probs = y_prob[0]

        top3_idx = np.argsort(probs)[::-1][:3]
        top3 = [
            {"category": self._classes[i], "probability": round(float(probs[i]), 4)}
            for i in top3_idx
        ]

        return Prediction(
            predicted_category=str(predicted_label),
            confidence=round(float(probs[y_pred[0]]), 4),
            top_3=top3,
            latency_ms=round(latency_ms, 3),
            sla_met=latency_ms <= self._sla_ms,
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def predict_one(self, raw: Dict[str, Any]) -> Prediction:
        """
        Classify a single receipt dict.

        Parameters
        ----------
        raw : dict with any subset of the feature schema.
              Missing numeric features → 0, missing categoricals → 'unknown'.

        Returns
        -------
        Prediction dataclass with category, confidence, top-3, latency, sla_met.
        """
        X = self._to_dataframe(raw)
        result = self._make_prediction(X)

        if not result.sla_met:
            logger.warning(
                "SLA breach: %.2fms > %.0fms for receipt=%s",
                result.latency_ms, self._sla_ms, raw.get("receipt_id", "?"),
            )
        return result

    def predict_batch(self, records: List[Dict[str, Any]]) -> BatchPrediction:
        """
        Classify a list of receipt dicts.  Each record is timed individually
        to give per-sample latency statistics.
        """
        predictions: List[Prediction] = []
        for rec in records:
            predictions.append(self.predict_one(rec))

        latencies = [p.latency_ms for p in predictions]
        violations = sum(1 for p in predictions if not p.sla_met)

        return BatchPrediction(
            predictions=predictions,
            mean_latency_ms=round(float(np.mean(latencies)), 3),
            p95_latency_ms=round(float(np.percentile(latencies, 95)), 3),
            sla_violations=violations,
        )

    def predict_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify an entire DataFrame.  Returns df with added columns:
        predicted_category, confidence, latency_ms.

        NOTE: Timing here is per-batch (not per-row) — use predict_batch
        if you need per-row latencies.
        """
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        # Fill missing columns with defaults
        for feat in NUMERIC_FEATURES:
            if feat not in df.columns:
                df[feat] = 0.0
        for feat in CATEGORICAL_FEATURES:
            if feat not in df.columns:
                df[feat] = "unknown"

        X = df[features].copy()
        t0 = time.perf_counter()
        y_pred = self._pipeline.predict(X)
        y_prob = self._pipeline.predict_proba(X)
        batch_ms = (time.perf_counter() - t0) * 1000

        df = df.copy()
        df["predicted_category"] = self._label_enc.inverse_transform(y_pred)
        df["confidence"] = y_prob[np.arange(len(y_pred)), y_pred].round(4)
        df["batch_latency_ms"] = round(batch_ms, 2)
        return df


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Receipt classifier inference")
    parser.add_argument("--model-dir", default="models/")
    # Single-record flags
    parser.add_argument("--amount", type=float, default=None)
    parser.add_argument("--merchant-type", default="restaurant")
    parser.add_argument("--payment-method", default="credit")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--item-count", type=int, default=2)
    # Batch
    parser.add_argument("--csv-path", default=None)
    args = parser.parse_args()

    clf = ReceiptClassifier(model_dir=args.model_dir)

    if args.csv_path:
        df = pd.read_csv(args.csv_path)
        result_df = clf.predict_dataframe(df)
        print(result_df[["predicted_category", "confidence", "batch_latency_ms"]].head(20))
    else:
        raw = {
            "amount_usd":      args.amount or 42.50,
            "merchant_type":   args.merchant_type,
            "payment_method":  args.payment_method,
            "currency":        args.currency,
            "item_count":      args.item_count,
        }
        pred = clf.predict_one(raw)
        print(json.dumps(asdict(pred), indent=2))
