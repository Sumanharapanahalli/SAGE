"""
PDF multi-page processing.

Converts each page to a PIL Image at target DPI, runs preprocessing +
OCR, and returns a structured per-page result.

Requires: pdf2image (which wraps poppler utilities).
System dependency: `apt install poppler-utils` or `brew install poppler`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np

from src.ocr_engine import BaseOCREngine, OCRResult
from src.preprocessing import ImagePreprocessor, PreprocessingConfig

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    page_number: int          # 1-indexed
    image_shape: tuple        # (H, W) of preprocessed image
    ocr: OCRResult
    preprocessing_applied: List[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    source_path: str
    total_pages: int
    pages: List[PageResult]

    @property
    def full_text(self) -> str:
        """Concatenate all pages with page separators."""
        parts = []
        for page in self.pages:
            parts.append(f"=== Page {page.page_number} ===")
            parts.append(page.ocr.full_text)
        return "\n\n".join(parts)

    @property
    def mean_confidence(self) -> float:
        if not self.pages:
            return 0.0
        return float(np.mean([p.ocr.mean_confidence for p in self.pages]))


class PDFProcessor:
    """
    Orchestrates PDF → image → preprocess → OCR for each page.

    Usage:
        processor = PDFProcessor(ocr_engine=engine, preprocessor=preprocessor)
        result = processor.process("invoice.pdf")
        print(result.full_text)
    """

    def __init__(
        self,
        ocr_engine: BaseOCREngine,
        preprocessor: Optional[ImagePreprocessor] = None,
        dpi: int = 300,
        first_page: Optional[int] = None,
        last_page: Optional[int] = None,
    ) -> None:
        try:
            import pdf2image
            self._pdf2image = pdf2image
        except ImportError as exc:
            raise ImportError(
                "pdf2image not installed. Run: pip install pdf2image"
            ) from exc

        self._ocr = ocr_engine
        self._preprocessor = preprocessor or ImagePreprocessor(PreprocessingConfig())
        self._dpi = dpi
        self._first_page = first_page
        self._last_page = last_page
        self._log = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, pdf_path: str | Path) -> DocumentResult:
        """
        Process all pages (or a range) of a PDF file.

        Args:
            pdf_path: Path to a PDF file.

        Returns:
            DocumentResult with per-page OCR output.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        self._log.info("Processing PDF: %s", pdf_path.name)
        pages = self._load_pages(pdf_path)
        total_pages = len(pages)

        results: List[PageResult] = []
        for idx, pil_page in enumerate(pages, start=1):
            self._log.debug("  Page %d/%d …", idx, total_pages)
            page_result = self._process_page(idx, pil_page)
            results.append(page_result)
            self._log.debug(
                "  Page %d done — words=%d conf=%.3f",
                idx, len(page_result.ocr.words), page_result.ocr.mean_confidence,
            )

        doc = DocumentResult(
            source_path=str(pdf_path),
            total_pages=total_pages,
            pages=results,
        )
        self._log.info(
            "Finished %s — %d pages, mean conf=%.3f",
            pdf_path.name, total_pages, doc.mean_confidence,
        )
        return doc

    def stream_pages(self, pdf_path: str | Path) -> Iterator[PageResult]:
        """
        Streaming generator — yields PageResult one at a time.
        Useful for large PDFs where holding all pages in memory is expensive.
        """
        pdf_path = Path(pdf_path)
        pages = self._load_pages(pdf_path)
        for idx, pil_page in enumerate(pages, start=1):
            yield self._process_page(idx, pil_page)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_pages(self, pdf_path: Path) -> list:
        """Convert PDF pages to PIL Images at target DPI."""
        kwargs: dict = {"dpi": self._dpi, "fmt": "RGB"}
        if self._first_page is not None:
            kwargs["first_page"] = self._first_page
        if self._last_page is not None:
            kwargs["last_page"] = self._last_page

        return self._pdf2image.convert_from_path(str(pdf_path), **kwargs)

    def _process_page(self, page_num: int, pil_image) -> PageResult:
        import cv2

        # PIL → numpy BGR
        raw_np = self._preprocessor.from_pil(pil_image)

        # Preprocessing pipeline
        preprocessed = self._preprocessor.preprocess(raw_np)

        # OCR on preprocessed image
        ocr_result = self._ocr.extract(preprocessed)

        return PageResult(
            page_number=page_num,
            image_shape=preprocessed.shape[:2],
            ocr=ocr_result,
            preprocessing_applied=["deskew", "denoise", "binarize"],
        )
