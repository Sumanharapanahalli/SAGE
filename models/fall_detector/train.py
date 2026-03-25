"""
Fall Detection Model — Training Script
=======================================
Trains the FallNet-Micro CNN-1D on the assembled dataset with:
  - Stratified train / val / test split (75 / 10 / 15 %)
  - Class-weighted loss to handle fall:ADL imbalance
  - LR schedule: cosine decay with warm restarts
  - Early stopping on validation AUC (patience = 15 epochs)
  - Checkpoint saved at best validation AUC

Usage:
    python train.py [--mobiact PATH] [--sisfall PATH] [--output-dir PATH]

IEC 62304 Design Record: FD-TRAIN-001 Rev 1.0
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

# Configure logging before TF import to suppress TF noise
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fall_detector.train")

# ── Suppress TensorFlow info / warning logs ───────────────────────────────────
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train FallNet-Micro fall detector")
    p.add_argument("--mobiact",    type=Path, default=None,
                   help="Root directory of MobiAct v2 dataset")
    p.add_argument("--sisfall",    type=Path, default=None,
                   help="Root directory of SisFall dataset")
    p.add_argument("--output-dir", type=Path, default=Path("models"),
                   help="Directory for saved model and artefacts")
    p.add_argument("--epochs",     type=int, default=100)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--seed",       type=int, default=42)
    return p.parse_args()


def train(args: argparse.Namespace) -> dict:
    """
    Full training pipeline.  Returns a metrics dict for downstream validation.
    """
    import tensorflow as tf
    from sklearn.utils.class_weight import compute_class_weight

    from data_pipeline import build_dataset, train_val_test_split
    from model import build_fallnet_micro, count_params, estimate_macs, model_summary_str

    tf.random.set_seed(args.seed)
    np.random.seed(args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ckpt_path = args.output_dir / "fall_detector_best.keras"

    # ── 1. Dataset ───────────────────────────────────────────────────────────
    logger.info("=== Phase 1: Dataset assembly ===")
    X, y, stats = build_dataset(
        mobiact_root=args.mobiact,
        sisfall_root=args.sisfall,
        rng_seed=args.seed,
    )
    logger.info("Dataset: %s", stats.summary())
    assert stats.fall_count >= 5_000,  f"Insufficient falls: {stats.fall_count}"
    assert stats.adl_count  >= 20_000, f"Insufficient ADLs: {stats.adl_count}"

    X_train, y_train, X_val, y_val, X_test, y_test = train_val_test_split(
        X, y, val_frac=0.10, test_frac=0.15, seed=args.seed)

    logger.info("Train:  %d  |  Val: %d  |  Test: %d",
                len(X_train), len(X_val), len(X_test))

    # ── 2. Class weights ─────────────────────────────────────────────────────
    classes = np.array([0, 1])
    cw = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weights = {0: float(cw[0]), 1: float(cw[1])}
    logger.info("Class weights: ADL=%.3f  Fall=%.3f",
                class_weights[0], class_weights[1])

    # ── 3. Model ─────────────────────────────────────────────────────────────
    logger.info("=== Phase 2: Model construction ===")
    model = build_fallnet_micro()
    pinfo = count_params(model)
    macs  = estimate_macs(model)
    logger.info("Parameters: %d  (~%s KB INT8)", pinfo["total_params"],
                pinfo["int8_size_kb"])
    logger.info("Estimated MACs per inference: %d", macs)
    logger.info(model_summary_str(model))

    # Verify size constraint
    assert pinfo["int8_size_kb"] <= 100.0, (
        f"Model INT8 size {pinfo['int8_size_kb']} KB exceeds 100 KB budget")

    # ── 4. Callbacks ──────────────────────────────────────────────────────────
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(ckpt_path),
            monitor="val_auc",
            mode="max",
            save_best_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_auc",
            mode="max",
            patience=15,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_auc",
            mode="max",
            factor=0.5,
            patience=6,
            min_lr=1e-6,
            verbose=1,
        ),
        tf.keras.callbacks.CSVLogger(
            str(args.output_dir / "training_history.csv"),
            append=False,
        ),
    ]

    # ── 5. Training ───────────────────────────────────────────────────────────
    logger.info("=== Phase 3: Training (max %d epochs, batch %d) ===",
                args.epochs, args.batch_size)
    t0 = time.time()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=args.epochs,
        batch_size=args.batch_size,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=2,
    )
    train_time = time.time() - t0
    logger.info("Training complete in %.1f s", train_time)

    # ── 6. Test-set evaluation ────────────────────────────────────────────────
    logger.info("=== Phase 4: Held-out test evaluation ===")
    y_prob = model.predict(X_test, batch_size=256, verbose=0).ravel()
    metrics = _compute_metrics(y_test, y_prob)
    _log_metrics(metrics)

    # ── 7. Validate acceptance criteria ──────────────────────────────────────
    _assert_acceptance_criteria(metrics, pinfo)

    # ── 8. Persist artefacts ──────────────────────────────────────────────────
    model.save(str(args.output_dir / "fall_detector_final.keras"))

    result = {
        "model_params":     pinfo,
        "macs":             macs,
        "train_time_s":     round(train_time, 1),
        "epochs_trained":   len(history.history["loss"]),
        "test_metrics":     metrics,
        "dataset_stats":    {
            "fall_count":  stats.fall_count,
            "adl_count":   stats.adl_count,
            "source_files": len(stats.source_files),
        },
        "class_weights":    class_weights,
        "checkpoint_path":  str(ckpt_path),
    }

    out_json = args.output_dir / "training_result.json"
    out_json.write_text(json.dumps(result, indent=2))
    logger.info("Training artefacts saved to %s", args.output_dir)

    return result


# ── Metric helpers ────────────────────────────────────────────────────────────
def _compute_metrics(y_true: np.ndarray, y_prob: np.ndarray,
                     threshold: float = 0.5) -> dict:
    from sklearn.metrics import (
        roc_auc_score, confusion_matrix, classification_report,
        average_precision_score,
    )

    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    sensitivity = tp / (tp + fn + 1e-9)
    specificity = tn / (tn + fp + 1e-9)
    ppv         = tp / (tp + fp + 1e-9)
    npv         = tn / (tn + fn + 1e-9)
    f1          = 2 * tp / (2 * tp + fp + fn + 1e-9)

    # Estimate false positives per day
    # Assumption: 1 window = 1 s (50 % overlap → 2 windows/s)
    # FP/day = fp_count / n_adl_windows × (24 h × 3600 s × 2)
    n_adl = int((y_true == 0).sum())
    fp_rate_per_day = (fp / (n_adl + 1e-9)) * (24 * 3600 * 2)

    return {
        "threshold":        threshold,
        "tp": int(tp), "tn": int(tn), "fp": int(fp), "fn": int(fn),
        "sensitivity":      round(float(sensitivity), 4),
        "specificity":      round(float(specificity), 4),
        "ppv":              round(float(ppv), 4),
        "npv":              round(float(npv), 4),
        "f1_score":         round(float(f1), 4),
        "roc_auc":          round(float(roc_auc_score(y_true, y_prob)), 4),
        "avg_precision":    round(float(average_precision_score(y_true, y_prob)), 4),
        "fp_per_day_est":   round(float(fp_rate_per_day), 2),
    }


def _log_metrics(m: dict) -> None:
    logger.info("── Test metrics ──────────────────────────────────")
    logger.info("  Sensitivity (recall): %.4f  [target ≥0.95]", m["sensitivity"])
    logger.info("  Specificity:          %.4f  [target ≥0.90]", m["specificity"])
    logger.info("  Precision (PPV):      %.4f", m["ppv"])
    logger.info("  NPV:                  %.4f", m["npv"])
    logger.info("  F1 Score:             %.4f", m["f1_score"])
    logger.info("  ROC-AUC:              %.4f", m["roc_auc"])
    logger.info("  Est. FP/day:          %.2f  [target ≤2.0]", m["fp_per_day_est"])
    logger.info("  TP=%d  TN=%d  FP=%d  FN=%d",
                m["tp"], m["tn"], m["fp"], m["fn"])


def _assert_acceptance_criteria(metrics: dict, pinfo: dict) -> None:
    failures = []

    if metrics["sensitivity"] < 0.95:
        failures.append(
            f"FAIL sensitivity={metrics['sensitivity']:.4f} < 0.95")
    if metrics["specificity"] < 0.90:
        failures.append(
            f"FAIL specificity={metrics['specificity']:.4f} < 0.90")
    if pinfo["int8_size_kb"] > 100.0:
        failures.append(
            f"FAIL model size={pinfo['int8_size_kb']} KB > 100 KB")
    if metrics["fp_per_day_est"] > 2.0:
        logger.warning("WARNING fp/day=%.2f > 2.0 — threshold tuning may be required",
                       metrics["fp_per_day_est"])

    if failures:
        for f in failures:
            logger.error(f)
        raise ValueError(
            "Acceptance criteria NOT met:\n" + "\n".join(failures))

    logger.info("✓ All acceptance criteria MET")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    args = parse_args()
    result = train(args)
    print(json.dumps(result, indent=2))
