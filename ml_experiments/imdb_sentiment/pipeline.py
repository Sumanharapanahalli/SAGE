"""
IMDB Sentiment Classification — end-to-end sklearn Pipeline.

Architecture
------------
TextPreprocessor (stateless)
    ↓
TfidfVectorizer  (fitted on TRAIN only — no leakage)
    ↓
LogisticRegression  (primary model)

Data
----
Loaded from HuggingFace ``datasets`` (imdb).
Stratified 80/20 train/test split.
Supports a ``--subset`` flag to limit to N samples for rapid iteration.

Anti-leakage guarantees
------------------------
1. TfidfVectorizer.fit_transform() is called ONLY on X_train.
2. X_test is transformed with the already-fitted vectorizer (transform only).
3. The TextPreprocessor is stateless, so order does not matter for it.
4. No feature selection or threshold derived from the full dataset.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer

from evaluate import check_class_imbalance, compute_metrics
from logger import ExperimentLogger
from preprocessing import TextPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default hyperparameters — override via build_pipeline()
# ---------------------------------------------------------------------------
DEFAULT_TFIDF_PARAMS: dict[str, Any] = {
    "max_features": 50_000,
    "ngram_range": (1, 2),
    "sublinear_tf": True,       # log(1 + tf) — reduces dominance of very frequent terms
    "min_df": 3,                # ignore tokens appearing in < 3 documents
    "max_df": 0.95,             # ignore tokens in > 95% of documents (near-stopwords)
    "strip_accents": "unicode",
    "analyzer": "word",
}

DEFAULT_LR_PARAMS: dict[str, Any] = {
    "C": 1.0,
    "max_iter": 1000,
    "solver": "lbfgs",
    "class_weight": "balanced",  # handles mild class imbalance automatically
    "random_state": 42,
}

TEST_SIZE = 0.20
RANDOM_STATE = 42


# ---------------------------------------------------------------------------
# Dataset loader
# ---------------------------------------------------------------------------

def load_imdb(subset: int | None = None) -> tuple[list[str], np.ndarray]:
    """
    Load the IMDB dataset via HuggingFace ``datasets``.

    Parameters
    ----------
    subset : if given, randomly sample ``subset`` examples (stratified).

    Returns
    -------
    (texts, labels)  — labels: 0=negative, 1=positive
    """
    logger.info("Loading IMDB dataset…")
    ds = load_dataset("imdb", split="train+test")   # 50 000 total
    texts: list[str] = ds["text"]
    labels: np.ndarray = np.array(ds["label"], dtype=np.int32)

    if subset is not None and subset < len(texts):
        rng = np.random.default_rng(RANDOM_STATE)
        # Stratified down-sample
        pos_idx = np.where(labels == 1)[0]
        neg_idx = np.where(labels == 0)[0]
        half = subset // 2
        chosen = np.concatenate([
            rng.choice(pos_idx, size=half, replace=False),
            rng.choice(neg_idx, size=half, replace=False),
        ])
        rng.shuffle(chosen)
        texts = [texts[i] for i in chosen]
        labels = labels[chosen]
        logger.info("Subset: %d samples", len(texts))
    else:
        logger.info("Full dataset: %d samples", len(texts))

    return texts, labels


# ---------------------------------------------------------------------------
# Pipeline builder
# ---------------------------------------------------------------------------

def build_pipeline(
    tfidf_params: dict[str, Any] | None = None,
    lr_params: dict[str, Any] | None = None,
) -> Pipeline:
    """
    Construct an sklearn Pipeline with:
      TextPreprocessor → TfidfVectorizer → LogisticRegression

    The vectorizer is inside the Pipeline so sklearn handles fit/transform
    discipline correctly: fit_transform on train, transform on test.
    """
    tfidf_params = {**DEFAULT_TFIDF_PARAMS, **(tfidf_params or {})}
    lr_params = {**DEFAULT_LR_PARAMS, **(lr_params or {})}

    return Pipeline(
        steps=[
            ("preprocessor", TextPreprocessor(min_token_len=2)),
            ("tfidf", TfidfVectorizer(**tfidf_params)),
            ("classifier", LogisticRegression(**lr_params)),
        ],
        verbose=False,
    )


# ---------------------------------------------------------------------------
# Training entry point
# ---------------------------------------------------------------------------

def train(
    subset: int | None = None,
    tfidf_params: dict[str, Any] | None = None,
    lr_params: dict[str, Any] | None = None,
    db_path: str | Path = "experiments.db",
) -> dict[str, Any]:
    """
    Full training run with leakage-free split, training, and evaluation.

    Parameters
    ----------
    subset     : limit dataset to N samples (None = full 50 k)
    tfidf_params / lr_params : hyperparameter overrides
    db_path    : path for the SQLite experiment log

    Returns
    -------
    metrics dict (same shape as ``compute_metrics`` output)
    """
    exp_logger = ExperimentLogger(db_path)

    # ---- 1. Load data -------------------------------------------------------
    texts, labels = load_imdb(subset=subset)

    # ---- 2. Check class balance ---------------------------------------------
    is_imbalanced, balance_stats = check_class_imbalance(labels)

    # ---- 3. Stratified split — CRITICAL: stratify=labels --------------------
    #   Stratification preserves the positive/negative ratio in both splits.
    #   All fitting happens on X_train only (enforced by Pipeline).
    X_train, X_test, y_train, y_test = train_test_split(
        texts,
        labels,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=labels,          # ← anti-leakage: ratio preserved, no info from test
    )
    logger.info(
        "Split → train: %d  test: %d  (test_size=%.0f%%)",
        len(X_train), len(X_test), TEST_SIZE * 100,
    )

    dataset_stats = {
        "total": len(texts),
        "train": len(X_train),
        "test": len(X_test),
        "test_size": TEST_SIZE,
        "random_state": RANDOM_STATE,
        **balance_stats,
    }

    # ---- 4. Build pipeline --------------------------------------------------
    merged_tfidf = {**DEFAULT_TFIDF_PARAMS, **(tfidf_params or {})}
    merged_lr = {**DEFAULT_LR_PARAMS, **(lr_params or {})}
    pipe = build_pipeline(merged_tfidf, merged_lr)

    run_params = {
        "tfidf": merged_tfidf,
        "logistic_regression": merged_lr,
        "preprocessing": {"min_token_len": 2},
    }

    run_id = exp_logger.start_run(params=run_params, dataset=dataset_stats)

    # ---- 5. Fit on TRAIN only -----------------------------------------------
    logger.info("Fitting pipeline on training data…")
    pipe.fit(X_train, y_train)
    logger.info(
        "Vocabulary size: %d",
        len(pipe.named_steps["tfidf"].vocabulary_),
    )

    # ---- 6. Predict on TEST — transform only (no re-fit) --------------------
    logger.info("Evaluating on held-out test set…")
    y_pred = pipe.predict(X_test)
    y_prob = pipe.predict_proba(X_test)[:, 1]   # probability of class 1 (positive)

    # ---- 7. Compute metrics -------------------------------------------------
    metrics = compute_metrics(
        y_true=y_test,
        y_pred=y_pred,
        y_prob=y_prob,
        label_names=["negative", "positive"],
    )
    metrics["leakage_risk"] = False          # documented: split → fit → transform order
    metrics["class_imbalance"] = is_imbalanced

    exp_logger.end_run(run_id, metrics=metrics)
    exp_logger.close()

    return metrics
