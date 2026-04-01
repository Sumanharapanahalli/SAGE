"""Corpus loading, skip-gram pair generation, and PyTorch Dataset."""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import Dataset

from .vocabulary import Vocabulary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in sample corpus (royalty / geography / grammar analogies guaranteed)
# ---------------------------------------------------------------------------
_SAMPLE_CORPUS = """\
The king ruled the kingdom with wisdom and justice. The queen was beloved by all the people
in the land. A man walked through the forest searching for his family. The woman carried
her child safely home through the dark forest path at night.

In Paris, the beautiful capital of France, millions of people gathered to celebrate the
national holiday. Berlin is the proud capital of Germany where history and culture meet.
London stands as the ancient capital of England, a city of bridges and museums.
Rome serves as Italy's eternal capital built upon seven hills overlooking the Tiber river.

The prince inherited the throne after his father the king passed away peacefully.
The princess married a duke from a neighboring kingdom ruled wisely by a duchess.
A boy ran quickly through the fields while a girl read books under the old oak tree.

Dogs are loyal animals that serve as faithful companions to humans everywhere.
Cats are independent creatures that hunt mice and sleep in warm sunny spots.

A computer program runs complex algorithms to process large amounts of data efficiently.
The software engineer wrote clean readable code that solved difficult real-world problems.
Machine learning models learn statistical patterns from large training datasets automatically.
Deep neural networks excel at image recognition, natural language processing, and speech tasks.

The athlete ran faster than ever before, breaking the world record at the Olympic games.
Scientists discovered a new planet orbiting a distant star in the Milky Way galaxy.
The doctor prescribed medicine to the patient who was slowly recovering from surgery.

The man became a great king after many years of learning wisdom from advisors.
The woman became queen after marrying the king in a grand ceremony attended by nobles.
Every man and woman in the kingdom worked hard to build a prosperous society together.

France is a country in western Europe known for its cuisine, art, and fashion worldwide.
Germany is a powerful nation in central Europe with a strong manufacturing economy.
England is part of the United Kingdom located on an island in the North Atlantic ocean.
Italy is a Mediterranean country famous for its food, art, architecture, and ancient history.
Europe is a continent home to many diverse cultures, languages, and historical civilizations.

Paris is to France as London is to England and Berlin is to Germany and Rome is to Italy.
The king is to the man as the queen is to the woman in the royal family hierarchy.
A prince is to a king as a princess is to a queen in matters of royal succession.

Good students get better grades than average students through hard work and dedication.
Bad habits become worse over time if they are not corrected with discipline and effort.
Big cities grow bigger every decade as more people move from rural areas seeking opportunity.
Small towns become smaller when young people leave to find jobs in larger urban centers.
Fast runners finish races faster than slow runners who struggle to maintain their pace.
Slow walkers walk slower than fast walkers on busy city streets during rush hour.

Dogs run quickly while cats walk slowly through the neighborhood streets at midnight.
The man runs every morning while the woman walks her dog in the park after dinner.
He walked to the store yesterday but she runs to work every single morning.
They talked for hours about politics and he walked home thinking about what was said.

The dollar is the currency used in the USA for all financial transactions daily.
The euro is the common currency used across Europe by many different member nations.
The pound is the traditional currency of England used since medieval times historically.
The yen is Japan's currency used throughout Asia for international trade and commerce.

A writer writes novels and the teacher teaches students in classrooms filled with books.
The baker bakes bread every morning while the farmer grows wheat in the fertile fields.
Engineers engineer solutions to difficult technical problems using mathematics and science.
Scientists study natural phenomena to understand how the physical world around us works.

King Arthur ruled Camelot with his knights who were known for their bravery and honor.
Queen Elizabeth ruled England for many decades and was deeply respected by her subjects.
The man in the story became king after proving his worth in battle against the enemy.
The woman in the legend became the most powerful queen the kingdom had ever known.

Paris hosted the Olympic games and attracted athletes from France and across the world.
Berlin was divided for decades but Germany reunified and the city became whole again.
London bridge is falling down but England remains strong and united as a proud nation.
The streets of Rome are paved with ancient stones from Italy's glorious historical past.

He is running to the store because she asked him to buy milk and bread for dinner.
They are going to Paris next summer to visit the museums and eat traditional French food.
She has been living in London since moving from the countryside of England last year.
We visited Rome last spring and fell in love with the beauty of Italy's ancient city.
""" * 8   # repeat to increase training signal for rare words

