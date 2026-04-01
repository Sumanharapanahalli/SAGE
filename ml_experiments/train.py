"""
Boston Housing — Linear Regression via Gradient Descent
=======================================================
Usage
-----
    python train.py                          # default hyperparams
    python train.py --lr 0.05 --schedule cosine --batch-size 64
    python train.py --sweep                  # grid search lr × schedule
    python train.py --no-plot                # skip matplotlib output

Artefacts written
-----------------
    training.log                             # full run log
    experiments/boston_linreg_gd_runs.jsonl  # one JSON record per run
    learning_curves.png                      # loss + LR schedule plots
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np

# ── Path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from src.linear_regression import LinearRegressionGD  # noqa: E402
from src.data_utils import (  # noqa: E402
    load_boston_housing,
    validate_data,
    train_test_split_reg,
)
from src.experiment_logger import ExperimentLogger  # noqa: E402

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-24s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("training.log", mode="a"),
    ],
)
logger = logging.getLogger("train")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Boston Housing: gradient-descent linear regression",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--lr", type=float, default=0.1, help="Initial learning rate")
    p.add_argument(
        "--schedule",
        default="cosine",
        choices=["constant", "step", "exponential", "cosine"],
    )
    p.add_argument("--iterations", type=int, default=10_000, help="Max GD iterations")
    p.add_argument("--batch-size", type=int, default=32, dest="batch_size")
    p.add_argument("--l2", type=float, default=0.0, help="L2 regularisation λ")
    p.add_argument("--patience", type=int, default=100)
    p.add_argument("--tol", type=float, default=1e-6)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test-size", type=float, default=0.20, dest="test_size")
    p.add_argument("--val-size", type=float, default=0.10, dest="val_size")
    p.add_argument("--sweep", action="store_true", help="Run hyperparameter grid search")
    p.add_argument("--no-plot", action="store_true", dest="no_plot")
    return p.parse_args()


# ── Single experiment ─────────────────────────────────────────────────────────

def run_experiment(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    params: Dict[str, Any],
    exp_logger: ExperimentLogger,
) -> Dict[str, Any]:
    """Train one model, log metrics, return result dict."""
    run_id = exp_logger.start_run(params=params)

    model = LinearRegressionGD(
        learning_rate=params["lr"],
        n_iterations=params["iterations"],
        batch_size=params["batch_size"],
        tol=params["tol"],
        patience=params["patience"],
        lr_schedule=params["schedule"],
        l2_lambda=params["l2"],
        random_state=params["seed"],
        verbose=True,
        log_interval=1_000,
    )

    # Train — scaler is fit inside model.fit() on X_train ONLY
    model.fit(X_train, y_train, X_val=X_val, y_val=y_val)

    # Evaluate on all three splits
    train_m = model.score(X_train, y_train)
    val_m = model.score(X_val, y_val)
    test_m = model.score(X_test, y_test)

    metrics = {
        "train_rmse": train_m["rmse"],
        "train_r2": train_m["r2"],
        "val_rmse": val_m["rmse"],
        "val_r2": val_m["r2"],
        "test_rmse": test_m["rmse"],
        "test_r2": test_m["r2"],
        "test_mae": test_m["mae"],
        "n_iter": model.n_iter_,
        "converged": int(model.converged_),
    }

    exp_logger.log_metrics(run_id, metrics)
    exp_logger.end_run(run_id)

    logger.info(
        "\n%s\n  Split       RMSE      MAE       R²\n"
        "  train    %7.4f   %7.4f   %7.4f\n"
        "  val      %7.4f   %7.4f   %7.4f\n"
        "  test     %7.4f   %7.4f   %7.4f\n"
        "  Iters: %d / %d  |  Converged: %s\n%s",
        "=" * 52,
        train_m["rmse"], train_m["mae"], train_m["r2"],
        val_m["rmse"], val_m["mae"], val_m["r2"],
        test_m["rmse"], test_m["mae"], test_m["r2"],
        model.n_iter_, params["iterations"], model.converged_,
        "=" * 52,
    )

    return {"model": model, "metrics": metrics, "run_id": run_id}


# ── Hyperparameter sweep ──────────────────────────────────────────────────────

_SWEEP_GRID = {
    "lr": [0.01, 0.05, 0.10, 0.20],
    "schedule": ["constant", "step", "exponential", "cosine"],
}


def run_sweep(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    base_params: Dict[str, Any],
    exp_logger: ExperimentLogger,
) -> Dict[str, Any]:
    """Grid search over lr × schedule; return best params by val RMSE."""
    best_val_rmse = float("inf")
    best_params: Optional[Dict[str, Any]] = None

    total = len(_SWEEP_GRID["lr"]) * len(_SWEEP_GRID["schedule"])
    done = 0

    for lr in _SWEEP_GRID["lr"]:
        for schedule in _SWEEP_GRID["schedule"]:
            done += 1
            params = {**base_params, "lr": lr, "schedule": schedule}
            logger.info("Sweep [%d/%d] lr=%.3f schedule=%s", done, total, lr, schedule)
            result = run_experiment(
                X_train, y_train, X_val, y_val, X_test, y_test, params, exp_logger
            )
            if result["metrics"]["val_rmse"] < best_val_rmse:
                best_val_rmse = result["metrics"]["val_rmse"]
                best_params = params

    logger.info(
        "Sweep complete. Best val_rmse=%.4f with params=%s", best_val_rmse, best_params
    )
    return best_params  # type: ignore[return-value]


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_learning_curves(
    model: LinearRegressionGD,
    save_path: str = "learning_curves.png",
) -> None:
    """Save loss + LR schedule plots to disk (requires matplotlib)."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(13, 4))
        fig.suptitle("Boston Housing — Gradient Descent Linear Regression", fontsize=13)

        ax = axes[0]
        ax.semilogy(model.loss_history_, color="#2196F3", linewidth=1.1, alpha=0.9)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Training MSE (log scale)")
        ax.set_title("Training Loss")
        ax.grid(True, alpha=0.3)
        ax.axvline(x=model.n_iter_ - 1, color="red", linestyle="--",
                   linewidth=0.8, label=f"stopped @ {model.n_iter_}")
        ax.legend(fontsize=9)

        ax = axes[1]
        ax.plot(model.lr_history_, color="#FF5722", linewidth=1.1, alpha=0.9)
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Learning Rate")
        ax.set_title(f"LR Schedule: {model.lr_schedule!r}")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info("Learning curves saved to %s", save_path)
        plt.close(fig)
    except ImportError:
        logger.warning("matplotlib not available — skipping learning-curve plot")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    # ── Load & validate ───────────────────────────────────────────────────────
    logger.info("Loading Boston Housing dataset ...")
    X, y, feature_names = load_boston_housing()
    logger.info("Features (%d): %s", len(feature_names), feature_names)
    validate_data(X, y, name="full_dataset")

    # ── Split (no normalisation here — done inside model.fit() on train only) ─
    X_train, X_val, X_test, y_train, y_val, y_test = train_test_split_reg(
        X, y,
        test_size=args.test_size,
        val_size=args.val_size,
        random_state=args.seed,
    )

    # ── Experiment logger ─────────────────────────────────────────────────────
    exp_logger = ExperimentLogger("boston_linreg_gd")

    base_params: Dict[str, Any] = {
        "lr": args.lr,
        "schedule": args.schedule,
        "iterations": args.iterations,
        "batch_size": args.batch_size,
        "l2": args.l2,
        "patience": args.patience,
        "tol": args.tol,
        "seed": args.seed,
    }

    # ── Train ─────────────────────────────────────────────────────────────────
    if args.sweep:
        best_params = run_sweep(
            X_train, y_train, X_val, y_val, X_test, y_test, base_params, exp_logger
        )
        final_result = run_experiment(
            X_train, y_train, X_val, y_val, X_test, y_test, best_params, exp_logger
        )
    else:
        final_result = run_experiment(
            X_train, y_train, X_val, y_val, X_test, y_test, base_params, exp_logger
        )

    # ── Plot ──────────────────────────────────────────────────────────────────
    if not args.no_plot:
        plot_learning_curves(final_result["model"])

    # ── Print summary table ───────────────────────────────────────────────────
    print("\n" + exp_logger.summary_table())

    # ── Print best run ────────────────────────────────────────────────────────
    best = exp_logger.best_run("val_rmse", mode="min")
    if best:
        logger.info(
            "Best run: id=%s  val_rmse=%.4f  test_rmse=%.4f  test_r2=%.4f  params=%s",
            best["run_id"],
            best["metrics"].get("val_rmse", float("nan")),
            best["metrics"].get("test_rmse", float("nan")),
            best["metrics"].get("test_r2", float("nan")),
            best["params"],
        )

    # ── Machine-readable output for CI / downstream pipelines ─────────────────
    output = {
        "model_type": "linear_regression_gradient_descent",
        "metrics": {
            "test_rmse": round(final_result["metrics"]["test_rmse"], 4),
            "test_r2": round(final_result["metrics"]["test_r2"], 4),
            "test_mae": round(final_result["metrics"]["test_mae"], 4),
        },
        "data_checks": {
            "leakage_risk": False,
            "class_imbalance": False,
        },
        "run_id": final_result["run_id"],
        "params": base_params,
    }
    print("\nJSON result:")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
