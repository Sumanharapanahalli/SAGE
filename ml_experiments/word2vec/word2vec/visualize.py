"""t-SNE visualisation of word embeddings with semantic-category colouring."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from sklearn.manifold import TSNE

from .model import Word2Vec
from .vocabulary import Vocabulary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Semantic word groups for colouring
# ---------------------------------------------------------------------------
WORD_GROUPS: Dict[str, List[str]] = {
    "royalty":    ["king", "queen", "prince", "princess", "duke", "duchess",
                   "throne", "kingdom", "noble", "lord"],
    "gender":     ["man", "woman", "boy", "girl", "male", "female",
                   "father", "mother", "son", "daughter"],
    "capitals":   ["paris", "london", "berlin", "rome", "madrid", "moscow",
                   "tokyo", "beijing", "washington", "sydney"],
    "countries":  ["france", "england", "germany", "italy", "spain", "russia",
                   "japan", "china", "usa", "australia"],
    "animals":    ["dog", "cat", "horse", "cow", "bird", "fish",
                   "lion", "tiger", "wolf", "bear"],
    "adjectives": ["good", "bad", "big", "small", "fast", "slow",
                   "hot", "cold", "hard", "soft"],
}

GROUP_COLOURS: Dict[str, str] = {
    "royalty":    "#e74c3c",   # red
    "gender":     "#3498db",   # blue
    "capitals":   "#2ecc71",   # green
    "countries":  "#f39c12",   # orange
    "animals":    "#9b59b6",   # purple
    "adjectives": "#1abc9c",   # teal
    "other":      "#95a5a6",   # grey
}


# ---------------------------------------------------------------------------

def _select_words(
    vocab: Vocabulary,
    n_words: int = 200,
) -> Tuple[List[str], List[int], List[str]]:
    """Select words to plot: prioritise semantic groups, pad with top-freq words."""
    selected: List[str] = []
    group_labels: List[str] = []

    # First: include words from semantic groups (in vocabulary)
    for group, words in WORD_GROUPS.items():
        for w in words:
            if w in vocab and w not in selected:
                selected.append(w)
                group_labels.append(group)

    # Pad with high-frequency vocabulary words (skip PAD/UNK)
    already = set(selected)
    for idx in range(2, min(vocab.size, 5000)):
        if len(selected) >= n_words:
            break
        w = vocab.decode(idx)
        if w not in already and w.isalpha() and len(w) > 2:
            selected.append(w)
            group_labels.append("other")

    indices = [vocab.encode(w) for w in selected]
    return selected, indices, group_labels


def tsne_plot(
    model: Word2Vec,
    vocab: Vocabulary,
    n_words: int = 200,
    perplexity: int = 30,
    save_path: str = "tsne_embeddings.png",
    annotate_groups: Optional[List[str]] = None,
    figsize: Tuple[int, int] = (14, 10),
) -> str:
    """Generate and save a t-SNE plot of word embeddings.

    Parameters
    ----------
    model        : trained Word2Vec model
    vocab        : corresponding Vocabulary
    n_words      : total words to embed (semantic groups + high-freq)
    perplexity   : t-SNE perplexity (lower = more local structure)
    save_path    : output file path
    annotate_groups : only annotate words from these groups (None = all groups)
    figsize      : matplotlib figure size

    Returns
    -------
    save_path    : path to saved PNG
    """
    if annotate_groups is None:
        annotate_groups = list(WORD_GROUPS.keys())

    words, indices, group_labels = _select_words(vocab, n_words)
    n = len(words)

    if n < 5:
        logger.warning("Too few words (%d) to generate t-SNE plot.", n)
        return save_path

    # ── Embeddings ────────────────────────────────────────────────────────────
    W = model.get_embeddings()        # (V, D) — L2-normalised
    X = W[np.array(indices)]          # (n, D)

    # ── t-SNE ─────────────────────────────────────────────────────────────────
    logger.info("Running t-SNE on %d words (perplexity=%d)…", n, perplexity)
    actual_perp = min(perplexity, max(5, n // 5))
    tsne = TSNE(
        n_components=2,
        perplexity=actual_perp,
        n_iter=1000,
        learning_rate="auto",
        init="pca",
        random_state=42,
        verbose=0,
    )
    X2d = tsne.fit_transform(X)     # (n, 2)

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=figsize, facecolor="#1a1a2e")
    ax.set_facecolor("#16213e")

    for i, (word, group) in enumerate(zip(words, group_labels)):
        colour = GROUP_COLOURS.get(group, GROUP_COLOURS["other"])
        ax.scatter(X2d[i, 0], X2d[i, 1], c=colour, s=20, alpha=0.8, zorder=2)

        if group in annotate_groups and group != "other":
            ax.annotate(
                word,
                (X2d[i, 0], X2d[i, 1]),
                fontsize=7,
                color=colour,
                alpha=0.9,
                xytext=(3, 3),
                textcoords="offset points",
                zorder=3,
            )

    # Draw analogy lines (king-man+woman=queen style arrows)
    _draw_analogy_arrow(
        ax, X2d, words,
        a="king", b="man", c="woman", d="queen",
        colour="#ffd700",
    )

    # Legend
    patches = [
        mpatches.Patch(color=GROUP_COLOURS[g], label=g.capitalize())
        for g in list(WORD_GROUPS.keys()) + ["other"]
        if g in set(group_labels)
    ]
    ax.legend(
        handles=patches,
        loc="lower right",
        framealpha=0.3,
        facecolor="#0f3460",
        edgecolor="#e94560",
        labelcolor="white",
        fontsize=9,
    )

    ax.set_title(
        f"Word2Vec Embeddings — t-SNE ({n} words)",
        color="white",
        fontsize=13,
        pad=12,
    )
    ax.tick_params(colors="#555577")
    ax.spines[:].set_color("#333355")

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    logger.info("t-SNE plot saved → %s", save_path)
    return save_path


def _draw_analogy_arrow(
    ax: plt.Axes,
    X2d: np.ndarray,
    words: List[str],
    a: str, b: str, c: str, d: str,
    colour: str = "#ffd700",
) -> None:
    """Draw a labelled arrow illustrating an analogy relationship."""
    for w in (a, b, c, d):
        if w not in words:
            return

    def xy(w: str) -> Tuple[float, float]:
        i = words.index(w)
        return float(X2d[i, 0]), float(X2d[i, 1])

    ax.annotate(
        "",
        xy=xy(d), xytext=xy(c),
        arrowprops=dict(
            arrowstyle="->",
            color=colour,
            lw=1.5,
            connectionstyle="arc3,rad=0.1",
        ),
        zorder=5,
    )
    mx = (xy(c)[0] + xy(d)[0]) / 2
    my = (xy(c)[1] + xy(d)[1]) / 2
    ax.text(
        mx, my,
        f"{a}−{b}+{c}={d}",
        fontsize=7,
        color=colour,
        ha="center",
        va="bottom",
        zorder=6,
    )
