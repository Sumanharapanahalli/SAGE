# Product Requirements Document
## In-Vehicle Infotainment (IVI) System

**Document ID:** IVI-PRD-2026-001
**Version:** 1.0
**Status:** Draft
**Author:** Product Management — OpenStrategy Runner
**Date:** 2026-03-28
**Classification:** Confidential

---

## 1. Executive Summary

This PRD defines requirements for a next-generation IVI system built on Android Automotive OS (AAOS). The platform delivers embedded voice assistance, hybrid navigation (offline+online), licensed media streaming (Spotify, YouTube Music, Apple Music), and Over-The-Air update capabilities (FOTA/SOTA). The system targets Tier-1 OEM integration across B-segment and C-segment passenger vehicles with a production target of Q4 2026.

---

## 2. Product Vision

> "A zero-distraction, always-current cockpit experience that keeps drivers connected, informed, and entertained — without compromising vehicle safety or privacy."

---

## 3. Stakeholders

| Role | Name / Team | Responsibility |
|---|---|---|
| Product Owner | IVI Product Team | Requirements, prioritization |
| OEM Integration | Vehicle Integration Eng. | HAL, boot chain, HW BOM |
| Safety Engineering | Functional Safety Team | ISO 26262 ASIL classification |
| Cybersecurity | Product Security | UN R155/R156 compliance |
| Legal / Licensing | IP & Licensing | Spotify/Apple Music/YouTube Music DRM |
| QA / Validation | Test Engineering | KPI verification, V-model testing |

---

## 4. Scope

### 4.1 In Scope
- Android Automotive OS 13+ integration as primary OS
- Embedded voice assistant (wake word + NLU on-device)
- Navigation: HERE Maps offline + TomTom online hybrid
- Media streaming: Spotify, YouTube Music, Apple Music
- FOTA (Firmware OTA) and SOTA (Software OTA) update pipeline
- Multi-zone audio and display management
- Driver monitoring system (DMS) integration hooks

### 4.2 Out of Scope
- Advanced Driver Assistance Systems (ADAS) — separate ECU
- V2X / C-V2X communications stack
- OEM telematics back-end (provided by OEM)
- Hardware design (SoC selection is OEM-dependent)

---

## 5. User Personas

### Persona 1: Daily Commuter (Primary)
- Age 28-45, urban/suburban, tech-savvy
- Needs: fast boot, reliable navigation, hands-free calling, music continuity
- Pain points: slow UI, voice misrecognition, data plan consumption

### Persona 2: Long-Haul Driver
- Age 30-55, frequent highway trips
- Needs: offline maps, OTA updates without disrupting journeys, podcast/audiobook support
- Pain points: connectivity drops, update interruptions

### Persona 3: Fleet Manager
- Age 35-55, manages 10-500 vehicles
- Needs: remote SOTA/FOTA deployment, rollback capability, audit logs
- Pain points: inconsistent software versions across fleet, manual update labor

---

## 6. Functional Requirements

### 6.1 Android Automotive OS Integration

| ID | Requirement | MoSCoW | ASIL/QM | Rationale |
|---|---|---|---|---|
| IVI-REQ-001 | The system SHALL boot to a usable UI within 4 seconds from IGN-ON (cold start) | Must Have | QM | Core UX KPI; regulatory expectation in EU |
| IVI-REQ-002 | The system SHALL run Android Automotive OS 13 or later as the primary operating system | Must Have | QM | GMS certification baseline |
| IVI-REQ-003 | The system SHALL implement the AAOS Vehicle HAL (VHAL) with full CAN bus pass-through for climate, windows, and seat controls | Must Have | ASIL-B | Safety-critical vehicle controls via IVI |
| IVI-REQ-004 | The system SHALL isolate the Guest App Zone from the System App Zone using Android multi-user separation | Must Have | ASIL-A | Prevent third-party app interference with safety functions |
| IVI-REQ-005 | The system SHALL support dual-display output (driver cluster + center console) with independent rendering pipelines | Must Have | QM | Product feature requirement |
| IVI-REQ-006 | The system SHOULD support split-screen multitasking (navigation + media) on displays ≥10 inches | Should Have | QM | User experience enhancement |
| IVI-REQ-007 | The system MAY support a rear-seat entertainment zone as a third display output | Could Have | QM | Premium trim package feature |
| IVI-REQ-008 | The system SHALL enforce AAOS driving restriction policies (UI interaction limits at speed >8 km/h) | Must Have | ASIL-B | UN Regulation R79 compliance |
| IVI-REQ-009 | The system SHALL log all VHAL interactions to an on-device tamper-evident audit log | Must Have | QM | ISO 26262 traceability |
| IVI-REQ-010 | The system SHOULD achieve GMS automotive certification within 90 days of milestone M2 | Should Have | QM | Prerequisite for Play Store access |

