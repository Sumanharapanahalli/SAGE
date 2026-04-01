"""Vocabulary: word ↔ index, negative-sampling table, subsampling."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

_NEG_TABLE_SIZE = 10_000_000


class Vocabulary:
    """Maps words ↔ integer indices and provides negative-sampling utilities."""

    PAD = "<PAD>"
    UNK = "<UNK>"

    def __init__(self) -> None:
        self.word2idx: Dict[str, int] = {}
        self.idx2word: Dict[int, str] = {}
        self.word_counts: Dict[str, int] = {}
        self.word_freqs: np.ndarray = np.array([], dtype=np.float32)
        self._neg_table: Optional[np.ndarray] = None
        self._neg_cursor: int = 0
        self.size: int = 0

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        tokens: List[str],
        min_count: int = 5,
        max_vocab_size: int = 30_000,
    ) -> "Vocabulary":
        """Build vocabulary from a flat token list.

        Special tokens PAD (idx=0) and UNK (idx=1) are always inserted first.
        Remaining words are ordered by descending frequency.
        """
        vocab = cls()
        counts = Counter(tokens)

        valid: List[tuple] = sorted(
            [(w, c) for w, c in counts.items() if c >= min_count],
            key=lambda x: -x[1],
        )
        # Reserve 2 slots for specials
        valid = valid[: max(0, max_vocab_size - 2)]

        for special in (cls.PAD, cls.UNK):
            idx = len(vocab.word2idx)
            vocab.word2idx[special] = idx
            vocab.idx2word[idx] = special
            vocab.word_counts[special] = 0

        for word, count in valid:
            idx = len(vocab.word2idx)
            vocab.word2idx[word] = idx
            vocab.idx2word[idx] = word
            vocab.word_counts[word] = count

        vocab.size = len(vocab.word2idx)

        # Normalised frequencies (special tokens get 0)
        total = sum(c for _, c in valid) or 1
        vocab.word_freqs = np.zeros(vocab.size, dtype=np.float32)
        for word, count in valid:
            vocab.word_freqs[vocab.word2idx[word]] = count / total

        logger.info(
            "Vocabulary: %d words (min_count=%d, total tokens=%d)",
            vocab.size,
            min_count,
            len(tokens),
        )
        return vocab

    # ── Negative-sampling table ───────────────────────────────────────────────

    def build_neg_table(self, power: float = 0.75) -> None:
        """Pre-build an alias / lookup table for fast negative sampling.

        Raises to ``power`` before normalising so rare words get sampled
        more often than their true frequency (Mikolov 2013 §2.2).
        """
        freqs = self.word_freqs.copy()
        freqs[:2] = 0.0           # never sample PAD or UNK as negatives
        powered = freqs ** power
        total = powered.sum()
        if total == 0:
            raise ValueError("All word frequencies are zero — cannot build neg table.")
        powered /= total

        self._neg_table = np.random.choice(
            self.size, size=_NEG_TABLE_SIZE, p=powered, replace=True
        ).astype(np.int32)
        self._neg_cursor = 0
        logger.info("Negative-sampling table: %d entries", _NEG_TABLE_SIZE)

    def sample_negatives(self, center_idx: int, n: int) -> np.ndarray:
        """Return *n* negative indices, guaranteed ≠ center_idx and ≠ PAD/UNK."""
        if self._neg_table is None:
            raise RuntimeError("Call build_neg_table() first.")

        out = []
        table = self._neg_table
        sz = len(table)
        cur = self._neg_cursor

        while len(out) < n:
            idx = int(table[cur % sz])
            cur += 1
            if idx != center_idx and idx > 1:
                out.append(idx)

        self._neg_cursor = cur % sz
        return np.array(out, dtype=np.int64)

    # ── Subsampling ───────────────────────────────────────────────────────────

    def keep_probs(self, threshold: float = 1e-3) -> np.ndarray:
        """P(keep word w) = min(1, sqrt(t / f(w)) + t / f(w)) — Mikolov 2013."""
        f = np.where(self.word_freqs > 0, self.word_freqs, 1e-10)
        ratio = threshold / f
        p = np.sqrt(ratio) + ratio
        p = np.minimum(1.0, p).astype(np.float32)
        p[:2] = 0.0   # discard PAD and UNK
        return p

    def subsample(self, tokens: List[str], threshold: float = 1e-3) -> List[str]:
        """Discard tokens proportional to their frequency (keeps rare words)."""
        p = self.keep_probs(threshold)
        unk = self.word2idx[self.UNK]
        rng = np.random.random(len(tokens))
        result = [
            t for t, r in zip(tokens, rng)
            if (idx := self.word2idx.get(t, unk)) > 1 and r < p[idx]
        ]
        logger.info(
            "Subsampling: %d → %d tokens (%.1f%% kept)",
            len(tokens),
            len(result),
            100.0 * len(result) / max(len(tokens), 1),
        )
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def encode(self, word: str) -> int:
        return self.word2idx.get(word, self.word2idx[self.UNK])

    def decode(self, idx: int) -> str:
        return self.idx2word.get(idx, self.UNK)

    def __len__(self) -> int:
        return self.size

    def __contains__(self, word: str) -> bool:
        return word in self.word2idx
