# Software Unit Test Records
**Document ID:** UTR-005
**Version:** 1.0.0
**Status:** PASSED — APPROVED
**Date:** 2026-03-27
**Safety Class:** IEC 62304 Class B
**Author:** Development Team / QA
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-03-01 | Dev/QA | Initial test execution |
| 1.0 | 2026-03-27 | Dev/QA | All anomalies resolved; approved |

---

## 1. Test Environment
*(IEC 62304 §5.5.4)*

| Parameter | Value |
|-----------|-------|
| Test executor | pytest 8.1.1 |
| Python version | 3.11.9 |
| OS | Ubuntu 22.04 LTS (Docker container) |
| Hardware emulation | ECG waveform simulator (synthetic + PhysioNet MIT-BIH dataset) |
| Execution date | 2026-03-20 |
| CI pipeline run | GitHub Actions run #4891 |
| Code coverage tool | coverage.py 7.4.3 |

---

## 2. Coverage Summary
*(IEC 62304 §5.5.4)*

| Module | Statements | Covered | Coverage % | Target | Status |
|--------|-----------|---------|-----------|--------|--------|
| `src/spm/filters.py` | 87 | 84 | **96.6%** | 90% | PASS |
| `src/spm/signal_quality.py` | 52 | 50 | **96.2%** | 90% | PASS |
| `src/spm/ring_buffer.py` | 38 | 37 | **97.4%** | 90% | PASS |
| `src/ade/feature_extraction.py` | 201 | 192 | **95.5%** | 90% | PASS |
| `src/ade/classifier.py` | 94 | 90 | **95.7%** | 90% | PASS |
| `src/ade/rule_engine.py` | 118 | 116 | **98.3%** | 90% | PASS |
| `src/ade/confidence.py` | 65 | 63 | **96.9%** | 90% | PASS |
| `src/alm/generator.py` | 78 | 76 | **97.4%** | 90% | PASS |
| `src/alm/dedup.py` | 44 | 43 | **97.7%** | 90% | PASS |
| `src/alm/queue.py` | 61 | 59 | **96.7%** | 90% | PASS |
| **TOTAL (Class B)** | **838** | **810** | **96.7%** | 90% | **PASS** |

---

## 3. Unit Test Results

### 3.1 SPM-FLT Filter Chain Tests

| Test ID | Test Name | Requirement | Input | Expected | Result | Defects |
|---------|-----------|-------------|-------|----------|--------|---------|
| UT-SPM-001 | test_bandpass_removes_baseline_wander | SPM-002 | Synthetic ECG + 0.1 Hz drift | Drift amplitude < 0.05 mV | **PASS** | — |
| UT-SPM-002 | test_notch_50hz_attenuation | SPM-004 | 50 Hz sine at 1.0 mV | Output < 0.05 mV | **PASS** | — |
| UT-SPM-003 | test_notch_60hz_attenuation | SPM-004 | 60 Hz sine at 1.0 mV | Output < 0.05 mV | **PASS** | — |
| UT-SPM-004 | test_nan_input_replaced | SDD §2.1 | Frame with NaN values | NaN replaced with 0.0 | **PASS** | — |
| UT-SPM-005 | test_clipping_to_physiological_range | SDD §2.1 | Input ±10 mV | Clipped to ±5 mV | **PASS** | — |
| UT-SPM-006 | test_filter_state_persists_across_frames | SDD §2.1 | 3 consecutive frames | Continuous phase response | **PASS** | — |
| UT-SPM-007 | test_invalid_sample_rate_raises | SDD §2.1 | sample_rate=50 | ValueError raised | **PASS** | — |
| UT-SPM-008 | test_reset_clears_filter_state | SDD §2.1 | Apply, reset, apply | Independent responses | **PASS** | — |

### 3.2 SPM-SQI Signal Quality Tests

| Test ID | Test Name | Requirement | Input | Expected | Result | Defects |
|---------|-----------|-------------|-------|----------|--------|---------|
| UT-SQI-001 | test_perfect_signal_sqi_above_threshold | ADE-006 | Clean synthetic ECG | SQI ≥ 0.8 | **PASS** | — |
| UT-SQI-002 | test_flatline_produces_low_sqi | ADE-006 | Constant 0.0 mV | SQI = 0.0 | **PASS** | — |
| UT-SQI-003 | test_saturated_signal_low_sqi | ADE-006 | ±5 mV clipped | SQI < 0.3 | **PASS** | — |
| UT-SQI-004 | test_noisy_signal_moderate_sqi | ADE-006 | ECG + Gaussian noise SNR=10 dB | 0.4 ≤ SQI ≤ 0.7 | **PASS** | — |
| UT-SQI-005 | test_is_acceptable_threshold | ADE-006 | SQI = 0.39 | is_acceptable() = False | **PASS** | — |
| UT-SQI-006 | test_is_acceptable_above_threshold | ADE-006 | SQI = 0.41 | is_acceptable() = True | **PASS** | — |

### 3.3 ADE-RULE Rule Engine Tests

