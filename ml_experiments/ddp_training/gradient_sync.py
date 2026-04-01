"""
Explicit gradient synchronization utilities for DDP training.

DDP automatically synchronises gradients via AllReduce during backward().
This module exposes:

  1. GradSyncMonitor  — hook-based per-parameter gradient norm tracking
  2. GradCompressor   — PowerSGD low-rank gradient compression (reduces comm. bandwidth)
  3. allreduce_tensor — bare AllReduce helper for custom reduce operations

When to use each:
  - GradSyncMonitor   : diagnose vanishing/exploding grads across ranks (dev / debug)
  - GradCompressor    : large models (>100 M params) where bandwidth is the bottleneck
  - allreduce_tensor  : custom metrics aggregation across ranks (e.g. global loss)

References:
  - Goyal et al. 2017  — "Accurate, Large Minibatch SGD: Training ImageNet in 1 Hour"
  - Vogels et al. 2019 — "PowerSGD: Practical Low-Rank Gradient Compression"
  - PyTorch DDP docs   — https://pytorch.org/docs/stable/notes/ddp.html
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import torch
import torch.distributed as dist
import torch.nn as nn
from torch.distributed.algorithms.ddp_comm_hooks import powerSGD_hook as powerSGD

logger = logging.getLogger(__name__)


# ─── 1. AllReduce helper ──────────────────────────────────────────────────────

def allreduce_tensor(tensor: torch.Tensor, op: dist.ReduceOp = dist.ReduceOp.SUM) -> torch.Tensor:
    """
    Blocking AllReduce across all ranks.
    Returns the reduced result on every rank.

    Usage:
        global_loss = allreduce_tensor(local_loss_sum) / world_size
    """
    if not dist.is_initialized():
        return tensor
    handle = dist.all_reduce(tensor, op=op, async_op=False)
    return tensor


def allreduce_scalar(value: float, op: dist.ReduceOp = dist.ReduceOp.SUM) -> float:
    """Convenience wrapper — reduces a Python float across all ranks."""
    t = torch.tensor(value, dtype=torch.float64,
                     device="cuda" if torch.cuda.is_available() else "cpu")
    allreduce_tensor(t, op)
    return t.item()


# ─── 2. Gradient norm monitor ────────────────────────────────────────────────

class GradSyncMonitor:
    """
    Registers backward hooks on every parameter to log gradient norms.
    Useful during development to verify DDP actually synchronises gradients
    and to catch vanishing/exploding gradient problems early.

    Usage:
        monitor = GradSyncMonitor(model, log_every=100)
        # inside train loop:
        monitor.step()            # increments internal step counter
        monitor.report()          # logs summary at log_every steps
        monitor.remove()          # call once training ends
    """

    def __init__(self, model: nn.Module, log_every: int = 100, rank: int = 0) -> None:
        self._rank     = rank
        self._log_every = log_every
        self._step     = 0
        self._norms: Dict[str, List[float]] = {}
        self._handles  = []

        for name, param in model.named_parameters():
            if param.requires_grad:
                self._norms[name] = []
                handle = param.register_hook(self._make_hook(name))
                self._handles.append(handle)

    def _make_hook(self, name: str):
        def hook(grad: torch.Tensor) -> None:
            self._norms[name].append(grad.detach().norm().item())
        return hook

    def step(self) -> None:
        self._step += 1

    def report(self) -> Optional[Dict[str, float]]:
        """Log grad norms if log_every steps have passed. Returns the stats dict or None."""
        if self._rank != 0 or self._step % self._log_every != 0:
            return None

        stats = {
            name: round(sum(vs) / len(vs), 6)
            for name, vs in self._norms.items()
            if vs
        }
        total_norm = sum(stats.values()) ** 0.5
        logger.info(f"[GradSync step={self._step}] total_norm={total_norm:.4f}  "
                    f"layers={len(stats)}")

        # Warn on anomalies
        for name, norm in stats.items():
            if norm < 1e-8:
                logger.warning(f"  Vanishing gradient: {name} norm={norm:.2e}")
            elif norm > 1e3:
                logger.warning(f"  Exploding gradient: {name} norm={norm:.2e}")

        # Clear accumulated norms
        for key in self._norms:
            self._norms[key] = []

        return stats

    def remove(self) -> None:
        """Deregister all hooks. Call once training ends to avoid memory leaks."""
        for h in self._handles:
            h.remove()
        self._handles.clear()
        logger.debug("GradSyncMonitor: all hooks removed.")


# ─── 3. PowerSGD gradient compression ────────────────────────────────────────

class GradCompressor:
    """
    Wraps PyTorch's built-in PowerSGD DDP communication hook.

    PowerSGD compresses gradients to low-rank approximations before AllReduce:
      - Reduces all-reduce communication volume by up to 40× for large layers
      - Adds per-step approximation error that is corrected over time (error feedback)
      - Compression rank `matrix_approximation_rank` controls quality / bandwidth trade-off:
            rank=1  → ~90% bandwidth reduction, slight accuracy degradation
            rank=4  → ~75% bandwidth reduction, near-lossless for most architectures

    Recommended when:
      - Model has > 100 M parameters AND
      - GPU ↔ GPU bandwidth is the training bottleneck (multi-node more than single-node)

    Usage:
        compressor = GradCompressor(model, matrix_approximation_rank=4)
        compressor.register(ddp_model)
        # No other changes to training loop needed.
    """

    def __init__(
        self,
        model: nn.Module,
        matrix_approximation_rank: int = 4,
        start_powerSGD_iter: int = 1_000,
        use_error_feedback: bool = True,
        warm_start: bool = True,
    ) -> None:
        self._rank = matrix_approximation_rank
        self._state = powerSGD.PowerSGDState(
            process_group=dist.group.WORLD if dist.is_initialized() else None,
            matrix_approximation_rank=matrix_approximation_rank,
            start_powerSGD_iter=start_powerSGD_iter,
            use_error_feedback=use_error_feedback,
            warm_start=warm_start,
        )
        logger.info(
            f"PowerSGD initialised — rank={matrix_approximation_rank}  "
            f"error_feedback={use_error_feedback}  "
            f"warmup_iters={start_powerSGD_iter}"
        )

    def register(self, ddp_model: nn.parallel.DistributedDataParallel) -> None:
        """
        Registers the PowerSGD hook on the DDP model.
        Must be called AFTER wrapping the model with DDP.
        """
        ddp_model.register_comm_hook(self._state, powerSGD.powerSGD_hook)
        logger.info("PowerSGD comm hook registered on DDP model.")

    @property
    def state(self) -> powerSGD.PowerSGDState:
        return self._state


# ─── 4. Gradient bucket inspector (debug) ────────────────────────────────────

def register_bucket_logging_hook(
    ddp_model: nn.parallel.DistributedDataParallel,
    rank: int = 0,
) -> None:
    """
    Registers a no-op comm hook that logs the size of each gradient bucket
    before AllReduce. Useful for tuning `bucket_cap_mb` in DDP.

    Only logs on rank 0. Replace with your real hook as needed.
    """
    if rank != 0:
        return  # only instrument rank 0 to avoid log floods

    def _logging_hook(state, bucket):
        tensors = bucket.gradients()
        total   = sum(t.numel() * t.element_size() for t in tensors)
        logger.debug(f"Gradient bucket: {len(tensors)} tensors  size={total / 1024:.1f} KB")
        return dist.all_reduce(bucket.buffer(), async_op=True).get_future()

    ddp_model.register_comm_hook(None, _logging_hook)
    logger.info("[rank 0] Bucket logging hook registered.")
