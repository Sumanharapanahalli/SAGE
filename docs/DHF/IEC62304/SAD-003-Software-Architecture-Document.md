# Software Architecture Document
**Document ID:** SAD-003
**Version:** 1.0.0
**Status:** APPROVED
**Date:** 2026-03-27
**Safety Class:** IEC 62304 Class B
**Author:** Software Architect
**Reviewed by:** Quality Engineer — J. Hargreaves
**Approved by:** Regulatory Affairs — M. Chen

---

## Document Control

| Version | Date | Author | Change Description |
|---------|------|--------|--------------------|
| 0.1 | 2026-02-01 | Architect | Initial draft |
| 0.2 | 2026-03-05 | Architect | Security architecture section added |
| 1.0 | 2026-03-27 | Architect | Approved for baseline |

---

## 1. Purpose and Scope
*(IEC 62304 §5.3.1)*

This Software Architecture Document (SAD) describes the decomposition of SAGE-MDS into software items, their interfaces, dependencies, and the rationale for architectural decisions. It serves as the primary traceability bridge between requirements (SRS-002) and detailed design (SDD-004).

---

## 2. Architectural Overview
*(IEC 62304 §5.3.2)*

SAGE-MDS follows a **layered pipeline architecture** with explicit isolation boundaries between safety-critical and non-safety-critical software items.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAGE-MDS v1.0                                  │
│  ┌────────────────────┐   ┌───────────────────────────────────┐  │
│  │  SAFETY-CRITICAL   │   │      NON-SAFETY-CRITICAL          │  │
│  │  (Class B)         │   │      (Class A)                    │  │
│  │                    │   │                                   │  │
│  │  ┌──────────────┐  │   │  ┌──────────────┐  ┌──────────┐  │  │
│  │  │ SPM          │  │   │  │ UI Layer     │  │ CGW      │  │  │
│  │  │ Signal       │  │   │  │ (React/TS)   │  │ Gateway  │  │  │
│  │  │ Processing   │  │   │  └──────┬───────┘  └────┬─────┘  │  │
│  │  └──────┬───────┘  │   │         │               │        │  │
│  │         │          │   └─────────│───────────────│────────┘  │
│  │  ┌──────▼───────┐  │             │               │           │
│  │  │ ADE          │──┼─────────────┘               │           │
│  │  │ Arrhythmia   │  │                             │           │
│  │  │ Detection    │  │                             │           │
│  │  └──────┬───────┘  │                             │           │
│  │         │          │                             │           │
│  │  ┌──────▼───────┐  │                             │           │
│  │  │ ALM          │──┼─────────────────────────────┘           │
│  │  │ Alert        │  │                                          │
│  │  │ Manager      │  │                                          │
│  │  └──────────────┘  │                                          │
│  └────────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Software Items Decomposition
*(IEC 62304 §5.3.2)*

### 3.1 Signal Processing Module (SPM) — Class B

| Software Unit | Responsibility | Language | Module Path |
|---------------|---------------|----------|-------------|
| SPM-SMP | ADC sampling interface, SPI driver wrapper | C | `src/hardware/spi_ecg.c` |
| SPM-FLT | Bandpass, notch, and baseline-wander filters | Python | `src/spm/filters.py` |
| SPM-SQI | Signal quality index computation | Python | `src/spm/signal_quality.py` |
| SPM-BUF | Pre-event ring buffer (30 s) | Python | `src/spm/ring_buffer.py` |
| SPM-LEAD | Lead-off detection | C | `src/hardware/lead_detect.c` |

### 3.2 Arrhythmia Detection Engine (ADE) — Class B

| Software Unit | Responsibility | Language | Module Path |
|---------------|---------------|----------|-------------|
| ADE-FEAT | Feature extraction (R-R intervals, morphology) | Python | `src/ade/feature_extraction.py` |
| ADE-CLF | ML classifier (PyTorch model inference) | Python | `src/ade/classifier.py` |
| ADE-RULE | Rule-based VF/pause detector (safety net) | Python | `src/ade/rule_engine.py` |
| ADE-CONF | Confidence scoring and SQI gating | Python | `src/ade/confidence.py` |
| ADE-HIST | Episode history tracker | Python | `src/ade/history.py` |

### 3.3 Alert Manager (ALM) — Class B

