"""
train.py — Fine-tune ResNet-18 on a custom 10-class dataset.

Features:
    • Stratified train / val / test split (no leakage)
    • Progressive layer unfreezing
    • Linear LR warmup + cosine annealing
    • Differential LRs (backbone vs. head)
    • Label-smoothing cross-entropy
    • Early stopping with best-weight restoration
    • MLflow experiment tracking (params, per-epoch metrics, artefacts)
    • Confusion matrix + classification report on test set

Usage:
    python train.py                         # uses config.yaml in cwd
    python train.py --config my_config.yaml
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import time
from pathlib import Path

import mlflow
import numpy as np
import torch
import torch.nn as nn
import yaml
from torch.optim import AdamW
from tqdm import tqdm

from dataset import load_splits
from early_stopping import build_early_stopping
from evaluate import log_metrics_to_mlflow, plot_confusion_matrix, run_evaluation
from model import apply_unfreeze_schedule, build_model
from scheduler import build_scheduler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ---------------------------------------------------------------------------
# One epoch
# ---------------------------------------------------------------------------

def train_one_epoch(
    model: nn.Module,
    loader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
    scaler: torch.cuda.amp.GradScaler,
) -> tuple[float, float]:
    model.train()
    total_loss = 0.0
    correct    = 0
    total      = 0

    for images, labels in tqdm(loader, desc="train", leave=False):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with torch.cuda.amp.autocast(enabled=device.type == "cuda"):
            logits = model(images)
            loss   = criterion(logits, labels)

        scaler.scale(loss).backward()
        # Gradient clipping prevents exploding gradients during warmup
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * labels.size(0)
        correct    += (logits.argmax(1) == labels).sum().item()
        total      += labels.size(0)

    return total_loss / total, correct / total


@torch.no_grad()
def validate(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    correct    = 0
    total      = 0

    for images, labels in tqdm(loader, desc="val  ", leave=False):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        with torch.cuda.amp.autocast(enabled=device.type == "cuda"):
            logits = model(images)
            loss   = criterion(logits, labels)
        total_loss += loss.item() * labels.size(0)
        correct    += (logits.argmax(1) == labels).sum().item()
        total      += labels.size(0)

    return total_loss / total, correct / total


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def save_checkpoint(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler,
    epoch: int,
    val_acc: float,
    path: str,
) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "epoch":            epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict(),
        "val_acc":          val_acc,
    }, path)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train(cfg: dict) -> dict:
    set_seed(cfg["experiment"]["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using device: %s", device)

    # ---- Data ----
    train_loader, val_loader, test_loader, class_names = load_splits(cfg)

    # ---- Model ----
    model = build_model(cfg).to(device)

    # ---- Optimiser (differential LRs) ----
    opt_cfg = cfg["optimizer"]
    peak_lr     = float(opt_cfg["lr"])
    backbone_lr = peak_lr * float(opt_cfg["backbone_lr_multiplier"])
    param_groups = model.get_param_groups(head_lr=peak_lr, backbone_lr=backbone_lr)
    optimizer = AdamW(param_groups, weight_decay=float(opt_cfg["weight_decay"]))

    # ---- Scheduler ----
    scheduler = build_scheduler(optimizer, cfg)

    # ---- Loss ----
    criterion = nn.CrossEntropyLoss(
        label_smoothing=cfg["training"]["label_smoothing"]
    ).to(device)

    # ---- Early stopping ----
    early_stop = build_early_stopping(cfg)

    # ---- AMP scaler ----
    scaler = torch.cuda.amp.GradScaler(enabled=device.type == "cuda")

    # ---- MLflow ----
    mlflow.set_tracking_uri(cfg["experiment"]["mlflow_tracking_uri"])
    mlflow.set_experiment(cfg["experiment"]["name"])

    with mlflow.start_run():
        # Log all config as flat params
        _log_cfg_flat(cfg)
        mlflow.log_param("device", str(device))
        mlflow.log_param("num_classes", len(class_names))
        mlflow.log_param("class_names", str(class_names))

        checkpoint_dir  = cfg["output"]["checkpoint_dir"]
        best_model_path = cfg["output"]["best_model_path"]
        best_val_acc    = 0.0

        for epoch in range(cfg["training"]["epochs"]):
            t0 = time.time()

            # Progressive unfreezing
            apply_unfreeze_schedule(model, cfg, epoch)

            # Train
            train_loss, train_acc = train_one_epoch(
                model, train_loader, optimizer, criterion, device, scaler
            )

            # Validate
            val_loss, val_acc = validate(model, val_loader, criterion, device)

            # Step scheduler (per epoch)
            scheduler.step()
            current_lr = scheduler.get_last_lr()

            epoch_time = time.time() - t0
            logger.info(
                "Epoch %3d/%d | train_loss=%.4f acc=%.4f | val_loss=%.4f acc=%.4f | "
                "lr_head=%.2e | %.1fs",
                epoch + 1, cfg["training"]["epochs"],
                train_loss, train_acc, val_loss, val_acc,
                current_lr[-1], epoch_time,
            )

            # MLflow per-epoch metrics
            step = epoch + 1
            mlflow.log_metrics({
                "train_loss": train_loss,
                "train_acc":  train_acc,
                "val_loss":   val_loss,
                "val_acc":    val_acc,
                "lr_head":    current_lr[-1],
                "lr_backbone": current_lr[0],
            }, step=step)

            # Save best checkpoint
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                save_checkpoint(model, optimizer, scheduler, epoch, val_acc, best_model_path)
                logger.info("  ↑ New best val_acc=%.4f — checkpoint saved.", val_acc)

            # Early stopping
            monitor_value = val_acc if cfg["early_stopping"]["monitor"] == "val_acc" else val_loss
            if early_stop(monitor_value, model, epoch + 1):
                logger.info("Early stopping at epoch %d.", epoch + 1)
                mlflow.log_param("stopped_epoch", early_stop.stopped_epoch)
                break

        # ---- Final evaluation on held-out test set ----
        logger.info("Loading best checkpoint for final evaluation: %s", best_model_path)
        ckpt = torch.load(best_model_path, map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])

        test_metrics = run_evaluation(model, test_loader, device, class_names, split_name="test")
        log_metrics_to_mlflow(test_metrics, prefix="test")

        cm_path = str(Path(checkpoint_dir) / "confusion_matrix.png")
        plot_confusion_matrix(model, test_loader, device, class_names, save_path=cm_path)
        mlflow.log_artifact(cm_path)
        mlflow.log_artifact(best_model_path)

        # ---- Target check ----
        target_acc = 0.85
        achieved   = test_metrics["accuracy"]
        status     = "PASS" if achieved >= target_acc else "FAIL"
        mlflow.log_param("target_achieved", status)
        logger.info(
            "\n%s\nTest accuracy: %.4f  (%s — target ≥%.0f%%)\n%s",
            "=" * 55, achieved, status, target_acc * 100, "=" * 55,
        )

        return test_metrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_cfg_flat(cfg: dict, prefix: str = "") -> None:
    for k, v in cfg.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            _log_cfg_flat(v, prefix=key)
        elif isinstance(v, list):
            mlflow.log_param(key, str(v))
        else:
            mlflow.log_param(key, v)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune ResNet-18 on a 10-class dataset.")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML.")
    args = parser.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    train(cfg)


if __name__ == "__main__":
    main()
