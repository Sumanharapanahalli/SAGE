"""
Dataset utilities for the document classifier.

Provides:
  - DocumentDataset: PyTorch Dataset (image + optional OCR text + label)
  - stratified_split: reproducible train/val/test split without leakage
  - class_weights: for handling class imbalance in cross-entropy loss

All splits are stratified on the document class label.
Scalers / encoders are fitted ONLY on the train fold.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from torch.utils.data import Dataset
from torchvision import transforms

logger = logging.getLogger(__name__)

DOCUMENT_CLASSES = ["invoice", "receipt", "contract"]


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class DocumentDataset(Dataset):
    """
    Loads document images and their class labels.

    Directory layout expected:
        root/
          invoice/
            img001.jpg
            ...
          receipt/
            ...
          contract/
            ...

    Args:
        samples:   List of (image_path, label_int) tuples.
        transform: torchvision transform applied to PIL images.
        texts:     Optional list of OCR text strings aligned to samples.
    """

    def __init__(
        self,
        samples: List[Tuple[str, int]],
        transform: Optional[transforms.Compose] = None,
        texts: Optional[List[str]] = None,
    ) -> None:
        self.samples = samples
        self.transform = transform
        self.texts = texts
        self._log = logging.getLogger(self.__class__.__name__)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict:
        path, label = self.samples[idx]
        image = Image.open(path).convert("RGB")

        if self.transform is not None:
            image = self.transform(image)

        item: Dict = {"image": image, "label": torch.tensor(label, dtype=torch.long)}

        if self.texts is not None:
            item["text"] = self.texts[idx]

        return item

    @classmethod
    def from_directory(
        cls,
        root: str | Path,
        transform: Optional[transforms.Compose] = None,
        classes: Optional[List[str]] = None,
    ) -> "DocumentDataset":
        """
        Scan root directory and build a dataset from the class sub-folders.

        Args:
            root:    Root directory containing one sub-folder per class.
            transform: Image transforms.
            classes: Ordered class names (determines label indices).
                     Defaults to DOCUMENT_CLASSES.
        """
        root = Path(root)
        classes = classes or DOCUMENT_CLASSES
        label_map = {cls: i for i, cls in enumerate(classes)}

        samples: List[Tuple[str, int]] = []
        extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}

        for cls_name in classes:
            cls_dir = root / cls_name
            if not cls_dir.is_dir():
                logger.warning("Class directory not found: %s", cls_dir)
                continue
            for fp in sorted(cls_dir.iterdir()):
                if fp.suffix.lower() in extensions:
                    samples.append((str(fp), label_map[cls_name]))

        logger.info("Loaded %d samples from %s", len(samples), root)
        return cls(samples=samples, transform=transform)


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def build_train_transforms(image_size: int = 224) -> transforms.Compose:
    """Augmented transforms for training (fit on train only)."""
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.RandomRotation(degrees=5),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.RandomHorizontalFlip(p=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


def build_eval_transforms(image_size: int = 224) -> transforms.Compose:
    """Deterministic transforms for validation and test (no augmentation)."""
    return transforms.Compose([
        transforms.Resize((image_size, image_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


# ---------------------------------------------------------------------------
# Stratified split (no leakage)
# ---------------------------------------------------------------------------

def stratified_split(
    samples: List[Tuple[str, int]],
    val_size: float = 0.15,
    test_size: float = 0.15,
    seed: int = 42,
) -> Tuple[List, List, List]:
    """
    Reproducible stratified train/val/test split.

    IMPORTANT: No scaler or encoder is ever fitted on val or test data.
    The LabelEncoder mapping is fixed by DOCUMENT_CLASSES order, so the
    integer-to-class mapping is identical across splits.

    Args:
        samples:   Full sample list of (path, label_int).
        val_size:  Fraction of data for validation.
        test_size: Fraction of data for test.
        seed:      Random seed for reproducibility.

    Returns:
        (train_samples, val_samples, test_samples)
    """
    labels = [s[1] for s in samples]

    # First split off test
    train_val, test = train_test_split(
        samples,
        test_size=test_size,
        stratify=labels,
        random_state=seed,
    )

    # Then split train/val from remaining
    train_val_labels = [s[1] for s in train_val]
    relative_val_size = val_size / (1.0 - test_size)
    train, val = train_test_split(
        train_val,
        test_size=relative_val_size,
        stratify=train_val_labels,
        random_state=seed,
    )

    logger.info(
        "Split — train: %d | val: %d | test: %d",
        len(train), len(val), len(test),
    )
    _log_class_distribution("Train", train)
    _log_class_distribution("Val",   val)
    _log_class_distribution("Test",  test)

    return train, val, test


def compute_class_weights(
    train_samples: List[Tuple[str, int]],
    num_classes: int,
) -> torch.Tensor:
    """
    Compute inverse-frequency class weights for CrossEntropyLoss.

    Fitted exclusively on train_samples to prevent data leakage.
    """
    from sklearn.utils.class_weight import compute_class_weight
    labels = [s[1] for s in train_samples]
    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.arange(num_classes),
        y=labels,
    )
    logger.info("Class weights: %s", dict(enumerate(weights.round(4))))
    return torch.tensor(weights, dtype=torch.float32)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_class_distribution(split_name: str, samples: List[Tuple[str, int]]) -> None:
    from collections import Counter
    dist = Counter(s[1] for s in samples)
    logger.info(
        "  %s class distribution: %s",
        split_name,
        {DOCUMENT_CLASSES[k]: v for k, v in sorted(dist.items())},
    )
