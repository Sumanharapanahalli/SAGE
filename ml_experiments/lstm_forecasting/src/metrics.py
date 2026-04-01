"""
metrics.py — Regression metrics appropriate for multi-step time-series forecasting.

Metrics
-------
MAE   — Mean Absolute Error (same units as target, easy to interpret)
RMSE  — Root Mean Squared Error (penalises large errors more)
MAPE  — Mean Absolute Percentage Error (scale-free, avoid near-zero targets)
sMAPE — Symmetric MAPE (bounded [0, 200%], handles zero targets)

All functions accept (y_true, y_pred) as numpy arrays of shape
(n_windows, horizon) or (n_samples,) and return scalar floats.
"""

from __future__ import annotations

import numpy as np


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    """MAPE in percent.  Skips entries where |y_true| < eps."""
    mask = np.abs(y_true) > eps
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    """sMAPE in percent — symmetric, bounded [0, 200%]."""
    denom = (np.abs(y_true) + np.abs(y_pred)) / 2 + eps
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100)


def per_horizon_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    """RMSE for each forecast step individually.

    Args:
        y_true: (n_windows, horizon)
        y_pred: (n_windows, horizon)

    Returns:
        (horizon,) RMSE per step
    """
    return np.sqrt(np.mean((y_true - y_pred) ** 2, axis=0))


def compute_all(y_true: np.ndarray, y_pred: np.ndarray, label: str = "") -> dict:
    """Return a dict with all metrics (suitable for MLflow logging)."""
    prefix = f"{label}_" if label else ""
    result = {
        f"{prefix}mae": mae(y_true, y_pred),
        f"{prefix}rmse": rmse(y_true, y_pred),
        f"{prefix}mape": mape(y_true, y_pred),
        f"{prefix}smape": smape(y_true, y_pred),
    }
    per_h = per_horizon_rmse(y_true, y_pred)
    for h, v in enumerate(per_h, start=1):
        result[f"{prefix}rmse_h{h}"] = float(v)
    return result
