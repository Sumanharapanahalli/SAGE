# Regulatory Compliance — Rehab Exercise Tracker

**Domain:** medtech
**Solution ID:** 007
**Generated:** 2026-03-22T11:53:39.308468
**HITL Level:** strict

---

## 1. Applicable Standards

- **FDA Class I**
- **HIPAA**
- **IEC 62304**

## 2. Domain Detection Results

- medtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | SAFETY | Conduct ISO 14971 hazard analysis and FMEA for the pose estimation system. Ident | Risk management, FMEA, hazard analysis |
| Step 5 | COMPLIANCE | Establish the Design History File (DHF) framework, quality management plan per I | Standards mapping, DHF, traceability |
| Step 6 | LEGAL | Draft HIPAA Business Associate Agreement templates, Terms of Service, Privacy Po | Privacy, licensing, contracts |
| Step 13 | SECURITY | Conduct threat modeling (STRIDE) for the full system, penetration test plan, HIP | Threat modeling, penetration testing |
| Step 17 | EMBEDDED_TEST | Create device testing harness for the native camera pipeline and on-device ML in | Hardware-in-the-loop verification |
| Step 18 | QA | Design and execute the quality assurance test plan covering functional testing,  | Verification & validation |
| Step 19 | SYSTEM_TEST | Execute full end-to-end system integration tests: therapist assigns program → pa | End-to-end validation, performance |
| Step 20 | COMPLIANCE | Compile complete Design History File (DHF) artifacts per FDA 21 CFR Part 820.30. | Standards mapping, DHF, traceability |
| Step 21 | REGULATORY | Prepare FDA 510(k) Substantial Equivalence analysis (if pursuing clearance) or c | Submission preparation, audit readiness |

**Total tasks:** 24 | **Compliance tasks:** 9 | **Coverage:** 38%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FDA Class I compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | HIPAA compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | IEC 62304 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** HIGH — Safety-critical domain requiring strict HITL gates

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Patient/User Safety | SAFETY tasks with FMEA and hazard analysis |
| Data Integrity | DATABASE tasks with audit trail requirements |
| Cybersecurity | SECURITY tasks with threat modeling |
| Regulatory Non-compliance | REGULATORY + COMPLIANCE tasks |
| Software Defects | QA + SYSTEM_TEST + EMBEDDED_TEST tasks |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 6 | Engineering |
| regulatory_specialist | 3 | Compliance |
| safety_engineer | 2 | Compliance |
| data_scientist | 2 | Analysis |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| ux_designer | 1 | Design |
| legal_advisor | 1 | Compliance |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically ambitious and clearly domain-knowledgeable plan that demonstrates familiarity with the regulatory, clinical, and engineering requirements of health software. However, it contains a foundational legal flaw that must be resolved before any other work begins: the FDA classification is inconsistent. A true General Wellness Policy device requires none of the ISO 14971, IEC 62304, or 21 CFR Part 820 overhead specified in steps 4, 5, and 20 — but if the device measures ROM against clinical norms and guides therapeutic exercise, it is almost certainly a 510(k)-required Class II device, not Class I. This single ambiguity could invalidate 6+ months of compliance work. Separately, the ML pipeline has no data foundation — fine-tuning MoveNet on rehabilitation exercises requires labeled clinical video data that does not exist in the plan and requires IRB approval to collect. The clinical validation study is statistically underpowered (n=10) and has no IRB process, making it unusable as regulatory evidence. The architecture has three significant operational risks: PostgreSQL under time-series write load at scale, Apache Airflow for simple metric aggregation, and the Expo/native module bridging decision. Security is treated as a post-build audit rather than a design input. The plan scores 62 — solid domain coverage and structure, but the regulatory classification ambiguity, missing dataset/IRB path, and ML data gap represent fundamental blockers, not refinements. Resolve the FDA classification first; everything else depends on it.

### Flaws Identified

