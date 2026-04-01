"""
metrics.py — OCR evaluation metrics.

Metrics
───────
• CER  — Character Error Rate   (Levenshtein / reference length)
• WER  — Word Error Rate        (token-level Levenshtein)
• EM   — Exact Match            (% lines with zero errors)
• FA   — Field Accuracy         (key–value extraction accuracy; optional)

All functions are pure: no side effects, no global state.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import jiwer
import numpy as np


# ── Pre-processing transforms (applied identically to preds + refs) ──────────
_TRANSFORM = jiwer.Compose([
    jiwer.ToLowerCase(),
    jiwer.RemoveMultipleSpaces(),
    jiwer.Strip(),
    jiwer.RemovePunctuation(),
])


def compute_cer(references: List[str], hypotheses: List[str]) -> float:
    """Character Error Rate — lower is better, 0.0 is perfect."""
    if not references:
        return 0.0
    # jiwer uses word-level Levenshtein by default; for CER we pass
    # space-joined characters so each character becomes a "word".
    ref_chars = [" ".join(list(r)) for r in references]
    hyp_chars = [" ".join(list(h)) for h in hypotheses]
    return jiwer.wer(ref_chars, hyp_chars)


def compute_wer(references: List[str], hypotheses: List[str]) -> float:
    """Word Error Rate — lower is better, 0.0 is perfect."""
    if not references:
        return 0.0
    return jiwer.wer(references, hypotheses, reference_transform=_TRANSFORM,
                     hypothesis_transform=_TRANSFORM)


def compute_exact_match(references: List[str], hypotheses: List[str]) -> float:
    """Fraction of lines where prediction == reference after normalisation."""
    if not references:
        return 0.0
    norm_ref = [_normalise(r) for r in references]
    norm_hyp = [_normalise(h) for h in hypotheses]
    matches = sum(r == h for r, h in zip(norm_ref, norm_hyp))
    return matches / len(references)


def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace, strip punctuation."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_field_accuracy(
    references: List[Dict[str, str]],
    hypotheses: List[Dict[str, str]],
    fields: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Per-field exact-match accuracy for structured key-value extraction.

    Parameters
    ----------
    references  : list of dicts  e.g. [{"total": "42.00", "date": "2024-01-01"}]
    hypotheses  : list of dicts  (same keys, model predictions)
    fields      : subset of keys to evaluate; None = all keys in references

    Returns
    -------
    Dict mapping field name → accuracy (0–1), plus an "overall" key.
    """
    if not references:
        return {}

    all_fields = fields or list(references[0].keys())
    field_correct: Dict[str, int] = {f: 0 for f in all_fields}
    field_total: Dict[str, int] = {f: 0 for f in all_fields}

    for ref, hyp in zip(references, hypotheses):
        for f in all_fields:
            ref_val = _normalise(str(ref.get(f, "")))
            hyp_val = _normalise(str(hyp.get(f, "")))
            field_total[f] += 1
            if ref_val == hyp_val:
                field_correct[f] += 1

    result = {
        f: field_correct[f] / field_total[f] if field_total[f] else 0.0
        for f in all_fields
    }
    if result:
        result["overall"] = float(np.mean(list(result.values())))
    return result


def aggregate_metrics(
    references: List[str],
    hypotheses: List[str],
) -> Dict[str, float]:
    """Compute all line-level OCR metrics in one call."""
    return {
        "cer": round(compute_cer(references, hypotheses), 4),
        "wer": round(compute_wer(references, hypotheses), 4),
        "exact_match": round(compute_exact_match(references, hypotheses), 4),
        "n_samples": len(references),
    }
