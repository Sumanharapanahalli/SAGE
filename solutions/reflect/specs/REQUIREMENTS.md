# REQUIREMENTS.md — Reflect Movement Analysis Platform

**Last Updated:** 2026-03-13
**Status:** Living Document

---

## Functional Requirements

### FR-01: Extract Pipeline
- FR-01.1 Accept video input: local file (.mp4, .mov), webcam, or URL
- FR-01.2 Extract 33 BlazePose landmarks per frame at ≥ 30 FPS
- FR-01.3 Normalize landmarks to hip-center, unit scale
- FR-01.4 Detect hold vs transition phases using landmark velocity
- FR-01.5 Compute gold standard skeleton: mean landmark position per hold phase
- FR-01.6 Derive angle ranges: target_min/max (mean ± 2σ), warning zone (±3σ)
- FR-01.7 Support rep-based movements: detect rep cycle top/bottom positions
- FR-01.8 Output portable skill pack: definition.json, signature.sig, thumbnail.png
- FR-01.9 Admin review UI: skeleton overlay on video, adjustable phase boundaries

### FR-02: Skill Pack
- FR-02.1 Schema version tracked (current: v4)
- FR-02.2 RSA-2048 signature required before distribution
- FR-02.3 Clinical review sign-off required for PT/therapy movements
- FR-02.4 Skill pack validates against JSON schema before signing
- FR-02.5 Pass rate on test recordings ≥ 85% before signing

### FR-03: C++ Pose Engine
- FR-03.1 Real-time joint scoring against skill pack thresholds
- FR-03.2 Confidence-weighted scoring: low-confidence joint has reduced weight
- FR-03.3 Per-joint severity: OK / warning / correction
- FR-03.4 FFI C API: stable, versioned, null-safe
- FR-03.5 Frame scoring latency < 5ms p95 on mid-range Android (2020+)
- FR-03.6 All 80 C++ tests pass in CI

### FR-04: Flutter App
- FR-04.1 Android and iOS support (desktop: Linux/macOS/Windows optional)
- FR-04.2 Camera pipeline at 30 FPS: CameraX (Android), AVFoundation (iOS)
- FR-04.3 Dart isolate for off-main-thread inference
- FR-04.4 CustomPainter skeleton overlay: < 2ms paint time
- FR-04.5 TTS feedback: one correction at a time, positive framing
- FR-04.6 Browse activity modules and movements
- FR-04.7 Session tracking: hold time, rep count, score history
- FR-04.8 Offline first: skill packs on device, no cloud upload of biometrics

### FR-05: Tenant / White-Label
- FR-05.1 Per-tenant branding: app name, logo, primary colour
- FR-05.2 Per-tenant activity module selection
- FR-05.3 Per-tenant feature flags
- FR-05.4 RSA license issued per tenant, validated offline
- FR-05.5 Tenant isolation: no cross-tenant data access
- FR-05.6 Tenant schema version: current v3

### FR-06: SAGE Agents (Development Assistant)
- FR-06.1 10 agents defined with full tool inventories
- FR-06.2 Escalation chain between agents
- FR-06.3 All agent tool calls logged (interactions.jsonl)
- FR-06.4 88+ agent tests passing

---

## Non-Functional Requirements

### NFR-01: Privacy & Security
- NFR-01.1 No biometric data uploaded to cloud — on-device only
- NFR-01.2 RSA-2048 signing for skill packs and tenant licenses
- NFR-01.3 Audit trail for all clinical sign-offs

### NFR-02: Performance
- NFR-02.1 Flutter app: 30 FPS on mid-range 2020+ device
- NFR-02.2 C++ scoring: < 5ms p95 per frame
- NFR-02.3 Extract pipeline: process 1 minute of video in < 2 minutes on CPU

### NFR-03: Test Coverage
- NFR-03.1 All non-Flutter test suites: no regressions between PRs
- NFR-03.2 New features require tests before merge
- NFR-03.3 Coverage baseline: maintained, never decreasing

### NFR-04: Portability
- NFR-04.1 Extract engine: runs on any machine with Python 3.10+ and MediaPipe
- NFR-04.2 Flutter app: single codebase for Android + iOS + desktop
- NFR-04.3 C++ engine: POSIX-compliant, Android NDK compatible

---

## Out of Scope (explicitly not building)

- Cloud pose inference (all inference on-device)
- Face recognition or biometric identification
- Individual user tracking across sessions (GDPR)
- Social features (leaderboards, sharing)
