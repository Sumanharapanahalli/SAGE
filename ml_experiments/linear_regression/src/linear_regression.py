"""
Linear Regression via Batch Gradient Descent — from scratch (no sklearn).

Features:
  - StandardScaler (fit on train only — no leakage)
  - Learning rate scheduling: constant | step | exponential | cosine
  - Convergence detection (loss delta threshold)
  - He-initialized weights for stable gradient flow
"""

import logging
from typing import Dict, List, Optional

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Feature Normalizer
# ---------------------------------------------------------------------------

class StandardScaler:
    """
    Manual StandardScaler — must be fit on training data ONLY.
    Prevents data leakage: transform test/val with training statistics.
    """

    def __init__(self) -> None:
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self._fitted = False

    def fit(self, X: np.ndarray) -> "StandardScaler":
        """Compute mean and std from training data."""
        self.mean_ = np.mean(X, axis=0)
        self.std_ = np.std(X, axis=0)
        # Constant features: avoid division by zero
        self.std_ = np.where(self.std_ == 0, 1.0, self.std_)
        self._fitted = True
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Apply training statistics to any split (train, val, test)."""
        if not self._fitted:
            raise RuntimeError("StandardScaler must be fit before transform.")
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit on X and return transformed X (training split only)."""
        return self.fit(X).transform(X)


# ---------------------------------------------------------------------------
# Learning Rate Schedulers
# ---------------------------------------------------------------------------

class LRScheduler:
    """Collection of learning rate decay strategies."""

    @staticmethod
    def constant(initial_lr: float, epoch: int, **_) -> float:
        return initial_lr

    @staticmethod
    def step_decay(
        initial_lr: float, epoch: int, drop: float = 0.5, epochs_drop: int = 200
    ) -> float:
        """Halve LR every `epochs_drop` epochs."""
        return initial_lr * (drop ** (epoch // epochs_drop))

    @staticmethod
    def exponential_decay(
        initial_lr: float, epoch: int, decay_rate: float = 0.0003
    ) -> float:
        """Smooth exponential decay: lr * exp(-k * t)."""
        return initial_lr * np.exp(-decay_rate * epoch)

    @staticmethod
    def cosine_annealing(
        initial_lr: float,
        epoch: int,
        T_max: int = 10_000,
        eta_min: float = 1e-7,
    ) -> float:
        """Cosine schedule from initial_lr → eta_min over T_max steps."""
        return eta_min + (initial_lr - eta_min) * 0.5 * (
            1.0 + np.cos(np.pi * epoch / T_max)
        )

    REGISTRY: Dict = {
        "constant": constant.__func__,       # type: ignore[attr-defined]
        "step": step_decay.__func__,         # type: ignore[attr-defined]
        "exponential": exponential_decay.__func__,  # type: ignore[attr-defined]
        "cosine": cosine_annealing.__func__,  # type: ignore[attr-defined]
    }

    @classmethod
    def get(cls, name: str):
        if name not in cls.REGISTRY:
            raise ValueError(
                f"Unknown schedule '{name}'. Choose from {list(cls.REGISTRY)}."
            )
        return cls.REGISTRY[name]


# ---------------------------------------------------------------------------
# Linear Regression — Batch Gradient Descent
# ---------------------------------------------------------------------------

class LinearRegressionGD:
    """
    Linear Regression via Batch Gradient Descent.

    Hypothesis:   ŷ = X @ w + b
    Loss (MSE):   L = (1/n) Σ (ŷᵢ - yᵢ)²
    Gradients:    ∂L/∂w = (2/n) Xᵀ(ŷ - y)
                  ∂L/∂b = (2/n) Σ(ŷᵢ - yᵢ)

    Parameters
    ----------
    learning_rate : float
        Base (initial) learning rate.
    n_iterations : int
        Maximum gradient descent steps.
    tolerance : float
        Stop when |loss_{t} - loss_{t-1}| < tolerance (convergence).
    lr_schedule : str
        One of "constant" | "step" | "exponential" | "cosine".
    random_state : int
        Seed for reproducible weight initialization.
    verbose : bool
        Print training progress.
    log_every : int
        Logging frequency (every N epochs).
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        n_iterations: int = 10_000,
        tolerance: float = 1e-7,
        lr_schedule: str = "exponential",
        random_state: int = 42,
        verbose: bool = True,
        log_every: int = 1_000,
    ) -> None:
        self.learning_rate = learning_rate
        self.n_iterations = n_iterations
        self.tolerance = tolerance
        self.lr_schedule = lr_schedule
        self.random_state = random_state
        self.verbose = verbose
        self.log_every = log_every

        # State populated by fit()
        self.weights_: Optional[np.ndarray] = None
        self.bias_: float = 0.0
        self.loss_history_: List[float] = []
        self.lr_history_: List[float] = []
        self.converged_at_: Optional[int] = None
        self.n_iter_actual_: int = 0

        self.logger = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_lr(self, epoch: int) -> float:
        fn = LRScheduler.get(self.lr_schedule)
        kwargs = (
            {"T_max": self.n_iterations}
            if self.lr_schedule == "cosine"
            else {}
        )
        return float(fn(self.learning_rate, epoch, **kwargs))

    @staticmethod
    def _mse(y_pred: np.ndarray, y_true: np.ndarray) -> float:
        return float(np.mean((y_pred - y_true) ** 2))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LinearRegressionGD":
        """
        Train via batch gradient descent.

        X must already be normalized (use StandardScaler.fit_transform on train).
        y may optionally be normalized (recommended for numerical stability).
        """
        np.random.seed(self.random_state)
        n_samples, n_features = X.shape

        # He initialization — variance 2/fan_in (stable for regression)
        self.weights_ = np.random.randn(n_features) * np.sqrt(2.0 / n_features)
        self.bias_ = 0.0
        self.loss_history_ = []
        self.lr_history_ = []
        self.converged_at_ = None

        prev_loss = float("inf")

        for epoch in range(self.n_iterations):
            # Forward pass
            y_pred = X @ self.weights_ + self.bias_

            # MSE loss
            loss = self._mse(y_pred, y)
            self.loss_history_.append(loss)

            # Current LR
            lr = self._get_lr(epoch)
            self.lr_history_.append(lr)

            # Convergence check (after first step)
            if epoch > 0 and abs(prev_loss - loss) < self.tolerance:
                self.converged_at_ = epoch
                self.logger.info(
                    f"Converged at epoch {epoch:,} | "
                    f"loss={loss:.8f} | Δ={abs(prev_loss - loss):.2e}"
                )
                break
            prev_loss = loss

            # Gradients
            error = y_pred - y                    # (n,)
            dw = (X.T @ error) / n_samples        # (p,)
            db = np.mean(error)                   # scalar

            # Gradient descent update
            self.weights_ -= lr * dw
            self.bias_ -= lr * db

            if self.verbose and epoch % self.log_every == 0:
                self.logger.info(
                    f"Epoch {epoch:6,d} | MSE={loss:.6f} | LR={lr:.2e}"
                )

        self.n_iter_actual_ = epoch + 1  # noqa: F821 (always assigned)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.weights_ is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
        return X @ self.weights_ + self.bias_

    def get_params(self) -> Dict:
        return {
            "learning_rate": self.learning_rate,
            "n_iterations": self.n_iterations,
            "tolerance": self.tolerance,
            "lr_schedule": self.lr_schedule,
            "random_state": self.random_state,
        }
