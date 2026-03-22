# Regulatory Compliance — Ev Charging Network

**Domain:** automotive
**Solution ID:** 027
**Generated:** 2026-03-22T11:53:39.316154
**HITL Level:** strict

---

## 1. Applicable Standards

- **OCPP 2.0.1**
- **IEC 61851**
- **ISO 15118**
- **PCI DSS**

## 2. Domain Detection Results

- automotive (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 2 | SAFETY | Perform FMEA and hazard analysis for the EV charging network. Identify failure m | Risk management, FMEA, hazard analysis |
| Step 3 | SECURITY | Produce threat model, penetration test plan, and SBOM for the EV charging networ | Threat modeling, penetration testing |
| Step 18 | EMBEDDED_TEST | Write firmware unit tests and HIL test specifications for the charge point contr | Hardware-in-the-loop verification |
| Step 20 | SYSTEM_TEST | Execute end-to-end system tests: full charge session lifecycle (connect → author | End-to-end validation, performance |
| Step 21 | COMPLIANCE | Produce compliance artifacts for PCI DSS v4.0, SOC 2 Type II, and UNECE R155/R15 | Standards mapping, DHF, traceability |

**Total tasks:** 22 | **Compliance tasks:** 5 | **Coverage:** 23%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | OCPP 2.0.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | IEC 61851 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | ISO 15118 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |

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
| developer | 10 | Engineering |
| regulatory_specialist | 2 | Compliance |
| ux_designer | 2 | Design |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| safety_engineer | 1 | Compliance |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 52/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates strong domain breadth and commendable technical detail across firmware, backend, infrastructure, and testing — the dependency graph is logical and the acceptance criteria are mostly measurable. However, it contains three category-level compliance errors that would cause significant rework or audit failure in a regulated environment: ISO 26262 is misapplied to EVSE infrastructure (the correct standard is IEC 61508/62061), UNECE R155 is misscoped to a CSMS operator who is not a regulated party under that regulation, and the PCI DSS SAQ A-EP classification is likely incorrect for a Stripe Elements implementation. ISO 15118 Plug & Charge is listed as a feature but is a multi-month PKI and protocol engineering project. The OCPP 2.0.1 Python library dependency is a production risk given its incomplete 2.0.1 implementation. On the infrastructure side, horizontal scaling of stateful OCPP WebSocket connections is architecturally unresolved — HPA alone does not address session affinity — and certificate lifecycle management is entirely absent despite mTLS being specified throughout. GDPR is not mentioned despite the driver app collecting location and payment data in likely EU-regulated markets. The firmware MISRA C zero-violation target is unachievable without specifying a tool and deviation process. These are not polish items — they represent fundamental rework of the compliance framework (Steps 2, 3, 21), a significant addition to the firmware scope, and a resolvable but non-trivial infrastructure architecture change. Score 52 reflects a plan that is architecturally coherent and technically competent in many areas but would fail regulatory review and production reliability assessment without addressing these gaps.

### Flaws Identified

1. ISO 26262 misapplied in Step 2: ISO 26262 governs automotive road vehicle E/E systems (ASIL A-D). A charging network management system is not a road vehicle component. The correct functional safety standard is IEC 61508 (general) or IEC 62061 for machinery safety. ASIL ratings generated here will be meaningless and create false compliance assurance.
2. UNECE R155/R156 scope error in Steps 2, 3, 21: UNECE R155/R156 apply to vehicle OEMs and their Tier-1 suppliers — not to charging network operators. The CSMS operator is not a regulated party under R155. The correct cybersecurity frameworks are IEC 62443 (industrial control systems) and ISO 27001. Building a UNECE R155 evidence package for a CSMS is wasted effort and signals a fundamental misunderstanding of the regulatory landscape.
3. PCI DSS SAQ A-EP misclassification in Step 11: SAQ A-EP applies when the merchant's website directly receives card data before passing it to a processor. Stripe Elements (iframe-hosted) qualifies for SAQ A — a significantly lighter attestation. Targeting A-EP triggers unnecessary firewall, IDS, and vulnerability scanning requirements on the CPMS servers that Stripe Elements specifically exempts merchants from.
4. ISO 15118 Plug & Charge is catastrophically underestimated in Step 7: ISO 15118 PnC requires a full V2G PKI (Root CA, Sub-CA, OEM Provisioning Certificate, Contract Certificate), EVCC/SECC TLS mutual authentication with client certificates, OCSP stapling, and contract certificate provisioning workflow. This is a multi-month engineering effort on its own. Listing it as a feature of the OCPP server is a plan-level failure.
5. Python `ocpp` library (mobilityhouse) OCPP 2.0.1 support is immature: The library's 2.0.1 support is incomplete and community-maintained. Key 2.0.1 features (Device Management, ISO 15118, Security Profiles) are partially or not implemented. Building a production CPMS on this library without forking and completing the implementation is a high-probability failure.
6. OCPP WebSocket horizontal scaling is unaddressed: FastAPI WebSocket connections are stateful — a charge point holds a persistent connection to one server process. The plan specifies K8s HPA at 70% CPU but does not address sticky sessions, consistent hashing for CP-to-pod affinity, or distributed OCPP session state. Scaling out CPMS pods without this will result in message routing failures and dropped sessions.
7. Load balancer concurrency control is absent: Step 9's LP solver rebalances on events (new session, 90% threshold). No mutex, solver queue, or debounce is specified. In a 50-CP site with simultaneous session starts, multiple rebalancing triggers will race, potentially generating conflicting SetChargingProfile pushes to the same charge points, violating the OCPP spec constraint that only one charging profile per purpose per connector may be active.
8. RFID authorization cache invalidation is unspecified: The 500ms SLA relies on a local whitelist cache, but the plan does not specify how revoked or suspended RFID tokens are invalidated across all CPMS instances. A revoked token that remains in cache until TTL expiry could continue authorizing sessions — a fraud and liability risk.
9. ENTSO-E API is EU-only and requires registration: Step 8 hard-codes ENTSO-E as the spot market feed. ENTSO-E is the European network operator data platform. US markets use EIA/CAISO/ERCOT. No market-agnostic abstraction layer is specified, making the pricing engine geographically locked to Europe with no stated deployment scope.
10. Firmware MISRA C zero-violation target is unrealistic without tooling specification: FreeRTOS itself ships with documented MISRA C deviations. mbedTLS has known MISRA violations. The acceptance criteria 'MISRA C violations zero' is unachievable without specifying the static analysis tool (LDRA, PC-lint Plus, Polyspace), the MISRA C edition (2004/2012/2023), and an approved deviations list. This criterion will either be silently dropped or block firmware release indefinitely.
11. No GDPR/privacy analysis for EU deployments: The driver app collects GPS location (charging history = movement profile), SoC telemetry, payment history, and RFID identity. For any EU deployment, GDPR Articles 5, 17, 25 (data minimization, right to erasure, privacy by design) require explicit design decisions. Not one step addresses this. A data protection impact assessment (DPIA) is required under GDPR Article 35 for large-scale processing of location data.
12. Certificate lifecycle management is missing entirely: mTLS is specified for inter-service communication (cert-manager) and OCPP charge points. No cert rotation schedule, CRL/OCSP infrastructure, automated renewal (cert-manager + Let's Encrypt or private CA), or charge-point certificate revocation workflow is specified. Certificate expiry is the #1 cause of production outages in EV charging deployments.
13. Involuntary session curtailment billing logic is undefined: Load balancing (Step 9) can reduce or stop charging mid-session. The payment service (Step 11) calculates cost from session start/stop and price snapshots. There is no specification for how a load-balancer-terminated session is billed (partial refund? prorated? operator liability?). This gap will produce disputed charges.
14. OTA firmware signing key storage is unspecified: The CI/CD pipeline (Step 17) signs firmware with Ed25519. The private key location is not specified — environment variable in GitHub Actions Secrets is the implied default, which means it can be exfiltrated by any malicious workflow step or supply chain compromise. HSM-backed signing (AWS CloudHSM, Google Cloud HSM) is required for production firmware distribution to safety-critical devices.

### Suggestions

1. Replace ISO 26262 with IEC 61508/IEC 62061 in Step 2. Assign SIL levels (not ASIL) to CPMS functions. If the charge point controller firmware controls an electrical contactor, it may qualify for SIL 2 under IEC 61508.
2. Replace UNECE R155 compliance with IEC 62443-4-2 (component security) for the charge point firmware and IEC 62443-3-3 (system security requirements) for the CSMS. These are the standards actual EV charging operators are assessed against.
3. Re-scope PCI DSS to SAQ A. Confirm with a QSA that Stripe Elements iframes are fully out-of-scope. If so, SAQ A requires only 22 requirements vs. SAQ A-EP's 191.
4. Extract ISO 15118 PnC into its own multi-step work stream: PKI design, EVCC/SECC implementation on firmware, contract certificate provisioning API, OCSP responder. If not in scope for MVP, explicitly exclude it and remove the reference from Step 7's acceptance criteria.
5. Evaluate alternative OCPP 2.0.1 server implementations: CitrineOS (TypeScript, actively maintained), SteVe (Java, 1.6 + 2.0), or building on the EVEREST framework. Alternatively, commission the mobilityhouse Python library's 2.0.1 completion as a tracked spike before committing to it.
6. Add an OCPP session affinity layer: use NGINX sticky sessions (IP hash or cookie) in front of multiple CPMS pods, store OCPP session state in Redis with the charge point ID as key, and ensure all pod replicas can handle failover by reading state from Redis on reconnect.
7. Add a rebalancing debounce and serialization queue to the load balancer: coalesce events within a 2-second window, serialize LP solver invocations with an asyncio.Lock, and version-stamp SetChargingProfile pushes so stale profile updates from a previous solver run are discarded.
8. Add a GDPR compliance step between Steps 3 and 4: define personal data inventory, legal basis for processing, retention periods (align with data_retention_policy.md in Step 4), and implement soft-delete + erasure API for driver accounts before building any PII-storing tables.
9. Add certificate lifecycle management to Step 16/17: define cert rotation period (90 days for inter-service), automate rotation via cert-manager CertificateRequest resources, implement charge-point certificate revocation via OCSP, and add a Grafana alert for certificates expiring within 30 days.
10. Specify OpenADR 2.0 (North America) or USEF (Europe) as the demand response protocol in Step 9, or build an adapter interface with two concrete implementations. The current 'utility signal (0-1 scale)' is a placeholder, not an integration specification.
11. Add an HSM requirement for OTA signing key in Step 17: use AWS CloudHSM or HashiCorp Vault with HSM backend for Ed25519 key storage. CI pipeline requests a signature from the HSM API; the private key never leaves the HSM.
12. Define OCPP Security Profile target explicitly in Step 7: Profile 1 (HTTP Basic Auth), Profile 2 (TLS + Client Certificate), or Profile 3 (Profile 2 + signed OCPP messages). Profile 3 is required for the threat model in Step 3 to be coherent.

### Missing Elements

1. Charge point provisioning and onboarding workflow: how a new physical EVSE is registered (certificate issuance, initial config push, network activation). This is a Day-2 operational gap that will block go-live.
2. GDPR Data Protection Impact Assessment (DPIA) and privacy-by-design decisions for driver data (location, SoC, payment history).
3. OpenADR 2.0 or USEF protocol specification for demand response integration (Step 9 references 'utility signal' without a wire protocol).
4. OCPP Security Profile selection and implementation specification.
5. Infeasibility handling in the fleet LP optimizer: what happens when the energy window cannot satisfy all SoC targets? The optimizer must produce a ranked partial solution, not crash or return an empty schedule.
6. Multi-region / multi-currency pricing architecture: ENTSO-E lock-in means the pricing engine has no defined path to non-EU markets.
7. Charge-point firmware version management: tracking deployed firmware versions across the fleet, rollout targeting (% of fleet, specific sites), and emergency rollback procedure at fleet scale.
8. Redis failure handling: if Redis pub/sub fails, charge point online/offline state cannot be published. The plan has no Redis sentinel, cluster, or fallback for this critical real-time path.
9. Billing dispute and chargeback handling workflow: not covered by payment service spec or compliance step.
10. ISO 14117 / IEC 62196 connector type support matrix: which connector types (CCS1, CCS2, CHAdeMO, Type 2, NACS) are supported and how connector type negotiation is handled in the OCPP session.
11. Rate limiting and DDoS protection for the OCPP WebSocket endpoint: charge points on cellular connections often share IP ranges; naive IP-based rate limiting will block legitimate CPs during carrier NAT events.

### Security Risks

1. OTA signing key in CI secrets: a compromised GitHub Actions workflow can exfiltrate the Ed25519 private key, enabling malicious firmware distribution to all deployed charge points — a potentially safety-critical attack vector for hardware controlling electrical contactors.
2. OCPP WebSocket endpoint DoS: the CPMS WebSocket server is internet-exposed (charge points on cellular). No WebSocket upgrade rate limiting or connection-level authentication timeout is specified. An attacker can exhaust file descriptors with unauthenticated WebSocket connections before TLS handshake.
3. Redis as a trust boundary: charge point online/offline state is published to Redis pub/sub. If an attacker gains Redis access (no AUTH or ACL specified in the plan), they can spoof charge point status, causing operators to dispatch maintenance to functional chargers or miss actual faults.
4. Fleet API key with no expiry or rotation policy: fleet integrations use static API keys. A leaked key grants full fleet account access (vehicle SoC, schedules, invoices) with no time-bound revocation.
5. OCPP message injection via WebSocket: if Security Profile 1 (HTTP Basic Auth, no message signing) is used, a man-in-the-middle who breaks TLS (e.g., via a compromised intermediate CA) can inject RemoteStartTransaction or ChangeAvailability messages, enabling unauthorized charging or taking chargers offline.
6. TimescaleDB audit log integrity: Step 4 requires append-only audit log with RLS preventing updates/deletes. PostgreSQL RLS can be bypassed by a superuser or the application's own DB role if not specifically restricted. No specification for a separate audit DB user with INSERT-only grants or external immutable log sink (e.g., CloudTrail, WORM storage).
7. Stripe webhook endpoint authentication gap: Step 11 specifies webhook receiver but does not explicitly call out Stripe webhook signature verification (Stripe-Signature header HMAC validation). Without this, any party can POST to the webhook endpoint and trigger payment confirmation events.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.316188
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
