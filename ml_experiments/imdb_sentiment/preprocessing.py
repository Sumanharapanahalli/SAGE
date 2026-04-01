"""
Text preprocessing pipeline:
  lowercase → tokenize → stopword removal → lemmatization

Designed to be fitted on train data ONLY and applied to test data
to prevent data leakage.
"""
from __future__ import annotations

import re
import string
from typing import Iterable

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from sklearn.base import BaseEstimator, TransformerMixin

# Download required NLTK assets once
for _pkg in ("punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4"):
    nltk.download(_pkg, quiet=True)

_STOP_WORDS: frozenset[str] = frozenset(stopwords.words("english"))
_LEMMATIZER = WordNetLemmatizer()

# Patterns compiled once for speed
_HTML_TAG = re.compile(r"<[^>]+>")
_NON_ALPHA = re.compile(r"[^a-z\s]")


def _clean_text(text: str) -> str:
    """Strip HTML, punctuation, and digits; lowercase."""
    text = _HTML_TAG.sub(" ", text)        # remove HTML tags (IMDB has them)
    text = text.lower()
    text = _NON_ALPHA.sub(" ", text)       # keep only [a-z] + whitespace
    return text


def preprocess_text(text: str, min_token_len: int = 2) -> str:
    """
    Full preprocessing chain for a single document.

    Steps
    -----
    1. HTML / punctuation removal + lowercase
    2. Tokenization (NLTK word_tokenize)
    3. Stopword removal
    4. Lemmatization
    5. Short-token filtering  (< min_token_len chars)

    Returns a single whitespace-joined string (TF-IDF expects strings).
    """
    text = _clean_text(text)
    tokens = word_tokenize(text)
    tokens = [
        _LEMMATIZER.lemmatize(tok)
        for tok in tokens
        if tok not in _STOP_WORDS and len(tok) >= min_token_len
    ]
    return " ".join(tokens)


class TextPreprocessor(BaseEstimator, TransformerMixin):
    """
    Sklearn-compatible transformer wrapping ``preprocess_text``.

    Fit does nothing (stateless), transform applies preprocessing.
    Inheriting BaseEstimator gives get_params / set_params for free,
    which is required by sklearn Pipeline / GridSearchCV.
    """

    def __init__(self, min_token_len: int = 2) -> None:
        self.min_token_len = min_token_len

    def fit(self, X: Iterable[str], y=None) -> "TextPreprocessor":  # noqa: N803
        # Stateless — nothing to fit; returns self for pipeline chaining
        return self

    def transform(self, X: Iterable[str]) -> list[str]:  # noqa: N803
        return [preprocess_text(doc, self.min_token_len) for doc in X]
