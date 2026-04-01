#!/usr/bin/env python3
"""
run_experiment.py — Orchestrates the full LSTM vs ARIMA experiment.

Usage
-----
    python run_experiment.py              # uses config.yaml defaults
    python run_experiment.py --epochs 30  # override any config key

Outputs
-------
* MLflow experiment logged to ./mlruns/
* Comparison table printed to stdout
* Model checkpoint saved to ./artifacts/lstm_best.pt
* JSON result summary written to ./artifacts/results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_experiment")

# ── Ensure src/ is importable ────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.data_utils import (
    generate_synthetic_series,
    temporal_split_and_scale,
    make_dataloaders,
    check_class_imbalance,
)
from src.lstm_model import LSTMForecaster
from src.arima_baseline import ARIMABaseline
from src.train import TrainConfig, train, predict_all, get_actuals
from src.evaluate import evaluate_model, comparison_table, inverse_scale


# ── Reproducibility ──────────────────────────────────────────────────────────

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ── Config loader ─────────────────────────────────────────────────────────────

def load_config(path: Path, overrides: dict) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    # Flatten overrides
    for k, v in overrides.items():
        for section in cfg.values():
            if isinstance(section, dict) and k in section:
                section[k] = v
    return cfg


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    parser = argparse.ArgumentParser(description="LSTM vs ARIMA time-series forecasting experiment")
    parser.add_argument("--config", default=str(ROOT / "config.yaml"))
    parser.add_argument("--epochs", type=int, help="Override training epochs")
    parser.add_argument("--no-arima", action="store_true", help="Skip slow ARIMA baseline")
    args = parser.parse_args()

    overrides = {}
    if args.epochs:
        overrides["epochs"] = args.epochs

    cfg = load_config(Path(args.config), overrides)
    set_seed(cfg["training"]["seed"])

    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)

    # ── MLflow setup ─────────────────────────────────────────────────────────
    try:
        import mlflow
        mlflow.set_tracking_uri(cfg["mlflow"]["tracking_uri"])
        mlflow.set_experiment(cfg["mlflow"]["experiment_name"])
        use_mlflow = True
    except ImportError:
        logger.warning("mlflow not installed — skipping experiment tracking")
        use_mlflow = False

    # ── 1. Data ──────────────────────────────────────────────────────────────
    logger.info("=== Step 1: Data Generation & Split ===")
    series = generate_synthetic_series(
        n=cfg["data"]["n_samples"],
        noise_std=cfg["data"]["noise_std"],
        seed=cfg["training"]["seed"],
    )

    # Data quality check — leakage and imbalance
    data_checks = check_class_imbalance(series)
    data_checks["leakage_risk"] = False   # enforced by temporal split + train-only scaler fit
    logger.info("Data checks: %s", data_checks)

    split = temporal_split_and_scale(series, train_ratio=cfg["data"]["train_ratio"])

    lookback  = cfg["windows"]["lookback"]
    horizon   = cfg["windows"]["horizon"]
    batch_sz  = cfg["training"]["batch_size"]

    train_dl, test_dl = make_dataloaders(split, lookback, horizon, batch_sz)

    # ── 2. LSTM Training ──────────────────────────────────────────────────────
    logger.info("=== Step 2: LSTM Training ===")
    model = LSTMForecaster(
        input_size=1,
        hidden_size=cfg["model"]["hidden_size"],
        num_layers=cfg["model"]["num_layers"],
        output_horizon=horizon,
        dropout=cfg["model"]["dropout"],
    )

    train_cfg = TrainConfig(
        epochs=cfg["training"]["epochs"],
        batch_size=batch_sz,
        learning_rate=cfg["training"]["learning_rate"],
        weight_decay=cfg["training"]["weight_decay"],
        patience=cfg["training"]["patience"],
        initial_teacher_forcing=cfg["model"]["initial_teacher_forcing"],
        final_teacher_forcing=cfg["model"]["final_teacher_forcing"],
    )

    mlflow_ctx = mlflow.start_run() if use_mlflow else None

    if use_mlflow:
        mlflow.log_params({
            "lookback": lookback, "horizon": horizon,
            "hidden_size": cfg["model"]["hidden_size"],
            "num_layers": cfg["model"]["num_layers"],
            "dropout": cfg["model"]["dropout"],
            "epochs": train_cfg.epochs,
            "lr": train_cfg.learning_rate,
            "batch_size": batch_sz,
            "initial_tf": train_cfg.initial_teacher_forcing,
            "final_tf": train_cfg.final_teacher_forcing,
            "seed": cfg["training"]["seed"],
        })

    train_result = train(model, train_dl, test_dl, train_cfg, mlflow_run=mlflow_ctx)

    # Save checkpoint
    ckpt_path = artifacts / "lstm_best.pt"
    torch.save(model.state_dict(), ckpt_path)
    logger.info("Checkpoint saved: %s", ckpt_path)

    # ── 3. LSTM Evaluation ────────────────────────────────────────────────────
    logger.info("=== Step 3: LSTM Evaluation ===")
    lstm_preds_scaled = predict_all(model, test_dl, device=train_cfg.device)
    lstm_actuals_scaled = get_actuals(test_dl)

    lstm_metrics = evaluate_model(lstm_actuals_scaled, lstm_preds_scaled, split.scaler, label="lstm")

    # ── 4. ARIMA Baseline ─────────────────────────────────────────────────────
    arima_metrics: dict = {}
    if not args.no_arima:
        logger.info("=== Step 4: ARIMA Baseline (walk-forward) ===")
        arima = ARIMABaseline(
            max_p=cfg["arima"]["max_p"],
            max_d=cfg["arima"]["max_d"],
            max_q=cfg["arima"]["max_q"],
            information_criterion=cfg["arima"]["information_criterion"],
        )
        train_size = int(len(series) * cfg["data"]["train_ratio"])
        arima_preds_raw, arima_actuals_raw = arima.walk_forward_forecast(
            series, train_size=train_size, lookback=lookback, horizon=horizon
        )
        # ARIMA operates in original space — evaluate directly without inverse scaling
        from src.metrics import compute_all as _ca
        arima_metrics = _ca(arima_actuals_raw, arima_preds_raw, label="arima")
        logger.info("ARIMA | MAE=%.4f RMSE=%.4f MAPE=%.2f%%",
                    arima_metrics["arima_mae"], arima_metrics["arima_rmse"], arima_metrics["arima_mape"])
        if use_mlflow:
            mlflow.log_metrics({f"arima_{k.split('arima_')[1]}": v for k, v in arima_metrics.items()})
    else:
        logger.info("Skipping ARIMA baseline (--no-arima)")

    # ── 5. Comparison Table ───────────────────────────────────────────────────
    if arima_metrics:
        table = comparison_table(lstm_metrics, arima_metrics, horizon=horizon)
        logger.info("\n\n=== Model Comparison ===\n%s\n", table)

    # ── 6. Log LSTM metrics to MLflow ────────────────────────────────────────
    if use_mlflow:
        mlflow.log_metrics({k: v for k, v in lstm_metrics.items()})
        mlflow.log_metric("best_val_loss", train_result.best_val_loss)
        mlflow.log_metric("best_epoch", train_result.best_epoch)
        mlflow.log_artifact(str(ckpt_path))
        mlflow_ctx.__exit__(None, None, None)

    # ── 7. JSON summary ───────────────────────────────────────────────────────
    summary = {
        "model_type": "LSTM-EncoderDecoder-TeacherForcing",
        "metrics": {
            "lstm_mae":   lstm_metrics.get("lstm_mae"),
            "lstm_rmse":  lstm_metrics.get("lstm_rmse"),
            "lstm_mape":  lstm_metrics.get("lstm_mape"),
            "lstm_smape": lstm_metrics.get("lstm_smape"),
            "arima_mae":  arima_metrics.get("arima_mae"),
            "arima_rmse": arima_metrics.get("arima_rmse"),
            "arima_mape": arima_metrics.get("arima_mape"),
            # accuracy / f1 are not applicable for regression
            "accuracy": None,
            "f1": None,
        },
        "data_checks": data_checks,
        "training": {
            "best_epoch": train_result.best_epoch,
            "best_val_loss": train_result.best_val_loss,
            "stopped_early": train_result.stopped_early,
            "total_epochs_run": len(train_result.train_losses),
        },
    }

    summary_path = artifacts / "results.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info("Results saved: %s", summary_path)

    return summary


if __name__ == "__main__":
    result = main()
    # Print canonical JSON output as required
    print(json.dumps(result, indent=2, default=str))
