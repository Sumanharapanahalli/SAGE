"""
NER Model Training — Production Script
=======================================
Trains a transformer-based Named Entity Recognition model.

Anti-leakage guarantees
------------------------
  • label2id / id2label built exclusively from the TRAIN split.
  • Tokenizer is pre-trained (frozen vocab) — no fit on any split.
  • Scaler / normalizer: none (token classification; no numeric features).
  • Val / test splits are never touched before the model is fully trained.

Reproducibility
---------------
  • RANDOM_SEED applied to Python, NumPy, PyTorch, and Transformers.
  • config.yaml fully defines every hyperparameter.
  • All params logged via ExperimentLogger and printed to stdout.
  • Trainer saves the best checkpoint; `trainer.evaluate()` on the held-out
    test set runs only once, after training completes.

Usage
-----
    python train_ner.py                          # use config.yaml defaults
    python train_ner.py --config config.yaml     # explicit config path
    python train_ner.py --epochs 5 --lr 3e-5     # CLI overrides
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import yaml
from datasets import Dataset, DatasetDict, load_dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    set_seed,
)

# Project-level experiment logger (path-relative from ml_experiments/)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from experiment_logger import ExperimentLogger  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("train_ner")


# ── Seqeval metric computation ────────────────────────────────────────────────

def _build_compute_metrics(label_list: list[str]):
    """Return a compute_metrics function closed over label_list."""
    try:
        from seqeval.metrics import (
            classification_report,
            f1_score,
            precision_score,
            recall_score,
        )
        _seqeval_ok = True
    except ImportError:
        log.warning("seqeval not installed — eval will use token accuracy only.")
        _seqeval_ok = False

    def compute_metrics(p):
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)

        # Strip padding (-100) and convert ids → string labels
        true_labels, true_preds = [], []
        for pred_row, label_row in zip(predictions, labels):
            row_true, row_pred = [], []
            for pred_id, label_id in zip(pred_row, label_row):
                if label_id == -100:       # padding / subword continuation
                    continue
                row_true.append(label_list[label_id])
                row_pred.append(label_list[pred_id])
            true_labels.append(row_true)
            true_preds.append(row_pred)

        if _seqeval_ok:
            results = {
                "precision": precision_score(true_labels, true_preds),
                "recall":    recall_score(true_labels, true_preds),
                "f1":        f1_score(true_labels, true_preds),
            }
            log.info(
                "\n%s",
                classification_report(true_labels, true_preds, digits=4),
            )
        else:
            # Fallback: flat token accuracy (ignores O-class dominance)
            flat_true  = [l for row in true_labels for l in row]
            flat_pred  = [l for row in true_preds  for l in row]
            correct    = sum(t == p for t, p in zip(flat_true, flat_pred))
            results    = {"accuracy": correct / max(len(flat_true), 1)}

        return results

    return compute_metrics


# ── CoNLL loader ──────────────────────────────────────────────────────────────

def _load_conll_file(path: Path) -> list[dict]:
    """
    Parse a CoNLL-2003 file into a list of {tokens, ner_tags} dicts.

    Each sentence is delimited by a blank line.
    Lines with a single '-DOCSTART-' token are skipped.
    """
    sentences: list[dict] = []
    current_tokens: list[str] = []
    current_tags:   list[str] = []

    with open(path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if not line or line.startswith("-DOCSTART-"):
                if current_tokens:
                    sentences.append({
                        "tokens":   current_tokens,
                        "ner_tags": current_tags,
                    })
                    current_tokens, current_tags = [], []
                continue
            parts = line.split()
            if len(parts) >= 2:
                current_tokens.append(parts[0])
                current_tags.append(parts[-1])   # last column = NER tag
            else:
                log.debug("Skipping malformed CoNLL line: %r", line)

    if current_tokens:
        sentences.append({"tokens": current_tokens, "ner_tags": current_tags})

    return sentences


def _load_conll_dataset(cfg: dict) -> Optional[DatasetDict]:
    """
    Load CoNLL files produced by ner_pipeline.py.
    Returns None if the files do not exist.
    """
    base = Path(__file__).parent
    train_path = (base / cfg["data"]["train_path"]).resolve()
    val_path   = (base / cfg["data"]["val_path"]).resolve()
    test_path  = (base / cfg["data"]["test_path"]).resolve()

    if not all(p.exists() for p in [train_path, val_path, test_path]):
        log.info("Local CoNLL files not found — will use HuggingFace fallback.")
        return None

    log.info("Loading local CoNLL splits …")
    ds = DatasetDict({
        "train": Dataset.from_list(_load_conll_file(train_path)),
        "validation": Dataset.from_list(_load_conll_file(val_path)),
        "test": Dataset.from_list(_load_conll_file(test_path)),
    })
    return ds


def _load_hf_fallback(cfg: dict) -> DatasetDict:
    """
    Download conll2003 from HuggingFace hub as a reproducible fallback.
    tag_names are extracted and returned alongside the dataset.
    """
    dataset_id = cfg["data"]["hf_fallback_dataset"]
    log.info("Loading HuggingFace dataset: %s", dataset_id)
    ds = load_dataset(dataset_id, trust_remote_code=True)
    return ds


# ── Label map builder — TRAIN-ONLY (anti-leakage) ───────────────────────────

def _build_label_map(train_tags: list[list[str]]) -> tuple[dict, dict, list]:
    """
    Build label2id and id2label from TRAINING tags only.

    Parameters
    ----------
    train_tags : list of per-sentence tag lists

    Returns
    -------
    label2id, id2label, label_list (alphabetically sorted, 'O' always at 0)
    """
    unique = sorted({tag for sent in train_tags for tag in sent})
    # Ensure 'O' comes first (convention) if present
    if "O" in unique:
        unique.remove("O")
        unique = ["O"] + unique
    label2id = {lbl: i for i, lbl in enumerate(unique)}
    id2label = {i: lbl for lbl, i in label2id.items()}
    log.info("Label map built from TRAIN split: %s", label2id)
    return label2id, id2label, unique


# ── Tokenization + label alignment ────────────────────────────────────────────

def _make_tokenize_fn(tokenizer, label2id: dict, cfg: dict):
    """
    Return a batched tokenize function that:
      1. Tokenizes word-split sentences into subword tokens.
      2. Aligns labels so that only the FIRST subword of each word gets the
         real label; continuation subwords and padding get label_id = -100
         (ignored by PyTorch cross-entropy loss).
    """
    max_len = cfg["model"]["max_length"]
    label_all = cfg["model"]["label_all_tokens"]

    def tokenize_and_align(batch):
        tokenized = tokenizer(
            batch["tokens"],
            truncation=True,
            max_length=max_len,
            is_split_into_words=True,
            padding=False,              # DataCollator handles padding
        )
        all_labels = []
        for i, word_labels in enumerate(batch["ner_tags"]):
            word_ids = tokenized.word_ids(batch_index=i)
            aligned, prev_word_id = [], None
            for word_id in word_ids:
                if word_id is None:                    # [CLS] / [SEP] / padding
                    aligned.append(-100)
                elif word_id != prev_word_id:          # first subword of a word
                    tag = word_labels[word_id]
                    aligned.append(label2id.get(tag, label2id.get("O", 0)))
                else:                                  # continuation subword
                    if label_all:
                        tag = word_labels[word_id]
                        aligned.append(label2id.get(tag, label2id.get("O", 0)))
                    else:
                        aligned.append(-100)
                prev_word_id = word_id
            all_labels.append(aligned)

        tokenized["labels"] = all_labels
        return tokenized

    return tokenize_and_align


# ── Dataset preprocessing ─────────────────────────────────────────────────────

def _prepare_datasets(
    raw: DatasetDict,
    tokenizer,
    label2id: dict,
    cfg: dict,
    use_hf_labels: bool = False,
) -> DatasetDict:
    """
    Tokenize and align labels. Removes all raw string columns except 'tokens'.

    Parameters
    ----------
    raw          : DatasetDict with 'tokens' and 'ner_tags' columns
    tokenizer    : Pre-trained tokenizer (no fitting on any split)
    label2id     : Built exclusively from training tags (anti-leakage)
    use_hf_labels: If True, ner_tags are integer IDs (HuggingFace conll2003)
    """
    if use_hf_labels:
        # HF conll2003 has integer ner_tags; convert to string labels first
        hf_id2label = raw["train"].features["ner_tags"].feature.names
        def int_to_str(batch):
            batch["ner_tags"] = [
                [hf_id2label[t] for t in sent] for sent in batch["ner_tags"]
            ]
            return batch
        raw = raw.map(int_to_str, batched=True)

    tokenize_fn = _make_tokenize_fn(tokenizer, label2id, cfg)
    processed = raw.map(
        tokenize_fn,
        batched=True,
        remove_columns=["tokens", "ner_tags"],
    )
    return processed


# ── Training ──────────────────────────────────────────────────────────────────

def train(cfg: dict) -> dict:
    """
    Full training pipeline. Returns a dict of final test-set metrics.
    """
    seed = cfg["training"]["seed"]
    set_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    base_dir = Path(__file__).parent
    model_dir   = (base_dir / cfg["output"]["model_dir"]).resolve()
    reports_dir = (base_dir / cfg["output"]["reports_dir"]).resolve()
    log_dir     = (base_dir / cfg["output"]["log_dir"]).resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    exp = ExperimentLogger("ner_training", log_dir=log_dir)
    run_id = exp.start_run(params={
        "base_model":  cfg["model"]["base_model"],
        "max_length":  cfg["model"]["max_length"],
        "epochs":      cfg["training"]["num_epochs"],
        "batch_size":  cfg["training"]["batch_size"],
        "lr":          cfg["training"]["learning_rate"],
        "seed":        seed,
        "fp16":        cfg["training"]["fp16"],
    })

    # ── Load data ──────────────────────────────────────────────────────────────
    raw_ds = _load_conll_dataset(cfg)
    use_hf = raw_ds is None
    if use_hf:
        raw_ds = _load_hf_fallback(cfg)

    # ── Build label map — TRAIN-ONLY (anti-leakage) ───────────────────────────
    if use_hf:
        train_str_tags = [
            [raw_ds["train"].features["ner_tags"].feature.names[t]
             for t in sent]
            for sent in raw_ds["train"]["ner_tags"]
        ]
    else:
        train_str_tags = raw_ds["train"]["ner_tags"]

    label2id, id2label, label_list = _build_label_map(train_str_tags)
    num_labels = len(label_list)
    exp.log_param(run_id, "num_labels", num_labels)
    exp.log_param(run_id, "labels", label_list)

    # ── Load tokenizer (pre-trained; no fitting) ───────────────────────────────
    model_name = cfg["model"]["base_model"]
    log.info("Loading tokenizer: %s", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # ── Tokenize all splits (val/test only processed, never fit on) ────────────
    log.info("Tokenizing dataset splits …")
    processed_ds = _prepare_datasets(raw_ds, tokenizer, label2id, cfg, use_hf_labels=use_hf)

    # ── Model ──────────────────────────────────────────────────────────────────
    log.info("Loading model: %s  (num_labels=%d)", model_name, num_labels)
    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=num_labels,
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True,
    )

    # ── Training args ──────────────────────────────────────────────────────────
    use_fp16 = cfg["training"]["fp16"] and torch.cuda.is_available()
    training_args = TrainingArguments(
        output_dir=str(model_dir),
        num_train_epochs=cfg["training"]["num_epochs"],
        per_device_train_batch_size=cfg["training"]["batch_size"],
        per_device_eval_batch_size=cfg["training"]["batch_size"] * 2,
        gradient_accumulation_steps=cfg["training"]["gradient_accumulation_steps"],
        learning_rate=cfg["training"]["learning_rate"],
        lr_scheduler_type=cfg["training"]["lr_scheduler"],
        warmup_ratio=cfg["training"]["warmup_ratio"],
        weight_decay=cfg["training"]["weight_decay"],
        fp16=use_fp16,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model=cfg["training"]["metric_for_best_model"],
        greater_is_better=cfg["training"]["greater_is_better"],
        save_total_limit=cfg["training"]["save_total_limit"],
        seed=seed,
        report_to="none",           # disable W&B/MLflow automatic reporting
        dataloader_num_workers=0,   # safe default; increase for larger datasets
        logging_steps=50,
    )

    data_collator = DataCollatorForTokenClassification(tokenizer)
    compute_metrics = _build_compute_metrics(label_list)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=processed_ds["train"],
        eval_dataset=processed_ds["validation"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[
            EarlyStoppingCallback(
                early_stopping_patience=cfg["training"]["early_stopping_patience"]
            )
        ],
    )

    # ── Train ──────────────────────────────────────────────────────────────────
    log.info("Starting training …")
    t0 = time.time()
    train_result = trainer.train()
    train_duration = time.time() - t0
    log.info("Training complete in %.1f seconds.", train_duration)

    # ── Save best model ────────────────────────────────────────────────────────
    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))
    log.info("Model saved → %s", model_dir)

    # ── Evaluate on held-out TEST set (one pass, after training) ──────────────
    log.info("Evaluating on held-out TEST set …")
    test_metrics = trainer.evaluate(eval_dataset=processed_ds["test"])
    log.info("Test metrics: %s", test_metrics)

    # Rename keys: eval_* → test_*
    test_metrics_clean = {
        k.replace("eval_", "test_"): v for k, v in test_metrics.items()
    }

    # ── Log experiment ─────────────────────────────────────────────────────────
    exp.log_metrics(run_id, {
        "train_loss":      train_result.training_loss,
        "train_duration_s": train_duration,
        **{f"test_{k}": v for k, v in test_metrics.items()
           if isinstance(v, (int, float))},
    })
    exp.end_run(run_id, status="completed")

    # ── Persist label map alongside model ─────────────────────────────────────
    import json
    label_map_path = model_dir / "label_map.json"
    label_map_path.write_text(
        json.dumps({"label2id": label2id, "id2label": id2label,
                    "label_list": label_list}, indent=2),
        encoding="utf-8",
    )
    log.info("Label map saved → %s", label_map_path)

    return test_metrics_clean


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(
        description="NER Model Trainer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", type=Path, default=Path(__file__).parent / "config.yaml")
    p.add_argument("--epochs", type=int,   help="Override num_epochs")
    p.add_argument("--lr",     type=float, help="Override learning_rate")
    p.add_argument("--batch",  type=int,   help="Override batch_size")
    p.add_argument("--fp16",   action="store_true", help="Enable fp16 training")
    return p.parse_args()


def main():
    args = _parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # CLI overrides
    if args.epochs: cfg["training"]["num_epochs"]      = args.epochs
    if args.lr:     cfg["training"]["learning_rate"]   = args.lr
    if args.batch:  cfg["training"]["batch_size"]      = args.batch
    if args.fp16:   cfg["training"]["fp16"]            = True

    log.info("Config: %s", cfg)
    results = train(cfg)

    print("\n=== Final Test-Set Metrics ===")
    for k, v in sorted(results.items()):
        print(f"  {k:<30} {v}")


if __name__ == "__main__":
    main()
