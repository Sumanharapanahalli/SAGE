"""
train_ocr.py — TrOCR fine-tuning for invoice / receipt OCR.

Usage
─────
    python src/train_ocr.py --config config/ocr_config.yaml

Design decisions
────────────────
• TrOCRProcessor (pre-trained) is loaded once and shared across all splits.
  It is NOT re-fitted on project data → zero leakage risk.
• Train/val/test split is stratified by doc_type before ANY preprocessing.
• Augmentation pipeline is built for train only; eval datasets get None.
• All hyperparameters and results are logged to MLflow.
• Seed is set for Python, NumPy, and PyTorch for reproducibility.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from pathlib import Path

import mlflow
import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader
from transformers import (
    AdamW,
    TrOCRProcessor,
    VisionEncoderDecoderModel,
    get_linear_schedule_with_warmup,
    EarlyStoppingCallback,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    default_data_collator,
)

from data_utils import (
    build_eval_transform,
    build_train_transform,
    check_class_imbalance,
    compute_dataset_fingerprint,
    InvoiceOCRDataset,
    load_annotations,
    stratified_split,
)
from metrics import aggregate_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Reproducibility ───────────────────────────────────────────────────────────

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # Deterministic ops where possible
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    os.environ["PYTHONHASHSEED"] = str(seed)
    logger.info("Seed set to %d", seed)


# ── Config loader ─────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)
    logger.info("Config loaded from %s", path)
    return cfg


# ── HuggingFace Trainer metric wrapper ───────────────────────────────────────

def make_compute_metrics(processor: TrOCRProcessor):
    """Returns a compute_metrics fn compatible with Seq2SeqTrainer."""

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        pred_ids = np.argmax(logits[0], axis=-1) if isinstance(logits, tuple) else logits
        # Decode predictions
        pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
        # Replace -100 (padding) in labels before decoding
        labels = np.where(labels != -100, labels, processor.tokenizer.pad_token_id)
        label_str = processor.batch_decode(labels, skip_special_tokens=True)
        result = aggregate_metrics(label_str, pred_str)
        return result

    return compute_metrics


# ── Main training entry point ─────────────────────────────────────────────────

def train(cfg: dict) -> dict:
    seed = cfg["experiment"]["seed"]
    set_seed(seed)

    # ── 1. Load & validate annotations ───────────────────────────────────────
    df = load_annotations(cfg["data"]["annotation_file"])
    imbalance = check_class_imbalance(df, col=cfg["data"]["stratify_col"])

    # ── 2. Stratified split (NO feature statistics computed here) ─────────────
    train_df, val_df, test_df = stratified_split(
        df,
        stratify_col=cfg["data"]["stratify_col"],
        train_frac=cfg["data"]["splits"]["train"],
        val_frac=cfg["data"]["splits"]["val"],
        seed=seed,
    )

    train_fingerprint = compute_dataset_fingerprint(train_df)
    logger.info("Train set fingerprint: %s", train_fingerprint)

    # ── 3. Load pre-trained TrOCR processor (shared; NOT fitted on project data) ──
    checkpoint = cfg["model"]["base_checkpoint"]
    logger.info("Loading processor from %s", checkpoint)
    processor = TrOCRProcessor.from_pretrained(checkpoint)

    # ── 4. Build datasets (augmentation is train-only) ───────────────────────
    train_aug = build_train_transform(cfg["data"]) if cfg["data"]["augmentation"]["enabled"] else None
    eval_aug = build_eval_transform()   # always None

    raw_dir = cfg["data"]["raw_dir"]
    max_len = cfg["model"]["max_target_length"]

    train_dataset = InvoiceOCRDataset(train_df, raw_dir, processor, train_aug, max_len)
    val_dataset   = InvoiceOCRDataset(val_df,   raw_dir, processor, eval_aug,  max_len)
    test_dataset  = InvoiceOCRDataset(test_df,  raw_dir, processor, eval_aug,  max_len)

    logger.info(
        "Dataset sizes — train: %d | val: %d | test: %d",
        len(train_dataset), len(val_dataset), len(test_dataset),
    )

    # ── 5. Model ──────────────────────────────────────────────────────────────
    logger.info("Loading model from %s", checkpoint)
    model = VisionEncoderDecoderModel.from_pretrained(checkpoint)

    # Configure decoder start token and pad token
    model.config.decoder_start_token_id = processor.tokenizer.cls_token_id
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    model.config.vocab_size = model.config.decoder.vocab_size
    model.config.eos_token_id = processor.tokenizer.sep_token_id
    model.config.max_length = max_len
    model.config.num_beams = cfg["model"]["beam_size"]

    # ── 6. Training arguments ─────────────────────────────────────────────────
    tr = cfg["training"]
    output_dir = Path(tr["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=tr["num_epochs"],
        per_device_train_batch_size=tr["per_device_train_batch_size"],
        per_device_eval_batch_size=tr["per_device_eval_batch_size"],
        learning_rate=tr["learning_rate"],
        warmup_steps=tr["warmup_steps"],
        weight_decay=tr["weight_decay"],
        fp16=tr["fp16"] and torch.cuda.is_available(),
        gradient_accumulation_steps=tr["gradient_accumulation_steps"],
        save_strategy=tr["save_strategy"],
        evaluation_strategy=tr["evaluation_strategy"],
        load_best_model_at_end=tr["load_best_model_at_end"],
        metric_for_best_model=tr["metric_for_best_model"],
        greater_is_better=tr["greater_is_better"],
        predict_with_generate=True,
        generation_max_length=max_len,
        seed=seed,
        data_seed=seed,
        report_to=[],   # disable HF default reporters; we use MLflow directly
        logging_steps=50,
    )

    # ── 7. MLflow experiment ──────────────────────────────────────────────────
    mlflow.set_tracking_uri(cfg["experiment"]["mlflow_tracking_uri"])
    mlflow.set_experiment(cfg["experiment"]["name"])

    with mlflow.start_run(tags=cfg["experiment"]["run_tags"]) as run:
        # Log all config params flat
        mlflow.log_params({
            "base_checkpoint": checkpoint,
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "test_samples": len(test_df),
            "seed": seed,
            "train_fingerprint": train_fingerprint,
            "class_imbalance_detected": imbalance,
            "num_epochs": tr["num_epochs"],
            "learning_rate": tr["learning_rate"],
            "batch_size": tr["per_device_train_batch_size"],
            "max_target_length": max_len,
            "beam_size": cfg["model"]["beam_size"],
        })

        trainer = Seq2SeqTrainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            tokenizer=processor.tokenizer,
            data_collator=default_data_collator,
            compute_metrics=make_compute_metrics(processor),
            callbacks=[
                EarlyStoppingCallback(
                    early_stopping_patience=tr["early_stopping_patience"]
                )
            ],
        )

        # ── 8. Train ──────────────────────────────────────────────────────────
        logger.info("Starting training …")
        train_result = trainer.train()
        mlflow.log_metrics({
            "train_runtime_s": train_result.metrics["train_runtime"],
            "train_samples_per_sec": train_result.metrics["train_samples_per_second"],
        })

        # ── 9. Evaluate on held-out test set ──────────────────────────────────
        logger.info("Evaluating on test set …")
        test_results = trainer.predict(test_dataset)
        pred_ids = test_results.predictions
        label_ids = test_results.label_ids

        pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
        label_ids = np.where(
            label_ids != -100, label_ids, processor.tokenizer.pad_token_id
        )
        label_str = processor.batch_decode(label_ids, skip_special_tokens=True)

        test_metrics = aggregate_metrics(label_str, pred_str)
        logger.info("Test metrics: %s", test_metrics)
        mlflow.log_metrics({f"test_{k}": v for k, v in test_metrics.items()})

        # ── 10. Threshold gate ────────────────────────────────────────────────
        ev = cfg["evaluation"]
        if test_metrics["cer"] > ev["cer_threshold"]:
            logger.warning(
                "CER %.4f exceeds threshold %.4f — model may not be production-ready",
                test_metrics["cer"], ev["cer_threshold"],
            )

        # ── 11. Save model + processor ────────────────────────────────────────
        model_dir = Path(cfg["artifacts"]["model_dir"])
        model_dir.mkdir(parents=True, exist_ok=True)
        trainer.save_model(str(model_dir))
        processor.save_pretrained(str(model_dir))
        mlflow.log_artifacts(str(model_dir), artifact_path="model")
        logger.info("Model saved to %s", model_dir)

        # ── 12. Persist eval report ───────────────────────────────────────────
        eval_report = {
            "run_id": run.info.run_id,
            "train_fingerprint": train_fingerprint,
            "class_imbalance_detected": imbalance,
            "test_metrics": test_metrics,
            "thresholds": {
                "cer_threshold": ev["cer_threshold"],
                "wer_threshold": ev["wer_threshold"],
                "cer_pass": test_metrics["cer"] <= ev["cer_threshold"],
                "wer_pass": test_metrics["wer"] <= ev["wer_threshold"],
            },
        }
        eval_path = Path(cfg["artifacts"]["eval_report_path"])
        eval_path.parent.mkdir(parents=True, exist_ok=True)
        with open(eval_path, "w") as f:
            json.dump(eval_report, f, indent=2)
        mlflow.log_artifact(str(eval_path))

        return eval_report


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Train TrOCR on invoice/receipt data")
    parser.add_argument("--config", default="config/ocr_config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    report = train(cfg)

    print("\n── Training complete ─────────────────────────────────────────")
    print(f"  CER         : {report['test_metrics']['cer']:.4f}")
    print(f"  WER         : {report['test_metrics']['wer']:.4f}")
    print(f"  Exact Match : {report['test_metrics']['exact_match']:.4f}")
    print(f"  CER gate    : {'PASS' if report['thresholds']['cer_pass'] else 'FAIL'}")
    print(f"  WER gate    : {'PASS' if report['thresholds']['wer_pass'] else 'FAIL'}")
    print("──────────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
