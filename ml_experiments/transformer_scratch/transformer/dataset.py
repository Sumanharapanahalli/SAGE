"""
Data pipeline for Transformer training.

Leakage prevention contract
---------------------------
1. Train / val / test indices are split BEFORE any fitting.
2. Vocabulary is built ONLY from the training slice.
3. The same frozen vocabulary encodes val and test (unknown tokens -> <UNK>).
4. No statistics from val/test touch the training pipeline.
"""
from __future__ import annotations
import random
from collections import Counter
from functools import partial

import torch
from torch.utils.data import Dataset, DataLoader

PAD = "<PAD>"
BOS = "<BOS>"
EOS = "<EOS>"
UNK = "<UNK>"
SPECIAL_TOKENS = [PAD, BOS, EOS, UNK]


class Vocabulary:
    """
    Bidirectional token <-> integer mapping.
    Always fit ONLY on training data.
    """

    def __init__(self) -> None:
        self.token2idx: dict[str, int] = {}
        self.idx2token: dict[int, str] = {}
        for tok in SPECIAL_TOKENS:
            self._add(tok)

    def _add(self, token: str) -> None:
        if token not in self.token2idx:
            idx = len(self.token2idx)
            self.token2idx[token] = idx
            self.idx2token[idx]   = token

    def build_from_corpus(
        self,
        sentences: list[list[str]],
        min_freq:  int = 1,
    ) -> None:
        """Fit vocabulary on *training* sentences only."""
        counter: Counter[str] = Counter()
        for sent in sentences:
            counter.update(sent)
        for token, freq in counter.most_common():
            if freq >= min_freq:
                self._add(token)

    def encode(self, tokens: list[str]) -> list[int]:
        unk = self.token2idx[UNK]
        return [self.token2idx.get(t, unk) for t in tokens]

    def decode(self, indices: list[int], skip_special: bool = True) -> list[str]:
        """Convert indices back to tokens, stopping at first EOS."""
        eos_id   = self.token2idx[EOS]
        skip_ids = {self.token2idx[t] for t in SPECIAL_TOKENS} if skip_special else set()
        out: list[str] = []
        for idx in indices:
            if idx == eos_id:
                break
            if idx not in skip_ids:
                out.append(self.idx2token.get(idx, UNK))
        return out

    @property
    def pad_idx(self) -> int: return self.token2idx[PAD]
    @property
    def bos_idx(self) -> int: return self.token2idx[BOS]
    @property
    def eos_idx(self) -> int: return self.token2idx[EOS]
    def __len__(self)  -> int: return len(self.token2idx)
    def __repr__(self) -> str: return f"Vocabulary(size={len(self)})"


class Seq2SeqDataset(Dataset):
    """Pre-encoded integer sequences. No fitting happens here."""

    def __init__(
        self,
        src_sequences: list[list[int]],
        tgt_sequences: list[list[int]],
        max_src_len:   int = 128,
        max_tgt_len:   int = 128,
    ):
        assert len(src_sequences) == len(tgt_sequences)
        self.src = [s[:max_src_len] for s in src_sequences]
        self.tgt = [t[:max_tgt_len] for t in tgt_sequences]

    def __len__(self) -> int:
        return len(self.src)

    def __getitem__(self, idx: int) -> dict[str, list[int]]:
        return {"src": self.src[idx], "tgt": self.tgt[idx]}


def collate_fn(
    batch:   list[dict[str, list[int]]],
    pad_idx: int,
) -> dict[str, torch.Tensor]:
    """
    Pad sequences to uniform length within a batch.

    Teacher forcing split:
      tgt_in  = tgt[:-1]   [BOS, t1, t2, ...]   <- decoder input
      tgt_out = tgt[1:]    [t1,  t2, ..., EOS]  <- decoder target
    """
    _pad = partial(
        torch.nn.utils.rnn.pad_sequence,
        batch_first=True,
        padding_value=pad_idx,
    )
    src_padded = _pad([torch.tensor(b["src"], dtype=torch.long) for b in batch])
    tgt_padded = _pad([torch.tensor(b["tgt"], dtype=torch.long) for b in batch])
    return {
        "src":     src_padded,
        "tgt_in":  tgt_padded[:, :-1],
        "tgt_out": tgt_padded[:, 1:],
    }


