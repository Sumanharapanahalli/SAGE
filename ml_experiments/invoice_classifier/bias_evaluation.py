"""
Invoice Classifier — Bias Evaluation
======================================
Evaluates model fairness across sensitive demographic/operational attributes:
  - Demographic parity (selection rate by group)
  - Equalized odds (TPR/FPR by group)
  - Per-group accuracy, F1, and prediction rate
  - Saves a structured bias_report.json

Uses fairlearn for standardised metric computation.
"""

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from fairlearn.metrics import (
    MetricFrame,
    demographic_parity_difference,
    equalized_odds_difference,
    false_negative_rate,
    false_positive_rate,
    selection_rate,
)
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("invoice_classifier.bias")

CONFIG_PATH = Path(__file__).parent / "config.yaml"
ARTIFACT_DIR = Path(__file__).parent / "artifacts"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def load_artifacts(artifact_dir: Path):
    model = joblib.load(artifact_dir / "model.joblib")
    tfidf = joblib.load(artifact_dir / "tfidf.joblib")
    scaler = joblib.load(artifact_dir / "scaler.joblib")
    ohe = joblib.load(artifact_dir / "ohe.joblib")
    le = joblib.load(artifact_dir / "label_encoder.joblib")
    return model, tfidf, scaler, ohe, le


def featurize(df, text_cols, num_cols, cat_cols, tfidf, scaler, ohe) -> np.ndarray:
    text = df[text_cols].fillna("").agg(" ".join, axis=1)
    num = df[num_cols].fillna(0).astype(float)
    cat = df[cat_cols].fillna("unknown")
    return np.hstack([
        tfidf.transform(text).toarray(),
        scaler.transform(num),
        ohe.transform(cat),
    ])


def per_class_metrics(y_true, y_pred, classes):
    """Per-class accuracy and F1 by binarizing each class."""
    results = {}
    for i, cls in enumerate(classes):
        y_t_bin = (y_true == i).astype(int)
        y_p_bin = (y_pred == i).astype(int)
        results[cls] = {
            "accuracy": round(accuracy_score(y_t_bin, y_p_bin), 4),
            "f1": round(f1_score(y_t_bin, y_p_bin, zero_division=0), 4),
            "selection_rate": round(float(y_p_bin.mean()), 4),
        }
    return results


def evaluate_bias(cfg: dict, artifact_dir: Path = ARTIFACT_DIR) -> dict:
    """
    Compute fairness metrics for each sensitive attribute listed in config.
    Returns a structured bias report dict.
    """
    from train import generate_synthetic_data  # local import to avoid circular

    seed = cfg["experiment"]["seed"]
    text_cols = cfg["data"]["text_columns"]
    num_cols = cfg["data"]["numeric_columns"]
    cat_cols = cfg["data"]["categorical_columns"]
    target = cfg["data"]["target_column"]
    sensitive_cols = cfg["bias"]["sensitive_columns"]

    # Load test split (reproduce the same split as training)
    df = generate_synthetic_data(seed=seed)
    le_target = LabelEncoder().fit(df[target])
    y_all = le_target.transform(df[target])

    _, df_test, _, y_test = train_test_split(
        df, y_all,
        test_size=cfg["data"]["test_size"],
        stratify=y_all,
        random_state=seed,
    )
    df_test = df_test.reset_index(drop=True)

    model, tfidf, scaler, ohe, le = load_artifacts(artifact_dir)

    X_test = featurize(df_test, text_cols, num_cols, cat_cols, tfidf, scaler, ohe)
    y_pred = model.predict(X_test)

    bias_report = {
        "overall": {
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "macro_f1": round(f1_score(y_test, y_pred, average="macro"), 4),
        },
        "per_class": per_class_metrics(y_test, y_pred, le.classes_),
        "sensitive_groups": {},
    }

    for col in sensitive_cols:
        if col not in df_test.columns:
            logger.warning("Sensitive column '%s' not found in data — skipping.", col)
            continue

        sensitive_feature = df_test[col].astype(str)
        group_data = {}

        for cls_idx, cls_name in enumerate(le.classes_):
            y_bin_true = (y_test == cls_idx).astype(int)
            y_bin_pred = (y_pred == cls_idx).astype(int)

            mf = MetricFrame(
                metrics={
                    "accuracy": accuracy_score,
                    "selection_rate": selection_rate,
                    "false_positive_rate": false_positive_rate,
                    "false_negative_rate": false_negative_rate,
                },
                y_true=y_bin_true,
                y_pred=y_bin_pred,
                sensitive_features=sensitive_feature,
            )

            dp_diff = demographic_parity_difference(
                y_bin_true, y_bin_pred, sensitive_features=sensitive_feature
            )
            eo_diff = equalized_odds_difference(
                y_bin_true, y_bin_pred, sensitive_features=sensitive_feature
            )

            group_data[cls_name] = {
                "demographic_parity_difference": round(float(dp_diff), 4),
                "equalized_odds_difference": round(float(eo_diff), 4),
                "per_group_accuracy": {
                    k: round(float(v), 4)
                    for k, v in mf.by_group["accuracy"].items()
                },
                "per_group_selection_rate": {
                    k: round(float(v), 4)
                    for k, v in mf.by_group["selection_rate"].items()
                },
                "flagged": abs(dp_diff) > 0.10 or abs(eo_diff) > 0.10,
            }

        # Aggregate flag: any class flagged?
        any_flagged = any(v["flagged"] for v in group_data.values())
        bias_report["sensitive_groups"][col] = {
            "per_class": group_data,
            "any_bias_flagged": any_flagged,
        }

        logger.info(
            "Bias [%s] — any_flagged=%s  dp_diffs=%s",
            col,
            any_flagged,
            {cls: round(group_data[cls]["demographic_parity_difference"], 3)
             for cls in group_data},
        )

    overall_flagged = any(
        v["any_bias_flagged"]
        for v in bias_report["sensitive_groups"].values()
    )
    bias_report["overall_bias_flagged"] = overall_flagged

    # Save
    out_path = artifact_dir / "bias_report.json"
    with open(out_path, "w") as f:
        json.dump(bias_report, f, indent=2)
    logger.info("Bias report saved to %s", out_path)

    return bias_report


if __name__ == "__main__":
    cfg = load_config()
    report = evaluate_bias(cfg)
    print(json.dumps(report, indent=2, default=str))
