# Regulatory Compliance — Industrial Iot Platform

**Domain:** iot
**Solution ID:** 052
**Generated:** 2026-03-22T11:53:39.323487
**HITL Level:** standard

---

## 1. Applicable Standards

- **IEC 62443**
- **ISO 27001**
- **NIST Cybersecurity Framework**

## 2. Domain Detection Results

- iot (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SECURITY | Produce IEC 62443 threat model covering MQTT broker, OPC-UA server, SCADA integr | Threat modeling, penetration testing |
| Step 14 | EMBEDDED_TEST | Write firmware unit tests (Unity framework) and HIL test specs for edge gateway: | Hardware-in-the-loop verification |
| Step 16 | SECURITY | Implement IEC 62443 security controls: mutual TLS for MQTT, OPC-UA certificate a | Threat modeling, penetration testing |
| Step 18 | COMPLIANCE | Produce IEC 62443 compliance evidence artifacts: Security Management Plan, Syste | Standards mapping, DHF, traceability |
| Step 19 | SYSTEM_TEST | Execute end-to-end system test suite: simulate 100 edge devices sending MQTT and | End-to-end validation, performance |

**Total tasks:** 20 | **Compliance tasks:** 5 | **Coverage:** 25%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | IEC 62443 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | NIST Cybersecurity Framework compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| devops_engineer | 2 | Engineering |
| safety_engineer | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| firmware_engineer | 1 | Engineering |
| data_scientist | 1 | Analysis |
| ux_designer | 1 | Design |
| regulatory_specialist | 1 | Compliance |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This plan has solid architectural ambition and covers the right problem surface — MQTT/OPC-UA ingestion, TimescaleDB time-series, ML for predictive maintenance, IEC 62443 compliance, and SCADA integration are all present and sequenced with genuine thought. However, it contains several category-level failures that would cause production rework: the API is designed after implementation (violating API-first, guaranteeing schema drift), the ML acceptance criteria are evaluated against data that does not exist and cannot exist at sprint time, the Python ingestion throughput target is unrealistic under load with validation enabled, and the PKI infrastructure required to make mTLS actually work across 100+ devices is entirely absent. The DNP3 library choice is a known minefield that the plan treats as a solved problem. The sequential bottleneck through Steps 5-10 → 11 → 12 → 13 means any ML delay (near-certain) freezes the entire frontend. For an MVP/prototype this would score higher, but the plan explicitly targets IEC 62443 compliance and production-grade industrial deployment — at that bar, the missing PKI lifecycle, undefined OTA signing scheme, absent observability stack, and unvalidated throughput assumptions are not polish items; they are ship-blocking gaps. Fundamental rework required on API sequencing, ML data strategy, library validation, and certificate infrastructure before this plan is production-credible.

### Flaws Identified

1. API design (Step 11) comes AFTER all backend services (Steps 5-10) are built. Services built without a contract will need rework when the OpenAPI spec is formalized. This is API-last, not API-first, and will cause schema drift between services.
2. ML training data does not exist. Step 10 requires F1 >= 0.80 for Isolation Forest and MAE <= 10% RMSE for LSTM RUL, but TimescaleDB will only contain days-old synthetic dev data at this point. LSTM RUL requires labeled run-to-failure datasets that cannot be generated during a development sprint.
3. Python/asyncio MQTT ingestion at 10,000 msg/s (Step 5) with per-message JSON Schema validation and Kafka producer overhead is unrealistic for a single process. Python GIL + aiomqtt + jsonschema + aiokafka will saturate well below this target. No benchmarking strategy precedes the commitment.
4. Firmware (Step 4) and MQTT ingestion (Step 5) are developed in parallel with no shared payload contract. If the STM32 firmware publishes one JSON structure and the ingestion service validates a different schema, you get 100% DLQ on first integration. No protocol contract document is defined before either step starts.
5. DNP3 via pydnp3 (Step 9) is a critical dependency risk. pydnp3 is minimally maintained, lacks DNP3 Secure Authentication v5 (SA5), and has incomplete unsolicited reporting support. Industrial RTUs frequently require SA5. This library will likely block the SCADA adapter in production.
6. Step 11 (API) depends on Steps 3, 8, 9, 10. Step 12 (FastAPI impl) depends on Step 11. Step 13 (frontend) depends on Step 12. This creates a 6-step sequential critical path through the middle of the project — ML completion gates the entire UI. Any ML delay (and ML always delays) freezes frontend development.
7. OTA firmware update is described as a 'stub' (Step 4) but the acceptance criteria require it to handle partial writes and boot from primary partition on failure. A functional OTA state machine for STM32F4 with dual-bank flash and bootloader handoff is 2-4 weeks of work, not a stub.
8. Certificate lifecycle for mTLS per-device (Step 16) is completely undefined. With 100+ devices: Who is the CA? What is the certificate rotation schedule? What happens when a device cert expires mid-operation? There is no PKI infrastructure step anywhere in this plan.
9. SBOM generation is placed at Step 2, before 95% of the codebase exists. SBOM must be a continuous process regenerated on every dependency change, not a one-time artifact. The SBOM produced at Step 2 will be obsolete by Step 5.
10. Step 19 requires 'zero message loss during Kafka broker failover' but Step 1 provisions a single-node Kafka. You cannot test multi-broker failover against a single-node cluster. A multi-broker setup with replication factor >= 2 and min.insync.replicas = 2 is required for this test to be meaningful.
11. No observability stack is defined anywhere. Steps mention metrics endpoints, but there is no Prometheus scrape config, Grafana dashboard, or log aggregation (Loki/ELK) step. Operators cannot monitor a production industrial IoT system through raw /metrics endpoints.
12. WCAG 2.1 AA (Step 13 acceptance criteria) is a significant standalone effort typically requiring an accessibility specialist and multiple audit/fix cycles. Listing it as a checkbox on a frontend step with no dedicated process or resource allocation is wishful thinking.
13. Step 3 sets a 365-day retention policy without regulatory analysis. Industrial maintenance records for equipment covered by regulations like OSHA 29 CFR 1910.217 or EU Machinery Directive may require 3-10 years. This number was chosen arbitrarily.

### Suggestions

1. Promote API design to Step 2 or 3 (after DB schema, before any service implementation). Define the canonical sensor payload schema, Kafka message envelope, and REST contracts before firmware or ingestion services are written. Use a shared Protobuf or JSON Schema repo as the single source of truth.
2. Replace the ML acceptance criteria with data-availability gates: Step 10 should first define what historical training data is required (source, volume, labeling), whether synthetic data generation is acceptable for MVP, and what the fallback is if F1 < 0.80 on real data. Do not accept metric targets against nonexistent data.
3. Benchmark Python MQTT ingestion throughput early. Add a Step 5a spike: build a minimal ingestion loop and load-test it against the Mosquitto broker before committing to the architecture. If Python cannot hit 10k msg/s with validation, you need a Go or Rust ingestion layer, or a simpler validation strategy (async/deferred schema check).
4. Replace pydnp3 with a proven DNP3 stack. Evaluate Automatak's DNP3 (C++ with Python bindings, actively maintained, SA5 support) or implement the DNP3 adapter as a sidecar using a battle-tested C library. Document the DNP3 feature matrix required and verify library support before committing.
5. Add a PKI/Certificate Management step between Steps 2 and 16. Define the CA hierarchy (offline root CA, intermediate CA), device certificate template, issuance workflow (CSR at provisioning time), rotation policy, and OCSP/CRL distribution. Without this, mTLS is an intent, not an implementation.
6. Add a multi-broker Kafka cluster to the dev Docker Compose from Step 1 (3-node cluster, replication factor 2). The failover test in Step 19 is only meaningful if the dev and staging environments match the topology being tested.
7. Add a Step 1b or Step 7b for observability infrastructure: Prometheus + Grafana + structured log aggregation. Define alert thresholds for ingestion lag, DB write latency, and Kafka consumer group lag. Industrial operators need dashboards, not raw metrics endpoints.
8. Decouple the firmware OTA from the ingestion service timeline. Create a dedicated OTA management service with a proper bootloader handoff protocol, cryptographic image verification (Ed25519 or ECDSA), and rollback mechanism. This is not a stub — scope it as a full task.
9. Define a data seeding and historical backfill strategy before Step 10. Either source real historical sensor datasets (NASA CMAPSS, PRONOSTIA bearings), generate synthetic run-to-failure data with a physics-based simulator, or descope LSTM RUL to anomaly detection only for MVP.
10. Separate the safety_engineer and security_engineer roles. IEC 62443 security engineering and functional safety engineering are distinct disciplines with different competency requirements. Assigning both to one role understates the required expertise.

### Missing Elements

1. PKI / Certificate Authority infrastructure for device identity provisioning — no CA, no issuance workflow, no rotation policy defined anywhere.
2. Canonical data contract (Protobuf schema or shared JSON Schema registry) shared between firmware, ingestion services, and Kafka consumers — currently each step invents its own schema.
3. Historical training dataset strategy for ML models — F1/MAE acceptance criteria are meaningless without a defined dataset source.
4. Multi-broker Kafka topology for failover testing — single-node Kafka cannot validate the Step 19 zero-message-loss acceptance criterion.
5. Observability stack — Prometheus, Grafana, and log aggregation are entirely absent from the plan.
6. Disaster recovery — no RPO/RTO, no TimescaleDB backup schedule, no multi-AZ strategy.
7. JWT key rotation procedure — RS256 keys expire; there is no defined process for rotating signing keys without downtime.
8. MQTT broker-level rate limiting and topic ACL policy — rate limiting is only defined at the API layer; a compromised device can flood the broker unchecked.
9. Device provisioning workflow — how does a new edge device receive its mTLS certificate and initial configuration at factory or field installation time?
10. Emergency override for SCADA HITL approval — what happens when an actuator command is safety-critical and the approver is unavailable? No degraded-mode procedure is defined.
11. Continuous SBOM pipeline — SBOM is a one-time artifact at Step 2 but must be regenerated on every dependency change to remain valid for IEC 62443 compliance.
12. DNP3 feature matrix validation against pydnp3 capabilities before committing to that library.

### Security Risks

1. No broker-level MQTT topic ACL or rate limiting. A single compromised device with a valid client certificate can publish to any topic at any rate, enabling sensor data spoofing or DoS of the ingestion pipeline.
2. DNP3 Secure Authentication v5 (SA5) is not explicitly required. Without SA5, the DNP3 link is vulnerable to spoofed master station commands — a well-documented ICS attack vector (cf. NERC CIP).
3. JWT key rotation is undefined. If the RS256 private key is compromised, there is no documented revocation or rotation procedure. Long-lived API keys (M2M) are particularly high risk without a rotation schedule.
4. OTA firmware images lack a defined cryptographic signing and verification scheme. The plan mentions 'firmware signing enabled' as an acceptance criterion but provides no signing key management, verification implementation, or rollback-on-invalid-signature behavior.
5. No intrusion detection or anomaly monitoring at the network level. IEC 62443-3-3 SR 6.1 requires security audit logging, but there is no SIEM or network-level IDS/IPS step. A lateral movement from DMZ to internal zone would go undetected.
6. Redis Pub/Sub for WebSocket fan-out (Step 12) uses fire-and-forget semantics. Alert notifications delivered over WebSocket can be silently dropped if a client is transiently disconnected. For a safety-relevant alert system, this is a reliability failure.
7. Secrets backend is 'HashiCorp Vault or AWS Secrets Manager' — the 'or' is unresolved at the point services are built. Services written assuming Vault dynamic secrets will not work with AWS Secrets Manager without code changes, and vice versa.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.323519
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
