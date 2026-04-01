"""
scheduler.py — LR warmup + cosine annealing scheduler.

Strategy:
    Phase 1 (epochs 0 → warmup_epochs-1):
        Linear warmup from lr * 1e-2 → peak_lr.
    Phase 2 (epochs warmup_epochs → max_epochs):
        CosineAnnealingLR from peak_lr → min_lr.

Both phases work with the PyTorch _LRScheduler interface so that
mlflow / logging of per-epoch LR just calls scheduler.get_last_lr().
"""

from __future__ import annotations

import math
import logging

import torch
from torch.optim import Optimizer
from torch.optim.lr_scheduler import _LRScheduler

logger = logging.getLogger(__name__)


class WarmupCosineScheduler(_LRScheduler):
    """
    Linear warmup followed by cosine annealing.

    Works with per-group LRs — each group's base_lr is treated as the
    peak LR for that group.
    """

    def __init__(
        self,
        optimizer: Optimizer,
        warmup_epochs: int,
        total_epochs: int,
        min_lr: float = 1e-6,
        last_epoch: int = -1,
    ) -> None:
        self.warmup_epochs = warmup_epochs
        self.total_epochs  = total_epochs
        self.min_lr        = min_lr
        super().__init__(optimizer, last_epoch)

    def get_lr(self) -> list[float]:
        epoch = self.last_epoch

        if epoch < self.warmup_epochs:
            # Linear warmup: scale from 1% to 100% of base_lr
            scale = 0.01 + 0.99 * (epoch / max(self.warmup_epochs - 1, 1))
            return [base_lr * scale for base_lr in self.base_lrs]

        # Cosine annealing
        cosine_epochs = self.total_epochs - self.warmup_epochs
        progress = (epoch - self.warmup_epochs) / max(cosine_epochs - 1, 1)
        cosine_factor = 0.5 * (1.0 + math.cos(math.pi * progress))

        return [
            self.min_lr + (base_lr - self.min_lr) * cosine_factor
            for base_lr in self.base_lrs
        ]


def build_scheduler(optimizer: Optimizer, cfg: dict) -> WarmupCosineScheduler:
    sched_cfg = cfg["scheduler"]
    train_cfg = cfg["training"]
    scheduler = WarmupCosineScheduler(
        optimizer=optimizer,
        warmup_epochs=sched_cfg["warmup_epochs"],
        total_epochs=train_cfg["epochs"],
        min_lr=sched_cfg["min_lr"],
    )
    logger.info(
        "Scheduler: linear warmup (%d epochs) → cosine annealing (%d epochs), min_lr=%.1e",
        sched_cfg["warmup_epochs"],
        train_cfg["epochs"] - sched_cfg["warmup_epochs"],
        sched_cfg["min_lr"],
    )
    return scheduler
