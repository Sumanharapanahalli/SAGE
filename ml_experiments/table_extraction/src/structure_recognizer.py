"""
Table structure recognition.

Given a cropped table image (or a pdfplumber Table object), produce a grid
of (row, col) → CellBBox mappings using:
  1. TableTransformer structure model  (image inputs)
  2. pdfplumber cell extraction        (native PDF inputs)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from .detector import TableRegion

logger = logging.getLogger(__name__)


@dataclass
class CellBBox:
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # x0,y0,x1,y1


@dataclass
class TableGrid:
    """Raw structural output before text extraction."""

    page_index: int
    region_bbox: tuple[float, float, float, float]
    cells: list[CellBBox] = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0
    row_spans: list[tuple[int, int]] = field(default_factory=list)  # (start_row, end_row) per logical row
    source: str = "transformer"
    raw_cells: list[Any] = field(default_factory=list)  # pdfplumber raw rows


class TableStructureRecognizer:
    """
    Recognizes the internal row/column structure of a detected table.

    Parameters
    ----------
    model_name:
        HuggingFace model id for structure recognition.
    iou_threshold:
        IoU threshold used when clustering cell boxes into rows/columns.
    """

    _STRUCTURE_MODEL = "microsoft/table-transformer-structure-recognition"

    def __init__(
        self,
        model_name: str = _STRUCTURE_MODEL,
        iou_threshold: float = 0.5,
        use_gpu: bool = True,
    ) -> None:
        self.model_name = model_name
        self.iou_threshold = iou_threshold
        self.use_gpu = use_gpu
        self._model = None
        self._processor = None
        self._device: str | None = None

    # ------------------------------------------------------------------
    # Lazy loading
    # ------------------------------------------------------------------

    def _load_transformer(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoImageProcessor, TableTransformerForObjectDetection

            self._device = "cuda" if (self.use_gpu and torch.cuda.is_available()) else "cpu"
            logger.info("Loading TableTransformer structure model on %s …", self._device)
            self._processor = AutoImageProcessor.from_pretrained(self.model_name)
            self._model = TableTransformerForObjectDetection.from_pretrained(self.model_name)
            self._model.to(self._device)
            self._model.eval()
        except ImportError as exc:
            raise RuntimeError("transformers/torch not installed.") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recognize_from_image(
        self, table_image: Image.Image, region: TableRegion
    ) -> TableGrid:
        """Run structure recognition on a cropped table image."""
        import torch

        self._load_transformer()

        img_rgb = table_image.convert("RGB")
        inputs = self._processor(images=img_rgb, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        target_sizes = torch.tensor([[img_rgb.height, img_rgb.width]]).to(self._device)
        results = self._processor.post_process_object_detection(
            outputs, threshold=0.5, target_sizes=target_sizes
        )[0]

        id2label = self._model.config.id2label
        rows_boxes: list[tuple[float, ...]] = []
        cols_boxes: list[tuple[float, ...]] = []
        cell_boxes: list[tuple[float, ...]] = []

        for score, label, box in zip(
            results["scores"].cpu().numpy(),
            results["labels"].cpu().numpy(),
            results["boxes"].cpu().numpy(),
        ):
            lbl_name = id2label.get(int(label), "")
            if "row" in lbl_name:
                rows_boxes.append(tuple(box.tolist()))
            elif "column" in lbl_name:
                cols_boxes.append(tuple(box.tolist()))
            elif "cell" in lbl_name:
                cell_boxes.append(tuple(box.tolist()))

        # Sort rows top-to-bottom, cols left-to-right
        rows_boxes.sort(key=lambda b: b[1])
        cols_boxes.sort(key=lambda b: b[0])

        grid = self._build_grid_from_transformer(
            rows_boxes, cols_boxes, cell_boxes, region
        )
        return grid

    def recognize_from_pdfplumber(self, pdfplumber_table: Any, region: TableRegion) -> TableGrid:
        """
        Build a TableGrid directly from a pdfplumber Table object.
        pdfplumber already provides a row×col matrix.
        """
        raw_rows = pdfplumber_table.extract()  # list[list[str|None]]
        if not raw_rows:
            return TableGrid(page_index=region.page_index, region_bbox=region.bbox, source="pdfplumber")

        n_rows = len(raw_rows)
        n_cols = max(len(r) for r in raw_rows) if raw_rows else 0

        cells: list[CellBBox] = []
        for r_idx, row in enumerate(raw_rows):
            for c_idx in range(n_cols):
                cell_val = row[c_idx] if c_idx < len(row) else None
                cells.append(
                    CellBBox(row=r_idx, col=c_idx, row_span=1, col_span=1)
                )

        grid = TableGrid(
            page_index=region.page_index,
            region_bbox=region.bbox,
            cells=cells,
            n_rows=n_rows,
            n_cols=n_cols,
            source="pdfplumber",
            raw_cells=raw_rows,
        )
        return grid

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_grid_from_transformer(
        self,
        rows_boxes: list[tuple],
        cols_boxes: list[tuple],
        cell_boxes: list[tuple],
        region: TableRegion,
    ) -> TableGrid:
        """
        Map detected cell bboxes onto the row/column grid.
        Handles spanning cells by assigning each cell box to the row and
        column it overlaps most with.
        """
        n_rows = len(rows_boxes)
        n_cols = len(cols_boxes)

        cells: list[CellBBox] = []
        assigned: set[tuple[int, int]] = set()

        for cbox in cell_boxes:
            r_idx = self._best_overlap_index(cbox, rows_boxes, axis="row")
            c_idx = self._best_overlap_index(cbox, cols_boxes, axis="col")
            if r_idx < 0 or c_idx < 0:
                continue
            key = (r_idx, c_idx)
            if key in assigned:
                continue
            assigned.add(key)
            cells.append(
                CellBBox(row=r_idx, col=c_idx, bbox=cbox[:4])
            )

        # Fill gaps (cells missed by model)
        for r in range(n_rows):
            for c in range(n_cols):
                if (r, c) not in assigned:
                    # Approximate bbox as intersection of row/col boxes
                    if r < len(rows_boxes) and c < len(cols_boxes):
                        rb = rows_boxes[r]
                        cb = cols_boxes[c]
                        approx = (
                            max(rb[0], cb[0]),
                            max(rb[1], cb[1]),
                            min(rb[2], cb[2]),
                            min(rb[3], cb[3]),
                        )
                        cells.append(CellBBox(row=r, col=c, bbox=approx))

        cells.sort(key=lambda c: (c.row, c.col))
        return TableGrid(
            page_index=region.page_index,
            region_bbox=region.bbox,
            cells=cells,
            n_rows=n_rows,
            n_cols=n_cols,
            source="transformer",
        )

    @staticmethod
    def _best_overlap_index(
        cell_box: tuple, reference_boxes: list[tuple], axis: str
    ) -> int:
        """Return the index in reference_boxes with maximum 1-D overlap."""
        if not reference_boxes:
            return -1

        # axis="row" → compare vertical (y) spans; axis="col" → horizontal (x)
        if axis == "row":
            c_lo, c_hi = cell_box[1], cell_box[3]
            spans = [(b[1], b[3]) for b in reference_boxes]
        else:
            c_lo, c_hi = cell_box[0], cell_box[2]
            spans = [(b[0], b[2]) for b in reference_boxes]

        best_idx, best_overlap = -1, 0.0
        for i, (lo, hi) in enumerate(spans):
            overlap = max(0.0, min(c_hi, hi) - max(c_lo, lo))
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i
        return best_idx
