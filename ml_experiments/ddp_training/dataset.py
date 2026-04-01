"""
Stratified train/val/test splitting with scaler fit ONLY on train data.

Data leakage prevention contract:
  - StandardScaler.fit()         → called ONCE on X_train only
  - StandardScaler.transform()   → called on X_val and X_test (no fit)
  - DistributedSampler           → applied after splits, not before
"""

import logging
from typing import Tuple

import numpy as np
import torch
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.preprocessing import StandardScaler
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)


class ClassificationDataset(Dataset):
    """Wraps pre-split, pre-scaled numpy arrays as a torch Dataset."""

    def __init__(self, X: np.ndarray, y: np.ndarray) -> None:
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.X[idx], self.y[idx]


def check_class_balance(y: np.ndarray, threshold: float = 0.2) -> bool:
    """
    Returns True if any class share deviates > `threshold` from a uniform distribution.
    Logs a warning when imbalance is detected.
    """
    classes, counts = np.unique(y, return_counts=True)
    shares = counts / counts.sum()
    uniform_share = 1.0 / len(classes)
    max_deviation = float(np.max(np.abs(shares - uniform_share)))
    imbalanced = max_deviation > threshold
    if imbalanced:
        logger.warning(
            f"Class imbalance detected — max deviation from uniform: {max_deviation:.2%}. "
            f"Class counts: {dict(zip(classes.tolist(), counts.tolist()))}"
        )
    return imbalanced


def stratified_split(
    X: np.ndarray,
    y: np.ndarray,
    train_split: float = 0.70,
    val_split: float = 0.15,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Two-stage stratified split:
      Stage 1: carve test set from full data
      Stage 2: carve val set from remaining trainval data

    Both stages preserve class proportions (StratifiedShuffleSplit).

    Returns: X_train, X_val, X_test, y_train, y_val, y_test
    """
    assert train_split + val_split < 1.0, "train_split + val_split must be < 1.0"
    test_split = 1.0 - train_split - val_split

    # Stage 1: isolate test
    sss1 = StratifiedShuffleSplit(n_splits=1, test_size=test_split, random_state=seed)
    trainval_idx, test_idx = next(sss1.split(X, y))

    # Stage 2: split trainval → train + val
    val_fraction_of_trainval = val_split / (train_split + val_split)
    sss2 = StratifiedShuffleSplit(
        n_splits=1, test_size=val_fraction_of_trainval, random_state=seed
    )
    local_train_idx, local_val_idx = next(sss2.split(X[trainval_idx], y[trainval_idx]))
    train_idx = trainval_idx[local_train_idx]
    val_idx = trainval_idx[local_val_idx]

    logger.info(
        f"Stratified split — train: {len(train_idx)}, "
        f"val: {len(val_idx)}, test: {len(test_idx)}"
    )
    # Verify class proportions are preserved
    for split_name, idx in [("train", train_idx), ("val", val_idx), ("test", test_idx)]:
        _, counts = np.unique(y[idx], return_counts=True)
        logger.debug(f"  {split_name} class dist: {(counts / counts.sum()).round(3).tolist()}")

    return (
        X[train_idx], X[val_idx], X[test_idx],
        y[train_idx], y[val_idx], y[test_idx],
    )


def fit_scaler_on_train(
    X_train: np.ndarray,
    X_val: np.ndarray,
    X_test: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    """
    Fits StandardScaler on X_train ONLY — prevents data leakage.
    Val and test are transformed with the train-fit scaler.

    Returns scaled arrays + the fitted scaler (save alongside checkpoints).
    """
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)    # ← ONLY fit here
    X_val_s   = scaler.transform(X_val)           # ← transform only
    X_test_s  = scaler.transform(X_test)          # ← transform only
    logger.info(
        f"Scaler fit on train ({len(X_train)} samples). "
        f"mean range: [{X_train_s.mean(0).min():.3f}, {X_train_s.mean(0).max():.3f}]"
    )
    return X_train_s, X_val_s, X_test_s, scaler
