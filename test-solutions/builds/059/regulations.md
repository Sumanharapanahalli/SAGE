# Regulatory Compliance — Smart Parking

**Domain:** iot
**Solution ID:** 059
**Generated:** 2026-03-22T11:53:39.325254
**HITL Level:** standard

---

## 1. Applicable Standards

- **IEC 62443**
- **PCI DSS**
- **ADA Compliance**
- **FCC Part 15**

## 2. Domain Detection Results

- iot (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | SECURITY | Produce threat model, IEC 62443 zone/conduit diagram, and SBOM for the full smar | Threat modeling, penetration testing |
| Step 17 | EMBEDDED_TEST | Write firmware unit tests (Unity/CMock) and HIL test spec for occupancy sensor n | Hardware-in-the-loop verification |
| Step 19 | SYSTEM_TEST | Design and execute end-to-end system tests: driver books slot via mobile app, se | End-to-end validation, performance |
| Step 20 | COMPLIANCE | Produce IEC 62443 compliance artifacts: security requirements traceability matri | Standards mapping, DHF, traceability |
| Step 22 | LEGAL | Draft Terms of Service, Privacy Policy (GDPR/CCPA), and data processing agreemen | Privacy, licensing, contracts |

**Total tasks:** 24 | **Compliance tasks:** 5 | **Coverage:** 21%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | IEC 62443 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 3 | ADA Compliance compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | FCC Part 15 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 8 | Engineering |
| devops_engineer | 3 | Engineering |
| regulatory_specialist | 2 | Compliance |
| data_scientist | 2 | Analysis |
| qa_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| firmware_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| legal_advisor | 1 | Compliance |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is an architecturally ambitious 24-step plan with genuinely good coverage of compliance, testing, and the full stack — but it contains at least two critical infrastructure contradictions that will cause the build to fail before reaching staging: the Mosquitto/AWS IoT Core dual-broker conflict and the unsupported assumption that TimescaleDB runs on AWS RDS. Beyond these blockers, the plan has no device provisioning strategy (meaning sensors cannot authenticate in production), no LoRaWAN network infrastructure despite specifying it as a firmware feature, and no solution to the ML cold-start problem at new city deployments. The security threat model is produced too early to be accurate, and IoT devices cannot reach a private-subnet-only MQTT broker from parking lots. With the critical infrastructure conflicts resolved and the missing provisioning/LoRa/ML-cold-start gaps addressed, this plan has the right bones — the dependency graph is mostly sound, the compliance artifacts are appropriately scoped, and the testing strategy is realistic. As written, a team that executes this plan verbatim will hit a wall in the firmware integration sprint and spend weeks in unplanned infrastructure rework. Score: 54 — fundamental rework on the IoT transport architecture, database hosting, and device provisioning is required before this is executable.

### Flaws Identified

1. CRITICAL — Mosquitto (Step 10) vs AWS IoT Core (Step 15) architectural conflict: the plan simultaneously builds a self-hosted Mosquitto broker AND provisions AWS IoT Core. These are mutually exclusive IoT transport choices. Running both in production creates duplicate device registries, split certificate authorities, and undefined routing logic. Pick one.
2. CRITICAL — TimescaleDB on AWS RDS is not supported: AWS RDS PostgreSQL does not offer TimescaleDB as a managed extension. TimescaleDB on AWS requires either self-managed EC2, Timescale Cloud, or Aurora PostgreSQL with custom extensions. Steps 6, 8, 11, and 15 all assume this works natively — it does not. The Terraform plan in Step 15 will not produce a working TimescaleDB instance.
3. CRITICAL — LoRaWAN fallback (Step 5) has no supporting infrastructure: the firmware specifies LoRaWAN as a fallback comms path, but nowhere in the 24 steps is LoRa gateway hardware provisioned, cloud network server configured (ChirpStack, TTN, or AWS IoT Core for LoRaWAN), or frequency band/regulatory approval addressed. This feature will not work.
4. CRITICAL — Sensor-triggered payment capture is a liability without error handling: Step 9 acceptance criterion states 'Capture triggered automatically on validated entry event from sensor.' A sensor false positive or network race condition triggers an unauthorized charge. No dispute resolution flow, no sensor confidence threshold for payment decisions, no fallback for failed captures during sensor outage.
5. HIGH — Device certificate provisioning at scale is entirely missing: Step 10 requires x.509 mTLS per-device certificates, but no step covers manufacturing-time certificate injection, a Certificate Authority setup, a device provisioning service, or bulk enrollment tooling. Provisioning 500+ ESP32 nodes in the field manually is not a deployment — it is a project failure.
6. HIGH — ML cold-start problem is unaddressed: Step 12 trains an LSTM on 'historical time-series data' but a new city deployment has zero historical occupancy data. Prophet requires weeks of data minimum; LSTM requires months. The acceptance criterion 'MAE <10% on held-out 30-day test set' cannot be validated at launch. No synthetic data strategy, transfer learning approach, or fallback-to-rule-based prediction is defined.
7. HIGH — Mosquitto broker in private subnets contradicts field device connectivity: Step 15 specifies 'private subnets for IoT broker' with 'no public ingress,' but ESP32 devices are deployed in parking lots and need internet-accessible MQTT endpoints. A private-subnet-only broker is unreachable from the field without a VPN or bastion — neither of which is in the plan.
8. HIGH — Security threat model (Step 3) precedes the attack surface being designed: Step 3 runs before Steps 6 (database), 7 (API), 8 (backend), 10 (IoT gateway), and 15 (infra). The STRIDE analysis and zone/conduit diagram will be based on assumptions, not implemented architecture. Step 20 (compliance artifacts) depends on Step 3 outputs that are structurally incomplete when produced.
9. HIGH — API design (Step 7) does not depend on database schema (Step 6): Steps 6 and 7 run in parallel. API response shapes and database column names frequently diverge when designed independently, requiring expensive reconciliation during Step 8 implementation.
10. MEDIUM — Firmware CI with physical hardware flashing is unresolved: Step 16 specifies 'esptool.py in CI for integration test harness' but GitHub Actions hosted runners have no USB/serial ports. Self-hosted runners with attached hardware are required, adding infra overhead and flakiness that can block the entire firmware pipeline.
11. MEDIUM — Turn-by-turn navigation inside parking structures is GPS-dead: Step 13 acceptance criterion requires 'turn-by-turn navigation from current location to selected slot functional on iOS and Android.' Multi-story or underground garages have no GPS signal. No indoor positioning technology (BLE beacons, WiFi RTT, UWB) is specified anywhere.
12. MEDIUM — Weather feature for ML model has no data source: Step 12 lists 'weather' as an input feature but no weather API integration, data ingestion pipeline, or historical weather backfill is defined in any step.
13. MEDIUM — GDPR right-to-erasure across immutable storage is underspecified: Step 22 requires a right-to-erasure API endpoint, but driver data exists across TimescaleDB hypertables (append-only chunks), S3 Parquet files (immutable), vector store embeddings, and potentially Stripe. Deletion across all these systems within GDPR's 30-day window requires a coordinated erasure pipeline that is not scoped.
14. MEDIUM — iOS WebSocket restrictions will break real-time slot updates: Step 13 assumes persistent WebSocket connections for slot availability updates on mobile. iOS aggressively suspends background apps and terminates WebSocket connections. No push notification fallback (APNs/FCM) or reconnection strategy is specified.
15. MEDIUM — Overstay and grace period logic is absent from payment design: Step 9 handles pre-auth, capture on entry, and refund on cancellation — but defines no behavior for overstay (vehicle stays past reservation end), partial refunds for early exit, or dynamic pricing. City parking contracts typically require these.
16. LOW — Step 3 applies IEC 62443 to a parking system: IEC 62443 is an industrial control system standard designed for SCADA/DCS. Smart parking is not an ICS. While defensible, IEC 62443 compliance adds significant overhead versus OWASP IoT Top 10 + ISO 27001, which are the actual standards city procurement will reference. No rationale for this choice is given.

### Suggestions

1. Resolve IoT transport architecture first (before any other step): choose AWS IoT Core (managed, scales, integrates with ECS natively) OR self-hosted Mosquitto (more control, more ops burden). Remove the other from the plan entirely. AWS IoT Core is the correct answer for a city-scale deployment.
2. Replace RDS TimescaleDB with Timescale Cloud or self-managed TimescaleDB on EC2 in the Terraform plan. Alternatively, use RDS PostgreSQL with native partitioning and evaluate whether TimescaleDB's performance guarantees are actually needed at the expected data volumes.
3. Add a Step 0 or Step 4.5: Hardware Architecture Decision Record covering sensor type selection (ultrasonic vs magnetic — fundamentally different deployment models), LoRa vs WiFi-only decision, PCB/enclosure specs, IP rating, and operating temperature range. This gates Steps 5 and 17.
4. Add device provisioning as a distinct step (dependency: Step 3 for CA setup, Step 10 for broker): define the Certificate Authority, device enrollment service, manufacturing provisioning tooling, and field replacement procedure. This unblocks actual deployment.
5. Address ML cold-start explicitly: ship Prophet with synthetic seasonality priors derived from city-average parking patterns as Day 1 behavior. Gate LSTM training on 90 days of real data. Define the model warm-up period in the PRD acceptance criteria.
6. Add a weather data ingestion step between Steps 11 and 12: specify the weather API provider (OpenWeatherMap, Tomorrow.io), ingestion cadence, historical backfill for training, and schema for joining to occupancy_events.
7. Move Step 7 (API design) to depend on Step 6 (database), or explicitly run a reconciliation task after both complete before Step 8 begins.
8. For Mosquitto CI testing in Step 16: use a software MQTT broker (Eclipse Mosquitto Docker container) for unit/integration tests and document that HIL tests require self-hosted runners with attached hardware — separate these into distinct CI job types.
9. Add indoor navigation strategy to Step 2 (UX) scope: either explicitly descope to outdoor-only navigation with a clear 'walk to entrance' CTA, or specify BLE beacon infrastructure as a dependency and add a beacon deployment step.
10. Define sensor confidence threshold policy for payment triggering in Step 9: a single sensor reading should not trigger a financial transaction. Require N consecutive occupied readings over T seconds before capture, with a manual override flow for disputes.

### Missing Elements

1. Device certificate authority and manufacturing-time provisioning workflow (required before any mTLS device auth can work)
2. LoRaWAN network server and gateway hardware provisioning (required if LoRaWAN fallback is kept in scope)
3. Weather API integration and historical weather data backfill (required for ML feature pipeline)
4. Application observability stack: no CloudWatch alarms, no distributed tracing (X-Ray/Jaeger), no error alerting (PagerDuty/OpsGenie) — the ops runbooks in Step 23 reference incident response but there is nothing to generate alerts
5. Overstay detection and dynamic pricing logic (common city contract requirement, affects payment and reservation services)
6. Sensor hardware validation: environmental testing (IP67 rating, -20°C to 60°C operation), false positive/negative rate baseline measurement against real vehicles before firmware acceptance criteria are meaningful
7. Indoor navigation strategy or explicit scope exclusion for sub-level parking structures
8. Data residency and sovereignty requirements for city government contracts (many cities require data to remain within national borders — affects AWS region selection and S3 export in Step 11)
9. Stripe payout and revenue split mechanism if the platform takes a fee from parking lot owners (likely required for commercial viability — no mention of platform economics in payment design)
10. API rate limiting and abuse prevention for the public-facing reservation API (no WAF, no rate limiter defined beyond IoT device MQTT limits)

### Security Risks

1. mTLS certificate revocation is unspecified: if a deployed sensor node is physically stolen or compromised, there is no documented CRL or OCSP responder to revoke its certificate. A stolen node retains valid authentication credentials indefinitely.
2. JWT secret rotation strategy absent: Step 8 uses python-jose for JWT but no key rotation procedure, token expiry policy, or refresh token flow is defined. Leaked JWT secrets require a service restart to invalidate — unacceptable for a city-scale deployment.
3. MQTT topic structure exposes lot and slot IDs to all authenticated devices: 'parking/{lot_id}/slot/{slot_id}/status' means any authenticated sensor can subscribe to any other sensor's topic. No per-device topic ACL is defined, enabling a compromised node to eavesdrop on the entire deployment.
4. Stripe webhook endpoint in Step 9 is verified by signature — correct — but the endpoint must be idempotent. Stripe will retry failed webhooks. If the capture logic is not idempotent, a transient failure causes double-captures. The acceptance criteria do not test idempotency.
5. S3 Parquet exports in Step 11 contain raw occupancy and potentially user-attributable data. No mention of S3 bucket encryption at rest, access logging, or pre-signed URL expiry for Athena access. Cold storage is frequently the weakest link in data breach scenarios.
6. OTA firmware update in Step 5 verifies the update succeeds but the plan does not specify the signing key custody model. Who holds the firmware signing key? What is the compromise procedure? Unsigned or weakly-signed OTA is the most common IoT supply chain attack vector.
7. Multi-agent coordinator in Step 21 accepts 'natural language or structured' queries against the analytics backend. Natural language input to a system with database access and bulk export capabilities is an injection risk. No input sanitization, query scope limiting, or output filtering is defined for the LLM-mediated path.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.325286
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
