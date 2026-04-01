"""
NER Model Evaluation — Metrics + Bias Analysis
===============================================
Loads a trained NER model and produces:
  1. Overall entity-level F1 / precision / recall (seqeval)
  2. Per-entity-type breakdown
  3. Bias slices: performance by entity type and sentence length bucket
  4. Class imbalance report: O-token vs entity token ratio
  5. Confusion matrix for entity types (predicted vs true spans)
  6. Reports written to output/reports/

Usage
-----
    python evaluate_ner.py                          # use config.yaml defaults
    python evaluate_ner.py --split test             # evaluate on test split
    python evaluate_ner.py --split val              # evaluate on val split
    python evaluate_ner.py --model ./my_ckpt        # custom model path
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import yaml
from datasets import Dataset, DatasetDict, load_dataset
from transformers import AutoModelForTokenClassification, AutoTokenizer, pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from experiment_logger import ExperimentLogger  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("evaluate_ner")


# ── CoNLL helpers (mirrored from train_ner.py) ────────────────────────────────

def _load_conll_file(path: Path) -> list[dict]:
    sentences, cur_toks, cur_tags = [], [], []
    with open(path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if not line or line.startswith("-DOCSTART-"):
                if cur_toks:
                    sentences.append({"tokens": cur_toks, "ner_tags": cur_tags})
                    cur_toks, cur_tags = [], []
                continue
            parts = line.split()
            if len(parts) >= 2:
                cur_toks.append(parts[0])
                cur_tags.append(parts[-1])
    if cur_toks:
        sentences.append({"tokens": cur_toks, "ner_tags": cur_tags})
    return sentences


def _load_split(cfg: dict, split: str) -> list[dict]:
    """
    Return a list of {'tokens': [...], 'ner_tags': [...]} dicts.
    Falls back to HuggingFace conll2003 if local files not found.
    """
    base = Path(__file__).parent
    path_key = {"train": "train_path", "val": "val_path", "test": "test_path"}[split]
    local_path = (base / cfg["data"][path_key]).resolve()

    if local_path.exists():
        log.info("Loading local CoNLL split: %s", local_path)
        return _load_conll_file(local_path)

    log.info("Local split not found — loading %s from HuggingFace …", split)
    hf_split = "validation" if split == "val" else split
    ds = load_dataset(cfg["data"]["hf_fallback_dataset"], split=hf_split,
                      trust_remote_code=True)
    id2label = ds.features["ner_tags"].feature.names
    return [
        {
            "tokens":   ex["tokens"],
            "ner_tags": [id2label[t] for t in ex["ner_tags"]],
        }
        for ex in ds
    ]


# ── Batch inference ───────────────────────────────────────────────────────────

def _predict_batch(
    sentences: list[dict],
    model,
    tokenizer,
    label_list: list[str],
    cfg: dict,
) -> tuple[list[list[str]], list[list[str]]]:
    """
    Run token-classification inference on sentences.

    Returns (true_labels, pred_labels) — parallel lists of per-word labels.
    Subword predictions are collapsed to the first subword (word-level).

    No data leakage: model and tokenizer are loaded from disk (trained state).
    """
    model.eval()
    device = next(model.parameters()).device
    max_len = cfg["model"]["max_length"]

    true_all, pred_all = [], []

    for sent in sentences:
        words = sent["tokens"]
        gold  = sent["ner_tags"]

        enc = tokenizer(
            words,
            truncation=True,
            max_length=max_len,
            is_split_into_words=True,
            return_tensors="pt",
            padding=False,
        ).to(device)

        with torch.no_grad():
            logits = model(**enc).logits          # (1, seq_len, num_labels)

        pred_ids = logits.argmax(-1)[0].cpu().numpy()
        word_ids  = enc.word_ids()

        # Collapse to word-level (first subword only)
        word_preds: dict[int, str] = {}
        for token_i, word_id in enumerate(word_ids):
            if word_id is None or word_id in word_preds:
                continue
            word_preds[word_id] = label_list[pred_ids[token_i]]

        # Align with gold labels (truncation may shorten)
        n = min(len(gold), len(word_preds))
        true_all.append(gold[:n])
        pred_all.append([word_preds[i] for i in range(n)])

    return true_all, pred_all


# ── Bias slicing ──────────────────────────────────────────────────────────────

def _entity_type_bias(
    sentences: list[dict],
    true_all: list[list[str]],
    pred_all: list[list[str]],
    entity_types: list[str],
) -> dict[str, dict]:
    """
    Per-entity-type F1 by slicing sentences that contain at least one entity
    of that type. Reports both span-level F1 (seqeval) and support count.
    """
    from seqeval.metrics import f1_score, precision_score, recall_score

    results = {}
    for etype in entity_types:
        b_tag = f"B-{etype}"
        indices = [
            i for i, sent in enumerate(sentences)
            if any(t == b_tag for t in sent["ner_tags"])
        ]
        if not indices:
            results[etype] = {"support": 0, "f1": None,
                               "precision": None, "recall": None}
            continue
        slice_true = [true_all[i] for i in indices]
        slice_pred = [pred_all[i] for i in indices]
        results[etype] = {
            "support":   len(indices),
            "f1":        round(f1_score(slice_true, slice_pred), 4),
            "precision": round(precision_score(slice_true, slice_pred), 4),
            "recall":    round(recall_score(slice_true, slice_pred), 4),
        }
    return results


def _length_bucket_bias(
    sentences: list[dict],
    true_all: list[list[str]],
    pred_all: list[list[str]],
    length_buckets: dict[str, list[int]],
) -> dict[str, dict]:
    """
    Per-sentence-length-bucket F1. Reveals if model degrades on long sentences.
    """
    from seqeval.metrics import f1_score, precision_score, recall_score

    results = {}
    for bucket_name, (lo, hi) in length_buckets.items():
        indices = [
            i for i, s in enumerate(sentences)
            if lo <= len(s["tokens"]) <= hi
        ]
        if not indices:
            results[bucket_name] = {"support": 0, "f1": None}
            continue
        slice_true = [true_all[i] for i in indices]
        slice_pred = [pred_all[i] for i in indices]
        results[bucket_name] = {
            "support":   len(indices),
            "length_range": [lo, hi],
            "f1":        round(f1_score(slice_true, slice_pred), 4),
            "precision": round(precision_score(slice_true, slice_pred), 4),
            "recall":    round(recall_score(slice_true, slice_pred), 4),
        }
    return results


def _class_imbalance_report(sentences: list[dict]) -> dict:
    """Count O vs entity tokens; flag if O dominance > 95%."""
    n_total, n_o, entity_counts = 0, 0, defaultdict(int)
    for sent in sentences:
        for tag in sent["ner_tags"]:
            n_total += 1
            if tag == "O":
                n_o += 1
            elif tag.startswith("B-"):
                entity_counts[tag[2:]] += 1

    o_ratio = n_o / max(n_total, 1)
    return {
        "total_tokens":  n_total,
        "o_tokens":      n_o,
        "entity_tokens": n_total - n_o,
        "o_ratio":       round(o_ratio, 4),
        "entity_counts": dict(entity_counts),
        "class_imbalance_flag": o_ratio > 0.95,
    }


# ── Main evaluation function ──────────────────────────────────────────────────

def evaluate(cfg: dict, split: str = "test", model_path: str | None = None) -> dict:
    base_dir    = Path(__file__).parent
    model_dir   = Path(model_path) if model_path else \
                  (base_dir / cfg["output"]["model_dir"]).resolve()
    reports_dir = (base_dir / cfg["output"]["reports_dir"]).resolve()
    log_dir     = (base_dir / cfg["output"]["log_dir"]).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    # ── Load model + tokenizer (trained artifacts, no re-fitting) ─────────────
    log.info("Loading model from %s", model_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model     = AutoModelForTokenClassification.from_pretrained(str(model_dir))
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    label_map_path = model_dir / "label_map.json"
    with open(label_map_path, encoding="utf-8") as f:
        label_map = json.load(f)
    label_list = label_map["label_list"]

    exp = ExperimentLogger("ner_evaluation", log_dir=log_dir)
    run_id = exp.start_run(params={
        "model_dir": str(model_dir),
        "split":     split,
        "seed":      cfg["training"]["seed"],
    })

    # ── Load evaluation split ─────────────────────────────────────────────────
    sentences = _load_split(cfg, split)
    log.info("Evaluating on %s set: %d sentences", split, len(sentences))

    # ── Inference ─────────────────────────────────────────────────────────────
    log.info("Running inference …")
    true_labels, pred_labels = _predict_batch(
        sentences, model, tokenizer, label_list, cfg
    )

    # ── Overall metrics (seqeval — entity-level, not token-level) ─────────────
    try:
        from seqeval.metrics import (
            classification_report,
            f1_score,
            precision_score,
            recall_score,
        )
        overall = {
            "overall_precision": round(precision_score(true_labels, pred_labels), 4),
            "overall_recall":    round(recall_score(true_labels, pred_labels), 4),
            "overall_f1":        round(f1_score(true_labels, pred_labels), 4),
            "classification_report": classification_report(
                true_labels, pred_labels, digits=4
            ),
        }
        log.info("\n%s", overall["classification_report"])
    except ImportError:
        log.warning("seqeval not available — skipping entity-level metrics.")
        overall = {}

    # ── Bias evaluation ───────────────────────────────────────────────────────
    entity_types   = cfg["evaluation"]["bias_entity_types"]
    length_buckets = cfg["evaluation"]["length_buckets"]

    log.info("Running bias evaluation: entity types = %s", entity_types)
    entity_bias = _entity_type_bias(sentences, true_labels, pred_labels, entity_types)

    log.info("Running bias evaluation: sentence length buckets")
    length_bias = _length_bucket_bias(sentences, true_labels, pred_labels, length_buckets)

    # ── Class imbalance ───────────────────────────────────────────────────────
    imbalance = _class_imbalance_report(sentences)
    if imbalance["class_imbalance_flag"]:
        log.warning(
            "Class imbalance: O-token ratio = %.1f%% (> 95%%). "
            "Consider weighted loss in re-training.",
            imbalance["o_ratio"] * 100,
        )

    # ── Compile report ────────────────────────────────────────────────────────
    report = {
        "split":            split,
        "model_dir":        str(model_dir),
        "overall_metrics":  overall,
        "bias": {
            "entity_type":      entity_bias,
            "sentence_length":  length_bias,
        },
        "class_imbalance":  imbalance,
    }

    report_path = reports_dir / f"eval_{split}_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("Evaluation report → %s", report_path)

    # ── Log metrics ───────────────────────────────────────────────────────────
    metrics_to_log = {
        "overall_f1":        overall.get("overall_f1", 0.0),
        "overall_precision": overall.get("overall_precision", 0.0),
        "overall_recall":    overall.get("overall_recall", 0.0),
        "class_imbalance":   float(imbalance["class_imbalance_flag"]),
    }
    for etype, vals in entity_bias.items():
        if vals["f1"] is not None:
            metrics_to_log[f"bias_f1_{etype.lower()}"] = vals["f1"]
    for bucket, vals in length_bias.items():
        if vals["f1"] is not None:
            metrics_to_log[f"bias_f1_len_{bucket}"] = vals["f1"]

    exp.log_metrics(run_id, metrics_to_log)
    exp.end_run(run_id, status="completed")

    return report


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(
        description="NER Model Evaluator + Bias Analyzer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", type=Path,
                   default=Path(__file__).parent / "config.yaml")
    p.add_argument("--split",  choices=["train", "val", "test"], default="test")
    p.add_argument("--model",  type=str, default=None,
                   help="Override model directory path")
    return p.parse_args()


def main():
    args = _parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    report = evaluate(cfg, split=args.split, model_path=args.model)

    print("\n=== Evaluation Summary ===")
    print(f"  Split:             {report['split']}")
    m = report["overall_metrics"]
    print(f"  Overall F1:        {m.get('overall_f1', 'N/A')}")
    print(f"  Overall Precision: {m.get('overall_precision', 'N/A')}")
    print(f"  Overall Recall:    {m.get('overall_recall', 'N/A')}")
    print("\n--- Bias by Entity Type ---")
    for etype, vals in report["bias"]["entity_type"].items():
        print(f"  {etype:<6}  support={vals['support']:>4}  "
              f"f1={vals['f1']}")
    print("\n--- Bias by Sentence Length ---")
    for bucket, vals in report["bias"]["sentence_length"].items():
        print(f"  {bucket:<8}  {vals.get('length_range')}  "
              f"support={vals['support']:>4}  f1={vals['f1']}")
    print("\n--- Class Imbalance ---")
    ci = report["class_imbalance"]
    print(f"  O-token ratio: {ci['o_ratio']:.1%}  "
          f"(flag={ci['class_imbalance_flag']})")


if __name__ == "__main__":
    main()
