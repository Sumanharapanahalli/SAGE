"""
NER Model Inference + Latency Benchmark
========================================
Provides:
  1. A clean `NERPredictor` class for production inference.
  2. A latency benchmark that measures p50 / p95 / p99 latency per sentence
     and compares against the SLA defined in config.yaml.
  3. A CLI for both single-text inference and bulk latency benchmarking.

SLA contract (from config.yaml evaluation.sla_latency_ms):
  • p99 per-sentence latency must be ≤ SLA threshold.
  • Benchmark fails (non-zero exit) if the SLA is breached.

Usage
-----
    # Single inference
    python infer_ner.py --text "Apple was founded by Steve Jobs in Cupertino."

    # Latency benchmark
    python infer_ner.py --benchmark

    # Benchmark with a custom sentence file (one sentence per line)
    python infer_ner.py --benchmark --sentences-file my_sents.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from statistics import mean, median, quantiles
from typing import Optional

import numpy as np
import torch
import yaml
from transformers import AutoModelForTokenClassification, AutoTokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("infer_ner")


# ── NERPredictor ──────────────────────────────────────────────────────────────

class NERPredictor:
    """
    Production-ready NER inference wrapper.

    Parameters
    ----------
    model_dir : path to the saved model + tokenizer + label_map.json
    device    : "cpu", "cuda", or "auto" (auto-detects CUDA)
    max_length: maximum subword token length (must match training config)
    """

    def __init__(
        self,
        model_dir: str | Path,
        device: str = "auto",
        max_length: int = 128,
    ) -> None:
        model_dir = Path(model_dir)

        if device == "auto":
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self._device = torch.device(device)

        log.info("Loading tokenizer from %s", model_dir)
        self._tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

        log.info("Loading model from %s (device=%s)", model_dir, self._device)
        self._model = AutoModelForTokenClassification.from_pretrained(
            str(model_dir)
        ).to(self._device)
        self._model.eval()

        label_map_path = model_dir / "label_map.json"
        with open(label_map_path, encoding="utf-8") as f:
            lm = json.load(f)
        self._label_list: list[str] = lm["label_list"]
        self._max_length = max_length

    # ── Core inference ────────────────────────────────────────────────────────

    def predict(self, text: str) -> list[dict]:
        """
        Run NER on a raw text string.

        Returns a list of entity dicts:
            [{"text": "Steve Jobs", "label": "PER", "start": 21, "end": 31}, ...]

        Start/end are character offsets in the original text.
        """
        # Pre-tokenize into words (simple whitespace split for speed; replace
        # with spaCy tokenizer for production-grade boundary handling)
        words = text.split()
        if not words:
            return []

        enc = self._tokenizer(
            words,
            truncation=True,
            max_length=self._max_length,
            is_split_into_words=True,
            return_tensors="pt",
            return_offsets_mapping=False,
        ).to(self._device)

        with torch.no_grad():
            logits = self._model(**enc).logits      # (1, seq_len, num_labels)

        pred_ids = logits.argmax(-1)[0].cpu().numpy()
        word_ids  = enc.word_ids()

        # Collapse subwords → word-level predictions (first subword wins)
        word_labels: dict[int, str] = {}
        for token_i, word_id in enumerate(word_ids):
            if word_id is None or word_id in word_labels:
                continue
            word_labels[word_id] = self._label_list[pred_ids[token_i]]

        # Build entity spans (BIO decoding)
        entities: list[dict] = []
        current_entity: Optional[dict] = None
        char_offset = 0

        for word_idx, word in enumerate(words):
            label = word_labels.get(word_idx, "O")
            word_start = text.index(word, char_offset)
            word_end   = word_start + len(word)
            char_offset = word_end

            if label.startswith("B-"):
                if current_entity:
                    entities.append(current_entity)
                current_entity = {
                    "text":  word,
                    "label": label[2:],
                    "start": word_start,
                    "end":   word_end,
                }
            elif label.startswith("I-") and current_entity:
                current_entity["text"] += " " + word
                current_entity["end"]   = word_end
            else:
                if current_entity:
                    entities.append(current_entity)
                    current_entity = None

        if current_entity:
            entities.append(current_entity)

        return entities

    def predict_batch(self, texts: list[str]) -> list[list[dict]]:
        """Run predict() over a list of texts."""
        return [self.predict(t) for t in texts]


# ── Latency benchmark ─────────────────────────────────────────────────────────

_DEFAULT_BENCH_SENTENCES = [
    "Apple was founded by Steve Jobs in Cupertino.",
    "Barack Obama served as the 44th President of the United States.",
    "Google's headquarters is located in Mountain View, California.",
    "The European Central Bank raised interest rates last Thursday.",
    "Microsoft acquired Activision Blizzard for $68.7 billion.",
    "Dr. Emily Chen leads the neuroscience team at Stanford University.",
    "The FIFA World Cup 2026 will be hosted by the United States, Canada and Mexico.",
    "Amazon Web Services reported $24.2 billion in revenue for Q3 2023.",
    "The Paris Agreement was signed by 196 countries in 2015.",
    "Elon Musk's SpaceX launched the Starship rocket from Boca Chica, Texas.",
]


def _run_latency_benchmark(
    predictor: NERPredictor,
    sentences: list[str],
    warmup_runs: int,
    benchmark_runs: int,
    sla_ms: float,
) -> dict:
    """
    Measure per-sentence inference latency.

    Warmup runs are discarded (JIT / CUDA kernel warm-up).
    Returns a dict with p50/p95/p99 latencies and SLA pass/fail.
    """
    log.info("Warming up (%d runs) …", warmup_runs)
    for _ in range(warmup_runs):
        for s in sentences:
            predictor.predict(s)

    log.info("Benchmarking (%d runs × %d sentences) …",
             benchmark_runs, len(sentences))
    latencies_ms: list[float] = []
    for _ in range(benchmark_runs):
        for s in sentences:
            t0 = time.perf_counter()
            predictor.predict(s)
            latencies_ms.append((time.perf_counter() - t0) * 1000)

    latencies_ms.sort()
    n = len(latencies_ms)
    p50  = latencies_ms[int(n * 0.50)]
    p95  = latencies_ms[int(n * 0.95)]
    p99  = latencies_ms[int(n * 0.99)]
    mean_ms = mean(latencies_ms)

    sla_pass = p99 <= sla_ms
    status = "PASS" if sla_pass else "FAIL"
    log.info(
        "Latency — mean=%.2fms  p50=%.2fms  p95=%.2fms  p99=%.2fms  "
        "SLA(%.0fms)=%s",
        mean_ms, p50, p95, p99, sla_ms, status,
    )
    if not sla_pass:
        log.error(
            "SLA BREACH: p99 latency %.2fms exceeds SLA threshold %.0fms.",
            p99, sla_ms,
        )

    return {
        "n_measurements": n,
        "n_sentences":    len(sentences),
        "mean_ms":        round(mean_ms, 3),
        "p50_ms":         round(p50, 3),
        "p95_ms":         round(p95, 3),
        "p99_ms":         round(p99, 3),
        "sla_ms":         sla_ms,
        "sla_pass":       sla_pass,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(
        description="NER Model Inference + Latency Benchmark",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--config", type=Path,
                   default=Path(__file__).parent / "config.yaml")
    p.add_argument("--model",  type=str, default=None,
                   help="Override model directory path")
    p.add_argument("--text",   type=str, default=None,
                   help="Text to run NER on (single inference)")
    p.add_argument("--benchmark", action="store_true",
                   help="Run latency benchmark and check SLA")
    p.add_argument("--sentences-file", type=Path, default=None,
                   help="File with one sentence per line (for benchmark)")
    p.add_argument("--device", default="auto",
                   help="Inference device: auto | cpu | cuda")
    return p.parse_args()


def main():
    args = _parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    base_dir  = Path(__file__).parent
    model_dir = args.model or str((base_dir / cfg["output"]["model_dir"]).resolve())

    predictor = NERPredictor(
        model_dir=model_dir,
        device=args.device,
        max_length=cfg["model"]["max_length"],
    )

    # ── Single inference ───────────────────────────────────────────────────────
    if args.text:
        entities = predictor.predict(args.text)
        print(f"\nInput: {args.text}")
        print("Entities:")
        for ent in entities:
            print(f"  [{ent['label']}]  \"{ent['text']}\"  "
                  f"(chars {ent['start']}–{ent['end']})")

    # ── Benchmark ─────────────────────────────────────────────────────────────
    if args.benchmark:
        if args.sentences_file:
            sents = [l.strip() for l in args.sentences_file.read_text().splitlines()
                     if l.strip()]
        else:
            sents = _DEFAULT_BENCH_SENTENCES

        bench_result = _run_latency_benchmark(
            predictor=predictor,
            sentences=sents,
            warmup_runs=cfg["inference"]["latency_warmup_runs"],
            benchmark_runs=cfg["inference"]["latency_benchmark_runs"],
            sla_ms=cfg["evaluation"]["sla_latency_ms"],
        )

        # Write benchmark result to reports
        reports_dir = (base_dir / cfg["output"]["reports_dir"]).resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)
        bench_path  = reports_dir / "latency_benchmark.json"
        bench_path.write_text(json.dumps(bench_result, indent=2), encoding="utf-8")
        log.info("Latency report → %s", bench_path)

        print("\n=== Latency Benchmark Results ===")
        for k, v in bench_result.items():
            print(f"  {k:<22} {v}")

        if not bench_result["sla_pass"]:
            sys.exit(1)    # non-zero exit signals CI failure

    if not args.text and not args.benchmark:
        print("Specify --text 'some text' or --benchmark. Use --help for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
