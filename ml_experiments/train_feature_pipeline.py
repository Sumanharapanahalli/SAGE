"""
Training script for the feature engineering pipeline.

Run:
    python ml_experiments/train_feature_pipeline.py

Steps:
  1. Load data (synthetic demo or CSV via --data path/to/file.csv)
  2. Data quality checks: missing-value audit, class-imbalance detection,
     leakage risk scan (near-perfect correlation to target)
  3. Stratified train/test split (no data from test set touches fit)
  4. Build sklearn Pipeline: ColumnTransformer → GradientBoostingClassifier
  5. Stratified K-Fold cross-validation on train set
  6. Final hold-out evaluation with accuracy, F1, ROC-AUC
  7. Log all params + metrics to MLflow (falls back to JSON if unavailable)
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline

# Add ml_experiments/src to path when running from repo root
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from feature_pipeline import build_feature_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------------

def audit_missing(df: pd.DataFrame) -> None:
    """Log missing-value summary and warn on columns with > 50 % missing."""
    missing_pct = df.isnull().mean().sort_values(ascending=False)
    nonzero = missing_pct[missing_pct > 0]
    if nonzero.empty:
        logger.info("No missing values found.")
        return
    logger.info("Missing value summary:\n%s", nonzero.to_string())
    high = nonzero[nonzero > 0.5]
    if not high.empty:
        logger.warning(
            "Columns with > 50%% missing — consider dropping: %s",
            high.index.tolist(),
        )


def check_class_imbalance(y: pd.Series, threshold: float = 0.10) -> bool:
    """
    Return True if any class proportion < ``threshold``.

    Log a warning with the full distribution when imbalance is detected.
    Consider SMOTE / class_weight='balanced' if True.
    """
    counts = y.value_counts(normalize=True).sort_index()
    logger.info("Class distribution:\n%s", counts.to_string())
    imbalanced = bool((counts < threshold).any())
    if imbalanced:
        logger.warning(
            "Class imbalance detected (min proportion %.3f < threshold %.2f). "
            "Consider class_weight='balanced' or oversampling.",
            counts.min(),
            threshold,
        )
    return imbalanced


def detect_leakage_risk(
    X: pd.DataFrame,
    y: pd.Series,
    correlation_threshold: float = 0.95,
) -> bool:
    """
    Flag numeric features with near-perfect Pearson correlation to the target.

    A |corr| > 0.95 to the target almost always signals target leakage — the
    feature encodes information that would not be available at inference time.

    Returns True if any leaker is found (does NOT raise — caller decides).
    """
    numeric_X = X.select_dtypes(include=np.number)
    if numeric_X.empty:
        return False

    y_numeric = pd.to_numeric(y, errors="coerce")
    correlations = numeric_X.corrwith(y_numeric).abs().dropna().sort_values(ascending=False)
    logger.info("Top feature-target correlations:\n%s", correlations.head(10).to_string())

    leakers = correlations[correlations > correlation_threshold]
    if not leakers.empty:
        logger.error(
            "LEAKAGE RISK — features with |corr| > %.2f to target: %s",
            correlation_threshold,
            leakers.index.tolist(),
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Experiment logging
# ---------------------------------------------------------------------------

def _log_to_mlflow(
    params: Dict[str, Any],
    metrics: Dict[str, float],
    run_name: str,
) -> None:
    import mlflow

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(params)
        mlflow.log_metrics(metrics)
    logger.info("MLflow run '%s' logged.", run_name)


def _log_to_json(
    params: Dict[str, Any],
    metrics: Dict[str, float],
    run_name: str,
    log_dir: Path = Path("experiment_logs"),
) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "run_name": run_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "params": params,
        "metrics": metrics,
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = log_dir / f"{run_name}_{ts}.json"
    out.write_text(json.dumps(record, indent=2))
    logger.info("Experiment logged → %s", out)


def log_experiment(
    params: Dict[str, Any],
    metrics: Dict[str, float],
    run_name: str = "feature_pipeline_run",
) -> None:
    """Log to MLflow when available, JSON file otherwise."""
    try:
        _log_to_mlflow(params, metrics, run_name)
    except Exception:
        _log_to_json(params, metrics, run_name)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    df: pd.DataFrame,
    target_col: str,
    numeric_cols: List[str],
    ohe_cols: List[str],
    target_enc_cols: List[str],
    numeric_strategy: str = "mean",
    test_size: float = 0.20,
    random_state: int = 42,
    cv_folds: int = 5,
) -> Tuple[Pipeline, Dict[str, float], bool, bool]:
    """
    Full training run.

    Pipeline
    --------
    leakage check → audit missing → stratified split
    → ColumnTransformer fit on train only
    → stratified K-Fold CV on train
    → hold-out evaluation
    → experiment log

    Returns
    -------
    (fitted_pipeline, metrics_dict, class_imbalance_flag, leakage_risk_flag)
    """
    X = df.drop(columns=[target_col])
    y = df[target_col]

    logger.info("Dataset shape: %s rows × %s cols", *df.shape)
    audit_missing(df)
    class_imbalance = check_class_imbalance(y)
    leakage_risk = detect_leakage_risk(X, y)

    # ── Stratified split ────────────────────────────────────────────────────
    # stratify=y preserves class proportions in both splits.
    # Transformers are fit ONLY on X_train — test set is never seen during fit.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=test_size,
        stratify=y,
        random_state=random_state,
        shuffle=True,
    )
    logger.info(
        "Stratified split → train=%d, test=%d (%.0f%%/%.0f%%)",
        len(X_train), len(X_test),
        (1 - test_size) * 100, test_size * 100,
    )

    # ── Pipeline assembly ───────────────────────────────────────────────────
    feature_transformer = build_feature_pipeline(
        numeric_cols=numeric_cols,
        ohe_cols=ohe_cols,
        target_enc_cols=target_enc_cols,
        numeric_strategy=numeric_strategy,
    )

    classifier = GradientBoostingClassifier(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=random_state,
    )

    pipeline = Pipeline(
        steps=[
            ("features", feature_transformer),
            ("classifier", classifier),
        ]
    )

    # ── Stratified K-Fold CV (on train only) ────────────────────────────────
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)

    t0 = time.perf_counter()
    cv_results = cross_validate(
        pipeline,
        X_train,
        y_train,
        cv=cv,
        scoring=["accuracy", "f1_weighted", "roc_auc_ovr_weighted"],
        return_train_score=False,
        n_jobs=-1,
        error_score="raise",
    )
    cv_elapsed = time.perf_counter() - t0

    cv_metrics: Dict[str, float] = {
        "cv_accuracy_mean":  float(np.mean(cv_results["test_accuracy"])),
        "cv_accuracy_std":   float(np.std(cv_results["test_accuracy"])),
        "cv_f1_mean":        float(np.mean(cv_results["test_f1_weighted"])),
        "cv_f1_std":         float(np.std(cv_results["test_f1_weighted"])),
        "cv_roc_auc_mean":   float(np.mean(cv_results["test_roc_auc_ovr_weighted"])),
        "cv_elapsed_s":      round(cv_elapsed, 2),
    }
    logger.info(
        "CV (%d-fold): accuracy=%.4f±%.4f | f1=%.4f±%.4f | roc_auc=%.4f",
        cv_folds,
        cv_metrics["cv_accuracy_mean"], cv_metrics["cv_accuracy_std"],
        cv_metrics["cv_f1_mean"],       cv_metrics["cv_f1_std"],
        cv_metrics["cv_roc_auc_mean"],
    )

    # ── Final fit on full train set ─────────────────────────────────────────
    pipeline.fit(X_train, y_train)   # scalers/encoders fit on X_train only

    # ── Hold-out evaluation ─────────────────────────────────────────────────
    y_pred  = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)

    holdout: Dict[str, float] = {
        "holdout_accuracy":     float(accuracy_score(y_test, y_pred)),
        "holdout_f1_weighted":  float(f1_score(y_test, y_pred, average="weighted")),
        "holdout_f1_macro":     float(f1_score(y_test, y_pred, average="macro")),
        "holdout_roc_auc":      float(
            roc_auc_score(y_test, y_proba, multi_class="ovr", average="weighted")
        ),
    }
    logger.info(
        "Hold-out: accuracy=%.4f | f1_weighted=%.4f | roc_auc=%.4f",
        holdout["holdout_accuracy"],
        holdout["holdout_f1_weighted"],
        holdout["holdout_roc_auc"],
    )
    logger.info("Classification report:\n%s", classification_report(y_test, y_pred))

    # ── Log experiment ──────────────────────────────────────────────────────
    params = {
        "numeric_cols":       numeric_cols,
        "ohe_cols":           ohe_cols,
        "target_enc_cols":    target_enc_cols,
        "numeric_strategy":   numeric_strategy,
        "test_size":          test_size,
        "cv_folds":           cv_folds,
        "classifier":         type(classifier).__name__,
        "n_estimators":       classifier.n_estimators,
        "learning_rate":      classifier.learning_rate,
        "max_depth":          classifier.max_depth,
        "subsample":          classifier.subsample,
        "class_imbalance":    class_imbalance,
        "leakage_risk":       leakage_risk,
    }
    log_experiment(params, {**cv_metrics, **holdout})

    return pipeline, {**cv_metrics, **holdout}, class_imbalance, leakage_risk


# ---------------------------------------------------------------------------
# Synthetic demo dataset
# ---------------------------------------------------------------------------

def make_demo_dataset(n: int = 5_000, random_state: int = 42) -> pd.DataFrame:
    """
    Generate a synthetic binary classification dataset with:
      - 4 numeric features (with ~8 % missing each)
      - 2 low-cardinality categoricals  → OHE
      - 1 high-cardinality categorical  → target encoding
    """
    rng = np.random.default_rng(random_state)

    df = pd.DataFrame(
        {
            "age":     rng.integers(18, 80, n).astype(float),
            "income":  rng.lognormal(10.0, 1.0, n),
            "score":   rng.normal(50.0, 15.0, n),
            "tenure":  rng.integers(0, 40, n).astype(float),
            "region":  rng.choice(["north", "south", "east", "west"], n),
            "product": rng.choice(["A", "B", "C"], n),
            "city":    rng.choice([f"city_{i:02d}" for i in range(50)], n),
        }
    )

    # Inject 8 % missing values in numeric and categorical columns
    for col in ["age", "income", "score", "tenure", "region", "city"]:
        mask = rng.random(n) < 0.08
        df.loc[mask, col] = np.nan

    # Structured target (not purely random — avoids trivial leakage)
    logit = (
        0.025  * df["age"].fillna(df["age"].median())
        + 3e-5 * df["income"].fillna(df["income"].median())
        - 0.6  * (df["product"] == "A").astype(float)
        + 0.4  * (df["region"] == "north").fillna(0)
        + rng.normal(0, 1, n)
    )
    df["churn"] = (logit > logit.median()).astype(int)
    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Feature Engineering Pipeline — demo")
    parser.add_argument(
        "--data", type=str, default=None,
        help="Path to CSV file (default: use synthetic demo dataset)",
    )
    parser.add_argument("--target",  type=str, default="churn")
    parser.add_argument("--rows",    type=int, default=5_000,
                        help="Rows for synthetic dataset (ignored if --data is given)")
    parser.add_argument("--strategy", type=str, default="mean",
                        choices=["mean", "median"])
    parser.add_argument("--test-size", type=float, default=0.20)
    parser.add_argument("--cv-folds",  type=int,   default=5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.data:
        df = pd.read_csv(args.data)
        logger.info("Loaded CSV: %s", args.data)
        # Infer column types automatically
        numeric_cols   = df.select_dtypes(include=np.number).columns.drop(args.target, errors="ignore").tolist()
        cat_cols       = df.select_dtypes(include="object").columns.tolist()
        ohe_cols       = [c for c in cat_cols if df[c].nunique() < 20]
        target_enc_cols = [c for c in cat_cols if df[c].nunique() >= 20]
    else:
        df              = make_demo_dataset(n=args.rows)
        numeric_cols    = ["age", "income", "score", "tenure"]
        ohe_cols        = ["region", "product"]
        target_enc_cols = ["city"]

    pipeline, metrics, class_imbalance, leakage_risk = train(
        df=df,
        target_col=args.target,
        numeric_cols=numeric_cols,
        ohe_cols=ohe_cols,
        target_enc_cols=target_enc_cols,
        numeric_strategy=args.strategy,
        test_size=args.test_size,
        random_state=42,
        cv_folds=args.cv_folds,
    )

    # Structured JSON output (mirrors the required schema)
    output = {
        "model_type": "classification",
        "metrics": {
            "accuracy": round(metrics["holdout_accuracy"], 4),
            "f1":       round(metrics["holdout_f1_weighted"], 4),
            "roc_auc":  round(metrics["holdout_roc_auc"], 4),
            "cv_accuracy_mean": round(metrics["cv_accuracy_mean"], 4),
            "cv_f1_mean":       round(metrics["cv_f1_mean"], 4),
        },
        "data_checks": {
            "leakage_risk":    leakage_risk,
            "class_imbalance": class_imbalance,
        },
        "pipeline_steps": [s[0] for s in pipeline.steps],
        "feature_groups": {
            "numeric":    numeric_cols,
            "ohe":        ohe_cols,
            "target_enc": target_enc_cols,
        },
    }
    print(json.dumps(output, indent=2))
