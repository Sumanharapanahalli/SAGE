"""
Distributed Data-Parallel (DDP) training — fault-tolerant, AMP-enabled.

Launch:
    torchrun --standalone --nproc_per_node=<NUM_GPUS> train_ddp.py [--config cfg.json] [--resume]

Key design decisions:
  - Linear scaling rule  : LR scales linearly with effective batch size (Goyal et al., 2017)
  - Warmup + cosine decay: prevents early instability when LR is high after scaling
  - Atomic checkpoints   : write to .tmp then os.rename — survives mid-write crashes
  - AMP (FP16)           : GradScaler handles underflow; disabled transparently on CPU
  - Gradient clipping    : prevents exploding gradients common with large LR
  - set_epoch sampler    : ensures each epoch gets a different shuffle across all ranks
  - Broadcast data       : rank 0 loads & preprocesses; broadcast to all ranks
                           (for very large datasets, replace with shared filesystem / mmap)
"""

import argparse
import logging
import math
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
import torch
import torch.distributed as dist
import torch.nn as nn
from torch.amp import GradScaler, autocast   # replaces deprecated torch.cuda.amp (PyTorch 2.3+)
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import DataLoader
from torch.utils.data.distributed import DistributedSampler

import experiment_logger as exp_log
from checkpoint import CheckpointManager
from config import TrainConfig
from dataset import (
    ClassificationDataset,
    check_class_balance,
    fit_scaler_on_train,
    stratified_split,
)
from evaluate import evaluate
from model import MLPClassifier


# ─── Distributed setup ───────────────────────────────────────────────────────

def setup_dist() -> Tuple[int, int, int]:
    """
    Initialise process group from environment variables set by torchrun.
    Returns (rank, world_size, local_rank).
    """
    dist.init_process_group(backend=os.environ.get("DIST_BACKEND", "nccl"))
    rank       = dist.get_rank()
    world_size = dist.get_world_size()
    local_rank = int(os.environ["LOCAL_RANK"])
    torch.cuda.set_device(local_rank)
    return rank, world_size, local_rank


def cleanup_dist() -> None:
    dist.destroy_process_group()


def barrier() -> None:
    if dist.is_initialized():
        dist.barrier()


# ─── Linear LR scaling (Goyal et al., 2017) ──────────────────────────────────

def linear_scaled_lr(base_lr: float, base_batch: int, world_size: int, per_gpu_batch: int) -> float:
    """
    Scale learning rate linearly with effective batch size:
        lr = base_lr × (num_gpus × per_gpu_batch) / base_batch

    Rationale: the noise scale of SGD is proportional to lr / batch_size.
    Keeping this ratio constant across different world sizes preserves training dynamics.
    """
    effective_batch = world_size * per_gpu_batch
    return base_lr * (effective_batch / base_batch)


# ─── LR scheduler with linear warmup ─────────────────────────────────────────

def build_scheduler(
    optimizer: torch.optim.Optimizer,
    cfg: TrainConfig,
    steps_per_epoch: int,
) -> torch.optim.lr_scheduler.LambdaLR:
    """
    Linear warmup → cosine decay (or step decay or constant).
    Warmup prevents gradient explosion in early steps when LR is large after scaling.
    """
    total_steps  = cfg.epochs * steps_per_epoch
    warmup_steps = cfg.lr_warmup_epochs * steps_per_epoch

    def lr_lambda(step: int) -> float:
        # Phase 1 — linear warmup
        if step < warmup_steps:
            return max(step / warmup_steps, 1e-6)

        # Phase 2 — chosen decay
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        if cfg.lr_scheduler == "cosine":
            return 0.5 * (1.0 + math.cos(math.pi * progress))
        elif cfg.lr_scheduler == "step":
            decay_at = [int(cfg.epochs * 0.5), int(cfg.epochs * 0.75)]
            epoch    = step // steps_per_epoch
            decay    = 1.0
            for milestone in decay_at:
                if epoch >= milestone:
                    decay *= 0.1
            return decay
        return 1.0  # none / constant

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


# ─── Data loading ─────────────────────────────────────────────────────────────

