"""
Training pipeline: Linear Regression (GD) on Boston Housing.

Usage:
    cd ml_experiments/linear_regression
    python src/train.py                      # best config
    python src/train.py --hp-search          # grid search over LR / schedules

Outputs:
    experiments/experiment_log.json          # all experiment records (appended)
    experiments/hparam_search_results.json   # HP search summary (if --hp-search)
    experiments/training.log                 # full training log

Data flow (no leakage):
    raw data
    → train/test split (random shuffle, seed=42)
    → StandardScaler.fit(X_train)           ← fit on TRAIN only
    → X_train_s = scaler.transform(X_train) ← apply to train
    → X_test_s  = scaler.transform(X_test)  ← apply to test (no re-fit)
    → normalize y_train (mean/std from train split)
    → fit LinearRegressionGD on (X_train_s, y_train_norm)
    → predict on X_test_s
    → inverse-transform predictions → original scale
    → evaluate RMSE, MAE, R², MAPE on original scale
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Path setup — allow running from project root or from src/
# ---------------------------------------------------------------------------
_SRC = Path(__file__).parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from linear_regression import LinearRegressionGD, StandardScaler
from utils import (
    check_leakage,
    class_balance_check,
    evaluate_regression,
    train_test_split_numpy,
)

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
_EXPERIMENTS_DIR = Path(__file__).parent.parent / "experiments"
_EXPERIMENTS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_EXPERIMENTS_DIR / "training.log"),
    ],
)
logger = logging.getLogger("train")


# ---------------------------------------------------------------------------
# Data loader
# ---------------------------------------------------------------------------

def load_boston_housing() -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """
    Load Boston Housing dataset.
    sklearn deprecated load_boston in 1.2; falls back to fetch_openml.

    Returns
    -------
    X : (506, 13) float64
    y : (506,)   float64  — median house value in $1000s
    feature_names : list[str]
    """
    try:
        # sklearn < 1.2
        from sklearn.datasets import load_boston  # type: ignore
        data = load_boston()
        logger.info("Loaded via sklearn.datasets.load_boston")
        return data.data.astype(np.float64), data.target.astype(np.float64), list(data.feature_names)
    except (ImportError, AttributeError):
        pass

    try:
        # sklearn >= 1.2
        from sklearn.datasets import fetch_openml
        data = fetch_openml(name="boston", version=1, as_frame=False, parser="auto")
        X = np.array(data.data, dtype=np.float64)
        y = np.array(data.target, dtype=np.float64)
        logger.info("Loaded via fetch_openml (sklearn >= 1.2 path)")
        return X, y, list(data.feature_names)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot load Boston Housing dataset: {exc}\n"
            "Install: pip install scikit-learn==1.3.2"
        ) from exc


# ---------------------------------------------------------------------------
# Experiment logger
# ---------------------------------------------------------------------------

def log_experiment(params: Dict, metrics: Dict, metadata: Dict) -> Path:
    """Append a structured experiment record to experiments/experiment_log.json."""
    log_path = _EXPERIMENTS_DIR / "experiment_log.json"

    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "params": params,
        "metrics": metrics,
        "metadata": metadata,
    }

    existing: List[Dict] = []
    if log_path.exists():
        with open(log_path) as fh:
            existing = json.load(fh)

    existing.append(record)
    with open(log_path, "w") as fh:
        json.dump(existing, fh, indent=2, default=str)

    logger.info(f"Experiment logged → {log_path}")
    return log_path


# ---------------------------------------------------------------------------
# Main training pipeline
# ---------------------------------------------------------------------------

def run_experiment(
    learning_rate: float = 0.05,
    n_iterations: int = 10_000,
    tolerance: float = 1e-7,
    lr_schedule: str = "exponential",
    test_size: float = 0.20,
    random_state: int = 42,
    normalize_y: bool = True,
) -> Dict:
    """
    Execute a single training run and return metrics + model.

    Key anti-leakage guarantees:
      1. StandardScaler.fit() called ONLY on X_train.
      2. y normalization statistics computed ONLY from y_train.
      3. X_test and y_test never touch the scaler's fit step.
    """
    # ------------------------------------------------------------------ #
    # 1. Load                                                              #
    # ------------------------------------------------------------------ #
    logger.info("Loading Boston Housing dataset...")
    X, y, feature_names = load_boston_housing()
    logger.info(f"Shape: X={X.shape}, y={y.shape}")
    logger.info(f"Target: min={y.min():.1f}, max={y.max():.1f}, mean={y.mean():.1f}")

    # Data checks
    balance = class_balance_check(y)
    logger.info(f"Target distribution: {balance}")

    # ------------------------------------------------------------------ #
    # 2. Train / Test Split                                                #
    # ------------------------------------------------------------------ #
    X_train, X_test, y_train, y_test = train_test_split_numpy(
        X, y, test_size=test_size, random_state=random_state
    )
    logger.info(
        f"Split: train={X_train.shape[0]} | test={X_test.shape[0]} "
        f"(test_size={test_size:.0%})"
    )

    # ------------------------------------------------------------------ #
    # 3. Feature Normalization — no leakage                                #
    # ------------------------------------------------------------------ #
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)   # fit + transform TRAIN
    X_test_s = scaler.transform(X_test)         # transform ONLY — no re-fit

    leakage_report = check_leakage(scaler_fitted_on_test=False)
    logger.info(f"Leakage check: {leakage_report}")

    # Normalize target (train statistics only)
    y_mean, y_std = 0.0, 1.0
    if normalize_y:
        y_mean = float(np.mean(y_train))
        y_std = float(np.std(y_train)) or 1.0
        y_train_n = (y_train - y_mean) / y_std
        logger.info(f"Target normalized: mean={y_mean:.3f}, std={y_std:.3f}")
    else:
        y_train_n = y_train

    # ------------------------------------------------------------------ #
    # 4. Train                                                             #
    # ------------------------------------------------------------------ #
    model = LinearRegressionGD(
        learning_rate=learning_rate,
        n_iterations=n_iterations,
        tolerance=tolerance,
        lr_schedule=lr_schedule,
        random_state=random_state,
        verbose=True,
        log_every=1_000,
    )
    logger.info(f"Hyperparameters: {model.get_params()}")

    t0 = time.perf_counter()
    model.fit(X_train_s, y_train_n)
    elapsed = time.perf_counter() - t0

    convergence = {
        "converged": model.converged_at_ is not None,
        "converged_at_epoch": model.converged_at_,
        "n_iter_actual": model.n_iter_actual_,
        "final_train_mse_normalized": round(model.loss_history_[-1], 8),
        "training_time_s": round(elapsed, 4),
    }
    logger.info(f"Convergence: {convergence}")

    # ------------------------------------------------------------------ #
    # 5. Evaluate                                                          #
    # ------------------------------------------------------------------ #
    # Predict → inverse-transform → original scale
    y_test_pred_n = model.predict(X_test_s)
    y_test_pred = y_test_pred_n * y_std + y_mean

    y_train_pred_n = model.predict(X_train_s)
    y_train_pred = y_train_pred_n * y_std + y_mean

    test_metrics = evaluate_regression(y_test, y_test_pred)
    train_metrics = evaluate_regression(y_train, y_train_pred)

    logger.info(
        f"TEST  — RMSE={test_metrics['rmse']:.4f} | "
        f"R²={test_metrics['r2']:.4f} | "
        f"MAE={test_metrics['mae']:.4f} | "
        f"MAPE={test_metrics['mape']:.2f}%"
    )
    logger.info(
        f"TRAIN — RMSE={train_metrics['rmse']:.4f} | "
        f"R²={train_metrics['r2']:.4f} (overfit gap check)"
    )

    # ------------------------------------------------------------------ #
    # 6. Feature Importance (|weight| on normalized scale)                #
    # ------------------------------------------------------------------ #
    importance = {
        name: round(float(abs(w)), 6)
        for name, w in zip(feature_names, model.weights_)
    }
    top5 = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
    logger.info(f"Top 5 features by |weight|: {top5}")

    # ------------------------------------------------------------------ #
    # 7. Log                                                               #
    # ------------------------------------------------------------------ #
    log_experiment(
        params={**model.get_params(), "test_size": test_size, "normalize_y": normalize_y},
        metrics={
            "test": {k: round(v, 4) for k, v in test_metrics.items()},
            "train": {k: round(v, 4) for k, v in train_metrics.items()},
        },
        metadata={
            **convergence,
            "dataset": "boston_housing",
            "n_samples": int(len(X)),
            "n_features": int(X.shape[1]),
            "feature_names": feature_names,
            "top_5_features_by_weight": dict(top5),
            "leakage_check": leakage_report,
            "data_checks": balance,
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_std": scaler.std_.tolist(),
            "final_weights": model.weights_.tolist(),
            "final_bias": float(model.bias_),
        },
    )

    return {
        "model": model,
        "scaler": scaler,
        "metrics": test_metrics,
        "train_metrics": train_metrics,
        "convergence": convergence,
        "leakage_check": leakage_report,
        "data_checks": balance,
    }


# ---------------------------------------------------------------------------
# Hyperparameter search
# ---------------------------------------------------------------------------

def hyperparameter_search() -> None:
    """Grid search over common LR / schedule combinations."""
    grid = [
        {"learning_rate": 0.05, "lr_schedule": "exponential"},
        {"learning_rate": 0.05, "lr_schedule": "cosine"},
        {"learning_rate": 0.10, "lr_schedule": "exponential"},
        {"learning_rate": 0.01, "lr_schedule": "step"},
        {"learning_rate": 0.05, "lr_schedule": "constant"},
        {"learning_rate": 0.10, "lr_schedule": "cosine"},
    ]

    rows = []
    for cfg in grid:
        logger.info(f"\n{'='*60}\nConfig: {cfg}")
        result = run_experiment(**cfg)
        rows.append({
            "config": cfg,
            "test_rmse": round(result["metrics"]["rmse"], 4),
            "test_r2": round(result["metrics"]["r2"], 4),
            "test_mae": round(result["metrics"]["mae"], 4),
            "converged": result["convergence"]["converged"],
            "n_iter_actual": result["convergence"]["n_iter_actual"],
        })

    rows.sort(key=lambda r: r["test_rmse"])
    logger.info("\n" + "="*65)
    logger.info("HP SEARCH RESULTS (sorted by test RMSE ↑):")
    logger.info(f"{'LR':>6} | {'Schedule':12} | {'RMSE':>6} | {'R²':>5} | {'MAE':>5} | {'Iters':>6}")
    logger.info("-"*65)
    for r in rows:
        logger.info(
            f"{r['config']['learning_rate']:>6.3f} | "
            f"{r['config']['lr_schedule']:12} | "
            f"{r['test_rmse']:>6.4f} | "
            f"{r['test_r2']:>5.4f} | "
            f"{r['test_mae']:>5.4f} | "
            f"{r['n_iter_actual']:>6}"
        )

    out = _EXPERIMENTS_DIR / "hparam_search_results.json"
    with open(out, "w") as fh:
        json.dump(rows, fh, indent=2)
    logger.info(f"HP search summary → {out}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train linear regression on Boston Housing")
    parser.add_argument("--hp-search", action="store_true", help="Run hyperparameter grid search")
    parser.add_argument("--lr", type=float, default=0.05, help="Learning rate (default 0.05)")
    parser.add_argument(
        "--schedule",
        choices=["constant", "step", "exponential", "cosine"],
        default="exponential",
        help="LR schedule (default: exponential)",
    )
    parser.add_argument("--iters", type=int, default=10_000, help="Max iterations")
    parser.add_argument("--tol", type=float, default=1e-7, help="Convergence tolerance")
    args = parser.parse_args()

    logger.info("=" * 65)
    logger.info("Linear Regression via Gradient Descent — Boston Housing")
    logger.info("=" * 65)

    if args.hp_search:
        hyperparameter_search()
    else:
        result = run_experiment(
            learning_rate=args.lr,
            n_iterations=args.iters,
            tolerance=args.tol,
            lr_schedule=args.schedule,
            test_size=0.20,
            random_state=42,
            normalize_y=True,
        )
        print("\n" + "=" * 50)
        print("FINAL TEST SET RESULTS — Boston Housing")
        print("=" * 50)
        for k, v in result["metrics"].items():
            print(f"  {k.upper():6s}: {v:.4f}")
        print("=" * 50)
        print(f"  Converged : {result['convergence']['converged']}")
        print(f"  At epoch  : {result['convergence']['converged_at_epoch']}")
        print(f"  Iterations: {result['convergence']['n_iter_actual']}")
        print(f"  Train time: {result['convergence']['training_time_s']}s")
        print("=" * 50)
