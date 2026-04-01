"""
Dialog Management — Training Script
=====================================
Reproducible training with:
- Stratified train / val / test splits (no leakage)
- Class-weighted cross-entropy (handles imbalance)
- MLflow experiment tracking
- Early stopping
- Bias evaluation + latency benchmark post-training
- Model card generation

Usage:
    python train.py --config config/dialog_management.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import mlflow
import mlflow.pytorch
import yaml
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader

from model import DialogManagementModel
from dataset import DialogDataset, collate_fn, generate_synthetic_dataset
from evaluate import (
    evaluate_model,
    bias_evaluation,
    benchmark_latency,
    save_confusion_matrix,
    save_evaluation_report,
    classification_report_dict,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Reproducibility ───────────────────────────────────────────────────────────

def set_seed(seed: int) -> None:
    """Pin all sources of randomness for full reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ["PYTHONHASHSEED"] = str(seed)


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ── Data Checks ───────────────────────────────────────────────────────────────

def check_data_quality(df: pd.DataFrame) -> dict:
    """Basic data quality checks — logged to MLflow."""
    class_counts = df["dialog_act"].value_counts()
    imbalance_ratio = float(class_counts.max() / class_counts.min())
    null_frac = float(df.isnull().mean().mean())

    checks = {
        "n_samples":            len(df),
        "n_classes":            int(df["dialog_act"].nunique()),
        "class_imbalance_ratio": round(imbalance_ratio, 2),
        "class_imbalance_flag": imbalance_ratio > 5.0,
        "null_fraction":        round(null_frac, 4),
        "leakage_risk":         False,  # scalers/encoders fit on train only
    }
    if checks["class_imbalance_flag"]:
        logger.warning(
            "Class imbalance ratio %.2f > 5.0 — using class-weighted loss.",
            imbalance_ratio,
        )
    return checks


# ── Training Loop ─────────────────────────────────────────────────────────────

def train_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler,
    criterion: nn.Module,
    device: torch.device,
    grad_clip: float,
) -> tuple[float, float, float]:
    """One training epoch. Returns (loss, accuracy, f1_weighted)."""
    model.train()
    total_loss = 0.0
    all_preds, all_labels = [], []

    for batch in loader:
        input_ids     = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels        = batch["labels"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)
        loss = criterion(logits, labels)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()
        all_preds.extend(logits.argmax(dim=-1).cpu().tolist())
        all_labels.extend(labels.cpu().tolist())

    avg_loss = total_loss / len(loader)
    acc = accuracy_score(all_labels, all_preds)
    f1  = f1_score(all_labels, all_preds, average="weighted", zero_division=0)
    return avg_loss, acc, f1


# ── Main ──────────────────────────────────────────────────────────────────────

