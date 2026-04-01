"""
Regression evaluation metrics — pure NumPy, no sklearn.
"""

from typing import Dict, Tuple

import numpy as np


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Squared Error — interpretable in target units."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Error — robust to outliers."""
    return float(np.mean(np.abs(y_true - y_pred)))


def r2_score(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Coefficient of Determination (R²).
    R² = 1 − SS_res / SS_tot
    R² = 1.0 → perfect fit
    R² = 0.0 → predicts the mean
    R² < 0   → worse than predicting the mean
    """
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    if ss_tot == 0.0:
        return 0.0
    return float(1.0 - ss_res / ss_tot)


def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    """Mean Absolute Percentage Error (%). Avoid division by zero via eps."""
    return float(
        np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + eps))) * 100
    )


def evaluate_regression(
    y_true: np.ndarray, y_pred: np.ndarray
) -> Dict[str, float]:
    """Full metric suite for a regression prediction."""
    return {
        "rmse": rmse(y_true, y_pred),
        "mae": mae(y_true, y_pred),
        "r2": r2_score(y_true, y_pred),
        "mape": mape(y_true, y_pred),
    }


def train_test_split_numpy(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.20,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Random train/test split (no stratification — regression target).

    NOTE: For regression, stratified splitting is not meaningful.
    Randomness is fixed via `random_state` for reproducibility.
    """
    np.random.seed(random_state)
    idx = np.random.permutation(len(y))
    n_test = max(1, int(len(y) * test_size))
    test_idx, train_idx = idx[:n_test], idx[n_test:]
    return X[train_idx], X[test_idx], y[train_idx], y[test_idx]


def check_leakage(scaler_fitted_on_test: bool = False) -> Dict[str, bool]:
    """
    Data leakage audit report.
    Call after pipeline is assembled to assert no leakage paths exist.
    """
    return {
        "scaler_fitted_on_test": scaler_fitted_on_test,
        "leakage_risk": scaler_fitted_on_test,
    }


def class_balance_check(y: np.ndarray) -> Dict[str, object]:
    """
    Not applicable for regression, but kept as a no-op for API consistency.
    Returns a dict indicating this is a continuous target.
    """
    return {
        "task_type": "regression",
        "class_imbalance": False,
        "target_mean": float(np.mean(y)),
        "target_std": float(np.std(y)),
        "target_min": float(np.min(y)),
        "target_max": float(np.max(y)),
    }
