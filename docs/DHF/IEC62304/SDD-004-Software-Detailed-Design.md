# Software Detailed Design
**Document ID:** SDD-004
**Version:** 1.0.0
**Status:** APPROVED
**Date:** 2026-03-27
**Safety Class:** IEC 62304 Class B
**Author:** Software Development Team
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-02-15 | Dev Team | Initial draft |
| 0.2 | 2026-03-10 | Dev Team | ADE-RULE hardening |
| 1.0 | 2026-03-27 | Dev Team | Approved for baseline |

---

## 1. Purpose and Scope
*(IEC 62304 §5.4.1)*

This Software Detailed Design (SDD) specifies the internal design of each software unit identified in SAD-003, including interfaces, algorithms, data structures, error handling, and implementation constraints. This document is the authoritative source for code review verification.

---

## 2. SPM — Signal Processing Module Units

### 2.1 SPM-FLT: Filter Chain
*(Implements: SPM-001, SPM-002, SPM-004)*

**Module:** `src/spm/filters.py`

**Class:** `ECGFilterChain`

```
ECGFilterChain
├── __init__(sample_rate: int = 250)
│     Initializes Butterworth bandpass (0.5–40 Hz, order=4)
│     Initializes notch filter (50 Hz and 60 Hz, Q=30)
│     Pre-computes filter coefficients (SciPy butter/iirnotch)
│
├── apply(raw_frame: np.ndarray[float32]) → np.ndarray[float32]
│     1. Apply high-pass (0.5 Hz) — removes baseline wander
│     2. Apply notch (50/60 Hz) — removes power-line noise
│     3. Apply low-pass (40 Hz) — removes high-freq artifacts
│     4. Clip to ±5 mV physiological range
│     Returns: filtered frame, same shape as input
│
└── reset()
      Resets filter state (called on lead reconnect)
```

**Error handling:**
- `ValueError` if `sample_rate` < 100 or > 1000 → raise, caller logs and uses default
- NaN/Inf in input → replaced with 0.0 and flagged in SQI (SPM-SQI)

**Constraints:**
- Filter state persisted across frames (causal filter, no look-ahead)
- Thread-safe: one instance per acquisition thread

---

### 2.2 SPM-SQI: Signal Quality Index
*(Implements: ADE-006)*

**Module:** `src/spm/signal_quality.py`

**Class:** `SignalQualityIndex`

```
SignalQualityIndex
├── compute(frame: np.ndarray) → float  [0.0–1.0]
│     SQI = weighted average of:
│       - flatline_score: std(frame) > threshold (weight 0.4)
│       - clipping_score: fraction of samples NOT at ±saturation (weight 0.3)
│       - noise_score: SNR estimate via periodogram (weight 0.3)
│     Returns 0.0 for completely invalid signal
│
└── is_acceptable(frame) → bool
      Returns SQI >= 0.4 (threshold per ADE-006)
```

---

### 2.3 SPM-BUF: Pre-Event Ring Buffer
*(Implements: SPM-005)*

**Module:** `src/spm/ring_buffer.py`

**Class:** `PreEventBuffer`

```
PreEventBuffer(capacity_seconds=30, sample_rate=250)
├── push(frame: np.ndarray) → None
│     Appends frame to circular buffer; overwrites oldest on full
│
├── snapshot() → np.ndarray
│     Returns copy of last 30 seconds of ECG data
│
└── clear() → None
```

**Implementation note:** uses `collections.deque(maxlen=7500)` (30 s × 250 Hz); thread-safe via `threading.Lock`

---

## 3. ADE — Arrhythmia Detection Engine Units

### 3.1 ADE-FEAT: Feature Extraction
*(Implements: ADE-001 through ADE-004)*

**Module:** `src/ade/feature_extraction.py`

**Class:** `FeatureExtractor`

Extracts 47 features per 10-second epoch:

| Feature Group | Count | Description |
|--------------|-------|-------------|
| R-R intervals | 12 | Mean, SD, RMSSD, pNN50, min, max, range, skewness, kurtosis, entropy, triangular index, TINN |
| Morphology | 10 | P-wave amplitude, QRS duration, T-wave amplitude, QT interval, QTc (Bazett), PR interval, QRS axis, ST elevation/depression per lead |
| Frequency domain | 8 | VLF, LF, HF power, LF/HF ratio, peak frequencies ×2, spectral entropy ×2 |
| Rhythm regularity | 7 | AF burden score, irregularity index, pacing artifact detection flag, pause duration, longest pause, beat-to-beat variance |
| Signal metadata | 10 | SQI per lead ×4, lead-off flags ×4, epoch timestamp, battery level |

```
FeatureExtractor
├── extract(filtered_epoch: np.ndarray, sqi: float) → np.ndarray[float32, shape=(47,)]
│     Returns feature vector; NaN if SQI < 0.4
│
└── feature_names() → list[str]
      Returns ordered list of 47 feature names (for interpretability logging)
```

---

### 3.2 ADE-CLF: ML Classifier
*(Implements: ADE-001 through ADE-005)*

**Module:** `src/ade/classifier.py`

**Class:** `ArrhythmiaClassifier`

- Model: 1D-CNN + LSTM hybrid, PyTorch 2.2
- Input: 47-feature vector + raw 10-s epoch (dual input)
- Output: softmax probabilities over 8 classes
- Model file: `model_cache/arrhythmia_v1.0.pt` (SHA-256: a3f7...documented in SRR-009)

