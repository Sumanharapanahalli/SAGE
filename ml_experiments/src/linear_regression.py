"""
Linear Regression via Mini-Batch Gradient Descent
==================================================
No scikit-learn dependency for model training.

Features
--------
- Z-score feature normalization (fit on training data ONLY — no leakage)
- Learning rate scheduling: constant | step | exponential | cosine
- Convergence detection: patience + relative-loss tolerance
- Gradient clipping for numerical stability
- L2 regularization
- Glicko-2-compatible scoring dict for Agent Gym integration
"""

import math
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class LinearRegressionGD:
    """
    Linear Regression implemented with Mini-Batch Gradient Descent.

    Parameters
    ----------
    learning_rate : float
        Initial learning rate (α₀).
    n_iterations : int
        Maximum number of GD iterations.
    batch_size : int
        Mini-batch size; set to len(X) for full-batch GD.
    tol : float
        Convergence tolerance on relative improvement of training loss.
    patience : int
        Consecutive non-improving iterations before early stop.
    lr_schedule : str
        One of ``"constant"``, ``"step"``, ``"exponential"``, ``"cosine"``.
    lr_decay : float
        Multiplicative decay factor (step / exponential schedules).
    step_size : int
        Iterations between decay steps (step schedule).
    l2_lambda : float
        L2 regularisation strength (0 = disabled).
    clip_grad : float
        Max ‖∇w‖ before rescaling (0 = disabled).
    random_state : int
        RNG seed for reproducibility.
    verbose : bool
        Emit progress logs every ``log_interval`` iterations.
    log_interval : int
        Logging stride.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        n_iterations: int = 10_000,
        batch_size: int = 32,
        tol: float = 1e-6,
        patience: int = 100,
        lr_schedule: str = "cosine",
        lr_decay: float = 0.95,
        step_size: int = 200,
        l2_lambda: float = 0.0,
        clip_grad: float = 1.0,
        random_state: int = 42,
        verbose: bool = True,
        log_interval: int = 1_000,
    ) -> None:
        self.learning_rate = learning_rate
        self.n_iterations = n_iterations
        self.batch_size = batch_size
        self.tol = tol
        self.patience = patience
        self.lr_schedule = lr_schedule
        self.lr_decay = lr_decay
        self.step_size = step_size
        self.l2_lambda = l2_lambda
        self.clip_grad = clip_grad
        self.random_state = random_state
        self.verbose = verbose
        self.log_interval = log_interval

        # ── Fitted attributes (populated by fit()) ────────────────────────────
        self.weights_: Optional[np.ndarray] = None
        self.bias_: float = 0.0
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.loss_history_: List[float] = []
        self.lr_history_: List[float] = []
        self.n_iter_: int = 0
        self.converged_: bool = False

    # ── Normalisation ─────────────────────────────────────────────────────────

    def _fit_scaler(self, X: np.ndarray) -> None:
        """Compute mean / std from training data ONLY."""
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0)
        # Constant features: set std to 1 to avoid division by zero
        self.std_ = np.where(self.std_ == 0.0, 1.0, self.std_)

    def _transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            raise RuntimeError("Scaler not fitted — call fit() first.")
        return (X - self.mean_) / self.std_

    # ── Learning-rate scheduling ──────────────────────────────────────────────

    def _get_lr(self, iteration: int) -> float:
        lr0 = self.learning_rate
        if self.lr_schedule == "constant":
            return lr0
        if self.lr_schedule == "step":
            return lr0 * (self.lr_decay ** (iteration // self.step_size))
        if self.lr_schedule == "exponential":
            return lr0 * (self.lr_decay ** iteration)
        if self.lr_schedule == "cosine":
            lr_min = lr0 / 100.0
            return lr_min + 0.5 * (lr0 - lr_min) * (
                1.0 + math.cos(math.pi * iteration / max(self.n_iterations, 1))
            )
        raise ValueError(
            f"Unknown lr_schedule {self.lr_schedule!r}. "
            "Choose from: constant, step, exponential, cosine."
        )

    # ── Forward / loss ────────────────────────────────────────────────────────

    def _forward(self, X: np.ndarray) -> np.ndarray:
        return X @ self.weights_ + self.bias_

    @staticmethod
    def _mse(y_pred: np.ndarray, y_true: np.ndarray) -> float:
        return float(np.mean((y_pred - y_true) ** 2))

    # ── Fit ───────────────────────────────────────────────────────────────────

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
    ) -> "LinearRegressionGD":
        """
        Fit the model on (X_train, y_train).

        Parameters
        ----------
        X_train : array (n_train, n_features)
        y_train : array (n_train,)
        X_val   : array (n_val, n_features) — optional; used for patience check
        y_val   : array (n_val,) — optional
        """
        rng = np.random.default_rng(self.random_state)

        X_train = np.asarray(X_train, dtype=float)
        y_train = np.asarray(y_train, dtype=float).ravel()
        n_samples, n_features = X_train.shape

        # Scaler fitted on training data only
        self._fit_scaler(X_train)
        X_norm = self._transform(X_train)

        X_val_norm = y_val_arr = None
        if X_val is not None and y_val is not None:
            X_val_norm = self._transform(np.asarray(X_val, dtype=float))
            y_val_arr = np.asarray(y_val, dtype=float).ravel()

        # Xavier-ish weight initialisation
        scale = math.sqrt(2.0 / n_features)
        self.weights_ = rng.standard_normal(n_features) * scale
        self.bias_ = 0.0

        self.loss_history_.clear()
        self.lr_history_.clear()

        best_eval_loss = float("inf")
        patience_ctr = 0
        prev_train_loss = float("inf")
        effective_bs = min(self.batch_size, n_samples)

        for i in range(self.n_iterations):
            # ── Mini-batch sampling ───────────────────────────────────────────
            idx = rng.choice(n_samples, size=effective_bs, replace=False)
            Xb, yb = X_norm[idx], y_train[idx]

            # ── Gradients (MSE) ───────────────────────────────────────────────
            err = self._forward(Xb) - yb          # (batch,)
            grad_w = (2.0 / effective_bs) * (Xb.T @ err)
            grad_b = (2.0 / effective_bs) * err.sum()

            # L2 penalty
            if self.l2_lambda > 0.0:
                grad_w += 2.0 * self.l2_lambda * self.weights_

            # Gradient clipping
            if self.clip_grad > 0.0:
                gnorm = float(np.linalg.norm(grad_w))
                if gnorm > self.clip_grad:
                    grad_w = grad_w * (self.clip_grad / gnorm)

            # ── Parameter update ──────────────────────────────────────────────
            lr = self._get_lr(i)
            self.weights_ -= lr * grad_w
            self.bias_ -= lr * grad_b

            # ── Book-keeping ──────────────────────────────────────────────────
            train_loss = self._mse(self._forward(X_norm), y_train)
            self.loss_history_.append(train_loss)
            self.lr_history_.append(lr)

            # Evaluate on validation set (or training set if none provided)
            eval_loss = train_loss
            if X_val_norm is not None:
                eval_loss = self._mse(self._forward(X_val_norm), y_val_arr)

            # ── Convergence detection ─────────────────────────────────────────
            if eval_loss < best_eval_loss - self.tol:
                best_eval_loss = eval_loss
                patience_ctr = 0
            else:
                patience_ctr += 1

            rel_improvement = abs(prev_train_loss - train_loss) / (prev_train_loss + 1e-12)
            prev_train_loss = train_loss

            if patience_ctr >= self.patience and rel_improvement < self.tol:
                self.converged_ = True
                self.n_iter_ = i + 1
                if self.verbose:
                    logger.info(
                        "Converged at iter %d | train_loss=%.6f | eval_loss=%.6f",
                        i + 1,
                        train_loss,
                        eval_loss,
                    )
                break

            if self.verbose and (i % self.log_interval == 0 or i == self.n_iterations - 1):
                logger.info(
                    "Iter %6d | lr=%.3e | train_loss=%.4f | eval_loss=%.4f",
                    i,
                    lr,
                    train_loss,
                    eval_loss,
                )
        else:
            self.n_iter_ = self.n_iterations

        return self

    # ── Predict ───────────────────────────────────────────────────────────────

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return predictions for X (applies stored normalisation)."""
        X_norm = self._transform(np.asarray(X, dtype=float))
        return self._forward(X_norm)

    # ── Score ─────────────────────────────────────────────────────────────────

    def score(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """
        Compute regression metrics.

        Returns
        -------
        dict with keys: rmse, mae, r2, mse
        """
        y = np.asarray(y, dtype=float).ravel()
        y_pred = self.predict(X)
        residuals = y - y_pred

        mse = float(np.mean(residuals ** 2))
        rmse = float(np.sqrt(mse))
        mae = float(np.mean(np.abs(residuals)))
        ss_res = float(np.sum(residuals ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        r2 = 1.0 - ss_res / (ss_tot + 1e-12)

        return {"rmse": rmse, "mae": mae, "r2": float(r2), "mse": mse}

    # ── Representation ────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"LinearRegressionGD(lr={self.learning_rate}, "
            f"schedule={self.lr_schedule!r}, "
            f"n_iter={self.n_iterations}, "
            f"batch={self.batch_size})"
        )
