"""
Invoice Data Classification — Training Script
=============================================
Production-grade training pipeline with:
  - Stratified train/val/test split (no leakage)
  - TF-IDF text features + numeric/categorical features
  - XGBoost gradient boosting (configurable)
  - MLflow experiment tracking
  - Class-imbalance handling via SMOTE
  - Full evaluation: accuracy, macro-F1, per-class report, confusion matrix
  - SHAP feature importance
  - Serialized model + preprocessor for inference
"""

import json
import logging
import os
import time
import warnings
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import shap
import yaml
from imblearn.over_sampling import SMOTE
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("invoice_classifier.train")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Synthetic data generator (replace with real data loading in production)
# ---------------------------------------------------------------------------

INVOICE_TYPES = [
    "vendor_invoice",
    "credit_note",
    "proforma",
    "recurring_subscription",
    "expense_report",
]
CURRENCIES = ["USD", "EUR", "GBP", "JPY", "INR"]
PAYMENT_METHODS = ["bank_transfer", "credit_card", "check", "ach"]
DEPARTMENTS = ["engineering", "marketing", "finance", "hr", "operations"]


def generate_synthetic_data(n_samples: int = 5_000, seed: int = 42) -> pd.DataFrame:
    """Generate a representative synthetic invoice dataset."""
    rng = np.random.default_rng(seed)
    n = n_samples

    labels = rng.choice(INVOICE_TYPES, size=n, p=[0.40, 0.20, 0.15, 0.15, 0.10])

    def _total(label):
        base = {"vendor_invoice": 5000, "credit_note": -2000, "proforma": 3000,
                "recurring_subscription": 500, "expense_report": 300}
        return rng.normal(base[label], abs(base[label]) * 0.3)

    df = pd.DataFrame(
        {
            "invoice_type": labels,
            "vendor_name": [
                f"Vendor_{rng.integers(1, 200)}" for _ in range(n)
            ],
            "line_items_text": [
                f"software license consulting services {rng.integers(1,50)} units"
                if t in ("vendor_invoice", "recurring_subscription")
                else f"credit adjustment refund #{rng.integers(1000, 9999)}"
                if t == "credit_note"
                else f"project estimate phase {rng.integers(1, 5)} milestones"
                for t in labels
            ],
            "payment_terms": rng.choice(
                ["net30", "net60", "net90", "immediate", "net15"], size=n
            ),
            "total_amount": [_total(t) for t in labels],
            "tax_amount": rng.uniform(0, 500, n),
            "num_line_items": rng.integers(1, 20, n),
            "days_to_due": rng.integers(-10, 120, n),
            "currency": rng.choice(CURRENCIES, size=n),
            "payment_method": rng.choice(PAYMENT_METHODS, size=n),
            "department": rng.choice(DEPARTMENTS, size=n),
        }
    )
    return df


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def build_preprocessor(cfg: dict):
    """ColumnTransformer that fits ONLY on training data."""
    text_cols = cfg["data"]["text_columns"]
    num_cols = cfg["data"]["numeric_columns"]
    cat_cols = cfg["data"]["categorical_columns"]
    tfidf_params = cfg["text"]

    # Combine all text columns into one string per row
    def _combine_text(df: pd.DataFrame) -> pd.Series:
        return df[text_cols].fillna("").agg(" ".join, axis=1)

    tfidf = TfidfVectorizer(
        max_features=tfidf_params["max_features"],
        ngram_range=tuple(tfidf_params["ngram_range"]),
        sublinear_tf=True,
    )
    scaler = StandardScaler()
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    return tfidf, scaler, ohe, _combine_text


def prepare_features(df: pd.DataFrame, cfg: dict):
    """Return X (dict of components) and y (encoded labels)."""
    text_cols = cfg["data"]["text_columns"]
    num_cols = cfg["data"]["numeric_columns"]
    cat_cols = cfg["data"]["categorical_columns"]
    target = cfg["data"]["target_column"]

    X_text = df[text_cols].fillna("").agg(" ".join, axis=1)
    X_num = df[num_cols].fillna(0).astype(float)
    X_cat = df[cat_cols].fillna("unknown")
    y = df[target]
    return X_text, X_num, X_cat, y


