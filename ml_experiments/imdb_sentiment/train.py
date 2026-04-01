"""
CLI entry point.

Usage
-----
# Full 50k dataset
python train.py

# Quick smoke-test on 2000 samples
python train.py --subset 2000

# Hyperparameter override
python train.py --subset 5000 --max-features 30000 --C 0.5
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from pipeline import train

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IMDB sentiment classifier")
    p.add_argument(
        "--subset",
        type=int,
        default=None,
        metavar="N",
        help="Limit dataset to N samples for faster iteration (default: full 50k)",
    )
    p.add_argument(
        "--max-features",
        type=int,
        default=50_000,
        dest="max_features",
        help="TF-IDF vocabulary size (default: 50000)",
    )
    p.add_argument(
        "--ngram-max",
        type=int,
        default=2,
        dest="ngram_max",
        help="Max ngram size for TF-IDF (default: 2 → unigrams + bigrams)",
    )
    p.add_argument(
        "--C",
        type=float,
        default=1.0,
        dest="C",
        help="Logistic Regression regularization strength (default: 1.0)",
    )
    p.add_argument(
        "--db",
        type=str,
        default="experiments.db",
        help="Path to SQLite experiment log (default: experiments.db)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    tfidf_overrides = {
        "max_features": args.max_features,
        "ngram_range": (1, args.ngram_max),
    }
    lr_overrides = {"C": args.C}

    logger.info("Starting training run — subset=%s  max_features=%d  C=%.3f",
                args.subset, args.max_features, args.C)

    metrics = train(
        subset=args.subset,
        tfidf_params=tfidf_overrides,
        lr_params=lr_overrides,
        db_path=args.db,
    )

    # Print a clean summary to stdout (machine-readable JSON)
    summary = {
        "accuracy": metrics["accuracy"],
        "f1_macro": metrics["f1_macro"],
        "f1_binary": metrics["f1_binary"],
        "roc_auc": metrics.get("roc_auc"),
        "mcc": metrics["mcc"],
        "leakage_risk": metrics["leakage_risk"],
        "class_imbalance": metrics["class_imbalance"],
    }
    print(json.dumps(summary, indent=2))

    # Non-zero exit if accuracy is suspiciously low (sanity guard for CI)
    if metrics["accuracy"] < 0.70:
        logger.error("Accuracy %.4f is below the 0.70 sanity floor.", metrics["accuracy"])
        sys.exit(1)


if __name__ == "__main__":
    main()