| Test ID | Test Name | Requirement | Input | Expected | Result | Defects |
|---------|-----------|-------------|-------|----------|--------|---------|
| UT-RULE-001 | test_vf_detected_amplitude_criterion | ADE-003 | HR=280, amplitude=0.08 mV, ≥3 beats | VF detected | **PASS** | — |
| UT-RULE-002 | test_vf_not_triggered_normal | ADE-003 | Sinus rhythm features | No rule fires | **PASS** | — |
| UT-RULE-003 | test_vt_detected | ADE-002 | HR=130, QRS=130 ms, ≥3 beats | VT detected | **PASS** | — |
| UT-RULE-004 | test_pause_detected | ADE-004 | RR gap = 3.2 s | PAUSE detected | **PASS** | — |
| UT-RULE-005 | test_pause_not_triggered_normal_rr | ADE-004 | Max RR = 1.2 s | No rule fires | **PASS** | — |
| UT-RULE-006 | test_avb1_pr_prolonged | ADE-004 | PR = 220 ms × 3 beats | AVB1 detected | **PASS** | — |
| UT-RULE-007 | test_af_irregularity | ADE-001 | Irregularity=0.22, no P-waves | AF detected | **PASS** | — |
| UT-RULE-008 | test_rule_priority_vf_over_vt | ADE-003 | Both VF and VT criteria met | VF returned (priority 1) | **PASS** | — |

### 3.4 ADE-CLF Classifier Tests

| Test ID | Test Name | Requirement | Input | Expected | Result | Defects |
|---------|-----------|-------------|-------|----------|--------|---------|
| UT-CLF-001 | test_model_checksum_validation | SDD §3.2 | Corrupted model file | RuntimeError raised | **PASS** | — |
| UT-CLF-002 | test_sinus_classification | ADE-001 | Normal sinus features (MIT-BIH record 100) | label=SINUS, conf≥0.90 | **PASS** | — |
| UT-CLF-003 | test_af_classification | ADE-001 | AF features (MIT-BIH record 201) | label=AF, conf≥0.85 | **PASS** | — |
| UT-CLF-004 | test_low_confidence_returns_unknown | ADE-005 | Ambiguous features | label=UNKNOWN | **PASS** | — |
| UT-CLF-005 | test_confidence_clamped_to_range | ADE-005 | Model raw output > 1.0 | confidence ≤ 1.0 | **PASS** | — |
| UT-CLF-006 | test_inference_time_within_budget | ADE-007 | 100 consecutive epochs | All < 200 ms | **PASS** | — |

### 3.5 ALM-GEN Alert Generator Tests

| Test ID | Test Name | Requirement | Input | Expected | Result | Defects |
|---------|-----------|-------------|-------|----------|--------|---------|
| UT-ALM-001 | test_vf_generates_high_priority | ALM-001 | label=VF | priority=HIGH | **PASS** | — |
| UT-ALM-002 | test_vt_high_confidence_high_priority | ALM-001 | label=VT, conf=0.8 | priority=HIGH | **PASS** | — |
| UT-ALM-003 | test_vt_low_confidence_medium | ALM-002 | label=VT, conf=0.6 | priority=MEDIUM | **PASS** | — |
| UT-ALM-004 | test_alert_has_uuid | SDD §4.1 | Any valid event | id is valid UUID v4 | **PASS** | — |
| UT-ALM-005 | test_alert_links_episode_id | SDD §4.1 | Event with episode | episode_id set correctly | **PASS** | — |
| UT-ALM-006 | test_avb1_generates_low_priority | ALM-002 | label=AVB1 | priority=LOW | **PASS** | — |

### 3.6 ALM-DEDUP Deduplication Tests

| Test ID | Test Name | Requirement | Input | Expected | Result | Defects |
|---------|-----------|-------------|-------|----------|--------|---------|
| UT-DDP-001 | test_same_type_within_5min_suppressed | ALM-003 | Two AF alerts, 3 min apart | Second suppressed | **PASS** | — |
| UT-DDP-002 | test_same_type_after_5min_passes | ALM-003 | Two AF alerts, 6 min apart | Second passes | **PASS** | — |
| UT-DDP-003 | test_different_type_not_suppressed | ALM-003 | AF then VT within 5 min | VT passes | **PASS** | — |

---

## 4. Anomalies Found During Unit Testing

| Defect ID | Test | Description | Severity | Status | Fix Reference |
|-----------|------|-------------|----------|--------|---------------|
| PR-001 | UT-CLF-006 | Inference time exceeded 200 ms on 2/100 epochs (PyTorch cold-start) | Major | RESOLVED | PR-001 fix: model pre-warmed at init |
| PR-002 | UT-SPM-004 | NaN replacement logged incorrectly (wrong event type string) | Minor | RESOLVED | PR-002 fix: log field corrected |

*(Full defect details in PRP-008)*

---

## 5. Test Sign-off

All 50 unit tests pass. Code coverage 96.7% across Class B modules (target: 90%).

**QA Engineer Sign-off:** J. Hargreaves — 2026-03-27 — _______________

---

*End of UTR-005*
