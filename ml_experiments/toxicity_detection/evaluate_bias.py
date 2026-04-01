"""
Bias Evaluation — Toxicity Detection Model
===========================================
Evaluates per-subgroup performance across identity categories (gender, race,
religion, disability, sexual orientation) to surface disparate impact.

Reports
-------
- Per-group accuracy, F1, FPR, FNR
- Demographic-parity gap vs overall baseline
- Passes/fails fairness threshold from config.yaml
- Saves JSON report to artifacts/bias_report.json

Usage
-----
    python evaluate_bias.py --config config.yaml --model_dir artifacts/toxicity_model
"""

from __future__ import annotations

import argparse
import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import torch
import yaml
from datasets import load_dataset
from sklearn.metrics import (
    accuracy_score, f1_score,
    confusion_matrix,
)
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("toxicity.bias")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_config(path: str) -> Dict[str, Any]:
    with open(path) as fh:
        return yaml.safe_load(fh)


def _safe_fpr_fnr(y_true: np.ndarray, y_pred: np.ndarray):
    """Return (FPR, FNR) safely even for single-class subgroups."""
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (cm[0, 0], 0, 0, 0)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else float("nan")
    fnr = fn / (fn + tp) if (fn + tp) > 0 else float("nan")
    return fpr, fnr


def _subgroup_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray) -> Dict:
    if len(y_true) == 0:
        return {}
    fpr, fnr = _safe_fpr_fnr(y_true, y_pred)
    return {
        "n": int(len(y_true)),
        "positive_rate": float(y_true.mean()),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "fpr": float(fpr),
        "fnr": float(fnr),
        "mean_pred_score": float(y_prob.mean()),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Inference helper
# ─────────────────────────────────────────────────────────────────────────────

def _run_inference(
    texts: List[str],
    classifier,
    batch_size: int = 64,
) -> np.ndarray:
    """Run pipeline in batches; return array of toxic probabilities."""
    probs = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        outputs = classifier(batch, truncation=True, max_length=128)
        for out in outputs:
            # pipeline label may be LABEL_0/LABEL_1 or toxic/non_toxic
            label = out["label"].lower()
            score = out["score"]
            if "1" in label or "toxic" in label:
                probs.append(score)
            else:
                probs.append(1.0 - score)
    return np.array(probs, dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Main evaluation
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_bias(
    cfg: Dict[str, Any],
    model_dir: str,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    data_cfg = cfg["data"]
    bias_cfg = cfg["bias"]
    identity_cols: List[str] = bias_cfg["identity_columns"]
    fairness_threshold: float = bias_cfg["fairness_threshold"]

    # ── Load model & tokenizer ────────────────────────────────────────────────
    logger.info("Loading model from %s", model_dir)
    classifier = pipeline(
        "text-classification",
        model=model_dir,
        tokenizer=model_dir,
        device=0 if torch.cuda.is_available() else -1,
        return_all_scores=False,
    )

    # ── Load dataset with identity annotations ────────────────────────────────
    logger.info("Loading dataset for bias evaluation …")
    try:
        raw = load_dataset(data_cfg["dataset_name"], split="train")
        df = raw.to_pandas()
        available_identity = [c for c in identity_cols if c in df.columns]
        text_col = data_cfg["text_column"]
        label_col = data_cfg["label_column"]
        df = df[[text_col, label_col] + available_identity].dropna(subset=[text_col, label_col])
        df[label_col] = (df[label_col] >= 0.5).astype(int)
    except Exception as exc:
        logger.warning("Real dataset unavailable (%s); using synthetic fallback.", exc)
        df, available_identity = _synthetic_bias_data()
        text_col, label_col = "comment_text", "toxic"

    logger.info("Bias eval dataset: %d rows, %d identity columns", len(df), len(available_identity))

    # ── Run inference on whole dataset ────────────────────────────────────────
    logger.info("Running inference …")
    y_prob = _run_inference(df[text_col].tolist(), classifier)
    y_pred = (y_prob >= threshold).astype(int)
    y_true = df[label_col].values

    # ── Overall baseline ──────────────────────────────────────────────────────
    overall = _subgroup_metrics(y_true, y_pred, y_prob)
    logger.info(
        "Overall → accuracy=%.4f  f1=%.4f  fpr=%.4f  fnr=%.4f",
        overall["accuracy"], overall["f1"], overall["fpr"], overall["fnr"],
    )

    # ── Per-subgroup evaluation ───────────────────────────────────────────────
    subgroup_results: Dict[str, Dict] = {}
    violations: List[str] = []

    for col in available_identity:
        mask = df[col].fillna(0).astype(float) >= 0.5
        if mask.sum() < 20:
            logger.debug("Skipping %s (n=%d < 20)", col, mask.sum())
            continue
        sg = _subgroup_metrics(y_true[mask], y_pred[mask], y_prob[mask])
        sg["gap_f1"]      = sg["f1"]  - overall["f1"]
        sg["gap_accuracy"]= sg["accuracy"] - overall["accuracy"]
        sg["gap_fpr"]     = sg["fpr"]  - overall["fpr"]
        subgroup_results[col] = sg

        if abs(sg["gap_f1"]) > fairness_threshold:
            violations.append(
                f"{col}: f1_gap={sg['gap_f1']:+.4f} (threshold ±{fairness_threshold})"
            )
        logger.info(
            "  %-40s  n=%5d  f1=%.4f  gap_f1=%+.4f  fpr=%.4f",
            col, sg["n"], sg["f1"], sg["gap_f1"], sg["fpr"],
        )

    # ── Fairness verdict ──────────────────────────────────────────────────────
    passed_fairness = len(violations) == 0
    if passed_fairness:
        logger.info("FAIRNESS CHECK PASSED — all subgroup gaps within threshold.")
    else:
        logger.warning("FAIRNESS CHECK FAILED — violations:\n  %s", "\n  ".join(violations))

    report = {
        "overall": overall,
        "subgroups": subgroup_results,
        "fairness_threshold": fairness_threshold,
        "violations": violations,
        "passed_fairness": passed_fairness,
        "identity_columns_evaluated": available_identity,
    }

    # ── Save report ───────────────────────────────────────────────────────────
    out_path = Path(cfg["paths"]["bias_report_path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    logger.info("Bias report saved to %s", out_path)

    return report


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic fallback
# ─────────────────────────────────────────────────────────────────────────────

def _synthetic_bias_data():
    rng = np.random.default_rng(0)
    n = 500
    identity_cols = ["male", "female", "black", "white", "muslim", "christian"]
    df = pd.DataFrame({
        "comment_text": [f"sample comment number {i}" for i in range(n)],
        "toxic": rng.binomial(1, 0.25, n),
    })
    for col in identity_cols:
        df[col] = rng.binomial(1, 0.2, n).astype(float)
    return df, identity_cols


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bias evaluation for toxicity model")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model_dir", default="artifacts/toxicity_model")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    cfg = load_config(args.config)
    report = evaluate_bias(cfg, args.model_dir, threshold=args.threshold)

    print(f"\nFairness check passed: {report['passed_fairness']}")
    if report["violations"]:
        print("Violations:")
        for v in report["violations"]:
            print(f"  {v}")


if __name__ == "__main__":
    main()
