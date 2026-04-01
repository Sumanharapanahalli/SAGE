"""
dataset.py — Data loading with stratified splits.

ImageFolder layout expected:
    data/
        class_0/  img1.jpg img2.jpg ...
        class_1/  ...
        ...
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset, Subset
from torchvision import transforms
from torchvision.datasets import ImageFolder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def build_transforms(cfg: dict, split: str) -> transforms.Compose:
    """
    Build augmentation pipeline.
    Augmentation ONLY applied to train split — prevents any leakage via
    transform state into val/test.
    """
    aug_cfg = cfg["augmentation"]
    norm_cfg = aug_cfg["normalize"]
    normalize = transforms.Normalize(mean=norm_cfg["mean"], std=norm_cfg["std"])
    img_size: int = cfg["data"]["image_size"]

    if split == "train":
        t = [
            transforms.RandomResizedCrop(img_size, scale=(0.7, 1.0)),
        ]
        if aug_cfg.get("random_horizontal_flip"):
            t.append(transforms.RandomHorizontalFlip())
        if aug_cfg.get("random_rotation"):
            t.append(transforms.RandomRotation(aug_cfg["random_rotation"]))
        if aug_cfg.get("color_jitter"):
            jcfg = aug_cfg["color_jitter"]
            t.append(transforms.ColorJitter(
                brightness=jcfg.get("brightness", 0),
                contrast=jcfg.get("contrast", 0),
                saturation=jcfg.get("saturation", 0),
            ))
        t += [transforms.ToTensor(), normalize]
    else:
        # val / test: deterministic resize + center crop only
        t = [
            transforms.Resize(int(img_size * 1.14)),
            transforms.CenterCrop(img_size),
            transforms.ToTensor(),
            normalize,
        ]

    return transforms.Compose(t)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class TransformSubset(Dataset):
    """Wraps a Subset and applies a transform independent of the base dataset."""

    def __init__(self, subset: Subset, transform: transforms.Compose) -> None:
        self.subset = subset
        self.transform = transform

    def __len__(self) -> int:
        return len(self.subset)

    def __getitem__(self, idx):
        img, label = self.subset[idx]
        # img comes as PIL from ImageFolder (transform=None on base)
        if self.transform:
            img = self.transform(img)
        return img, label


def load_splits(
    cfg: dict,
) -> Tuple[DataLoader, DataLoader, DataLoader, list[str]]:
    """
    Loads data, performs stratified train/val/test split, wraps each
    with the correct transforms, returns (train_loader, val_loader,
    test_loader, class_names).

    Critical anti-leakage contract:
        • The base ImageFolder uses transform=None so raw PIL images are
          stored in Subsets — no normalisation happens at this stage.
        • Each Subset is wrapped in TransformSubset with its own transform.
        • Normalisation stats are ImageNet constants (not computed from
          dataset), so there is no fit-on-test risk.
    """
    data_cfg = cfg["data"]
    data_dir = Path(data_cfg["data_dir"])
    seed: int = cfg["experiment"]["seed"]

    # Load without any transform — raw PIL images
    base_dataset = ImageFolder(root=str(data_dir), transform=None)
    class_names = base_dataset.classes
    all_targets = np.array(base_dataset.targets)
    all_indices = np.arange(len(base_dataset))

    logger.info("Total samples: %d | Classes: %s", len(base_dataset), class_names)
    _check_class_imbalance(all_targets, class_names)

    # ---- Stratified split: trainval / test ----
    test_size = data_cfg["test_split"]
    trainval_idx, test_idx = train_test_split(
        all_indices,
        test_size=test_size,
        stratify=all_targets,
        random_state=seed,
    )

    # ---- Stratified split: train / val (within trainval) ----
    val_size_relative = data_cfg["val_split"] / (1.0 - test_size)
    trainval_targets = all_targets[trainval_idx]
    train_idx, val_idx = train_test_split(
        trainval_idx,
        test_size=val_size_relative,
        stratify=trainval_targets,
        random_state=seed,
    )

    logger.info(
        "Split sizes — train: %d | val: %d | test: %d",
        len(train_idx), len(val_idx), len(test_idx),
    )
    _check_split_leakage(train_idx, val_idx, test_idx)

    # ---- Wrap each split with its own transform ----
    train_ds = TransformSubset(Subset(base_dataset, train_idx), build_transforms(cfg, "train"))
    val_ds   = TransformSubset(Subset(base_dataset, val_idx),   build_transforms(cfg, "val"))
    test_ds  = TransformSubset(Subset(base_dataset, test_idx),  build_transforms(cfg, "test"))

    num_workers = data_cfg.get("num_workers", 4)
    batch_size  = cfg["training"]["batch_size"]

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=num_workers, pin_memory=True, drop_last=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False,
                              num_workers=num_workers, pin_memory=True)
    test_loader  = DataLoader(test_ds,  batch_size=batch_size, shuffle=False,
                              num_workers=num_workers, pin_memory=True)

    return train_loader, val_loader, test_loader, class_names


# ---------------------------------------------------------------------------
# Integrity checks
# ---------------------------------------------------------------------------

def _check_class_imbalance(targets: np.ndarray, class_names: list[str]) -> None:
    counts = np.bincount(targets)
    max_ratio = counts.max() / counts.min()
    if max_ratio > 3.0:
        logger.warning(
            "Class imbalance detected (max/min ratio=%.1f). "
            "Consider WeightedRandomSampler or class-weighted loss.",
            max_ratio,
        )
    for name, count in zip(class_names, counts):
        logger.debug("  %-30s: %d samples", name, count)


def _check_split_leakage(
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    test_idx: np.ndarray,
) -> None:
    train_set = set(train_idx.tolist())
    val_set   = set(val_idx.tolist())
    test_set  = set(test_idx.tolist())
    overlap_tv = train_set & val_set
    overlap_tt = train_set & test_set
    overlap_vt = val_set & test_set
    if overlap_tv or overlap_tt or overlap_vt:
        raise RuntimeError(
            f"DATA LEAKAGE DETECTED — split overlap: "
            f"train∩val={len(overlap_tv)}, train∩test={len(overlap_tt)}, "
            f"val∩test={len(overlap_vt)}"
        )
    logger.info("Leakage check passed — no index overlap between splits.")
