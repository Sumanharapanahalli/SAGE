"""
early_stopping.py — Early stopping with best-weight restoration.
"""

from __future__ import annotations

import copy
import logging
from typing import Optional

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class EarlyStopping:
    """
    Monitors a metric and stops training when it stops improving.

    Parameters
    ----------
    patience  : epochs to wait without improvement before stopping
    monitor   : 'val_acc' (higher=better) or 'val_loss' (lower=better)
    min_delta : minimum change that counts as improvement
    restore   : if True, model weights are restored to the best epoch on stop
    """

    def __init__(
        self,
        patience: int = 10,
        monitor: str = "val_acc",
        min_delta: float = 1e-3,
        restore: bool = True,
    ) -> None:
        self.patience   = patience
        self.monitor    = monitor
        self.min_delta  = min_delta
        self.restore    = restore
        self._higher_is_better = monitor == "val_acc"
        self._best_value: Optional[float] = None
        self._best_weights: Optional[dict] = None
        self._counter: int = 0
        self.stopped_epoch: int = 0

    @property
    def best(self) -> Optional[float]:
        return self._best_value

    def __call__(self, value: float, model: nn.Module, epoch: int) -> bool:
        """
        Returns True when training should stop.
        """
        improved = self._is_improvement(value)

        if improved:
            self._best_value = value
            self._counter    = 0
            if self.restore:
                self._best_weights = copy.deepcopy(model.state_dict())
            logger.debug("EarlyStopping: improvement %.4f → storing best weights.", value)
        else:
            self._counter += 1
            logger.debug(
                "EarlyStopping: no improvement (%d/%d) — best=%.4f current=%.4f",
                self._counter, self.patience, self._best_value or 0.0, value,
            )

        if self._counter >= self.patience:
            self.stopped_epoch = epoch
            if self.restore and self._best_weights:
                model.load_state_dict(self._best_weights)
                logger.info(
                    "EarlyStopping triggered at epoch %d. "
                    "Restored weights from best epoch (best %s=%.4f).",
                    epoch, self.monitor, self._best_value or 0.0,
                )
            else:
                logger.info(
                    "EarlyStopping triggered at epoch %d (best %s=%.4f).",
                    epoch, self.monitor, self._best_value or 0.0,
                )
            return True
        return False

    def _is_improvement(self, value: float) -> bool:
        if self._best_value is None:
            return True
        if self._higher_is_better:
            return value > self._best_value + self.min_delta
        return value < self._best_value - self.min_delta


def build_early_stopping(cfg: dict) -> EarlyStopping:
    es_cfg = cfg["early_stopping"]
    return EarlyStopping(
        patience=es_cfg["patience"],
        monitor=es_cfg["monitor"],
        min_delta=es_cfg["min_delta"],
        restore=es_cfg["restore_best_weights"],
    )
