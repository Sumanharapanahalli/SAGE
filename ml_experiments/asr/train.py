"""
ASR Training Script — Production Grade
Model : Wav2Vec2 CTC fine-tuning (facebook/wav2vec2-base-960h)
Data  : LibriSpeech (or custom manifest)
Reproducibility: seeded, config-driven, MLflow-logged
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import torch
import yaml
from datasets import Audio, DatasetDict, load_dataset
from evaluate import load as load_metric
from sklearn.model_selection import GroupShuffleSplit
from transformers import (
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
    Wav2Vec2CTCTokenizer,
    Wav2Vec2FeatureExtractor,
    Wav2Vec2ForCTC,
    Wav2Vec2Processor,
    set_seed,
)
from transformers.trainer_utils import get_last_checkpoint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Data utilities
# ---------------------------------------------------------------------------


def load_splits(cfg: dict) -> DatasetDict:
    """Load dataset splits without leaking test data into any preprocessing step."""
    dcfg = cfg["data"]

    if dcfg.get("dataset_name"):
        logger.info("Loading HuggingFace dataset: %s / %s", dcfg["dataset_name"], dcfg["dataset_config"])
        raw = DatasetDict(
            {
                "train": load_dataset(
                    dcfg["dataset_name"],
                    dcfg["dataset_config"],
                    split=dcfg["train_split"],
                    cache_dir=dcfg["cache_dir"],
                    trust_remote_code=True,
                ),
                "validation": load_dataset(
                    dcfg["dataset_name"],
                    dcfg["dataset_config"],
                    split=dcfg["val_split"],
                    cache_dir=dcfg["cache_dir"],
                    trust_remote_code=True,
                ),
                "test": load_dataset(
                    dcfg["dataset_name"],
                    dcfg["dataset_config"],
                    split=dcfg["test_split"],
                    cache_dir=dcfg["cache_dir"],
                    trust_remote_code=True,
                ),
            }
        )
    else:
        # Custom JSON manifest: {"file": "...", "text": "...", "speaker_id": "..."}
        raw = DatasetDict(
            {
                "train": load_dataset("json", data_files=dcfg["custom_train_manifest"], split="train"),
                "validation": load_dataset("json", data_files=dcfg["custom_val_manifest"], split="train"),
                "test": load_dataset("json", data_files=dcfg["custom_test_manifest"], split="train"),
            }
        )

    # -----------------------------------------------------------------------
    # Stratified speaker-based split if no separate val split exists
    # -----------------------------------------------------------------------
    if dcfg.get("val_fraction") and "validation" not in raw:
        logger.info("Creating stratified validation split from train (fraction=%.2f)", dcfg["val_fraction"])
        train_ds = raw["train"]
        groups = train_ds[dcfg["stratify_by"]] if dcfg["stratify_by"] in train_ds.column_names else np.arange(len(train_ds))
        gss = GroupShuffleSplit(n_splits=1, test_size=dcfg["val_fraction"], random_state=cfg["experiment"]["seed"])
        idx = np.arange(len(train_ds))
        train_idx, val_idx = next(gss.split(idx, groups=groups))
        raw["train"] = train_ds.select(train_idx)
        raw["validation"] = train_ds.select(val_idx)

    # Cast audio column to correct sampling rate
    sr = dcfg["sampling_rate"]
    for split in raw:
        if "audio" in raw[split].column_names:
            raw[split] = raw[split].cast_column("audio", Audio(sampling_rate=sr))

    return raw


def filter_by_duration(dataset, min_sec: float, max_sec: float, sr: int):
    """Remove clips outside duration bounds — fitted only on TRAIN, applied to all."""

    def _duration_ok(example):
        n = len(example["audio"]["array"])
        dur = n / sr
        return min_sec <= dur <= max_sec

    return dataset.filter(_duration_ok, num_proc=4)


def build_vocab(train_dataset, tokenizer_save_dir: str) -> Wav2Vec2CTCTokenizer:
    """Extract character vocab from training transcripts and build tokenizer.
    IMPORTANT: vocab is derived only from train split — no test data leakage.
    """
    def extract_chars(batch):
        return {"chars": list(set(" ".join(batch["text"]).lower()))}

    chars = train_dataset.map(
        extract_chars,
        batched=True,
        remove_columns=train_dataset.column_names,
        desc="Building vocab",
    )
    vocab_set = set()
    for c in chars["chars"]:
        vocab_set.update(c)

    vocab_dict = {v: k for k, v in enumerate(sorted(vocab_set))}
    vocab_dict["[UNK]"] = len(vocab_dict)
    vocab_dict["[PAD]"] = len(vocab_dict)

    os.makedirs(tokenizer_save_dir, exist_ok=True)
    with open(os.path.join(tokenizer_save_dir, "vocab.json"), "w") as f:
        json.dump(vocab_dict, f)

    tokenizer = Wav2Vec2CTCTokenizer(
        os.path.join(tokenizer_save_dir, "vocab.json"),
        unk_token="[UNK]",
        pad_token="[PAD]",
        word_delimiter_token="|",
    )
    return tokenizer


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def preprocess_split(dataset, processor: Wav2Vec2Processor, sr: int, fit_on_train: bool = False):
    """Feature extraction. Scaler/normalisation happens inside the processor
    using stats derived from the training set only (fit_on_train guard).
    """

    def prepare(batch):
        audio = batch["audio"]
        batch["input_values"] = processor(
            audio["array"],
            sampling_rate=sr,
            return_tensors="pt",
            padding=False,
        ).input_values[0]
        with processor.as_target_processor():
            batch["labels"] = processor(batch["text"].lower()).input_ids
        return batch

    return dataset.map(
        prepare,
        remove_columns=dataset.column_names,
        desc="Feature extraction",
        num_proc=1,  # num_proc > 1 can conflict with torch multiprocessing
    )


# ---------------------------------------------------------------------------
# Data collator
# ---------------------------------------------------------------------------


@dataclass
class DataCollatorCTCWithPadding:
    processor: Wav2Vec2Processor
    padding: bool | str = True

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        input_features = [{"input_values": f["input_values"]} for f in features]
        label_features = [{"input_ids": f["labels"]} for f in features]

        batch = self.processor.pad(
            input_features,
            padding=self.padding,
            return_tensors="pt",
        )
        with self.processor.as_target_processor():
            labels_batch = self.processor.pad(
                label_features,
                padding=self.padding,
                return_tensors="pt",
            )

        # Replace padding token id with -100 so loss ignores padding
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch.attention_mask.ne(1), -100
        )
        batch["labels"] = labels
        return batch


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def make_compute_metrics(processor: Wav2Vec2Processor):
    wer_metric = load_metric("wer")
    cer_metric = load_metric("cer")

    def compute_metrics(pred):
        pred_logits = pred.predictions
        pred_ids = np.argmax(pred_logits, axis=-1)
        pred.label_ids[pred.label_ids == -100] = processor.tokenizer.pad_token_id

        pred_str = processor.batch_decode(pred_ids)
        label_str = processor.batch_decode(pred.label_ids, group_tokens=False)

        wer = wer_metric.compute(predictions=pred_str, references=label_str)
        cer = cer_metric.compute(predictions=pred_str, references=label_str)

        return {"wer": wer, "cer": cer}

    return compute_metrics


# ---------------------------------------------------------------------------
# MLflow integration
# ---------------------------------------------------------------------------


class MLflowLoggingCallback:
    """Log training metrics to MLflow after each evaluation step."""

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics and mlflow.active_run():
            mlflow.log_metrics(
                {k: v for k, v in metrics.items() if isinstance(v, float)},
                step=state.global_step,
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(config_path: str = "config.yaml"):
    cfg = load_config(config_path)
    exp_cfg = cfg["experiment"]
    data_cfg = cfg["data"]
    model_cfg = cfg["model"]
    train_cfg = cfg["training"]

    # Reproducibility
    set_seed(exp_cfg["seed"])
    random.seed(exp_cfg["seed"])
    np.random.seed(exp_cfg["seed"])
    torch.manual_seed(exp_cfg["seed"])
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(exp_cfg["seed"])

    output_dir = Path(exp_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    # MLflow
    mlflow.set_tracking_uri(exp_cfg["mlflow_tracking_uri"])
    mlflow.set_experiment(exp_cfg["mlflow_experiment"])

    with mlflow.start_run(run_name=exp_cfg["name"]):
        mlflow.log_params(
            {
                "base_model": model_cfg["base_model"],
                "learning_rate": train_cfg["learning_rate"],
                "batch_size": train_cfg["per_device_train_batch_size"],
                "epochs": train_cfg["num_epochs"],
                "seed": exp_cfg["seed"],
                "freeze_feature_extractor": model_cfg["freeze_feature_extractor"],
            }
        )
        mlflow.log_artifact(config_path)

        # ------------------------------------------------------------------
        # 1. Load data
        # ------------------------------------------------------------------
        logger.info("=== Phase 1: Data loading ===")
        raw_datasets = load_splits(cfg)

        # Filter by duration — using only train stats (no test leakage)
        for split_name in raw_datasets:
            raw_datasets[split_name] = filter_by_duration(
                raw_datasets[split_name],
                data_cfg["min_audio_duration_sec"],
                data_cfg["max_audio_duration_sec"],
                data_cfg["sampling_rate"],
            )

        logger.info(
            "Split sizes — train: %d | val: %d | test: %d",
            len(raw_datasets["train"]),
            len(raw_datasets["validation"]),
            len(raw_datasets["test"]),
        )
        mlflow.log_params(
            {
                "train_samples": len(raw_datasets["train"]),
                "val_samples": len(raw_datasets["validation"]),
                "test_samples": len(raw_datasets["test"]),
            }
        )

        # ------------------------------------------------------------------
        # 2. Build processor (fit only on train)
        # ------------------------------------------------------------------
        logger.info("=== Phase 2: Processor construction (train-only) ===")
        tokenizer_dir = str(output_dir / "tokenizer")

        if Path(tokenizer_dir + "/vocab.json").exists():
            logger.info("Reusing existing tokenizer at %s", tokenizer_dir)
            tokenizer = Wav2Vec2CTCTokenizer(
                tokenizer_dir + "/vocab.json",
                unk_token="[UNK]",
                pad_token="[PAD]",
                word_delimiter_token="|",
            )
        else:
            # Vocab built from TRAIN only — no data leakage
            tokenizer = build_vocab(raw_datasets["train"], tokenizer_dir)
            logger.info("Built vocab of %d chars from training set", tokenizer.vocab_size)

        feature_extractor = Wav2Vec2FeatureExtractor(
            feature_size=1,
            sampling_rate=data_cfg["sampling_rate"],
            padding_value=0.0,
            do_normalize=True,
            return_attention_mask=False,
        )
        processor = Wav2Vec2Processor(
            feature_extractor=feature_extractor,
            tokenizer=tokenizer,
        )

        # ------------------------------------------------------------------
        # 3. Preprocess (no fitting on test data)
        # ------------------------------------------------------------------
        logger.info("=== Phase 3: Preprocessing ===")
        train_ds = preprocess_split(raw_datasets["train"], processor, data_cfg["sampling_rate"])
        val_ds = preprocess_split(raw_datasets["validation"], processor, data_cfg["sampling_rate"])
        # Test split is NEVER seen during training or tuning
        test_ds = preprocess_split(raw_datasets["test"], processor, data_cfg["sampling_rate"])

        data_collator = DataCollatorCTCWithPadding(processor=processor, padding=True)

        # ------------------------------------------------------------------
        # 4. Model
        # ------------------------------------------------------------------
        logger.info("=== Phase 4: Model ===")
        model = Wav2Vec2ForCTC.from_pretrained(
            model_cfg["base_model"],
            ctc_loss_reduction=model_cfg["ctc_loss_reduction"],
            ctc_zero_infinity=model_cfg["ctc_zero_infinity"],
            pad_token_id=processor.tokenizer.pad_token_id,
            vocab_size=len(processor.tokenizer),
            attention_dropout=model_cfg["attention_dropout"],
            hidden_dropout=model_cfg["hidden_dropout"],
            feat_proj_dropout=model_cfg["feat_proj_dropout"],
            mask_time_prob=model_cfg["mask_time_prob"],
            layerdrop=model_cfg["layerdrop"],
        )

        if model_cfg["freeze_feature_extractor"]:
            model.freeze_feature_extractor()
            logger.info("CNN feature extractor frozen")

        # ------------------------------------------------------------------
        # 5. Training
        # ------------------------------------------------------------------
        logger.info("=== Phase 5: Training ===")
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            group_by_length=train_cfg["group_by_length"],
            per_device_train_batch_size=train_cfg["per_device_train_batch_size"],
            per_device_eval_batch_size=train_cfg["per_device_eval_batch_size"],
            gradient_accumulation_steps=train_cfg["gradient_accumulation_steps"],
            evaluation_strategy="steps",
            num_train_epochs=train_cfg["num_epochs"],
            fp16=train_cfg["fp16"],
            gradient_checkpointing=train_cfg["gradient_checkpointing"],
            save_steps=train_cfg["save_steps"],
            eval_steps=train_cfg["eval_steps"],
            logging_steps=train_cfg["logging_steps"],
            learning_rate=train_cfg["learning_rate"],
            weight_decay=train_cfg["weight_decay"],
            warmup_steps=train_cfg["warmup_steps"],
            lr_scheduler_type=train_cfg["lr_scheduler_type"],
            save_total_limit=3,
            push_to_hub=False,
            load_best_model_at_end=train_cfg["load_best_model_at_end"],
            metric_for_best_model=train_cfg["metric_for_best_model"],
            greater_is_better=train_cfg["greater_is_better"],
            seed=exp_cfg["seed"],
            data_seed=exp_cfg["seed"],
            report_to="none",  # MLflow is handled via callback
        )

        # Resume from checkpoint if available
        last_ckpt = get_last_checkpoint(str(output_dir))
        if last_ckpt:
            logger.info("Resuming from checkpoint: %s", last_ckpt)

        trainer = Trainer(
            model=model,
            data_collator=data_collator,
            args=training_args,
            compute_metrics=make_compute_metrics(processor),
            train_dataset=train_ds,
            eval_dataset=val_ds,
            tokenizer=processor.feature_extractor,
            callbacks=[
                EarlyStoppingCallback(
                    early_stopping_patience=train_cfg["early_stopping_patience"]
                ),
                MLflowLoggingCallback(),
            ],
        )

        trainer.train(resume_from_checkpoint=last_ckpt)

        # ------------------------------------------------------------------
        # 6. Save
        # ------------------------------------------------------------------
        logger.info("=== Phase 6: Saving model ===")
        trainer.save_model(str(output_dir / "best_model"))
        processor.save_pretrained(str(output_dir / "best_model"))
        logger.info("Model saved to %s/best_model", output_dir)
        mlflow.log_artifacts(str(output_dir / "best_model"), artifact_path="model")

        # ------------------------------------------------------------------
        # 7. Final test evaluation (run once, after training is complete)
        # ------------------------------------------------------------------
        logger.info("=== Phase 7: Final test evaluation ===")
        test_results = trainer.evaluate(eval_dataset=test_ds)
        logger.info("Test results: %s", test_results)
        mlflow.log_metrics(
            {f"test_{k}": v for k, v in test_results.items() if isinstance(v, float)}
        )

        results_path = output_dir / "test_results.json"
        with open(results_path, "w") as f:
            json.dump(test_results, f, indent=2)
        mlflow.log_artifact(str(results_path))

        logger.info("Training complete. WER=%.4f | CER=%.4f",
                    test_results.get("eval_wer", -1),
                    test_results.get("eval_cer", -1))

    return test_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ASR Training")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()
    main(args.config)
