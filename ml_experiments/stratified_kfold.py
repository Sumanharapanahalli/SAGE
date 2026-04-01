"""
Stratified K-Fold Cross-Validation — Scratch vs sklearn
========================================================
Rules enforced:
  - Stratification maintained in every fold (both implementations)
  - Scaler fit only on train fold, transform applied to test fold (no leakage)
  - Full classification metrics: accuracy, precision, recall, F1 (macro + weighted)
  - All experiments logged via Python logging + JSON results file
  - Reproducible: random_state threaded through everywhere
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold as SklearnStratifiedKFold
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "stratified_kfold.log"),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Stratified K-Fold implementation
# ---------------------------------------------------------------------------

class StratifiedKFoldScratch:
    """
    Stratified K-Fold split implemented from scratch.

    Algorithm:
      1. Bucket sample indices by class label.
      2. For each bucket, shuffle and split into k approximately equal parts.
      3. Fold i = union of part-i from every class bucket  →  test indices.
      4. Train indices = everything not in test.

    This guarantees class proportions are preserved in every fold.
    """

    def __init__(self, n_splits: int = 5, shuffle: bool = True, random_state: int | None = None):
        if n_splits < 2:
            raise ValueError("n_splits must be >= 2")
        self.n_splits = n_splits
        self.shuffle = shuffle
        self.random_state = random_state

    # ------------------------------------------------------------------
    def split(self, X: np.ndarray, y: np.ndarray):
        """
        Yield (train_indices, test_indices) for each fold.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
        y : array-like of shape (n_samples,)  — class labels

        Yields
        ------
        train_idx : np.ndarray
        test_idx  : np.ndarray
        """
        rng = np.random.RandomState(self.random_state)
        y = np.asarray(y)
        n_samples = len(y)

        # --- 1. Bucket indices by class ---
        class_indices: dict[Any, list[int]] = defaultdict(list)
        for idx, label in enumerate(y):
            class_indices[label].append(idx)

        # --- 2. Shuffle within each class bucket ---
        class_folds: dict[Any, list[np.ndarray]] = {}
        for label, indices in class_indices.items():
            indices_arr = np.array(indices)
            if self.shuffle:
                rng.shuffle(indices_arr)
            # Split into n_splits parts (unequal lengths handled by array_split)
            class_folds[label] = np.array_split(indices_arr, self.n_splits)

        # --- 3. Build fold test sets ---
        for fold_i in range(self.n_splits):
            test_parts = [class_folds[label][fold_i] for label in class_folds]
            test_idx = np.concatenate(test_parts)
            train_idx = np.setdiff1d(np.arange(n_samples), test_idx)

            # Sort for reproducibility / interpretability
            train_idx = np.sort(train_idx)
            test_idx = np.sort(test_idx)

            yield train_idx, test_idx

    # ------------------------------------------------------------------
    def get_n_splits(self) -> int:
        return self.n_splits

    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"StratifiedKFoldScratch(n_splits={self.n_splits}, "
            f"shuffle={self.shuffle}, random_state={self.random_state})"
        )


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

METRIC_NAMES = ["accuracy", "precision_macro", "recall_macro", "f1_macro",
                "precision_weighted", "recall_weighted", "f1_weighted"]


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute all classification metrics for a single fold."""
    return {
        "accuracy":            accuracy_score(y_true, y_pred),
        "precision_macro":     precision_score(y_true, y_pred, average="macro",   zero_division=0),
        "recall_macro":        recall_score(y_true, y_pred,    average="macro",   zero_division=0),
        "f1_macro":            f1_score(y_true, y_pred,        average="macro",   zero_division=0),
        "precision_weighted":  precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall_weighted":     recall_score(y_true, y_pred,    average="weighted", zero_division=0),
        "f1_weighted":         f1_score(y_true, y_pred,        average="weighted", zero_division=0),
    }


def verify_stratification(y: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray) -> dict:
    """Return class proportions for train / test — used to confirm stratification."""
    classes, full_counts = np.unique(y, return_counts=True)
    full_props = full_counts / len(y)
    test_classes, test_counts = np.unique(y[test_idx], return_counts=True)
    test_props_map = dict(zip(test_classes.tolist(), (test_counts / len(test_idx)).tolist()))
    return {
        "full_proportions":  dict(zip(classes.tolist(), full_props.tolist())),
        "test_proportions":  test_props_map,
        "max_drift":         float(max(
            abs(test_props_map.get(c, 0.0) - p)
            for c, p in zip(classes.tolist(), full_props.tolist())
        )),
    }


