# Regulatory Compliance — Identity Platform

**Domain:** enterprise
**Solution ID:** 091
**Generated:** 2026-03-22T11:53:39.335531
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**
- **NIST 800-63**
- **GDPR**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft terms of service, privacy policy, data processing agreements (DPA), and IP | Privacy, licensing, contracts |
| Step 4 | SECURITY | Perform threat modeling (STRIDE), produce a threat model document, define securi | Threat modeling, penetration testing |
| Step 21 | QA | Produce a QA test plan, test case library, and execution report covering functio | Verification & validation |
| Step 22 | SYSTEM_TEST | Execute end-to-end system integration tests: SSO federation with 3 test SPs (Okt | End-to-end validation, performance |
| Step 23 | COMPLIANCE | Produce compliance evidence artifacts for ISO 27001 and SOC 2 Type II: control m | Standards mapping, DHF, traceability |

**Total tasks:** 28 | **Compliance tasks:** 5 | **Coverage:** 18%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | NIST 800-63 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 4 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |

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
| developer | 13 | Engineering |
| devops_engineer | 3 | Engineering |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| safety_engineer | 1 | Compliance |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| regulatory_specialist | 1 | Compliance |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 62/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally sound IAM plan with impressive breadth — 28 steps, correct dependency ordering, appropriate technology choices, and genuine security-first thinking (STRIDE, SBOM, hash chain audit log, PKCE). However, it has three architectural defects that will hit production and cannot be patched post-launch: (1) the GDPR erasure vs. immutable audit chain conflict is a fundamental design contradiction requiring pseudonymization to be designed in from the database schema, not bolted on later; (2) the 99.99% SLA target is physically unachievable with active-passive failover and will become an SLA breach liability on the first major incident; (3) IdP-initiated SAML SSO and the absence of XSW attack mitigations represent critical authentication bypass risks in what is explicitly an identity security product. The plan also underspecifies operational concerns that will create SOC 2 audit failures: no access certification workflow, no key rotation procedure, no SCIM client credential lifecycle, and no LDAP bridge for the brownfield enterprise market this product targets. For an MVP targeting internal proof-of-concept with no compliance certification, score would be ~72. For the stated goal of production enterprise IAM with ISO 27001 and SOC 2 evidence collection, this requires resolving the three architectural conflicts and filling the seven missing controls before a production commitment.

### Flaws Identified

1. GDPR right-to-erasure vs. immutable audit hash chain is an irreconcilable architectural conflict. Step 14 builds a SHA-256-chained immutable log; GDPR Article 17 requires deleting personal data on request. Erasing a record breaks the chain. No pseudonymization or selective-erasure strategy is defined anywhere in the plan.
2. Step 24 claims RPO=0 with PostgreSQL streaming replication. Async replication has inherent lag. True RPO=0 requires synchronous_commit=remote_write or 'on', which adds measurable write latency to every auth transaction. This tradeoff is never acknowledged or benchmarked.
3. Step 26 targets 99.99% availability (~52 min/year downtime) with active-passive multi-region and RTO<30s. Active-passive cannot hit 99.99% — a 30s failover alone consumes 60% of the annual budget in a single incident. Active-active with anycast DNS is required for that SLA, and it is absent from the infra design.
4. SAML IdP-initiated SSO (step 10) is explicitly included with no CSRF mitigation specified. This is a known critical attack vector (SAML Bearer Subject Confirmation bypasses RelayState binding). Including it without mandatory InResponseTo validation or deprecation guidance is a production security defect.
5. Session invalidation cascade on SCIM de-provisioning is never addressed. When Azure AD pushes a SCIM DELETE for a user (step 13), there is no explicit step that revokes active OIDC tokens, SAML sessions, and Redis session entries. The user is 'deleted' but can continue authenticating until token TTL expires.
6. Step 12 targets OPA sidecar p95 policy evaluation < 5ms. OPA over network sidecar introduces 1–3ms baseline per call. Under contention (SCIM bulk import triggering thousands of RBAC checks simultaneously), p95 routinely exceeds this. No benchmarking baseline or fallback (embedded OPA via go-rego) is specified.
7. Audit hash chain at enterprise event volume (step 14) is a sequential write bottleneck. A single hash chain across all event types means every high-frequency auth event (10k concurrent sessions from step 22) must write serially or the chain breaks. No sharding strategy, per-tenant sub-chains, or append-only log design is specified.
8. OAuth 2.0 token revocation (RFC 7009) is absent from both the API spec (step 6) and backend implementation (step 9). Token introspection is included, but without a POST /oauth2/revoke endpoint, clients cannot force-invalidate compromised access tokens — a compliance requirement under SOC 2 CC6.1.
9. SCIM bearer token provisioning model is undefined. Step 13 builds the SCIM server but no step defines how Okta/Azure AD/Google Workspace clients authenticate to it. SCIM clients use long-lived bearer tokens — their issuance, rotation, and scoping is never addressed, leaving a credential management gap.
10. Step 10 specifies AES-256-CBC for SAML encrypted assertions. AES-CBC is vulnerable to padding oracle attacks and is deprecated in the 2023 SAML V2.0 Security Considerations errata. AES-128-GCM key transport is the correct choice. Using a known-weak cipher in an identity system for regulated enterprise customers is unacceptable.

### Suggestions

1. Add a dedicated 'PII pseudonymization strategy' design step between steps 7 and 8. Define how audit events store user references (opaque IDs, not raw PII), and document the erasure procedure: delete the identity record, and the audit log retains the opaque ID — chain intact, PII gone.
2. Replace the RPO=0 claim in step 24 with an explicit synchronous replication policy decision: document the write latency penalty of synchronous_commit=on (~5-10ms per transaction on cross-AZ replication) and let the business decide RPO=0 vs. sub-second RPO.
3. Downgrade the SLA to 99.95% (~4.4 hours/year) to match active-passive architecture capabilities, or replace the infra design in step 24 with active-active multi-region using read replicas and a distributed session layer.
4. Add XML Signature Wrapping (XSW) attack vectors explicitly to the threat model in step 4, and require the SAML implementation (step 10) to use a library with proven XSW defenses (python3-saml's strict mode, not pysaml2 without hardened config). Add a dedicated XSW regression test in step 20.
5. Add step 13.1: 'SCIM de-provisioning event bus'. When SCIM DELETE fires, publish to an internal event (Redis pub/sub or Postgres LISTEN/NOTIFY) consumed by the auth service to invalidate all active sessions and tokens for that user_id synchronously.
6. Replace OPA network sidecar with embedded OPA (via python-rego or direct WASM evaluation) in the auth-service hot path. Reserve the sidecar for admin/policy management APIs only. This eliminates the network round-trip and makes 5ms p95 achievable.
7. Redesign the audit hash chain in step 14 to use per-tenant append-only chains with periodic anchor checkpointing (e.g., hourly Merkle root stored in a separate tamper-evident table). This enables parallel writes per tenant while maintaining verifiability.
8. Add a step between steps 8 and 9 for SCIM client credential management: define a /scim/credentials API for provisioning SCIM bearer tokens with scoped permissions, expiry, and rotation workflow. Wire rotation alerts into step 25's alerting rules.
9. Change SAML encrypted assertion cipher in step 10 to AES-128-GCM with RSA-OAEP key transport. Update the acceptance criteria to require validation against the OASIS SAML V2.0 Errata 05 (2023) security profile.
10. Add a credential compromise detection step (between steps 11 and 12): integrate k-anonymity HaveIBeenPwned API for password-based auth and define the alert-and-force-reenroll workflow for compromised credentials surfaced post-deployment.

### Missing Elements

1. Account lockout and credential stuffing protection: no step defines lockout thresholds, CAPTCHA triggers, or IP-based rate limiting at the auth endpoint layer. OWASP ZAP in step 21 will find this gap but there is no implementation step to close it.
2. JWT algorithm confusion attack mitigation: no acceptance criterion in step 9 requires explicit algorithm pinning ('alg' header validation, rejection of 'none', prevention of RS256→HS256 downgrade). This is a P0 security control for any OIDC implementation.
3. Access certification / periodic access review workflow: step 16's coordinator agent mentions 'access review' as a use case, but no backend step implements the workflow (review campaign creation, reviewer assignment, approve/revoke decisions, audit trail). This is a core SOC 2 CC6.3 control.
4. LDAP/Active Directory bridge or directory sync connector: absent from all 28 steps. The majority of enterprise customers run on-prem AD. Without an LDAP connector or AD FS federation, the 'enterprise IAM' claim is significantly weakened for brownfield deployments.
5. Password policy engine: no step defines password complexity rules, breach password rejection, or history enforcement for password-based auth flows. NIST SP 800-63B compliance requires breach corpus checking.
6. Key rotation and JWK rollover procedure: step 9 creates RS256 signing keys but no operational procedure exists for zero-downtime key rotation. Enterprises require documented key lifecycle management for SOC 2 audit evidence.
7. Key generation ceremony documentation for ISO 27001: Annex A control A.10.1.2 (key management) requires documented key generation procedures, often with witnesses. Not present anywhere in the 28 steps.
8. Disaster recovery drill step: step 24 configures HA but no step validates the failover actually works end-to-end (DB failover, Redis failover, DNS TTL propagation, session continuity). A chaos engineering or DR drill step is absent.
9. PKCE state parameter and nonce validation specification: step 9 implements PKCE but no acceptance criterion explicitly requires state parameter CSRF protection or nonce replay prevention in the OIDC flow.
10. Rate limiting and DDoS protection at the API gateway layer: no WAF, request rate limiting (per-IP, per-client-id), or abuse detection is specified in any step. The auth endpoints are the highest-value targets in the system.

### Security Risks

1. XML Signature Wrapping (XSW): if pysaml2 is chosen without explicit strict-mode configuration, it is vulnerable to XSW attacks that allow an attacker to authenticate as any user by wrapping a valid signature around a forged assertion. Not in the threat model despite SAML being in scope.
2. IdP-initiated SSO CSRF: step 10 includes IdP-initiated SSO with no RelayState CSRF token requirement or InResponseTo binding enforcement. An attacker can craft a SAML response that authenticates a victim to a malicious SP session.
3. Refresh token family race condition: step 9 specifies 'family invalidation on reuse detection' but the implementation of a concurrent reuse window (two requests arrive within milliseconds of each other — one legitimate, one replayed) can cause false positives that lock out legitimate users or false negatives that allow attacker access.
4. SCIM injection: step 13 lists 'SCIM injection' as a focus area in the threat model (step 4) but no acceptance criterion in step 13 requires parameterized filter query parsing. SCIM filter expressions (RFC 7644 Section 3.4.2) parsed with string interpolation are injectable.
5. Audit log GDPR conflict enables compliance choice: the immutable hash chain in step 14 creates an architecture where the team must choose between GDPR compliance (erasure) and audit integrity (immutability). Without a design decision on pseudonymization, this will be discovered during the first GDPR erasure request in production, requiring an emergency architectural change.
6. Redis session store single point of failure: step 9 stores sessions in Redis with 'configurable TTL'. If Redis Cluster is not configured (step 8 mentions Redis but not Redis Cluster), a Redis failure terminates all active user sessions simultaneously — an auth outage indistinguishable from a P1 incident.
7. JWT 'alg: none' and algorithm substitution: without explicit algorithm pinning in the token validation middleware, a compromised or malicious client can submit JWTs with 'alg: none' or switch from RS256 to HS256 using the public key as the HMAC secret. Neither python-jose nor authlib protect against this by default without explicit configuration.
8. Secrets in Docker Compose for development: step 8 uses .env.example for environment variables in Docker Compose. Developers routinely copy .env.example to .env and commit it. No pre-commit hook to block .env commits is in the acceptance criteria, creating a credential leak vector in the development phase that can persist to production.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.335569
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
