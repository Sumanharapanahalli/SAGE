"""
receipt_classifier/train.py
───────────────────────────
Production training script for receipt data classification.

Design guarantees
─────────────────
1. Stratified train/test split  — class distribution preserved
2. No data leakage              — scaler/encoder fitted ONLY on train fold
3. Reproducible                 — global seed propagated everywhere
4. Experiment tracking          — MLflow logs params, metrics, artefacts
5. Model persisted              — joblib artefact written to MODEL_DIR

Usage
─────
    python train.py                     # defaults from config.yaml
    python train.py --n-samples 10000   # synthetic dataset size
    python train.py --csv-path data.csv # use real data
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from joblib import dump
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OrdinalEncoder, StandardScaler

from data import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    RECEIPT_CATEGORIES,
    TARGET_COLUMN,
    load_dataset,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("receipt_classifier.train")

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as fh:
        return yaml.safe_load(fh)


# ── Reproducibility ────────────────────────────────────────────────────────────

def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    logger.info("Global seed set to %d", seed)


# ── Feature pipeline (fitted on train only) ────────────────────────────────────

def build_feature_pipeline() -> ColumnTransformer:
    """
    Returns an unfitted ColumnTransformer.

    IMPORTANT: call .fit() on train data only.  Calling .fit_transform() on the
    full dataset before splitting is a data-leakage violation — never do that.
    """
    numeric_pipe = Pipeline([
        ("scaler", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, NUMERIC_FEATURES),
            ("cat", categorical_pipe, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


# ── Model pipeline ─────────────────────────────────────────────────────────────

def build_model_pipeline(params: dict) -> Pipeline:
    """Combine feature transformer + GBM classifier into a single Pipeline."""
    return Pipeline([
        ("features", build_feature_pipeline()),
        ("clf", GradientBoostingClassifier(
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            subsample=params["subsample"],
            min_samples_leaf=params["min_samples_leaf"],
            random_state=params["random_state"],
        )),
    ])


# ── Class-imbalance check ──────────────────────────────────────────────────────

def check_class_imbalance(y: pd.Series, threshold: float = 3.0) -> bool:
    """Return True if max/min class ratio exceeds threshold."""
    counts = y.value_counts()
    ratio = counts.max() / counts.min()
    if ratio > threshold:
        logger.warning(
            "Class imbalance detected — max/min ratio=%.2f > %.1f. "
            "Consider class_weight='balanced' or oversampling.",
            ratio, threshold,
        )
        return True
    return False


# ── Training ───────────────────────────────────────────────────────────────────

def train(
    csv_path: str | None = None,
    n_samples: int = 5_000,
    config: dict | None = None,
) -> dict:
    """
    Full training run.  Returns a metrics dict for downstream use.

    Steps
    ─────
    1. Load config and set seed
    2. Load / generate data
    3. Encode target labels
    4. Stratified train / test split  ← NO LEAKAGE from here on
    5. Fit pipeline on train only
    6. Evaluate on held-out test set
    7. Cross-validation on train set
    8. Log everything with MLflow
    9. Persist model artefact
    """
    if config is None:
        config = load_config()

    training_cfg = config["training"]
    model_cfg = config["model"]
    paths_cfg = config["paths"]

    seed = training_cfg["random_state"]
    set_global_seed(seed)

    # ── 1. Load data ─────────────────────────────────────────────────────────
    dataset = load_dataset(csv_path=csv_path, n_samples=n_samples, random_state=seed)
    X, y_raw = dataset.X, dataset.y

    # ── 2. Encode labels ─────────────────────────────────────────────────────
    label_enc = LabelEncoder()
    label_enc.fit(RECEIPT_CATEGORIES)          # fit on full label space, not y
    y = pd.Series(label_enc.transform(y_raw), name=TARGET_COLUMN)

    # ── 3. Imbalance check ───────────────────────────────────────────────────
    imbalanced = check_class_imbalance(y_raw, threshold=training_cfg["imbalance_threshold"])

    # ── 4. Stratified split ──────────────────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=training_cfg["test_size"],
        random_state=seed,
        stratify=y,            # ← preserves class distribution
    )
    logger.info(
        "Split: %d train / %d test  (test_size=%.0f%%)",
        len(X_train), len(X_test), training_cfg["test_size"] * 100,
    )

    # ── 5. Fit pipeline on train only ────────────────────────────────────────
    model_params = {**model_cfg, "random_state": seed}
    pipeline = build_model_pipeline(model_params)

    logger.info("Fitting pipeline on training set …")
    t0 = time.perf_counter()
    pipeline.fit(X_train, y_train)
    train_duration_s = time.perf_counter() - t0
    logger.info("Training complete in %.2fs", train_duration_s)

    # ── 6. Evaluate on test set ──────────────────────────────────────────────
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)

    # Latency: average single-sample inference time
    latency_ms_list = []
    for i in range(min(200, len(X_test))):
        t = time.perf_counter()
        pipeline.predict(X_test.iloc[[i]])
        latency_ms_list.append((time.perf_counter() - t) * 1000)
    p95_latency_ms = float(np.percentile(latency_ms_list, 95))

    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average="macro")
    f1_weighted = f1_score(y_test, y_pred, average="weighted")
    logloss = log_loss(y_test, y_prob)
    roc_auc = roc_auc_score(y_test, y_prob, multi_class="ovr", average="macro")

    report = classification_report(
        y_test, y_pred,
        target_names=label_enc.classes_,
        output_dict=True,
    )

    logger.info("Test accuracy=%.4f  F1(macro)=%.4f  AUC=%.4f", acc, f1_macro, roc_auc)
    logger.info("P95 inference latency: %.2f ms", p95_latency_ms)

    sla_ms = config["inference"]["latency_sla_ms"]
    if p95_latency_ms > sla_ms:
        logger.warning("SLA BREACH: p95 latency %.2fms > %dms SLA", p95_latency_ms, sla_ms)
    else:
        logger.info("SLA OK: p95 %.2fms <= %dms", p95_latency_ms, sla_ms)

    # ── 7. Cross-validation (train set only) ─────────────────────────────────
    cv = StratifiedKFold(n_splits=training_cfg["cv_folds"], shuffle=True, random_state=seed)
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=cv, scoring="f1_macro", n_jobs=-1)
    logger.info("CV F1(macro): %.4f ± %.4f", cv_scores.mean(), cv_scores.std())

    # ── 8. MLflow logging ────────────────────────────────────────────────────
    mlflow.set_experiment(config["mlflow"]["experiment_name"])
    with mlflow.start_run(run_name="receipt_classifier_gbm") as run:
        # Parameters
        mlflow.log_params({
            "n_samples":      len(X),
            "test_size":      training_cfg["test_size"],
            "cv_folds":       training_cfg["cv_folds"],
            "random_state":   seed,
            **{f"model_{k}": v for k, v in model_cfg.items()},
        })

        # Metrics
        mlflow.log_metrics({
            "test_accuracy":     acc,
            "test_f1_macro":     f1_macro,
            "test_f1_weighted":  f1_weighted,
            "test_log_loss":     logloss,
            "test_roc_auc_macro": roc_auc,
            "cv_f1_macro_mean":  cv_scores.mean(),
            "cv_f1_macro_std":   cv_scores.std(),
            "train_duration_s":  train_duration_s,
            "p95_latency_ms":    p95_latency_ms,
        })

        # Per-class metrics
        for cls_name in label_enc.classes_:
            if cls_name in report:
                mlflow.log_metrics({
                    f"cls_{cls_name}_precision": report[cls_name]["precision"],
                    f"cls_{cls_name}_recall":    report[cls_name]["recall"],
                    f"cls_{cls_name}_f1":        report[cls_name]["f1-score"],
                })

        # Tags
        mlflow.set_tags({
            "class_imbalanced": str(imbalanced),
            "sla_met":          str(p95_latency_ms <= sla_ms),
            "data_source":      csv_path or "synthetic",
        })

        # Artefacts
        model_dir = Path(paths_cfg["model_dir"])
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "pipeline.joblib"
        dump(pipeline, model_path)
        mlflow.log_artifact(str(model_path))

        label_enc_path = model_dir / "label_encoder.joblib"
        dump(label_enc, label_enc_path)
        mlflow.log_artifact(str(label_enc_path))

        # Classification report JSON
        report_path = model_dir / "classification_report.json"
        with open(report_path, "w") as fh:
            json.dump(report, fh, indent=2)
        mlflow.log_artifact(str(report_path))

        # Log sklearn model (schema + signature)
        mlflow.sklearn.log_model(pipeline, artifact_path="model")

        run_id = run.info.run_id
        logger.info("MLflow run_id=%s", run_id)

    metrics = {
        "accuracy":       round(acc, 4),
        "f1_macro":       round(f1_macro, 4),
        "f1_weighted":    round(f1_weighted, 4),
        "roc_auc_macro":  round(roc_auc, 4),
        "log_loss":       round(logloss, 4),
        "cv_f1_mean":     round(float(cv_scores.mean()), 4),
        "cv_f1_std":      round(float(cv_scores.std()), 4),
        "p95_latency_ms": round(p95_latency_ms, 2),
        "sla_met":        p95_latency_ms <= sla_ms,
        "class_imbalanced": imbalanced,
        "mlflow_run_id":  run_id,
    }
    return metrics


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train receipt classifier")
    parser.add_argument("--csv-path", default=None, help="Path to real receipt CSV")
    parser.add_argument("--n-samples", type=int, default=5_000, help="Synthetic dataset size")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Config YAML path")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = load_config(Path(args.config))
    results = train(csv_path=args.csv_path, n_samples=args.n_samples, config=cfg)
    print("\n=== Training Results ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
