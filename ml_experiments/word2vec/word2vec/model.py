"""Word2Vec skip-gram model with negative-sampling loss."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .vocabulary import Vocabulary

logger = logging.getLogger(__name__)


class Word2Vec(nn.Module):
    """Skip-gram Word2Vec with negative-sampling loss.

    Architecture
    ────────────
    • ``in_embeddings``  — centre-word embedding matrix  (V × D)
    • ``out_embeddings`` — context-word embedding matrix (V × D)

    The two matrices are intentionally separate (as in the original paper).
    At inference time only ``in_embeddings`` is exposed via
    :meth:`get_embeddings`.

    Loss (per batch)
    ────────────────
    L = -[ log σ(v_c · v_o) + Σ_k log σ(−v_c · v_k) ]

    where v_c = centre embedding, v_o = context embedding,
    v_k = k-th negative embedding.
    """

    def __init__(self, vocab_size: int, embedding_dim: int) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim

        self.in_embeddings = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.out_embeddings = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self._init_weights()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_weights(self) -> None:
        """Uniform init for in-embeddings; zeros for out-embeddings (Mikolov)."""
        half = 0.5 / self.embedding_dim
        nn.init.uniform_(self.in_embeddings.weight, -half, half)
        nn.init.zeros_(self.out_embeddings.weight)

    # ── Forward ───────────────────────────────────────────────────────────────

    def forward(
        self,
        center: torch.Tensor,      # (B,)
        context: torch.Tensor,     # (B,)
        negatives: torch.Tensor,   # (B, K)
    ) -> torch.Tensor:
        """Return mean negative-sampling loss over the batch."""
        # (B, D)
        v_c = self.in_embeddings(center)
        # (B, D)
        v_o = self.out_embeddings(context)
        # (B, K, D)
        v_neg = self.out_embeddings(negatives)

        # Positive score:  σ(v_c · v_o)
        pos_score = (v_c * v_o).sum(dim=1)          # (B,)
        pos_loss = F.logsigmoid(pos_score)           # (B,)

        # Negative scores: σ(−v_c · v_k)
        # bmm: (B, 1, D) × (B, D, K) → (B, 1, K) → squeeze → (B, K)
        neg_score = torch.bmm(
            v_c.unsqueeze(1),           # (B, 1, D)
            v_neg.permute(0, 2, 1),     # (B, D, K)
        ).squeeze(1)                    # (B, K)
        neg_loss = F.logsigmoid(-neg_score).sum(dim=1)  # (B,)

        loss = -(pos_loss + neg_loss).mean()
        return loss

    # ── Inference helpers ─────────────────────────────────────────────────────

    @torch.no_grad()
    def get_embeddings(self) -> np.ndarray:
        """Return normalised in-embedding matrix as a NumPy array (V, D)."""
        W = self.in_embeddings.weight.data.float()
        norms = W.norm(dim=1, keepdim=True).clamp(min=1e-8)
        return (W / norms).cpu().numpy()

    @torch.no_grad()
    def most_similar(
        self,
        word: str,
        vocab: Vocabulary,
        topk: int = 10,
        exclude_special: bool = True,
    ) -> List[Tuple[str, float]]:
        """Return top-k most similar words by cosine similarity."""
        if word not in vocab:
            raise KeyError(f"'{word}' not in vocabulary")

        W = self.get_embeddings()              # (V, D) — already normalised
        idx = vocab.encode(word)
        scores = W @ W[idx]                    # (V,)
        scores[idx] = -2.0                     # exclude self

        if exclude_special:
            scores[0] = -2.0                   # PAD
            scores[1] = -2.0                   # UNK

        top_idx = np.argsort(-scores)[:topk]
        return [(vocab.decode(int(i)), float(scores[i])) for i in top_idx]

    @torch.no_grad()
    def analogy(
        self,
        a: str,
        b: str,
        c: str,
        vocab: Vocabulary,
        topk: int = 5,
    ) -> List[Tuple[str, float]]:
        """3CosAdd: find d such that  a − b + c ≈ d.

        a : b  ::  c : ?
        e.g.  king − man + woman ≈ queen
        """
        missing = [w for w in (a, b, c) if w not in vocab]
        if missing:
            raise KeyError(f"Words not in vocabulary: {missing}")

        W = self.get_embeddings()              # (V, D) — normalised
        query = W[vocab.encode(c)] - W[vocab.encode(b)] + W[vocab.encode(a)]
        query_norm = query / (np.linalg.norm(query) + 1e-8)

        scores = W @ query_norm                # (V,)
        for w in (a, b, c):
            scores[vocab.encode(w)] = -2.0    # exclude input words
        scores[0] = scores[1] = -2.0          # exclude PAD, UNK

        top_idx = np.argsort(-scores)[:topk]
        return [(vocab.decode(int(i)), float(scores[i])) for i in top_idx]
