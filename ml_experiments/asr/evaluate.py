"""
ASR Evaluation Script — WER / CER / RTF + Bias Analysis
Loads best checkpoint, evaluates on held-out test set,
and breaks down WER by demographic subgroups.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import torch
import yaml
from datasets import Audio, load_dataset
from evaluate import load as load_metric
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core metrics
# ---------------------------------------------------------------------------

wer_metric = load_metric("wer")
cer_metric = load_metric("cer")


def compute_wer(predictions: list[str], references: list[str]) -> float:
    return wer_metric.compute(predictions=predictions, references=references)


def compute_cer(predictions: list[str], references: list[str]) -> float:
    return cer_metric.compute(predictions=predictions, references=references)


def compute_rtf(audio_durations_sec: list[float], inference_times_sec: list[float]) -> float:
    """Real-Time Factor = total inference time / total audio duration.
    RTF < 1.0 means the model runs faster than real-time.
    """
    total_audio = sum(audio_durations_sec)
    total_infer = sum(inference_times_sec)
    return total_infer / total_audio if total_audio > 0 else float("inf")


# ---------------------------------------------------------------------------
# Transcription loop
# ---------------------------------------------------------------------------


def transcribe_batch(
    examples: list[dict],
    model: Wav2Vec2ForCTC,
    processor: Wav2Vec2Processor,
    device: torch.device,
    sampling_rate: int,
) -> tuple[list[str], list[float]]:
    """Transcribe a batch and return (predictions, inference_times_sec)."""
    times = []
    preds = []

    for ex in examples:
        audio_array = np.array(ex["audio"]["array"], dtype=np.float32)
        inputs = processor(
            audio_array,
            sampling_rate=sampling_rate,
            return_tensors="pt",
            padding=True,
        ).to(device)

        t0 = time.perf_counter()
        with torch.no_grad():
            logits = model(**inputs).logits
        times.append(time.perf_counter() - t0)

        pred_ids = torch.argmax(logits, dim=-1)
        preds.append(processor.decode(pred_ids[0]))

    return preds, times


# ---------------------------------------------------------------------------
# Bias evaluation
# ---------------------------------------------------------------------------


def evaluate_bias(
    df: pd.DataFrame,
    bias_groups: list[str],
) -> dict[str, dict[str, float]]:
    """Compute WER breakdown per subgroup. Requires columns in df:
    'prediction', 'reference', and any column in bias_groups.
    """
    results: dict[str, dict[str, float]] = {}

    for group_col in bias_groups:
        if group_col not in df.columns:
            logger.warning("Bias group column '%s' not found — skipping", group_col)
            continue

        group_results = {}
        for group_val, sub_df in df.groupby(group_col):
            if len(sub_df) < 5:
                logger.warning("Subgroup %s=%s has only %d samples — low confidence", group_col, group_val, len(sub_df))
            wer = compute_wer(sub_df["prediction"].tolist(), sub_df["reference"].tolist())
            group_results[str(group_val)] = round(wer, 4)

        results[group_col] = group_results
        # Flag if max/min WER gap exceeds 10 percentage points (fairness threshold)
        vals = list(group_results.values())
        if vals and (max(vals) - min(vals)) > 0.10:
            logger.warning(
                "BIAS ALERT: WER gap in '%s' = %.1f pp (max=%.4f, min=%.4f). Investigate.",
                group_col,
                (max(vals) - min(vals)) * 100,
                max(vals),
                min(vals),
            )

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(config_path: str = "config.yaml", model_dir: str | None = None):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    exp_cfg = cfg["experiment"]
    data_cfg = cfg["data"]
    eval_cfg = cfg["evaluation"]

    model_dir = model_dir or str(Path(exp_cfg["output_dir"]) / "best_model")
    output_dir = Path(exp_cfg["output_dir"])

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Evaluating on device: %s", device)

    # Load model + processor
    logger.info("Loading model from %s", model_dir)
    processor = Wav2Vec2Processor.from_pretrained(model_dir)
    model = Wav2Vec2ForCTC.from_pretrained(model_dir).to(device)
    model.eval()

    # Load TEST split only — never train or val
    logger.info("Loading test split: %s", data_cfg["test_split"])
    test_ds = load_dataset(
        data_cfg["dataset_name"],
        data_cfg["dataset_config"],
        split=data_cfg["test_split"],
        cache_dir=data_cfg["cache_dir"],
        trust_remote_code=True,
    ).cast_column("audio", Audio(sampling_rate=data_cfg["sampling_rate"]))

    logger.info("Test samples: %d", len(test_ds))

    # Transcribe
    logger.info("Transcribing test set …")
    examples = [test_ds[i] for i in range(len(test_ds))]
    predictions, infer_times = transcribe_batch(
        examples, model, processor, device, data_cfg["sampling_rate"]
    )
    references = [ex["text"].lower() for ex in examples]
    audio_durations = [
        len(ex["audio"]["array"]) / data_cfg["sampling_rate"] for ex in examples
    ]

    # Core metrics
    wer = compute_wer(predictions, references)
    cer = compute_cer(predictions, references)
    rtf = compute_rtf(audio_durations, infer_times)
    p95_latency_ms = np.percentile(infer_times, 95) * 1000

    logger.info("WER       = %.4f (%.1f%%)", wer, wer * 100)
    logger.info("CER       = %.4f (%.1f%%)", cer, cer * 100)
    logger.info("RTF       = %.4f (target < %.2f)", rtf, eval_cfg["rtf_sla_threshold"])
    logger.info("p95 latency = %.1f ms (SLA = %d ms)", p95_latency_ms, cfg["inference"]["latency_sla_ms"])

    rtf_ok = rtf < eval_cfg["rtf_sla_threshold"]
    latency_ok = p95_latency_ms < cfg["inference"]["latency_sla_ms"]
    logger.info("RTF SLA: %s | Latency SLA: %s", "PASS" if rtf_ok else "FAIL", "PASS" if latency_ok else "FAIL")

    # Build results dataframe (include metadata columns for bias analysis)
    records = []
    for i, ex in enumerate(examples):
        row = {
            "id": ex.get("id", i),
            "prediction": predictions[i],
            "reference": references[i],
            "duration_sec": audio_durations[i],
            "infer_time_sec": infer_times[i],
        }
        for col in eval_cfg["bias_groups"]:
            row[col] = ex.get(col, None)
        records.append(row)

    df = pd.DataFrame(records)

    # Per-sample WER (approximated as 0/1 exact match for efficiency;
    # true per-sample WER uses jiwer)
    try:
        import jiwer
        df["sample_wer"] = df.apply(
            lambda r: jiwer.wer(r["reference"], r["prediction"]), axis=1
        )
    except ImportError:
        df["sample_wer"] = (df["prediction"] != df["reference"]).astype(float)

    # Bias evaluation
    logger.info("=== Bias Evaluation ===")
    bias_report = evaluate_bias(df, eval_cfg["bias_groups"])

    # Assemble full report
    eval_report = {
        "model_dir": model_dir,
        "test_split": data_cfg["test_split"],
        "num_samples": len(test_ds),
        "metrics": {
            "wer": round(wer, 4),
            "cer": round(cer, 4),
            "rtf": round(rtf, 4),
            "p95_latency_ms": round(p95_latency_ms, 1),
        },
        "sla": {
            "rtf_pass": rtf_ok,
            "latency_pass": latency_ok,
        },
        "bias_by_group": bias_report,
        "percentile_wer": {
            "p25": round(float(df["sample_wer"].quantile(0.25)), 4),
            "p50": round(float(df["sample_wer"].quantile(0.50)), 4),
            "p75": round(float(df["sample_wer"].quantile(0.75)), 4),
            "p95": round(float(df["sample_wer"].quantile(0.95)), 4),
        },
    }

    report_path = output_dir / "eval_report.json"
    with open(report_path, "w") as f:
        json.dump(eval_report, f, indent=2)
    logger.info("Evaluation report saved: %s", report_path)

    # Save prediction CSV for audit
    csv_path = output_dir / "test_predictions.csv"
    df.to_csv(csv_path, index=False)
    logger.info("Predictions saved: %s", csv_path)

    # Log to MLflow
    mlflow.set_tracking_uri(exp_cfg["mlflow_tracking_uri"])
    mlflow.set_experiment(exp_cfg["mlflow_experiment"])
    with mlflow.start_run(run_name=f"{exp_cfg['name']}-eval"):
        mlflow.log_metrics(eval_report["metrics"])
        mlflow.log_artifact(str(report_path))
        mlflow.log_artifact(str(csv_path))
        for group, breakdown in bias_report.items():
            for subval, wer_val in breakdown.items():
                mlflow.log_metric(f"wer_{group}_{subval}", wer_val)

    return eval_report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ASR Evaluation")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--model_dir", default=None, help="Override model dir")
    args = parser.parse_args()
    report = main(args.config, args.model_dir)
    print(json.dumps(report, indent=2))