def prepare_datasets(
    cfg: TrainConfig, rank: int
) -> Tuple[ClassificationDataset, ClassificationDataset, ClassificationDataset, bool]:
    """
    Rank 0 loads and preprocesses data; result is broadcast to all ranks.
    Scaler is fit on train only (no leakage).
    Returns (train_ds, val_ds, test_ds, class_imbalanced).
    """
    if rank == 0:
        # ── Replace this section with your real data loading ──────────────────
        from sklearn.datasets import make_classification

        X, y = make_classification(
            n_samples    = 12_000,
            n_features   = cfg.input_dim,
            n_informative= 20,
            n_redundant  = 10,
            n_classes    = cfg.num_classes,
            n_clusters_per_class=1,
            weights      = None,   # balanced; pass list for imbalanced demo
            random_state = cfg.seed,
        )
        X = X.astype(np.float32)
        y = y.astype(np.int64)
        # ─────────────────────────────────────────────────────────────────────

        imbalanced = check_class_balance(y)

        X_tr, X_val, X_te, y_tr, y_val, y_te = stratified_split(
            X, y,
            train_split=cfg.train_split,
            val_split=cfg.val_split,
            seed=cfg.seed,
        )
        X_tr, X_val, X_te, _ = fit_scaler_on_train(X_tr, X_val, X_te)

        payload = [
            torch.tensor(X_tr),  torch.tensor(y_tr),
            torch.tensor(X_val), torch.tensor(y_val),
            torch.tensor(X_te),  torch.tensor(y_te),
            imbalanced,
        ]
    else:
        payload = [None] * 7

    dist.broadcast_object_list(payload, src=0)
    X_tr, y_tr, X_val, y_val, X_te, y_te, imbalanced = payload

    train_ds = ClassificationDataset(X_tr.numpy(), y_tr.numpy())
    val_ds   = ClassificationDataset(X_val.numpy(), y_val.numpy())
    test_ds  = ClassificationDataset(X_te.numpy(), y_te.numpy())
    return train_ds, val_ds, test_ds, bool(imbalanced)


# ─── Training step ────────────────────────────────────────────────────────────

