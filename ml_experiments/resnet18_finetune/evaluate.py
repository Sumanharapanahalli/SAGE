"""
evaluate.py — Comprehensive evaluation: accuracy, per-class F1, confusion matrix.

Can be imported from train.py or run standalone:
    python evaluate.py --checkpoint checkpoints/best_model.pt --config config.yaml
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import numpy as np
import seaborn as sns
import torch
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    top_k_accuracy_score,
)
from torch.utils.data import DataLoader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

@torch.no_grad()
def run_evaluation(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    class_names: list[str],
    split_name: str = "test",
) -> dict:
    """
    Returns a metrics dict:
        accuracy, top5_accuracy, macro_f1, weighted_f1,
        per_class_f1 (dict), classification_report (str)
    """
    model.eval()
    all_preds: list[int]   = []
    all_labels: list[int]  = []
    all_probs: list[np.ndarray] = []

    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        logits = model(images)
        probs  = torch.softmax(logits, dim=1).cpu().numpy()
        preds  = logits.argmax(dim=1).cpu().numpy()
        all_preds.extend(preds.tolist())
        all_labels.extend(labels.numpy().tolist())
        all_probs.append(probs)

    y_true  = np.array(all_labels)
    y_pred  = np.array(all_preds)
    y_probs = np.vstack(all_probs)

    accuracy     = float((y_true == y_pred).mean())
    top5_acc     = top_k_accuracy_score(y_true, y_probs, k=min(5, len(class_names)))
    macro_f1     = float(f1_score(y_true, y_pred, average="macro",    zero_division=0))
    weighted_f1  = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
    per_class_f1_arr = f1_score(y_true, y_pred, average=None, zero_division=0)
    per_class_f1 = {cls: float(per_class_f1_arr[i]) for i, cls in enumerate(class_names)}

    report = classification_report(y_true, y_pred, target_names=class_names, zero_division=0)

    metrics = {
        "accuracy":    accuracy,
        "top5_accuracy": top5_acc,
        "macro_f1":    macro_f1,
        "weighted_f1": weighted_f1,
        "per_class_f1": per_class_f1,
        "classification_report": report,
    }

    logger.info(
        "[%s] accuracy=%.4f | top-5=%.4f | macro_f1=%.4f | weighted_f1=%.4f",
        split_name.upper(), accuracy, top5_acc, macro_f1, weighted_f1,
    )
    logger.info("\n%s", report)

    return metrics


# ---------------------------------------------------------------------------
# Confusion matrix plot
# ---------------------------------------------------------------------------

def plot_confusion_matrix(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    class_names: list[str],
    save_path: str = "confusion_matrix.png",
) -> str:
    model.eval()
    all_preds, all_labels = [], []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            preds  = model(images).argmax(dim=1).cpu().numpy()
            all_preds.extend(preds.tolist())
            all_labels.extend(labels.numpy().tolist())

    cm = confusion_matrix(all_labels, all_preds)
    cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        cm_norm, annot=True, fmt=".2f", cmap="Blues",
        xticklabels=class_names, yticklabels=class_names, ax=ax,
    )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Normalised Confusion Matrix")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150)
    plt.close(fig)
    logger.info("Confusion matrix saved to %s", save_path)
    return save_path


# ---------------------------------------------------------------------------
# Log metrics to mlflow
# ---------------------------------------------------------------------------

def log_metrics_to_mlflow(metrics: dict, prefix: str = "test") -> None:
    mlflow.log_metric(f"{prefix}_accuracy",    metrics["accuracy"])
    mlflow.log_metric(f"{prefix}_top5_accuracy", metrics.get("top5_accuracy", 0.0))
    mlflow.log_metric(f"{prefix}_macro_f1",    metrics["macro_f1"])
    mlflow.log_metric(f"{prefix}_weighted_f1", metrics["weighted_f1"])
    for cls, f1 in metrics["per_class_f1"].items():
        safe_cls = cls.replace(" ", "_")
        mlflow.log_metric(f"{prefix}_f1_{safe_cls}", f1)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

def _main() -> None:
    import yaml
    from dataset import load_splits
    from model import build_model

    parser = argparse.ArgumentParser(description="Evaluate a trained ResNet-18 checkpoint.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _, _, test_loader, class_names = load_splits(cfg)

    model = build_model(cfg).to(device)
    ckpt  = torch.load(args.checkpoint, map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    logger.info("Loaded checkpoint from %s (epoch %d)", args.checkpoint, ckpt.get("epoch", -1))

    metrics = run_evaluation(model, test_loader, device, class_names, split_name="test")
    plot_confusion_matrix(model, test_loader, device, class_names)

    target = 0.85
    status = "PASS" if metrics["accuracy"] >= target else "FAIL"
    print(f"\n{'='*50}")
    print(f"Test accuracy: {metrics['accuracy']:.4f} ({status} — target ≥{target:.0%})")
    print(f"{'='*50}")


if __name__ == "__main__":
    _main()
