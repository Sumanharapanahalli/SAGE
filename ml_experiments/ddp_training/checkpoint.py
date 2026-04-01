"""
Fault-tolerant checkpoint manager for DDP training.

Design guarantees:
  - Atomic writes   : write to .tmp then os.rename (POSIX atomic on same filesystem)
  - Rank-0 only     : only the coordinator process writes; all ranks read on resume
  - Symlink cursor  : latest.pt → newest checkpoint (no path guessing on resume)
  - Pruning         : keeps last N checkpoints to cap disk usage
  - DDP-aware load  : strips `module.` prefix so raw model can load DDP-saved weights
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class CheckpointManager:
    def __init__(self, checkpoint_dir: str, keep_last_n: int = 3) -> None:
        self.dir = Path(checkpoint_dir)
        self.keep_last_n = keep_last_n
        self.dir.mkdir(parents=True, exist_ok=True)

    # ── Save ─────────────────────────────────────────────────────────────────

    def save(
        self,
        epoch: int,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: Any,
        scaler: Optional[torch.amp.GradScaler],
        metrics: Dict[str, Any],
        config_dict: Dict[str, Any],
        rank: int,
        tag: str = "",
    ) -> None:
        """Checkpoint the full training state. Skipped on non-zero ranks."""
        if rank != 0:
            return

        # Unwrap DDP to get the raw module's state dict
        raw_model = model.module if isinstance(model, nn.parallel.DistributedDataParallel) else model

        payload: Dict[str, Any] = {
            "epoch": epoch,
            "model_state_dict": raw_model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
            "scaler_state_dict": scaler.state_dict() if scaler is not None else None,
            "metrics": metrics,
            "config": config_dict,
        }

        suffix = f"_{tag}" if tag else ""
        tmp_path   = self.dir / f"ckpt_epoch_{epoch:04d}{suffix}.tmp"
        final_path = self.dir / f"ckpt_epoch_{epoch:04d}{suffix}.pt"

        # Atomic write: tmp → rename (survives mid-write crash)
        torch.save(payload, tmp_path)
        os.replace(tmp_path, final_path)          # atomic on POSIX, best-effort on Windows

        # Update latest symlink (or plain copy of path on systems without symlink support)
        latest = self.dir / "latest.pt"
        try:
            if latest.is_symlink() or latest.exists():
                latest.unlink()
            latest.symlink_to(final_path.name)
        except (OSError, NotImplementedError):
            # Fallback: write the path as a text cursor file
            (self.dir / "latest.txt").write_text(str(final_path))

        logger.info(f"[rank 0] Checkpoint saved → {final_path}  metrics={metrics}")
        self._prune()

    # ── Load / Resume ─────────────────────────────────────────────────────────

    def load_latest(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: Any,
        scaler: Optional[torch.amp.GradScaler],
        device: torch.device,
    ) -> int:
        """
        Load the latest checkpoint and restore all training state.
        Returns the epoch to resume FROM (start_epoch = saved_epoch + 1).
        Returns 0 if no checkpoint exists.
        """
        ckpt_path = self._resolve_latest()
        if ckpt_path is None:
            logger.info("No checkpoint found — training from scratch.")
            return 0

        logger.info(f"Resuming from {ckpt_path}")
        ckpt = torch.load(ckpt_path, map_location=device)

        # Load model — handle both DDP-wrapped and bare module
        target = model.module if isinstance(model, nn.parallel.DistributedDataParallel) else model
        target.load_state_dict(ckpt["model_state_dict"])

        optimizer.load_state_dict(ckpt["optimizer_state_dict"])

        if scheduler is not None and ckpt.get("scheduler_state_dict") is not None:
            scheduler.load_state_dict(ckpt["scheduler_state_dict"])

        if scaler is not None and ckpt.get("scaler_state_dict") is not None:
            scaler.load_state_dict(ckpt["scaler_state_dict"])

        epoch = ckpt["epoch"]
        logger.info(f"Resumed at epoch {epoch} — metrics: {ckpt.get('metrics', {})}")
        return epoch + 1   # resume from next epoch

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_latest(self) -> Optional[Path]:
        symlink = self.dir / "latest.pt"
        if symlink.exists():
            return symlink.resolve()
        cursor = self.dir / "latest.txt"
        if cursor.exists():
            p = Path(cursor.read_text().strip())
            return p if p.exists() else None
        # Fallback: highest epoch file
        files = sorted(self.dir.glob("ckpt_epoch_*.pt"))
        return files[-1] if files else None

    def _prune(self) -> None:
        """Delete old checkpoints beyond keep_last_n (ignores 'best' tagged ones)."""
        routine: List[Path] = sorted(
            [p for p in self.dir.glob("ckpt_epoch_*.pt") if "best" not in p.stem],
            key=lambda p: int(p.stem.split("_")[2]),
        )
        for old in routine[: -self.keep_last_n]:
            old.unlink(missing_ok=True)
            logger.debug(f"Pruned checkpoint: {old.name}")
