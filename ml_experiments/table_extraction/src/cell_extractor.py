"""
Cell content extraction.

Responsibilities:
  - Extract raw text from cell bounding boxes (OCR for images, direct for PDFs)
  - Normalize whitespace
  - Represent empty cells as None (never omit them)
  - Detect "totals" rows (rows where first column contains total-like keywords)
  - Output row/col-indexed JSON-serializable dicts
"""

from __future__ import annotations

import re
import logging
from typing import Any

from PIL import Image
import numpy as np

from .structure_recognizer import TableGrid, CellBBox

logger = logging.getLogger(__name__)

# Keywords that indicate a totals / subtotals row
_TOTALS_KEYWORDS = re.compile(
    r"\b(total|subtotal|sub-total|grand total|sum|net|gross|balance|amount due)\b",
    re.IGNORECASE,
)

# Whitespace normalizer
_WS_RE = re.compile(r"\s+")


class CellExtractor:
    """
    Extracts text from a TableGrid and formats the result as a list of row dicts.

    Parameters
    ----------
    ocr_engine:
        "pytesseract" | "easyocr" | None
        When None, assumes structured text is already available (native PDF).
    ocr_lang:
        Language string passed to the OCR engine (default "eng").
    confidence_threshold:
        For EasyOCR: minimum word confidence to include (default 0.3).
    """

    def __init__(
        self,
        ocr_engine: str | None = None,
        ocr_lang: str = "eng",
        confidence_threshold: float = 0.3,
    ) -> None:
        self.ocr_engine = ocr_engine
        self.ocr_lang = ocr_lang
        self.confidence_threshold = confidence_threshold
        self._easyocr_reader = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_from_native_pdf(
        self,
        raw_rows: list[list[str | None]],
        column_labels: list[str | None],
    ) -> list[dict[str, Any]]:
        """
        Convert pdfplumber's raw cell matrix into structured row dicts.

        Empty cells become None (never omitted).
        Totals rows are tagged with ``_is_total: true``.
        """
        result: list[dict[str, Any]] = []
        n_cols = len(column_labels)

        for row in raw_rows:
            record: dict[str, Any] = {}
            for col_idx, label in enumerate(column_labels):
                raw_val = row[col_idx] if col_idx < len(row) else None
                clean_val = self._clean(raw_val)
                key = label if label else f"col_{col_idx}"
                record[key] = clean_val

            record["_is_total"] = self._is_totals_row(record)
            result.append(record)

        return result

    def extract_from_image(
        self,
        table_image: Image.Image,
        grid: TableGrid,
        column_labels: list[str | None],
    ) -> list[dict[str, Any]]:
        """
        OCR each cell bounding box and build row dicts.

        Parameters
        ----------
        table_image:
            Cropped image of the table (must match grid coordinate space).
        grid:
            TableGrid output from structure recognition.
        column_labels:
            Flat list of resolved column labels.
        """
        # Build a row × col matrix of cell texts
        matrix: dict[tuple[int, int], str | None] = {}
        for cell in grid.cells:
            text = self._ocr_cell(table_image, cell)
            matrix[(cell.row, cell.col)] = text

        # Determine the start of data rows (skip header rows)
        # We trust that column_labels were derived from header rows already
        # so here we output all rows (caller filters header rows if needed)
        result: list[dict[str, Any]] = []
        for r_idx in range(grid.n_rows):
            record: dict[str, Any] = {}
            for c_idx in range(grid.n_cols):
                label = column_labels[c_idx] if c_idx < len(column_labels) else f"col_{c_idx}"
                key = label if label else f"col_{c_idx}"
                record[key] = matrix.get((r_idx, c_idx))  # None if cell missing

            record["_is_total"] = self._is_totals_row(record)
            result.append(record)

        return result

    def to_typed_rows(
        self,
        rows: list[dict[str, Any]],
        column_labels: list[str | None],
    ) -> list[dict[str, Any]]:
        """
        Attempt numeric coercion for cells that look like numbers.
        Leaves strings as strings. None stays None.
        """
        typed: list[dict[str, Any]] = []
        for row in rows:
            new_row: dict[str, Any] = {}
            for label in column_labels:
                key = label if label else f"col_{column_labels.index(label)}"
                val = row.get(key)
                new_row[key] = self._coerce_numeric(val)
            new_row["_is_total"] = row.get("_is_total", False)
            typed.append(new_row)
        return typed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ocr_cell(self, image: Image.Image, cell: CellBBox) -> str | None:
        x0, y0, x1, y1 = cell.bbox
        w, h = image.size
        # Clamp to image bounds
        x0 = max(0, int(x0))
        y0 = max(0, int(y0))
        x1 = min(w, int(x1))
        y1 = min(h, int(y1))

        if x1 <= x0 or y1 <= y0:
            return None

        crop = image.crop((x0, y0, x1, y1))

        if self.ocr_engine == "pytesseract":
            return self._pytesseract_crop(crop)
        elif self.ocr_engine == "easyocr":
            return self._easyocr_crop(crop)
        else:
            # No OCR engine: return None (caller must supply text separately)
            return None

    def _pytesseract_crop(self, crop: Image.Image) -> str | None:
        try:
            import pytesseract
            text = pytesseract.image_to_string(
                crop, lang=self.ocr_lang, config="--psm 7"  # single text line
            )
            return self._clean(text)
        except Exception:
            logger.warning("pytesseract failed on crop.", exc_info=True)
            return None

    def _easyocr_crop(self, crop: Image.Image) -> str | None:
        try:
            import easyocr

            if self._easyocr_reader is None:
                self._easyocr_reader = easyocr.Reader(
                    [self.ocr_lang], gpu=False, verbose=False
                )
            arr = np.array(crop)
            results = self._easyocr_reader.readtext(arr)
            texts = [
                r[1] for r in results
                if len(r) > 2 and r[2] >= self.confidence_threshold
            ]
            return self._clean(" ".join(texts)) if texts else None
        except Exception:
            logger.warning("easyocr failed on crop.", exc_info=True)
            return None

    @staticmethod
    def _clean(text: str | None) -> str | None:
        if text is None:
            return None
        text = _WS_RE.sub(" ", text).strip()
        return text if text else None

    @staticmethod
    def _coerce_numeric(val: str | None) -> int | float | str | None:
        if val is None:
            return None
        # Strip currency symbols and thousands separators
        cleaned = re.sub(r"[£$€¥₹,]", "", val).strip()
        cleaned = cleaned.rstrip("%")
        try:
            if "." in cleaned:
                return float(cleaned)
            return int(cleaned)
        except ValueError:
            return val

    @staticmethod
    def _is_totals_row(record: dict[str, Any]) -> bool:
        """Return True if any cell value matches totals keywords."""
        for v in record.values():
            if isinstance(v, str) and _TOTALS_KEYWORDS.search(v):
                return True
        return False
