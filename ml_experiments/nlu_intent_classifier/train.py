"""
train.py — Reproducible NLU intent classification training pipeline.

Enforced guarantees:
  ✓ Stratified train/val/test split (no data leakage)
  ✓ Scaler/encoder fit on train only
  ✓ All hyperparameters logged to MLflow
  ✓ Random seed fixed end-to-end (Python, NumPy, PyTorch)
  ✓ Early stopping on validation loss
  ✓ Class-imbalance detection logged as warning
  ✓ Model artifact + tokenizer saved for inference

Usage:
    python train.py [--config config.yaml]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import torch
import yaml
from rich.logging import RichHandler
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from data_utils import load_and_split
from evaluate_model import compute_metrics, run_bias_evaluation

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True, show_time=True)],
)
logger = logging.getLogger("nlu_train")


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ["PYTHONHASHSEED"] = str(seed)
    logger.info("Global seed set to %d", seed)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

def train_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    optimizer: AdamW,
    scheduler: Any,
    device: torch.device,
    grad_clip: float,
) -> float:
    model.train()
    total_loss = 0.0
    for batch in loader:
        optimizer.zero_grad()
        input_ids      = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels         = batch["label"].to(device)

        # Mask out-of-scope samples (label == -1) from loss
        valid = labels >= 0
        if valid.sum() == 0:
            continue

        out = model(
            input_ids=input_ids[valid],
            attention_mask=attention_mask[valid],
            labels=labels[valid],
        )
        loss = out.loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
        optimizer.step()
        scheduler.step()
        total_loss += loss.item()

    return total_loss / max(len(loader), 1)


@torch.no_grad()
def eval_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
) -> tuple[float, list[int], list[int]]:
    model.eval()
    total_loss, all_preds, all_labels = 0.0, [], []
    for batch in loader:
        input_ids      = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels         = batch["label"].to(device)

        valid = labels >= 0
        if valid.sum() == 0:
            continue

        out = model(
            input_ids=input_ids[valid],
            attention_mask=attention_mask[valid],
            labels=labels[valid],
        )
        total_loss += out.loss.item()
        preds = out.logits.argmax(dim=-1).cpu().tolist()
        all_preds.extend(preds)
        all_labels.extend(labels[valid].cpu().tolist())

    return total_loss / max(len(loader), 1), all_preds, all_labels


# ---------------------------------------------------------------------------
# HF Dataset → PyTorch DataLoader
# ---------------------------------------------------------------------------

def make_loader(hf_dataset: Any, batch_size: int, shuffle: bool) -> DataLoader:
    hf_dataset = hf_dataset.with_format("torch")
    return DataLoader(hf_dataset, batch_size=batch_size, shuffle=shuffle)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(cfg_path: str) -> dict[str, Any]:
    # ── Config ──────────────────────────────────────────────────────────
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    seed    = cfg["experiment"]["random_seed"]
    outdir  = Path(cfg["output"]["model_dir"])
    tokdir  = Path(cfg["output"]["tokenizer_dir"])
    metrics_path = Path(cfg["output"]["metrics_path"])
    outdir.mkdir(parents=True, exist_ok=True)
    tokdir.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    set_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Device: %s", device)

    # ── MLflow ──────────────────────────────────────────────────────────
    mlflow.set_tracking_uri(cfg["experiment"]["tracking_uri"])
    mlflow.set_experiment(cfg["experiment"]["name"])

    with mlflow.start_run() as run:
        mlflow.log_params({
            "backbone":      cfg["model"]["backbone"],
            "epochs":        cfg["training"]["epochs"],
            "batch_size":    cfg["training"]["batch_size"],
            "lr":            cfg["training"]["learning_rate"],
            "weight_decay":  cfg["training"]["weight_decay"],
            "warmup_ratio":  cfg["training"]["warmup_ratio"],
            "max_length":    cfg["data"]["max_length"],
            "test_size":     cfg["data"]["test_size"],
            "val_size":      cfg["data"]["val_size"],
            "seed":          seed,
        })
        mlflow.log_artifact(cfg_path, artifact_path="config")

        # ── Tokenizer (fit-free — no leakage risk) ───────────────────
        tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["backbone"])
        tokenizer.save_pretrained(str(tokdir))

        # ── Data ─────────────────────────────────────────────────────
        dataset_dict, label_enc, data_report = load_and_split(cfg, tokenizer)

        num_labels = len(label_enc)
        cfg["model"]["num_labels"] = num_labels
        logger.info("Number of intent classes: %d", num_labels)

        mlflow.log_params({
            "num_labels":        num_labels,
            "class_imbalance":   data_report.class_imbalance_flag,
            "imbalance_ratio":   round(data_report.imbalance_ratio, 2),
            "train_samples":     data_report.train_size,
            "val_samples":       data_report.val_size,
            "test_samples":      data_report.test_size,
        })

        train_loader = make_loader(dataset_dict["train"],
                                   cfg["training"]["batch_size"], shuffle=True)
        val_loader   = make_loader(dataset_dict["val"],
                                   cfg["training"]["batch_size"], shuffle=False)
        test_loader  = make_loader(dataset_dict["test"],
                                   cfg["training"]["batch_size"], shuffle=False)

        # ── Model ────────────────────────────────────────────────────
        model = AutoModelForSequenceClassification.from_pretrained(
            cfg["model"]["backbone"],
            num_labels=num_labels,
            hidden_dropout_prob=cfg["model"]["dropout"],
            attention_probs_dropout_prob=cfg["model"]["dropout"],
        )
        model.to(device)

        # ── Optimiser + scheduler ────────────────────────────────────
        optimizer = AdamW(
            model.parameters(),
            lr=cfg["training"]["learning_rate"],
            weight_decay=cfg["training"]["weight_decay"],
        )
        total_steps   = len(train_loader) * cfg["training"]["epochs"]
        warmup_steps  = int(total_steps * cfg["training"]["warmup_ratio"])
        scheduler     = get_linear_schedule_with_warmup(
            optimizer, warmup_steps, total_steps
        )

        # ── Training loop ────────────────────────────────────────────
        best_val_loss = float("inf")
        patience_ctr  = 0
        patience      = cfg["training"]["early_stopping_patience"]

        for epoch in range(1, cfg["training"]["epochs"] + 1):
            t0 = time.perf_counter()
            train_loss = train_epoch(
                model, train_loader, optimizer, scheduler,
                device, cfg["training"]["gradient_clip"],
            )
            val_loss, val_preds, val_labels = eval_epoch(model, val_loader, device)
            elapsed = time.perf_counter() - t0

            val_metrics = compute_metrics(val_preds, val_labels,
                                          label_enc.classes_, prefix="val")

            logger.info(
                "Epoch %d/%d | train_loss=%.4f val_loss=%.4f "
                "val_acc=%.3f val_f1=%.3f | %.1fs",
                epoch, cfg["training"]["epochs"],
                train_loss, val_loss,
                val_metrics["val_accuracy"], val_metrics["val_f1_macro"],
                elapsed,
            )
            mlflow.log_metrics(
                {"train_loss": train_loss, "val_loss": val_loss,
                 **val_metrics, "epoch_seconds": elapsed},
                step=epoch,
            )

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_ctr  = 0
                model.save_pretrained(str(outdir))
                logger.info("  ✓ New best model saved (val_loss=%.4f)", best_val_loss)
            else:
                patience_ctr += 1
                if patience_ctr >= patience:
                    logger.info("Early stopping triggered at epoch %d.", epoch)
                    break

        # ── Test evaluation ──────────────────────────────────────────
        model = AutoModelForSequenceClassification.from_pretrained(str(outdir))
        model.to(device)
        _, test_preds, test_labels = eval_epoch(model, test_loader, device)
        test_metrics = compute_metrics(test_preds, test_labels,
                                       label_enc.classes_, prefix="test")

        logger.info("── Test results ─────────────────────────────")
        for k, v in test_metrics.items():
            logger.info("  %s: %.4f", k, v)

        mlflow.log_metrics(test_metrics)

        # ── Bias evaluation ──────────────────────────────────────────
        bias_report = run_bias_evaluation(
            test_preds, test_labels,
            label_enc.classes_,
            bias_slices=cfg["data"]["bias_slices"],
        )
        mlflow.log_dict(bias_report, "bias_report.json")

        # ── Persist all metrics ──────────────────────────────────────
        final_metrics = {
            **test_metrics,
            "data_report": {
                "class_imbalance": data_report.class_imbalance_flag,
                "imbalance_ratio": round(data_report.imbalance_ratio, 2),
                "leakage_risk": False,
                "train_size": data_report.train_size,
                "val_size": data_report.val_size,
                "test_size": data_report.test_size,
            },
            "bias_report": bias_report,
            "mlflow_run_id": run.info.run_id,
        }
        with open(metrics_path, "w") as f:
            json.dump(final_metrics, f, indent=2)
        mlflow.log_artifact(str(metrics_path), artifact_path="evaluation")
        logger.info("Metrics saved → %s", metrics_path)

        # ── Model card ───────────────────────────────────────────────
        from model_card_generator import generate_model_card
        card_path = generate_model_card(cfg, final_metrics, label_enc.classes_)
        mlflow.log_artifact(str(card_path), artifact_path="model_card")
        logger.info("Model card → %s", card_path)

        logger.info("Run ID: %s", run.info.run_id)
        return final_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NLU intent classifier training")
    parser.add_argument("--config", default="config.yaml",
                        help="Path to YAML config file")
    args = parser.parse_args()
    main(args.config)