1. FDA classification is internally contradictory. 'General Wellness Policy' devices are NOT medical devices and are exempt from 21 CFR Part 820, ISO 14971, and IEC 62304 entirely. Yet the plan mandates a full DHF, ISO 13485 QMS, IEC 62304 Class B lifecycle, and ISO 14971 FMEA. If the device qualifies for General Wellness exemption, this compliance layer is ~6 months of wasted effort. If it makes ROM improvement or therapeutic exercise claims, it is a Class II medical device requiring 510(k) — not Class I. The plan tries to have both simultaneously, which is not a legal position.
2. Step 9 assumes MoveNet fine-tuning on 'rehab exercise test set' but no step creates or acquires this dataset. MoveNet Thunder was trained on fitness/yoga imagery. Clinical rehabilitation exercises (post-surgical shoulder flexion, knee extension after ACL repair) are distribution-shifted from training data. Fine-tuning requires IRB-approved clinical data collection with patient consent — a process that typically takes 4-6 months and is completely absent from the plan.
3. Clinical validation study (Step 18) uses n=10 participants across 15 exercises. This is statistically underpowered for a ±5-degree ROM accuracy claim. A one-sample t-test against goniometer ground truth with SD typical of pose estimation (~3-8 degrees) requires n≥25 per exercise type for 80% power at α=0.05. With n=10, you will fail to detect meaningful error in borderline exercises. This study design will not survive FDA scrutiny.
4. React Native + Expo SDK 52 with a complex custom native camera pipeline (Step 10) creates a fundamental technical conflict. Expo's managed workflow does not support arbitrary native modules. Switching to bare workflow or Expo Dev Client negates most of the Expo productivity benefit and adds native build complexity equivalent to writing native apps. The plan treats this as trivial bridging but it is a major architectural decision that determines the entire mobile development strategy.
5. PostgreSQL is chosen for 30fps × 33 keypoints × 60-minute sessions (≈3.56M rows per session at 17 keypoints or ≈7.1M if tracking all 33). At 500 concurrent sessions (load test target), that's 1.78B inserts/hour during peak. PostgreSQL with column-level AES-256 encryption on each row will not sustain this without TimescaleDB extension or a dedicated time-series backend (InfluxDB/QuestDB). The Step 7 benchmark of '<500ms for a single 60s session insert' is far too narrow — it tests the happy path, not concurrent write saturation.
6. Apache Airflow in Step 14 for session metric aggregation is 10x the operational complexity required. Airflow needs its own scheduler, webserver, worker pool, Celery, Redis, and a separate PostgreSQL metadata database — adding 5+ new K8s deployments. The actual work (aggregate reps, compute form scores, run trend calcs) is 6 SQL queries that belong in a Celery beat task or a PostgreSQL scheduled function. This will consume disproportionate DevOps time to operate.
7. Security threat modeling (Step 13) depends on Steps 11 and 12 — meaning security is designed after the entire system is built. STRIDE analysis at this point becomes a documentation exercise rather than a design input. PHI encryption strategy, camera feed privacy, and injection attack surfaces need to be in Step 7-8 as design constraints, not Step 13 as a post-hoc audit.
8. No IRB (Institutional Review Board) approval process is present anywhere in the plan. The clinical validation study in Step 18 — comparing app ROM measurements to goniometer readings on human participants — requires IRB approval before a single subject is enrolled. IRB submission, review, and approval typically takes 3-6 months at academic medical centers. This is a hard gating dependency that is completely absent, making Step 18's timeline unrealistic.
9. No offline mode is designed. Physical rehabilitation patients perform home exercise programs without reliable internet access. The plan's entire session flow assumes live API connectivity. A patient mid-session who loses connectivity will get no pose feedback and no rep counting. For a home rehab product, offline-first session execution with sync-on-reconnect is a core functional requirement, not an enhancement.
10. Step 10 is labeled 'FIRMWARE' but implements native mobile SDK code. This is either a naming error or signals that the build orchestrator has incorrectly classified this task, which means agent routing is wrong and the firmware agent (with embedded/RTOS expertise) may be producing iOS Swift code.

### Suggestions

1. Resolve the FDA classification before writing a single line of code. If the intended use is 'exercise guidance and tracking for general wellness' with no diagnostic or therapeutic claims, operate under the General Wellness Policy — drop ISO 14971, IEC 62304, and DHF entirely. If ROM measurement is compared against clinical norms or used to guide clinical decisions, file a Pre-Sub meeting request with FDA to determine whether 510(k) is required. The answer changes the budget by 12-18 months and $500K-$2M.
2. Add a Step 0 (Data Collection) before Step 9: design an IRB-approved study to collect labeled video of rehabilitation exercises performed by actual patients under physical therapist supervision, with concurrent goniometer ground truth. Minimum 500 labeled sessions across 30 exercise types from 50+ participants. Without this, the 'fine-tuning' in Step 9 and the clinical validation in Step 18 have no foundation.
3. Replace Expo managed workflow with either (a) a true native app (Swift + Kotlin) if performance is the priority, or (b) React Native bare workflow with explicit bridging contracts defined before Step 10 begins. The current plan conflates framework choices in a way that will cause integration failure at Step 12.
4. Replace PostgreSQL time-series storage for pose keypoints with TimescaleDB (drop-in PostgreSQL extension) or partition the pose_keypoints table by session_id with hypertables. Alternatively, store raw keypoint streams in S3 as compressed binary blobs and compute aggregates (rep counts, form scores) server-side before persisting only derived metrics to PostgreSQL.
5. Replace Apache Airflow with Celery beat tasks that are already in the stack (Step 11 uses Celery + Redis). A single Celery periodic task triggered on session completion handles all 6 metrics with zero additional infrastructure.
6. Move security threat modeling to Step 4.5 (between Safety and Compliance) as a design input, not a post-implementation audit. The STRIDE output should feed the database design (Step 7) and API design (Step 8) with specific mitigations as requirements.
7. Add IRB engagement as a parallel step to Step 1-2, targeting academic medical center or clinic partner who can sponsor the study. IRB approval should be a hard dependency before Step 18 begins.
8. Add offline-first architecture as a requirement in Step 1. The session execution flow must function without connectivity: local TFLite inference (already planned), local SQLite session storage, background sync queue. This changes the API design (Step 8) to support idempotent session upload rather than live streaming.
9. The clinical validation statistical design needs a formal power analysis. Engage a biostatistician at Step 1 to define minimum sample sizes per exercise type, stratified by joint (shoulder vs. knee vs. hip), with pre-specified primary endpoint and non-inferiority margin vs. goniometer.
10. Pediatric use case: specify minimum age in intended use statement and add COPPA analysis in Step 6. Many sports/orthopedic rehab patients are 12-17. If the app is available to minors, parental consent flows and data handling for minors must be designed.
11. Add a model monitoring strategy to Step 16 DevOps: pose accuracy alerting when inference latency increases (indicating OS/hardware changes) or when form score distributions shift (indicating model drift). Without this, accuracy regression post-launch will go undetected.