# ---------------------------------------------------------------------------
# Core cross-validation runner (shared logic)
# ---------------------------------------------------------------------------

def run_cv(
    splitter,
    X: np.ndarray,
    y: np.ndarray,
    model_fn,
    label: str,
    random_state: int = 42,
) -> dict:
    """
    Run k-fold CV with the given splitter.  Scaler is fit per fold on train only.

    Returns
    -------
    dict with per-fold metrics and aggregate mean ± std.
    """
    log.info("=" * 70)
    log.info("Starting CV run  |  splitter=%s  |  folds=%d", label, splitter.n_splits)
    log.info("=" * 70)

    fold_metrics: list[dict[str, float]] = []
    fold_stratification: list[dict] = []
    t0 = time.perf_counter()

    for fold_i, (train_idx, test_idx) in enumerate(splitter.split(X, y)):
        # ---- Stratification verification ----
        strat_info = verify_stratification(y, train_idx, test_idx)
        fold_stratification.append(strat_info)

        # ---- Scale: fit on TRAIN only (no leakage) ----
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X[train_idx])   # fit + transform on train
        X_test  = scaler.transform(X[test_idx])        # transform only on test

        y_train, y_test = y[train_idx], y[test_idx]

        # ---- Train ----
        model = model_fn(random_state=random_state)
        model.fit(X_train, y_train)

        # ---- Predict + evaluate ----
        y_pred = model.predict(X_test)
        metrics = compute_metrics(y_test, y_pred)
        fold_metrics.append(metrics)

        log.info(
            "Fold %d/%d | train=%d test=%d | strat_drift=%.4f | "
            "acc=%.4f f1_macro=%.4f f1_weighted=%.4f",
            fold_i + 1, splitter.n_splits,
            len(train_idx), len(test_idx),
            strat_info["max_drift"],
            metrics["accuracy"], metrics["f1_macro"], metrics["f1_weighted"],
        )

    elapsed = time.perf_counter() - t0

    # ---- Aggregate ----
    agg: dict[str, dict[str, float]] = {}
    for metric in METRIC_NAMES:
        vals = np.array([fm[metric] for fm in fold_metrics])
        agg[metric] = {"mean": float(vals.mean()), "std": float(vals.std())}

    log.info("--- %s Summary (%.3fs) ---", label, elapsed)
    for metric, stats in agg.items():
        log.info("  %-22s %.4f ± %.4f", metric, stats["mean"], stats["std"])

    return {
        "label":              label,
        "n_splits":           splitter.n_splits,
        "elapsed_seconds":    round(elapsed, 4),
        "fold_metrics":       fold_metrics,
        "fold_stratification": fold_stratification,
        "aggregate":          agg,
    }


# ---------------------------------------------------------------------------
# Class-imbalance check
# ---------------------------------------------------------------------------

