"""Training configuration — serializable, resumable."""

from dataclasses import dataclass, field, asdict
from typing import List
import json


@dataclass
class TrainConfig:
    # ── Data ──────────────────────────────────────────────────────────────────
    data_path: str = "data/"
    num_classes: int = 10
    input_dim: int = 784          # override for your data
    train_split: float = 0.70
    val_split: float = 0.15       # test = 1 - train - val

    # ── Model ─────────────────────────────────────────────────────────────────
    hidden_dims: List[int] = field(default_factory=lambda: [512, 256, 128])
    dropout: float = 0.30

    # ── Optimiser ─────────────────────────────────────────────────────────────
    epochs: int = 100
    base_batch_size: int = 64     # per-GPU; effective = base_batch_size × world_size
    base_lr: float = 0.01         # LR for 1 GPU / base_batch_size — scaled linearly
    weight_decay: float = 1e-4
    momentum: float = 0.9
    grad_clip: float = 1.0

    # ── LR Schedule ───────────────────────────────────────────────────────────
    lr_warmup_epochs: int = 5
    lr_scheduler: str = "cosine"  # cosine | step | none

    # ── Checkpointing ─────────────────────────────────────────────────────────
    checkpoint_dir: str = "checkpoints/"
    checkpoint_every: int = 5     # epochs between routine saves
    keep_last_n: int = 3

    # ── Distributed ───────────────────────────────────────────────────────────
    backend: str = "nccl"         # nccl for GPU; gloo for CPU fallback
    find_unused_parameters: bool = False

    # ── Logging ───────────────────────────────────────────────────────────────
    log_dir: str = "logs/"
    log_every: int = 50           # steps

    # ── Reproducibility ───────────────────────────────────────────────────────
    seed: int = 42

    # ── AMP ───────────────────────────────────────────────────────────────────
    use_amp: bool = True          # automatic mixed precision (FP16)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "TrainConfig":
        with open(path) as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
