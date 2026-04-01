"""
Experiment: Decision Tree (Info Gain) + Reduced Error Pruning on Iris dataset.

Data pipeline
-------------
  Stratified 60/20/20 train/val/test split
  StandardScaler fitted on train only — val and test are transform-only
  (no data leakage)

Evaluation
----------
  Accuracy, F1 (macro + weighted), Precision, Recall
  Confusion matrix, per-class classification report
  Pre- vs post-pruning comparison

Logging
-------
  JSON experiment record written to experiments/<timestamp>.json
  Human-readable log to experiments/<timestamp>.log

Usage
-----
  python train_evaluate.py
"""

import copy
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from sklearn.datasets import load_iris
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# Local
sys.path.insert(0, str(Path(__file__).parent / "src"))
from decision_tree import DecisionTreeClassifier, ReducedErrorPruner  # noqa: E402

# ---------------------------------------------------------------------------
# Experiment config — all hyperparameters in one place
# ---------------------------------------------------------------------------

PARAMS: dict = {
    "random_state": 42,
    "test_size": 0.20,       # 20 % held-out test set
    "val_size": 0.20,        # 20 % validation (for REP)
    # train_size is implicitly 60 %
    "max_depth": None,       # grow full tree — REP will prune it
    "min_samples_split": 2,
    "min_samples_leaf": 1,
    "class_imbalance_ratio_threshold": 1.5,
}

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
EXPERIMENTS_DIR = Path(__file__).parent / "experiments"
EXPERIMENTS_DIR.mkdir(exist_ok=True)

log_path = EXPERIMENTS_DIR / f"{RUN_ID}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: evaluate a model on one split
# ---------------------------------------------------------------------------

def evaluate(
    model: DecisionTreeClassifier,
    X: np.ndarray,
    y: np.ndarray,
    split_name: str,
    target_names: list[str],
) -> dict:
    y_pred = model.predict(X)
    metrics = {
        "accuracy": round(accuracy_score(y, y_pred), 6),
        "f1_macro": round(f1_score(y, y_pred, average="macro"), 6),
        "f1_weighted": round(f1_score(y, y_pred, average="weighted"), 6),
        "precision_macro": round(precision_score(y, y_pred, average="macro"), 6),
        "recall_macro": round(recall_score(y, y_pred, average="macro"), 6),
    }
    logger.info("")
    logger.info("── %s ──", split_name)
    for k, v in metrics.items():
        logger.info("  %-22s %.6f", k, v)
    logger.info("\n%s", classification_report(y, y_pred, target_names=target_names))
    logger.info("Confusion matrix:\n%s", confusion_matrix(y, y_pred))
    return metrics


# ---------------------------------------------------------------------------
# Data checks
# ---------------------------------------------------------------------------

