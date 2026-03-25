"""
Fall Detection CNN-1D Model Architecture
=========================================
Lightweight 1-D CNN designed for:
  - Input:  400 samples × 6 channels (2 s @ 200 Hz)
  - Target: STM32L476 @ 80 MHz with CMSIS-NN / TFLite Micro
  - INT8 quantized size ≤ 100 KB
  - Inference latency ≤ 20 ms on Cortex-M4

Architecture (CNN-1D "FallNet-Micro"):
  Layer 1: Conv1D(16, k=5, s=1, pad=same) → BN → ReLU → MaxPool(2)   → [200, 16]
  Layer 2: Conv1D(32, k=5, s=1, pad=same) → BN → ReLU → MaxPool(2)   → [100, 32]
  Layer 3: Conv1D(64, k=3, s=1, pad=same) → BN → ReLU → MaxPool(2)   → [ 50, 64]
  Layer 4: Conv1D(32, k=3, s=1, pad=same) → BN → ReLU → GlobalAvgPool → [32]
  Head:    Dense(32, relu) → Dropout(0.3) → Dense(1, sigmoid)

Parameter count: ~15 400  →  ~15.4 KB INT8 (well within 100 KB budget)
MACs per inference: ~2.1 M  → well within 20 ms at 80 MHz with CMSIS-NN

IEC 62304 Design Record: FD-ARCH-001 Rev 1.0
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Input dimensions ─────────────────────────────────────────────────────────
WINDOW_SAMPLES = 400
CHANNELS       = 6


def build_fallnet_micro(
    input_shape: Tuple[int, int] = (WINDOW_SAMPLES, CHANNELS),
    dropout_rate: float = 0.30,
    l2_reg: float = 1e-4,
) -> "tf.keras.Model":
    """
    Build the FallNet-Micro CNN-1D model.

    Args:
        input_shape:  (time_steps, channels) — default (400, 6)
        dropout_rate: Dropout probability after Dense(32) head
        l2_reg:       L2 weight decay on convolutional kernels

    Returns:
        Compiled Keras model (binary cross-entropy, Adam lr=1e-3)
    """
    import tensorflow as tf
    from tensorflow.keras import layers, regularizers

    reg = regularizers.l2(l2_reg)

    inp = tf.keras.Input(shape=input_shape, name="imu_window")

    # ── Block 1 ──────────────────────────────────────────────────────────
    x = layers.Conv1D(16, kernel_size=5, padding="same",
                      kernel_regularizer=reg, use_bias=False,
                      name="conv1")(inp)
    x = layers.BatchNormalization(name="bn1")(x)
    x = layers.ReLU(name="relu1")(x)
    x = layers.MaxPooling1D(pool_size=2, name="pool1")(x)

    # ── Block 2 ──────────────────────────────────────────────────────────
    x = layers.Conv1D(32, kernel_size=5, padding="same",
                      kernel_regularizer=reg, use_bias=False,
                      name="conv2")(x)
    x = layers.BatchNormalization(name="bn2")(x)
    x = layers.ReLU(name="relu2")(x)
    x = layers.MaxPooling1D(pool_size=2, name="pool2")(x)

    # ── Block 3 ──────────────────────────────────────────────────────────
    x = layers.Conv1D(64, kernel_size=3, padding="same",
                      kernel_regularizer=reg, use_bias=False,
                      name="conv3")(x)
    x = layers.BatchNormalization(name="bn3")(x)
    x = layers.ReLU(name="relu3")(x)
    x = layers.MaxPooling1D(pool_size=2, name="pool3")(x)

    # ── Block 4 ──────────────────────────────────────────────────────────
    x = layers.Conv1D(32, kernel_size=3, padding="same",
                      kernel_regularizer=reg, use_bias=False,
                      name="conv4")(x)
    x = layers.BatchNormalization(name="bn4")(x)
    x = layers.ReLU(name="relu4")(x)
    x = layers.GlobalAveragePooling1D(name="gap")(x)

    # ── Classification head ───────────────────────────────────────────────
    x = layers.Dense(32, activation="relu", kernel_regularizer=reg,
                     name="dense1")(x)
    x = layers.Dropout(dropout_rate, name="dropout")(x)
    out = layers.Dense(1, activation="sigmoid", name="output")(x)

    model = tf.keras.Model(inputs=inp, outputs=out, name="FallNet_Micro")

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Recall(name="sensitivity"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.AUC(name="auc"),
        ],
    )

    return model


def model_summary_str(model: "tf.keras.Model") -> str:
    """Return model summary as a string for logging / reports."""
    lines = []
    model.summary(print_fn=lambda s: lines.append(s))
    return "\n".join(lines)


def count_params(model: "tf.keras.Model") -> dict:
    """Return parameter counts for the model card."""
    total     = model.count_params()
    trainable = sum(np.prod(v.shape) for v in model.trainable_variables)
    return {
        "total_params":     int(total),
        "trainable_params": int(trainable),
        "int8_size_kb":     round(total / 1024, 1),
    }


def estimate_macs(model: "tf.keras.Model") -> int:
    """
    Estimate multiply-accumulate operations for a Conv1D model.
    MACs(conv) = L_out × C_in × C_out × kernel
    """
    macs = 0
    for layer in model.layers:
        cfg = layer.get_config()
        if "Conv1D" in type(layer).__name__:
            # Approximate: ignores stride details
            try:
                filters   = cfg["filters"]
                kernel    = cfg["kernel_size"][0] if isinstance(
                    cfg["kernel_size"], (list, tuple)) else cfg["kernel_size"]
                in_ch     = layer.input_shape[-1]
                out_len   = layer.output_shape[-2]
                macs     += out_len * in_ch * filters * kernel
            except Exception:
                pass
    return macs