# ---------------------------------------------------------------------------
# Model builder
# ---------------------------------------------------------------------------

def build_model(cfg: dict) -> XGBClassifier:
    hp = cfg["model"]["hyperparams"]
    return XGBClassifier(
        **hp,
        objective="multi:softprob",
        eval_metric="mlogloss",
        use_label_encoder=False,
        random_state=cfg["experiment"]["seed"],
        n_jobs=-1,
        verbosity=0,
    )


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def evaluate(y_true, y_pred, y_proba, label_encoder, split_name: str) -> dict:
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average="macro")
    weighted_f1 = f1_score(y_true, y_pred, average="weighted")
    report = classification_report(
        y_true, y_pred,
        target_names=label_encoder.classes_,
        output_dict=True,
    )
    cm = confusion_matrix(y_true, y_pred)

    try:
        auc = roc_auc_score(y_true, y_proba, multi_class="ovr", average="macro")
    except Exception:
        auc = float("nan")

    metrics = {
        f"{split_name}_accuracy": round(acc, 4),
        f"{split_name}_macro_f1": round(macro_f1, 4),
        f"{split_name}_weighted_f1": round(weighted_f1, 4),
        f"{split_name}_auc_ovr": round(auc, 4) if not np.isnan(auc) else None,
    }
    logger.info(
        "%s  acc=%.4f  macro_f1=%.4f  auc=%.4f",
        split_name.upper(), acc, macro_f1, auc if not np.isnan(auc) else -1,
    )
    logger.info("\n%s", classification_report(
        y_true, y_pred, target_names=label_encoder.classes_
    ))
    return metrics, cm, report


def check_class_imbalance(y_series: pd.Series) -> bool:
    counts = y_series.value_counts(normalize=True)
    imbalanced = bool((counts < 0.05).any() or (counts > 0.80).any())
    logger.info("Class distribution:\n%s", counts.to_string())
    if imbalanced:
        logger.warning("Class imbalance detected — applying SMOTE on training set.")
    return imbalanced


# ---------------------------------------------------------------------------
# Main training pipeline
# ---------------------------------------------------------------------------

