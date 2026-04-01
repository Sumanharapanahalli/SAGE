"""Transformer encoder-decoder from scratch (Vaswani et al., 2017).

Improvements over original paper:
  - Pre-LayerNorm (more stable gradient flow)
  - GELU activation (instead of ReLU)
  - Weight tying: decoder embedding <-> output projection
  - Xavier uniform init for all weight matrices
  - Beam search decoding in addition to greedy
"""
from __future__ import annotations
import math
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class MultiHeadAttention(nn.Module):
    """
    Multi-head scaled dot-product attention.

    Used three ways:
      - Encoder self-attention    : query=key=value=encoder_state
      - Decoder masked self-attn  : same, but tgt_mask enforces causality
      - Decoder cross-attention   : query=decoder_state, key=value=encoder_output
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        if d_model % num_heads != 0:
            raise ValueError(
                f"d_model ({d_model}) must be divisible by num_heads ({num_heads})"
            )
        self.d_model   = d_model
        self.num_heads = num_heads
        self.d_k       = d_model // num_heads
        self.scale     = math.sqrt(self.d_k)

        # No bias — matches original paper
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.W_k = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.W_o = nn.Linear(d_model, d_model, bias=False)
        self.attn_dropout = nn.Dropout(dropout)

    def _split_heads(self, x: torch.Tensor) -> torch.Tensor:
        """(B, seq, d_model) -> (B, heads, seq, d_k)"""
        B, seq, _ = x.shape
        return x.view(B, seq, self.num_heads, self.d_k).transpose(1, 2)

    def _merge_heads(self, x: torch.Tensor) -> torch.Tensor:
        """(B, heads, seq, d_k) -> (B, seq, d_model)"""
        B, _, seq, _ = x.shape
        return x.transpose(1, 2).contiguous().view(B, seq, self.d_model)

    def forward(
        self,
        query: torch.Tensor,                   # (B, tgt_len, d_model)
        key:   torch.Tensor,                   # (B, src_len, d_model)
        value: torch.Tensor,                   # (B, src_len, d_model)
        mask:  Optional[torch.Tensor] = None,  # bool, broadcastable to (B,h,tgt,src)
    ) -> tuple[torch.Tensor, torch.Tensor]:
        Q = self._split_heads(self.W_q(query))   # (B,h,tgt,d_k)
        K = self._split_heads(self.W_k(key))     # (B,h,src,d_k)
        V = self._split_heads(self.W_v(value))   # (B,h,src,d_k)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # (B,h,tgt,src)

        if mask is not None:
            scores = scores.masked_fill(~mask, float("-inf"))

        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = torch.nan_to_num(attn_weights, nan=0.0)  # guard all-masked rows
        attn_weights = self.attn_dropout(attn_weights)

        context = torch.matmul(attn_weights, V)   # (B,h,tgt,d_k)
        output  = self.W_o(self._merge_heads(context))
        return output, attn_weights


class PositionalEncoding(nn.Module):
    """
    Fixed sinusoidal positional encoding.

    PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))

    Registered as a buffer: moves with .to(device), saved in state_dict,
    but not updated by the optimizer.
    """

    def __init__(self, d_model: int, max_seq_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        pe  = torch.zeros(max_seq_len, d_model)
        pos = torch.arange(0, max_seq_len, dtype=torch.float).unsqueeze(1)
        div = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float)
            * (-math.log(10_000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_seq_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, seq_len, d_model)"""
        return self.dropout(x + self.pe[:, : x.size(1)])