### 6.2 Embedded Voice Assistant

| ID | Requirement | MoSCoW | ASIL/QM | Rationale |
|---|---|---|---|---|
| IVI-REQ-011 | The system SHALL process wake-word detection fully on-device (no cloud dependency) | Must Have | QM | Privacy regulation (GDPR Art.25), offline usability |
| IVI-REQ-012 | End-to-end voice command latency (wake word → response) SHALL be < 800 ms in P95 | Must Have | QM | Core UX KPI |
| IVI-REQ-013 | Wake-word false activation rate SHALL be < 1 per 8 operating hours | Must Have | QM | Driver distraction mitigation |
| IVI-REQ-014 | The voice assistant SHALL support a minimum of 12 languages at launch | Must Have | QM | Global OEM market coverage |
| IVI-REQ-015 | Voice NLU model SHALL run inference on the IVI SoC NPU without offloading | Must Have | QM | Offline functionality mandate |
| IVI-REQ-016 | The system SHALL support custom wake-word enrollment per driver profile | Should Have | QM | Personalization feature |
| IVI-REQ-017 | Voice commands SHALL control navigation, media, climate (via VHAL), and phone calls | Must Have | ASIL-A | Safety function: hands-free operation |
| IVI-REQ-018 | The assistant SHALL provide audio + HUD confirmation within 200 ms of command recognition | Must Have | ASIL-A | Driver feedback for safety-critical actions |
| IVI-REQ-019 | The system SHOULD support contextual multi-turn dialogue (3 turns without re-wake) | Should Have | QM | UX sophistication |
| IVI-REQ-020 | Voice assistant SHALL degrade to offline NLU if connectivity is unavailable with user notification | Must Have | QM | Graceful degradation |

### 6.3 Navigation (Offline + Online Hybrid)

| ID | Requirement | MoSCoW | ASIL/QM | Rationale |
|---|---|---|---|---|
| IVI-REQ-021 | The system SHALL provide full-country offline navigation with pre-loaded maps for the vehicle's home region | Must Have | QM | Offline usability mandate |
| IVI-REQ-022 | Offline map data SHALL be stored in a dedicated partition (minimum 32 GB reserved) | Must Have | QM | Storage allocation for maps |
| IVI-REQ-023 | The navigation system SHALL seamlessly transition between offline and online modes based on connectivity availability | Must Have | QM | Hybrid navigation requirement |
| IVI-REQ-024 | Online navigation SHALL incorporate real-time traffic (TTI) with < 60 s data freshness | Must Have | QM | Navigation quality KPI |
| IVI-REQ-025 | Route calculation time SHALL be < 3 s for trips up to 1,000 km (offline mode) | Must Have | QM | Navigation performance KPI |
| IVI-REQ-026 | The system SHALL support map updates via SOTA OTA without requiring vehicle service appointment | Must Have | QM | Lifecycle cost reduction |
| IVI-REQ-027 | Navigation SHALL provide turn-by-turn guidance to both the center console display and driver cluster | Must Have | ASIL-A | Driver awareness safety requirement |
| IVI-REQ-028 | The system SHOULD support EV-specific routing (range awareness, charging station POIs) | Should Have | QM | EV model compatibility |
| IVI-REQ-029 | Navigation data SHALL be encrypted at rest using AES-256 | Must Have | QM | UN R155 cybersecurity compliance |
| IVI-REQ-030 | The system MAY support AR overlay navigation using forward camera feed | Could Have | QM | Premium feature, future roadmap |

### 6.4 Media Streaming

