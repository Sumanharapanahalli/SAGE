"""
receipt_classifier/data.py
──────────────────────────
Synthetic receipt dataset generator + feature schema.

Real usage: replace `generate_synthetic_data()` with your ETL loader.
Feature contract (column names / dtypes) is enforced here so train.py
and inference.py share a single source of truth.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Label space ────────────────────────────────────────────────────────────────
RECEIPT_CATEGORIES: List[str] = [
    "food_dining",
    "travel_transport",
    "accommodation",
    "office_supplies",
    "entertainment",
    "utilities",
    "healthcare",
    "retail_shopping",
]

# ── Feature schema ─────────────────────────────────────────────────────────────
NUMERIC_FEATURES: List[str] = [
    "amount_usd",
    "item_count",
    "discount_pct",
    "tip_pct",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "days_since_last_purchase",
    "merchant_avg_ticket",
    "merchant_transaction_count",
]

CATEGORICAL_FEATURES: List[str] = [
    "payment_method",   # cash | credit | debit | mobile
    "merchant_type",    # restaurant | airline | hotel | ...
    "currency",         # USD | EUR | GBP | ...
]

TARGET_COLUMN = "category"
SENSITIVE_COLUMNS: List[str] = ["payment_method", "currency"]  # for bias eval


@dataclass
class ReceiptDataset:
    X: pd.DataFrame
    y: pd.Series
    feature_names: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.feature_names = list(self.X.columns)
        assert len(self.X) == len(self.y), "X / y length mismatch"


# ── Synthetic generator ────────────────────────────────────────────────────────

def generate_synthetic_data(
    n_samples: int = 5_000,
    random_state: int = 42,
    class_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Generate a reproducible synthetic receipt dataset.

    Parameters
    ----------
    n_samples     : total rows
    random_state  : numpy seed — guarantees reproducibility
    class_weights : optional dict mapping category → relative frequency.
                    Defaults to a mildly imbalanced distribution
                    (food_dining ~30 %, healthcare ~5 %).
    """
    rng = np.random.default_rng(random_state)

    if class_weights is None:
        class_weights = {
            "food_dining":       0.28,
            "travel_transport":  0.15,
            "accommodation":     0.10,
            "office_supplies":   0.12,
            "entertainment":     0.10,
            "utilities":         0.10,
            "healthcare":        0.05,
            "retail_shopping":   0.10,
        }

    # Normalise weights
    total = sum(class_weights.values())
    probs = [class_weights[c] / total for c in RECEIPT_CATEGORIES]
    categories = rng.choice(RECEIPT_CATEGORIES, size=n_samples, p=probs)

    # Per-category amount distributions (mean, std) in USD
    amount_params = {
        "food_dining":       (25,  20),
        "travel_transport":  (120, 80),
        "accommodation":     (180, 120),
        "office_supplies":   (55,  40),
        "entertainment":     (60,  50),
        "utilities":         (90,  30),
        "healthcare":        (150, 100),
        "retail_shopping":   (70,  60),
    }

    amounts = np.array([
        max(1.0, rng.normal(*amount_params[c]))
        for c in categories
    ])

    item_count = rng.integers(1, 15, size=n_samples)
    discount_pct = rng.uniform(0, 0.30, size=n_samples)
    tip_pct = np.where(
        np.isin(categories, ["food_dining", "accommodation"]),
        rng.uniform(0.10, 0.25, size=n_samples),
        0.0,
    )
    hour_of_day = rng.integers(0, 24, size=n_samples)
    day_of_week = rng.integers(0, 7, size=n_samples)
    is_weekend = (day_of_week >= 5).astype(int)
    days_since_last = rng.integers(0, 60, size=n_samples)

    merchant_avg_ticket = amounts * rng.uniform(0.8, 1.2, size=n_samples)
    merchant_tx_count = rng.integers(50, 5_000, size=n_samples)

    payment_methods = rng.choice(
        ["credit", "debit", "cash", "mobile"], size=n_samples, p=[0.45, 0.30, 0.15, 0.10]
    )

    merchant_type_map = {
        "food_dining":       ["restaurant", "cafe", "fast_food"],
        "travel_transport":  ["airline", "taxi", "car_rental"],
        "accommodation":     ["hotel", "airbnb", "hostel"],
        "office_supplies":   ["stationery", "electronics", "printing"],
        "entertainment":     ["cinema", "theater", "streaming"],
        "utilities":         ["electricity", "water", "telecom"],
        "healthcare":        ["pharmacy", "clinic", "hospital"],
        "retail_shopping":   ["clothing", "grocery", "department_store"],
    }
    merchant_types = np.array([
        rng.choice(merchant_type_map[c]) for c in categories
    ])

    currencies = rng.choice(
        ["USD", "EUR", "GBP", "CAD"], size=n_samples, p=[0.60, 0.20, 0.12, 0.08]
    )

    df = pd.DataFrame({
        "amount_usd":                amounts.round(2),
        "item_count":                item_count,
        "discount_pct":              discount_pct.round(4),
        "tip_pct":                   tip_pct.round(4),
        "hour_of_day":               hour_of_day,
        "day_of_week":               day_of_week,
        "is_weekend":                is_weekend,
        "days_since_last_purchase":  days_since_last,
        "merchant_avg_ticket":       merchant_avg_ticket.round(2),
        "merchant_transaction_count": merchant_tx_count,
        "payment_method":            payment_methods,
        "merchant_type":             merchant_types,
        "currency":                  currencies,
        TARGET_COLUMN:               categories,
    })

    logger.info(
        "Generated %d synthetic receipts | class distribution:\n%s",
        n_samples,
        df[TARGET_COLUMN].value_counts().to_string(),
    )
    return df


def load_dataset(
    csv_path: str | None = None,
    n_samples: int = 5_000,
    random_state: int = 42,
) -> ReceiptDataset:
    """
    Load receipts from CSV or fall back to synthetic data.

    Parameters
    ----------
    csv_path     : path to a CSV with columns matching the feature schema.
                   If None, synthetic data is generated.
    n_samples    : used only for synthetic generation.
    random_state : seed for synthetic generation.
    """
    if csv_path is not None:
        logger.info("Loading receipt data from %s", csv_path)
        df = pd.read_csv(csv_path)
        required = set(NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN])
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")
    else:
        logger.info("No CSV provided — generating synthetic data (n=%d)", n_samples)
        df = generate_synthetic_data(n_samples=n_samples, random_state=random_state)

    X = df[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = df[TARGET_COLUMN]
    return ReceiptDataset(X=X, y=y)