def check_data(y: np.ndarray, threshold: float) -> dict[str, bool]:
    counts = np.bincount(y)
    ratio = int(counts.max()) / int(counts.min()) if counts.min() > 0 else float("inf")
    return {
        "leakage_risk": False,          # enforced structurally (scaler fit on train only)
        "class_imbalance": ratio > threshold,
        "imbalance_ratio": round(ratio, 4),
    }


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_experiment() -> dict:
    logger.info("=" * 60)
    logger.info("Experiment ID : %s", RUN_ID)
    logger.info("Parameters    : %s", json.dumps(PARAMS))
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 1. Load dataset
    # ------------------------------------------------------------------
    iris = load_iris()
    X, y = iris.data.astype(np.float64), iris.target.astype(int)
    feature_names: list[str] = list(iris.feature_names)
    target_names: list[str] = list(iris.target_names)

    logger.info(
        "Dataset: Iris — %d samples × %d features — %d classes: %s",
        X.shape[0], X.shape[1], len(target_names), target_names,
    )
    logger.info("Class distribution: %s", dict(zip(target_names, np.bincount(y).tolist())))

    # ------------------------------------------------------------------
    # 2. Data checks
    # ------------------------------------------------------------------
    dc = check_data(y, PARAMS["class_imbalance_ratio_threshold"])
    logger.info("Data checks: %s", dc)

    # ------------------------------------------------------------------
    # 3. Stratified splits  (train 60 / val 20 / test 20)
    #    — leakage impossible: scaler fitted on train ONLY
    # ------------------------------------------------------------------
    X_tv, X_test, y_tv, y_test = train_test_split(
        X, y,
        test_size=PARAMS["test_size"],
        random_state=PARAMS["random_state"],
        stratify=y,
    )
    # val_size relative to the remaining (train+val) portion
    val_ratio = PARAMS["val_size"] / (1.0 - PARAMS["test_size"])
    X_train, X_val, y_train, y_val = train_test_split(
        X_tv, y_tv,
        test_size=val_ratio,
        random_state=PARAMS["random_state"],
        stratify=y_tv,
    )
    logger.info(
        "Split sizes — train: %d  val: %d  test: %d",
        len(X_train), len(X_val), len(X_test),
    )
    logger.info(
        "Train class dist: %s  Val: %s  Test: %s",
        np.bincount(y_train).tolist(),
        np.bincount(y_val).tolist(),
        np.bincount(y_test).tolist(),
    )

    # ------------------------------------------------------------------
    # 4. Feature scaling — fit on TRAIN only (no leakage)
    # ------------------------------------------------------------------
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)   # fit + transform
    X_val   = scaler.transform(X_val)          # transform only
    X_test  = scaler.transform(X_test)         # transform only
    logger.info("StandardScaler: mean=%s  std=%s", scaler.mean_.round(4), scaler.scale_.round(4))
    logger.info("Scaler fitted on training data only — no leakage.")

    # ------------------------------------------------------------------
    # 5. Train unpruned tree
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=== Unpruned Decision Tree ===")
    tree = DecisionTreeClassifier(
        max_depth=PARAMS["max_depth"],
        min_samples_split=PARAMS["min_samples_split"],
        min_samples_leaf=PARAMS["min_samples_leaf"],
    )
    tree.fit(X_train, y_train)
    logger.info("Depth: %d  |  Nodes: %d  |  Leaves: %d",
                tree.get_depth(), tree.count_nodes(), tree.count_leaves())

    m_unp_train = evaluate(tree, X_train, y_train, "Unpruned — Train", target_names)
    m_unp_val   = evaluate(tree, X_val,   y_val,   "Unpruned — Val",   target_names)
    m_unp_test  = evaluate(tree, X_test,  y_test,  "Unpruned — Test",  target_names)

    # ------------------------------------------------------------------
    # 6. Reduced Error Pruning on a deep copy
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=== Reduced Error Pruning ===")
    pruned_tree = copy.deepcopy(tree)
    pruner = ReducedErrorPruner(pruned_tree)
    pruner.prune(X_val, y_val)
    logger.info("After pruning — Depth: %d  |  Nodes: %d  |  Leaves: %d",
                pruned_tree.get_depth(), pruned_tree.count_nodes(), pruned_tree.count_leaves())

    m_prn_train = evaluate(pruned_tree, X_train, y_train, "Pruned — Train", target_names)
    m_prn_val   = evaluate(pruned_tree, X_val,   y_val,   "Pruned — Val",   target_names)
    m_prn_test  = evaluate(pruned_tree, X_test,  y_test,  "Pruned — Test",  target_names)

    # ------------------------------------------------------------------
    # 7. Summary table
    # ------------------------------------------------------------------
    logger.info("")
    logger.info("=" * 60)
    logger.info("%-30s  %10s  %10s", "Metric", "Unpruned", "Pruned")
    logger.info("-" * 54)
    logger.info("%-30s  %10d  %10d", "Tree depth",     tree.get_depth(),        pruned_tree.get_depth())
    logger.info("%-30s  %10d  %10d", "Node count",     tree.count_nodes(),      pruned_tree.count_nodes())
    logger.info("%-30s  %10d  %10d", "Leaf count",     tree.count_leaves(),     pruned_tree.count_leaves())
    logger.info("-" * 54)
    for metric in ("accuracy", "f1_macro", "precision_macro", "recall_macro"):
        logger.info(
            "%-30s  %10.4f  %10.4f",
            f"Test {metric}", m_unp_test[metric], m_prn_test[metric],
        )
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 8. Build result record
    # ------------------------------------------------------------------
    result = {
        "run_id": RUN_ID,
        "dataset": "iris",
        "model_type": "DecisionTreeClassifier (information gain + reduced error pruning)",
        "params": PARAMS,
        "split": {
            "n_train": int(len(X_train)),
            "n_val": int(len(X_val)),
            "n_test": int(len(X_test)),
        },
        "data_checks": dc,
        "unpruned": {
            "depth": tree.get_depth(),
            "nodes": tree.count_nodes(),
            "leaves": tree.count_leaves(),
            "train": m_unp_train,
            "val":   m_unp_val,
            "test":  m_unp_test,
        },
        "pruned": {
            "depth": pruned_tree.get_depth(),
            "nodes": pruned_tree.count_nodes(),
            "leaves": pruned_tree.count_leaves(),
            "train": m_prn_train,
            "val":   m_prn_val,
            "test":  m_prn_test,
        },
        # Top-level metrics for the final (pruned) model on test
        "metrics": {
            "accuracy": m_prn_test["accuracy"],
            "f1": m_prn_test["f1_macro"],
        },
    }

    record_path = EXPERIMENTS_DIR / f"{RUN_ID}.json"
    record_path.write_text(json.dumps(result, indent=2))
    logger.info("Experiment record saved: %s", record_path)
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_experiment()
    # Print the final JSON summary required by the task spec
    summary = {
        "files": [
            "ml_experiments/decision_tree_iris/src/decision_tree.py",
            "ml_experiments/decision_tree_iris/train_evaluate.py",
            "ml_experiments/decision_tree_iris/requirements.txt",
        ],
        "model_type": result["model_type"],
        "metrics": result["metrics"],
        "data_checks": {
            "leakage_risk": result["data_checks"]["leakage_risk"],
            "class_imbalance": result["data_checks"]["class_imbalance"],
        },
    }
    print("\n" + "=" * 60)
    print("FINAL JSON OUTPUT")
    print("=" * 60)
    print(json.dumps(summary, indent=2))
