"""
evaluate.py — Evaluation, inverse-transform, and comparison table.

Inverse-transforming predictions
---------------------------------
After predicting in scaled space, we apply scaler.inverse_transform()
to recover original units.  The scaler was fit only on training data,
so this operation is leakage-free in both directions.

Comparison report
-----------------
Prints a markdown table comparing LSTM vs ARIMA across all metrics
and per-horizon RMSE profile.
"""

from __future__ import annotations

import logging
from typing import Dict

import numpy as np
from sklearn.preprocessing import MinMaxScaler

from .metrics import compute_all, per_horizon_rmse

logger = logging.getLogger(__name__)


def inverse_scale(arr: np.ndarray, scaler: MinMaxScaler) -> np.ndarray:
    """Inverse-scale a (N, H) or (N,) array using a pre-fit scaler."""
    original_shape = arr.shape
    flat = arr.reshape(-1, 1)
    unscaled = scaler.inverse_transform(flat)
    return unscaled.reshape(original_shape).astype(np.float32)


def evaluate_model(
    y_true_scaled: np.ndarray,
    y_pred_scaled: np.ndarray,
    scaler: MinMaxScaler,
    label: str,
) -> Dict[str, float]:
    """Compute metrics in original units (after inverse-scaling).

    Args:
        y_true_scaled: (N, horizon) scaled actuals
        y_pred_scaled: (N, horizon) scaled predictions
        scaler:        fit scaler (train-only)
        label:         e.g. "lstm" or "arima"

    Returns:
        dict of metric_name → value
    """
    y_true = inverse_scale(y_true_scaled, scaler)
    y_pred = inverse_scale(y_pred_scaled, scaler)
    metrics = compute_all(y_true, y_pred, label=label)
    logger.info(
        "%s | MAE=%.4f RMSE=%.4f MAPE=%.2f%% sMAPE=%.2f%%",
        label.upper(),
        metrics[f"{label}_mae"],
        metrics[f"{label}_rmse"],
        metrics[f"{label}_mape"],
        metrics[f"{label}_smape"],
    )
    return metrics


def comparison_table(lstm_metrics: dict, arima_metrics: dict, horizon: int = 7) -> str:
    """Return a markdown comparison table."""
    rows = ["| Metric | LSTM | ARIMA | Winner |", "|--------|------|-------|--------|"]

    def _row(name: str, lstm_key: str, arima_key: str, lower_is_better: bool = True) -> str:
        l_val = lstm_metrics.get(lstm_key, float("nan"))
        a_val = arima_metrics.get(arima_key, float("nan"))
        if np.isnan(l_val) or np.isnan(a_val):
            winner = "—"
        elif lower_is_better:
            winner = "LSTM" if l_val < a_val else "ARIMA"
        else:
            winner = "LSTM" if l_val > a_val else "ARIMA"
        return f"| {name} | {l_val:.4f} | {a_val:.4f} | {winner} |"

    rows.append(_row("MAE",   "lstm_mae",   "arima_mae"))
    rows.append(_row("RMSE",  "lstm_rmse",  "arima_rmse"))
    rows.append(_row("MAPE%", "lstm_mape",  "arima_mape"))
    rows.append(_row("sMAPE%","lstm_smape", "arima_smape"))
    rows.append("|  |  |  |  |")
    rows.append("| **Per-step RMSE** |  |  |  |")

    for h in range(1, horizon + 1):
        lk = f"lstm_rmse_h{h}"
        ak = f"arima_rmse_h{h}"
        rows.append(_row(f"  H+{h}", lk, ak))

    return "\n".join(rows)