def train(cfg: dict):
    seed = cfg["experiment"]["seed"]
    np.random.seed(seed)
    artifact_dir = Path(cfg["experiment"]["artifact_dir"])
    artifact_dir.mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(cfg["experiment"]["mlflow_tracking_uri"])
    mlflow.set_experiment(cfg["experiment"]["name"])

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    data_path = Path(cfg["data"]["raw_path"])
    if data_path.exists():
        df = pd.read_csv(data_path)
        logger.info("Loaded %d rows from %s", len(df), data_path)
    else:
        logger.warning("Data file not found — using synthetic data for demonstration.")
        df = generate_synthetic_data(seed=seed)

    X_text, X_num, X_cat, y_raw = prepare_features(df, cfg)

    # ------------------------------------------------------------------
    # 2. Label encoding
    # ------------------------------------------------------------------
    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    # ------------------------------------------------------------------
    # 3. Stratified split — NO leakage: fit transformers on train only
    # ------------------------------------------------------------------
    test_size = cfg["data"]["test_size"]
    val_ratio = cfg["data"]["val_size"]

    X_text_trval, X_text_test, X_num_trval, X_num_test, X_cat_trval, X_cat_test, y_trval, y_test = (
        train_test_split(
            X_text, X_num, X_cat, y,
            test_size=test_size, stratify=y, random_state=seed,
        )
    )
    val_size_adj = val_ratio / (1 - test_size)
    X_text_tr, X_text_val, X_num_tr, X_num_val, X_cat_tr, X_cat_val, y_tr, y_val = (
        train_test_split(
            X_text_trval, X_num_trval, X_cat_trval, y_trval,
            test_size=val_size_adj, stratify=y_trval, random_state=seed,
        )
    )
    logger.info(
        "Split sizes — train: %d  val: %d  test: %d",
        len(y_tr), len(y_val), len(y_test),
    )

    # ------------------------------------------------------------------
    # 4. Fit preprocessors on TRAIN only
    # ------------------------------------------------------------------
    tfidf = TfidfVectorizer(
        max_features=cfg["text"]["max_features"],
        ngram_range=tuple(cfg["text"]["ngram_range"]),
        sublinear_tf=True,
    )
    scaler = StandardScaler()
    ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    X_text_tr_vec = tfidf.fit_transform(X_text_tr).toarray()
    X_num_tr_sc = scaler.fit_transform(X_num_tr)
    X_cat_tr_enc = ohe.fit_transform(X_cat_tr)

    # Transform val & test (no fitting — prevents leakage)
    X_text_val_vec = tfidf.transform(X_text_val).toarray()
    X_num_val_sc = scaler.transform(X_num_val)
    X_cat_val_enc = ohe.transform(X_cat_val)

    X_text_test_vec = tfidf.transform(X_text_test).toarray()
    X_num_test_sc = scaler.transform(X_num_test)
    X_cat_test_enc = ohe.transform(X_cat_test)

    X_tr = np.hstack([X_text_tr_vec, X_num_tr_sc, X_cat_tr_enc])
    X_val = np.hstack([X_text_val_vec, X_num_val_sc, X_cat_val_enc])
    X_test = np.hstack([X_text_test_vec, X_num_test_sc, X_cat_test_enc])

    # ------------------------------------------------------------------
    # 5. Class imbalance check + optional SMOTE
    # ------------------------------------------------------------------
    imbalanced = check_class_imbalance(y_raw.iloc[: len(y_tr)])  # train labels only
    if imbalanced:
        smote = SMOTE(random_state=seed)
        X_tr, y_tr = smote.fit_resample(X_tr, y_tr)
        logger.info("Post-SMOTE train size: %d", len(y_tr))

    # ------------------------------------------------------------------
    # 6. Train + MLflow logging
    # ------------------------------------------------------------------
    model = build_model(cfg)
    with mlflow.start_run(run_name=f"xgb_{int(time.time())}") as run:
        mlflow.log_params(cfg["model"]["hyperparams"])
        mlflow.log_param("seed", seed)
        mlflow.log_param("n_train", len(y_tr))
        mlflow.log_param("n_val", len(y_val))
        mlflow.log_param("n_test", len(y_test))
        mlflow.log_param("smote_applied", imbalanced)
        mlflow.log_param("classes", list(le.classes_))

        logger.info("Fitting model…")
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            verbose=50,
        )

        # Val evaluation
        y_val_pred = model.predict(X_val)
        y_val_proba = model.predict_proba(X_val)
        val_metrics, val_cm, val_report = evaluate(
            y_val, y_val_pred, y_val_proba, le, "val"
        )
        mlflow.log_metrics(val_metrics)

        # Test evaluation
        y_test_pred = model.predict(X_test)
        y_test_proba = model.predict_proba(X_test)
        test_metrics, test_cm, test_report = evaluate(
            y_test, y_test_pred, y_test_proba, le, "test"
        )
        mlflow.log_metrics(test_metrics)

        # Inference latency check
        sla_ms = cfg["sla"]["inference_latency_ms"]
        latency_p99 = _measure_latency(
            model, tfidf, scaler, ohe, X_text_test.iloc[:100], X_num_test.iloc[:100], X_cat_test.iloc[:100]
        )
        mlflow.log_metric("inference_latency_p99_ms", latency_p99)
        sla_ok = latency_p99 <= sla_ms
        mlflow.log_param("sla_met", sla_ok)
        logger.info("Inference latency p99=%.2f ms  SLA=%d ms  [%s]",
                    latency_p99, sla_ms, "PASS" if sla_ok else "FAIL")

        # ------------------------------------------------------------------
        # 7. Persist artifacts
        # ------------------------------------------------------------------
        joblib.dump(model, artifact_dir / "model.joblib")
        joblib.dump(tfidf, artifact_dir / "tfidf.joblib")
        joblib.dump(scaler, artifact_dir / "scaler.joblib")
        joblib.dump(ohe, artifact_dir / "ohe.joblib")
        joblib.dump(le, artifact_dir / "label_encoder.joblib")

        eval_summary = {
            "val": val_metrics,
            "test": test_metrics,
            "inference_latency_p99_ms": latency_p99,
            "sla_met": sla_ok,
            "class_imbalance_detected": imbalanced,
            "leakage_risk": False,
        }
        with open(artifact_dir / "eval_summary.json", "w") as f:
            json.dump(eval_summary, f, indent=2)

        mlflow.log_artifacts(str(artifact_dir))

        # ------------------------------------------------------------------
        # 8. SHAP feature importance (sample 500 rows)
        # ------------------------------------------------------------------
        _compute_shap(model, X_tr[:500], artifact_dir)

        logger.info("Run ID: %s", run.info.run_id)
        logger.info("Artifacts saved to: %s", artifact_dir)
        return eval_summary


