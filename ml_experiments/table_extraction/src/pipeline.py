"""
End-to-end table extraction pipeline.

Input:  PDF path or image path
Output: list[TableOutput] — one entry per detected table

Each TableOutput carries:
  - page_index
  - detection_bbox + confidence
  - column_labels (flat, multi-row merged)
  - header_rows (raw text)
  - data_rows  (list of dicts, None for empty cells, _is_total flag)
  - n_header_rows
  - is_multi_row_header
  - source ("transformer" | "pdfplumber_*")
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from .detector import TableDetector, TableRegion
from .structure_recognizer import TableStructureRecognizer
from .header_inference import HeaderInference, HeaderResult
from .cell_extractor import CellExtractor
from .experiment_logger import ExperimentLogger

logger = logging.getLogger(__name__)


@dataclass
class TableOutput:
    """Fully extracted, structured table."""

    page_index: int
    detection_confidence: float
    detection_source: str
    detection_bbox: tuple[float, float, float, float]

    n_header_rows: int
    is_multi_row_header: bool
    header_confidence: float
    column_labels: list[str | None]
    header_rows: list[list[str | None]]

    data_rows: list[dict[str, Any]]  # None cells preserved as null
    n_data_rows: int
    n_cols: int

    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)


class TableExtractionPipeline:
    """
    Orchestrates the full detection → structure → header → extraction flow.

    Parameters
    ----------
    detection_threshold:
        Minimum confidence for the TableTransformer detector.
    max_header_rows:
        Passed to HeaderInference.
    ocr_engine:
        "pytesseract" | "easyocr" | None (use None for native PDFs).
    coerce_types:
        If True, attempt numeric coercion on data cells.
    log_experiments:
        If True, log each run to MLflow via ExperimentLogger.
    experiment_name:
        MLflow experiment name.
    """

    def __init__(
        self,
        detection_threshold: float = 0.7,
        max_header_rows: int = 4,
        ocr_engine: str | None = None,
        coerce_types: bool = True,
        log_experiments: bool = False,
        experiment_name: str = "table_extraction",
    ) -> None:
        self.detection_threshold = detection_threshold
        self.max_header_rows = max_header_rows
        self.ocr_engine = ocr_engine
        self.coerce_types = coerce_types
        self.log_experiments = log_experiments
        self.experiment_name = experiment_name

        self._detector = TableDetector(detection_threshold=detection_threshold)
        self._structure = TableStructureRecognizer()
        self._header_inf = HeaderInference(max_header_rows=max_header_rows)
        self._extractor = CellExtractor(ocr_engine=ocr_engine)
        self._exp_logger: ExperimentLogger | None = (
            ExperimentLogger(experiment_name) if log_experiments else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_pdf(self, pdf_path: str | Path) -> list[TableOutput]:
        """Extract all tables from a PDF file."""
        import pdfplumber

        pdf_path = Path(pdf_path)
        logger.info("Processing PDF: %s", pdf_path.name)

        regions = self._detector.detect_from_pdf(pdf_path)
        if not regions:
            logger.info("No tables detected in %s.", pdf_path.name)
            return []

        outputs: list[TableOutput] = []
        with pdfplumber.open(pdf_path) as pdf:
            for region in regions:
                page = pdf.pages[region.page_index]
                out = self._process_region_pdf(region, page)
                if out:
                    outputs.append(out)

        if self._exp_logger:
            self._exp_logger.log_run(
                input_path=str(pdf_path),
                n_tables=len(outputs),
                params={
                    "detection_threshold": self.detection_threshold,
                    "max_header_rows": self.max_header_rows,
                    "ocr_engine": self.ocr_engine,
                },
                tables=outputs,
            )

        logger.info("Extracted %d table(s) from %s.", len(outputs), pdf_path.name)
        return outputs

    def process_image(self, image_path: str | Path | Image.Image) -> list[TableOutput]:
        """Extract all tables from an image file."""
        if not isinstance(image_path, Image.Image):
            image_path = Path(image_path)
            image = Image.open(image_path).convert("RGB")
            fname = image_path.name
        else:
            image = image_path
            fname = "<PIL.Image>"

        logger.info("Processing image: %s", fname)
        regions = self._detector.detect_from_image(image)
        if not regions:
            logger.info("No tables detected.")
            return []

        outputs: list[TableOutput] = []
        for region in regions:
            out = self._process_region_image(region, image)
            if out:
                outputs.append(out)

        if self._exp_logger:
            self._exp_logger.log_run(
                input_path=fname,
                n_tables=len(outputs),
                params={
                    "detection_threshold": self.detection_threshold,
                    "max_header_rows": self.max_header_rows,
                    "ocr_engine": self.ocr_engine,
                },
                tables=outputs,
            )
        return outputs

    def process_bytes(
        self, data: bytes, mime_type: str = "application/pdf"
    ) -> list[TableOutput]:
        """Process raw bytes (useful for API integrations)."""
        import tempfile, os

        if mime_type == "application/pdf":
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                return self.process_pdf(tmp_path)
            finally:
                os.unlink(tmp_path)
        else:
            from io import BytesIO
            img = Image.open(BytesIO(data)).convert("RGB")
            return self.process_image(img)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_region_pdf(self, region: TableRegion, page: Any) -> TableOutput | None:
        """Process a single PDF table region."""
        try:
            pdfplumber_table = region.raw_meta.get("pdfplumber_table")
            if pdfplumber_table is None:
                # Crop page image and fall back to transformer structure recognition
                img = page.to_image(resolution=150).original
                return self._process_region_image(region, img)

            grid = self._structure.recognize_from_pdfplumber(pdfplumber_table, region)
            raw_rows: list[list[str | None]] = grid.raw_cells  # already extracted

            if not raw_rows:
                return None

            header_result: HeaderResult = self._header_inf.infer(raw_rows)
            data_raw = raw_rows[header_result.n_header_rows:]
            data_rows = self._extractor.extract_from_native_pdf(
                data_raw, header_result.column_labels
            )
            if self.coerce_types:
                data_rows = self._extractor.to_typed_rows(data_rows, header_result.column_labels)

            return TableOutput(
                page_index=region.page_index,
                detection_confidence=region.confidence,
                detection_source=region.source,
                detection_bbox=region.bbox,
                n_header_rows=header_result.n_header_rows,
                is_multi_row_header=header_result.is_multi_row,
                header_confidence=header_result.confidence,
                column_labels=header_result.column_labels,
                header_rows=header_result.header_rows,
                data_rows=data_rows,
                n_data_rows=len(data_rows),
                n_cols=grid.n_cols,
                notes=header_result.notes,
            )
        except Exception:
            logger.error("Failed to process PDF region on page %d.", region.page_index, exc_info=True)
            return None

    def _process_region_image(
        self, region: TableRegion, image: Image.Image
    ) -> TableOutput | None:
        """Crop region from image, recognise structure, OCR cells."""
        try:
            x0, y0, x1, y1 = region.bbox
            w, h = image.size
            x0 = max(0, int(x0))
            y0 = max(0, int(y0))
            x1 = min(w, int(x1))
            y1 = min(h, int(y1))
            table_img = image.crop((x0, y0, x1, y1))

            grid = self._structure.recognize_from_image(table_img, region)
            if grid.n_rows == 0 or grid.n_cols == 0:
                return None

            # Build raw text matrix for header inference
            raw_matrix: dict[tuple[int, int], str | None] = {}
            for cell in grid.cells:
                raw_matrix[(cell.row, cell.col)] = self._extractor._ocr_cell(table_img, cell)

            raw_rows = [
                [raw_matrix.get((r, c)) for c in range(grid.n_cols)]
                for r in range(grid.n_rows)
            ]

            header_result: HeaderResult = self._header_inf.infer(raw_rows)
            data_raw = raw_rows[header_result.n_header_rows:]
            data_rows = self._extractor.extract_from_native_pdf(
                data_raw, header_result.column_labels
            )
            if self.coerce_types:
                data_rows = self._extractor.to_typed_rows(data_rows, header_result.column_labels)

            return TableOutput(
                page_index=region.page_index,
                detection_confidence=region.confidence,
                detection_source=region.source,
                detection_bbox=region.bbox,
                n_header_rows=header_result.n_header_rows,
                is_multi_row_header=header_result.is_multi_row,
                header_confidence=header_result.confidence,
                column_labels=header_result.column_labels,
                header_rows=header_result.header_rows,
                data_rows=data_rows,
                n_data_rows=len(data_rows),
                n_cols=grid.n_cols,
                notes=header_result.notes,
            )
        except Exception:
            logger.error("Failed to process image region.", exc_info=True)
            return None
