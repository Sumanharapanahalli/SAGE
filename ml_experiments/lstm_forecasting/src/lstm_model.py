"""
lstm_model.py — Encoder-Decoder LSTM with teacher forcing.

Architecture
------------
  Encoder: LSTM over the 30-step lookback window → hidden state h, c
  Decoder: Step-by-step LSTM that generates the 7-step forecast

Teacher Forcing
---------------
During training, at each decoder step t the decoder receives either:
  * The ground-truth y[t-1]  (teacher forcing, probability = tf_ratio)
  * Its own previous prediction (scheduled sampling, prob = 1 - tf_ratio)

tf_ratio is linearly annealed from `initial_teacher_forcing` to
`final_teacher_forcing` over the training epochs, transitioning the model
from supervised sequence learning to autonomous autoregressive generation.

Inference
---------
tf_ratio = 0.0 → purely autoregressive (no ground truth available).
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class LSTMForecaster(nn.Module):
    """Encoder-decoder LSTM for multi-step time-series forecasting.

    Args:
        input_size:    Number of input features per timestep.
        hidden_size:   LSTM hidden dimension.
        num_layers:    Number of stacked LSTM layers.
        output_horizon: Number of future steps to predict.
        dropout:       Dropout probability (applied between LSTM layers).
    """

    def __init__(
        self,
        input_size: int = 1,
        hidden_size: int = 128,
        num_layers: int = 2,
        output_horizon: int = 7,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.output_horizon = output_horizon

        lstm_dropout = dropout if num_layers > 1 else 0.0  # PyTorch ignores dropout for single-layer

        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=lstm_dropout,
        )

        # Decoder receives one scalar at each step
        self.decoder = nn.LSTM(
            input_size=1,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=lstm_dropout,
        )

        self.projection = nn.Linear(hidden_size, 1)
        self.dropout = nn.Dropout(dropout)

        self._init_weights()
        n_params = sum(p.numel() for p in self.parameters())
        logger.info("LSTMForecaster: hidden=%d layers=%d horizon=%d params=%s",
                    hidden_size, num_layers, output_horizon, f"{n_params:,}")

    def _init_weights(self) -> None:
        for name, p in self.named_parameters():
            if "weight_ih" in name:
                nn.init.xavier_uniform_(p)
            elif "weight_hh" in name:
                nn.init.orthogonal_(p)
            elif "bias" in name:
                nn.init.zeros_(p)
                # Forget-gate bias trick: set to 1.0 to improve gradient flow
                n = p.size(0)
                p.data[n // 4 : n // 2].fill_(1.0)

    def forward(
        self,
        x: torch.Tensor,
        target: Optional[torch.Tensor] = None,
        teacher_forcing_ratio: float = 0.5,
    ) -> torch.Tensor:
        """Forward pass with optional teacher forcing.

        Args:
            x:                    (batch, lookback, input_size)
            target:               (batch, horizon) — ground truth; None at inference
            teacher_forcing_ratio: probability of feeding ground truth to decoder

        Returns:
            predictions: (batch, horizon) — scaled predictions
        """
        # ---- Encode ---------------------------------------------------------
        _, (hidden, cell) = self.encoder(x)   # hidden: (num_layers, batch, H)

        # ---- Decode step-by-step --------------------------------------------
        # Seed the decoder with the last observed value
        decoder_input = x[:, -1:, :1]        # (batch, 1, 1)

        outputs: list[torch.Tensor] = []
        for t in range(self.output_horizon):
            dec_out, (hidden, cell) = self.decoder(decoder_input, (hidden, cell))
            # dec_out: (batch, 1, H)
            pred = self.projection(self.dropout(dec_out))   # (batch, 1, 1)
            outputs.append(pred.squeeze(-1))                # (batch, 1)

            use_teacher = (
                target is not None
                and teacher_forcing_ratio > 0.0
                and torch.rand(1, device=x.device).item() < teacher_forcing_ratio
            )
            if use_teacher:
                decoder_input = target[:, t].unsqueeze(1).unsqueeze(-1)  # (batch, 1, 1)
            else:
                decoder_input = pred                                      # (batch, 1, 1)

        return torch.cat(outputs, dim=1)   # (batch, horizon)


# ---------------------------------------------------------------------------
# Teacher-forcing schedule
# ---------------------------------------------------------------------------

def teacher_forcing_ratio(epoch: int, total_epochs: int, initial: float, final: float) -> float:
    """Linear annealing schedule from `initial` to `final`."""
    if total_epochs <= 1:
        return initial
    ratio = initial + (final - initial) * (epoch / (total_epochs - 1))
    return float(max(final, min(initial, ratio)))
