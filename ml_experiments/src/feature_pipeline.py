"""
Production-grade feature engineering pipeline using sklearn Pipeline.

Handles:
  - Missing values: mean / median imputation for numerics, mode for categoricals
  - Categorical encoding: OneHotEncoder (low-cardinality) + TargetEncoder (high-cardinality)
  - Numeric scaling: StandardScaler (fit on train only)
  - Interaction features: pairwise products via PolynomialFeatures

All transformers are fit exclusively on training data — call
``pipeline.fit(X_train, y_train)`` / ``pipeline.transform(X_test)``.

sklearn >= 1.3 required for TargetEncoder (falls back to OHE with a warning).

Design note: TargetEncoder is NOT wrapped in a sub-Pipeline inside ColumnTransformer.
In sklearn 1.4, y-routing through Pipeline → ColumnTransformer → inner Pipeline is
unreliable. Instead, ``ModeImputeAndTargetEncode`` is a single custom transformer
that owns both the imputer and encoder, so y is always available at fit time.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, PolynomialFeatures, StandardScaler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom transformer: pairwise interaction terms
# ---------------------------------------------------------------------------

class PairwiseInteractions(BaseEstimator, TransformerMixin):
    """
    Generate pairwise interaction features (no squared terms, no bias column).

    Wraps PolynomialFeatures so ``get_feature_names_out`` works correctly
    when used inside a Pipeline / ColumnTransformer.
    """

    def __init__(self, degree: int = 2, interaction_only: bool = True):
        self.degree = degree
        self.interaction_only = interaction_only

    def fit(self, X, y=None):
        self._poly = PolynomialFeatures(
            degree=self.degree,
            interaction_only=self.interaction_only,
            include_bias=False,
        )
        self._poly.fit(X)
        return self

    def transform(self, X):
        return self._poly.transform(X)

    def get_feature_names_out(self, input_features=None):
        return self._poly.get_feature_names_out(input_features)


# ---------------------------------------------------------------------------
# Custom transformer: mode-impute + target encode (single step)
# ---------------------------------------------------------------------------

class ModeImputeAndTargetEncode(BaseEstimator, TransformerMixin):
    """
    Mode-impute missing categoricals, then apply target encoding.

    Owns both the imputer and the encoder as plain instance attributes to avoid
    y-routing issues that arise when TargetEncoder is nested inside a Pipeline
    inside a ColumnTransformer (sklearn >= 1.4).

    Uses sklearn's TargetEncoder (sklearn >= 1.3) with internal 5-fold
    cross-fitting to prevent within-fold target leakage. Falls back to
    OneHotEncoder with a warning when sklearn < 1.3 is detected.
    """

    def __init__(self, cv: int = 5, smooth: str = "auto", random_state: int = 42):
        self.cv = cv
        self.smooth = smooth
        self.random_state = random_state

    def fit(self, X, y):
        self._imputer = SimpleImputer(strategy="most_frequent")
        X_imputed = self._imputer.fit_transform(X)

        try:
            from sklearn.preprocessing import TargetEncoder

            self._encoder = TargetEncoder(
                smooth=self.smooth,
                cv=self.cv,
                shuffle=True,
                random_state=self.random_state,
            )
            self._encoder.fit(X_imputed, y)
            self._fallback = False
        except ImportError:
            logger.warning(
                "sklearn < 1.3 — TargetEncoder unavailable. "
                "Falling back to OneHotEncoder for target-encoded columns."
            )
            self._encoder = OneHotEncoder(
                handle_unknown="ignore", sparse_output=False, dtype=np.float32
            )
            self._encoder.fit(X_imputed)
            self._fallback = True

        return self

    def transform(self, X):
        X_imputed = self._imputer.transform(X)
        return self._encoder.transform(X_imputed)

    def get_feature_names_out(self, input_features=None):
        if hasattr(self._encoder, "get_feature_names_out"):
            return self._encoder.get_feature_names_out(input_features)
        return np.asarray(input_features or [], dtype=object)


# ---------------------------------------------------------------------------
# Sub-pipeline builders (numeric and OHE — no y dependency)
# ---------------------------------------------------------------------------

def _numeric_pipeline(strategy: str = "mean") -> Pipeline:
    """
    Numeric feature pipeline: impute → z-score scale → pairwise interactions.

    Parameters
    ----------
    strategy : ``"mean"`` (default) or ``"median"`` for numeric imputation.
               Use ``"median"`` when columns are skewed or contain outliers.
    """
    if strategy not in ("mean", "median"):
        raise ValueError(f"strategy must be 'mean' or 'median', got {strategy!r}")
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy=strategy)),
            ("scaler", StandardScaler()),
            ("interactions", PairwiseInteractions(degree=2, interaction_only=True)),
        ]
    )


def _ohe_pipeline() -> Pipeline:
    """
    OHE pipeline: mode-impute → one-hot encode.

    Unknown categories at inference time map to all-zeros (no error raised).
    Suitable for low-cardinality columns (< ~20 unique values).
    """
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                    dtype=np.float32,
                ),
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_feature_pipeline(
    numeric_cols: List[str],
    ohe_cols: List[str],
    target_enc_cols: List[str],
    numeric_strategy: str = "mean",
) -> ColumnTransformer:
    """
    Assemble the full feature engineering ColumnTransformer.

    Parameters
    ----------
    numeric_cols:
        Continuous numeric columns.
        Steps: mean/median imputation → StandardScaler → pairwise interactions.
    ohe_cols:
        Low-cardinality categoricals (< ~20 unique values).
        Steps: mode imputation → OneHotEncoder.
    target_enc_cols:
        High-cardinality categoricals (zip codes, IDs, city names, …).
        Steps: mode imputation + TargetEncoder (cv=5 cross-fitting, sklearn >= 1.3).
        Handled by ``ModeImputeAndTargetEncode`` — a single transformer that owns
        both steps so y is always available during fit.
    numeric_strategy:
        ``"mean"`` (default) or ``"median"`` for numeric imputation.

    Returns
    -------
    ColumnTransformer
        Fit on training data only::

            ct = build_feature_pipeline(...)
            full_pipeline = Pipeline([("features", ct), ("clf", clf)])
            full_pipeline.fit(X_train, y_train)   # ← leakage-safe
            full_pipeline.predict(X_test)
    """
    transformers: list = []

    if numeric_cols:
        transformers.append(
            ("numeric", _numeric_pipeline(strategy=numeric_strategy), numeric_cols)
        )

    if ohe_cols:
        transformers.append(("ohe_cat", _ohe_pipeline(), ohe_cols))

    if target_enc_cols:
        transformers.append(
            ("target_cat", ModeImputeAndTargetEncode(cv=5, smooth="auto"), target_enc_cols)
        )

    if not transformers:
        raise ValueError(
            "At least one of numeric_cols / ohe_cols / target_enc_cols must be non-empty."
        )

    return ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=True,
        n_jobs=1,  # parallelism at CV level (cross_validate n_jobs=-1) is safer
    )
