"""
Table region detector.

Dual-path strategy:
  1. Native PDF  → pdfplumber lattice/stream detection (no model needed)
  2. Image / scanned PDF → TableTransformer (microsoft/table-transformer-detection)

Each path returns a list of TableRegion with bounding boxes and confidence scores.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pdfplumber
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class TableRegion:
    """Detected table bounding box in a document page."""

    page_index: int
    bbox: tuple[float, float, float, float]   # x0, y0, x1, y1 (pixels or PDF units)
    confidence: float
    source: str  # "transformer" | "pdfplumber_lattice" | "pdfplumber_stream"
    raw_meta: dict[str, Any] = field(default_factory=dict)


class TableDetector:
    """
    Detects table regions in PDFs and images.

    Parameters
    ----------
    model_name:
        HuggingFace model id for TableTransformer detection.
    detection_threshold:
        Minimum confidence to keep a detected region.
    use_gpu:
        If True, moves the model to CUDA when available.
    """

    _TRANSFORMER_MODEL = "microsoft/table-transformer-detection"

    def __init__(
        self,
        model_name: str = _TRANSFORMER_MODEL,
        detection_threshold: float = 0.7,
        use_gpu: bool = True,
    ) -> None:
        self.model_name = model_name
        self.detection_threshold = detection_threshold
        self.use_gpu = use_gpu
        self._model = None
        self._processor = None
        self._device: str | None = None

    # ------------------------------------------------------------------
    # Lazy model loading (avoid heavy import at module init time)
    # ------------------------------------------------------------------

    def _load_transformer(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoImageProcessor, TableTransformerForObjectDetection

            self._device = "cuda" if (self.use_gpu and torch.cuda.is_available()) else "cpu"
            logger.info("Loading TableTransformer on %s …", self._device)
            self._processor = AutoImageProcessor.from_pretrained(self.model_name)
            self._model = TableTransformerForObjectDetection.from_pretrained(self.model_name)
            self._model.to(self._device)
            self._model.eval()
            logger.info("TableTransformer loaded.")
        except ImportError as exc:
            raise RuntimeError(
                "transformers / torch not installed. Run: pip install transformers torch"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_from_pdf(self, pdf_path: str | Path) -> list[TableRegion]:
        """
        Detect tables in a PDF file.

        Tries pdfplumber first (fast, no model).
        Falls back to image-based detection for scanned pages.
        """
        pdf_path = Path(pdf_path)
        regions: list[TableRegion] = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                native = self._detect_native_pdf(page, page_idx)
                if native:
                    regions.extend(native)
                    logger.debug("Page %d: %d native tables found.", page_idx, len(native))
                else:
                    # Rasterize and run vision model
                    img = page.to_image(resolution=150).original
                    image_regions = self._detect_from_pil(img, page_idx)
                    regions.extend(image_regions)
                    logger.debug(
                        "Page %d: %d transformer-detected tables.", page_idx, len(image_regions)
                    )
        return regions

    def detect_from_image(self, image: str | Path | Image.Image) -> list[TableRegion]:
        """Detect tables in a single image (PNG/JPEG/TIFF …)."""
        if not isinstance(image, Image.Image):
            image = Image.open(image).convert("RGB")
        return self._detect_from_pil(image, page_index=0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_native_pdf(self, page: Any, page_index: int) -> list[TableRegion]:
        """
        Use pdfplumber's built-in table finder.
        Returns empty list if no tables are found natively.
        """
        regions: list[TableRegion] = []
        try:
            # Lattice first (lines define cells)
            settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
            tables = page.find_tables(table_settings=settings)
            source = "pdfplumber_lattice"

            if not tables:
                # Stream fallback (whitespace-delimited)
                settings = {"vertical_strategy": "text", "horizontal_strategy": "text"}
                tables = page.find_tables(table_settings=settings)
                source = "pdfplumber_stream"

            for tbl in tables:
                bbox = tbl.bbox  # (x0, top, x1, bottom) in PDF user-space units
                regions.append(
                    TableRegion(
                        page_index=page_index,
                        bbox=bbox,
                        confidence=1.0,  # rule-based → deterministic
                        source=source,
                        raw_meta={"pdfplumber_table": tbl},
                    )
                )
        except Exception:
            logger.warning("pdfplumber native detection failed on page %d.", page_index, exc_info=True)
        return regions

    def _detect_from_pil(self, image: Image.Image, page_index: int) -> list[TableRegion]:
        """Run TableTransformer on a PIL image and return detected regions."""
        import torch

        self._load_transformer()

        image_rgb = image.convert("RGB")
        inputs = self._processor(images=image_rgb, return_tensors="pt")
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        target_sizes = torch.tensor([[image_rgb.height, image_rgb.width]]).to(self._device)
        results = self._processor.post_process_object_detection(
            outputs, threshold=self.detection_threshold, target_sizes=target_sizes
        )[0]

        regions: list[TableRegion] = []
        for score, label, box in zip(
            results["scores"].cpu().numpy(),
            results["labels"].cpu().numpy(),
            results["boxes"].cpu().numpy(),
        ):
            x0, y0, x1, y1 = box.tolist()
            regions.append(
                TableRegion(
                    page_index=page_index,
                    bbox=(x0, y0, x1, y1),
                    confidence=float(score),
                    source="transformer",
                    raw_meta={"label": int(label)},
                )
            )
        return regions

    def detect_from_bytes(self, data: bytes, mime_type: str = "application/pdf") -> list[TableRegion]:
        """Convenience: detect from raw bytes."""
        if mime_type == "application/pdf":
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                return self.detect_from_pdf(tmp_path)
            finally:
                os.unlink(tmp_path)
        else:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            return self.detect_from_image(img)
