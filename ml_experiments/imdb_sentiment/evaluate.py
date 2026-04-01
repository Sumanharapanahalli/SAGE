"""
Evaluation utilities for binary sentiment classification.

Metrics reported
----------------
- Accuracy
- Precision / Recall / F1  (binary + macro)
- ROC-AUC
- Matthews Correlation Coefficient (MCC)
- Confusion matrix
- Classification report (full)

All metrics are computed on the held-out TEST split only.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None = None,
    label_names: list[str] | None = None,
) -> dict[str, Any]:
    """
    Compute a full suite of classification metrics.

    Parameters
    ----------
    y_true  : ground-truth labels (0/1)
    y_pred  : predicted labels (0/1)
    y_prob  : predicted probabilities for class 1 — required for ROC-AUC
    label_names : human-readable class names for the report

    Returns
    -------
    dict with scalar metrics + full classification_report string
    """
    label_names = label_names or ["negative", "positive"]

    metrics: dict[str, Any] = {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_binary": round(float(precision_score(y_true, y_pred)), 4),
        "recall_binary": round(float(recall_score(y_true, y_pred)), 4),
        "f1_binary": round(float(f1_score(y_true, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro")), 4),
        "mcc": round(float(matthews_corrcoef(y_true, y_pred)), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classification_report": classification_report(
            y_true, y_pred, target_names=label_names
        ),
    }

    if y_prob is not None:
        metrics["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)

    _log_summary(metrics)
    return metrics


def check_class_imbalance(
    y: np.ndarray, threshold: float = 0.3
) -> tuple[bool, dict[str, Any]]:
    """
    Flag class imbalance when the minority class fraction < ``threshold``.

    Returns (is_imbalanced, stats_dict).
    """
    classes, counts = np.unique(y, return_counts=True)
    total = len(y)
    fractions = {int(c): round(float(n / total), 4) for c, n in zip(classes, counts)}
    minority_frac = min(fractions.values())
    is_imbalanced = minority_frac < threshold

    stats = {
        "class_counts": {int(c): int(n) for c, n in zip(classes, counts)},
        "class_fractions": fractions,
        "minority_fraction": minority_frac,
        "is_imbalanced": is_imbalanced,
    }
    if is_imbalanced:
        logger.warning(
            "Class imbalance detected — minority fraction %.2f < threshold %.2f. "
            "Consider oversampling or class_weight='balanced'.",
            minority_frac,
            threshold,
        )
    return is_imbalanced, stats


def _log_summary(metrics: dict[str, Any]) -> None:
    logger.info(
        "Evaluation | acc=%.4f  f1_macro=%.4f  roc_auc=%s  mcc=%.4f",
        metrics["accuracy"],
        metrics["f1_macro"],
        metrics.get("roc_auc", "N/A"),
        metrics["mcc"],
    )
    logger.info("\n%s", metrics["classification_report"])
