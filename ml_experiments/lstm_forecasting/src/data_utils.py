"""
data_utils.py — Data loading, windowing, and temporal train/test splitting.

Key design decisions
---------------------
* Temporal split (no shuffling) prevents look-ahead leakage.
* MinMaxScaler is fit ONLY on training windows — test windows are transformed
  with the already-fit scaler.  This is the single most common source of
  data leakage in time-series ML.
* Windowing produces (X, y) pairs where X = lookback window, y = horizon.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import torch
from torch.utils.data import Dataset, DataLoader

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Synthetic data generator (replace with real data loader for production)
# ---------------------------------------------------------------------------

def generate_synthetic_series(n: int = 2000, noise_std: float = 0.5, seed: int = 42) -> np.ndarray:
    """Multi-component synthetic time series (trend + seasonal + noise)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)
    trend = 0.02 * t
    weekly = 3.0 * np.sin(2 * np.pi * t / 7)
    monthly = 1.5 * np.sin(2 * np.pi * t / 30)
    noise = rng.normal(0, noise_std, n)
    series = trend + weekly + monthly + noise
    logger.info("Generated synthetic series: length=%d, mean=%.3f, std=%.3f", n, series.mean(), series.std())
    return series.astype(np.float32)


# ---------------------------------------------------------------------------
# Window dataset
# ---------------------------------------------------------------------------

class TimeSeriesWindowDataset(Dataset):
    """Sliding-window dataset.

    Args:
        series: 1-D float32 array (already scaled).
        lookback: encoder input length.
        horizon: decoder target length.
    """

    def __init__(self, series: np.ndarray, lookback: int, horizon: int) -> None:
        self.lookback = lookback
        self.horizon = horizon
        X, y = [], []
        for i in range(len(series) - lookback - horizon + 1):
            X.append(series[i : i + lookback])
            y.append(series[i + lookback : i + lookback + horizon])
        self.X = torch.tensor(np.array(X), dtype=torch.float32).unsqueeze(-1)  # (N, L, 1)
        self.y = torch.tensor(np.array(y), dtype=torch.float32)                # (N, H)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]


# ---------------------------------------------------------------------------
# Leakage-safe split + scaling
# ---------------------------------------------------------------------------

@dataclass
class SplitResult:
    train_series: np.ndarray
    test_series: np.ndarray
    scaler: MinMaxScaler
    train_raw: np.ndarray   # un-scaled, for ARIMA
    test_raw: np.ndarray


def temporal_split_and_scale(
    series: np.ndarray,
    train_ratio: float = 0.80,
) -> SplitResult:
    """Temporal (chronological) split.  Scaler fit on TRAIN only.

    For classification the system prompt mandates stratified splitting.
    For regression time-series the correct analogue is a temporal split —
    shuffling would introduce look-ahead leakage.
    """
    n = len(series)
    split_idx = int(n * train_ratio)

    train_raw = series[:split_idx].copy()
    test_raw = series[split_idx:].copy()

    # Fit scaler exclusively on training data — NEVER on test data
    scaler = MinMaxScaler(feature_range=(-1, 1))
    train_scaled = scaler.fit_transform(train_raw.reshape(-1, 1)).flatten()
    test_scaled = scaler.transform(test_raw.reshape(-1, 1)).flatten()

    logger.info(
        "Temporal split: train=%d (%.0f%%), test=%d (%.0f%%)",
        len(train_raw), train_ratio * 100,
        len(test_raw), (1 - train_ratio) * 100,
    )
    logger.info("Scaler fit on train only — leakage risk: NONE")

    return SplitResult(train_scaled, test_scaled, scaler, train_raw, test_raw)


# ---------------------------------------------------------------------------
# DataLoader factory
# ---------------------------------------------------------------------------

def make_dataloaders(
    split: SplitResult,
    lookback: int,
    horizon: int,
    batch_size: int,
    num_workers: int = 0,
) -> Tuple[DataLoader, DataLoader]:
    train_ds = TimeSeriesWindowDataset(split.train_series, lookback, horizon)
    test_ds = TimeSeriesWindowDataset(split.test_series, lookback, horizon)

    logger.info("Train windows: %d | Test windows: %d", len(train_ds), len(test_ds))

    train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True,  num_workers=num_workers)
    test_dl  = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    return train_dl, test_dl


# ---------------------------------------------------------------------------
# Class-imbalance check (N/A for regression — documented for completeness)
# ---------------------------------------------------------------------------

def check_class_imbalance(series: np.ndarray) -> dict:
    """For regression tasks class_imbalance is not applicable.
    Returns metadata about the target distribution instead."""
    return {
        "class_imbalance": False,
        "task_type": "regression",
        "target_mean": float(np.mean(series)),
        "target_std": float(np.std(series)),
        "target_min": float(np.min(series)),
        "target_max": float(np.max(series)),
    }