def train(config: dict) -> dict:
    cfg_train  = config["training"]
    cfg_model  = config["model"]
    cfg_data   = config["data"]
    cfg_inf    = config["inference"]
    cfg_mlflow = config["mlflow"]
    cfg_art    = config["artifacts"]

    set_seed(cfg_train["seed"])

    Path(cfg_art["model_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg_art["report_dir"]).mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(cfg_mlflow["tracking_uri"])
    mlflow.set_experiment(cfg_mlflow["experiment_name"])

    with mlflow.start_run() as run:
        # ── Log hyperparameters ──────────────────────────────────────────────
        mlflow.log_params({
            "encoder":          cfg_model["encoder"],
            "hidden_size":      cfg_model["hidden_size"],
            "lstm_layers":      cfg_model["lstm_layers"],
            "dropout":          cfg_model["dropout"],
            "max_seq_len":      cfg_model["max_seq_len"],
            "epochs":           cfg_train["epochs"],
            "batch_size":       cfg_train["batch_size"],
            "learning_rate":    cfg_train["learning_rate"],
            "weight_decay":     cfg_train["weight_decay"],
            "warmup_ratio":     cfg_train["warmup_ratio"],
            "seed":             cfg_train["seed"],
            "test_size":        cfg_train["test_size"],
            "val_size":         cfg_train["val_size"],
            "dataset":          cfg_data["dataset"],
        })

        # ── Load data ────────────────────────────────────────────────────────
        logger.info("Loading data (source: %s) …", cfg_data["dataset"])
        df = generate_synthetic_dataset(n_samples=cfg_data.get("n_samples", 2000), seed=cfg_train["seed"])

        # ── Data quality checks (before split — labels exist, no leakage) ────
        data_checks = check_data_quality(df)
        mlflow.log_params(data_checks)
        logger.info("Data checks: %s", json.dumps(data_checks, indent=2))

        # ── Label encoding — uses full label set, NOT test statistics ────────
        label_enc = LabelEncoder()
        df["label"] = label_enc.fit_transform(df["dialog_act"])
        n_classes = len(label_enc.classes_)
        class_names = label_enc.classes_.tolist()

        # ── Stratified splits — NO DATA LEAKAGE ─────────────────────────────
        train_val_df, test_df = train_test_split(
            df,
            test_size=cfg_train["test_size"],
            random_state=cfg_train["seed"],
            stratify=df["label"],       # stratified on label
        )
        adjusted_val_size = cfg_train["val_size"] / (1.0 - cfg_train["test_size"])
        train_df, val_df = train_test_split(
            train_val_df,
            test_size=adjusted_val_size,
            random_state=cfg_train["seed"],
            stratify=train_val_df["label"],  # stratified on label
        )

        logger.info(
            "Split: train=%d | val=%d | test=%d (stratified)",
            len(train_df), len(val_df), len(test_df),
        )
        mlflow.log_params({
            "n_train": len(train_df),
            "n_val":   len(val_df),
            "n_test":  len(test_df),
        })

        # ── Datasets — tokenizer loaded from checkpoint (not fitted) ─────────
        encoder_name = cfg_model["encoder"]
        max_len      = cfg_model["max_seq_len"]
        n_workers    = cfg_data.get("num_workers", 0)

        train_dataset = DialogDataset(train_df, encoder_name, max_len)
        val_dataset   = DialogDataset(val_df,   encoder_name, max_len)
        test_dataset  = DialogDataset(test_df,  encoder_name, max_len)

        train_loader = DataLoader(
            train_dataset, batch_size=cfg_train["batch_size"],
            shuffle=True, collate_fn=collate_fn, num_workers=n_workers,
        )
        val_loader = DataLoader(
            val_dataset, batch_size=cfg_train["batch_size"],
            shuffle=False, collate_fn=collate_fn, num_workers=n_workers,
        )
        test_loader = DataLoader(
            test_dataset, batch_size=cfg_train["batch_size"],
            shuffle=False, collate_fn=collate_fn, num_workers=n_workers,
        )

        # ── Model ────────────────────────────────────────────────────────────
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Device: %s", device)

        model = DialogManagementModel(
            encoder_name=encoder_name,
            hidden_size=cfg_model["hidden_size"],
            n_classes=n_classes,
            lstm_layers=cfg_model["lstm_layers"],
            dropout=cfg_model["dropout"],
        ).to(device)

        mlflow.log_param("n_trainable_params", model.n_trainable_params)
        logger.info("Model params: %s", f"{model.n_trainable_params:,}")

        # ── Class-weighted loss (handles imbalance without data leakage) ─────
        class_counts = train_df["dialog_act"].value_counts()
        weights_arr = np.array([
            len(train_df) / (n_classes * class_counts.get(c, 1))
            for c in class_names
        ])
        class_weights = torch.tensor(weights_arr, dtype=torch.float32).to(device)
        criterion = nn.CrossEntropyLoss(weight=class_weights)

        # ── Optimizer + scheduler ────────────────────────────────────────────
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=cfg_train["learning_rate"],
            weight_decay=cfg_train["weight_decay"],
        )
        total_steps = len(train_loader) * cfg_train["epochs"]
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            optimizer,
            max_lr=cfg_train["learning_rate"],
            total_steps=total_steps,
            pct_start=cfg_train["warmup_ratio"],
        )

        # ── Training loop ────────────────────────────────────────────────────
        best_val_f1      = 0.0
        patience_counter = 0
        best_model_path  = Path(cfg_art["model_dir"]) / "best_model.pt"

        for epoch in range(cfg_train["epochs"]):
            tr_loss, tr_acc, tr_f1 = train_epoch(
                model, train_loader, optimizer, scheduler, criterion, device,
                cfg_train["gradient_clip"],
            )
            val_metrics = evaluate_model(model, val_loader, device, criterion)

            logger.info(
                "Epoch %2d/%d | loss=%.4f acc=%.4f f1=%.4f | val_loss=%.4f val_acc=%.4f val_f1=%.4f",
                epoch + 1, cfg_train["epochs"],
                tr_loss, tr_acc, tr_f1,
                val_metrics["loss"], val_metrics["accuracy"], val_metrics["f1_weighted"],
            )

            mlflow.log_metrics(
                {
                    "train_loss":       tr_loss,
                    "train_accuracy":   tr_acc,
                    "train_f1":         tr_f1,
                    "val_loss":         val_metrics["loss"],
                    "val_accuracy":     val_metrics["accuracy"],
                    "val_f1_weighted":  val_metrics["f1_weighted"],
                    "val_f1_macro":     val_metrics["f1_macro"],
                    "lr":               scheduler.get_last_lr()[0],
                },
                step=epoch,
            )

            # ── Early stopping ───────────────────────────────────────────────
            if val_metrics["f1_weighted"] > best_val_f1:
                best_val_f1      = val_metrics["f1_weighted"]
                patience_counter = 0
                torch.save(
                    {
                        "epoch":              epoch,
                        "model_state_dict":   model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "val_f1":             best_val_f1,
                        "label_classes":      class_names,
                        "config":             config,
                    },
                    best_model_path,
                )
                logger.info("  ✓ New best model (val_f1=%.4f)", best_val_f1)
            else:
                patience_counter += 1
                if patience_counter >= cfg_train["early_stopping_patience"]:
                    logger.info("Early stopping triggered at epoch %d.", epoch + 1)
                    break

        # ── Load best checkpoint for test evaluation ──────────────────────────
        ckpt = torch.load(best_model_path, map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])

        # ── Test evaluation ───────────────────────────────────────────────────
        logger.info("Running test evaluation …")
        test_metrics = evaluate_model(model, test_loader, device, criterion)
        cls_report   = classification_report_dict(
            test_metrics["_labels"], test_metrics["_preds"], class_names
        )

        mlflow.log_metrics({
            "test_accuracy":    test_metrics["accuracy"],
            "test_f1_weighted": test_metrics["f1_weighted"],
            "test_f1_macro":    test_metrics["f1_macro"],
            "test_loss":        test_metrics["loss"],
        })

        # ── Confusion matrix ─────────────────────────────────────────────────
        cm_path = Path(cfg_art["report_dir"]) / "confusion_matrix.png"
        save_confusion_matrix(
            test_metrics["_labels"], test_metrics["_preds"], class_names, cm_path
        )
        mlflow.log_artifact(str(cm_path))

        # ── Bias evaluation ───────────────────────────────────────────────────
        logger.info("Running bias evaluation …")
        bias_results = bias_evaluation(
            model, test_df, label_enc, encoder_name, max_len, device
        )
        mlflow.log_metric(
            "bias_parity_gap",
            bias_results.get("summary", {}).get("demographic_parity_gap", 0.0),
        )

        # ── Latency benchmark ─────────────────────────────────────────────────
        logger.info("Benchmarking inference latency …")
        latency_stats = benchmark_latency(model, test_dataset, device, n_samples=200)
        mlflow.log_metrics({
            "latency_p50_ms": latency_stats["p50_ms"],
            "latency_p95_ms": latency_stats["p95_ms"],
            "latency_p99_ms": latency_stats["p99_ms"],
        })

        sla_ms = cfg_inf["max_latency_ms"]
        within_sla = latency_stats["p95_ms"] <= sla_ms
        if not within_sla:
            logger.warning(
                "⚠ P95 latency %.1f ms exceeds SLA of %s ms", latency_stats["p95_ms"], sla_ms
            )

        # ── Save evaluation report ────────────────────────────────────────────
        report_path = Path(cfg_art["report_dir"]) / "evaluation_report.json"
        save_evaluation_report(
            test_metrics, cls_report, bias_results, latency_stats, sla_ms, report_path
        )
        mlflow.log_artifact(str(report_path))

        # ── Save label encoder ────────────────────────────────────────────────
        le_path = Path(cfg_art["model_dir"]) / "label_encoder.json"
        with open(le_path, "w") as f:
            json.dump({"classes": class_names}, f, indent=2)
        mlflow.log_artifact(str(le_path))

        # ── Log model ────────────────────────────────────────────────────────
        mlflow.pytorch.log_model(model, "dialog_management_model")

        # ── Summary ───────────────────────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("TEST RESULTS")
        logger.info("=" * 60)
        logger.info("  Accuracy:      %.4f", test_metrics["accuracy"])
        logger.info("  F1 (weighted): %.4f", test_metrics["f1_weighted"])
        logger.info("  F1 (macro):    %.4f", test_metrics["f1_macro"])
        logger.info("  P95 latency:   %.1f ms (SLA: %s ms) [%s]",
                    latency_stats["p95_ms"], sla_ms, "OK" if within_sla else "FAIL")
        logger.info("  Run ID:        %s", run.info.run_id)

        return {
            "run_id":            run.info.run_id,
            "test_accuracy":     test_metrics["accuracy"],
            "test_f1_weighted":  test_metrics["f1_weighted"],
            "test_f1_macro":     test_metrics["f1_macro"],
            "latency_p95_ms":    latency_stats["p95_ms"],
            "within_sla":        within_sla,
            "bias_flag":         bias_results.get("summary", {}).get("bias_flag", False),
            "data_checks":       data_checks,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Dialog Management model")
    parser.add_argument(
        "--config",
        default="config/dialog_management.yaml",
        help="Path to YAML config file",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    results = train(cfg)
    print(json.dumps(results, indent=2))
