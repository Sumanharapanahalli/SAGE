"""Training loop with linear LR decay and MLflow experiment tracking."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional

import mlflow
import mlflow.pytorch
import numpy as np
import torch
from torch.utils.data import DataLoader

from .config import Word2VecConfig
from .dataset import SkipGramDataset, build_skipgram_pairs, load_corpus
from .model import Word2Vec
from .vocabulary import Vocabulary

logger = logging.getLogger(__name__)


class Trainer:
    """Encapsulates all training logic for Word2Vec skip-gram.

    Usage::

        cfg = Word2VecConfig()
        trainer = Trainer(cfg)
        model, vocab = trainer.run()
    """

    def __init__(self, cfg: Word2VecConfig) -> None:
        self.cfg = cfg
        self.device = self._resolve_device(cfg.device)
        torch.manual_seed(cfg.seed)
        np.random.seed(cfg.seed)
        logger.info("Trainer device: %s", self.device)

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> tuple[Word2Vec, Vocabulary]:
        """Full pipeline: load corpus → build vocab → train → return."""
        cfg = self.cfg

        # ── 1. Corpus ─────────────────────────────────────────────────────────
        tokens = load_corpus(cfg.corpus_path)

        # ── 2. Vocabulary ─────────────────────────────────────────────────────
        vocab = Vocabulary.build(tokens, cfg.min_count, cfg.max_vocab_size)
        vocab.build_neg_table(cfg.neg_sampling_power)

        # ── 3. Subsample + encode tokens ──────────────────────────────────────
        # NOTE: subsample operates on the TRAINING tokens only.
        # No scaler/encoder is fitted on held-out data → zero leakage.
        subsampled = vocab.subsample(tokens, cfg.subsample_threshold)
        token_ids = [vocab.encode(t) for t in subsampled]

        # ── 4. Skip-gram pairs ────────────────────────────────────────────────
        logger.info("Building skip-gram pairs (window=%d)…", cfg.window_size)
        pairs = build_skipgram_pairs(token_ids, cfg.window_size)
        logger.info("Total pairs: %d", len(pairs))

        dataset = SkipGramDataset(pairs, vocab, cfg.num_negatives)
        loader = DataLoader(
            dataset,
            batch_size=cfg.batch_size,
            shuffle=True,
            num_workers=min(4, os.cpu_count() or 1),
            pin_memory=(self.device.type == "cuda"),
        )

        # ── 5. Model ──────────────────────────────────────────────────────────
        model = Word2Vec(vocab.size, cfg.embedding_dim).to(self.device)
        total_params = sum(p.numel() for p in model.parameters())
        logger.info(
            "Model: vocab=%d, dim=%d, params=%d",
            vocab.size, cfg.embedding_dim, total_params,
        )

        # ── 6. Optimiser (SGD — matches original word2vec) ────────────────────
        optimizer = torch.optim.SGD(model.parameters(), lr=cfg.learning_rate)

        # ── 7. MLflow run ─────────────────────────────────────────────────────
        mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
        mlflow.set_experiment(cfg.experiment_name)

        Path(cfg.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        best_loss = float("inf")
        run_id: Optional[str] = None

        with mlflow.start_run() as run:
            run_id = run.info.run_id
            mlflow.log_params(self._params_dict(cfg, vocab, len(pairs)))

            total_steps = cfg.epochs * len(loader)
            step = 0

            for epoch in range(1, cfg.epochs + 1):
                model.train()
                epoch_loss = 0.0
                epoch_start = time.time()

                for batch in loader:
                    # Linear LR decay:  lr_t = lr_0 × (1 - t / T_max)
                    lr_t = max(
                        cfg.min_lr,
                        cfg.learning_rate * (1.0 - step / total_steps),
                    )
                    for g in optimizer.param_groups:
                        g["lr"] = lr_t

                    center, context, negatives = (t.to(self.device) for t in batch)
                    optimizer.zero_grad(set_to_none=True)
                    loss = model(center, context, negatives)
                    loss.backward()
                    # Gradient clipping — prevents exploding gradients on rare words
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
                    optimizer.step()

                    batch_loss = loss.item()
                    epoch_loss += batch_loss
                    step += 1

                    if step % cfg.log_every_n_steps == 0:
                        mlflow.log_metrics(
                            {"train/loss": batch_loss, "train/lr": lr_t},
                            step=step,
                        )
                        logger.debug(
                            "step=%d  loss=%.4f  lr=%.6f", step, batch_loss, lr_t
                        )

                avg_loss = epoch_loss / max(len(loader), 1)
                elapsed = time.time() - epoch_start
                logger.info(
                    "Epoch %d/%d — avg_loss=%.4f  time=%.1fs",
                    epoch, cfg.epochs, avg_loss, elapsed,
                )
                mlflow.log_metrics(
                    {"epoch/avg_loss": avg_loss, "epoch/elapsed_s": elapsed},
                    step=epoch,
                )

                # Checkpoint best model (by training loss — no test leakage)
                if avg_loss < best_loss:
                    best_loss = avg_loss
                    ckpt_path = Path(cfg.checkpoint_dir) / "best_model.pt"
                    torch.save(
                        {
                            "epoch": epoch,
                            "model_state": model.state_dict(),
                            "vocab_size": vocab.size,
                            "embedding_dim": cfg.embedding_dim,
                            "loss": best_loss,
                        },
                        ckpt_path,
                    )
                    mlflow.log_artifact(str(ckpt_path), artifact_path="checkpoints")

            mlflow.log_metric("final/best_loss", best_loss)
            # Log the model itself
            mlflow.pytorch.log_model(model, artifact_path="word2vec_model")

        logger.info("Training complete. Best loss=%.4f  run_id=%s", best_loss, run_id)
        return model, vocab

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _resolve_device(device_str: str) -> torch.device:
        if device_str == "auto":
            if torch.cuda.is_available():
                return torch.device("cuda")
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return torch.device("mps")
            return torch.device("cpu")
        return torch.device(device_str)

    @staticmethod
    def _params_dict(cfg: Word2VecConfig, vocab: Vocabulary, n_pairs: int) -> Dict:
        return {
            "embedding_dim":        cfg.embedding_dim,
            "window_size":          cfg.window_size,
            "num_negatives":        cfg.num_negatives,
            "neg_sampling_power":   cfg.neg_sampling_power,
            "subsample_threshold":  cfg.subsample_threshold,
            "min_count":            cfg.min_count,
            "max_vocab_size":       cfg.max_vocab_size,
            "epochs":               cfg.epochs,
            "batch_size":           cfg.batch_size,
            "learning_rate":        cfg.learning_rate,
            "min_lr":               cfg.min_lr,
            "vocab_size":           vocab.size,
            "n_training_pairs":     n_pairs,
            "seed":                 cfg.seed,
        }
