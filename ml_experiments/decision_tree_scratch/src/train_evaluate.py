"""
train_evaluate.py
-----------------
Production training + evaluation pipeline for the from-scratch
Decision Tree + Reduced Error Pruning on the Iris dataset.

Data strategy (zero leakage):
  60% train  → tree building only
  20% val    → REP pruning only
  20% test   → final evaluation (touched EXACTLY once, at the very end)

All splits are stratified to preserve class distribution.
No scaler/encoder is fitted here (trees are scale-invariant); if a
preprocessing step were needed it would be fitted solely on X_train.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
from sklearn.datasets import load_iris
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split

# Local import (run from src/ or set PYTHONPATH=src)
from decision_tree import DecisionTreeClassifier, reduced_error_pruning

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stdout,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

EXPERIMENT_LOG_PATH = Path(__file__).parent.parent / "experiment_log.json"


# ---------------------------------------------------------------------------
# Experiment logging
# ---------------------------------------------------------------------------

def log_experiment(params: Dict[str, Any], results: Dict[str, Any]) -> None:
    """
    Append one experiment record to a JSON log file.
    Thread-safe for single-process sequential runs.
    """
    record: Dict[str, Any] = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "params": params,
        "results": results,
    }
    existing: list = []
    if EXPERIMENT_LOG_PATH.exists():
        with open(EXPERIMENT_LOG_PATH, "r") as fh:
            try:
                existing = json.load(fh)
            except json.JSONDecodeError:
                log.warning("Corrupt experiment log — starting fresh.")
    existing.append(record)
    with open(EXPERIMENT_LOG_PATH, "w") as fh:
        json.dump(existing, fh, indent=2)
    log.info("Experiment appended → %s", EXPERIMENT_LOG_PATH)


# ---------------------------------------------------------------------------
# Data loading & integrity checks
# ---------------------------------------------------------------------------

def load_and_check_iris() -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Load Iris, run data integrity checks, return (X, y, class_names, checks).

    Checks performed:
      - NaN / inf presence
      - Class imbalance (ratio of max/min class count > 2)
      - Feature scale range (informational only — trees are scale-invariant)
    """
    iris = load_iris(as_frame=False)
    X: np.ndarray = iris.data.astype(np.float64)
    y: np.ndarray = iris.target.astype(int)

    has_nan = bool(np.isnan(X).any() or np.isinf(X).any())
    counts = np.bincount(y)
    imbalance_ratio = float(counts.max() / counts.min())
    is_imbalanced = imbalance_ratio > 2.0  # flag if dominant class ≥ 2× minority

    log.info("Dataset shape       : %s", X.shape)
    log.info("Class counts        : %s", dict(zip(iris.target_names, counts.tolist())))
    log.info("Imbalance ratio     : %.2f  (imbalanced=%s)", imbalance_ratio, is_imbalanced)
    log.info("NaN / Inf in data   : %s", has_nan)
    log.info(
        "Feature ranges      : %s",
        {iris.feature_names[i]: (round(float(X[:, i].min()), 2), round(float(X[:, i].max()), 2))
         for i in range(X.shape[1])},
    )

    checks: Dict[str, Any] = {
        "leakage_risk": False,          # enforced by fit-only-on-train below
        "class_imbalance": is_imbalanced,
        "has_nan_or_inf": has_nan,
        "imbalance_ratio": round(imbalance_ratio, 4),
        "n_samples": int(len(y)),
        "n_features": int(X.shape[1]),
        "n_classes": int(len(np.unique(y))),
    }
    return X, y, iris.target_names, checks


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    max_depth: int | None = None,
    min_samples_split: int = 2,
    min_samples_leaf: int = 1,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    End-to-end pipeline: load → split → train → prune → evaluate → log.

    Returns a dict with test metrics and data checks for downstream use.
    """
    banner = "=" * 64
    log.info(banner)
    log.info("  Decision Tree (from scratch) + REP  |  Iris Dataset")
    log.info(banner)

    # ------------------------------------------------------------------ #
    # 1. Load & check data                                                #
    # ------------------------------------------------------------------ #
    X, y, class_names, data_checks = load_and_check_iris()

    # ------------------------------------------------------------------ #
    # 2. Stratified 60 / 20 / 20 split — NO LEAKAGE                      #
    #    Scalers / encoders (if any) must be fit ONLY on X_train.         #
    #    Trees are scale-invariant, so no preprocessing is needed here.   #
    # ------------------------------------------------------------------ #
    # Step 1: carve off 20% test
    X_temp, X_test, y_temp, y_test = train_test_split(
        X, y,
        test_size=0.20,
        stratify=y,
        random_state=random_state,
    )
    # Step 2: split remaining 80% → 75% train / 25% val = 60% / 20% overall
    X_train, X_val, y_train, y_val = train_test_split(
        X_temp, y_temp,
        test_size=0.25,
        stratify=y_temp,
        random_state=random_state,
    )

    log.info(
        "Split (stratified)  : train=%d  val=%d  test=%d",
        len(y_train), len(y_val), len(y_test),
    )
    log.info("Train class dist    : %s", np.bincount(y_train).tolist())
    log.info("Val   class dist    : %s", np.bincount(y_val).tolist())
    log.info("Test  class dist    : %s", np.bincount(y_test).tolist())

    # ------------------------------------------------------------------ #
    # 3. Hyperparameters                                                  #
    # ------------------------------------------------------------------ #
    params: Dict[str, Any] = {
        "model": "DecisionTreeClassifier (from scratch, information gain)",
        "pruning": "Reduced Error Pruning (REP)",
        "dataset": "iris",
        "split_strategy": "stratified 60/20/20",
        "random_state": random_state,
        "max_depth": max_depth,
        "min_samples_split": min_samples_split,
        "min_samples_leaf": min_samples_leaf,
        "criterion": "entropy / information_gain",
        "threshold_strategy": "midpoints between consecutive unique values (C4.5)",
    }
    log.info("Hyperparameters     : %s", params)

    # ------------------------------------------------------------------ #
    # 4. Train (unpruned)                                                 #
    # ------------------------------------------------------------------ #
    t0 = time.perf_counter()
    clf = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_split=min_samples_split,
        min_samples_leaf=min_samples_leaf,
    )
    clf.fit(X_train, y_train)
    train_time = time.perf_counter() - t0

    depth_pre = clf.depth()
    nodes_pre = clf.n_nodes()
    leaves_pre = clf.n_leaves()
    val_acc_pre = clf.score(X_val, y_val)
    train_acc_pre = clf.score(X_train, y_train)

    log.info(banner)
    log.info("UNPRUNED TREE")
    log.info("  Depth       : %d", depth_pre)
    log.info("  Nodes       : %d", nodes_pre)
    log.info("  Leaves      : %d", leaves_pre)
    log.info("  Train acc   : %.4f", train_acc_pre)
    log.info("  Val   acc   : %.4f", val_acc_pre)
    log.info("  Train time  : %.4f s", train_time)

    # ------------------------------------------------------------------ #
    # 5. Reduced Error Pruning on validation set                          #
    #    X_test is NOT touched here.                                      #
    # ------------------------------------------------------------------ #
    t1 = time.perf_counter()
    clf = reduced_error_pruning(clf, X_val, y_val)
    prune_time = time.perf_counter() - t1

    depth_post = clf.depth()
    nodes_post = clf.n_nodes()
    leaves_post = clf.n_leaves()
    val_acc_post = clf.score(X_val, y_val)
    pruned_count = getattr(clf, "n_pruned_nodes_", 0)

    log.info(banner)
    log.info("PRUNED TREE  (REP, %d nodes removed)", pruned_count)
    log.info("  Depth       : %d  (was %d)", depth_post, depth_pre)
    log.info("  Nodes       : %d  (was %d)", nodes_post, nodes_pre)
    log.info("  Leaves      : %d  (was %d)", leaves_post, leaves_pre)
    log.info("  Val   acc   : %.4f  (was %.4f)", val_acc_post, val_acc_pre)
    log.info("  Prune time  : %.4f s", prune_time)

    # ------------------------------------------------------------------ #
    # 6. Final evaluation — test set touched EXACTLY ONCE                 #
    # ------------------------------------------------------------------ #
    y_pred = clf.predict(X_test)

    accuracy = float(accuracy_score(y_test, y_pred))
    f1_weighted = float(f1_score(y_test, y_pred, average="weighted"))
    f1_macro = float(f1_score(y_test, y_pred, average="macro"))
    f1_per_class = f1_score(y_test, y_pred, average=None).tolist()
    cm = confusion_matrix(y_test, y_pred).tolist()
    report = classification_report(y_test, y_pred, target_names=class_names)

    log.info(banner)
    log.info("TEST RESULTS  (n=%d, held-out, never seen before)", len(y_test))
    log.info("  Accuracy        : %.4f", accuracy)
    log.info("  F1 (weighted)   : %.4f", f1_weighted)
    log.info("  F1 (macro)      : %.4f", f1_macro)
    log.info("  F1 per class    : %s", [round(v, 4) for v in f1_per_class])
    log.info("\n%s", report)
    log.info("Confusion matrix:\n%s", np.array(cm))

    # ------------------------------------------------------------------ #
    # 7. Log experiment                                                   #
    # ------------------------------------------------------------------ #
    results: Dict[str, Any] = {
        "test_accuracy": round(accuracy, 4),
        "test_f1_weighted": round(f1_weighted, 4),
        "test_f1_macro": round(f1_macro, 4),
        "test_f1_per_class": {
            str(class_names[i]): round(f1_per_class[i], 4)
            for i in range(len(class_names))
        },
        "confusion_matrix": cm,
        "val_accuracy_pre_pruning": round(val_acc_pre, 4),
        "val_accuracy_post_pruning": round(val_acc_post, 4),
        "train_accuracy_pre_pruning": round(train_acc_pre, 4),
        "tree_depth_pre_pruning": depth_pre,
        "tree_depth_post_pruning": depth_post,
        "n_nodes_pre_pruning": nodes_pre,
        "n_nodes_post_pruning": nodes_post,
        "n_leaves_post_pruning": leaves_post,
        "n_pruned_nodes": pruned_count,
        "train_time_s": round(train_time, 6),
        "prune_time_s": round(prune_time, 6),
        "data_checks": {
            "leakage_risk": False,
            "class_imbalance": data_checks["class_imbalance"],
            "has_nan_or_inf": data_checks["has_nan_or_inf"],
        },
    }
    log_experiment(params, results)

    return {
        "model_type": "decision_tree_information_gain_rep",
        "metrics": {
            "accuracy": round(accuracy, 4),
            "f1": round(f1_weighted, 4),
        },
        "data_checks": {
            "leakage_risk": False,
            "class_imbalance": data_checks["class_imbalance"],
        },
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    summary = run_pipeline(
        max_depth=None,       # grow full tree, let REP control complexity
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
    )
    log.info("Pipeline summary: %s", json.dumps(summary, indent=2))
