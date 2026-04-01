"""
evaluate.py — Comprehensive evaluation: accuracy metrics + bias analysis.

Outputs
───────
• artifacts/eval_report.json  — overall metrics + threshold pass/fail
• artifacts/bias_report.json  — per-slice CER/WER across doc_type,
                                 scan_quality, and language
• artifacts/latency_report.json — p50/p95/p99 latency + SLA verdict

Usage
─────
    python src/evaluate.py \
        --config   config/ocr_config.yaml \
        --model_dir artifacts/model \
        --data_split test
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import mlflow
import numpy as np
import pandas as pd
import yaml
from PIL import Image
from tqdm import tqdm

from data_utils import load_annotations, stratified_split
from inference import OCRInferencePipeline
from metrics import aggregate_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Slice evaluation ──────────────────────────────────────────────────────────

def evaluate_slice(
    pipeline: OCRInferencePipeline,
    df: pd.DataFrame,
    raw_dir: str,
    desc: str = "",
) -> Dict:
    """Run inference on every row in df and return aggregate_metrics."""
    references, hypotheses = [], []
    for _, row in tqdm(df.iterrows(), total=len(df), desc=desc, leave=False):
        img_path = Path(raw_dir) / row["image_path"]
        try:
            result = pipeline.predict(img_path)
            references.append(row["text"])
            hypotheses.append(result["text"])
        except Exception as exc:
            logger.warning("Skipping %s: %s", img_path, exc)
            references.append(row["text"])
            hypotheses.append("")  # worst-case: empty prediction

    return aggregate_metrics(references, hypotheses)


# ── Bias evaluation ───────────────────────────────────────────────────────────

def evaluate_bias(
    pipeline: OCRInferencePipeline,
    test_df: pd.DataFrame,
    raw_dir: str,
    bias_slices: Dict[str, List[str]],
) -> Dict:
    """Compute CER/WER for every declared bias slice.

    Returns a nested dict:  bias_report[slice_col][slice_value] = metrics
    """
    bias_report: Dict[str, Dict] = {}

    for col, values in bias_slices.items():
        bias_report[col] = {}
        for val in values:
            subset = test_df[test_df[col] == val]
            if subset.empty:
                logger.warning("Bias slice %s=%s — 0 samples found", col, val)
                bias_report[col][val] = {"n_samples": 0, "cer": None, "wer": None}
                continue
            logger.info("Evaluating bias slice %s=%s (%d samples)", col, val, len(subset))
            metrics = evaluate_slice(
                pipeline, subset, raw_dir, desc=f"{col}={val}"
            )
            bias_report[col][val] = metrics

        # Flag slices where CER spread > 0.10 (potential bias)
        cer_values = [
            v["cer"]
            for v in bias_report[col].values()
            if v.get("cer") is not None and v.get("n_samples", 0) > 0
        ]
        if len(cer_values) >= 2:
            cer_spread = max(cer_values) - min(cer_values)
            bias_report[col]["_cer_spread"] = round(cer_spread, 4)
            if cer_spread > 0.10:
                logger.warning(
                    "Potential bias in '%s': CER spread = %.4f (best %.4f, worst %.4f)",
                    col, cer_spread, min(cer_values), max(cer_values),
                )

    return bias_report


# ── Latency benchmark ────────────────────────────────────────────────────────

def run_latency_benchmark(
    pipeline: OCRInferencePipeline,
    test_df: pd.DataFrame,
    raw_dir: str,
    n_samples: int = 200,
) -> Dict:
    """Sample ≤ n_samples images for latency profiling."""
    sample = test_df.sample(
        n=min(n_samples, len(test_df)), random_state=42
    )
    images = [Path(raw_dir) / p for p in sample["image_path"]]
    return pipeline.benchmark(images, n_warmup=min(5, len(images)))


# ── Main ─────────────────────────────────────────────────────────────────────

def main(config_path: str, model_dir: str, data_split: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    ev = cfg["evaluation"]
    raw_dir = cfg["data"]["raw_dir"]
    seed = cfg["experiment"]["seed"]

    # ── 1. Load split ─────────────────────────────────────────────────────────
    df = load_annotations(cfg["data"]["annotation_file"])
    train_df, val_df, test_df = stratified_split(
        df,
        stratify_col=cfg["data"]["stratify_col"],
        train_frac=cfg["data"]["splits"]["train"],
        val_frac=cfg["data"]["splits"]["val"],
        seed=seed,
    )
    eval_df = {"train": train_df, "val": val_df, "test": test_df}[data_split]
    logger.info("Evaluating on '%s' split — %d samples", data_split, len(eval_df))

    # ── 2. Load inference pipeline ────────────────────────────────────────────
    pipeline = OCRInferencePipeline(
        model_dir,
        sla_ms=ev["latency_sla_ms"],
    )

    # ── 3. Overall metrics ────────────────────────────────────────────────────
    logger.info("Computing overall metrics …")
    overall_metrics = evaluate_slice(pipeline, eval_df, raw_dir, desc="overall")
    logger.info("Overall metrics: %s", overall_metrics)

    cer_pass = overall_metrics["cer"] <= ev["cer_threshold"]
    wer_pass = overall_metrics["wer"] <= ev["wer_threshold"]

    eval_report = {
        "split": data_split,
        "overall_metrics": overall_metrics,
        "thresholds": {
            "cer_threshold": ev["cer_threshold"],
            "wer_threshold": ev["wer_threshold"],
            "cer_pass": cer_pass,
            "wer_pass": wer_pass,
        },
    }

    # ── 4. Bias evaluation ────────────────────────────────────────────────────
    logger.info("Running bias evaluation …")
    bias_report = evaluate_bias(pipeline, eval_df, raw_dir, ev["bias_slices"])

    # ── 5. Latency benchmark ──────────────────────────────────────────────────
    logger.info("Running latency benchmark …")
    latency_report = run_latency_benchmark(
        pipeline, eval_df, raw_dir, n_samples=ev["latency_n_samples"]
    )
    logger.info("Latency stats: %s", latency_report)

    # ── 6. Write reports ──────────────────────────────────────────────────────
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)

    for path, obj in [
        (cfg["artifacts"]["eval_report_path"], eval_report),
        (cfg["artifacts"]["bias_report_path"], bias_report),
        ("artifacts/latency_report.json", latency_report),
    ]:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(obj, f, indent=2)
        logger.info("Wrote %s", path)

    # ── 7. Log to active MLflow run (if one exists) ───────────────────────────
    try:
        mlflow.set_tracking_uri(cfg["experiment"]["mlflow_tracking_uri"])
        mlflow.set_experiment(cfg["experiment"]["name"])
        with mlflow.start_run(run_name=f"eval_{data_split}"):
            mlflow.log_metrics({f"eval_{k}": v for k, v in overall_metrics.items()
                                 if isinstance(v, (int, float))})
            mlflow.log_metrics({
                "latency_p95_ms": latency_report.get("p95_ms", -1),
                "sla_pass": int(latency_report.get("sla_pass", False)),
            })
            for path in [
                cfg["artifacts"]["eval_report_path"],
                cfg["artifacts"]["bias_report_path"],
                "artifacts/latency_report.json",
            ]:
                mlflow.log_artifact(path)
    except Exception as exc:
        logger.warning("MLflow logging skipped: %s", exc)

    # ── 8. Print summary ──────────────────────────────────────────────────────
    print("\n── Evaluation Summary ─────────────────────────────────────────")
    print(f"  Split        : {data_split}  ({overall_metrics['n_samples']} samples)")
    print(f"  CER          : {overall_metrics['cer']:.4f}  {'PASS ✓' if cer_pass else 'FAIL ✗'}")
    print(f"  WER          : {overall_metrics['wer']:.4f}  {'PASS ✓' if wer_pass else 'FAIL ✗'}")
    print(f"  Exact Match  : {overall_metrics['exact_match']:.4f}")
    print(f"  Latency p95  : {latency_report.get('p95_ms', '?')} ms  "
          f"  {'PASS ✓' if latency_report.get('sla_pass') else 'FAIL ✗'}")
    print("\n  Bias (CER spread per slice):")
    for col, slices in bias_report.items():
        spread = slices.get("_cer_spread")
        flag = "⚠" if spread is not None and spread > 0.10 else " "
        print(f"    {flag} {col:<16} spread = {spread}")
    print("───────────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",     default="config/ocr_config.yaml")
    parser.add_argument("--model_dir",  default="artifacts/model")
    parser.add_argument("--data_split", default="test",
                        choices=["train", "val", "test"])
    args = parser.parse_args()
    main(args.config, args.model_dir, args.data_split)