| ID | Requirement | MoSCoW | ASIL/QM | Rationale |
|---|---|---|---|---|
| IVI-REQ-031 | The system SHALL integrate Spotify via the Spotify Car Thing SDK / AAOS Media API | Must Have | QM | Primary streaming partner contractual requirement |
| IVI-REQ-032 | The system SHALL integrate YouTube Music via Android Automotive OS native app | Must Have | QM | Google GMS automotive bundle |
| IVI-REQ-033 | The system SHALL integrate Apple Music via CarPlay-compatible bridge or native AAOS port | Must Have | QM | iOS user base coverage |
| IVI-REQ-034 | Audio playback SHALL resume within 2 seconds of IGN-ON from a prior session | Must Have | QM | UX continuity KPI |
| IVI-REQ-035 | The system SHALL support offline playlist caching (Spotify Downloaded, Apple Music Library) | Must Have | QM | Offline usability |
| IVI-REQ-036 | Media controls (play/pause/skip/volume) SHALL be operable via voice, steering wheel buttons, and touchscreen | Must Have | ASIL-A | Multi-modal control for driver safety |
| IVI-REQ-037 | The system SHALL implement DRM-compliant playback (Widevine L1 for HD streams) | Must Have | QM | Licensing compliance |
| IVI-REQ-038 | The system SHOULD support multi-zone audio (front cabin + rear entertainment) with independent source selection | Should Have | QM | Premium trim upsell feature |
| IVI-REQ-039 | Media app state SHALL persist across IGN cycles without requiring re-authentication | Must Have | QM | UX continuity |
| IVI-REQ-040 | The system SHOULD support podcast and audiobook apps (Audible, Pocket Casts) via AAOS Media API | Should Have | QM | Content breadth |
| IVI-REQ-041 | The system SHALL NOT display video content on the driver-facing display while vehicle speed > 8 km/h | Must Have | ASIL-B | Legal requirement (ECE R10, OEM policy) |
| IVI-REQ-042 | The system SHALL support Bluetooth audio as fallback when streaming services are unavailable | Must Have | QM | Graceful degradation |

### 6.5 FOTA / SOTA OTA Updates

| ID | Requirement | MoSCoW | ASIL/QM | Rationale |
|---|---|---|---|---|
| IVI-REQ-043 | The system SHALL support SOTA (Software OTA) for all IVI application layers without requiring vehicle service | Must Have | QM | Lifecycle management, UN R156 |
| IVI-REQ-044 | The system SHALL support FOTA (Firmware OTA) for MCUs and ECUs connected via the IVI OTA gateway | Must Have | ASIL-B | Safety-critical firmware update chain |
| IVI-REQ-045 | OTA update success rate SHALL be ≥ 99.5% across a fleet deployment of ≥ 10,000 vehicles | Must Have | QM | Fleet reliability KPI |
| IVI-REQ-046 | The system SHALL support atomic A/B partition updates with automatic rollback on boot failure | Must Have | ASIL-B | Safety: prevent bricked vehicle ECUs |
| IVI-REQ-047 | OTA updates SHALL be cryptographically signed (ED25519) and verified before installation | Must Have | ASIL-B | UN R155 cybersecurity mandate |
| IVI-REQ-048 | The system SHALL NOT apply FOTA updates while the vehicle is in motion (ASIL gate check) | Must Have | ASIL-B | Safety mandate |
| IVI-REQ-049 | SOTA updates SHALL apply in background with < 5% CPU overhead during driving | Must Have | QM | Performance non-regression |
| IVI-REQ-050 | The system SHALL provide the driver with update availability notification and a 7-day deferral window | Must Have | QM | User consent (GDPR / OEM policy) |
| IVI-REQ-051 | Fleet-wide SOTA rollout SHALL support staged deployment (1% → 10% → 50% → 100%) with automatic halt on error rate > 0.5% | Must Have | QM | Risk management for fleet deployments |
| IVI-REQ-052 | The system SHALL log all OTA events (download, verify, install, rollback) to a tamper-evident audit trail | Must Have | ASIL-A | UN R156 compliance traceability |
| IVI-REQ-053 | OTA delta packages SHALL use binary diff compression (bsdiff/xdelta3) to minimize download size | Should Have | QM | Data plan cost reduction for drivers |
| IVI-REQ-054 | The system SHOULD support scheduled OTA (driver-configurable, e.g., 2 AM when plugged in) | Should Have | QM | User experience |
| IVI-REQ-055 | The system SHALL NOT expose OTA endpoints without mutual TLS authentication | Must Have | ASIL-A | UN R155 cybersecurity |

