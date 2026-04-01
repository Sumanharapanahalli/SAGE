"""
data_utils.py — Invoice/Receipt OCR dataset utilities.

Design contract
───────────────
• Scalers / processors are NEVER fitted on val or test data.
• Augmentation is ONLY applied to training splits.
• Stratified split preserves doc_type distribution across all three partitions.
• All paths returned are absolute so callers are location-independent.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import albumentations as A
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import TrOCRProcessor

logger = logging.getLogger(__name__)

# ── Annotation schema ────────────────────────────────────────────────────────
# annotations.csv columns:
#   image_path   (str)  — path relative to data/raw/
#   text         (str)  — ground-truth transcription for the line crop
#   doc_type     (str)  — "invoice" | "receipt" | "mixed"
#   scan_quality (str)  — "high" | "medium" | "low"  (optional, filled if known)
#   language     (str)  — ISO 639-1 code, default "en"
REQUIRED_COLS = {"image_path", "text", "doc_type"}


def load_annotations(annotation_file: str | Path) -> pd.DataFrame:
    """Load and validate the annotation CSV.

    Returns a DataFrame with NaN rows dropped and column types normalised.
    Raises ValueError if required columns are missing.
    """
    df = pd.read_csv(annotation_file)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"Annotation file missing columns: {missing}")

    df = df.dropna(subset=list(REQUIRED_COLS)).reset_index(drop=True)
    df["text"] = df["text"].astype(str).str.strip()
    df["doc_type"] = df["doc_type"].str.lower().str.strip()

    # Fill optional columns with defaults if absent
    if "scan_quality" not in df.columns:
        df["scan_quality"] = "unknown"
    if "language" not in df.columns:
        df["language"] = "en"

    logger.info("Loaded %d annotations from %s", len(df), annotation_file)
    return df


def stratified_split(
    df: pd.DataFrame,
    stratify_col: str,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Three-way stratified split.

    Leakage guard: the split is purely index-based; no feature statistics
    are computed here.  train_frac + val_frac + test_frac must equal 1.0.
    """
    test_frac = round(1.0 - train_frac - val_frac, 10)
    assert test_frac > 0, "train_frac + val_frac must be < 1.0"

    # --- First cut: train vs (val+test) ----------------------------------
    train_df, temp_df = train_test_split(
        df,
        test_size=(val_frac + test_frac),
        stratify=df[stratify_col],
        random_state=seed,
    )

    # --- Second cut: val vs test ------------------------------------------
    val_relative = val_frac / (val_frac + test_frac)
    val_df, test_df = train_test_split(
        temp_df,
        test_size=(1.0 - val_relative),
        stratify=temp_df[stratify_col],
        random_state=seed,
    )

    for name, split in [("train", train_df), ("val", val_df), ("test", test_df)]:
        dist = split[stratify_col].value_counts(normalize=True).to_dict()
        logger.info("Split '%s' — %d samples | class dist: %s", name, len(split), dist)

    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
        test_df.reset_index(drop=True),
    )


# ── Augmentation (train-only) ────────────────────────────────────────────────

def build_train_transform(cfg: dict) -> A.Compose:
    """Albumentations pipeline applied ONLY to training images."""
    aug = cfg.get("augmentation", {})
    return A.Compose([
        A.RandomBrightnessContrast(
            brightness_limit=aug.get("random_brightness", 0.2),
            contrast_limit=aug.get("random_contrast", 0.2),
            p=0.5,
        ),
        A.Rotate(
            limit=aug.get("random_rotation_deg", 3),
            border_mode=cv2.BORDER_REPLICATE,
            p=0.4,
        ),
        A.ImageCompression(
            quality_lower=aug.get("jpeg_quality_range", [60, 100])[0],
            quality_upper=aug.get("jpeg_quality_range", [60, 100])[1],
            p=0.3,
        ),
        A.GaussNoise(var_limit=(10, 50), p=0.2),
    ])


def build_eval_transform() -> None:
    """No augmentation for val/test — returns None intentionally."""
    return None


# ── Dataset ───────────────────────────────────────────────────────────────────

class InvoiceOCRDataset(Dataset):
    """Line-crop dataset for TrOCR fine-tuning.

    The TrOCRProcessor (pixel values + token ids) is fitted on the
    HuggingFace pre-trained vocabulary — it is NEVER re-fitted on any
    project data, eliminating the primary leakage vector for text models.

    Parameters
    ----------
    df          : annotation DataFrame (one row = one text line crop)
    raw_dir     : root directory containing the images referenced in df
    processor   : pre-loaded TrOCRProcessor (shared across all splits)
    augment     : Albumentations Compose or None
    max_length  : maximum decoder token length
    """

    def __init__(
        self,
        df: pd.DataFrame,
        raw_dir: str | Path,
        processor: TrOCRProcessor,
        augment: Optional[A.Compose] = None,
        max_length: int = 128,
    ) -> None:
        self.df = df.reset_index(drop=True)
        self.raw_dir = Path(raw_dir)
        self.processor = processor
        self.augment = augment
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Dict:
        row = self.df.iloc[idx]
        img_path = self.raw_dir / row["image_path"]

        # --- Load image ---------------------------------------------------
        image = Image.open(img_path).convert("RGB")
        img_np = np.array(image)

        # --- Augmentation (train-only guard is in the caller) -------------
        if self.augment is not None:
            augmented = self.augment(image=img_np)
            img_np = augmented["image"]
            image = Image.fromarray(img_np)

        # --- TrOCR processor encodes pixel values -------------------------
        pixel_values = self.processor(
            images=image, return_tensors="pt"
        ).pixel_values.squeeze(0)

        # --- Tokenise label -----------------------------------------------
        labels = self.processor.tokenizer(
            row["text"],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).input_ids.squeeze(0)

        # TrOCR convention: pad token id → -100 to be ignored in loss
        labels[labels == self.processor.tokenizer.pad_token_id] = -100

        return {
            "pixel_values": pixel_values,
            "labels": labels,
            # Metadata passthrough for bias evaluation
            "doc_type": row["doc_type"],
            "scan_quality": row["scan_quality"],
            "language": row["language"],
            "text": row["text"],
        }


def compute_dataset_fingerprint(df: pd.DataFrame) -> str:
    """SHA-256 hash of image paths + texts — detects silent data changes."""
    key = "|".join(df["image_path"].astype(str) + ":" + df["text"].astype(str))
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def check_class_imbalance(
    df: pd.DataFrame, col: str = "doc_type", threshold: float = 3.0
) -> bool:
    """Return True if the majority/minority class ratio exceeds threshold."""
    counts = df[col].value_counts()
    if len(counts) < 2:
        return False
    ratio = counts.iloc[0] / counts.iloc[-1]
    if ratio > threshold:
        logger.warning(
            "Class imbalance detected in '%s': max/min ratio = %.1f (threshold %.1f)",
            col, ratio, threshold,
        )
        return True
    return False
