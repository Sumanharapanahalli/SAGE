"""
Dialog Management Model — Transformer-LSTM-Policy Architecture
==============================================================
DistilBERT encoder → LSTM dialog state tracker → MLP policy head

Designed for multi-domain dialog act classification (MultiWOZ-style).
"""

import torch
import torch.nn as nn
from transformers import DistilBertModel


class DialogManagementModel(nn.Module):
    """
    End-to-end differentiable dialog management network.

    Pipeline:
        utterance + history  →  DistilBERT (contextual)
                             →  Projection (encoder_dim → hidden_size)
                             →  LSTM (dialog state dynamics)
                             →  MLP policy head (logits over dialog acts)

    Args:
        encoder_name:   HuggingFace model id (default: distilbert-base-uncased)
        hidden_size:    Internal representation width for LSTM + policy head
        n_classes:      Number of distinct dialog act labels
        lstm_layers:    Number of stacked LSTM layers
        dropout:        Dropout probability (applied after projection & in head)
    """

    def __init__(
        self,
        encoder_name: str = "distilbert-base-uncased",
        hidden_size: int = 256,
        n_classes: int = 15,
        lstm_layers: int = 2,
        dropout: float = 0.3,
    ) -> None:
        super().__init__()

        # ── Encoder ─────────────────────────────────────────────────────────
        self.encoder = DistilBertModel.from_pretrained(encoder_name)
        encoder_dim: int = self.encoder.config.dim  # 768 for base models

        # ── Projection ──────────────────────────────────────────────────────
        self.projection = nn.Sequential(
            nn.Linear(encoder_dim, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        # ── Dialog State Tracker ─────────────────────────────────────────────
        self.state_tracker = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=lstm_layers,
            batch_first=True,
            dropout=dropout if lstm_layers > 1 else 0.0,
            bidirectional=False,
        )

        # ── Policy Head ──────────────────────────────────────────────────────
        self.policy_head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, n_classes),
        )

        self._init_weights()

    def _init_weights(self) -> None:
        """Xavier initialization for non-pretrained linear layers."""
        for name, module in self.named_modules():
            if isinstance(module, nn.Linear) and "encoder" not in name:
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(
        self,
        input_ids: torch.Tensor,      # (B, seq_len)
        attention_mask: torch.Tensor, # (B, seq_len)
    ) -> torch.Tensor:                # (B, n_classes)
        # 1. Contextual encoding — CLS token as utterance+history representation
        enc_out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls = enc_out.last_hidden_state[:, 0, :]  # (B, encoder_dim)

        # 2. Project to working dimension
        projected = self.projection(cls).unsqueeze(1)  # (B, 1, hidden_size)

        # 3. LSTM dialog state update
        lstm_out, _ = self.state_tracker(projected)    # (B, 1, hidden_size)
        state = lstm_out[:, -1, :]                     # (B, hidden_size)

        # 4. Policy: predict next dialog act
        return self.policy_head(state)                 # (B, n_classes)

    def freeze_encoder(self) -> None:
        """Freeze DistilBERT weights (use for warm-up phase training)."""
        for param in self.encoder.parameters():
            param.requires_grad = False

    def unfreeze_encoder(self) -> None:
        """Unfreeze DistilBERT weights for full fine-tuning."""
        for param in self.encoder.parameters():
            param.requires_grad = True

    @property
    def n_trainable_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
