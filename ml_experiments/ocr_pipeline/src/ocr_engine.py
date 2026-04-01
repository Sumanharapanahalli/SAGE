"""
OCR engine abstraction layer.

Supports Tesseract, PaddleOCR, and a confidence-weighted ensemble.
Each engine returns a uniform OCRResult so the rest of the pipeline
is engine-agnostic.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    x: int
    y: int
    w: int
    h: int


@dataclass
class OCRWord:
    text: str
    confidence: float          # [0, 1]
    bbox: Optional[BoundingBox] = None


@dataclass
class OCRResult:
    """Unified OCR output regardless of engine."""
    full_text: str
    words: List[OCRWord]
    mean_confidence: float
    engine: str
    raw: Optional[Any] = None  # engine-native output for debugging

    def __post_init__(self) -> None:
        if self.words and self.mean_confidence == 0.0:
            confidences = [w.confidence for w in self.words if w.confidence >= 0]
            self.mean_confidence = float(np.mean(confidences)) if confidences else 0.0


# ---------------------------------------------------------------------------
# Engine enum
# ---------------------------------------------------------------------------

class EngineType(str, Enum):
    TESSERACT = "tesseract"
    PADDLEOCR = "paddleocr"
    ENSEMBLE  = "ensemble"


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseOCREngine(abc.ABC):
    """All engines must implement extract()."""

    @abc.abstractmethod
    def extract(self, image: np.ndarray) -> OCRResult:
        """
        Extract text from a preprocessed (grayscale or binary) image.

        Args:
            image: uint8 numpy array (grayscale or BGR).

        Returns:
            OCRResult with full text, per-word data, and confidence scores.
        """

    @abc.abstractmethod
    @property
    def name(self) -> str: ...


# ---------------------------------------------------------------------------
# Tesseract engine
# ---------------------------------------------------------------------------

class TesseractEngine(BaseOCREngine):
    """
    Wraps pytesseract.  Uses image_to_data for per-word confidence.

    tesseract_config examples:
      "--oem 3 --psm 6"   → block of text (default)
      "--oem 3 --psm 11"  → sparse text
    """

    def __init__(
        self,
        lang: str = "eng",
        config: str = "--oem 3 --psm 6",
        confidence_threshold: float = 0.0,
    ) -> None:
        try:
            import pytesseract
            self._ts = pytesseract
        except ImportError as exc:
            raise ImportError("pytesseract not installed. Run: pip install pytesseract") from exc

        self.lang = lang
        self.config = config
        self.confidence_threshold = confidence_threshold
        self._log = logging.getLogger(self.__class__.__name__)

    @property
    def name(self) -> str:
        return "tesseract"

    def extract(self, image: np.ndarray) -> OCRResult:
        pil_img = self._to_pil(image)
        data = self._ts.image_to_data(
            pil_img,
            lang=self.lang,
            config=self.config,
            output_type=self._ts.Output.DICT,
        )
        words: List[OCRWord] = []
        for i, text in enumerate(data["text"]):
            text = text.strip()
            if not text:
                continue
            raw_conf = int(data["conf"][i])
            if raw_conf < 0:
                conf = 0.0
            else:
                conf = raw_conf / 100.0

            bbox = BoundingBox(
                x=data["left"][i],
                y=data["top"][i],
                w=data["width"][i],
                h=data["height"][i],
            )
            words.append(OCRWord(text=text, confidence=conf, bbox=bbox))

        full_text = self._ts.image_to_string(pil_img, lang=self.lang, config=self.config)
        mean_conf = float(np.mean([w.confidence for w in words])) if words else 0.0

        self._log.debug(
            "Tesseract extracted %d words, mean conf=%.3f", len(words), mean_conf
        )
        return OCRResult(
            full_text=full_text.strip(),
            words=words,
            mean_confidence=mean_conf,
            engine=self.name,
            raw=data,
        )

    @staticmethod
    def _to_pil(image: np.ndarray) -> Image.Image:
        import cv2
        if image.ndim == 2:
            return Image.fromarray(image, mode="L")
        return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


# ---------------------------------------------------------------------------
# PaddleOCR engine
# ---------------------------------------------------------------------------

class PaddleOCREngine(BaseOCREngine):
    """
    Wraps PaddleOCR.  Lazy-imports to avoid hard dependency when using
    Tesseract-only mode.
    """

    def __init__(
        self,
        lang: str = "en",
        use_gpu: bool = False,
        confidence_threshold: float = 0.5,
    ) -> None:
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False)
        except ImportError as exc:
            raise ImportError("paddleocr not installed. Run: pip install paddlepaddle paddleocr") from exc

        self.confidence_threshold = confidence_threshold
        self._log = logging.getLogger(self.__class__.__name__)

    @property
    def name(self) -> str:
        return "paddleocr"

    def extract(self, image: np.ndarray) -> OCRResult:
        # PaddleOCR accepts BGR numpy arrays
        result = self._ocr.ocr(image, cls=True)

        words: List[OCRWord] = []
        lines: List[str] = []

        if result and result[0]:
            for line in result[0]:
                bbox_points, (text, conf) = line
                text = text.strip()
                if not text:
                    continue
                # Convert 4-point polygon to x/y/w/h
                pts = np.array(bbox_points, dtype=int)
                x, y = pts[:, 0].min(), pts[:, 1].min()
                w = pts[:, 0].max() - x
                h = pts[:, 1].max() - y
                words.append(
                    OCRWord(
                        text=text,
                        confidence=float(conf),
                        bbox=BoundingBox(x=int(x), y=int(y), w=int(w), h=int(h)),
                    )
                )
                lines.append(text)

        full_text = "\n".join(lines)
        mean_conf = float(np.mean([w.confidence for w in words])) if words else 0.0

        self._log.debug(
            "PaddleOCR extracted %d words, mean conf=%.3f", len(words), mean_conf
        )
        return OCRResult(
            full_text=full_text,
            words=words,
            mean_confidence=mean_conf,
            engine=self.name,
            raw=result,
        )


# ---------------------------------------------------------------------------
# Ensemble engine
# ---------------------------------------------------------------------------

class EnsembleOCREngine(BaseOCREngine):
    """
    Runs multiple engines and returns a confidence-weighted merged result.

    Merge strategy: the engine with the highest mean_confidence provides
    the full_text; word lists are concatenated with engine provenance.
    """

    def __init__(self, engines: List[BaseOCREngine]) -> None:
        if not engines:
            raise ValueError("EnsembleOCREngine requires at least one engine.")
        self._engines = engines
        self._log = logging.getLogger(self.__class__.__name__)

    @property
    def name(self) -> str:
        return "ensemble[" + ",".join(e.name for e in self._engines) + "]"

    def extract(self, image: np.ndarray) -> OCRResult:
        results: List[OCRResult] = []
        for eng in self._engines:
            try:
                r = eng.extract(image)
                results.append(r)
                self._log.debug("%s → conf=%.3f", eng.name, r.mean_confidence)
            except Exception:
                self._log.exception("Engine %s failed; skipping.", eng.name)

        if not results:
            return OCRResult(full_text="", words=[], mean_confidence=0.0, engine=self.name)

        best = max(results, key=lambda r: r.mean_confidence)
        all_words = [w for r in results for w in r.words]
        mean_conf = float(np.mean([r.mean_confidence for r in results]))

        return OCRResult(
            full_text=best.full_text,
            words=all_words,
            mean_confidence=mean_conf,
            engine=self.name,
            raw={"results": results},
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_ocr_engine(
    engine_type: str = "tesseract",
    **kwargs: Any,
) -> BaseOCREngine:
    """
    Factory that builds an OCR engine from a string identifier.

    Args:
        engine_type: "tesseract" | "paddleocr" | "ensemble"
        **kwargs: forwarded to the engine constructor.

    Returns:
        Configured OCR engine instance.
    """
    _type = EngineType(engine_type.lower())

    if _type == EngineType.TESSERACT:
        return TesseractEngine(
            lang=kwargs.get("lang", "eng"),
            config=kwargs.get("config", "--oem 3 --psm 6"),
            confidence_threshold=kwargs.get("confidence_threshold", 0.0),
        )
    elif _type == EngineType.PADDLEOCR:
        return PaddleOCREngine(
            lang=kwargs.get("lang", "en"),
            use_gpu=kwargs.get("use_gpu", False),
            confidence_threshold=kwargs.get("confidence_threshold", 0.5),
        )
    elif _type == EngineType.ENSEMBLE:
        engines: List[BaseOCREngine] = [
            TesseractEngine(lang=kwargs.get("lang", "eng")),
            PaddleOCREngine(lang=kwargs.get("lang", "en")),
        ]
        return EnsembleOCREngine(engines)
    else:
        raise ValueError(f"Unknown engine type: {engine_type}")
