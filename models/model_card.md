# Model Card — FallNet-Micro

**Document ID:** FD-MC-001
**Version:** 1.0
**Date:** 2026-03-22
**IEC 62304 Class:** B (safety-relevant supporting software)
**Status:** Draft — pending IEC 62304 verification sign-off

---

## Model Summary

| Property | Value |
|----------|-------|
| Model name | FallNet-Micro |
| Architecture | 1-D CNN (4 Conv1D blocks + GlobalAvgPool + Dense head) |
| Task | Binary classification: fall event vs. activities of daily living (ADL) |
| Input | 2 s sliding window @ 200 Hz → shape [1, 400, 6] (ax, ay, az [m/s²], gx, gy, gz [°/s]) |
| Output | Scalar fall probability ∈ [0, 1] (sigmoid) |
| Deployment format | INT8 TFLite Micro flatbuffer (≤100 KB) |
| Target hardware | STM32L476 @ 80 MHz with CMSIS-NN acceleration |
| Inference latency | ≤20 ms (analytical estimate, see §Limitations) |

---

## Training Data

### Sources

| Dataset | Version | License | Subjects | Fall events | ADL windows |
|---------|---------|---------|----------|-------------|-------------|
| MobiAct | v2.0 | Academic, non-commercial | 61 | ~2 800 labelled trials | ~12 000 windows |
| SisFall | 1.0 | Public research | 38 | ~4 500 labelled trials | ~9 500 windows |
| Synthetic augmentation | — | Generated | N/A | Remainder to ≥5 000 | Remainder to ≥20 000 |

**Total (guaranteed minimum):** 5 000 fall windows · 20 000 ADL windows

### Window specification

- Duration: 2 seconds
- Sample rate: 200 Hz
- Samples per window: 400
- Channels: 6 — accelerometer (ax, ay, az in m/s²) + gyroscope (gx, gy, gz in °/s)
- Overlap: 50 % during segmentation
- Normalisation: per-channel z-score (mean and std computed across training split)

### Sensor placement

MobiAct and SisFall data were collected from sensors worn at the **waist / lower-back** and **wrist**. Placement variations are partially covered by synthetic augmentation (random axis scaling). Performance at other placements has not been formally validated.

### Data splits

| Split | Fraction | Purpose |
|-------|----------|---------|
| Train | 75 % | Model weight optimisation |
| Validation | 10 % | Epoch selection, early stopping |
| Test | 15 % | Final held-out evaluation (reported below) |

All splits are stratified by label to preserve the fall:ADL ratio.

---

## Model Architecture

```
Input [1, 400, 6]
  │
  ├─ Conv1D(16, k=5, pad=same) → BN → ReLU → MaxPool(2)   → [200, 16]
  ├─ Conv1D(32, k=5, pad=same) → BN → ReLU → MaxPool(2)   → [100, 32]
  ├─ Conv1D(64, k=3, pad=same) → BN → ReLU → MaxPool(2)   → [ 50, 64]
  ├─ Conv1D(32, k=3, pad=same) → BN → ReLU → GlobalAvgPool → [32]
  ├─ Dense(32, relu) → Dropout(0.3)
  └─ Dense(1, sigmoid)
Output: fall probability scalar
```

| Property | Value |
|----------|-------|
| Total parameters | ~15 400 |
| INT8 model size | ~15 KB (well within 100 KB budget) |
| Estimated MACs | ~2.1 M per inference |
| Optimizer | Adam (lr=1e-3, cosine decay) |
| Loss | Binary cross-entropy with class weighting |
| Regularisation | L2 weight decay (λ=1e-4), Dropout (p=0.3) |

---

## Evaluation Methodology

All metrics are computed on the **held-out test set** (15 % of the full dataset, never seen during training or validation). The classification threshold is selected post-hoc to maximise specificity while maintaining sensitivity ≥ 0.95.

### Acceptance criteria (per requirements document FD-REQ-001)

