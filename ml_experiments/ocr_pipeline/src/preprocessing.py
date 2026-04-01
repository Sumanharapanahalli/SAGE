"""
Image preprocessing: deskew (up to 15°), denoise, binarization, contrast enhancement.
All operations are stateless; each method returns a new array (no in-place mutation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingConfig:
    target_dpi: int = 300
    max_skew_angle: float = 15.0
    denoise_h: int = 10
    denoise_template_window: int = 7
    denoise_search_window: int = 21
    binarize_block_size: int = 11
    binarize_c: int = 2
    enhance_contrast: bool = True
    clahe_clip_limit: float = 2.0
    clahe_tile_grid: Tuple[int, int] = field(default_factory=lambda: (8, 8))
    min_contour_area: int = 100


class ImagePreprocessor:
    """
    Full preprocessing pipeline for scanned documents.

    Pipeline: load → deskew → denoise → (CLAHE) → adaptive-binarize
    All intermediate images remain as uint8 grayscale numpy arrays.
    """

    def __init__(self, config: Optional[PreprocessingConfig] = None) -> None:
        self.config = config or PreprocessingConfig()
        self._log = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Run the full preprocessing pipeline.

        Args:
            image: BGR or grayscale uint8 numpy array.

        Returns:
            Binary uint8 numpy array ready for OCR.
        """
        gray = self._to_gray(image)
        deskewed = self.deskew(gray)
        denoised = self.denoise(deskewed)
        binary = self.binarize(denoised)
        return binary

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Correct document skew.  Angles larger than max_skew_angle are
        clamped before rotation to avoid content loss.

        Args:
            image: Grayscale uint8 numpy array.

        Returns:
            Deskewed grayscale image with white fill on borders.
        """
        angle = self._detect_skew_angle(image)

        if abs(angle) > self.config.max_skew_angle:
            self._log.warning(
                "Detected skew %.2f° exceeds limit %.1f°; clamping.",
                angle,
                self.config.max_skew_angle,
            )
            angle = float(np.sign(angle)) * self.config.max_skew_angle

        if abs(angle) < 0.05:
            return image.copy()

        self._log.debug("Correcting skew: %.2f°", angle)
        return self._rotate(image, angle)

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Non-local means denoising — effective against Gaussian and salt-and-pepper
        noise common in scanned documents.
        """
        return cv2.fastNlMeansDenoising(
            image,
            h=self.config.denoise_h,
            templateWindowSize=self.config.denoise_template_window,
            searchWindowSize=self.config.denoise_search_window,
        )

    def binarize(self, image: np.ndarray) -> np.ndarray:
        """
        Adaptive Gaussian thresholding with optional CLAHE pre-pass for
        low-contrast documents.

        Adaptive thresholding handles uneven illumination far better than
        global Otsu on real-world scans.
        """
        if self.config.enhance_contrast:
            clahe = cv2.createCLAHE(
                clipLimit=self.config.clahe_clip_limit,
                tileGridSize=self.config.clahe_tile_grid,
            )
            image = clahe.apply(image)

        binary = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            self.config.binarize_block_size,
            self.config.binarize_c,
        )
        return binary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_gray(self, image: np.ndarray) -> np.ndarray:
        if image.ndim == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image.copy()

    def _detect_skew_angle(self, image: np.ndarray) -> float:
        """
        Estimate skew angle via contour-based minAreaRect.

        Strategy:
        1. Invert + Otsu threshold to isolate dark text on white.
        2. Dilate horizontally to merge characters into word/line blobs.
        3. Fit rotated bounding rectangles; collect orientation angles.
        4. Return median angle (robust to noisy outliers).
        """
        _, binary = cv2.threshold(
            image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        dilated = cv2.dilate(binary, kernel)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        angles: list[float] = []
        for cnt in contours:
            if cv2.contourArea(cnt) < self.config.min_contour_area:
                continue
            _, _, angle = cv2.minAreaRect(cnt)
            # minAreaRect returns angle in (-90, 0]; normalise to [-45, 45]
            if angle < -45:
                angle += 90
            angles.append(angle)

        if not angles:
            self._log.debug("No contours found; assuming zero skew.")
            return 0.0

        median_angle = float(np.median(angles))
        self._log.debug("Detected skew angle: %.2f° (from %d contours)", median_angle, len(angles))
        return median_angle

    def _rotate(self, image: np.ndarray, angle: float) -> np.ndarray:
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        return cv2.warpAffine(
            image,
            M,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )

    # ------------------------------------------------------------------
    # PIL interop
    # ------------------------------------------------------------------

    @staticmethod
    def from_pil(pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to BGR numpy array."""
        return cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)

    @staticmethod
    def to_pil(image: np.ndarray) -> Image.Image:
        """Convert grayscale or BGR numpy array to PIL Image."""
        if image.ndim == 2:
            return Image.fromarray(image, mode="L")
        return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
