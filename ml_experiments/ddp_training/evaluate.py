"""
Evaluation metrics for multi-class classification.

Metrics reported:
  - Loss (cross-entropy)
  - Accuracy (micro)
  - F1 macro (imbalance-robust)
  - Precision / Recall macro
  - ROC-AUC (OvR macro, binary-aware)
  - Per-class classification report (logged, not returned in dict)
"""

import logging
from typing import Any, Dict

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


@torch.no_grad()
def evaluate(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    num_classes: int,
    split: str = "val",
) -> Dict[str, Any]:
    """
    Full forward pass over `loader`. Does not modify model state.

    Args:
        model:       The model (DDP-wrapped or bare — both work).
        loader:      DataLoader for the split to evaluate.
        device:      Target device.
        num_classes: Number of output classes.
        split:       Label prefix for returned metric keys (e.g. "val", "test").

    Returns:
        Dict of metric_name → float, all keyed with `split` prefix.
    """
    model.eval()
    criterion = nn.CrossEntropyLoss(reduction="sum")

    all_preds: list = []
    all_labels: list = []
    all_probs: list = []
    total_loss = 0.0
    total_samples = 0

    for X_batch, y_batch in loader:
        X_batch = X_batch.to(device, non_blocking=True)
        y_batch = y_batch.to(device, non_blocking=True)

        logits = model(X_batch)
        loss = criterion(logits, y_batch)

        probs = torch.softmax(logits, dim=-1)
        preds = logits.argmax(dim=-1)

        total_loss   += loss.item()
        total_samples += len(y_batch)

        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(y_batch.cpu().numpy())
        all_probs.extend(probs.cpu().numpy())

    preds_arr  = np.array(all_preds)
    labels_arr = np.array(all_labels)
    probs_arr  = np.array(all_probs)

    avg_loss  = total_loss / total_samples
    accuracy  = accuracy_score(labels_arr, preds_arr)
    f1        = f1_score(labels_arr, preds_arr, average="macro", zero_division=0)
    precision = precision_score(labels_arr, preds_arr, average="macro", zero_division=0)
    recall    = recall_score(labels_arr, preds_arr, average="macro", zero_division=0)

    try:
        if num_classes == 2:
            auc = roc_auc_score(labels_arr, probs_arr[:, 1])
        else:
            auc = roc_auc_score(
                labels_arr, probs_arr, multi_class="ovr", average="macro"
            )
    except ValueError as exc:
        logger.warning(f"AUC computation skipped: {exc}")
        auc = float("nan")

    # Full per-class report (info level — visible in log file, not returned)
    report = classification_report(
        labels_arr, preds_arr, zero_division=0, digits=4
    )
    logger.info(f"[{split}] Classification report:\n{report}")

    metrics: Dict[str, Any] = {
        f"{split}_loss":           round(avg_loss,  4),
        f"{split}_accuracy":       round(accuracy,  4),
        f"{split}_f1_macro":       round(f1,        4),
        f"{split}_precision_macro": round(precision, 4),
        f"{split}_recall_macro":   round(recall,    4),
        f"{split}_auc_ovr":        round(auc, 4) if not np.isnan(auc) else None,
    }

    logger.info(
        f"[{split}] " +
        " | ".join(f"{k.split('_', 1)[1]}={v}" for k, v in metrics.items())
    )
    return metrics
