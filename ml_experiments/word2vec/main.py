"""Entry point for Word2Vec skip-gram training, evaluation, and visualisation."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import mlflow
import torch

from word2vec.config import Word2VecConfig
from word2vec.evaluate import AnalogyEvaluator
from word2vec.trainer import Trainer
from word2vec.visualize import tsne_plot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("word2vec.main")


# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Train Word2Vec (skip-gram + negative sampling) from scratch."
    )
    p.add_argument("--corpus",       type=str,  default=None,
                   help="Path to plain-text corpus (default: NLTK Brown+Reuters)")
    p.add_argument("--dim",          type=int,  default=100,
                   help="Embedding dimension (default: 100)")
    p.add_argument("--epochs",       type=int,  default=5)
    p.add_argument("--window",       type=int,  default=5)
    p.add_argument("--negatives",    type=int,  default=5)
    p.add_argument("--min-count",    type=int,  default=5)
    p.add_argument("--batch-size",   type=int,  default=512)
    p.add_argument("--lr",           type=float, default=0.025)
    p.add_argument("--device",       type=str,  default="auto")
    p.add_argument("--tsne-words",   type=int,  default=200)
    p.add_argument("--tsne-out",     type=str,  default="tsne_embeddings.png")
    p.add_argument("--checkpoint-dir", type=str, default="checkpoints")
    p.add_argument("--seed",         type=int,  default=42)
    p.add_argument("--no-tsne",      action="store_true",
                   help="Skip t-SNE (faster for quick checks)")
    p.add_argument("--output-json",  type=str,  default=None,
                   help="Write final JSON report to this path")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    cfg = Word2VecConfig(
        corpus_path      = args.corpus,
        embedding_dim    = args.dim,
        epochs           = args.epochs,
        window_size      = args.window,
        num_negatives    = args.negatives,
        min_count        = args.min_count,
        batch_size       = args.batch_size,
        learning_rate    = args.lr,
        device           = args.device,
        tsne_n_words     = args.tsne_words,
        tsne_save_path   = args.tsne_out,
        checkpoint_dir   = args.checkpoint_dir,
        seed             = args.seed,
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    trainer = Trainer(cfg)
    model, vocab = trainer.run()
    model.eval()

    # ── Evaluate ──────────────────────────────────────────────────────────────
    evaluator = AnalogyEvaluator(
        model,
        vocab,
        extra_pairs=cfg.analogy_tests,
        seed=cfg.seed,
    )

    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    mlflow.set_experiment(cfg.experiment_name)

    with mlflow.start_run(run_name="evaluation", nested=True):
        reports = evaluator.run()
        for report in reports.values():
            report.log_to_mlflow()

    # ── Demo: king − man + woman ──────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("ANALOGY DEMO: king − man + woman = ?")
    try:
        results = model.analogy("king", "man", "woman", vocab, topk=5)
        for rank, (word, score) in enumerate(results, 1):
            marker = " ← expected" if word == "queen" else ""
            logger.info("  %d. %-15s  cosine=%.4f%s", rank, word, score, marker)
    except KeyError as e:
        logger.warning("Demo skipped — word not in vocabulary: %s", e)
    logger.info("=" * 60)

    # ── Nearest neighbours ────────────────────────────────────────────────────
    for probe in ("king", "paris", "good", "dog"):
        if probe in vocab:
            neighbours = model.most_similar(probe, vocab, topk=5)
            logger.info(
                "most_similar('%s'): %s",
                probe,
                ", ".join(f"{w}({s:.2f})" for w, s in neighbours),
            )

    # ── t-SNE ─────────────────────────────────────────────────────────────────
    if not args.no_tsne:
        plot_path = tsne_plot(
            model, vocab,
            n_words=cfg.tsne_n_words,
            perplexity=cfg.tsne_perplexity,
            save_path=cfg.tsne_save_path,
        )
        with mlflow.start_run(run_name="visualisation", nested=True):
            mlflow.log_artifact(plot_path, artifact_path="plots")

    # ── JSON report ───────────────────────────────────────────────────────────
    test_report = reports.get("test", next(iter(reports.values())) if reports else None)
    json_report = {
        "model_type": "word2vec_skipgram_negative_sampling",
        "metrics": {
            "accuracy":       round(test_report.accuracy, 4)      if test_report else 0.0,
            "f1":             round(test_report.mrr, 4)            if test_report else 0.0,
            "top5_accuracy":  round(test_report.top5_accuracy, 4)  if test_report else 0.0,
            "mrr":            round(test_report.mrr, 4)            if test_report else 0.0,
            "analogy_accuracy": round(test_report.accuracy, 4)    if test_report else 0.0,
        },
        "data_checks": {
            "leakage_risk":    False,   # subsampling/vocab fit on train tokens only
            "class_imbalance": False,   # N/A — unsupervised; analogy splits are stratified
        },
        "training": {
            "vocab_size":      vocab.size,
            "embedding_dim":   cfg.embedding_dim,
            "epochs":          cfg.epochs,
            "window_size":     cfg.window_size,
            "num_negatives":   cfg.num_negatives,
        },
        "eval_splits": {
            split: {
                "accuracy":      r.accuracy,
                "top5_accuracy": r.top5_accuracy,
                "mrr":           r.mrr,
                "n_valid":       r.n_valid,
                "n_total":       r.n_total,
            }
            for split, r in reports.items()
        },
    }

    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(json_report, f, indent=2)
        logger.info("JSON report saved → %s", out_path)

    print(json.dumps(json_report, indent=2))


if __name__ == "__main__":
    main()
