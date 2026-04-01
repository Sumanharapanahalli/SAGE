"""Configuration for Word2Vec skip-gram training."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Word2VecConfig:
    # ── Model ────────────────────────────────────────────────────────────────
    embedding_dim: int = 100

    # ── Skip-gram window / negatives ─────────────────────────────────────────
    window_size: int = 5
    num_negatives: int = 5
    neg_sampling_power: float = 0.75   # unigram^power for negative table

    # ── Subsampling of frequent words ─────────────────────────────────────────
    subsample_threshold: float = 1e-3  # t in Mikolov 2013

    # ── Vocabulary ────────────────────────────────────────────────────────────
    min_count: int = 5
    max_vocab_size: int = 30_000

    # ── Training ──────────────────────────────────────────────────────────────
    epochs: int = 5
    batch_size: int = 512
    learning_rate: float = 0.025
    min_lr: float = 1e-4            # linear decay floor

    # ── Data ──────────────────────────────────────────────────────────────────
    corpus_path: Optional[str] = None  # None → NLTK Brown + Reuters

    # ── Evaluation (analogy test quadruples: a, b, c, expected_d) ────────────
    analogy_tests: List[Tuple[str, str, str, str]] = field(
        default_factory=lambda: [
            # Semantic – royalty
            ("king",   "man",    "woman",  "queen"),
            ("king",   "queen",  "man",    "woman"),
            # Semantic – capitals
            ("paris",  "france", "berlin", "germany"),
            ("paris",  "france", "london", "england"),
            ("paris",  "france", "rome",   "italy"),
            # Semantic – currency
            ("dollar", "usa",    "euro",   "europe"),
            # Syntactic – comparative
            ("good",   "better", "bad",    "worse"),
            ("big",    "bigger", "small",  "smaller"),
            ("fast",   "faster", "slow",   "slower"),
            # Syntactic – past tense
            ("run",    "ran",    "go",     "went"),
            ("walk",   "walked", "talk",   "talked"),
        ]
    )

    # ── MLflow ────────────────────────────────────────────────────────────────
    experiment_name: str = "word2vec_skipgram_ns"
    mlflow_tracking_uri: str = "mlruns"
    log_every_n_steps: int = 500

    # ── Checkpointing ─────────────────────────────────────────────────────────
    checkpoint_dir: str = "checkpoints"
    save_best_only: bool = True

    # ── Visualization ─────────────────────────────────────────────────────────
    tsne_n_words: int = 200
    tsne_perplexity: int = 30
    tsne_save_path: str = "tsne_embeddings.png"

    # ── Device ────────────────────────────────────────────────────────────────
    device: str = "auto"   # "auto" | "cpu" | "cuda" | "mps"

    # ── Reproducibility ───────────────────────────────────────────────────────
    seed: int = 42