class FeedForward(nn.Module):
    """Position-wise two-layer FFN with GELU activation."""

    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class EncoderLayer(nn.Module):
    """
    Pre-LayerNorm encoder layer:

      x = x + Dropout(SelfAttn(LN(x)))
      x = x + Dropout(FFN(LN(x)))
    """

    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn       = FeedForward(d_model, d_ff, dropout)
        self.norm1     = nn.LayerNorm(d_model, eps=1e-6)
        self.norm2     = nn.LayerNorm(d_model, eps=1e-6)
        self.dropout   = nn.Dropout(dropout)

    def forward(
        self,
        x:        torch.Tensor,
        src_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        normed = self.norm1(x)
        attn_out, _ = self.self_attn(normed, normed, normed, src_mask)
        x = x + self.dropout(attn_out)
        x = x + self.dropout(self.ffn(self.norm2(x)))
        return x


class DecoderLayer(nn.Module):
    """
    Pre-LayerNorm decoder layer:

      x = x + Dropout(MaskedSelfAttn(LN(x)))         # causal
      x = x + Dropout(CrossAttn(LN(x), enc_output))  # attends encoder
      x = x + Dropout(FFN(LN(x)))
    """

    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn  = MultiHeadAttention(d_model, num_heads, dropout)
        self.cross_attn = MultiHeadAttention(d_model, num_heads, dropout)
        self.ffn        = FeedForward(d_model, d_ff, dropout)
        self.norm1      = nn.LayerNorm(d_model, eps=1e-6)
        self.norm2      = nn.LayerNorm(d_model, eps=1e-6)
        self.norm3      = nn.LayerNorm(d_model, eps=1e-6)
        self.dropout    = nn.Dropout(dropout)

    def forward(
        self,
        x:          torch.Tensor,
        enc_output: torch.Tensor,
        src_mask:   Optional[torch.Tensor] = None,
        tgt_mask:   Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        normed = self.norm1(x)
        attn_out, _        = self.self_attn(normed, normed, normed, tgt_mask)
        x = x + self.dropout(attn_out)

        normed = self.norm2(x)
        cross_out, cross_w = self.cross_attn(normed, enc_output, enc_output, src_mask)
        x = x + self.dropout(cross_out)

        x = x + self.dropout(self.ffn(self.norm3(x)))
        return x, cross_w


class Encoder(nn.Module):
    def __init__(
        self,
        vocab_size:  int,
        d_model:     int,
        num_heads:   int,
        num_layers:  int,
        d_ff:        int,
        max_seq_len: int,
        dropout:     float = 0.1,
        pad_idx:     int   = 0,
    ):
        super().__init__()
        self.d_model      = d_model
        self.embedding    = nn.Embedding(vocab_size, d_model, padding_idx=pad_idx)
        self.pos_encoding = PositionalEncoding(d_model, max_seq_len, dropout)
        self.layers       = nn.ModuleList(
            [EncoderLayer(d_model, num_heads, d_ff, dropout) for _ in range(num_layers)]
        )
        self.norm = nn.LayerNorm(d_model, eps=1e-6)

    def forward(
        self,
        src:      torch.Tensor,
        src_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        x = self.pos_encoding(self.embedding(src) * math.sqrt(self.d_model))
        for layer in self.layers:
            x = layer(x, src_mask)
        return self.norm(x)


class Decoder(nn.Module):
    def __init__(
        self,
        vocab_size:  int,
        d_model:     int,
        num_heads:   int,
        num_layers:  int,
        d_ff:        int,
        max_seq_len: int,
        dropout:     float = 0.1,
        pad_idx:     int   = 0,
    ):
        super().__init__()
        self.d_model      = d_model
        self.embedding    = nn.Embedding(vocab_size, d_model, padding_idx=pad_idx)
        self.pos_encoding = PositionalEncoding(d_model, max_seq_len, dropout)
        self.layers       = nn.ModuleList(
            [DecoderLayer(d_model, num_heads, d_ff, dropout) for _ in range(num_layers)]
        )
        self.norm = nn.LayerNorm(d_model, eps=1e-6)

    def forward(
        self,
        tgt:        torch.Tensor,
        enc_output: torch.Tensor,
        src_mask:   Optional[torch.Tensor] = None,
        tgt_mask:   Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, list[torch.Tensor]]:
        x = self.pos_encoding(self.embedding(tgt) * math.sqrt(self.d_model))
        cross_weights: list[torch.Tensor] = []
        for layer in self.layers:
            x, cw = layer(x, enc_output, src_mask, tgt_mask)
            cross_weights.append(cw)
        return self.norm(x), cross_weights


class Transformer(nn.Module):
    """
    Full Transformer encoder-decoder.

    Key design choices
    ------------------
    Pre-LayerNorm : applied before each sub-layer (more stable than post-norm)
    Sinusoidal PE : no learned position parameters
    Causal mask   : lower-triangular bool mask prevents attending to future tokens
    Weight tying  : decoder embedding == output projection (fewer params, better PPL)
    Xavier init   : all weight matrices initialised with xavier_uniform_

    Args
    ----
    src_vocab_size     : Source vocabulary size.
    tgt_vocab_size     : Target vocabulary size.
    d_model            : Model dimension.                     Default 512.
    num_heads          : Attention heads.                     Default 8.
    num_encoder_layers : Stacked encoder layers.              Default 6.
    num_decoder_layers : Stacked decoder layers.              Default 6.
    d_ff               : FFN inner dimension.                 Default 2048.
    max_seq_len        : Max supported sequence length.       Default 512.
    dropout            : Dropout rate.                        Default 0.1.
    pad_idx            : Padding token index.                 Default 0.
    tie_weights        : Tie decoder emb <-> output proj.     Default True.
    """

    def __init__(
        self,
        src_vocab_size:     int,
        tgt_vocab_size:     int,
        d_model:            int   = 512,
        num_heads:          int   = 8,
        num_encoder_layers: int   = 6,
        num_decoder_layers: int   = 6,
        d_ff:               int   = 2048,
        max_seq_len:        int   = 512,
        dropout:            float = 0.1,
        pad_idx:            int   = 0,
        tie_weights:        bool  = True,
    ):
        super().__init__()
        self.pad_idx = pad_idx

        self.encoder = Encoder(
            src_vocab_size, d_model, num_heads, num_encoder_layers,
            d_ff, max_seq_len, dropout, pad_idx,
        )
        self.decoder = Decoder(
            tgt_vocab_size, d_model, num_heads, num_decoder_layers,
            d_ff, max_seq_len, dropout, pad_idx,
        )
        self.output_projection = nn.Linear(d_model, tgt_vocab_size, bias=False)

        if tie_weights:
            self.output_projection.weight = self.decoder.embedding.weight

        self._init_weights()

    # ------------------------------------------------------------------ masks

    def make_src_mask(self, src: torch.Tensor) -> torch.Tensor:
        """Padding mask: True=real token, False=PAD.  Shape (B,1,1,src_len)."""
        return (src != self.pad_idx).unsqueeze(1).unsqueeze(2)

    def make_tgt_mask(self, tgt: torch.Tensor) -> torch.Tensor:
        """
        Causal + padding mask for autoregressive decoding.
        True positions may be attended to.  Shape (B,1,tgt_len,tgt_len).
        """
        B, tgt_len = tgt.shape
        pad_mask = (tgt != self.pad_idx).unsqueeze(1).unsqueeze(2)  # (B,1,1,T)
        causal   = torch.tril(
            torch.ones(tgt_len, tgt_len, dtype=torch.bool, device=tgt.device)
        )
        return pad_mask & causal  # (B,1,T,T)

    # ------------------------------------------------------------------ init

    def _init_weights(self):
        for name, p in self.named_parameters():
            if p.dim() > 1:
                nn.init.xavier_uniform_(p)
            elif "bias" in name:
                nn.init.zeros_(p)

    # ----------------------------------------------------------------- forward

    def forward(
        self,
        src: torch.Tensor,  # (B, src_len)
        tgt: torch.Tensor,  # (B, tgt_len) — right-shifted, starts with <BOS>
    ) -> tuple[torch.Tensor, list[torch.Tensor]]:
        """
        Returns
        -------
        logits             : (B, tgt_len, tgt_vocab_size)
        cross_attn_weights : list[(B, heads, tgt_len, src_len)] per decoder layer
        """
        src_mask = self.make_src_mask(src)
        tgt_mask = self.make_tgt_mask(tgt)

        enc_output             = self.encoder(src, src_mask)
        dec_output, cross_attn = self.decoder(tgt, enc_output, src_mask, tgt_mask)
        logits                 = self.output_projection(dec_output)
        return logits, cross_attn

    # ---------------------------------------------------------- greedy decode

    @torch.no_grad()
    def greedy_decode(
        self,
        src:     torch.Tensor,
        bos_idx: int,
        eos_idx: int,
        max_len: int = 128,
    ) -> torch.Tensor:
        """
        Greedy autoregressive decoding (argmax at each step).
        Stops when every sequence in the batch has emitted EOS.

        Returns decoded token sequences: (B, decoded_len)  incl. leading BOS.
        """
        self.eval()
        device   = src.device
        B        = src.size(0)
        src_mask = self.make_src_mask(src)
        enc_out  = self.encoder(src, src_mask)

        tgt      = torch.full((B, 1), bos_idx, dtype=torch.long, device=device)
        finished = torch.zeros(B, dtype=torch.bool, device=device)

        for _ in range(max_len - 1):
            tgt_mask    = self.make_tgt_mask(tgt)
            dec_out, _  = self.decoder(tgt, enc_out, src_mask, tgt_mask)
            next_logits = self.output_projection(dec_out[:, -1, :])
            next_token  = next_logits.argmax(dim=-1, keepdim=True)           # (B,1)
            next_token  = next_token.masked_fill(finished.unsqueeze(1), self.pad_idx)
            tgt         = torch.cat([tgt, next_token], dim=1)
            finished    = finished | (next_token.squeeze(1) == eos_idx)
            if finished.all():
                break

        return tgt

    # ------------------------------------------------------------ beam decode

    @torch.no_grad()
    def beam_decode(
        self,
        src:            torch.Tensor,
        bos_idx:        int,
        eos_idx:        int,
        beam_size:      int   = 4,
        max_len:        int   = 128,
        length_penalty: float = 0.6,
    ) -> torch.Tensor:
        """
        Beam search (batch_size=1).  Returns (1, decoded_len).
        Length penalty: score /= len^alpha  (Wu et al., 2016)
        """
        assert src.size(0) == 1, "beam_decode supports batch_size=1"
        self.eval()
        device   = src.device
        src_mask = self.make_src_mask(src)
        enc_out  = self.encoder(src, src_mask)

        enc_out  = enc_out.expand(beam_size, -1, -1)
        src_mask = src_mask.expand(beam_size, -1, -1, -1)

        beams       = torch.full((beam_size, 1), bos_idx, dtype=torch.long, device=device)
        beam_scores = torch.zeros(beam_size, device=device)
        completed:  list[tuple[float, torch.Tensor]] = []

        for step in range(max_len - 1):
            tgt_mask        = self.make_tgt_mask(beams)
            dec_out, _      = self.decoder(beams, enc_out, src_mask, tgt_mask)
            logits          = self.output_projection(dec_out[:, -1, :])
            log_probs       = F.log_softmax(logits, dim=-1)            # (beams, V)

            V            = log_probs.size(-1)
            total        = (beam_scores.unsqueeze(1) + log_probs).view(-1)
            top_scores, top_idx = total.topk(beam_size)
            beam_ids     = top_idx // V
            token_ids    = top_idx %  V

            new_beams    = torch.cat([beams[beam_ids], token_ids.unsqueeze(1)], dim=1)
            beam_scores  = top_scores

            for i in range(beam_size):
                if token_ids[i] == eos_idx:
                    penalty = (step + 1) ** length_penalty
                    completed.append((beam_scores[i].item() / penalty, new_beams[i].clone()))

            if len(completed) >= beam_size:
                break
            beams = new_beams

        if completed:
            best_seq = max(completed, key=lambda x: x[0])[1]
        else:
            best_seq = beams[beam_scores.argmax()]

        return best_seq.unsqueeze(0)

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
