"""
Data utilities for Boston Housing experiments
==============================================
- Load Boston Housing via fetch_openml (modern, no deprecation warnings)
- Data validation: NaN / Inf / target statistics
- Deterministic train/val/test split (no stratification — regression task)

Leakage prevention is enforced here:
  - split() returns raw numpy arrays
  - normalisation happens inside LinearRegressionGD.fit() on train data only
  - test data is NEVER passed to the scaler's fit step
"""

import logging
from typing import Dict, Any, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── Dataset loading ───────────────────────────────────────────────────────────

def load_boston_housing() -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Load Boston Housing dataset.

    Tries fetch_openml first (sklearn ≥ 1.0, no deprecation warnings).
    Falls back to the legacy load_boston() for sklearn < 1.2 environments.

    Returns
    -------
    X            : np.ndarray, shape (506, 13)
    y            : np.ndarray, shape (506,)  — MEDV in $1 000s
    feature_names: list[str]
    """
    # Primary: fetch_openml — works with sklearn >= 1.0, no warnings
    try:
        from sklearn.datasets import fetch_openml

        dataset = fetch_openml(
            name="boston",
            version=1,
            as_frame=True,
            parser="auto",
        )
        X = dataset.data.values.astype(float)
        y = dataset.target.values.astype(float)
        feature_names = list(dataset.data.columns)
        logger.info(
            "Boston Housing loaded via fetch_openml: shape=%s, target=%s",
            X.shape,
            y.shape,
        )
        return X, y, feature_names
    except Exception as exc:
        logger.warning("fetch_openml failed (%s); falling back to legacy API", exc)

    # Fallback: load_boston — deprecated in sklearn 1.2, removed in 1.4
    try:
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            from sklearn.datasets import load_boston  # type: ignore[attr-defined]

        data = load_boston()
        X = data.data.astype(float)
        y = data.target.astype(float)
        feature_names = list(data.feature_names)
        logger.info(
            "Boston Housing loaded via load_boston (legacy): shape=%s", X.shape
        )
        return X, y, feature_names
    except (ImportError, AttributeError):
        pass

    raise RuntimeError(
        "Could not load Boston Housing dataset. "
        "Ensure scikit-learn is installed and internet access is available for "
        "fetch_openml."
    )


# ── Validation ────────────────────────────────────────────────────────────────

def validate_data(
    X: np.ndarray,
    y: np.ndarray,
    name: str = "dataset",
) -> Dict[str, Any]:
    """
    Sanity-check array pair and return a structured report.

    Checks
    ------
    - NaN and Inf in X and y
    - Target distribution statistics
    - Leakage risk flag (always False here — leakage is prevented by design)
    - class_imbalance flag (N/A for regression — always False)
    """
    nan_X = int(np.isnan(X).sum())
    nan_y = int(np.isnan(y).sum())
    inf_X = int(np.isinf(X).sum())
    inf_y = int(np.isinf(y).sum())

    report: Dict[str, Any] = {
        "name": name,
        "n_samples": int(X.shape[0]),
        "n_features": int(X.shape[1]),
        "nan_X": nan_X,
        "nan_y": nan_y,
        "inf_X": inf_X,
        "inf_y": inf_y,
        "y_mean": float(y.mean()),
        "y_std": float(y.std()),
        "y_min": float(y.min()),
        "y_max": float(y.max()),
        # Leakage prevention: enforced by splitting before normalisation and
        # by fitting the scaler inside LinearRegressionGD.fit() on train only.
        "leakage_risk": False,
        # Regression task — class imbalance not applicable
        "class_imbalance": False,
    }

    if nan_X + nan_y > 0:
        logger.warning(
            "[%s] Found NaN: X=%d, y=%d — handle before training", name, nan_X, nan_y
        )
    if inf_X + inf_y > 0:
        logger.warning(
            "[%s] Found Inf: X=%d, y=%d — handle before training", name, inf_X, inf_y
        )

    logger.info(
        "[%s] n=%d  features=%d  y: μ=%.2f σ=%.2f [%.1f, %.1f]",
        name,
        report["n_samples"],
        report["n_features"],
        report["y_mean"],
        report["y_std"],
        report["y_min"],
        report["y_max"],
    )
    return report


# ── Train / val / test split ──────────────────────────────────────────────────

def train_test_split_reg(
    X: np.ndarray,
    y: np.ndarray,
    test_size: float = 0.20,
    val_size: float = 0.10,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Deterministic random split for regression tasks.

    Note on stratification: stratification applies to classification problems
    to preserve class distribution across folds. For continuous regression
    targets we use a simple random permutation with a fixed seed.

    Returns
    -------
    X_train, X_val, X_test, y_train, y_val, y_test
    """
    rng = np.random.default_rng(random_state)
    n = len(X)
    indices = rng.permutation(n)

    n_test = int(round(n * test_size))
    n_val = int(round(n * val_size))

    test_idx = indices[:n_test]
    val_idx = indices[n_test: n_test + n_val]
    train_idx = indices[n_test + n_val:]

    logger.info(
        "Split — train: %d  val: %d  test: %d  (total: %d)",
        len(train_idx),
        len(val_idx),
        len(test_idx),
        n,
    )
    return (
        X[train_idx], X[val_idx], X[test_idx],
        y[train_idx], y[val_idx], y[test_idx],
    )