def train_one_epoch(
    model     : nn.Module,
    loader    : DataLoader,
    optimizer : torch.optim.Optimizer,
    scheduler : torch.optim.lr_scheduler.LambdaLR,
    scaler    : Optional[GradScaler],
    device    : torch.device,
    epoch     : int,
    cfg       : TrainConfig,
    rank      : int,
    log       : logging.Logger,
) -> Dict[str, float]:
    model.train()
    criterion   = nn.CrossEntropyLoss()
    total_loss  = correct = total = 0
    t0          = time.perf_counter()

    for step, (X_b, y_b) in enumerate(loader):
        X_b = X_b.to(device, non_blocking=True)
        y_b = y_b.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with autocast("cuda", enabled=(scaler is not None)):
            logits = model(X_b)
            loss   = criterion(logits, y_b)

        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)                                    # unscale before clip
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimizer.step()

        scheduler.step()

        total_loss += loss.item() * len(y_b)
        correct    += (logits.argmax(-1) == y_b).sum().item()
        total      += len(y_b)

        if rank == 0 and (step + 1) % cfg.log_every == 0:
            log.info(
                f"Epoch {epoch:03d}  step {step+1}/{len(loader)}  "
                f"loss={loss.item():.4f}  "
                f"lr={scheduler.get_last_lr()[0]:.2e}"
            )

    return {
        "train_loss":     round(total_loss / total, 4),
        "train_accuracy": round(correct / total, 4),
        "epoch_time_s":   round(time.perf_counter() - t0, 1),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="DDP training")
    parser.add_argument("--config", default=None, help="Path to TrainConfig JSON")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    args = parser.parse_args()

    rank, world_size, local_rank = setup_dist()
    device = torch.device(f"cuda:{local_rank}")

    # Config
    cfg = TrainConfig.load(args.config) if args.config else TrainConfig()

    # Logging — rank 0 only (other ranks would produce duplicate, interleaved output)
    if rank == 0:
        Path(cfg.log_dir).mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s][R0] %(message)s",
            datefmt="%H:%M:%S",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(Path(cfg.log_dir) / "train.log"),
            ],
        )
    else:
        logging.disable(logging.CRITICAL)

    log = logging.getLogger(__name__)

    # Per-rank seeds (same base + rank offset keeps augmentation varied across GPUs)
    torch.manual_seed(cfg.seed + rank)
    np.random.seed(cfg.seed + rank)

    if rank == 0:
        log.info(f"Starting DDP training — world_size={world_size}  device={device}")
        cfg.save(Path(cfg.log_dir) / "config.json")

    # ── Data ──────────────────────────────────────────────────────────────────
    train_ds, val_ds, test_ds, class_imbalanced = prepare_datasets(cfg, rank)

    train_sampler = DistributedSampler(
        train_ds, num_replicas=world_size, rank=rank, shuffle=True, seed=cfg.seed
    )
    val_sampler = DistributedSampler(
        val_ds, num_replicas=world_size, rank=rank, shuffle=False
    )

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg.base_batch_size,
        sampler=train_sampler,
        num_workers=min(4, os.cpu_count() or 1),
        pin_memory=True,
        persistent_workers=True,
        drop_last=True,   # keeps all batches the same size — important for BN in DDP
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg.base_batch_size * 2,
        sampler=val_sampler,
        num_workers=min(4, os.cpu_count() or 1),
        pin_memory=True,
    )
    # Test is evaluated once at the end; only rank 0 needs it
    test_loader = (
        DataLoader(test_ds, batch_size=cfg.base_batch_size * 2, shuffle=False,
                   num_workers=2, pin_memory=True)
        if rank == 0 else None
    )

    # ── Model + DDP ───────────────────────────────────────────────────────────
    model = MLPClassifier(
        input_dim  =cfg.input_dim,
        hidden_dims=cfg.hidden_dims,
        num_classes=cfg.num_classes,
        dropout    =cfg.dropout,
    ).to(device)

    model = DDP(
        model,
        device_ids            =[local_rank],
        output_device         =local_rank,
        find_unused_parameters=cfg.find_unused_parameters,
        # gradient_as_bucket_view=True,  # reduces memory; requires PyTorch ≥ 1.13
    )

    # ── Optimiser with linear LR scaling ─────────────────────────────────────
    scaled_lr = linear_scaled_lr(cfg.base_lr, cfg.base_batch_size, world_size, cfg.base_batch_size)
    if rank == 0:
        log.info(
            f"Linear LR scaling: {cfg.base_lr} × {world_size} GPUs "
            f"(eff. batch={world_size * cfg.base_batch_size}) → scaled_lr={scaled_lr:.6f}"
        )

    optimizer = torch.optim.SGD(
        model.parameters(),
        lr          =scaled_lr,
        momentum    =cfg.momentum,
        weight_decay=cfg.weight_decay,
        nesterov    =True,
    )
    scheduler = build_scheduler(optimizer, cfg, len(train_loader))
    scaler    = GradScaler("cuda") if (cfg.use_amp and torch.cuda.is_available()) else None

    # ── Checkpointing + optional resume ──────────────────────────────────────
    ckpt_mgr    = CheckpointManager(cfg.checkpoint_dir, keep_last_n=cfg.keep_last_n)
    start_epoch = 0
    if args.resume:
        start_epoch = ckpt_mgr.load_latest(model, optimizer, scheduler, scaler, device)
        barrier()   # all ranks must finish loading before training starts

    # ── Experiment tracking (rank 0) ──────────────────────────────────────────
    if rank == 0:
        run_id = exp_log.start_run(
            config    =cfg.to_dict(),
            world_size=world_size,
            scaled_lr =scaled_lr,
        )

    best_val_f1 = 0.0

    # ── Training loop ─────────────────────────────────────────────────────────
    for epoch in range(start_epoch, cfg.epochs):
        train_sampler.set_epoch(epoch)   # crucial: different shuffle each epoch

        train_metrics = train_one_epoch(
            model, train_loader, optimizer, scheduler, scaler,
            device, epoch, cfg, rank, log,
        )

        # Synchronise before evaluation
        barrier()

        val_metrics: Dict[str, float] = {}
        if rank == 0:
            val_metrics = evaluate(model, val_loader, device, cfg.num_classes, "val")

        # Routine checkpoint
        if rank == 0 and (epoch + 1) % cfg.checkpoint_every == 0:
            ckpt_mgr.save(
                epoch, model, optimizer, scheduler, scaler,
                {**train_metrics, **val_metrics}, cfg.to_dict(), rank=0,
            )

        # Best-model checkpoint
        if rank == 0:
            f1_now = val_metrics.get("val_f1_macro", 0.0)
            if f1_now > best_val_f1:
                best_val_f1 = f1_now
                ckpt_mgr.save(
                    epoch, model, optimizer, scheduler, scaler,
                    {**train_metrics, **val_metrics, "is_best": True},
                    cfg.to_dict(), rank=0, tag="best",
                )
                log.info(f"▲ New best val F1={best_val_f1:.4f}  epoch={epoch}")

            exp_log.log_epoch(run_id, epoch, {**train_metrics, **val_metrics})

        barrier()

    # ── Final test evaluation ─────────────────────────────────────────────────
    if rank == 0:
        test_metrics = evaluate(model, test_loader, device, cfg.num_classes, "test")
        log.info(f"Final test metrics: {test_metrics}")
        exp_log.finish_run(run_id, test_metrics)

    cleanup_dist()


if __name__ == "__main__":
    main()