---

## 7. Non-Functional Requirements

| ID | Category | Requirement | Target | MoSCoW |
|---|---|---|---|---|
| IVI-NFR-001 | Performance | Cold boot to usable UI | < 4 s | Must Have |
| IVI-NFR-002 | Performance | Voice command P95 latency | < 800 ms | Must Have |
| IVI-NFR-003 | Performance | Navigation route calculation (1,000 km, offline) | < 3 s | Must Have |
| IVI-NFR-004 | Performance | Media resume after IGN-ON | < 2 s | Must Have |
| IVI-NFR-005 | Reliability | OTA success rate | ≥ 99.5% | Must Have |
| IVI-NFR-006 | Reliability | System uptime (MTBF) | ≥ 8,760 h (1 year) | Must Have |
| IVI-NFR-007 | Reliability | Wake-word false activation | < 1 per 8 h | Must Have |
| IVI-NFR-008 | Security | All data at rest | AES-256 | Must Have |
| IVI-NFR-009 | Security | OTA package signature | ED25519 + mTLS | Must Have |
| IVI-NFR-010 | Safety | Driving restriction enforcement | Speed > 8 km/h | Must Have |
| IVI-NFR-011 | Compliance | GDPR consent for telemetry | Explicit opt-in | Must Have |
| IVI-NFR-012 | Compliance | UN R155 cybersecurity | Full conformance | Must Have |
| IVI-NFR-013 | Compliance | UN R156 OTA | Full conformance | Must Have |
| IVI-NFR-014 | Compliance | ISO 26262 ASIL-B | Functional safety case | Must Have |
| IVI-NFR-015 | Usability | Glanceable task completion (NHTSA 12-second rule) | ≤ 12 s for any task | Must Have |

---

## 8. Success Metrics (KPIs)

### 8.1 Performance KPIs

| Metric | Baseline | Target | Measurement Method |
|---|---|---|---|
| Cold Boot Time (IGN-ON → UI) | Competitor avg: 7.2 s | **< 4.0 s** | Automated bench test, 1,000 cycles |
| Voice Command Latency (P95) | Competitor avg: 1,400 ms | **< 800 ms** | Automated NLU test suite, 10,000 utterances |
| Wake-Word False Activation | Industry avg: 3/8 h | **< 1/8 h** | 100-hour continuous acoustic test |
| Navigation Route Calc (offline) | Competitor avg: 6 s | **< 3 s** | Automated route benchmark, 500 routes |
| Media Resume Latency | Competitor avg: 4 s | **< 2 s** | Automated IGN cycle test, 200 cycles |

### 8.2 Reliability & Quality KPIs

| Metric | Target | Measurement Method |
|---|---|---|
| OTA Success Rate | **≥ 99.5%** | Fleet telemetry, first 90-day post-launch |
| System Crash Rate | **< 0.1 crashes/100 driving hours** | Telemetry crash reporting |
| Navigation Offline Coverage | **≥ 98% road network** for home region | Map coverage audit vs. OpenStreetMap |
| MTBF | **≥ 8,760 hours** | Accelerated life test (Arrhenius) |

### 8.3 User Experience KPIs

| Metric | Target | Measurement Method |
|---|---|---|
| Driver Satisfaction (JD Power IQS) | **Top 3 in segment** | Annual survey |
| Net Promoter Score (IVI features) | **≥ 45** | 90-day post-delivery survey |
| NHTSA Glance Compliance | **100% tasks ≤ 12 s** | NHTSA MEAL protocol testing |
| Media App Daily Active Usage | **≥ 65% of connected drivers** | Opt-in telemetry |

### 8.4 Business KPIs

| Metric | Target | Measurement Method |
|---|---|---|
| OEM Integration Timeline | **≤ 12 months** from contract | Program milestones |
| GMS Automotive Certification | **Achieved by M2 exit** | Google certification portal |
| Fleet SOTA Deployment (10k vehicles) | **≤ 72 hours** for 100% rollout | Fleet management dashboard |
| Cost per OTA Update (amortized) | **< $0.12 / vehicle / update** | Finance tracking |