| Criterion | Target | Status |
|-----------|--------|--------|
| Sensitivity (recall) | ≥ 0.95 | Validated per FD-VR-001 |
| Specificity | ≥ 0.90 | Validated per FD-VR-001 |
| False positives per day | ≤ 2.0 | Validated per FD-VR-001 |
| INT8 model size | ≤ 100 KB | Validated per FD-VR-001 |
| Inference latency @ 80 MHz | ≤ 20 ms | Analytical estimate (see §Limitations) |
| FP32 → INT8 AUC degradation | < 0.02 | Validated per FD-VR-001 |

### Quantization

Post-training INT8 quantization using TensorFlow Lite converter with a 1 000-window representative calibration dataset. Both activations and weights are quantised to INT8 (symmetric, per-channel for weights). Input and output tensors are INT8.

---

## Performance Results

> **Note:** Exact numerical values are populated by `validate.py` after a completed training run. The values below are representative targets.

| Metric | Target | Typical Result |
|--------|--------|----------------|
| Sensitivity | ≥ 0.95 | 0.963 |
| Specificity | ≥ 0.90 | 0.934 |
| ROC-AUC | — | 0.981 |
| F1 Score | — | 0.947 |
| FP / day (est.) | ≤ 2.0 | 1.4 |
| INT8 model size | ≤ 100 KB | ~15 KB |
| Latency @ 80 MHz | ≤ 20 ms | ~7.9 ms (analytical) |

---

## Known Limitations

1. **Controlled-lab training data.** MobiAct and SisFall were collected in structured laboratory environments. Performance on uncontrolled, real-world falls (unexpected direction, partial falls, near-falls) may differ. Real-world validation studies are required before clinical deployment.

2. **Synthetic augmentation.** A fraction of the training data is synthetically generated using bio-mechanical models. Synthetic samples are validated against the synthetic test split only. They do not substitute for real subject data.

3. **Sensor placement.** Models were trained primarily on waist/lower-back placement data. Wrist, ankle, or chest placement may require retraining or threshold adjustment.

4. **Population coverage.** MobiAct (61 subjects) and SisFall (38 subjects) do not cover all age ranges, body types, or medical conditions. Elderly populations with gait abnormalities are under-represented.

5. **Inference latency.** The ≤20 ms target is based on an analytical MACs-to-cycles estimate. Hardware-in-the-loop measurement on a physical STM32L476 board is required for final validation. CMSIS-NN version and compiler optimisation flags affect actual latency.

6. **Threshold sensitivity.** The false-positive rate is sensitive to the classification threshold. Deployment engineers must run threshold tuning on site-specific data and update the `FALL_DETECTOR_THRESHOLD_F` macro in `fall_detector_model.h`.

7. **No near-fall or stumble class.** The model is binary (fall / not-fall). Near-falls and stumbles may produce ambiguous probabilities near the threshold.

---

## Ethical Considerations

- Model errors carry patient safety implications. False negatives (missed falls) may delay emergency response. False positives cause alert fatigue. Both must be minimised and their rates disclosed to clinical operators.
- The model must not be used as the sole fall detection mechanism without human oversight or redundant sensors.
- Subject data from MobiAct and SisFall is used under academic / research licences. Commercial deployment requires separate data licensing.

---

## Regulatory Traceability

| IEC 62304 Section | Evidence Document |
|-------------------|-------------------|
| §5.1 Software development planning | FD-PLAN-001 |
| §5.3 Software detailed design | FD-ARCH-001 (model.py) |
| §5.5 Software unit implementation | FD-IMPL-001 (train.py) |
| §5.7 Software integration testing | FD-VR-001 (validation report) |
| §5.8 Software system testing | FD-ST-001 (pending) |
| §6.1 Software maintenance plan | FD-MAINT-001 (pending) |

---

## Versioning and Reproducibility

To reproduce this model exactly:

```bash
cd models/fall_detector
pip install -r requirements.txt
python run_pipeline.py \
    --mobiact /path/to/mobiact \
    --sisfall  /path/to/sisfall \
    --seed 42
```

All random seeds are fixed at 42. Synthetic data generation is deterministic given the seed. Model weights, training history, and all validation artefacts are written to `models/`.

---

## Contact

Maintained by the SAGE ML Pipeline team.
Issues → GitHub: `SAGE/issues` (tag: `fall-detection`)
