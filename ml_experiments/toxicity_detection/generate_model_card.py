"""
Model Card Generator — Toxicity Detection
==========================================
Reads evaluation results, bias report, and config to produce a
structured model_card.yaml following Hugging Face Model Card spec.

Usage
-----
    python generate_model_card.py --config config.yaml \
        --eval_results artifacts/toxicity_model/evaluation_results.json \
        --bias_report  artifacts/bias_report.json \
        --latency_report artifacts/latency_report.json
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
)
logger = logging.getLogger("toxicity.model_card")


def _load_json(path: str) -> Optional[Dict]:
    p = Path(path)
    if p.exists():
        with open(p) as fh:
            return json.load(fh)
    return None


def generate_model_card(
    cfg: Dict[str, Any],
    eval_results: Optional[Dict],
    bias_report: Optional[Dict],
    latency_report: Optional[Dict],
) -> Dict[str, Any]:
    test_metrics = eval_results.get("test", {}) if eval_results else {}
    overall_bias = bias_report.get("overall", {}) if bias_report else {}
    fairness_violations = bias_report.get("violations", []) if bias_report else []

    card: Dict[str, Any] = {
        "model_details": {
            "name": "toxicity-bert-baseline",
            "version": "1.0.0",
            "date": str(date.today()),
            "type": "text-classification",
            "architecture": "DistilBERT (fine-tuned)",
            "pretrained_base": cfg["model"]["pretrained_name"],
            "num_labels": cfg["model"]["num_labels"],
            "max_sequence_length": cfg["model"]["max_length"],
            "framework": "transformers (HuggingFace)",
            "license": "Apache 2.0",
        },

        "intended_use": {
            "primary_uses": [
                "Detecting toxic language in user-generated text",
                "Content moderation pipeline pre-filtering",
                "Research on online toxicity patterns",
            ],
            "out_of_scope": [
                "Legal or judicial decision-making",
                "Medical / clinical contexts",
                "Real-time high-stakes enforcement without human review",
                "Languages other than English (fine-tuned on English corpus)",
            ],
            "users": ["Platform trust & safety teams", "Researchers", "NLP engineers"],
        },

        "training_data": {
            "dataset": cfg["data"]["dataset_name"],
            "description": (
                "Jigsaw Toxic Comment Classification Dataset: Wikipedia talk page comments "
                "labelled for toxic, severe_toxic, obscene, threat, insult, identity_hate."
            ),
            "split_strategy": "Stratified train/val/test split (prevents class leakage)",
            "test_size": cfg["data"]["test_size"],
            "val_size": cfg["data"]["val_size"],
            "preprocessing": "Tokenization with pre-trained DistilBERT tokenizer (vocab fixed, not re-fitted)",
            "class_balance_note": "Dataset is imbalanced (~10% toxic). Stratification used to preserve ratio.",
        },

        "training_config": {
            "epochs": cfg["training"]["epochs"],
            "batch_size": cfg["training"]["batch_size"],
            "learning_rate": cfg["training"]["learning_rate"],
            "weight_decay": cfg["training"]["weight_decay"],
            "warmup_ratio": cfg["training"]["warmup_ratio"],
            "fp16": cfg["training"]["fp16"],
            "early_stopping_patience": cfg["training"]["early_stopping_patience"],
            "seed": cfg["training"]["seed"],
            "reproducibility": "Fixed seed via transformers.set_seed + torch.manual_seed",
        },

        "evaluation_metrics": {
            "test_set": {
                "accuracy": test_metrics.get("accuracy"),
                "f1": test_metrics.get("f1"),
                "precision": test_metrics.get("precision"),
                "recall": test_metrics.get("recall"),
                "roc_auc": test_metrics.get("roc_auc"),
            },
            "primary_metric": "F1-score (chosen for imbalanced binary classification)",
            "threshold": 0.5,
            "metric_rationale": (
                "F1 balances precision and recall — important when false negatives "
                "(missed toxic content) and false positives (wrongly flagged benign content) "
                "carry different costs in moderation contexts."
            ),
        },

        "bias_and_fairness": {
            "evaluation_performed": bias_report is not None,
            "identity_groups_evaluated": bias_report.get("identity_columns_evaluated", []) if bias_report else [],
            "fairness_metric": "F1 gap vs. overall baseline",
            "fairness_threshold": bias_report.get("fairness_threshold") if bias_report else None,
            "passed_fairness_check": bias_report.get("passed_fairness") if bias_report else None,
            "violations": fairness_violations,
            "overall_bias_metrics": {
                "accuracy": overall_bias.get("accuracy"),
                "f1": overall_bias.get("f1"),
                "fpr": overall_bias.get("fpr"),
                "fnr": overall_bias.get("fnr"),
            },
            "bias_mitigation_notes": (
                "No active mitigation applied in this baseline. Recommend: "
                "(1) re-weighting by identity-group frequency, "
                "(2) adversarial debiasing, or (3) dataset augmentation for under-represented groups."
            ),
        },

        "inference_performance": {
            "sla_ms": cfg["inference"]["sla_ms"],
            "latency_benchmark": (
                {
                    "mean_ms":   latency_report.get("mean_ms"),
                    "p95_ms":    latency_report.get("p95_ms"),
                    "p99_ms":    latency_report.get("p99_ms"),
                    "sla_passed": latency_report.get("sla_passed"),
                }
                if latency_report
                else "benchmark not yet run — execute: python inference.py --benchmark"
            ),
            "hardware": "CPU (optimized) / GPU (if available)",
            "optimization_notes": "Consider ONNX export or torch.quantization for production latency reduction.",
        },

        "limitations": [
            "English-only: accuracy degrades on non-English or code-switched text.",
            "Domain shift: trained on Wikipedia talk pages; performance may vary on social media, gaming chat, etc.",
            "Implicit toxicity: sarcasm, dog-whistles, and context-dependent toxicity may not be detected.",
            "Class imbalance: model may under-detect rare toxic categories.",
            "Temporal drift: new slang or evolving toxic language patterns require periodic retraining.",
        ],

        "ethical_considerations": [
            "Model may perpetuate biases present in training data annotations.",
            "False positives can suppress legitimate speech, especially for marginalized communities.",
            "False negatives allow harmful content to pass through — human review recommended for high-stakes decisions.",
            "Identity mentions (e.g., 'I am Black') can spuriously increase toxicity scores — investigate with bias report.",
            "Deployment should include a human-in-the-loop for ambiguous cases.",
        ],

        "recommendations": [
            "Run evaluate_bias.py after each retrain and review violation list before deployment.",
            "Monitor production prediction distribution; alert on drift (mean toxic_probability shift > 5%).",
            "Calibrate threshold per use-case: lower for recall-sensitive (safety) vs. higher for precision-sensitive (UX).",
            "Retrain quarterly or on significant vocabulary drift events.",
            "Log all predictions with trace_ids for audit trail and feedback loop.",
        ],

        "experiment_tracking": {
            "platform": "MLflow",
            "tracking_uri": cfg["paths"]["mlflow_tracking_uri"],
            "experiment": "toxicity_detection_baseline",
        },

        "how_to_use": {
            "inference": "python inference.py --model_dir artifacts/toxicity_model --text 'your text here'",
            "benchmark": "python inference.py --model_dir artifacts/toxicity_model --benchmark",
            "bias_eval": "python evaluate_bias.py --model_dir artifacts/toxicity_model",
            "retrain":   "python train_toxicity_model.py --config config.yaml",
        },
    }

    return card


def main():
    parser = argparse.ArgumentParser(description="Generate model card YAML")
    parser.add_argument("--config",          default="config.yaml")
    parser.add_argument("--eval_results",    default="artifacts/toxicity_model/evaluation_results.json")
    parser.add_argument("--bias_report",     default="artifacts/bias_report.json")
    parser.add_argument("--latency_report",  default="artifacts/latency_report.json")
    parser.add_argument("--output",          default="model_card.yaml")
    args = parser.parse_args()

    with open(args.config) as fh:
        cfg = yaml.safe_load(fh)

    eval_results    = _load_json(args.eval_results)
    bias_report     = _load_json(args.bias_report)
    latency_report  = _load_json(args.latency_report)

    card = generate_model_card(cfg, eval_results, bias_report, latency_report)

    with open(args.output, "w") as fh:
        yaml.dump(card, fh, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info("Model card written to %s", args.output)
    print(f"Model card saved: {args.output}")


if __name__ == "__main__":
    main()