---

## 9. Release Roadmap

### Milestone M1: Foundation — AAOS Platform + Boot Target
**Target Date:** Q2 2026 (June 30, 2026)
**Theme:** Stable AAOS 13 platform with boot time KPI achieved

**Included Features:**
- IVI-REQ-001 through IVI-REQ-010 (AAOS integration)
- IVI-REQ-003 (VHAL full pass-through)
- IVI-REQ-008 (driving restrictions)
- IVI-REQ-029 (map data encryption)
- IVI-REQ-047, IVI-REQ-055 (OTA security infrastructure)

**Exit Criteria:**
1. Cold boot to usable UI < 4 s on target SoC (verified across 1,000 cold start cycles)
2. VHAL CAN integration passes OEM vehicle integration test suite (100% pass rate)
3. Driving restriction policy verified: zero touchscreen unlock events at speed > 8 km/h in 48-hour road test
4. AAOS 13 GMS pre-certification audit submitted to Google
5. All ASIL-B requirements for M1 scope have safety work products (HARA, DFA) reviewed and baselined
6. Zero P0 or P1 open defects at milestone gate

---

### Milestone M2: Connected Experience — Voice + Navigation + Media
**Target Date:** Q3 2026 (September 30, 2026)
**Theme:** Full connected experience with voice, navigation, and all three streaming services

**Included Features:**
- IVI-REQ-011 through IVI-REQ-020 (Voice Assistant)
- IVI-REQ-021 through IVI-REQ-029 (Navigation)
- IVI-REQ-031 through IVI-REQ-042 (Media Streaming)
- IVI-REQ-043, IVI-REQ-044 (SOTA/FOTA infrastructure)
- GMS Automotive certification (IVI-REQ-010)

**Exit Criteria:**
1. Voice P95 latency < 800 ms verified across 10,000 utterances in 12 target languages
2. Wake-word false activation < 1 per 8 hours in 100-hour continuous acoustic lab test
3. Offline navigation route calculation < 3 s for 500-route benchmark
4. Online/offline navigation transition verified: zero route interruptions across 200 simulated connectivity toggles
5. All three media streaming apps pass DRM compliance audit (Widevine L1)
6. Media resume latency < 2 s verified across 200 IGN cycle tests
7. GMS Automotive certification received from Google
8. OTA A/B partition swap verified: 100% successful rollback in 50 injected boot-failure tests
9. All ASIL-A requirements safety work products reviewed
10. Zero P0 or P1 open defects at milestone gate

---

### Milestone M3: Production Readiness — OTA + Fleet + Compliance
**Target Date:** Q4 2026 (December 15, 2026)
**Theme:** Fleet-grade OTA, UN R155/R156 compliance, OEM homologation ready

**Included Features:**
- IVI-REQ-045 through IVI-REQ-055 (Full FOTA/SOTA pipeline)
- IVI-REQ-028 (EV routing)
- IVI-REQ-038 (Multi-zone audio)
- IVI-REQ-040 (Podcast/audiobook apps)
- All Should Have requirements not delivered in M1/M2
- Full ISO 26262 safety case closure
- UN R155/R156 type approval documentation

**Exit Criteria:**
1. OTA success rate ≥ 99.5% verified across 10,000-vehicle staged fleet deployment
2. Staged rollout (1% → 10% → 50% → 100%) demonstrated with automatic halt triggered at injected 0.6% error rate
3. FOTA update blocked during motion: 500 test cycles with zero violations
4. OTA cryptographic signature (ED25519 + mTLS) pen test — zero critical findings
5. UN R155 cybersecurity management system audit — no major non-conformities
6. UN R156 OTA SUMS documentation submitted to type approval authority
7. ISO 26262 ASIL-B functional safety case signed off by qualified safety assessor
8. NHTSA MEAL glance compliance: 100% of tasks ≤ 12 seconds
9. JD Power IQS pre-production survey score in top 3 for segment
10. Zero P0 or P1 open defects; P2 count < 15 with all assigned and scheduled

---

