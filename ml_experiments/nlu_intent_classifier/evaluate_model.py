"""
evaluate_model.py — Comprehensive evaluation including bias analysis.

Metrics computed:
  - Accuracy (overall + per-class)
  - Macro / weighted F1, Precision, Recall
  - Top-K accuracy (K=3)
  - Matthews Correlation Coefficient (MCC) — robust to class imbalance
  - Confusion matrix
  - Per-slice accuracy/F1 for bias evaluation
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
    top_k_accuracy_score,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    preds: list[int],
    labels: list[int],
    class_names: list[str],
    prefix: str = "",
) -> dict[str, float]:
    """
    Compute a comprehensive metric suite.

    Args:
        preds:       Predicted label indices.
        labels:      Ground-truth label indices (may contain -1 for OOS).
        class_names: Ordered list of class name strings.
        prefix:      Prepended to metric keys (e.g. 'val', 'test').

    Returns:
        Flat dict of metric_name → float.
    """
    # Filter out OOS samples (label == -1) for standard metrics
    valid = [(p, l) for p, l in zip(preds, labels) if l >= 0]
    if not valid:
        logger.warning("No valid (non-OOS) samples found for evaluation.")
        return {}

    y_pred, y_true = zip(*valid)
    y_pred = np.array(y_pred)
    y_true = np.array(y_true)

    p = "" if not prefix else f"{prefix}_"
    results: dict[str, float] = {
        f"{p}accuracy":         round(accuracy_score(y_true, y_pred), 4),
        f"{p}f1_macro":         round(f1_score(y_true, y_pred, average="macro",   zero_division=0), 4),
        f"{p}f1_weighted":      round(f1_score(y_true, y_pred, average="weighted", zero_division=0), 4),
        f"{p}precision_macro":  round(precision_score(y_true, y_pred, average="macro",   zero_division=0), 4),
        f"{p}recall_macro":     round(recall_score(y_true, y_pred, average="macro",      zero_division=0), 4),
        f"{p}mcc":              round(float(matthews_corrcoef(y_true, y_pred)), 4),
    }

    # Top-3 accuracy (only meaningful with ≥3 classes)
    num_classes = len(class_names)
    if num_classes >= 3:
        # top_k_accuracy_score requires probability scores;
        # simulate with one-hot preds as a proxy (real use: pass logits)
        one_hot = np.eye(num_classes)[y_pred]
        results[f"{p}top3_accuracy"] = round(
            float(top_k_accuracy_score(y_true, one_hot, k=min(3, num_classes))), 4
        )

    # OOS detection rate
    oos_total  = sum(1 for l in labels if l == -1)
    oos_rate   = oos_total / max(len(labels), 1)
    results[f"{p}oos_rate"] = round(oos_rate, 4)

    # Per-class F1 (logged for diagnostic, not MLflow primary metrics)
    per_class_f1 = f1_score(y_true, y_pred, average=None, zero_division=0)
    results[f"{p}min_class_f1"] = round(float(per_class_f1.min()), 4)
    results[f"{p}max_class_f1"] = round(float(per_class_f1.max()), 4)

    # Full classification report to log
    report = classification_report(
        y_true, y_pred,
        target_names=[class_names[i] for i in range(num_classes) if i < len(class_names)],
        zero_division=0,
    )
    logger.info("Classification report (%s):\n%s", prefix, report)

    return results


# ---------------------------------------------------------------------------
# Confusion matrix helper
# ---------------------------------------------------------------------------

def get_confusion_matrix(
    preds: list[int],
    labels: list[int],
    class_names: list[str],
) -> dict[str, Any]:
    valid = [(p, l) for p, l in zip(preds, labels) if l >= 0]
    if not valid:
        return {}
    y_pred, y_true = map(np.array, zip(*valid))
    cm = confusion_matrix(y_true, y_pred)
    return {
        "matrix": cm.tolist(),
        "class_names": class_names,
    }


# ---------------------------------------------------------------------------
# Bias evaluation
# ---------------------------------------------------------------------------

def run_bias_evaluation(
    preds: list[int],
    labels: list[int],
    class_names: list[str],
    bias_slices: list[str] | None = None,
    slice_data: dict[str, list] | None = None,
) -> dict[str, Any]:
    """
    Evaluate model fairness across data slices.

    When `bias_slices` is empty (default), runs aggregate bias checks:
      - Per-class accuracy disparity
      - Worst-class vs best-class F1 gap
      - Error concentration (Gini coefficient over per-class errors)

    When `bias_slices` is provided, per-slice accuracy/F1 are computed
    if the corresponding columns are available in `slice_data`.

    Returns:
        Bias report dict — safe to serialize to JSON.
    """
    bias_slices = bias_slices or []
    slice_data  = slice_data or {}

    valid = [(p, l) for p, l in zip(preds, labels) if l >= 0]
    if not valid:
        return {"status": "no_valid_samples"}

    y_pred, y_true = map(np.array, zip(*valid))
    num_classes    = len(class_names)

    # ── Per-class accuracy ───────────────────────────────────────────
    per_class_correct = np.zeros(num_classes, dtype=int)
    per_class_total   = np.zeros(num_classes, dtype=int)
    for yt, yp in zip(y_true, y_pred):
        if 0 <= yt < num_classes:
            per_class_total[yt]   += 1
            per_class_correct[yt] += int(yt == yp)

    per_class_acc = np.where(
        per_class_total > 0,
        per_class_correct / per_class_total,
        np.nan,
    )

    valid_acc = per_class_acc[~np.isnan(per_class_acc)]
    acc_disparity = float(valid_acc.max() - valid_acc.min()) if len(valid_acc) else 0.0

    # ── Per-class F1 ────────────────────────────────────────────────
    per_class_f1 = f1_score(y_true, y_pred, average=None,
                             labels=list(range(num_classes)), zero_division=0)
    f1_gap = float(per_class_f1.max() - per_class_f1.min())

    # ── Error concentration (Gini) ───────────────────────────────────
    errors_per_class = per_class_total - per_class_correct
    gini = _gini(errors_per_class.astype(float))

    # ── Flag thresholds ──────────────────────────────────────────────
    flags: list[str] = []
    if acc_disparity > 0.20:
        flags.append(f"High per-class accuracy disparity: {acc_disparity:.2f}")
    if f1_gap > 0.30:
        flags.append(f"Large F1 gap between best/worst class: {f1_gap:.2f}")
    if gini > 0.60:
        flags.append(f"Error concentration (Gini={gini:.2f}) — model struggles on few classes")

    report: dict[str, Any] = {
        "per_class_accuracy":     {class_names[i]: round(float(v), 4)
                                   for i, v in enumerate(per_class_acc)
                                   if not np.isnan(v)},
        "per_class_f1":           {class_names[i]: round(float(v), 4)
                                   for i, v in enumerate(per_class_f1)},
        "accuracy_disparity":     round(acc_disparity, 4),
        "f1_gap":                 round(f1_gap, 4),
        "error_concentration_gini": round(gini, 4),
        "flags":                  flags,
        "bias_flag":              len(flags) > 0,
    }

    # ── Slice-level evaluation (when metadata available) ─────────────
    slice_results: dict[str, Any] = {}
    for col in bias_slices:
        if col not in slice_data:
            logger.warning("Bias slice column '%s' not in slice_data — skipping.", col)
            continue
        col_vals = np.array(slice_data[col])[np.array([l >= 0 for l in labels])]
        for val in np.unique(col_vals):
            mask = col_vals == val
            if mask.sum() < 10:
                continue
            slice_acc = accuracy_score(y_true[mask], y_pred[mask])
            slice_f1  = f1_score(y_true[mask], y_pred[mask],
                                  average="macro", zero_division=0)
            slice_results[f"{col}={val}"] = {
                "accuracy": round(float(slice_acc), 4),
                "f1_macro": round(float(slice_f1), 4),
                "n":        int(mask.sum()),
            }

    if slice_results:
        report["slice_evaluation"] = slice_results
        slice_accs = [v["accuracy"] for v in slice_results.values()]
        report["max_slice_acc_gap"] = round(max(slice_accs) - min(slice_accs), 4)

    if flags:
        logger.warning("Bias flags raised: %s", flags)
    else:
        logger.info("Bias evaluation: no significant disparity detected.")

    return report


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _gini(values: np.ndarray) -> float:
    """Gini coefficient of error concentration across classes (0=equal, 1=all in one)."""
    if values.sum() == 0:
        return 0.0
    sorted_v = np.sort(values)
    n = len(sorted_v)
    idx = np.arange(1, n + 1)
    return float((2 * (idx * sorted_v).sum() / (n * sorted_v.sum())) - (n + 1) / n)


# Re-export for convenience
from sklearn.metrics import f1_score  # noqa: E402 (needed by bias eval)
