"""
Invoice Classifier — Inference Module
======================================
Loads serialized artifacts from training and runs predictions with:
  - Single-sample and batch prediction
  - p99 latency measurement and SLA enforcement
  - Confidence score output
  - Input validation
"""

import logging
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger("invoice_classifier.inference")

ARTIFACT_DIR = Path(__file__).parent / "artifacts"

TEXT_COLUMNS = ["vendor_name", "line_items_text", "payment_terms"]
NUM_COLUMNS = ["total_amount", "tax_amount", "num_line_items", "days_to_due"]
CAT_COLUMNS = ["currency", "payment_method", "department"]


class InvoiceClassifier:
    """Production inference wrapper with SLA enforcement."""

    SLA_MS = 100  # p99 single-sample budget

    def __init__(self, artifact_dir: Path = ARTIFACT_DIR):
        self.model = joblib.load(artifact_dir / "model.joblib")
        self.tfidf = joblib.load(artifact_dir / "tfidf.joblib")
        self.scaler = joblib.load(artifact_dir / "scaler.joblib")
        self.ohe = joblib.load(artifact_dir / "ohe.joblib")
        self.le = joblib.load(artifact_dir / "label_encoder.joblib")
        logger.info("Artifacts loaded from %s", artifact_dir)

    def _featurize(self, df: pd.DataFrame) -> np.ndarray:
        """Transform raw DataFrame into model-ready feature matrix."""
        text = df[TEXT_COLUMNS].fillna("").agg(" ".join, axis=1)
        num = df[NUM_COLUMNS].fillna(0).astype(float)
        cat = df[CAT_COLUMNS].fillna("unknown")

        text_vec = self.tfidf.transform(text).toarray()
        num_sc = self.scaler.transform(num)
        cat_enc = self.ohe.transform(cat)

        return np.hstack([text_vec, num_sc, cat_enc])

    def predict(self, df: pd.DataFrame) -> list[dict]:
        """
        Predict invoice type for each row.

        Returns a list of dicts:
          {label, confidence, probabilities, latency_ms}
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")

        results = []
        for i in range(len(df)):
            row = df.iloc[[i]]
            t0 = time.perf_counter()
            X = self._featurize(row)
            proba = self.model.predict_proba(X)[0]
            pred_idx = int(np.argmax(proba))
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if elapsed_ms > self.SLA_MS:
                logger.warning(
                    "SLA breach: sample %d took %.2f ms (budget %d ms)",
                    i, elapsed_ms, self.SLA_MS,
                )

            results.append(
                {
                    "label": self.le.classes_[pred_idx],
                    "confidence": round(float(proba[pred_idx]), 4),
                    "probabilities": {
                        cls: round(float(p), 4)
                        for cls, p in zip(self.le.classes_, proba)
                    },
                    "latency_ms": round(elapsed_ms, 3),
                    "sla_met": elapsed_ms <= self.SLA_MS,
                }
            )

        return results

    def predict_batch(self, df: pd.DataFrame) -> list[dict]:
        """
        Vectorised batch prediction — more efficient for large batches.
        No per-sample latency; reports total and mean latency.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")

        t0 = time.perf_counter()
        X = self._featurize(df)
        probas = self.model.predict_proba(X)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        pred_idxs = np.argmax(probas, axis=1)
        results = []
        for i, (idx, proba) in enumerate(zip(pred_idxs, probas)):
            results.append(
                {
                    "label": self.le.classes_[idx],
                    "confidence": round(float(proba[idx]), 4),
                    "probabilities": {
                        cls: round(float(p), 4)
                        for cls, p in zip(self.le.classes_, proba)
                    },
                }
            )

        logger.info(
            "Batch predict: %d samples in %.2f ms (%.3f ms/sample)",
            len(df), elapsed_ms, elapsed_ms / len(df),
        )
        return results

    def measure_latency(self, n_trials: int = 200) -> dict:
        """
        Run n_trials single-sample inferences on synthetic data and return
        latency percentiles (p50, p95, p99).
        """
        from train import generate_synthetic_data, load_config
        cfg = load_config()
        df = generate_synthetic_data(n_samples=n_trials, seed=0)

        latencies = []
        for i in range(n_trials):
            t0 = time.perf_counter()
            self._featurize(df.iloc[[i]])
            self.model.predict_proba(self._featurize(df.iloc[[i]]))
            latencies.append((time.perf_counter() - t0) * 1000)

        stats = {
            "p50_ms": round(float(np.percentile(latencies, 50)), 3),
            "p95_ms": round(float(np.percentile(latencies, 95)), 3),
            "p99_ms": round(float(np.percentile(latencies, 99)), 3),
            "mean_ms": round(float(np.mean(latencies)), 3),
            "sla_ms": self.SLA_MS,
            "sla_met": float(np.percentile(latencies, 99)) <= self.SLA_MS,
        }
        logger.info("Latency stats: %s", stats)
        return stats


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    clf = InvoiceClassifier()

    sample = pd.DataFrame(
        [
            {
                "vendor_name": "Acme Corp",
                "line_items_text": "software license 12 months 5 seats",
                "payment_terms": "net30",
                "total_amount": 12000.0,
                "tax_amount": 960.0,
                "num_line_items": 1,
                "days_to_due": 30,
                "currency": "USD",
                "payment_method": "bank_transfer",
                "department": "engineering",
            }
        ]
    )

    preds = clf.predict(sample)
    print(json.dumps(preds, indent=2))

    latency = clf.measure_latency(n_trials=100)
    print(json.dumps(latency, indent=2))
