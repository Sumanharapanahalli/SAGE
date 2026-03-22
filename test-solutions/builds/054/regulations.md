# Regulatory Compliance — Asset Tracking

**Domain:** iot
**Solution ID:** 054
**Generated:** 2026-03-22T11:53:39.324007
**HITL Level:** standard

---

## 1. Applicable Standards

- **IEC 62443**
- **FCC Part 15**
- **GDPR**

## 2. Domain Detection Results

- iot (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | SECURITY | Produce IEC 62443 SL-2 threat model for the full asset tracking system. Cover BL | Threat modeling, penetration testing |
| Step 18 | SECURITY | Implement IEC 62443 SL-2 security controls across all system layers: (1) Device  | Threat modeling, penetration testing |
| Step 19 | EMBEDDED_TEST | Write HIL (Hardware-in-the-Loop) test suite for BLE beacon and GPS tracker firmw | Hardware-in-the-loop verification |
| Step 21 | SYSTEM_TEST | End-to-end system test using hardware simulators. Scenario 1: full supply chain  | End-to-end validation, performance |
| Step 22 | COMPLIANCE | Produce IEC 62443 compliance artifacts for the asset tracking system. Deliverabl | Standards mapping, DHF, traceability |

**Total tasks:** 24 | **Compliance tasks:** 5 | **Coverage:** 21%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | IEC 62443 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | FCC Part 15 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| developer | 10 | Engineering |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 3 | Engineering |
| firmware_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| data_scientist | 1 | Analysis |
| system_tester | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically detailed and well-structured plan that covers the right domains — firmware, backend services, RTLS, geofencing, supply chain FSM, security, and compliance — with appropriate sequencing for most dependencies. The database schema, ingestion pipeline design, and testing strategy (real DB, HIL simulators, E2E with Playwright/Locust) reflect solid engineering discipline. However, there are several concrete failure modes that will prevent this from shipping as specified. The ±2m BLE RTLS accuracy target is physically unachievable with RSSI trilateration in real environments and will cause acceptance test failures at system test. The Redis Pub/Sub/Streams inconsistency is a silent data loss bug in the highest-throughput path. The AES-128 beacon encryption has no corresponding decryption implementation. The hardware_sim dependency inversion will block CI setup for weeks. CRL-based revocation is operationally incompatible with offline IoT devices. These are not polish issues — they are architectural decisions that affect every downstream step. Address the RTLS accuracy target, Redis architecture, encryption key management, MQTT broker selection, and device provisioning pipeline before implementation begins, and this plan becomes a solid foundation for an MVP.

### Flaws Identified

1. RTLS ±2m accuracy with BLE RSSI trilateration is physically unrealistic. Log-distance path loss (n=2.5) in a warehouse environment with metal shelving, forklift interference, and human bodies will produce ±4–8m at best. Achieving ±2m requires UWB (Decawave/Qorvo) or RF fingerprinting with a calibration phase — neither is in this plan. The acceptance criteria in steps 12 and 21 will fail against real hardware.
2. GPS tracker power target is wrong. Step 8 specifies < 15mA active, < 50µA hibernate. The Sequans Monarch GM01Q LTE-M modem alone draws 200–350mA during transmission bursts. Even with duty cycling, sustained active power will be 50–100mA minimum. The 15mA figure is either a hibernate-mode target or a spec error that will invalidate battery life calculations.
3. Redis Pub/Sub vs Redis Streams inconsistency. Step 11 payload says 'Redis Streams' but the description says 'Redis Pub/Sub.' These are fundamentally different: Pub/Sub is fire-and-forget with no persistence; Streams have consumer groups and replay. Using Pub/Sub means any service restart loses in-flight events. For a 1000 events/sec ingestion pipeline this is a data loss vector that must be resolved architecturally before any code is written.
4. AES-128 payload encryption in firmware (step 7) has no corresponding decryption in the BLE receiver (step 10). The firmware encrypts beacon payloads but step 10's acceptance criteria only validates that asset_id, battery_pct, and sequence_num are decoded. If firmware encryption is active, the receiver will read garbage. Either the encryption is dead code or there is a missing decryption key management step.
5. Hardware simulator dependencies are inverted. Step 9 (hardware_sim) depends on steps 7 and 8 (firmware implementation). Simulators should be built from packet format specs, not from completed firmware. This creates a blocking dependency that slows CI setup: the test infrastructure cannot exist until firmware is done, which means backend integration tests (step 20) cannot run until step 7 and 8 are complete.
6. CRL checking for certificate revocation on offline devices is architecturally broken. Step 18 requires 'GPS tracker rejected by broker when certificate is revoked (CRL check passes).' Devices that are offline for up to 72h (per step 8 offline buffer requirement) cannot reach a CRL distribution point at connection time. OCSP Stapling or short-lived certificates with automated rotation are required for embedded devices. CRL-based revocation will either block legitimate reconnections or be silently bypassed.
7. MQTT broker is never specified. Steps 8, 10, 11 all depend critically on MQTT broker capabilities — X.509 mutual TLS, topic ACLs, CRL checking, QoS guarantees, and horizontal scaling. AWS IoT Core, HiveMQ, EMQ X, and self-hosted Mosquitto have radically different implementations and operational costs for these features. Leaving this unspecified until step 23 (DevOps) means security design (step 18) is being done against an undefined target.
8. MQTT QoS levels are never specified anywhere in the 24-step plan. QoS 0 means the 1000 events/sec pipeline accepts message loss. QoS 1 means the 72h offline buffer replay (step 8) will produce duplicates at the broker unless deduplication is explicitly handled. QoS 2 at 1000 events/sec has significant throughput penalties. This omission means the reliability guarantees claimed in steps 11 and 21 cannot be verified.
9. Geofencing scalability math does not hold at load. Step 13 requires ST_Contains evaluation of 1000 geofences in < 50ms per position update. At 1000 assets pushing events at 1Hz (step 21 load scenario), this is 1000 simultaneous ST_Contains evaluations each against 1000 geofences. PostGIS with spatial index handles this per-query, but 1000 concurrent queries against the same geofence table will saturate a single PostgreSQL instance. No read replica or caching strategy is specified.
10. Supply chain FSM (step 14) transition triggers are undefined. The derived events RECEIVED/IN_TRANSIT/DEPARTED are listed but no trigger rules are specified. What distinguishes RECEIVED_AT_WAREHOUSE from an asset merely entering a warehouse geofence mid-transit? Without explicit FSM transition conditions (e.g., 'RECEIVED requires dwell > 5 min in WAREHOUSE-type geofence after IN_TRANSIT state'), the state machine will generate false events that corrupt supply chain records.

### Suggestions

1. Replace BLE trilateration accuracy target with a realistic ±4m indoor / ±2m with calibration target. Add a beacon calibration step where each deployment site runs a calibration pass to fit the path loss model to the actual environment. If ±2m is a hard business requirement, scope UWB hardware as an alternative and add it to the threat model.
2. Fix the Redis architecture decision explicitly in step 11: choose Redis Streams with consumer groups for the ingestion pipeline. This gives persistence, consumer group replay on restart, and backpressure. Remove all Pub/Sub references and replace with explicit stream names and consumer group names.
3. Add a device provisioning pipeline step between steps 4 and 7. This is a manufacturing-time concern: how are X.509 certs burned into GPS trackers on the production line? How are BLE gateway HMAC keys provisioned? Without this, the security model exists on paper but cannot be operationalized. CFSSL is listed in step 18 but the enrollment workflow is missing.
4. Invert the hardware_sim dependency. Step 9 should depend only on step 6 (API/packet format spec) and step 2 (scaffold). The simulators model the wire format, not the firmware implementation. This unblocks backend testing (steps 11–14) from firmware completion.
5. Replace CRL with OCSP Stapling or short-lived certificate strategy for GPS trackers. The broker should staple OCSP responses; devices validate the stapled response. For the offline scenario, define a grace period policy (e.g., accept certificates with OCSP response < 24h old).
6. Specify MQTT broker in step 2 (scaffold/config), not step 23 (DevOps). The security model and firmware implementation both depend on this. Recommend AWS IoT Core for the default path (handles X.509 provisioning, topic ACLs, and CRL/revocation natively) with Mosquitto for local dev only.
7. Add explicit MQTT topic ACL design to step 6 (API spec). Each device should only be authorized to publish to its own topic (e.g., gps/location/{device_id}). A compromised tracker should not be able to inject data for other devices. This is an FR2 (use control) requirement under IEC 62443 that is currently missing from the security controls.
8. Add a beacon topology calibration sub-step to step 12 (RTLS engine). The path loss parameters (n, A) must be measured per deployment environment, not hardcoded. The calibration procedure should be part of the site commissioning process with an API endpoint to store per-site parameters.

### Missing Elements

1. Floor plan ingestion and beacon placement management. The RTLS engine consumes floor plan GeoJSON and beacon topology but there is no step for how operators upload floor plans, place virtual beacon markers, and keep this map synchronized with physical beacon installations. Without this, the RTLS engine cannot be configured for a real site.
2. Time synchronization strategy for BLE beacons. GPS trackers get time from GNSS. BLE beacons have no NTP source. Gateway-stamped timestamps introduce drift equal to gateway clock error. For supply chain forensics and SLA breach attribution, sub-second timestamp accuracy matters. No NTP or PTP strategy is specified for gateways.
3. API versioning strategy. IoT firmware is long-lived and cannot be updated atomically across a fleet. The API spec (step 6) must define versioning from day one. A GPS tracker firmware from 2025 may still be calling /v1/gps/ingest in 2028. No versioning approach is specified.
4. Beacon battery management workflow. BLE beacons are battery-powered. The system collects battery_pct telemetry but there is no step for battery threshold alerts, bulk battery status reporting for fleet managers, or maintenance workflow triggering. This is a core operational requirement for a deployed asset tracking system.
5. Data retention implementation. Step 1 lists 'data retention policy' as a requirement but no implementation step exists for TimescaleDB data retention policies, automated chunk dropping, or GDPR-compliant per-asset data deletion. For a system ingesting 1Hz location events per asset, unmanaged retention will exhaust storage within months.
6. WebSocket horizontal scaling strategy. Step 12 exposes a WebSocket endpoint for live RTLS streaming. WebSockets are stateful and do not scale horizontally behind a standard load balancer without sticky sessions or a relay layer. With 1000 assets and multiple concurrent dashboard users, this is a scalability ceiling that must be addressed before production.
7. OTA rollout control and rollback. Steps 7 and 8 implement OTA firmware update mechanisms but there is no OTA management plane: no staged rollout (canary to 1% of fleet first), no rollback trigger on error rate spike, no version inventory dashboard. Pushing a bad firmware to 10,000 GPS trackers simultaneously is an unrecoverable failure mode.

### Security Risks

1. BLE beacon payloads are readable by any BLE scanner in range. AES-128 encryption is specified in step 7 firmware but the key distribution mechanism is never defined. How does each beacon get its encryption key? How does the gateway decrypt it? If the key is hardcoded in firmware, a single beacon compromise exposes the entire fleet. This is an FR4 (data confidentiality) gap under IEC 62443.
2. HMAC-SHA256 for BLE gateway authentication (step 11) introduces a shared-secret key management problem. HMAC requires a pre-shared key per gateway. The plan does not specify how these keys are provisioned, rotated, or revoked. A stolen or decommissioned gateway with a valid HMAC key can inject arbitrary location events indefinitely.
3. ERP webhook in step 14 is an uncontrolled data exfiltration path. The configurable POST endpoint sends supply chain events to an external system with no specification of authentication, payload filtering, or data minimization. A misconfigured webhook URL could send asset location data to an unauthorized third party. This violates FR4 and FR5 under IEC 62443 SL-2.
4. Redis is used as the internal message bus between services (steps 11, 12, 13) but Redis security configuration is never addressed. No authentication (requirepass/ACLs), no TLS between services, and no network isolation beyond implicit container networking. A single compromised internal service can inject arbitrary messages to any Redis channel, bypassing all device-level authentication.
5. JWT signing key management is incomplete. Step 18 specifies 15-minute JWT expiry and refresh token rotation but does not address signing key rotation, JWKS endpoint, or key ID (kid) header. A compromised signing key can forge valid tokens for any user indefinitely until the key is manually rotated — which requires a service restart in most naive implementations.
6. GPS spoofing countermeasures are identified in the threat model (step 4) but no implementation step addresses them. The firmware (step 8) has no consistency checks between GPS position, accelerometer data, and expected velocity profiles. A spoofed GPS signal that moves an asset 50km in 1 second should be detectable but will currently be accepted and stored as a valid location event.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.324040
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
