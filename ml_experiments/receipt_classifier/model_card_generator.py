"""
receipt_classifier/model_card_generator.py
──────────────────────────────────────────
Generates a model card YAML from the evaluation report produced by evaluate.py.

The model card follows the Google Model Card specification (condensed):
  https://modelcards.withgoogle.com/about

Usage
─────
    python model_card_generator.py                          # uses models/evaluation_report.json
    python model_card_generator.py --report models/evaluation_report.json
    python model_card_generator.py --report models/evaluation_report.json --out model_card.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_report(report_path: Path) -> Dict[str, Any]:
    with open(report_path) as fh:
        return json.load(fh)


def _bias_flags(bias_summary: Dict) -> list[str]:
    """Return human-readable bias flags, or ['none detected'] if clean."""
    flags = []
    for col, summary in bias_summary.items():
        if summary.get("bias_flag"):
            flags.append(
                f"{col}: demographic_parity_gap={summary['demographic_parity_gap']:.3f}, "
                f"accuracy_gap={summary['accuracy_gap']:.3f}"
            )
    return flags or ["none detected"]


def _format_per_class(per_class: Dict) -> list[Dict]:
    return [
        {
            "class":     cls,
            "precision": m["precision"],
            "recall":    m["recall"],
            "f1":        m["f1"],
            "support":   m["support"],
        }
        for cls, m in per_class.items()
    ]


# ── Generator ──────────────────────────────────────────────────────────────────

def generate_model_card(
    report: Dict[str, Any],
    out_path: Path,
) -> Dict[str, Any]:
    """
    Build a model card dict from the evaluation report and write it to out_path.

    Returns the card dict for downstream use.
    """
    agg = report.get("aggregate_metrics", {})
    latency = report.get("latency_benchmark", {})
    bias = report.get("bias_evaluation", {})
    per_class = report.get("per_class_metrics", {})
    data_checks = report.get("data_checks", {})

    card: Dict[str, Any] = {
        "model_details": {
            "name": "receipt_classifier",
            "version": "1.0.0",
            "type": "GradientBoostingClassifier (sklearn)",
            "task": "multi-class receipt categorisation",
            "classes": list(per_class.keys()),
            "date_generated": str(date.today()),
            "python_version": platform.python_version(),
            "framework": f"scikit-learn {_sklearn_version()}",
            "description": (
                "Classifies expense receipts into 8 spend categories "
                "(food_dining, travel_transport, accommodation, office_supplies, "
                "entertainment, utilities, healthcare, retail_shopping) "
                "from structured transaction features."
            ),
        },
        "intended_use": {
            "primary_use": "Automated expense categorisation for corporate T&E workflows",
            "intended_users": ["Finance operations teams", "Expense management SaaS platforms"],
            "out_of_scope": [
                "Fraud detection",
                "PII extraction",
                "Receipts outside the 8 supported categories",
            ],
        },
        "training_data": {
            "source": "Synthetic receipt dataset (see data.py) — replace with real data in production",
            "features": {
                "numeric": [
                    "amount_usd", "item_count", "discount_pct", "tip_pct",
                    "hour_of_day", "day_of_week", "is_weekend",
                    "days_since_last_purchase", "merchant_avg_ticket",
                    "merchant_transaction_count",
                ],
                "categorical": ["payment_method", "merchant_type", "currency"],
            },
            "split": "80 % train / 20 % test — stratified by class label",
            "leakage_prevention": (
                "StandardScaler and OrdinalEncoder fitted exclusively on the "
                "training fold; test fold is transform-only."
            ),
        },
        "evaluation": {
            "dataset": "Held-out stratified 20 % test split (same seed as training)",
            "aggregate_metrics": {
                "accuracy":         agg.get("accuracy"),
                "f1_macro":         agg.get("f1_macro"),
                "f1_weighted":      agg.get("f1_weighted"),
                "precision_macro":  agg.get("precision_macro"),
                "recall_macro":     agg.get("recall_macro"),
                "roc_auc_macro":    agg.get("roc_auc_macro"),
                "log_loss":         agg.get("log_loss"),
            },
            "per_class_metrics": _format_per_class(per_class),
            "cross_validation": "5-fold StratifiedKFold on training set (F1 macro)",
        },
        "performance_requirements": {
            "latency_sla_ms": latency.get("sla_ms"),
            "sla_met":        latency.get("sla_met"),
            "measured_latency": {
                "p50_ms": latency.get("p50_ms"),
                "p95_ms": latency.get("p95_ms"),
                "p99_ms": latency.get("p99_ms"),
                "mean_ms": latency.get("mean_ms"),
            },
            "note": "Single-sample p95 latency, 300 measurements after 10 warm-up calls.",
        },
        "fairness_and_bias": {
            "sensitive_attributes": ["payment_method", "currency"],
            "methodology": (
                "Demographic parity gap and accuracy gap computed per sensitive "
                "attribute group. Bias flagged when dp_gap > 0.10 or acc_gap > 0.05."
            ),
            "findings": _bias_flags(bias.get("summary", {})),
            "per_group_breakdown": bias.get("groups", {}),
            "limitations": (
                "Bias evaluation relies on synthetic data distributions. "
                "Re-run with production data before deployment."
            ),
        },
        "ethical_considerations": [
            "Model trained on synthetic data — validate against real receipt distributions before production use.",
            "Currency and payment method are proxy-sensitive attributes; monitor for proxy discrimination.",
            "Healthcare receipts carry implied health information — handle with appropriate data governance.",
        ],
        "limitations": [
            "Merchant type and currency features may not generalise to unseen values (OrdinalEncoder handles via unknown_value=-1).",
            "Soft-labels (probabilities) should be calibrated for high-stakes downstream decisions.",
            "Model does not handle multi-category receipts (e.g. a single receipt spanning food + retail).",
        ],
        "data_checks": {
            "leakage_risk":    data_checks.get("leakage_risk", False),
            "class_imbalance": data_checks.get("class_imbalance", False),
            "test_samples":    data_checks.get("test_samples"),
        },
        "reproducibility": {
            "random_seed": 42,
            "seed_propagation": ["random.seed", "numpy.random.seed", "PYTHONHASHSEED"],
            "deterministic": True,
        },
        "artefacts": {
            "pipeline":          "models/pipeline.joblib",
            "label_encoder":     "models/label_encoder.joblib",
            "classification_report": "models/classification_report.json",
            "evaluation_report": "models/evaluation_report.json",
            "model_card":        str(out_path),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as fh:
        yaml.dump(card, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info("Model card written to %s", out_path)
    return card


def _sklearn_version() -> str:
    try:
        import sklearn
        return sklearn.__version__
    except ImportError:
        return "unknown"


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate receipt classifier model card")
    parser.add_argument(
        "--report",
        default="models/evaluation_report.json",
        help="Path to evaluation_report.json produced by evaluate.py",
    )
    parser.add_argument(
        "--out",
        default="models/model_card.yaml",
        help="Output path for the model card YAML",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    args = parse_args()
    report_path = Path(args.report)

    if not report_path.exists():
        logger.error(
            "Evaluation report not found at %s. Run evaluate.py first.", report_path
        )
        sys.exit(1)

    report = _load_report(report_path)
    card = generate_model_card(report, out_path=Path(args.out))

    print("\n=== Model Card Summary ===")
    print(f"  Model   : {card['model_details']['name']} v{card['model_details']['version']}")
    print(f"  Accuracy: {card['evaluation']['aggregate_metrics']['accuracy']}")
    print(f"  F1 macro: {card['evaluation']['aggregate_metrics']['f1_macro']}")
    print(f"  SLA met : {card['performance_requirements']['sla_met']}")
    print(f"  Bias    : {card['fairness_and_bias']['findings']}")
    print(f"\nFull card → {args.out}")
