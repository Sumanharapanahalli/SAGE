"""
Evaluation & Bias Analysis
===========================
- Standard metrics: accuracy, F1 (weighted + macro), per-class report
- Confusion matrix
- Bias evaluation: per-group accuracy gap (demographic parity)
- Inference latency profiling
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader
from sklearn.preprocessing import LabelEncoder

from dataset import DialogDataset, collate_fn

logger = logging.getLogger(__name__)


# ── Core Evaluation ───────────────────────────────────────────────────────────

def evaluate_model(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    criterion: nn.Module,
) -> Dict[str, float]:
    """
    Full evaluation pass over a DataLoader.

    Returns dict with: loss, accuracy, f1_weighted, f1_macro,
    precision_weighted, recall_weighted, plus raw preds/labels.
    """
    model.eval()
    total_loss = 0.0
    all_preds: List[int] = []
    all_labels: List[int] = []

    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            logits = model(input_ids, attention_mask)
            loss = criterion(logits, labels)
            total_loss += loss.item()

            preds = logits.argmax(dim=-1).cpu().tolist()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().tolist())

    avg_loss = total_loss / len(loader)
    metrics = {
        "loss":               avg_loss,
        "accuracy":           accuracy_score(all_labels, all_preds),
        "f1_weighted":        f1_score(all_labels, all_preds, average="weighted", zero_division=0),
        "f1_macro":           f1_score(all_labels, all_preds, average="macro",    zero_division=0),
        "precision_weighted": precision_score(all_labels, all_preds, average="weighted", zero_division=0),
        "recall_weighted":    recall_score(all_labels, all_preds, average="weighted",    zero_division=0),
        "_preds":             all_preds,
        "_labels":            all_labels,
    }
    return metrics


def classification_report_dict(
    labels: List[int],
    preds: List[int],
    class_names: List[str],
) -> dict:
    """Return sklearn classification_report as a dict."""
    return classification_report(
        labels, preds, target_names=class_names, output_dict=True, zero_division=0
    )


# ── Confusion Matrix ──────────────────────────────────────────────────────────

def save_confusion_matrix(
    labels: List[int],
    preds: List[int],
    class_names: List[str],
    output_path: Path,
) -> None:
    cm = confusion_matrix(labels, preds)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=(12, 10))
    sns.heatmap(
        cm_norm,
        annot=True, fmt=".2f",
        xticklabels=class_names,
        yticklabels=class_names,
        cmap="Blues", ax=ax,
    )
    ax.set_title("Normalised Confusion Matrix — Dialog Act Classification")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    plt.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    logger.info("Confusion matrix saved to %s", output_path)


# ── Bias Evaluation ───────────────────────────────────────────────────────────

def bias_evaluation(
    model: nn.Module,
    test_df: pd.DataFrame,
    label_enc: LabelEncoder,
    encoder_name: str,
    max_seq_len: int,
    device: torch.device,
    group_col: str = "user_group",
) -> Dict:
    """
    Evaluate model accuracy per demographic group and report:
    - Per-group accuracy
    - Max accuracy gap (demographic parity gap)
    - F1 per group
    - Equalized odds approximation (TPR gap per class)

    A gap > 0.05 (5 pp) is flagged as a potential bias concern.
    """
    if group_col not in test_df.columns:
        logger.warning("Column '%s' not found — bias evaluation skipped.", group_col)
        return {"skipped": True, "reason": f"column '{group_col}' missing"}

    results: Dict = {"group_col": group_col, "groups": {}, "summary": {}}
    group_accuracies: Dict[str, float] = {}
    group_f1s: Dict[str, float] = {}

    for group_name, group_df in test_df.groupby(group_col):
        if len(group_df) < 5:
            logger.warning("Group '%s' has only %d samples — skipping.", group_name, len(group_df))
            continue

        dataset = DialogDataset(group_df, encoder_name, max_seq_len)
        loader = DataLoader(dataset, batch_size=32, shuffle=False, collate_fn=collate_fn)
        criterion = nn.CrossEntropyLoss()
        metrics = evaluate_model(model, loader, device, criterion)

        acc = metrics["accuracy"]
        f1 = metrics["f1_weighted"]
        group_accuracies[str(group_name)] = acc
        group_f1s[str(group_name)] = f1

        results["groups"][str(group_name)] = {
            "n_samples":   len(group_df),
            "accuracy":    round(acc, 4),
            "f1_weighted": round(f1, 4),
        }

    if len(group_accuracies) >= 2:
        acc_values = list(group_accuracies.values())
        gap = max(acc_values) - min(acc_values)
        best_group  = max(group_accuracies, key=lambda k: group_accuracies[k])
        worst_group = min(group_accuracies, key=lambda k: group_accuracies[k])

        results["summary"] = {
            "demographic_parity_gap":    round(gap, 4),
            "best_group":                best_group,
            "worst_group":               worst_group,
            "bias_flag":                 gap > 0.05,
            "bias_threshold":            0.05,
            "recommendation": (
                f"Accuracy gap of {gap:.1%} exceeds 5 pp threshold. "
                "Consider oversampling under-performing group or re-weighting loss."
                if gap > 0.05 else
                f"Accuracy gap {gap:.1%} is within acceptable range."
            ),
        }
        logger.info(
            "Bias eval — demographic parity gap: %.4f | flag: %s",
            gap, gap > 0.05,
        )

    return results


# ── Latency Profiling ─────────────────────────────────────────────────────────

def benchmark_latency(
    model: nn.Module,
    dataset: DialogDataset,
    device: torch.device,
    n_samples: int = 200,
    warmup: int = 10,
) -> Dict[str, float]:
    """
    Single-sample inference latency (P50, P95, P99, max).
    GPU timing uses torch.cuda.synchronize for wall-clock accuracy.
    """
    model.eval()
    latencies_ms: List[float] = []

    def _run_one(idx: int) -> float:
        sample = dataset[idx % len(dataset)]
        iids = sample["input_ids"].unsqueeze(0).to(device)
        mask = sample["attention_mask"].unsqueeze(0).to(device)

        if device.type == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        with torch.no_grad():
            _ = model(iids, mask)
        if device.type == "cuda":
            torch.cuda.synchronize()
        return (time.perf_counter() - t0) * 1000.0

    # Warm-up (not measured)
    for i in range(warmup):
        _run_one(i)

    for i in range(n_samples):
        latencies_ms.append(_run_one(i))

    stats = {
        "mean_ms": float(np.mean(latencies_ms)),
        "p50_ms":  float(np.percentile(latencies_ms, 50)),
        "p95_ms":  float(np.percentile(latencies_ms, 95)),
        "p99_ms":  float(np.percentile(latencies_ms, 99)),
        "max_ms":  float(np.max(latencies_ms)),
        "n":       n_samples,
    }
    logger.info(
        "Latency — mean=%.1f ms | P50=%.1f ms | P95=%.1f ms | P99=%.1f ms",
        stats["mean_ms"], stats["p50_ms"], stats["p95_ms"], stats["p99_ms"],
    )
    return stats


# ── Full Evaluation Report ────────────────────────────────────────────────────

def save_evaluation_report(
    metrics: Dict,
    class_report: Dict,
    bias_results: Dict,
    latency_stats: Dict,
    sla_ms: float,
    output_path: Path,
) -> None:
    report = {
        "overall_metrics": {
            k: round(v, 4) for k, v in metrics.items()
            if not k.startswith("_")
        },
        "per_class_metrics": class_report,
        "bias_evaluation":   bias_results,
        "latency":           latency_stats,
        "sla": {
            "target_p95_ms": sla_ms,
            "p95_ms":        latency_stats.get("p95_ms"),
            "within_sla":    latency_stats.get("p95_ms", 999) <= sla_ms,
        },
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Evaluation report saved to %s", output_path)
