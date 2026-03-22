# Regulatory Compliance — Water Quality Monitor

**Domain:** iot
**Solution ID:** 056
**Generated:** 2026-03-22T11:53:39.324473
**HITL Level:** standard

---

## 1. Applicable Standards

- **EPA Standards**
- **IEC 62443**
- **ISO 17025**

## 2. Domain Detection Results

- iot (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | SECURITY | Produce a threat model for the IoT sensor network and cloud platform. Cover devi | Threat modeling, penetration testing |
| Step 6 | COMPLIANCE | Map product requirements to IEC 62443, ISO 27001, and SOC 2 Type II controls. Pr | Standards mapping, DHF, traceability |
| Step 7 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR + CCPA for location and monitoring  | Privacy, licensing, contracts |
| Step 16 | EMBEDDED_TEST | Write firmware unit tests (Unity framework) and HIL test specs for all 4 sensor  | Hardware-in-the-loop verification |
| Step 18 | QA | Design the QA test plan covering: sensor reading accuracy validation (against NI | Verification & validation |
| Step 19 | SYSTEM_TEST | Execute end-to-end system tests across the full stack: physical (or simulated) s | End-to-end validation, performance |

**Total tasks:** 22 | **Compliance tasks:** 6 | **Coverage:** 27%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | EPA Standards compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | IEC 62443 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | ISO 17025 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 6 | Engineering |
| qa_engineer | 3 | Engineering |
| devops_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| marketing_strategist | 1 | Operations |
| ux_designer | 1 | Design |
| safety_engineer | 1 | Compliance |
| regulatory_specialist | 1 | Compliance |
| legal_advisor | 1 | Compliance |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This is an architecturally ambitious and well-structured plan that demonstrates genuine domain knowledge — the sensor selection, SAGE framework integration, IEC 62443 zoning intent, and TimescaleDB choice are all defensible. However, it has three categories of failure that would each independently block production: (1) Scientific invalidity — missing temperature compensation invalidates every pH, DO, and conductivity reading for EPA purposes, and the DFRobot turbidity sensor cannot satisfy Method 180.1, making the entire compliance reporting feature legally unusable; (2) Infrastructure assumptions that are wrong — TimescaleDB on RDS as described does not exist in the form assumed, and the absence of a durable message queue between EMQX and the DB writer means data loss is guaranteed under any ingestion service restart; (3) Compliance gaps — CROMERR is the legal framework for electronic EPA submissions and its absence means the product cannot file reports to federal or state agency data systems regardless of how correct the PDF looks. The plan would work as a prototype for demonstrating the architecture, but shipping it as a compliance product without addressing these issues would expose customers to regulatory liability. Score reflects strong structural foundation undermined by fundamental measurement, infrastructure, and regulatory gaps that require rework before production readiness.

### Flaws Identified

1. Temperature compensation is entirely absent. pH, dissolved oxygen, and conductivity readings are all temperature-dependent. The EZO circuits support temperature-compensated readings (requires a DS18B20 or PT1000 probe and a separate EZO-RTD circuit), but no temperature sensor appears in the BOM, HAL driver list, schema, or calibration wizard. Without temperature compensation, every EPA report generated is scientifically invalid.
2. TimescaleDB on AWS RDS is not straightforward. AWS RDS for PostgreSQL supports only a limited, vetted extension list — TimescaleDB community edition requires either self-hosted EC2, Timescale Cloud, or MSB (Managed Service for TimescaleDB). The plan assumes 'RDS_TimescaleDB' as if it is a first-class RDS offering. This assumption will break infra provisioning.
3. Throughput acceptance criteria is internally inconsistent. Step 9 requires '>10,000 readings/second for 1,000-node deployments' but Step 10 specifies 1Hz sample rate = 1,000 msg/s for 1,000 nodes. The 10x discrepancy is never explained. Either the benchmark target is wrong or the sample rate assumption is wrong — whichever it is, the schema sizing, EMQX capacity planning, and MQTT ingestion pipeline are all built on the wrong number.
4. CROMERR (Cross-Media Electronic Reporting Rule, 40 CFR Part 3) is never mentioned. Any system that electronically submits compliance data to EPA or state agencies must meet CROMERR identity proofing, electronic signature, and audit trail requirements. A PDF export does not satisfy CROMERR. This is a legal blocker, not a gap — missing this means the product cannot legally file EPA reports electronically.
5. DFRobot SEN0189 is not suitable for EPA Method 180.1 turbidity compliance. It is a $4 analog sensor calibrated in NTU-equivalent units using scattered light at a fixed angle, with no ISO 7027 compliance and no NIST-traceable certification path. Atlas Scientific makes an EZO-TBD circuit for turbidity with a compliant probe. Using the DFRobot part invalidates the turbidity compliance claim.
6. Thundering herd on reconnect is unaddressed. If 1,000 nodes each hold a 24-hour circular buffer (86,400 readings) and reconnect simultaneously after a network outage, that is 86,400,000 MQTT messages arriving in a short window. The ingestion pipeline, EMQX, and TimescaleDB will be overwhelmed. There is no jitter/backoff strategy, no replay rate limiting, and no EMQX queue depth configuration to handle this scenario.
7. Device provisioning at scale (X.509 certificate issuance for 1,000+ nodes) is not designed. 'Device identity provisioned' appears as a one-line acceptance criterion in Step 5. In practice this requires a PKI hierarchy (root CA → intermediate CA → device cert), a zero-touch provisioning flow (device generates keypair, CSR submitted to CA at manufacturing or first boot), certificate revocation (OCSP or CRL), and rotation. None of this is designed. AWS IoT Core would solve most of it but is not in the architecture.
8. The ingestion pipeline between EMQX and TimescaleDB has no durability layer. The plan describes 'MQTT broker bridge (EMQX) → ingestion pipeline → TimescaleDB' with async batch inserts in FastAPI. If the FastAPI ingestion service crashes or TimescaleDB is slow, messages queued in EMQX will be dropped (QoS 0) or back-pressure will cause device disconnections. A durable message queue (Kafka, Kinesis, or even EMQX's built-in persistence) between broker and DB writer is required for the 99.5% uptime SLA with zero data loss.
9. MQTT QoS level is never specified anywhere in the plan. For EPA compliance and zero data loss, QoS 1 or 2 is required. QoS 0 (fire-and-forget) is the default and would silently drop readings under any network instability. This should be an explicit firmware and broker configuration requirement.
10. Calibration drift management is missing. The calibration wizard covers initial 4-point calibration but the plan has no: (a) calibration interval scheduling and operator reminders, (b) drift detection to flag when a sensor's response curve has shifted beyond tolerance, (c) out-of-calibration data flagging or lockout to prevent submission of stale-calibration readings to EPA reports. ISO/EPA QA/QC procedures require documented calibration intervals (typically 30–90 days for EZO circuits in field deployments).
11. Data quality flags are absent from the schema. EPA reporting under 40 CFR Part 136 and NPDES permits requires data qualifier flags (e.g., 'Q' for questionable, 'D' for dilution applied, 'E' for estimated, '<' for below detection limit). The readings table has no quality_flag column. Any EPA report generated without qualifier flags will be rejected by agency data systems.
12. Multi-site management deferred to V2 is architecturally dangerous. The database schema, API tenant isolation, and device identity model all need multi-site awareness from day 1 (foreign keys, node_id scoping, VPN segmentation per site). Retrofitting multi-site later requires schema migrations and breaking API changes. The stakeholder list includes 'municipal water utility' which universally has multiple intake/discharge points.
13. Step 8 (SAGE CONFIG) is a prerequisite for Step 9 (DATABASE DESIGN). This is backwards. Database schema should be designed based on domain requirements, not gated behind a YAML configuration step. The schema design for a time-series IoT system is a technical deliverable that should be independent of the agent framework configuration.
14. NTP time synchronization and clock drift are not addressed. Accurate timestamps are essential for EPA compliance (readings must have legally defensible timestamps). The firmware spec does not include NTP sync task, clock drift compensation, or handling of readings with invalid system time (e.g., before first NTP sync after power-on). A reading with a wrong timestamp in an EPA report is a compliance violation.

### Suggestions

1. Add a 5th sensor: Atlas Scientific EZO-RTD (temperature probe). Make temperature compensation a firmware-level requirement, not an optional calibration step. Update schema to include temperature_c column in all readings. All 3 EZO circuits (pH, DO, EC) expose temperature compensation commands — wire them together in the HAL.
2. Replace 'RDS_TimescaleDB' with an explicit choice: Timescale Cloud (managed, simplest), self-hosted TimescaleDB on EC2 within the same VPC (full control), or MSB. Document the chosen option in the infra architecture. If cost is a constraint, Timescale Cloud's compression reduces storage cost ~94% vs raw PostgreSQL.
3. Add an intermediate message bus (Amazon Kinesis Data Streams or MSK/Kafka) between EMQX and the TimescaleDB writer. This gives you replay-on-failure, back-pressure handling, and the ability to fan out the same stream to multiple consumers (ML anomaly detection, alert engine, archival) without coupling them to EMQX.
4. Replace the DFRobot SEN0189 with Atlas Scientific EZO-TBD + probe in the BOM and firmware spec. This keeps the sensor interface consistent (all EZO UART protocol) and provides a NIST-traceable calibration path required for EPA Method 180.1.
5. Add CROMERR compliance as a dedicated task between Steps 6 and 7. Define the electronic signature method (Level 2 e-signature for most NPDES submissions), identity proofing workflow for compliance officers, and the CDX (Central Data Exchange) submission format for federal EPA reporting.
6. Add MQTT QoS level as an explicit firmware and broker configuration requirement. Set QoS 1 for all sensor readings and QoS 2 for calibration records and alert events. Update EMQX configuration to enable persistent sessions and offline message queuing.
7. Add reconnect jitter and replay rate limiting to the firmware. On reconnect, each node should wait a random backoff (0–300s based on node_id hash) before replaying buffered readings, capped at a configurable max replay rate (e.g., 10 readings/second). Prevents thundering herd after mass outages.
8. Design the PKI and provisioning flow in Step 5 with specificity: define the CA hierarchy, the manufacturing-time provisioning flow (or first-boot provisioning via a claim certificate), and the cert rotation procedure. AWS IoT Core + Just-In-Time Provisioning would cover most of this without building custom PKI.
9. Add data_quality_flag (VARCHAR or ENUM) and is_temperature_compensated (BOOLEAN) columns to the readings table in Step 9. Add a view or materialized view that filters out unqualified readings for EPA report generation.
10. Move multi-site support to MVP scope for the schema and device identity layers only (add site_id foreign key to sensor_nodes, scope all queries by site_id). Defer the multi-site UI management to V2 as planned, but do not defer the data model change.

### Missing Elements

1. Temperature sensor (EZO-RTD or DS18B20) in hardware BOM and temperature compensation logic in all sensor HAL drivers
2. CROMERR compliance design for electronic EPA submissions (40 CFR Part 3)
3. NPDES permit-specific report format support — most dischargers submit to state agencies via EDI or agency-specific portals, not generic PDF
4. PKI hierarchy design and zero-touch device provisioning workflow at manufacturing scale
5. Calibration interval management: scheduling, reminders, drift detection, and out-of-calibration data quarantine
6. Data quality flag column in schema and qualifier logic in EPA report generation
7. Durable message queue between EMQX and TimescaleDB writer (currently a reliability gap under the 99.5% uptime SLA)
8. Reconnect backoff and replay rate-limiting strategy for the 86,400-reading offline buffer
9. NTP sync task in firmware and timestamp validation before readings are committed to the queue
10. MQTT QoS level specified in firmware requirements and EMQX broker configuration
11. Firmware signing key management (HSM or AWS KMS for private key storage — cannot be a plaintext file in CI)
12. Certificate revocation mechanism (OCSP/CRL) for compromised or decommissioned devices
13. Sensor detection limit handling: what happens when DO = 0 or pH reads outside physical range? Schema and report generation must handle below-detection-limit values with appropriate flags
14. Multi-site data model (site_id) in MVP schema — cannot be retrofitted cleanly after launch

### Security Risks

1. Firmware signing key management unspecified. If the signing private key is stored in GitHub Actions secrets or as a plaintext CI environment variable, it can be exfiltrated via a compromised dependency or Actions runner. Require HSM or AWS KMS-backed signing with audit logging for every firmware release signature.
2. Zero-touch device provisioning gap creates a supply chain attack surface. Without a defined provisioning flow, someone inserting a rogue node with a valid claim certificate (or exploiting a permissive provisioning policy) could inject false readings into EPA compliance reports. Require per-device unique claim certificates burned at manufacturing, not shared claim certs.
3. EMQX topic authorization not specified. By default, EMQX permits any authenticated device to publish to any topic. A compromised sensor node could publish to other nodes' topics, injecting false readings. Require per-device ACL rules: node_id X can only publish to `sensors/{node_id}/readings`.
4. No mention of MQTT payload schema validation at the ingestion layer. A compromised device sending malformed JSON or oversize payloads could crash the FastAPI ingestion service or cause database errors. Validate payload schema and enforce max size at the EMQX hook layer before reaching the ingestion pipeline.
5. OAuth2 JWT secret rotation not addressed. If the JWT signing secret is static and leaked, all sessions are compromised with no recovery path. Require JWKS endpoint with short-lived tokens (15 min access, 24h refresh) and documented rotation procedure.
6. IEC 62443 zone model places MQTT broker in the OT zone with 'no direct OT→internet path', but sensors must reach the MQTT broker over the internet (or cellular) from field deployments. The zone model as described does not account for remote field devices — the OT zone would need to be a VPN tunnel termination, not a network segment. This misapplication of the zone model leaves field devices uncategorized.
7. No mention of rate limiting or anomaly detection on the MQTT ingestion path. A compromised node (or botnet of nodes) could flood the ingestion pipeline with high-frequency readings. Require per-device message rate limits enforced at the EMQX broker level.
8. SOC 2 Type II is listed as a compliance target but the timeline implies it would be in-scope from launch. SOC 2 Type II requires a minimum 6-month observation period of controls in operation. Either the launch date expectations are wrong, or the plan should target SOC 2 Type I for initial certification and Type II at the 12-month mark.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.324506
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
