"""
data_utils.py — Data loading, validation, and stratified splitting.

Rules enforced here:
  - Stratified split so class distribution is preserved in every partition
  - Scaler/encoder fit ONLY on train split; transform applied to val/test
  - Class-imbalance detection before training begins
  - No data leakage across splits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from datasets import Dataset, DatasetDict, load_dataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from transformers import PreTrainedTokenizerBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-quality report
# ---------------------------------------------------------------------------

@dataclass
class DataReport:
    num_classes: int
    class_counts: dict[str, int]
    imbalance_ratio: float          # max_count / min_count
    class_imbalance_flag: bool      # True if ratio > 10
    leakage_risk: bool = False      # always False after this pipeline
    train_size: int = 0
    val_size: int = 0
    test_size: int = 0
    duplicate_rate: float = 0.0
    empty_text_count: int = 0

    def log(self) -> None:
        logger.info("── Data report ──────────────────────────────")
        logger.info("  Classes        : %d", self.num_classes)
        logger.info("  Imbalance ratio: %.1f", self.imbalance_ratio)
        logger.info("  Imbalance flag : %s", self.class_imbalance_flag)
        logger.info("  Train / Val / Test: %d / %d / %d",
                    self.train_size, self.val_size, self.test_size)
        logger.info("  Duplicate rate : %.2f%%", self.duplicate_rate * 100)
        logger.info("  Empty texts    : %d", self.empty_text_count)
        logger.info("─────────────────────────────────────────────")


# ---------------------------------------------------------------------------
# Label encoder (fit on train only)
# ---------------------------------------------------------------------------

class IntentLabelEncoder:
    """Wraps sklearn LabelEncoder; serialisable for artifact logging."""

    def __init__(self) -> None:
        self._enc = LabelEncoder()
        self.classes_: list[str] = []

    def fit(self, labels: list[str]) -> "IntentLabelEncoder":
        self._enc.fit(labels)
        self.classes_ = list(self._enc.classes_)
        return self

    def transform(self, labels: list[str]) -> np.ndarray:
        return self._enc.transform(labels)

    def inverse_transform(self, ids: np.ndarray) -> list[str]:
        return list(self._enc.inverse_transform(ids))

    def __len__(self) -> int:
        return len(self.classes_)


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_and_split(
    cfg: dict[str, Any],
    tokenizer: PreTrainedTokenizerBase,
) -> tuple[DatasetDict, IntentLabelEncoder, DataReport]:
    """
    Load dataset, validate quality, stratify-split, tokenise.

    Returns:
        dataset_dict  – HF DatasetDict with 'train', 'val', 'test'
        label_encoder – fitted on train labels only
        report        – DataReport for downstream logging
    """
    text_col: str = cfg["data"]["text_column"]
    label_col: str = cfg["data"]["label_column"]
    test_size: float = cfg["data"]["test_size"]
    val_size: float = cfg["data"]["val_size"]
    seed: int = cfg["experiment"]["random_seed"]
    max_length: int = cfg["data"]["max_length"]

    # ── 1. Load ──────────────────────────────────────────────────────────
    dataset_id = cfg["data"]["dataset"]
    logger.info("Loading dataset: %s", dataset_id)
    try:
        raw = load_dataset(dataset_id, trust_remote_code=True)
        df = _hf_to_df(raw, text_col, label_col)
    except Exception:
        logger.warning("HF dataset '%s' unavailable; generating synthetic data.", dataset_id)
        df = _synthetic_df(text_col, label_col, seed=seed)

    # ── 2. Basic quality checks ──────────────────────────────────────────
    df = df.dropna(subset=[text_col, label_col]).reset_index(drop=True)
    empty_count = int((df[text_col].str.strip() == "").sum())
    df = df[df[text_col].str.strip() != ""].reset_index(drop=True)

    dup_rate = df.duplicated(subset=[text_col]).mean()
    df = df.drop_duplicates(subset=[text_col]).reset_index(drop=True)

    counts = df[label_col].value_counts()
    imbalance_ratio = float(counts.iloc[0] / counts.iloc[-1])

    report = DataReport(
        num_classes=int(counts.shape[0]),
        class_counts=counts.to_dict(),
        imbalance_ratio=imbalance_ratio,
        class_imbalance_flag=imbalance_ratio > 10,
        leakage_risk=False,      # enforced by design below
        duplicate_rate=dup_rate,
        empty_text_count=empty_count,
    )

    if report.class_imbalance_flag:
        logger.warning(
            "Class imbalance detected (ratio=%.1f). "
            "Consider oversampling or weighted loss.", imbalance_ratio
        )

    # ── 3. Stratified split (train first, then val from train) ───────────
    texts = df[text_col].tolist()
    labels = df[label_col].tolist()

    X_train_val, X_test, y_train_val, y_test = train_test_split(
        texts, labels,
        test_size=test_size,
        stratify=labels,
        random_state=seed,
    )

    val_fraction = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val,
        test_size=val_fraction,
        stratify=y_train_val,
        random_state=seed,
    )

    # ── 4. Fit label encoder on TRAIN ONLY ──────────────────────────────
    enc = IntentLabelEncoder().fit(y_train)
    # Val/test may contain unseen labels (OOS); map them to -1 for analysis
    y_train_ids = enc.transform(y_train).tolist()
    y_val_ids   = _safe_transform(enc, y_val)
    y_test_ids  = _safe_transform(enc, y_test)

    report.train_size = len(X_train)
    report.val_size   = len(X_val)
    report.test_size  = len(X_test)
    report.log()

    # ── 5. Tokenise (no leakage — tokenizer is fit-free) ────────────────
    def tokenise(batch: dict) -> dict:
        return tokenizer(
            batch[text_col],
            padding="max_length",
            truncation=True,
            max_length=max_length,
        )

    def make_hf(texts_: list[str], label_ids: list[int]) -> Dataset:
        ds = Dataset.from_dict({text_col: texts_, "label": label_ids})
        return ds.map(tokenise, batched=True).remove_columns([text_col])

    dataset_dict = DatasetDict({
        "train": make_hf(X_train, y_train_ids),
        "val":   make_hf(X_val,   y_val_ids),
        "test":  make_hf(X_test,  y_test_ids),
    })

    return dataset_dict, enc, report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hf_to_df(raw: Any, text_col: str, label_col: str) -> pd.DataFrame:
    """Flatten multi-split HF dataset into a single DataFrame."""
    frames = []
    for split_name, split_ds in raw.items():
        df_split = split_ds.to_pandas()[[text_col, label_col]].copy()
        df_split["_source_split"] = split_name
        frames.append(df_split)
    return pd.concat(frames, ignore_index=True)


def _safe_transform(enc: IntentLabelEncoder, labels: list[str]) -> list[int]:
    """Transform labels; unseen labels become -1 (out-of-scope sentinel)."""
    known = set(enc.classes_)
    return [enc.transform([l])[0] if l in known else -1 for l in labels]


def _synthetic_df(text_col: str, label_col: str, seed: int = 42) -> pd.DataFrame:
    """
    Minimal synthetic dataset for CI / offline testing.
    Mirrors the CLINC-OOS structure with 5 intents × 200 samples.
    """
    rng = np.random.default_rng(seed)
    intents = {
        "book_flight":      ["book a flight to {city}", "I need to fly to {city}", "reserve a seat to {city}"],
        "check_balance":    ["what is my balance", "how much money do I have", "show my account balance"],
        "cancel_order":     ["cancel my order", "I want to cancel", "please cancel order {id}"],
        "track_package":    ["where is my package", "track order {id}", "check delivery status"],
        "weather_forecast": ["what is the weather in {city}", "will it rain tomorrow", "weather forecast {city}"],
    }
    cities = ["Paris", "London", "Tokyo", "Berlin", "Sydney"]
    texts, labels = [], []
    for intent, templates in intents.items():
        for _ in range(200):
            tmpl = templates[rng.integers(len(templates))]
            city = cities[rng.integers(len(cities))]
            oid  = str(rng.integers(10000, 99999))
            texts.append(tmpl.format(city=city, id=oid))
            labels.append(intent)
    df = pd.DataFrame({text_col: texts, label_col: labels})
    return df.sample(frac=1, random_state=seed).reset_index(drop=True)
