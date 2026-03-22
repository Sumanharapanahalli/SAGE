# Regulatory Compliance — Noise Monitoring

**Domain:** iot
**Solution ID:** 060
**Generated:** 2026-03-22T11:53:39.325496
**HITL Level:** standard

---

## 1. Applicable Standards

- **EPA Noise Standards**
- **WHO Guidelines**
- **IEC 61672**
- **IEC 62443**

## 2. Domain Detection Results

- iot (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SAFETY | Produce a hazard analysis and risk assessment for the IoT sensor network: sensor | Risk management, FMEA, hazard analysis |
| Step 5 | SECURITY | Perform threat modeling (STRIDE) for the full IoT stack: sensor nodes, MQTT brok | Threat modeling, penetration testing |
| Step 16 | EMBEDDED_TEST | Design and implement hardware-in-the-loop (HIL) test harness for sensor nodes: a | Hardware-in-the-loop verification |
| Step 17 | COMPLIANCE | Produce IEC 62443 compliance artifacts for the noise monitoring IoT system: Secu | Standards mapping, DHF, traceability |
| Step 19 | QA | Develop the quality assurance test plan covering all system tiers: sensor accura | Verification & validation |
| Step 20 | SYSTEM_TEST | Execute end-to-end system integration tests across the full stack: simulate 50 v | End-to-end validation, performance |

**Total tasks:** 21 | **Compliance tasks:** 6 | **Coverage:** 29%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | EPA Noise Standards compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | WHO Guidelines compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | IEC 61672 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | IEC 62443 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

## 5. Risk Assessment Summary

**Risk Level:** STANDARD — Compliance focus on data protection and quality

| Risk Category | Mitigation in Plan |
|--------------|-------------------|
| Data Privacy | SECURITY + LEGAL tasks |
| Service Quality | QA + SYSTEM_TEST tasks |
| Compliance Gap | REGULATORY tasks (if applicable) |

## 6. Agent Team Assignment

| Agent Role | Tasks Assigned | Team |
|-----------|---------------|------|
| developer | 9 | Engineering |
| regulatory_specialist | 2 | Compliance |
| firmware_engineer | 2 | Engineering |
| data_scientist | 2 | Analysis |
| qa_engineer | 2 | Engineering |
| safety_engineer | 1 | Compliance |
| devops_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically ambitious and structurally coherent plan that correctly identifies the major system components and chooses appropriate technology at each layer. The security posture (STRIDE + IEC 62443 + mTLS + secure boot) and compliance approach (FMEA, traceability matrix, SL-2/SL-3 targets) demonstrate genuine domain knowledge. However, the plan has a cluster of correctness-critical gaps that would cause failures before a regulator or in production: NTP/timezone handling is entirely absent, making the compliance calculations legally unreliable; the Leq gap-handling policy is unspecified, leaving ISO 1996-1 conformance undefined; the ML pipeline has no drift detection or retraining path; and certificate enforcement is placed at the wrong architectural layer. These are not polish issues — they are foundational correctness and auditability failures that a regulatory reviewer would flag immediately. The public complaint endpoint and Kubernetes secrets management are active security liabilities as written. The plan scores 63: the architecture is right, the technology choices are defensible, and a skilled team could build this, but it requires a focused remediation pass on time/timezone correctness, the ML lifecycle, and the security layer assignments before any implementation begins.

### Flaws Identified

1. Step 8: mTLS device certificate validation is assigned to the Python ingestion service, but it MUST be enforced at the Mosquitto broker layer (via `use_identity_as_username` + `require_certificate true`). If the broker accepts plaintext or password-auth fallback, the application-layer check is irrelevant — attackers never reach it.
2. Step 6/10: No NTP synchronisation strategy in firmware. The compliance pipeline computes Leq over calendar hours and day/night periods. If a sensor clock drifts 3–5 minutes (common on embedded Wi-Fi), readings land in the wrong compliance period, producing legally incorrect reports. This is a fundamental correctness flaw.
3. Step 10: Timezone handling is entirely absent. WHO and EU Directive 2002/49/EC thresholds differentiate day (07:00–23:00) and night periods. 'Hourly aggregation' in UTC means sensors in different zones will have wrong period assignments. For a compliance system submitted to regulators, this is disqualifying.
4. Step 10: No specification of how Leq is computed when a sensor has gaps (offline, dropout). A sensor offline for 20 minutes in an hour produces a systematically lower Leq than reality. The plan must define whether gaps are excluded, interpolated, or flagged — ISO 1996-1 does not allow silent omission.
5. Step 9 (ML): 'Domain-specific labeled captures' is hand-wavy. ESC-50 and UrbanSound8K are academic datasets recorded in controlled conditions and do not represent outdoor MEMS microphone frequency response, wind noise, or rain artefacts. Without real-world captures from the actual hardware, the 82% F1 target is unvalidated and likely overoptimistic in deployment.
6. Step 9 (ML): No model drift detection or retraining pipeline. Urban noise patterns change seasonally and with land-use changes. A classifier trained in summer will degrade on winter data (HVAC loads, different traffic patterns). There is no mechanism to detect or respond to this degradation.
7. Step 13: Compliance reports have no digital signature or reproducibility guarantee. If a report is disputed in a regulatory proceeding 18 months later, there is no mechanism to prove the report reflects the data as it existed at generation time. Reports must either be immutably archived or signed with a timestamp authority.
8. Step 14: 500 Leaflet.js markers at 60 fps on a standard laptop is not achievable without marker clustering (e.g., Leaflet.markercluster) or canvas-based rendering. Leaflet DOM markers degrade to ~10 fps at 200+ markers in Chrome. The acceptance criterion will fail on real hardware.
9. Step 3: `frequency_spectrum blob` in the schema description is a red flag. If it is a true binary blob, frequency data cannot be queried, indexed, or aggregated at the database layer. It must be JSONB or a PostgreSQL float array for the ML and compliance pipeline to function without deserialising every row.
10. Step 18: 'HIL smoke test (if HIL runner available)' is a conditional gate that makes firmware CI meaningless. If the HIL runner is unavailable, firmware merges with no hardware validation. Either commit to a dedicated HIL runner in CI or explicitly document that firmware changes require manual HIL sign-off — do not leave it conditional.
11. Step 7: The plan does not address what happens when a device is returned for repair after eFuse burning. Burned eFuses on ESP32-S3 are irreversible. A returned device with burned fuses cannot be reflashed with a new identity without board-level rework. There is no RMA/repair workflow.
12. Step 15: Public complaint submission endpoint has no CAPTCHA, rate limiting, or bot protection specified. A trivial script can flood the database with fake complaints, polluting the compliance correlation dataset and generating false enforcement recommendations.

### Suggestions

1. Add NTP sync as a mandatory firmware task that runs at boot and periodically. Reject (or flag) readings where the local clock diverges from NTP by more than 2 seconds. Log clock-sync events to the audit trail.
2. Store all timestamps in UTC in the database, but add a `timezone` column to `sensor_nodes` and compute day/night compliance periods using the sensor's local timezone via PostgreSQL `AT TIME ZONE`. Test with sensors in UTC±12 boundary conditions.
3. Change `frequency_spectrum` in `noise_readings` from blob to `REAL[]` (PostgreSQL array) or JSONB. This enables `unnest()` aggregations and TimescaleDB continuous aggregates on frequency bands without full row deserialisation.
4. Move mTLS enforcement to Mosquitto: set `require_certificate true`, `use_identity_as_username true`, and configure the CA cert in `mosquitto.conf`. The ingestion service should trust the broker's assertion that the connection is authenticated.
5. Define a gap-handling policy for Leq aggregation. Recommended: flag any hourly aggregation with >10% sensor gap as `INCOMPLETE` and exclude it from compliance calculations; include it in the audit log as a data quality event.
6. Replace the 500-marker Leaflet acceptance criterion with: 'renders 500 sensors using marker clustering at zoom < 12; unclusters to individual markers at zoom ≥ 14; repaints in < 100 ms on cluster state change'. Use Leaflet.markercluster or migrate to deck.gl ScatterplotLayer for heatmap scale.
7. Add a model serving version column to `source_classifications` so that every classification is traceable to the exact ONNX model that produced it. This is required for auditability when the model is retrained.
8. Add a data drift monitor (e.g., Evidently AI) that computes feature distribution statistics weekly and alerts when KL-divergence on any 1/3-octave band exceeds a threshold. Trigger manual retraining review above the threshold.
9. Generate compliance reports with a SHA-256 hash of the underlying query parameters and result set, stored in the `audit_log`. Optionally sign with a server-side RSA key. This enables future reproducibility verification.
10. Add `POST /complaints` rate limiting at the API gateway level: max 5 requests per IP per minute, with CAPTCHA challenge above 2 submissions per session. Store IP hash (not raw IP) to satisfy GDPR.
11. Add a `GDPR` section to Step 11: specify retention period for complaints (recommended: 3 years for regulatory correlation, then anonymise), implement a soft-delete with anonymisation on right-to-erasure request, and document the lawful basis for processing contact_email.
12. Step 18 is missing a staging environment. Add a `staging` namespace in Kubernetes that mirrors production topology. System tests (Step 20) should run against staging, not a separate test cluster, to catch environment-specific failures.

### Missing Elements

1. NTP/PTP time synchronisation specification for firmware and its interaction with compliance period boundaries
2. Timezone-aware compliance threshold evaluation — the plan computes in UTC implicitly
3. Sensor gap handling policy and its impact on Leq computation (ISO 1996-1 conformance requires explicit treatment)
4. Model retraining pipeline: trigger criteria, data labelling workflow, validation gate before promotion to production
5. Concept/data drift monitoring for the ML classifier
6. GDPR data retention and right-to-erasure implementation for citizen_complaints
7. Report reproducibility and tamper-evidence mechanism (hash or digital signature)
8. RMA/repair workflow for devices with burned eFuses
9. Secrets management solution for Kubernetes production (Vault, External Secrets Operator, or Sealed Secrets — env vars are insufficient in K8s)
10. Staging environment between CI and production
11. Incident response and patch management procedure (mandatory IEC 62443-2-1 SR 6.1 requirement — its absence will fail the compliance audit in Step 17)
12. Backup and disaster recovery plan for TimescaleDB and Redis
13. Acoustic housing/weatherproofing specification — firmware accuracy targets are meaningless without a defined acoustic enclosure; outdoor MEMS performance is enclosure-dependent
14. Factory calibration procedure and calibration certificate template for each sensor node
15. API versioning strategy (v1/v2 path prefix or Accept header) — the OpenAPI spec has none, making future breaking changes impossible to deploy without downtime

### Security Risks

1. MQTT broker accepting connections without broker-enforced mTLS: if Mosquitto is misconfigured, the application-layer cert check in Step 8 is a dead letter. Sensor impersonation becomes trivial. Verify with `mosquitto_pub --insecure` against the broker — if it connects, the mTLS is not enforced.
2. Public `/complaints` endpoint with no rate limiting or bot protection is a direct injection vector into the compliance dataset. Fake complaints with high correlation scores (crafted GPS coordinates near sensors) will generate false enforcement recommendations routed to the HITL queue, creating analyst fatigue and potential regulatory liability.
3. Kubernetes secrets for database credentials, Redis passwords, and mTLS CA keys: if stored as standard K8s Secrets (base64-encoded), any user with `get secrets` RBAC permission or etcd access has all credentials. The plan specifies no Vault or equivalent. This is a common production breach vector.
4. Audio clip uploads to object storage: the plan mentions signed URLs but does not specify who can generate them, with what expiry, or what access controls prevent unauthenticated access to audio files containing potentially identifiable environmental sounds. Public bucket misconfiguration risk.
5. OTA update signing: Step 6 specifies OTA but Step 7 specifies secure boot with RSA-3072. The plan does not explicitly state that OTA firmware images must be signed with the same key chain as secure boot. An unsigned OTA image accepted by the bootloader would bypass the entire secure boot guarantee.
6. Redis Streams has no authentication configured in the plan. If Redis is accessible within the cluster without a password (`requirepass`), any compromised microservice can inject arbitrary events into the compliance pipeline, triggering false enforcement recommendations.
7. The enforcement recommender agent (Step 12) uses 'local noise ordinance thresholds' with no specified source. If this data is fetched from an external URL or mutable config file, an attacker who controls that source can manipulate enforcement recommendations before HITL review, creating a prompt-injection-equivalent risk at the data layer.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.325528
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
