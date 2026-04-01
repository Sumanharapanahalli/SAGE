"""
Document type classifier — supports two backends:

  1. LayoutLM (microsoft/layoutlm-base-uncased)
     Uses both text tokens and spatial bounding-box embeddings from OCR.
     Best accuracy; requires OCR output aligned with bounding boxes.

  2. Lightweight CNN (EfficientNet-B0 via timm)
     Image-only; no OCR required at inference.
     Faster, lower memory, still competitive on clear scans.

Both expose the same interface: predict(image) → label_str
"""

from __future__ import annotations

import abc
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from src.dataset import DOCUMENT_CLASSES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseDocumentClassifier(abc.ABC):

    @abc.abstractmethod
    def predict(self, image: np.ndarray | Image.Image) -> str:
        """Return the predicted document class name."""

    @abc.abstractmethod
    def predict_proba(self, image: np.ndarray | Image.Image) -> Dict[str, float]:
        """Return per-class probabilities as {class_name: prob}."""

    @abc.abstractmethod
    def save(self, path: str | Path) -> None: ...

    @classmethod
    @abc.abstractmethod
    def load(cls, path: str | Path) -> "BaseDocumentClassifier": ...


# ---------------------------------------------------------------------------
# LayoutLM classifier
# ---------------------------------------------------------------------------

class LayoutLMClassifier(BaseDocumentClassifier):
    """
    Fine-tunes microsoft/layoutlm-base-uncased for sequence classification.

    Input:
        - OCR words (List[str]) extracted from document
        - Normalised bounding boxes (List[[x0,y0,x1,y1]] in [0,1000] range)
        - Optional image (used for visual context when LayoutLMv3 is chosen)

    The model processes layout + text jointly; document type classification
    is done on the [CLS] token representation.
    """

    def __init__(
        self,
        pretrained: str = "microsoft/layoutlm-base-uncased",
        num_classes: int = 3,
        max_seq_length: int = 512,
        device: Optional[str] = None,
    ) -> None:
        from transformers import LayoutLMForSequenceClassification, LayoutLMTokenizer

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.max_seq_length = max_seq_length
        self.classes = DOCUMENT_CLASSES[:num_classes]

        self._log = logging.getLogger(self.__class__.__name__)
        self._log.info("Loading %s on %s", pretrained, self.device)

        self.tokenizer = LayoutLMTokenizer.from_pretrained(pretrained)
        self.model = LayoutLMForSequenceClassification.from_pretrained(
            pretrained,
            num_labels=num_classes,
        ).to(self.device)

    def encode(
        self,
        words: List[str],
        boxes: List[List[int]],
    ) -> Dict[str, torch.Tensor]:
        """
        Tokenise words and attach layout boxes.

        boxes must be normalised to [0, 1000] (LayoutLM convention).
        """
        encoding = self.tokenizer(
            words,
            boxes=boxes,
            max_length=self.max_seq_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
            is_split_into_words=True,
        )
        return {k: v.to(self.device) for k, v in encoding.items()}

    def forward_from_ocr(
        self,
        words: List[str],
        boxes: List[List[int]],
    ) -> torch.Tensor:
        """Run forward pass; returns logits (1, num_classes)."""
        encoding = self.encode(words, boxes)
        with torch.no_grad():
            output = self.model(**encoding)
        return output.logits

    def predict_from_ocr(
        self,
        words: List[str],
        boxes: List[List[int]],
    ) -> str:
        logits = self.forward_from_ocr(words, boxes)
        idx = int(logits.argmax(dim=-1).item())
        return self.classes[idx]

    def predict(self, image: np.ndarray | Image.Image) -> str:
        raise NotImplementedError(
            "LayoutLMClassifier requires OCR output. Use predict_from_ocr()."
        )

    def predict_proba(self, image: np.ndarray | Image.Image) -> Dict[str, float]:
        raise NotImplementedError("Use predict_proba_from_ocr() for LayoutLM.")

    def predict_proba_from_ocr(
        self,
        words: List[str],
        boxes: List[List[int]],
    ) -> Dict[str, float]:
        logits = self.forward_from_ocr(words, boxes)
        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()
        return {cls: float(p) for cls, p in zip(self.classes, probs)}

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(path))
        self.tokenizer.save_pretrained(str(path))
        self._log.info("LayoutLM saved to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "LayoutLMClassifier":
        from transformers import LayoutLMForSequenceClassification, LayoutLMTokenizer
        path = Path(path)
        obj = cls.__new__(cls)
        obj._log = logging.getLogger(cls.__name__)
        obj.device = "cuda" if torch.cuda.is_available() else "cpu"
        obj.classes = DOCUMENT_CLASSES
        obj.max_seq_length = 512
        obj.tokenizer = LayoutLMTokenizer.from_pretrained(str(path))
        obj.model = LayoutLMForSequenceClassification.from_pretrained(str(path)).to(obj.device)
        return obj


# ---------------------------------------------------------------------------
# CNN classifier (EfficientNet-B0)
# ---------------------------------------------------------------------------

class CNNDocumentClassifier(BaseDocumentClassifier):
    """
    Lightweight image-only classifier using EfficientNet-B0 as backbone.

    The final classification head is replaced with a new linear layer for
    num_classes outputs.  Only the head is trained by default (feature
    extraction mode); set freeze_backbone=False for full fine-tuning.
    """

    def __init__(
        self,
        num_classes: int = 3,
        pretrained: bool = True,
        freeze_backbone: bool = False,
        image_size: int = 224,
        device: Optional[str] = None,
    ) -> None:
        import timm
        from torchvision import transforms

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.classes = DOCUMENT_CLASSES[:num_classes]
        self.image_size = image_size
        self._log = logging.getLogger(self.__class__.__name__)

        self.model = timm.create_model(
            "efficientnet_b0",
            pretrained=pretrained,
            num_classes=num_classes,
        ).to(self.device)

        if freeze_backbone:
            for name, param in self.model.named_parameters():
                if "classifier" not in name:
                    param.requires_grad = False
            self._log.info("Backbone frozen; training head only.")

        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _to_tensor(self, image: np.ndarray | Image.Image) -> torch.Tensor:
        if isinstance(image, np.ndarray):
            import cv2
            image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        return tensor

    def predict(self, image: np.ndarray | Image.Image) -> str:
        self.model.eval()
        with torch.no_grad():
            logits = self.model(self._to_tensor(image))
        idx = int(logits.argmax(dim=-1).item())
        return self.classes[idx]

    def predict_proba(self, image: np.ndarray | Image.Image) -> Dict[str, float]:
        self.model.eval()
        with torch.no_grad():
            logits = self.model(self._to_tensor(image))
        probs = torch.softmax(logits, dim=-1).squeeze().cpu().numpy()
        return {cls: float(p) for cls, p in zip(self.classes, probs)}

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), path / "cnn_weights.pt")
        self._log.info("CNN saved to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "CNNDocumentClassifier":
        path = Path(path)
        obj = cls(pretrained=False)
        obj.model.load_state_dict(torch.load(path / "cnn_weights.pt", map_location=obj.device))
        return obj


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_classifier(
    model_type: str = "layoutlm",
    **kwargs,
) -> BaseDocumentClassifier:
    if model_type == "layoutlm":
        return LayoutLMClassifier(**kwargs)
    elif model_type == "cnn":
        return CNNDocumentClassifier(**kwargs)
    else:
        raise ValueError(f"Unknown model_type: {model_type}. Choose 'layoutlm' or 'cnn'.")
