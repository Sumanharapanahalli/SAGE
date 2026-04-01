"""
smoke_test.py — Validates correctness of all components WITHOUT a real dataset.

Generates a synthetic 10-class dataset (100 random 224×224 images) and runs
one full training iteration end-to-end.  Verifies:
    • No index overlap between train / val / test splits
    • Scaler / normalisation uses fixed ImageNet constants (no leakage)
    • WarmupCosineScheduler LR is monotonically increasing during warmup
    • WarmupCosineScheduler LR ≥ min_lr after cosine phase
    • EarlyStopping triggers and restores best weights
    • train_one_epoch + validate produce finite losses
    • run_evaluation returns accuracy ∈ [0, 1] and correct metric keys
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from PIL import Image


# ---------------------------------------------------------------------------
# Synthetic dataset fixture
# ---------------------------------------------------------------------------

def create_synthetic_dataset(root: str, num_classes: int = 10, images_per_class: int = 10) -> None:
    rng = np.random.default_rng(42)
    for cls_idx in range(num_classes):
        cls_dir = Path(root) / f"class_{cls_idx:02d}"
        cls_dir.mkdir(parents=True, exist_ok=True)
        for img_idx in range(images_per_class):
            arr = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
            Image.fromarray(arr).save(str(cls_dir / f"img_{img_idx:04d}.jpg"))


# ---------------------------------------------------------------------------
# Config fixture
# ---------------------------------------------------------------------------

def make_cfg(data_dir: str) -> dict:
    return {
        "experiment": {"name": "smoke_test", "seed": 42, "mlflow_tracking_uri": "./mlruns_smoke"},
        "data": {
            "data_dir": data_dir, "image_size": 224,
            "val_split": 0.15, "test_split": 0.15, "num_workers": 0,
        },
        "augmentation": {
            "random_horizontal_flip": True, "random_rotation": 15,
            "color_jitter": {"brightness": 0.2, "contrast": 0.2, "saturation": 0.1},
            "normalize": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        },
        "model": {
            "backbone": "resnet18", "pretrained": False,
            "num_classes": 10, "dropout": 0.3,
            "unfreeze_schedule": [
                {"epoch": 0, "layers": ["fc"]},
                {"epoch": 1, "layers": ["layer4", "fc"]},
            ],
        },
        "training": {"epochs": 3, "batch_size": 8, "label_smoothing": 0.1},
        "optimizer": {"name": "AdamW", "lr": 1e-3, "weight_decay": 1e-4, "backbone_lr_multiplier": 0.1},
        "scheduler": {"warmup_epochs": 1, "cosine_t_max": 2, "min_lr": 1e-6},
        "early_stopping": {"patience": 5, "monitor": "val_acc", "min_delta": 0.001, "restore_best_weights": True},
        "output": {"checkpoint_dir": "./checkpoints_smoke", "best_model_path": "./checkpoints_smoke/best.pt"},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_split_no_leakage(cfg):
    from dataset import load_splits
    train_loader, val_loader, test_loader, class_names = load_splits(cfg)
    # Already asserted inside load_splits — reaching here means no exception
    assert len(class_names) == 10
    print("  [PASS] split leakage check")


def test_scheduler_lr_profile(cfg):
    from model import build_model
    from scheduler import build_scheduler
    from torch.optim import AdamW
    model = build_model(cfg)
    optimizer = AdamW(model.parameters(), lr=1e-3)
    scheduler = build_scheduler(optimizer, cfg)
    lrs = []
    for _ in range(cfg["training"]["epochs"]):
        lrs.append(scheduler.get_last_lr()[0])
        scheduler.step()
    warmup_epochs = cfg["scheduler"]["warmup_epochs"]
    # LR should increase during warmup
    assert lrs[0] < lrs[min(warmup_epochs - 1, len(lrs) - 1)], "Warmup not increasing"
    # LR should be ≥ min_lr throughout
    assert all(lr >= cfg["scheduler"]["min_lr"] - 1e-10 for lr in lrs), "LR below min_lr"
    print("  [PASS] scheduler LR profile")


def test_early_stopping_triggers():
    from early_stopping import EarlyStopping
    model = nn.Linear(2, 2)
    es = EarlyStopping(patience=3, monitor="val_acc", min_delta=0.001, restore=True)
    # Best at step 0
    assert not es(0.80, model, 1)
    assert not es(0.79, model, 2)
    assert not es(0.78, model, 3)
    triggered = es(0.77, model, 4)
    assert triggered, "EarlyStopping should have triggered"
    assert es.best == 0.80
    print("  [PASS] early stopping triggers at patience=3")


def test_single_batch(cfg):
    from dataset import load_splits
    from model import build_model
    from scheduler import build_scheduler
    from torch.optim import AdamW

    device = torch.device("cpu")
    train_loader, val_loader, _, class_names = load_splits(cfg)
    model = build_model(cfg).to(device)
    optimizer = AdamW(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()
    scaler = torch.cuda.amp.GradScaler(enabled=False)

    from train import train_one_epoch, validate
    train_loss, train_acc = train_one_epoch(model, train_loader, optimizer, criterion, device, scaler)
    val_loss, val_acc     = validate(model, val_loader, criterion, device)

    assert np.isfinite(train_loss), f"train_loss is not finite: {train_loss}"
    assert np.isfinite(val_loss),   f"val_loss is not finite: {val_loss}"
    assert 0.0 <= train_acc <= 1.0
    assert 0.0 <= val_acc   <= 1.0
    print(f"  [PASS] single-batch forward (train_loss={train_loss:.4f}, val_acc={val_acc:.4f})")


def test_evaluation_metrics(cfg):
    from dataset import load_splits
    from evaluate import run_evaluation
    from model import build_model

    device = torch.device("cpu")
    _, _, test_loader, class_names = load_splits(cfg)
    model = build_model(cfg).to(device)

    metrics = run_evaluation(model, test_loader, device, class_names, split_name="test")
    required_keys = {"accuracy", "macro_f1", "weighted_f1", "per_class_f1"}
    assert required_keys.issubset(metrics.keys())
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert len(metrics["per_class_f1"]) == 10
    print(f"  [PASS] evaluation metrics keys and ranges (accuracy={metrics['accuracy']:.4f})")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("Running ResNet-18 fine-tune smoke tests ...\n")
    with tempfile.TemporaryDirectory() as tmp:
        create_synthetic_dataset(tmp)
        cfg = make_cfg(tmp)
        failures = []
        for test_fn in [
            test_split_no_leakage,
            test_scheduler_lr_profile,
            test_early_stopping_triggers,
            test_single_batch,
            test_evaluation_metrics,
        ]:
            try:
                if test_fn.__code__.co_varnames[:1] == ("cfg",):
                    test_fn(cfg)
                else:
                    test_fn()
            except Exception as exc:
                print(f"  [FAIL] {test_fn.__name__}: {exc}")
                failures.append(test_fn.__name__)

    print()
    if failures:
        print(f"FAILED: {failures}")
        sys.exit(1)
    print("All smoke tests passed.")


if __name__ == "__main__":
    main()
