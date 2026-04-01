"""Word analogy evaluation (3CosAdd) with stratified train/val/test splits."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import mlflow
import numpy as np
from sklearn.model_selection import train_test_split

from .model import Word2Vec
from .vocabulary import Vocabulary

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AnalogyResult:
    quadruple: Tuple[str, str, str, str]  # (a, b, c, expected_d)
    predicted: str
    expected: str
    correct: bool
    rank: int            # rank of expected_d in cosine-similarity list
    top5: List[str] = field(default_factory=list)


@dataclass
class EvalReport:
    split: str
    n_total: int
    n_valid: int         # quadruples where all 4 words are in vocabulary
    n_correct: int
    accuracy: float
    top5_accuracy: float
    mrr: float           # mean reciprocal rank
    results: List[AnalogyResult] = field(default_factory=list)

    def log_to_mlflow(self, prefix: str = "eval") -> None:
        mlflow.log_metrics(
            {
                f"{prefix}/{self.split}/accuracy":      self.accuracy,
                f"{prefix}/{self.split}/top5_accuracy": self.top5_accuracy,
                f"{prefix}/{self.split}/mrr":           self.mrr,
                f"{prefix}/{self.split}/n_valid":       self.n_valid,
                f"{prefix}/{self.split}/n_correct":     self.n_correct,
            }
        )

    def __str__(self) -> str:
        return (
            f"[{self.split:5s}] acc={self.accuracy:.3f}  "
            f"top5={self.top5_accuracy:.3f}  mrr={self.mrr:.3f}  "
            f"({self.n_correct}/{self.n_valid} valid, {self.n_total} total)"
        )


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class AnalogyEvaluator:
    """Evaluates word embeddings on the word analogy task.

    Implements the 3CosAdd method:
        d* = argmax_w [ cos(w, c) − cos(w, a) + cos(w, b) ]
           = argmax_w [ cos(w,  c − a + b) ]   (after L2-normalisation)

    The analogy quadruples are stratified by *category* (semantic vs.
    syntactic) to ensure balanced train / val / test splits.
    """

    # Hard analogy pairs beyond user-supplied config — used when the model
    # is evaluated outside of training to keep evaluation honest.
    SEMANTIC_PAIRS: List[Tuple[str, str, str, str]] = [
        ("king",   "man",    "woman",  "queen"),
        ("king",   "queen",  "man",    "woman"),
        ("paris",  "france", "berlin", "germany"),
        ("paris",  "france", "london", "england"),
        ("paris",  "france", "rome",   "italy"),
        ("berlin", "germany","london", "england"),
        ("london", "england","paris",  "france"),
        ("rome",   "italy",  "paris",  "france"),
    ]

    SYNTACTIC_PAIRS: List[Tuple[str, str, str, str]] = [
        ("good",   "better", "bad",    "worse"),
        ("big",    "bigger", "small",  "smaller"),
        ("fast",   "faster", "slow",   "slower"),
        ("run",    "ran",    "go",     "went"),
        ("walk",   "walked", "talk",   "talked"),
        ("king",   "kings",  "queen",  "queens"),
        ("man",    "men",    "woman",  "women"),
        ("dog",    "dogs",   "cat",    "cats"),
    ]

    def __init__(
        self,
        model: Word2Vec,
        vocab: Vocabulary,
        extra_pairs: Optional[List[Tuple[str, str, str, str]]] = None,
        seed: int = 42,
    ) -> None:
        self.model = model
        self.vocab = vocab
        self.seed = seed

        all_pairs = self.SEMANTIC_PAIRS + self.SYNTACTIC_PAIRS
        if extra_pairs:
            all_pairs = all_pairs + extra_pairs

        # Deduplicate while preserving order
        seen = set()
        unique_pairs = []
        for p in all_pairs:
            key = tuple(p)
            if key not in seen:
                seen.add(key)
                unique_pairs.append(p)

        self._pairs = unique_pairs
        # Category label: 0 = semantic, 1 = syntactic (for stratification)
        n_sem = len(self.SEMANTIC_PAIRS)
        self._categories = (
            [0] * n_sem
            + [1] * len(self.SYNTACTIC_PAIRS)
            + [0 if extra_pairs and i < len(extra_pairs) // 2 else 1
               for i, _ in enumerate(extra_pairs or [])]
        )[: len(unique_pairs)]

    # ── Splits ────────────────────────────────────────────────────────────────

    def _stratified_splits(
        self,
    ) -> Tuple[List, List, List]:
        """Return train / val / test splits stratified by category.

        Split sizes: 60 / 20 / 20 %.  If too few samples per stratum,
        falls back to random split.
        """
        n = len(self._pairs)
        if n < 6:
            # Not enough data — use all as test
            return [], [], self._pairs

        indices = list(range(n))
        try:
            train_idx, tmp_idx = train_test_split(
                indices,
                test_size=0.40,
                stratify=self._categories,
                random_state=self.seed,
            )
            # Stratify labels for the temp split
            tmp_labels = [self._categories[i] for i in tmp_idx]
            val_idx, test_idx = train_test_split(
                tmp_idx,
                test_size=0.50,
                stratify=tmp_labels,
                random_state=self.seed,
            )
        except ValueError:
            # Fallback: random split (too few samples per class)
            rng = np.random.default_rng(self.seed)
            rng.shuffle(indices)
            t1 = int(0.6 * n)
            t2 = int(0.8 * n)
            train_idx, val_idx, test_idx = indices[:t1], indices[t1:t2], indices[t2:]

        return (
            [self._pairs[i] for i in train_idx],
            [self._pairs[i] for i in val_idx],
            [self._pairs[i] for i in test_idx],
        )

    # ── Core evaluation ───────────────────────────────────────────────────────

    def evaluate_pairs(
        self,
        pairs: List[Tuple[str, str, str, str]],
        split_name: str,
    ) -> EvalReport:
        """Evaluate a list of analogy quadruples."""
        results: List[AnalogyResult] = []
        n_valid = 0
        n_correct = 0
        reciprocal_ranks: List[float] = []
        top5_hits = 0

        W = self.model.get_embeddings()  # (V, D) — already L2-normalised

        for a, b, c, expected_d in pairs:
            # Skip if any word is OOV
            if any(w not in self.vocab for w in (a, b, c, expected_d)):
                logger.debug("Skipping OOV quadruple: %s", (a, b, c, expected_d))
                continue
            n_valid += 1

            try:
                top_candidates = self.model.analogy(a, b, c, self.vocab, topk=10)
            except KeyError:
                continue

            top_words = [w for w, _ in top_candidates]
            predicted = top_words[0] if top_words else ""
            correct = predicted == expected_d

            # Rank of expected answer (1-indexed, ∞ if not in top-10)
            if expected_d in top_words:
                rank = top_words.index(expected_d) + 1
                reciprocal_ranks.append(1.0 / rank)
            else:
                rank = 9999
                reciprocal_ranks.append(0.0)

            if correct:
                n_correct += 1
            if expected_d in top_words[:5]:
                top5_hits += 1

            results.append(
                AnalogyResult(
                    quadruple=(a, b, c, expected_d),
                    predicted=predicted,
                    expected=expected_d,
                    correct=correct,
                    rank=rank,
                    top5=top_words[:5],
                )
            )

        accuracy     = n_correct / max(n_valid, 1)
        top5_accuracy = top5_hits / max(n_valid, 1)
        mrr          = float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0

        return EvalReport(
            split=split_name,
            n_total=len(pairs),
            n_valid=n_valid,
            n_correct=n_correct,
            accuracy=accuracy,
            top5_accuracy=top5_accuracy,
            mrr=mrr,
            results=results,
        )

    # ── Full evaluation pipeline ──────────────────────────────────────────────

    def run(self) -> Dict[str, EvalReport]:
        """Run analogy evaluation on train / val / test splits."""
        train_pairs, val_pairs, test_pairs = self._stratified_splits()

        reports: Dict[str, EvalReport] = {}
        for split_name, pairs in (
            ("train", train_pairs),
            ("val",   val_pairs),
            ("test",  test_pairs),
        ):
            if not pairs:
                continue
            report = self.evaluate_pairs(pairs, split_name)
            reports[split_name] = report
            logger.info(str(report))

        # Print detailed results for the test split
        if "test" in reports:
            self._print_detailed(reports["test"])

        return reports

    @staticmethod
    def _print_detailed(report: EvalReport) -> None:
        logger.info("\n=== Analogy Test Results ===")
        for r in report.results:
            status = "✓" if r.correct else "✗"
            a, b, c, d = r.quadruple
            logger.info(
                "%s  %s − %s + %s = %s  (predicted: %s, rank: %s)",
                status, a, b, c, d, r.predicted,
                r.rank if r.rank < 9999 else "OOT",
            )
        logger.info(
            "\nSummary: acc=%.3f  top5=%.3f  mrr=%.3f",
            report.accuracy, report.top5_accuracy, report.mrr,
        )
