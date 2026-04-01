"""
NER Dataset Validators
======================
Pydantic v2 models for ingestion-time validation of raw and labeled NER data.

All validation is *fail-fast*: the pipeline rejects a document immediately if
any constraint is violated, preventing corrupt data from entering the store.

Validated constraints
---------------------
- text is non-empty and within length bounds
- every span (start, end) is within text character bounds
- spans are non-overlapping and non-empty
- entity labels belong to the allowed tag set
- token BIO sequences are well-formed (no I-X without preceding B-X)
"""

from __future__ import annotations

import logging
import re
from typing import ClassVar, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# ── Allowed entity label set ─────────────────────────────────────────────────

ALLOWED_ENTITY_TYPES: frozenset[str] = frozenset(
    ["PER", "ORG", "LOC", "GPE", "DATE", "TIME", "MONEY", "PRODUCT", "EVENT", "MISC"]
)

BIO_PREFIXES: frozenset[str] = frozenset(["B", "I", "O"])

MAX_TEXT_CHARS = 100_000
MIN_TEXT_CHARS = 1


# ── Input models (raw, pre-ingestion) ────────────────────────────────────────


class EntitySpan(BaseModel):
    """A single named-entity annotation as a character-level span."""

    start: int = Field(..., ge=0, description="Inclusive start character offset.")
    end: int = Field(..., description="Exclusive end character offset.")
    label: str = Field(..., description="Entity type label, e.g. PER, ORG, LOC.")

    @field_validator("label")
    @classmethod
    def label_in_allowed_set(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in ALLOWED_ENTITY_TYPES:
            raise ValueError(
                f"Entity label {v!r} not in allowed set: {sorted(ALLOWED_ENTITY_TYPES)}"
            )
        return v

    @model_validator(mode="after")
    def span_is_non_empty(self) -> "EntitySpan":
        if self.end <= self.start:
            raise ValueError(
                f"Span end ({self.end}) must be > start ({self.start})."
            )
        return self


class RawDocument(BaseModel):
    """One document as received from the ingestion source."""

    doc_id: str = Field(..., min_length=1, description="Unique document identifier.")
    text: str = Field(..., description="Raw UTF-8 text.")
    entities: list[EntitySpan] = Field(default_factory=list)
    source: str = Field(default="unknown", description="Provenance tag.")
    language: str = Field(default="en", pattern=r"^[a-z]{2}$")

    # ── Class-level constraints ───────────────────────────────────────────────
    _max_chars: ClassVar[int] = MAX_TEXT_CHARS
    _min_chars: ClassVar[int] = MIN_TEXT_CHARS

    @field_validator("text")
    @classmethod
    def text_length_in_bounds(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < cls._min_chars:
            raise ValueError("text must not be empty.")
        if len(stripped) > cls._max_chars:
            raise ValueError(
                f"text length {len(stripped)} exceeds maximum {cls._max_chars} chars."
            )
        return stripped

    @model_validator(mode="after")
    def spans_within_text(self) -> "RawDocument":
        n = len(self.text)
        for span in self.entities:
            if span.end > n:
                raise ValueError(
                    f"Span [{span.start}, {span.end}) exceeds text length {n} "
                    f"in doc {self.doc_id!r}."
                )
        return self

    @model_validator(mode="after")
    def no_overlapping_spans(self) -> "RawDocument":
        sorted_spans = sorted(self.entities, key=lambda s: s.start)
        for i in range(1, len(sorted_spans)):
            prev, curr = sorted_spans[i - 1], sorted_spans[i]
            if curr.start < prev.end:
                raise ValueError(
                    f"Overlapping spans detected in doc {self.doc_id!r}: "
                    f"[{prev.start},{prev.end}) {prev.label} overlaps "
                    f"[{curr.start},{curr.end}) {curr.label}."
                )
        return self

    @model_validator(mode="after")
    def doc_id_is_safe(self) -> "RawDocument":
        """doc_id must be URL/filename safe: alphanumeric + _ + -"""
        if not re.fullmatch(r"[\w\-]+", self.doc_id):
            raise ValueError(
                f"doc_id {self.doc_id!r} contains unsafe characters. "
                "Use only [a-zA-Z0-9_-]."
            )
        return self


# ── Labeled models (post-tokenization) ───────────────────────────────────────


class LabeledToken(BaseModel):
    """A single token with its BIO NER tag."""

    text: str = Field(..., min_length=1)
    bio_tag: str = Field(
        ...,
        description="BIO2 tag: O | B-<TYPE> | I-<TYPE>",
    )

    @field_validator("bio_tag")
    @classmethod
    def bio_tag_format(cls, v: str) -> str:
        if v == "O":
            return v
        parts = v.split("-", 1)
        if len(parts) != 2 or parts[0] not in ("B", "I"):
            raise ValueError(
                f"BIO tag {v!r} must be 'O', 'B-<TYPE>', or 'I-<TYPE>'."
            )
        label = parts[1].upper()
        if label not in ALLOWED_ENTITY_TYPES:
            raise ValueError(
                f"Entity type {label!r} in tag {v!r} not in allowed set."
            )
        return f"{parts[0]}-{label}"


class LabeledSentence(BaseModel):
    """A sentence broken into tokens with BIO tags — the atomic training unit."""

    sentence_id: str
    doc_id: str
    tokens: list[LabeledToken] = Field(..., min_length=1)

    @model_validator(mode="after")
    def bio_sequence_is_valid(self) -> "LabeledSentence":
        """I-X tag must be preceded by B-X or I-X with the same type."""
        prev_tag = "O"
        for i, tok in enumerate(self.tokens):
            tag = tok.bio_tag
            if tag.startswith("I-"):
                entity_type = tag.split("-", 1)[1]
                if not (
                    prev_tag == f"B-{entity_type}"
                    or prev_tag == f"I-{entity_type}"
                ):
                    raise ValueError(
                        f"Sentence {self.sentence_id!r}: invalid BIO transition "
                        f"at token {i} ({prev_tag!r} → {tag!r}). "
                        f"I-{entity_type} must follow B-{entity_type} or I-{entity_type}."
                    )
            prev_tag = tag
        return self

    @property
    def entity_types_present(self) -> set[str]:
        return {
            tok.bio_tag.split("-", 1)[1]
            for tok in self.tokens
            if tok.bio_tag != "O"
        }

    @property
    def has_entities(self) -> bool:
        return any(tok.bio_tag != "O" for tok in self.tokens)


# ── Ingestion-level batch check ───────────────────────────────────────────────


def validate_batch(
    raw_docs: list[dict],
    *,
    strict: bool = True,
) -> tuple[list[RawDocument], list[dict]]:
    """
    Validate a batch of raw document dicts.

    Parameters
    ----------
    raw_docs : list of dicts (from JSONL ingestion)
    strict   : if True, raise on first error; if False, collect errors and continue

    Returns
    -------
    (valid_docs, error_records)
        valid_docs    : list[RawDocument] — passed validation
        error_records : list[dict]        — failed, with 'error' key appended
    """
    valid: list[RawDocument] = []
    errors: list[dict] = []

    for i, raw in enumerate(raw_docs):
        try:
            doc = RawDocument.model_validate(raw)
            valid.append(doc)
        except Exception as exc:
            doc_id = raw.get("doc_id", f"[index={i}]")
            msg = f"Validation failed for doc {doc_id!r}: {exc}"
            logger.warning(msg)
            if strict:
                raise ValueError(msg) from exc
            errors.append({**raw, "error": str(exc)})

    logger.info("Batch validation: %d valid, %d rejected", len(valid), len(errors))
    return valid, errors
