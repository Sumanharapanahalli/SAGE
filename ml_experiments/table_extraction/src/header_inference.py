"""
Header inference for extracted tables.

Handles:
  - Single-row headers (most common)
  - Multi-row headers (merged / nested column labels)
  - Spanning header cells
  - Tables with no header (numeric / continuation tables)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Heuristic: a cell is "header-like" if it matches these patterns
_NUMERIC_RE = re.compile(r"^\s*[-+]?[\d,\.]+\s*(%|[A-Z]{3})?\s*$")
_CURRENCY_RE = re.compile(r"^\s*[\$€£¥₹]")
_EMPTY_RE = re.compile(r"^\s*$")


@dataclass
class HeaderResult:
    """
    Output of header inference for a single table.

    Attributes
    ----------
    n_header_rows:
        Number of rows classified as header (0 = no header detected).
    header_rows:
        Raw text for each header row, preserving None for empty cells.
    column_labels:
        Flat list of resolved column labels (multi-row headers merged).
    is_multi_row:
        True when n_header_rows > 1.
    confidence:
        0–1 confidence in the inferred structure.
    """

    n_header_rows: int
    header_rows: list[list[str | None]]
    column_labels: list[str | None]
    is_multi_row: bool
    confidence: float
    notes: list[str] = field(default_factory=list)


class HeaderInference:
    """
    Infers which rows of a raw cell matrix are headers.

    Strategy:
      1. Classify each row as "data", "header", or "ambiguous" using
         heuristics (dtype analysis, positional bias, formatting cues).
      2. Identify the contiguous header block at the top of the table.
      3. For multi-row headers, merge spanning cells top-down.
      4. Fall back to auto-generated column names when no header is found.

    Parameters
    ----------
    max_header_rows:
        Maximum number of contiguous rows to consider as headers (default 4).
    text_ratio_threshold:
        Minimum fraction of text (non-numeric) cells for a row to be
        considered a header (default 0.6).
    """

    def __init__(
        self,
        max_header_rows: int = 4,
        text_ratio_threshold: float = 0.6,
    ) -> None:
        self.max_header_rows = max_header_rows
        self.text_ratio_threshold = text_ratio_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def infer(self, rows: list[list[str | None]]) -> HeaderResult:
        """
        Infer headers from a 2-D list of cell strings.

        Parameters
        ----------
        rows:
            Outer list = rows; inner list = cell text (None for empty).

        Returns
        -------
        HeaderResult
        """
        if not rows:
            return HeaderResult(0, [], [], False, 0.0, notes=["empty table"])

        n_cols = max(len(r) for r in rows)
        rows = self._pad_rows(rows, n_cols)

        row_scores = [self._header_score(row) for row in rows]
        n_header_rows, confidence = self._detect_header_boundary(row_scores)

        header_rows = rows[:n_header_rows] if n_header_rows else []
        column_labels = self._merge_header_rows(header_rows, n_cols)

        notes: list[str] = []
        if n_header_rows == 0:
            column_labels = [f"col_{i}" for i in range(n_cols)]
            notes.append("no header detected — auto-generated column labels")
        if n_header_rows > 1:
            notes.append(f"multi-row header detected ({n_header_rows} rows)")

        return HeaderResult(
            n_header_rows=n_header_rows,
            header_rows=header_rows,
            column_labels=column_labels,
            is_multi_row=n_header_rows > 1,
            confidence=confidence,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _header_score(self, row: list[str | None]) -> float:
        """
        Score a row on how header-like it is (0 = pure data, 1 = pure header).

        Heuristics:
        - High fraction of non-numeric, non-empty cells → header
        - Presence of all-caps words → header
        - Row has merged/empty cells at start → possible sub-header
        """
        if not row:
            return 0.0

        non_empty = [c for c in row if c and not _EMPTY_RE.match(c)]
        if not non_empty:
            return 0.0  # empty row → data separator, not a header

        text_count = sum(
            1 for c in non_empty
            if not _NUMERIC_RE.match(c) and not _CURRENCY_RE.match(c)
        )
        text_ratio = text_count / len(non_empty)

        allcaps_bonus = 0.1 * sum(1 for c in non_empty if c == c.upper() and len(c) > 1) / max(len(non_empty), 1)
        short_text_bonus = 0.1 if all(len(c) < 60 for c in non_empty) else 0.0

        score = min(1.0, text_ratio + allcaps_bonus + short_text_bonus)
        return score

    def _detect_header_boundary(
        self, row_scores: list[float]
    ) -> tuple[int, float]:
        """
        Find how many contiguous top rows qualify as headers.

        Returns (n_header_rows, confidence).
        """
        # At least the first row must score above threshold
        if not row_scores or row_scores[0] < self.text_ratio_threshold:
            return 0, 1.0 - row_scores[0] if row_scores else 1.0

        n = 1
        for i in range(1, min(len(row_scores), self.max_header_rows)):
            if row_scores[i] >= self.text_ratio_threshold:
                n += 1
            else:
                break

        # Confidence is the mean score of the header block
        confidence = float(sum(row_scores[:n]) / n)
        return n, confidence

    def _merge_header_rows(
        self, header_rows: list[list[str | None]], n_cols: int
    ) -> list[str | None]:
        """
        Merge multiple header rows into flat column labels.

        For spanning cells (non-null in row k, null in row k+1 below),
        the parent label is propagated downward (e.g., "Revenue / Q1").
        """
        if not header_rows:
            return []
        if len(header_rows) == 1:
            return [c if c and not _EMPTY_RE.match(c) else None for c in header_rows[0]]

        # Track current "parent" label per column (for spanning headers)
        parent_labels: list[str | None] = [None] * n_cols
        label_parts: list[list[str]] = [[] for _ in range(n_cols)]

        for row in header_rows:
            for col_idx in range(n_cols):
                cell = row[col_idx] if col_idx < len(row) else None
                cell = cell if cell and not _EMPTY_RE.match(cell) else None

                if cell:
                    parent_labels[col_idx] = cell
                    label_parts[col_idx].append(cell)
                elif parent_labels[col_idx]:
                    # Propagate parent label
                    label_parts[col_idx].append(parent_labels[col_idx])

        merged: list[str | None] = []
        for parts in label_parts:
            # Deduplicate consecutive identical parts (repeated spanning label)
            deduped = [parts[0]] if parts else []
            for p in parts[1:]:
                if p != deduped[-1]:
                    deduped.append(p)
            merged.append(" / ".join(deduped) if deduped else None)

        return merged

    @staticmethod
    def _pad_rows(
        rows: list[list[str | None]], n_cols: int
    ) -> list[list[str | None]]:
        return [
            row + [None] * (n_cols - len(row)) if len(row) < n_cols else row[:n_cols]
            for row in rows
        ]