```
ArrhythmiaClassifier
├── __init__(model_path: str, device: str = "cpu")
│     Loads PyTorch model; validates SHA-256 checksum before load
│     Raises RuntimeError if checksum mismatch
│
├── predict(features: np.ndarray, epoch: np.ndarray) → ClassificationResult
│     Returns: {label: str, confidence: float, class_probabilities: dict}
│     Clips confidence to [0.0, 1.0]
│     Returns label="UNKNOWN" if top probability < 0.5
│
└── ClassificationResult: dataclass
      label: str  (one of: SINUS, AF, SVT, VT, VF, AVB1, AVB2, AVB3, PAUSE, UNKNOWN)
      confidence: float
      class_probabilities: dict[str, float]
      inference_time_ms: float
```

**Safety constraint:** ADE-RULE always runs independently; ADE-CLF result is merged post-hoc (ADE-CONF).

---

### 3.3 ADE-RULE: Rule-Based Safety Net
*(Implements: ADE-003 — VF within 5 seconds; ADE-004 — pause and AV block)*

**Module:** `src/ade/rule_engine.py`

**Class:** `RuleEngine`

Rules evaluated in strict priority order:

1. **VF rule:** if ≥ 3 consecutive beats with amplitude < 0.1 mV AND HR > 250 bpm → `VF`
2. **VT rule:** if ≥ 3 beats with QRS duration > 120 ms AND HR > 120 bpm → `VT`
3. **Pause rule:** if R-R gap > 2.5 seconds → `PAUSE`
4. **AV block rule:** if PR interval > 200 ms on ≥ 3 consecutive beats → `AVB1`
5. **AF rule:** if irregularity index > 0.15 AND no P-waves detected → `AF`

```
RuleEngine
├── evaluate(epoch_features: dict) → RuleResult | None
│     Returns first matching rule result or None if no rule fires
│
└── RuleResult: dataclass
      label: str
      rule_id: str
      triggered_values: dict
```

**Override policy (ADE-CONF):** if ADE-RULE fires, its label overrides ADE-CLF for safety-critical classes (VF, PAUSE); for others, confidence-weighted merge is used.

---

### 3.4 ADE-CONF: Confidence Gating
*(Implements: ADE-005, ADE-006)*

**Module:** `src/ade/confidence.py`

```
ConfidenceGate
├── merge(clf_result: ClassificationResult, rule_result: RuleResult | None,
│         sqi: float) → FinalClassification
│
│     Logic:
│       if sqi < 0.4: return UNCLASSIFIED (no alert)
│       if rule_result and rule_result.label in {VF, PAUSE}: return rule_result (safety override)
│       if rule_result: confidence = max(clf_result.confidence, 0.85) and use rule label
│       else: use clf_result as-is
│
└── FinalClassification: dataclass
      label: str
      confidence: float
      source: Literal["clf", "rule", "merged", "unclassified"]
      sqi: float
```

---

## 4. ALM — Alert Manager Units

### 4.1 ALM-GEN: Alert Generator
*(Implements: ALM-001, ALM-002)*

**Module:** `src/alm/generator.py`

**Priority mapping:**

| Classification | Confidence | Priority | SLA |
|---------------|-----------|----------|-----|
| VF | any | HIGH | 5 s |
| VT | ≥ 0.7 | HIGH | 5 s |
| VT | < 0.7 | MEDIUM | 30 s |
| AF | ≥ 0.8 | MEDIUM | 30 s |
| PAUSE | any | HIGH | 5 s |
| AVB3 | any | HIGH | 5 s |
| AVB2 | ≥ 0.8 | MEDIUM | 30 s |
| AVB1 | any | LOW | 300 s |
| SVT | ≥ 0.75 | MEDIUM | 30 s |

```python
@dataclass
class Alert:
    id: str           # UUID v4
    type: str         # arrhythmia label
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    confidence: float
    episode_id: str   # links to SPM-BUF snapshot
    patient_id: str   # de-identified
    generated_at: datetime
    source: str       # clf | rule | merged
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
```

---

### 4.2 ALM-DEDUP: Duplicate Suppression
*(Implements: ALM-003)*

```
DedupFilter
├── should_suppress(alert: Alert) → bool
│     Checks: same type within 5-minute sliding window AND previous alert not resolved
│     Returns True (suppress) if duplicate; False (pass through) otherwise
│
└── _window: deque of (type, generated_at) with 5-min TTL cleanup on each call
```

---

## 5. CGW — Communication Gateway Units

### 5.1 CGW-DEID: De-identification
*(Implements: CGW-005, HIPAA Safe Harbor)*

Safe Harbor method applied per 45 CFR §164.514(b):
- Patient name → removed
- DOB → year only (if age < 90)
- Geographic data → state only
- All direct identifiers → pseudonymous `patient_token` (HMAC-SHA256, rotating daily key)
- Device serial → pseudonymous `device_token`

---

## 6. Error Handling Strategy
*(IEC 62304 §5.5.3)*

| Error Class | Handling Strategy |
|------------|-----------------|
| Sensor/hardware fault | Log + continue with degraded state; alert "SIGNAL_LOST" |
| Model inference failure | Fall back to ADE-RULE exclusively; log anomaly PRP-008 |
| Database write failure | In-memory queue with retry; alert if > 60 s backlog |
| Network failure | Local queue with exponential backoff; maximum 24-h retention |
| Authentication failure | Lock device after 5 attempts; require PIN reset |
| Unexpected exception (Class B) | Watchdog catches; restart module; log full traceback to audit_log.db |

---

*End of SDD-004*