def generate_synthetic_data(
    vocab_size:  int = 50,
    num_samples: int = 20_000,
    min_len:     int = 5,
    max_len:     int = 20,
    task:        str = "copy",   # "copy" | "reverse"
    seed:        int = 42,
) -> tuple[list[list[str]], list[list[str]]]:
    """
    Synthetic sequence task — standard sanity-check for transformers.

    copy:    [a, b, c] -> [a, b, c]   (should reach ~100% accuracy)
    reverse: [a, b, c] -> [c, b, a]   (tests long-range cross-attention)
    """
    rng    = random.Random(seed)
    tokens = [f"tok_{i}" for i in range(vocab_size)]
    srcs, tgts = [], []
    for _ in range(num_samples):
        length = rng.randint(min_len, max_len)
        src    = [rng.choice(tokens) for _ in range(length)]
        tgt    = src[::-1] if task == "reverse" else src[:]
        srcs.append(src)
        tgts.append(tgt)
    return srcs, tgts


def build_dataloaders(
    task:         str   = "copy",
    vocab_size:   int   = 50,
    num_samples:  int   = 20_000,
    batch_size:   int   = 128,
    max_seq_len:  int   = 30,
    train_ratio:  float = 0.80,
    val_ratio:    float = 0.10,
    num_workers:  int   = 2,
    seed:         int   = 42,
) -> tuple[DataLoader, DataLoader, DataLoader, Vocabulary, Vocabulary]:
    """
    Build train / val / test DataLoaders with zero data leakage.

    Returns
    -------
    (train_loader, val_loader, test_loader, src_vocab, tgt_vocab)
    """
    rng = random.Random(seed)

    src_sentences, tgt_sentences = generate_synthetic_data(
        vocab_size=vocab_size, num_samples=num_samples, task=task, seed=seed,
    )

    # 1. Split indices BEFORE vocabulary fitting
    indices = list(range(num_samples))
    rng.shuffle(indices)
    n_train   = int(num_samples * train_ratio)
    n_val     = int(num_samples * val_ratio)
    train_idx = indices[:n_train]
    val_idx   = indices[n_train : n_train + n_val]
    test_idx  = indices[n_train + n_val :]

    # 2. Build vocabulary on TRAINING data only
    train_src_raw = [src_sentences[i] for i in train_idx]
    train_tgt_raw = [tgt_sentences[i] for i in train_idx]

    src_vocab = Vocabulary()
    tgt_vocab = Vocabulary()
    src_vocab.build_from_corpus(train_src_raw, min_freq=1)
    tgt_vocab.build_from_corpus(train_tgt_raw, min_freq=1)

    # 3. Encode all splits with the FROZEN training vocabulary
    def _encode(idx_list: list[int]) -> tuple[list[list[int]], list[list[int]]]:
        srcs, tgts = [], []
        for i in idx_list:
            srcs.append(src_vocab.encode([BOS] + src_sentences[i] + [EOS]))
            tgts.append(tgt_vocab.encode([BOS] + tgt_sentences[i] + [EOS]))
        return srcs, tgts

    tr_src, tr_tgt = _encode(train_idx)
    va_src, va_tgt = _encode(val_idx)
    te_src, te_tgt = _encode(test_idx)

    # 4. Wrap in Dataset / DataLoader
    _mkds = lambda s, t: Seq2SeqDataset(s, t, max_seq_len, max_seq_len)
    _col  = partial(collate_fn, pad_idx=src_vocab.pad_idx)
    kw    = dict(collate_fn=_col, num_workers=num_workers, pin_memory=True)

    return (
        DataLoader(_mkds(tr_src, tr_tgt), batch_size=batch_size, shuffle=True,  **kw),
        DataLoader(_mkds(va_src, va_tgt), batch_size=batch_size, shuffle=False, **kw),
        DataLoader(_mkds(te_src, te_tgt), batch_size=batch_size, shuffle=False, **kw),
        src_vocab,
        tgt_vocab,
    )
