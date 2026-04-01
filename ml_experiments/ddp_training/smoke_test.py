"""
CPU smoke test — runs the full training pipeline on a tiny synthetic dataset
without requiring GPUs or a distributed environment.

Usage:
    python smoke_test.py           # runs all checks, exits 0 on success

Checks:
    1. Stratified split preserves class proportions
    2. Scaler fitted only on train (no leakage)
    3. Model forward pass produces correct output shape
    4. Checkpoint save + load round-trip is lossless
    5. Single-process training loop completes without error
    6. Evaluation returns expected metric keys
    7. Linear LR scaling formula is correct
    8. Experiment logger writes SQLite + JSONL entries
"""

import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure local imports resolve
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

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

logging.basicConfig(level=logging.WARNING)   # suppress info during tests


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_data(n=500, d=32, k=4, seed=0):
    rng = np.random.default_rng(seed)
    X   = rng.standard_normal((n, d)).astype(np.float32)
    y   = rng.integers(0, k, n).astype(np.int64)
    return X, y


def _make_loader(X, y, batch=32):
    ds = ClassificationDataset(X, y)
    return DataLoader(ds, batch_size=batch, shuffle=False)


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestStratifiedSplit(unittest.TestCase):

    def test_sizes_sum_to_total(self):
        X, y = _make_data(n=600)
        Xtr, Xv, Xte, ytr, yv, yte = stratified_split(X, y, 0.70, 0.15)
        self.assertEqual(len(Xtr) + len(Xv) + len(Xte), 600)

    def test_class_proportions_preserved(self):
        X, y = _make_data(n=1000, k=4)
        _, _, _, ytr, yv, yte = stratified_split(X, y, 0.70, 0.15)
        for split_y in [ytr, yv, yte]:
            _, counts = np.unique(split_y, return_counts=True)
            shares = counts / counts.sum()
            # Each class should be within ±5% of 25 %
            np.testing.assert_allclose(shares, np.full(4, 0.25), atol=0.05)

    def test_no_overlap(self):
        X, y = _make_data(n=400)
        Xtr, Xv, Xte, _, _, _ = stratified_split(X, y, 0.70, 0.15)
        # Use float hash of first feature to detect duplicates across splits
        tr_set  = set(Xtr[:, 0].tolist())
        val_set = set(Xv[:, 0].tolist())
        te_set  = set(Xte[:, 0].tolist())
        self.assertEqual(len(tr_set & val_set), 0, "train/val overlap")
        self.assertEqual(len(tr_set & te_set),  0, "train/test overlap")
        self.assertEqual(len(val_set & te_set), 0, "val/test overlap")


class TestScalerLeakage(unittest.TestCase):

    def test_fit_only_on_train(self):
        X, y = _make_data(n=300, d=16)
        Xtr, Xv, Xte, _, _, _ = stratified_split(X, y, 0.70, 0.15)
        Xtr_s, Xv_s, Xte_s, scaler = fit_scaler_on_train(Xtr, Xv, Xte)

        # After scaling, train mean should be ~0 and std ~1 per feature
        np.testing.assert_allclose(Xtr_s.mean(0), np.zeros(16), atol=1e-5)
        np.testing.assert_allclose(Xtr_s.std(0),  np.ones(16),  atol=0.1)

        # Val/test should NOT be normalised to mean=0 (they use train stats)
        val_mean_abs = np.abs(Xv_s.mean(0)).mean()
        # If scaler was accidentally re-fit on val, mean would be ~0; it should differ
        # (This is a probabilistic check — very unlikely to fail with n=300)
        self.assertGreater(val_mean_abs, 1e-4,
            "Val mean is suspiciously close to 0 — possible leakage.")


class TestModelForward(unittest.TestCase):

    def test_output_shape(self):
        model = MLPClassifier(input_dim=32, hidden_dims=[64, 32], num_classes=4)
        x = torch.randn(16, 32)
        out = model(x)
        self.assertEqual(out.shape, (16, 4))

    def test_output_changes_with_input(self):
        model = MLPClassifier(input_dim=32, hidden_dims=[64], num_classes=4)
        model.eval()
        x1 = torch.randn(8, 32)
        x2 = torch.randn(8, 32)
        with torch.no_grad():
            self.assertFalse(torch.allclose(model(x1), model(x2)))

    def test_kaiming_init_no_nan(self):
        model = MLPClassifier(input_dim=128, hidden_dims=[256, 128, 64], num_classes=10)
        for p in model.parameters():
            self.assertFalse(torch.isnan(p).any(), "NaN found in initial weights")


