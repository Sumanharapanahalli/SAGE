"""
Baseline Text Toxicity Detection — Fine-tuning Pipeline
========================================================
Pre-trained base : unitary/toxic-bert  (DistilBERT fine-tuned on Jigsaw)
Task             : Binary classification  (toxic / non-toxic)
Experiment log   : MLflow
Reproducibility  : seed fixed via transformers.set_seed + torch manual_seed

Usage
-----
    python train_toxicity_model.py --config config.yaml
    python train_toxicity_model.py --config config.yaml --smoke_test  # 200-row fast check
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Optional

import mlflow
import mlflow.pytorch
import numpy as np
import pandas as pd
import torch
import yaml
from datasets import ClassLabel, Dataset, DatasetDict, load_dataset
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("toxicity.train")


# ─────────────────────────────────────────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_config(path: str) -> Dict[str, Any]:
    with open(path) as fh:
        return yaml.safe_load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# Reproducibility
# ─────────────────────────────────────────────────────────────────────────────

def fix_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    set_seed(seed)
    logger.info("Global seed fixed to %d", seed)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading & splitting  (NO leakage: tokenizer fitted from vocab only)
# ─────────────────────────────────────────────────────────────────────────────

def load_and_split(cfg: Dict[str, Any], smoke_test: bool = False) -> DatasetDict:
    """Load raw dataset and perform stratified train/val/test split."""
    data_cfg = cfg["data"]
    text_col = data_cfg["text_column"]
    label_col = data_cfg["label_column"]

    logger.info("Loading dataset: %s", data_cfg["dataset_name"])

    try:
        raw = load_dataset(data_cfg["dataset_name"], split="train")
        df = raw.to_pandas()[[text_col, label_col]].dropna()
        df[label_col] = df[label_col].astype(int)
    except Exception as exc:
        logger.warning("Could not load HuggingFace dataset (%s); generating synthetic data.", exc)
        df = _synthetic_data(n=2000)
        text_col, label_col = "comment_text", "toxic"

    if smoke_test:
        df = df.sample(n=min(200, len(df)), random_state=cfg["training"]["seed"])
        logger.info("Smoke-test mode: using %d rows", len(df))

    # ── Stratified split (test first, then val from remaining train) ──────────
    seed = cfg["training"]["seed"]
    test_frac = data_cfg["test_size"]
    val_frac = data_cfg["val_size"]

    df_train_val, df_test = train_test_split(
        df,
        test_size=test_frac,
        stratify=df[label_col],
        random_state=seed,
    )
    val_frac_adj = val_frac / (1.0 - test_frac)
    df_train, df_val = train_test_split(
        df_train_val,
        test_size=val_frac_adj,
        stratify=df_train_val[label_col],
        random_state=seed,
    )

    logger.info(
        "Split → train=%d  val=%d  test=%d | positive rate train=%.3f  test=%.3f",
        len(df_train), len(df_val), len(df_test),
        df_train[label_col].mean(), df_test[label_col].mean(),
    )

    # ── Class-imbalance check ─────────────────────────────────────────────────
    pos_rate = df_train[label_col].mean()
    if pos_rate < 0.10 or pos_rate > 0.90:
        logger.warning(
            "Class imbalance detected (positive_rate=%.3f). "
            "Consider class weights or oversampling.",
            pos_rate,
        )

    def _to_hf(dataframe: pd.DataFrame) -> Dataset:
        return Dataset.from_dict(
            {"text": dataframe[text_col].tolist(), "label": dataframe[label_col].tolist()}
        )

    return DatasetDict(
        train=_to_hf(df_train),
        validation=_to_hf(df_val),
        test=_to_hf(df_test),
    )


def _synthetic_data(n: int = 2000) -> pd.DataFrame:
    """Generate labelled synthetic data when the real dataset is unavailable."""
    rng = np.random.default_rng(42)
    toxic_phrases = [
        "I hate you", "you are disgusting", "go kill yourself",
        "terrible person", "you are worthless", "offensive garbage",
    ]
    clean_phrases = [
        "Have a great day", "nice to meet you", "the weather is lovely",
        "I enjoy reading books", "thanks for your help", "great work",
    ]
    rows = []
    for _ in range(n):
        is_toxic = rng.random() < 0.30
        phrase = rng.choice(toxic_phrases if is_toxic else clean_phrases)
        extra = " ".join(rng.choice(["word"] * 20, size=rng.integers(5, 25)))
        rows.append({"comment_text": f"{phrase} {extra}", "toxic": int(is_toxic)})
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Tokenisation  (tokenizer loaded from pre-trained vocab — no fitting on data)
# ─────────────────────────────────────────────────────────────────────────────

def tokenize_datasets(
    datasets: DatasetDict,
    tokenizer: AutoTokenizer,
    max_length: int,
) -> DatasetDict:
    """Apply tokenization. Tokenizer vocab is pre-trained — zero leakage risk."""

    def _tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=max_length,
            padding=False,          # dynamic padding via DataCollatorWithPadding
        )

    tokenized = datasets.map(_tokenize, batched=True, remove_columns=["text"])
    tokenized = tokenized.cast_column("label", ClassLabel(names=["non_toxic", "toxic"]))
    return tokenized


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(eval_pred) -> Dict[str, float]:
    logits, labels = eval_pred
    probs = torch.softmax(torch.tensor(logits), dim=-1)[:, 1].numpy()
    preds = (probs >= 0.5).astype(int)
    return {
        "accuracy":  float(accuracy_score(labels, preds)),
        "f1":        float(f1_score(labels, preds, zero_division=0)),
        "precision": float(precision_score(labels, preds, zero_division=0)),
        "recall":    float(recall_score(labels, preds, zero_division=0)),
        "roc_auc":   float(roc_auc_score(labels, probs)),
    }


def full_evaluation(
    trainer: Trainer,
    dataset: Dataset,
    split_name: str,
) -> Dict[str, Any]:
    """Compute full evaluation including confusion matrix and classification report."""
    preds_output = trainer.predict(dataset)
    logits = preds_output.predictions
    labels = preds_output.label_ids
    probs = torch.softmax(torch.tensor(logits), dim=-1)[:, 1].numpy()
    preds = (probs >= 0.5).astype(int)

    report = classification_report(
        labels, preds,
        target_names=["non_toxic", "toxic"],
        output_dict=True,
    )
    cm = confusion_matrix(labels, preds).tolist()

    results = {
        "split": split_name,
        "accuracy":    float(accuracy_score(labels, preds)),
        "f1":          float(f1_score(labels, preds, zero_division=0)),
        "precision":   float(precision_score(labels, preds, zero_division=0)),
        "recall":      float(recall_score(labels, preds, zero_division=0)),
        "roc_auc":     float(roc_auc_score(labels, probs)),
        "confusion_matrix": cm,
        "classification_report": report,
    }
    logger.info(
        "[%s] accuracy=%.4f  f1=%.4f  precision=%.4f  recall=%.4f  roc_auc=%.4f",
        split_name,
        results["accuracy"], results["f1"],
        results["precision"], results["recall"], results["roc_auc"],
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────────────────────

def build_training_args(cfg: Dict[str, Any], output_dir: str) -> TrainingArguments:
    tc = cfg["training"]
    return TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=tc["epochs"],
        per_device_train_batch_size=tc["batch_size"],
        per_device_eval_batch_size=tc["eval_batch_size"],
        learning_rate=tc["learning_rate"],
        weight_decay=tc["weight_decay"],
        warmup_ratio=tc["warmup_ratio"],
        gradient_accumulation_steps=tc["gradient_accumulation_steps"],
        fp16=tc["fp16"] and torch.cuda.is_available(),
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model=tc["metric_for_best_model"],
        greater_is_better=tc["greater_is_better"],
        logging_steps=50,
        report_to="none",           # MLflow handled manually below
        seed=tc["seed"],
        dataloader_num_workers=2,
    )


def train(cfg: Dict[str, Any], smoke_test: bool = False) -> Dict[str, Any]:
    fix_seed(cfg["training"]["seed"])

    # ── MLflow setup ─────────────────────────────────────────────────────────
    mlflow.set_tracking_uri(cfg["paths"]["mlflow_tracking_uri"])
    mlflow.set_experiment("toxicity_detection_baseline")

    with mlflow.start_run(run_name="toxic-bert-finetune") as run:
        mlflow.log_params({
            "model": cfg["model"]["pretrained_name"],
            "max_length": cfg["model"]["max_length"],
            "epochs": cfg["training"]["epochs"],
            "batch_size": cfg["training"]["batch_size"],
            "learning_rate": cfg["training"]["learning_rate"],
            "weight_decay": cfg["training"]["weight_decay"],
            "seed": cfg["training"]["seed"],
            "smoke_test": smoke_test,
        })

        # ── Load tokenizer (pre-trained vocab, NOT fit on our data) ───────────
        logger.info("Loading tokenizer: %s", cfg["model"]["pretrained_name"])
        tokenizer = AutoTokenizer.from_pretrained(cfg["model"]["pretrained_name"])

        # ── Data ──────────────────────────────────────────────────────────────
        raw_datasets = load_and_split(cfg, smoke_test=smoke_test)
        tokenized = tokenize_datasets(raw_datasets, tokenizer, cfg["model"]["max_length"])
        collator = DataCollatorWithPadding(tokenizer=tokenizer)

        # ── Model ─────────────────────────────────────────────────────────────
        logger.info("Loading model: %s", cfg["model"]["pretrained_name"])
        model = AutoModelForSequenceClassification.from_pretrained(
            cfg["model"]["pretrained_name"],
            num_labels=cfg["model"]["num_labels"],
            hidden_dropout_prob=cfg["model"]["dropout"],
            ignore_mismatched_sizes=True,
        )

        output_dir = cfg["paths"]["output_dir"]
        training_args = build_training_args(cfg, output_dir)

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized["train"],
            eval_dataset=tokenized["validation"],
            tokenizer=tokenizer,
            data_collator=collator,
            compute_metrics=compute_metrics,
            callbacks=[
                EarlyStoppingCallback(
                    early_stopping_patience=cfg["training"]["early_stopping_patience"]
                )
            ],
        )

        # ── Train ─────────────────────────────────────────────────────────────
        logger.info("Starting training …")
        t0 = time.time()
        train_result = trainer.train()
        train_secs = time.time() - t0
        logger.info("Training finished in %.1f s", train_secs)

        # ── Evaluate ──────────────────────────────────────────────────────────
        val_results  = full_evaluation(trainer, tokenized["validation"], "validation")
        test_results = full_evaluation(trainer, tokenized["test"],       "test")

        # ── Log to MLflow ──────────────────────────────────────────────────────
        for k, v in val_results.items():
            if isinstance(v, float):
                mlflow.log_metric(f"val_{k}", v)
        for k, v in test_results.items():
            if isinstance(v, float):
                mlflow.log_metric(f"test_{k}", v)
        mlflow.log_metric("train_runtime_s", train_secs)

        # ── Save model ────────────────────────────────────────────────────────
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)
        logger.info("Model saved to %s", output_dir)

        # ── Persist results JSON ──────────────────────────────────────────────
        results_path = Path(output_dir) / "evaluation_results.json"
        with open(results_path, "w") as fh:
            json.dump({"validation": val_results, "test": test_results}, fh, indent=2)
        mlflow.log_artifact(str(results_path))

        logger.info("MLflow run_id: %s", run.info.run_id)
        return {"val": val_results, "test": test_results, "run_id": run.info.run_id}


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train toxicity detection model")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--smoke_test", action="store_true",
                        help="Run on 200 rows for CI/fast iteration")
    args = parser.parse_args()

    cfg = load_config(args.config)
    results = train(cfg, smoke_test=args.smoke_test)

    print("\n=== Final Test Metrics ===")
    for k in ("accuracy", "f1", "precision", "recall", "roc_auc"):
        print(f"  {k:>12}: {results['test'][k]:.4f}")


if __name__ == "__main__":
    main()
