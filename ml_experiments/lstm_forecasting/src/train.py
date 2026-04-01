"""
train.py — LSTM training loop with teacher-forcing annealing.

Design decisions
----------------
* Huber loss (smooth L1): robust to outliers — better than MSE for noisy series.
* Gradient clipping (max_norm=1.0): prevents exploding gradients in LSTM.
* Early stopping on validation loss (patience configurable).
* Teacher-forcing ratio is linearly annealed each epoch.
* All hyperparameters logged to MLflow at run start.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader

from .lstm_model import LSTMForecaster, teacher_forcing_ratio as tf_schedule

logger = logging.getLogger(__name__)


@dataclass
class TrainConfig:
    epochs: int = 60
    batch_size: int = 64
    learning_rate: float = 1e-3
    weight_decay: float = 1e-5
    patience: int = 10
    initial_teacher_forcing: float = 1.0
    final_teacher_forcing: float = 0.0
    grad_clip: float = 1.0
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class TrainResult:
    train_losses: list[float] = field(default_factory=list)
    val_losses: list[float] = field(default_factory=list)
    tf_ratios: list[float] = field(default_factory=list)
    best_val_loss: float = float("inf")
    best_epoch: int = 0
    stopped_early: bool = False


def train(
    model: LSTMForecaster,
    train_dl: DataLoader,
    val_dl: DataLoader,
    cfg: TrainConfig,
    mlflow_run=None,
) -> TrainResult:
    """Full training loop.

    Args:
        model:      LSTMForecaster (moved to device inside this function)
        train_dl:   Training DataLoader
        val_dl:     Validation DataLoader (typically the test split)
        cfg:        TrainConfig
        mlflow_run: active mlflow.ActiveRun (optional — skipped if None)

    Returns:
        TrainResult with per-epoch history
    """
    device = torch.device(cfg.device)
    model = model.to(device)

    criterion = nn.HuberLoss(delta=1.0)
    optimizer = AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    scheduler = ReduceLROnPlateau(optimizer, mode="min", patience=cfg.patience // 2, factor=0.5)

    result = TrainResult()
    best_state: Optional[dict] = None
    no_improve_counter = 0

    logger.info(
        "Training: device=%s epochs=%d batch=%d lr=%.0e TF %.1f→%.1f",
        cfg.device, cfg.epochs, cfg.batch_size,
        cfg.learning_rate, cfg.initial_teacher_forcing, cfg.final_teacher_forcing,
    )

    for epoch in range(cfg.epochs):
        tf_ratio = tf_schedule(epoch, cfg.epochs, cfg.initial_teacher_forcing, cfg.final_teacher_forcing)

        # ---- Train ----------------------------------------------------------
        model.train()
        running_loss = 0.0
        for x_batch, y_batch in train_dl:
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            preds = model(x_batch, target=y_batch, teacher_forcing_ratio=tf_ratio)
            loss = criterion(preds, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimizer.step()
            running_loss += loss.item() * x_batch.size(0)

        train_loss = running_loss / len(train_dl.dataset)

        # ---- Validate -------------------------------------------------------
        model.eval()
        val_running = 0.0
        with torch.no_grad():
            for x_batch, y_batch in val_dl:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device)
                preds = model(x_batch, teacher_forcing_ratio=0.0)   # no TF at eval
                val_running += criterion(preds, y_batch).item() * x_batch.size(0)
        val_loss = val_running / len(val_dl.dataset)

        scheduler.step(val_loss)
        result.train_losses.append(train_loss)
        result.val_losses.append(val_loss)
        result.tf_ratios.append(tf_ratio)

        if mlflow_run is not None:
            import mlflow
            mlflow.log_metrics(
                {"train_loss": train_loss, "val_loss": val_loss, "tf_ratio": tf_ratio},
                step=epoch,
            )

        if val_loss < result.best_val_loss:
            result.best_val_loss = val_loss
            result.best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve_counter = 0
        else:
            no_improve_counter += 1

        if epoch % 10 == 0 or epoch == cfg.epochs - 1:
            logger.info(
                "Epoch %3d/%d | train=%.4f val=%.4f | TF=%.2f | best=ep%d",
                epoch, cfg.epochs, train_loss, val_loss, tf_ratio, result.best_epoch,
            )

        if no_improve_counter >= cfg.patience:
            logger.info("Early stopping at epoch %d (patience=%d)", epoch, cfg.patience)
            result.stopped_early = True
            break

    # Restore best weights
    if best_state is not None:
        model.load_state_dict(best_state)
        logger.info("Restored best model from epoch %d (val_loss=%.4f)", result.best_epoch, result.best_val_loss)

    return result


# ---------------------------------------------------------------------------
# Inference helper
# ---------------------------------------------------------------------------

def predict_all(model: LSTMForecaster, dataloader: DataLoader, device: str = "cpu") -> np.ndarray:
    """Run inference over the full dataloader, return (N, horizon) array."""
    model.eval()
    dev = torch.device(device)
    model = model.to(dev)
    all_preds = []
    with torch.no_grad():
        for x_batch, _ in dataloader:
            preds = model(x_batch.to(dev), teacher_forcing_ratio=0.0)
            all_preds.append(preds.cpu().numpy())
    return np.concatenate(all_preds, axis=0)


def get_actuals(dataloader: DataLoader) -> np.ndarray:
    """Collect ground-truth y from a DataLoader."""
    ys = []
    for _, y_batch in dataloader:
        ys.append(y_batch.numpy())
    return np.concatenate(ys, axis=0)
