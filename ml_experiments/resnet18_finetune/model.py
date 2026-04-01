"""
model.py — ResNet-18 fine-tuning with progressive layer unfreezing.
"""

from __future__ import annotations

import logging
from typing import Optional

import torch
import torch.nn as nn
from torchvision import models

logger = logging.getLogger(__name__)


class ResNet18Classifier(nn.Module):
    """
    ResNet-18 with a custom classification head.

    Architecture changes vs. stock ResNet-18:
        • avgpool kept as-is (GlobalAveragePool to 512-d)
        • fc replaced by: Dropout → Linear(512, num_classes)

    Progressive unfreezing is controlled externally via set_trainable_layers().
    """

    def __init__(self, num_classes: int = 10, dropout: float = 0.4) -> None:
        super().__init__()
        weights = models.ResNet18_Weights.IMAGENET1K_V1
        backbone = models.resnet18(weights=weights)

        # Replace the classification head
        in_features = backbone.fc.in_features          # 512 for ResNet-18
        backbone.fc = nn.Sequential(
            nn.Dropout(p=dropout),
            nn.Linear(in_features, num_classes),
        )
        self.model = backbone

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)

    # ------------------------------------------------------------------
    # Progressive unfreezing helpers
    # ------------------------------------------------------------------

    def freeze_all(self) -> None:
        for p in self.model.parameters():
            p.requires_grad = False
        # Always keep head trainable
        for p in self.model.fc.parameters():
            p.requires_grad = True

    def set_trainable_layers(self, layer_names: list[str]) -> None:
        """
        Unfreeze only named top-level blocks.
        Example: layer_names = ["layer4", "fc"]
        """
        # First freeze everything
        for p in self.model.parameters():
            p.requires_grad = False

        for name in layer_names:
            block = getattr(self.model, name, None)
            if block is None:
                logger.warning("Layer '%s' not found in model — skipping.", name)
                continue
            for p in block.parameters():
                p.requires_grad = True

        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        total     = sum(p.numel() for p in self.parameters())
        logger.info(
            "Trainable params: %d / %d (%.1f%%) — active layers: %s",
            trainable, total, 100 * trainable / total, layer_names,
        )

    def get_param_groups(
        self,
        head_lr: float,
        backbone_lr: float,
    ) -> list[dict]:
        """
        Return two param groups for differential learning rates:
            - backbone layers (lower LR for preservation of pretrained features)
            - classification head (higher LR for task adaptation)
        """
        head_params     = list(self.model.fc.parameters())
        head_param_ids  = {id(p) for p in head_params}
        backbone_params = [p for p in self.parameters()
                           if id(p) not in head_param_ids and p.requires_grad]
        return [
            {"params": backbone_params, "lr": backbone_lr},
            {"params": head_params,     "lr": head_lr},
        ]


def build_model(cfg: dict) -> ResNet18Classifier:
    model_cfg = cfg["model"]
    model = ResNet18Classifier(
        num_classes=model_cfg["num_classes"],
        dropout=model_cfg["dropout"],
    )
    # Start with only the head trainable (epoch 0 schedule)
    schedule_epoch_0 = model_cfg["unfreeze_schedule"][0]["layers"]
    model.freeze_all()
    model.set_trainable_layers(schedule_epoch_0)
    return model


def apply_unfreeze_schedule(model: ResNet18Classifier, cfg: dict, epoch: int) -> None:
    """Called at the start of each epoch to apply the progressive unfreeze schedule."""
    schedule = cfg["model"]["unfreeze_schedule"]
    layers_to_activate = None
    for entry in schedule:
        if epoch >= entry["epoch"]:
            layers_to_activate = entry["layers"]
    if layers_to_activate:
        model.set_trainable_layers(layers_to_activate)