# ---------------------------------------------------------------------------


def load_corpus(path: Optional[str] = None) -> List[str]:
    """Load and tokenise a text corpus.

    Priority order:
      1. ``path`` (plain-text file) if provided
      2. NLTK Brown + Reuters corpora  (downloaded automatically)
      3. Built-in sample corpus

    Returns a flat list of lowercase alphabetic tokens.
    """
    if path and os.path.isfile(path):
        logger.info("Loading corpus from file: %s", path)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return _tokenise(text)

    try:
        import nltk

        for resource in ("brown", "reuters", "punkt_tab"):
            try:
                nltk.data.find(f"corpora/{resource}" if resource != "punkt_tab"
                               else f"tokenizers/{resource}")
            except LookupError:
                nltk.download(resource, quiet=True)

        from nltk.corpus import brown, reuters

        words: List[str] = []
        words.extend(w.lower() for w in brown.words() if w.isalpha())
        words.extend(w.lower() for w in reuters.words() if w.isalpha())
        logger.info("Loaded NLTK corpora: %d tokens", len(words))
        return words

    except Exception as exc:  # noqa: BLE001
        logger.warning("NLTK load failed (%s); falling back to built-in corpus.", exc)
        return _tokenise(_SAMPLE_CORPUS)


def _tokenise(text: str) -> List[str]:
    """Lowercase + keep only alphabetic tokens."""
    return re.findall(r"[a-z]+", text.lower())


# ---------------------------------------------------------------------------
# Skip-gram pair generation
# ---------------------------------------------------------------------------

def build_skipgram_pairs(
    token_ids: List[int],
    window_size: int = 5,
) -> List[Tuple[int, int]]:
    """Generate (center, context) index pairs using a dynamic window.

    The actual window width is sampled uniformly in [1, window_size] per
    center word, exactly as in the original word2vec implementation.
    """
    pairs: List[Tuple[int, int]] = []
    n = len(token_ids)

    for i, center in enumerate(token_ids):
        w = np.random.randint(1, window_size + 1)
        lo = max(0, i - w)
        hi = min(n, i + w + 1)
        for j in range(lo, hi):
            if j != i:
                pairs.append((center, token_ids[j]))

    logger.debug("Generated %d skip-gram pairs from %d tokens", len(pairs), n)
    return pairs


# ---------------------------------------------------------------------------
# PyTorch Dataset
# ---------------------------------------------------------------------------

class SkipGramDataset(Dataset):
    """PyTorch Dataset for skip-gram with negative sampling.

    Each item: (center_idx, context_idx, neg_indices[num_negatives])

    NOTE: negatives are drawn at __getitem__ time so each epoch sees
    different negatives — matching the stochastic nature of the original.
    """

    def __init__(
        self,
        pairs: List[Tuple[int, int]],
        vocab: Vocabulary,
        num_negatives: int = 5,
    ) -> None:
        super().__init__()
        self.centers = np.array([p[0] for p in pairs], dtype=np.int64)
        self.contexts = np.array([p[1] for p in pairs], dtype=np.int64)
        self.vocab = vocab
        self.num_negatives = num_negatives

    def __len__(self) -> int:
        return len(self.centers)

    def __getitem__(self, idx: int):
        center = int(self.centers[idx])
        context = int(self.contexts[idx])
        negatives = self.vocab.sample_negatives(center, self.num_negatives)

        return (
            torch.tensor(center,   dtype=torch.long),
            torch.tensor(context,  dtype=torch.long),
            torch.tensor(negatives, dtype=torch.long),
        )