| Software Unit | Responsibility | Language | Module Path |
|---------------|---------------|----------|-------------|
| ALM-GEN | Alert generation and priority assignment | Python | `src/alm/generator.py` |
| ALM-DEDUP | Duplicate suppression logic | Python | `src/alm/dedup.py` |
| ALM-QUEUE | Persistent alert queue (SQLite-backed) | Python | `src/alm/queue.py` |
| ALM-ESC | Escalation timer and secondary contact routing | Python | `src/alm/escalation.py` |
| ALM-LOG | Alert audit logger | Python | `src/alm/audit.py` |

### 3.4 Communication Gateway (CGW) — Class A

| Software Unit | Responsibility | Language | Module Path |
|---------------|---------------|----------|-------------|
| CGW-TLS | mTLS session management | Python | `src/cgw/tls_client.py` |
| CGW-REST | FHIR REST client (FastAPI-based) | Python | `src/cgw/rest_client.py` |
| CGW-DEID | De-identification processor | Python | `src/cgw/deidentify.py` |
| CGW-RETRY | Offline queue and retry logic | Python | `src/cgw/retry_queue.py` |

### 3.5 User Interface Layer (UI) — Class A

| Software Unit | Responsibility | Language | Module Path |
|---------------|---------------|----------|-------------|
| UI-ECG | Real-time ECG waveform renderer | TypeScript | `web/src/components/ECGDisplay.tsx` |
| UI-ALERT | Alert banner and acknowledgement flow | TypeScript | `web/src/components/AlertBanner.tsx` |
| UI-AUTH | PIN-based authentication | TypeScript | `web/src/components/PINAuth.tsx` |
| UI-RHY | Rhythm classification display | TypeScript | `web/src/components/RhythmPanel.tsx` |

---

## 4. Data Architecture
*(IEC 62304 §5.3.4)*

### 4.1 Data Flows

```
ECG Hardware → [SPI] → SPM-SMP → [numpy array, 250 Hz frames]
→ SPM-FLT → SPM-SQI → [filtered frame + SQI score]
→ ADE-FEAT → [feature vector: 47 features]
→ ADE-CLF → [classification: label + confidence]
→ ADE-RULE → [rule override flag if VF/pause]
→ ALM-GEN → [Alert object: {id, type, priority, timestamp, episode_id, confidence}]
→ ALM-DEDUP → ALM-QUEUE → [persisted + routed to UI and CGW]
```

### 4.2 Data Stores

| Store | Type | Content | Retention | Backup |
|-------|------|---------|-----------|--------|
| alert_queue.db | SQLite WAL | Pending/sent alerts | 30 days | Cloud sync |
| episode_store/ | File system | Raw ECG episodes | 7 days | Cloud upload |
| audit_log.db | SQLite | All system events | 90 days + cloud | Immutable |
| model_cache/ | File system | PyTorch model weights | Versioned | Read-only |

---

## 5. Security Architecture
*(IEC 62443-4-1, SEC-001–SEC-005)*

- **Process isolation:** SPM, ADE, ALM run in separate OS processes; IPC via shared-memory ring buffer
- **Memory safety:** ASLR + stack canaries on all C modules; Python runtime bounds checking
- **Secret management:** Device certificates stored in hardware TPM; never in filesystem
- **Update integrity:** OTA updates validated by signature before installation; rollback on failure
- **Audit trail:** All security events written to append-only log with SHA-256 chain hash

---

## 6. Failure Modes and Mitigations
*(IEC 62304 §5.3.3, ISO 14971 Risk Controls)*

| Failure Mode | Affected Item | Mitigation | Residual Risk |
|-------------|--------------|------------|---------------|
| ADE classifier crash | ADE-CLF | ADE-RULE provides safety-net detection; watchdog restarts process | Low |
| Database corruption | ALM-QUEUE | SQLite WAL mode; local + cloud redundancy | Low |
| SPM sampling lag | SPM-SMP | Latency watchdog triggers alert + log | Medium → Low |
| TLS certificate expiry | CGW-TLS | Certificate expiry monitoring; 30-day renewal reminder | Low |
| Memory exhaustion | All | Memory limit per process (cgroups); OOM → graceful degradation | Low |

---

## 7. Architecture Rationale

| Decision | Rationale |
|----------|-----------|
| Pipeline architecture | Enables independent testing and replacement of each stage |
| Separate Class A/B processes | Failure in UI/CGW cannot corrupt safety-critical ADE/ALM state |
| Dual detection (ML + rules) | Rule engine is independent safety net; prevents single-point failure in ML model |
| SQLite for alert queue | Zero-dependency, ACID-compliant persistence with WAL mode crash resilience |
| FHIR R4 for cloud integration | Interoperability with EHR systems; future-proof standard |

---

*End of SAD-003*
