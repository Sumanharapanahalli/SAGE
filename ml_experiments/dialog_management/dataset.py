"""
Dialog Management Dataset
=========================
Handles MultiWOZ-style data loading, tokenisation, and collation.

KEY GUARANTEE: The tokenizer is loaded from a pretrained checkpoint and is
NEVER fitted on data — there is no vocabulary estimation step that could
leak test-set statistics into training.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import DistilBertTokenizerFast

logger = logging.getLogger(__name__)


class DialogDataset(Dataset):
    """
    PyTorch Dataset for dialog act classification.

    Each sample packs the current utterance with up to `max_history_turns`
    prior turns into a single DistilBERT sequence:

        [CLS] <history turn 1> [SEP] ... [SEP] <current utterance> [SEP]

    Args:
        df:                 DataFrame with columns: history, current_utterance, label
        encoder_name:       HuggingFace model name — tokenizer loaded from hub
        max_seq_len:        Maximum subword token length (padding/truncation applied)
        max_history_turns:  Maximum number of history turns to include
    """

    REQUIRED_COLS = {"history", "current_utterance", "label"}

    def __init__(
        self,
        df: pd.DataFrame,
        encoder_name: str = "distilbert-base-uncased",
        max_seq_len: int = 128,
        max_history_turns: int = 5,
    ) -> None:
        missing = self.REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        self.df = df.reset_index(drop=True)
        self.max_seq_len = max_seq_len
        self.max_history_turns = max_history_turns

        # Tokenizer loaded from pretrained checkpoint — no fitting on corpus
        self.tokenizer = DistilBertTokenizerFast.from_pretrained(encoder_name)
        logger.info(
            "DialogDataset: %d samples | vocab_size=%d | max_seq_len=%d",
            len(df),
            self.tokenizer.vocab_size,
            max_seq_len,
        )

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        row = self.df.iloc[idx]

        # Truncate history to last N turns to limit sequence length
        history_turns: List[str] = [
            t.strip()
            for t in str(row["history"]).split("[SEP]")
            if t.strip()
        ][-self.max_history_turns :]

        history_text = " [SEP] ".join(history_turns)
        current_text = str(row["current_utterance"]).strip()
        full_text = f"{history_text} [SEP] {current_text}" if history_text else current_text

        encoding = self.tokenizer(
            full_text,
            max_length=self.max_seq_len,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].squeeze(0),       # (seq_len,)
            "attention_mask": encoding["attention_mask"].squeeze(0),  # (seq_len,)
            "labels": torch.tensor(int(row["label"]), dtype=torch.long),
        }


def collate_fn(batch: List[Dict[str, torch.Tensor]]) -> Dict[str, torch.Tensor]:
    """Stack a list of sample dicts into batched tensors."""
    return {
        "input_ids": torch.stack([b["input_ids"] for b in batch]),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch]),
        "labels": torch.stack([b["labels"] for b in batch]),
    }


# ── Synthetic MultiWOZ-style data generator ──────────────────────────────────

DIALOG_ACTS = [
    "inform", "request", "confirm", "deny", "greet",
    "bye", "book", "recommend", "nooffer", "offerbook",
    "offerbooked", "reqmore", "welcome", "select", "nobook",
]

DOMAINS = [
    "restaurant", "hotel", "taxi", "train",
    "attraction", "hospital", "police",
]

_TEMPLATES = {
    "inform":      "I can provide {domain} information for you.",
    "request":     "What {domain} details do you need?",
    "confirm":     "Would you like to confirm the {domain} booking?",
    "deny":        "I'm sorry, that {domain} is not available.",
    "greet":       "Hello! How can I help you today?",
    "bye":         "Thank you for using our service. Goodbye!",
    "book":        "I'll book the {domain} for you right away.",
    "recommend":   "I recommend this {domain} option.",
    "nooffer":     "Unfortunately no {domain} matches your criteria.",
    "offerbook":   "Would you like me to book this {domain}?",
    "offerbooked": "Your {domain} has been booked successfully.",
    "reqmore":     "Is there anything else I can help you with?",
    "welcome":     "You're welcome! Anything else?",
    "select":      "Please select a {domain} from the options.",
    "nobook":      "I cannot book this {domain} at the moment.",
}

# Simulated class imbalance (mirrors real MultiWOZ distributions)
_ACT_WEIGHTS = np.array([
    0.20, 0.15, 0.10, 0.05, 0.08, 0.05, 0.08,
    0.08, 0.03, 0.04, 0.04, 0.04, 0.02, 0.02, 0.02,
])
_ACT_PROBS = _ACT_WEIGHTS / _ACT_WEIGHTS.sum()


def generate_synthetic_dataset(
    n_samples: int = 2000,
    seed: int = 42,
    user_groups: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Generate a synthetic MultiWOZ-style dataset for demonstration purposes.
    Replace this function with your real data loader in production.

    Returns:
        DataFrame with columns:
            dialog_id, turn_id, history, current_utterance,
            dialog_act, label, domain, user_group
    """
    rng = np.random.default_rng(seed)
    user_groups = user_groups or ["group_a", "group_b", "group_c"]
    rows = []

    for i in range(n_samples):
        domain = rng.choice(DOMAINS)
        act = rng.choice(DIALOG_ACTS, p=_ACT_PROBS)
        history_len = rng.integers(1, 6)

        history_turns = [
            f"[{rng.choice(['user', 'sys'])}] "
            + _TEMPLATES[rng.choice(DIALOG_ACTS)].format(domain=domain)
            for _ in range(history_len)
        ]

        rows.append({
            "dialog_id":         f"dialog_{i:05d}",
            "turn_id":           int(rng.integers(1, 10)),
            "history":           " [SEP] ".join(history_turns),
            "current_utterance": _TEMPLATES[act].format(domain=domain),
            "dialog_act":        act,
            "domain":            domain,
            "user_group":        rng.choice(user_groups),
        })

    df = pd.DataFrame(rows)
    logger.info("Generated synthetic dataset: %d samples, %d acts", len(df), df["dialog_act"].nunique())
    return df