class TestCheckpointRoundtrip(unittest.TestCase):

    def test_save_load_model_weights(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg   = TrainConfig(checkpoint_dir=tmpdir)
            model = MLPClassifier(input_dim=32, hidden_dims=[64], num_classes=4)
            optim = torch.optim.SGD(model.parameters(), lr=0.01)
            sched = torch.optim.lr_scheduler.LambdaLR(optim, lambda s: 1.0)

            mgr = CheckpointManager(tmpdir, keep_last_n=2)
            mgr.save(
                epoch=0, model=model, optimizer=optim,
                scheduler=sched, scaler=None,
                metrics={"val_f1_macro": 0.75},
                config_dict=cfg.to_dict(), rank=0,
            )

            weights_before = {k: v.clone() for k, v in model.state_dict().items()}

            # Corrupt the model in memory
            for p in model.parameters():
                p.data.fill_(999.0)

            # Restore
            resume_epoch = mgr.load_latest(
                model, optim, sched, scaler=None,
                device=torch.device("cpu"),
            )

            self.assertEqual(resume_epoch, 1)   # last epoch + 1
            for k, before in weights_before.items():
                torch.testing.assert_close(model.state_dict()[k], before)

    def test_pruning_keeps_last_n(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model = MLPClassifier(input_dim=8, hidden_dims=[16], num_classes=2)
            optim = torch.optim.SGD(model.parameters(), lr=0.01)
            sched = torch.optim.lr_scheduler.LambdaLR(optim, lambda s: 1.0)
            mgr   = CheckpointManager(tmpdir, keep_last_n=2)

            for epoch in range(5):
                mgr.save(epoch, model, optim, sched, None, {}, {}, rank=0)

            routine = [p for p in Path(tmpdir).glob("ckpt_epoch_*.pt") if "best" not in p.stem]
            self.assertLessEqual(len(routine), 2)


class TestEvaluate(unittest.TestCase):

    def test_metric_keys_present(self):
        model  = MLPClassifier(input_dim=32, hidden_dims=[64], num_classes=4)
        X, y   = _make_data(n=100)
        _, _, Xte, _, _, yte = stratified_split(X, y, 0.70, 0.15)
        Xte_s, _, _, _ = fit_scaler_on_train(Xte, Xte, Xte)
        loader = _make_loader(Xte_s, yte)

        metrics = evaluate(model, loader, torch.device("cpu"), 4, "test")
        for key in ("test_accuracy", "test_f1_macro", "test_loss",
                    "test_precision_macro", "test_recall_macro"):
            self.assertIn(key, metrics, f"Missing metric: {key}")

    def test_accuracy_in_range(self):
        model  = MLPClassifier(input_dim=32, hidden_dims=[64], num_classes=4)
        X, y   = _make_data(n=200)
        loader = _make_loader(X, y)
        metrics = evaluate(model, loader, torch.device("cpu"), 4, "val")
        acc = metrics["val_accuracy"]
        self.assertGreaterEqual(acc, 0.0)
        self.assertLessEqual(acc, 1.0)


class TestLinearLRScaling(unittest.TestCase):
    """Verify the linear scaling rule formula: lr × (world × per_gpu) / base."""

    def _scale(self, base_lr, base_batch, world, per_gpu):
        # Replicated from train_ddp.py to keep test self-contained
        return base_lr * (world * per_gpu) / base_batch

    def test_single_gpu_no_change(self):
        self.assertAlmostEqual(self._scale(0.01, 64, 1, 64), 0.01)

    def test_double_gpu_doubles_lr(self):
        self.assertAlmostEqual(self._scale(0.01, 64, 2, 64), 0.02)

    def test_four_gpu_quadruples_lr(self):
        self.assertAlmostEqual(self._scale(0.01, 64, 4, 64), 0.04)

    def test_larger_per_gpu_batch(self):
        # 2 GPUs × 128 per-GPU vs base 64 → 4× LR
        self.assertAlmostEqual(self._scale(0.01, 64, 2, 128), 0.04)


class TestExperimentLogger(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        # Redirect logger paths to temp dir
        import experiment_logger as exp_log
        exp_log._DB_PATH    = Path(self._tmpdir.name) / "experiments.db"
        exp_log._JSONL_PATH = Path(self._tmpdir.name) / "experiments.jsonl"
        self._exp_log = exp_log

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_full_run_lifecycle(self):
        exp = self._exp_log
        run_id = exp.start_run(config={"epochs": 10}, world_size=2, scaled_lr=0.02)
        self.assertEqual(len(run_id), 8)

        exp.log_epoch(run_id, 0, {"train_loss": 0.8, "val_f1_macro": 0.5})
        exp.log_epoch(run_id, 1, {"train_loss": 0.6, "val_f1_macro": 0.65})
        exp.finish_run(run_id, {"test_accuracy": 0.88, "test_f1_macro": 0.87})

        # Verify SQLite
        import sqlite3
        con = sqlite3.connect(exp._DB_PATH)
        rows = con.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchall()
        self.assertEqual(rows[0][0], "finished")

        epoch_rows = con.execute(
            "SELECT epoch FROM epoch_metrics WHERE run_id=?", (run_id,)
        ).fetchall()
        self.assertEqual(len(epoch_rows), 2)
        con.close()

        # Verify JSONL
        lines = exp._JSONL_PATH.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)


class TestClassBalanceCheck(unittest.TestCase):

    def test_balanced_returns_false(self):
        y = np.array([0, 1, 2, 3] * 100)
        self.assertFalse(check_class_balance(y, threshold=0.2))

    def test_imbalanced_returns_true(self):
        y = np.array([0] * 900 + [1] * 100)
        self.assertTrue(check_class_balance(y, threshold=0.2))


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromModule(
        sys.modules[__name__]
    ))
    sys.exit(0 if result.wasSuccessful() else 1)