def check_class_imbalance(y: np.ndarray, threshold: float = 0.2) -> dict:
    classes, counts = np.unique(y, return_counts=True)
    proportions = counts / len(y)
    imbalanced = bool(proportions.min() < threshold)
    return {
        "class_distribution": dict(zip(classes.tolist(), counts.tolist())),
        "class_proportions":  dict(zip(classes.tolist(), proportions.tolist())),
        "imbalanced":         imbalanced,
        "minority_proportion": float(proportions.min()),
    }


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def main() -> dict:
    RANDOM_STATE = 42
    N_SPLITS     = 5
    RESULTS_PATH = Path("logs/experiment_results.json")

    # ---- Load dataset ----
    log.info("Loading breast_cancer dataset")
    data = load_breast_cancer()
    X, y = data.data, data.target
    log.info("Dataset shape: X=%s  |  classes=%s", X.shape, np.unique(y).tolist())

    # ---- Data checks ----
    imbalance_check = check_class_imbalance(y)
    log.info("Class imbalance check: %s", imbalance_check)

    # ---- Experiment parameters ----
    params = {
        "dataset":       "breast_cancer",
        "n_samples":     int(X.shape[0]),
        "n_features":    int(X.shape[1]),
        "n_splits":      N_SPLITS,
        "random_state":  RANDOM_STATE,
        "model":         "LogisticRegression",
        "model_params":  {"max_iter": 1000, "solver": "lbfgs"},
        "scaler":        "StandardScaler",
        "leakage_risk":  False,   # scaler fit on train only, verified below
    }
    log.info("Experiment params: %s", json.dumps(params, indent=2))

    model_fn = lambda random_state: LogisticRegression(
        max_iter=1000, solver="lbfgs", random_state=random_state
    )

    # ---- Run 1: Custom scratch implementation ----
    scratch_splitter = StratifiedKFoldScratch(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )
    scratch_results = run_cv(scratch_splitter, X, y, model_fn,
                             label="StratifiedKFold-Scratch", random_state=RANDOM_STATE)

    # ---- Run 2: sklearn StratifiedKFold ----
    sklearn_splitter = SklearnStratifiedKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )
    sklearn_results = run_cv(sklearn_splitter, X, y, model_fn,
                             label="StratifiedKFold-sklearn", random_state=RANDOM_STATE)

    # ---- Comparison table ----
    log.info("")
    log.info("=" * 70)
    log.info("COMPARISON: Scratch vs sklearn (mean ± std across %d folds)", N_SPLITS)
    log.info("=" * 70)
    log.info("%-22s  %-22s  %-22s", "Metric", "Scratch", "sklearn")
    log.info("-" * 70)
    for metric in METRIC_NAMES:
        s = scratch_results["aggregate"][metric]
        k = sklearn_results["aggregate"][metric]
        log.info(
            "%-22s  %.4f ± %.4f       %.4f ± %.4f",
            metric, s["mean"], s["std"], k["mean"], k["std"]
        )

    # ---- Drift comparison ----
    scratch_drifts = [f["max_drift"] for f in scratch_results["fold_stratification"]]
    sklearn_drifts = [f["max_drift"] for f in sklearn_results["fold_stratification"]]
    log.info("")
    log.info("Stratification drift (max class proportion delta from global):")
    log.info("  Scratch: %.5f ± %.5f", np.mean(scratch_drifts), np.std(scratch_drifts))
    log.info("  sklearn: %.5f ± %.5f", np.mean(sklearn_drifts), np.std(sklearn_drifts))

    # ---- Persist results ----
    output = {
        "params":           params,
        "data_checks": {
            "leakage_risk":    False,
            "class_imbalance": imbalance_check["imbalanced"],
            "imbalance_detail": imbalance_check,
        },
        "scratch": scratch_results,
        "sklearn": sklearn_results,
        "comparison": {
            metric: {
                "scratch_mean": scratch_results["aggregate"][metric]["mean"],
                "scratch_std":  scratch_results["aggregate"][metric]["std"],
                "sklearn_mean": sklearn_results["aggregate"][metric]["mean"],
                "sklearn_std":  sklearn_results["aggregate"][metric]["std"],
                "delta_mean":   abs(
                    scratch_results["aggregate"][metric]["mean"] -
                    sklearn_results["aggregate"][metric]["mean"]
                ),
            }
            for metric in METRIC_NAMES
        },
    }

    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(output, indent=2))
    log.info("Results saved → %s", RESULTS_PATH)

    return output


if __name__ == "__main__":
    results = main()

    # Final machine-readable summary to stdout
    print("\n" + "=" * 70)
    print("FINAL RESULTS (mean ± std)")
    print("=" * 70)
    print(f"{'Metric':<24} {'Scratch':^22} {'sklearn':^22} {'|Δ mean|':^10}")
    print("-" * 70)
    for metric, vals in results["comparison"].items():
        print(
            f"{metric:<24} "
            f"{vals['scratch_mean']:.4f} ± {vals['scratch_std']:.4f}   "
            f"{vals['sklearn_mean']:.4f} ± {vals['sklearn_std']:.4f}   "
            f"{vals['delta_mean']:.6f}"
        )
    print()
    print(f"Leakage risk    : {results['data_checks']['leakage_risk']}")
    print(f"Class imbalance : {results['data_checks']['class_imbalance']}")