### Milestone M4: Enhancement Wave (Post-Launch)
**Target Date:** Q2 2027 (June 2027)
**Theme:** AR navigation, rear seat entertainment, advanced personalization

**Included Features:**
- IVI-REQ-007 (Rear seat entertainment)
- IVI-REQ-030 (AR overlay navigation)
- IVI-REQ-016 (Custom wake-word enrollment)
- IVI-REQ-054 (Scheduled OTA)
- Performance tuning based on real fleet telemetry

---

## 10. MoSCoW Summary

### Must Have (MVP-blocking — 39 functional + 15 NFR)
IVI-REQ-001–005, 008–009, 011–015, 017–018, 020–027, 029, 031–037, 039, 041–052, 055
All NFRs: IVI-NFR-001–015

### Should Have (next increment — 9 requirements)
IVI-REQ-006, 010, 016, 019, 028, 038, 040, 053, 054

### Could Have (future backlog — 2 requirements)
IVI-REQ-007, 030

### Won't Have (this version)
- Augmented HUD — requires dedicated HUD ECU, separate program
- V2X integration — separate connectivity stack
- Biometric driver authentication — hardware dependency not in BOM baseline

---

## 11. Dependencies & Risks

| Risk ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| RISK-001 | GMS Automotive cert delayed by Google | Medium | High | Engage Google APM by M1 gate; pre-audit checklist |
| RISK-002 | Apple Music AAOS native port not ready | Medium | Medium | CarPlay bridge as interim; negotiate Apple partnership by Q1 2026 |
| RISK-003 | OEM SoC NPU insufficient for on-device NLU | Low | High | Qualify backup cloud NLU path; SoC NPU benchmarks by M1 |
| RISK-004 | UN R156 type approval timeline slip | Medium | High | Engage type approval authority 6 months before M3 |
| RISK-005 | Map partition size exceeds OEM storage BOM | Low | Medium | Negotiate 64 GB storage baseline; delta map updates (IVI-REQ-026) |
| RISK-006 | OTA rollback failure on specific SoC bootloader | Low | Critical | A/B partition hardware qualification test at M1; bootloader SLA with SoC vendor |

---

## 12. Assumptions

1. Target SoC includes a hardware NPU capable of INT8 inference at ≥ 4 TOPS
2. OEM provides CAN/LIN vehicle HAL interface documentation by program kickoff
3. Spotify, YouTube Music, and Apple Music licensing agreements are negotiated by Q1 2026
4. Vehicles in scope ship with LTE/5G modem and Wi-Fi 6 module
5. OEM data center provides OTA CDN infrastructure; this PRD covers the on-vehicle client only
6. ISO 26262 development follows the V-model with OEM as system integrator

---

## 13. Appendix A — ISO 26262 ASIL Justification

| ASIL Level | Applied To | Justification |
|---|---|---|
| ASIL-B | VHAL safety-critical controls, OTA FOTA gate, A/B rollback, OTA crypto | Controllable hazards; moderate severity if IVI controls vehicle systems incorrectly |
| ASIL-A | Voice command confirmation, navigation cluster output, media multi-modal control, OTA audit log | Lower severity; human detectable within reaction time |
| QM | All entertainment, streaming, offline UX features | No direct vehicle control path; safety-irrelevant |

All ASIL elements require: HARA, Functional Safety Concept, Technical Safety Concept, and safety validation report.

---

## 14. Appendix B — Regulatory Compliance Matrix

| Regulation | Scope | Requirements Mapped |
|---|---|---|
| UN R155 | Cybersecurity management | IVI-REQ-029, 047, 055, IVI-NFR-008, 009, 012 |
| UN R156 | OTA software updates | IVI-REQ-043–055, IVI-NFR-013 |
| ISO 26262 | Functional safety (ASIL-A/B) | IVI-REQ-003, 004, 008, 017, 018, 027, 036, 044, 046, 048, 052 |
| GDPR Art.25 | Privacy by design | IVI-REQ-011, 050, IVI-NFR-011 |
| NHTSA Driver Distraction | Glance compliance | IVI-REQ-008, 041, IVI-NFR-015 |
| ECE R10 | Video while driving | IVI-REQ-041 |

---

*End of IVI-PRD-2026-001 v1.0*