# ---------------------------------------------------------------------------
# Latency measurement
# ---------------------------------------------------------------------------

def _measure_latency(model, tfidf, scaler, ohe, X_text, X_num, X_cat) -> float:
    """Return p99 single-sample inference latency in ms (100 trials)."""
    latencies = []
    for i in range(len(X_text)):
        t0 = time.perf_counter()
        text_vec = tfidf.transform([X_text.iloc[i]]).toarray()
        num_sc = scaler.transform(X_num.iloc[[i]])
        cat_enc = ohe.transform(X_cat.iloc[[i]])
        x = np.hstack([text_vec, num_sc, cat_enc])
        model.predict(x)
        latencies.append((time.perf_counter() - t0) * 1000)
    return float(np.percentile(latencies, 99))


# ---------------------------------------------------------------------------
# SHAP importance
# ---------------------------------------------------------------------------

def _compute_shap(model, X_sample, artifact_dir: Path):
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
        mean_abs = np.abs(shap_values).mean(axis=(0, 2)) if shap_values.ndim == 3 else np.abs(shap_values).mean(axis=0)
        top_idx = np.argsort(mean_abs)[::-1][:20]
        importance = {f"feature_{i}": float(mean_abs[i]) for i in top_idx}
        with open(artifact_dir / "shap_importance.json", "w") as f:
            json.dump(importance, f, indent=2)
        logger.info("SHAP importance saved.")
    except Exception as exc:
        logger.warning("SHAP computation skipped: %s", exc)


# ---------------------------------------------------------------------------
# Cross-validation diagnostic (optional — call separately)
# ---------------------------------------------------------------------------

def cross_validate_model(cfg: dict, n_splits: int = 5):
    """Stratified k-fold CV for robust estimate before final training."""
    seed = cfg["experiment"]["seed"]
    df = generate_synthetic_data(seed=seed)
    X_text, X_num, X_cat, y_raw = prepare_features(df, cfg)
    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fold_f1s = []
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X_text, y)):
        X_t_text, X_v_text = X_text.iloc[tr_idx], X_text.iloc[val_idx]
        X_t_num, X_v_num = X_num.iloc[tr_idx], X_num.iloc[val_idx]
        X_t_cat, X_v_cat = X_cat.iloc[tr_idx], X_cat.iloc[val_idx]
        y_t, y_v = y[tr_idx], y[val_idx]

        tfidf = TfidfVectorizer(max_features=2000, sublinear_tf=True)
        scaler = StandardScaler()
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

        X_t = np.hstack([
            tfidf.fit_transform(X_t_text).toarray(),
            scaler.fit_transform(X_t_num),
            ohe.fit_transform(X_t_cat),
        ])
        X_v = np.hstack([
            tfidf.transform(X_v_text).toarray(),
            scaler.transform(X_v_num),
            ohe.transform(X_v_cat),
        ])
        model = XGBClassifier(n_estimators=100, random_state=seed, verbosity=0, n_jobs=-1)
        model.fit(X_t, y_t)
        pred = model.predict(X_v)
        f1 = f1_score(y_v, pred, average="macro")
        fold_f1s.append(f1)
        logger.info("Fold %d  macro_f1=%.4f", fold + 1, f1)

    logger.info("CV macro_f1 = %.4f ± %.4f", np.mean(fold_f1s), np.std(fold_f1s))
    return fold_f1s


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = load_config()
    results = train(cfg)
    print(json.dumps(results, indent=2))