### Missing Elements

1. IRB approval process and timeline — hard blocker for clinical validation study
2. Labeled clinical rehabilitation dataset acquisition plan — prerequisite for ML fine-tuning
3. Offline session execution architecture — core functional requirement for home rehab use
4. Formal statistical power analysis for clinical validation study design
5. App Store compliance review — Apple App Store guidelines Section 5.1.1 (Data Collection and Storage) has specific requirements for health apps; HealthKit integration review; Google Play health app policy
6. Consent management flows — camera access consent, PHI processing consent, research participation consent
7. Exercise contraindication enforcement logic — the safety FMEA identifies 'missed contraindicated movement' as a hazard but no implementation step builds contraindication checking into the exercise assignment or session flow
8. Data retention and right-to-deletion implementation — HIPAA requires appropriate retention (state laws add 7-10 year requirements); GDPR Article 17 right to erasure; no deletion pipeline designed
9. Mid-range Android device coverage — device matrix covers flagship devices only; rehab patient populations skew toward mid-range hardware (Samsung A-series, Moto G); Tensor G1 NPU support is materially different from Snapdragon NPU
10. BAA execution process with cloud providers — Step 16 mentions 'AWS BAA signed' as acceptance criteria but does not identify who is responsible, when it must be in place (before any PHI touches AWS), or the downstream vendor BAA chain (Twilio for SMS, SendGrid for email, etc.)
11. Push notification delivery for missed sessions — step 19 tests delivery but no implementation step builds the missed-session detection logic or notification scheduling system
12. Video storage strategy — Step 7 lists 'session video' as a PHI field requiring encryption, but no implementation step addresses whether video is recorded, stored, or streamed; this is either a major omitted feature or the field is a vestigial artifact

### Security Risks

1. Column-level AES-256 encryption on PostgreSQL without key rotation strategy: if the application-layer encryption key is compromised, all PHI is exposed retroactively. Key management via AWS KMS with automatic 90-day rotation must be specified in the database design, not assumed.
2. TFLite model file distribution: the on-device model is a proprietary asset. The plan has no model integrity verification (hash validation before loading) or anti-tampering protection. A compromised model could produce systematically wrong pose feedback — the exact hazard identified in the FMEA.
3. SMART on FHIR token storage on mobile: SMART on FHIR access tokens are long-lived bearer tokens. If stored incorrectly (AsyncStorage in React Native is NOT the Keychain), an attacker with device access can impersonate the patient. Step 13 mentions Keychain/Keystore but Step 12 (where token storage is actually implemented) has no corresponding acceptance criterion.
4. Camera feed privacy: the real-time camera pipeline processes video frames in memory. On Android, the Camera2 API frame buffer can be accessed by apps with CAMERA permission. If the app is compromised or a malicious library is included, live video of patients could be exfiltrated. No frame-level access controls or in-memory isolation is specified.
5. Pose keypoint ingestion API (POST /pose-data) accepts 30fps × 33 keypoints from mobile clients. Without strict input validation and rate limiting per session_id, this endpoint is vulnerable to coordinate injection — an attacker could submit fabricated pose data that generates fraudulent 'good form' scores, corrupting therapy records. Step 8 specifies rate limiting but not session-scoped validation or signed payloads.
6. Celery + Redis task queue: if Redis is not password-protected and network-isolated within the VPC, an attacker with internal network access can inject arbitrary Celery tasks, including report generation with attacker-controlled patient data. The plan does not specify Redis AUTH or TLS for the Celery broker connection.
7. WeasyPrint PDF generation: WeasyPrint renders HTML to PDF using a headless browser-like engine. If therapist report templates include any unsanitized patient-provided content (exercise notes, pain descriptions), this is a server-side HTML injection vector. The plan has no explicit output encoding requirement for the report generation pipeline.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.308512
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
