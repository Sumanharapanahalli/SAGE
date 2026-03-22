# Regulatory Compliance — Compliance Platform

**Domain:** enterprise
**Solution ID:** 095
**Generated:** 2026-03-22T11:53:39.336707
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**
- **GDPR**
- **NIST CSF**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (DPA) template | Privacy, licensing, contracts |
| Step 4 | COMPLIANCE | Build the canonical control framework library: normalize SOC 2 TSC criteria, ISO | Standards mapping, DHF, traceability |
| Step 11 | SECURITY | Conduct security review of compliance_platform: threat model (STRIDE), OWASP Top | Threat modeling, penetration testing |
| Step 13 | QA | Produce QA test plan for compliance_platform: test strategy, test case catalog f | Verification & validation |
| Step 14 | SYSTEM_TEST | Execute end-to-end system tests for compliance_platform: full SOC 2 assessment c | End-to-end validation, performance |

**Total tasks:** 18 | **Compliance tasks:** 5 | **Coverage:** 28%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | NIST CSF compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| qa_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| regulatory_specialist | 1 | Compliance |
| ux_designer | 1 | Design |
| safety_engineer | 1 | Compliance |
| system_tester | 1 | Engineering |
| devops_engineer | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 57/100 (FAIL) — 1 iteration(s)

**Summary:** This is a structurally coherent plan with good coverage of the GRC domain, a realistic DB schema, and appropriate multi-tenant architecture. The dependency graph is mostly logical, the acceptance criteria are measurable, and the HITL approval pattern is correctly applied to agent proposals. However, the plan has several production-blocking gaps that prevent a score above 60: security threat modeling occurring after full implementation is an architectural mistake for a security-focused product; GDPR compliance is contractual rather than implemented (no DSAR workflow, no functional erasure cascade); the SAGE/standalone app coupling is unresolved; concurrent editing has no conflict resolution design; and several integration stories (AV scanning, notification delivery, enterprise SSO, third-party integrations) are documented requirements with no implementation steps. The AI-generated legal documents without legal review is an unacceptable risk for a product sold to compliance teams. None of these are fatal to the architecture — all are fixable — but collectively they represent 3-4 additional sprints of work not accounted for in the current plan, and at least two (RLS+connection-pooling, concurrent editing) would cause production incidents if shipped as-is.

### Flaws Identified

1. Security threat modeling (Step 11) occurs AFTER full backend implementation (Step 8). For a platform that stores compliance evidence and risk data, threat modeling must precede API design, not follow it. STRIDE analysis will almost certainly surface design-level changes, forcing costly rework of already-implemented code.
2. Step 3 uses an AI agent to generate legally binding documents (ToS, DPA, Privacy Policy). The acceptance criteria has zero requirement for legal counsel review. Shipping an AI-generated DPA that claims Art. 28 GDPR compliance without lawyer sign-off is a liability landmine, especially for a platform sold to compliance teams.
3. Step 4 control library accuracy depends entirely on the regulatory_specialist agent output with no external validation mechanism. Incorrect SOC 2 ↔ ISO 27001 cross-walk mappings would give customers false compliance confidence — a critical failure mode for a GRC product. 'Validated against official standard text' by the same AI that generated it is circular.
4. PostgreSQL RLS implementation (Step 6) has well-known production gotchas that the plan ignores: SECURITY DEFINER functions bypass RLS entirely, superuser connections bypass RLS, and PgBouncer transaction pooling breaks SET LOCAL for RLS. No connection pooling strategy is specified anywhere in the plan.
5. Step 9 (Agentic) creates proposals that go to 'SAGE proposal store' but the compliance platform has its own FastAPI backend and DB. The coupling between the standalone GRC application and the SAGE framework's /approvals page is never resolved. Which UI does the auditor use to approve ControlGapAnalyst proposals — the compliance platform's UI or SAGE's?
6. No concurrent editing conflict resolution anywhere in the plan. Step 13 identifies 'two auditors editing the same finding concurrently' as an edge case to test — but neither the DB design (Step 6) nor the API spec (Step 7) nor the backend (Step 8) specifies optimistic locking, ETags, or any conflict resolution strategy. Testing a failure mode you haven't designed for is not a strategy.
7. Evidence file antivirus scanning is mentioned in Steps 7 and 11 as a 'hook' but no AV service is selected, integrated, or implemented. ClamAV, cloud AV APIs, and commercial solutions have wildly different latency/reliability profiles. 'Virus scan hook' appearing in an acceptance criteria without implementation is wishful thinking.
8. GDPR compliance is contractual, not implemented. Articles 33/34 (breach notification within 72 hours), Art. 17 (right to erasure with cascade delete), and Data Subject Access Request (DSAR) workflows have no implementation steps. Step 16's operational runbook mentions GDPR Art. 17 for tenant offboarding, but there is no backend service implementing it. Soft deletes (Step 6) actively conflict with GDPR erasure requirements.
9. No notification delivery mechanism implemented. Step 8 background jobs 'create notifications in DB' but there is no email service, in-app notification system, or webhook delivery specified. PBC request due date reminders that exist only in a database table are not reminders.
10. Report generation for PDF/XLSX (Steps 7, 10) has no library or service specified. Generating a SOC 2 Type II readiness report or ISO 27001 Statement of Applicability with correct formatting is not trivial. WeasyPrint, ReportLab, and Puppeteer have different tradeoffs for complex tables and charts. This is a known effort black hole.
11. Integration implementations are completely absent. Step 2 identifies AWS Security Hub, GCP SCC, Jira, ServiceNow, and GitHub as integration targets with an 'integration requirements matrix' deliverable. But there is no implementation step for any of these integrations. The matrix documents what should happen; nothing builds it.
12. Step 14 acceptance criteria includes 'Failover scenario tested' with no corresponding test scenario defined in the payload. This is a dead acceptance criterion — no scenario means no pass/fail definition.
13. The k6 load test (Step 14, 50 VUs, p95 < 2s) does not test the actual performance bottleneck: concurrent evidence file uploads to S3-compatible storage. API response time during file upload proxying or pre-signed URL generation under load is the relevant metric, not generic dashboard p95.

### Suggestions

1. Move threat modeling to before Step 5 (UX design), not after Step 8. At minimum, insert a lightweight STRIDE session between Steps 2 and 5 to catch design-level security issues before they are built. The full OWASP ASVS assessment can remain at Step 11.
2. Step 3 legal documents must have a 'reviewed by qualified legal counsel' acceptance criterion, or replace the AI-generated docs with attorney-reviewed templates that the agent only fills in. Selling a GRC platform to a CISO with an AI-hallucinated DPA is a deal-killer.
3. Add explicit DSAR and right-to-erasure endpoint implementations to Step 8. The DB schema needs hard-delete capability for GDPR Art. 17, not just soft-delete flags. Add a /gdpr/erasure endpoint that cascades properly and is tested.
4. Resolve the SAGE/standalone app coupling in Step 9 explicitly. Either: (a) the compliance platform implements its own approval queue UI and the SAGE proposal store is used only as a backend storage mechanism, or (b) specify that SAGE runs as a sidecar and the frontend routes to SAGE's /approvals page for agent proposals. Pick one and document it.
5. Add optimistic locking to the DB schema design (Step 6): version column on findings, pbc_requests, and risk_register_items. Add ETag/If-Match handling to the API spec (Step 7) for these resources. Test concurrent edit conflict in Step 14.
6. Select and implement an actual AV scanning service in Step 8, not a 'hook'. If ClamAV is the choice, specify the async scan pattern (upload to quarantine bucket → scan → move to permanent bucket on clean). If a cloud API, specify timeout/fallback behavior.
7. Add a Redis caching layer to Step 8 for the control coverage dashboard aggregation queries. A heat-map of 93 ISO controls × N assessments × M evidence items is expensive to recompute on every page load for multi-tenant deployments.
8. Add connection pooling specification to Step 6/8: PgBouncer in session mode (not transaction mode) is required for PostgreSQL RLS to work correctly. Document this as a hard infrastructure requirement.
9. Add a control library validation step with a human reviewer (regulatory specialist or external GRC consultant) before Step 8 seeds the data into production. The AI-generated cross-walk should be diff'd against at least one published SOC2↔ISO27001 mapping (AICPA publishes one).
10. Step 15 CI/CD pipeline should include the API spec contract test (Step 7 OpenAPI against Step 8 implementation) as a pipeline gate, not just lint/test/security scan.

### Missing Elements

1. DSAR (Data Subject Access Request) workflow — no implementation step exists for GDPR Art. 15/17/20 subject rights
2. Notification delivery service — email (SES/SendGrid/SMTP), in-app notification store, or webhook fan-out; none specified or implemented
3. Integration implementation steps — AWS Security Hub, GCP SCC, Jira, ServiceNow connectors are documented requirements (Step 2) with no corresponding build steps
4. SAML/OIDC SSO implementation — listed as integration target in Step 2, required by enterprise buyers, but no implementation step exists
5. Optimistic locking / concurrency control strategy for collaborative editing resources
6. Data residency enforcement at infrastructure level — GDPR requires EU data stays in EU regions; contractual clauses alone (Step 3) do not implement this
7. AV scanning service selection and async scan pipeline implementation
8. Report template system for standard GRC report formats (SOC 2 Type II narrative, ISO 27001 Statement of Applicability) — generic PDF export is not sufficient for auditor deliverables
9. Redis or equivalent caching layer for aggregation-heavy dashboard queries
10. JWT secret rotation runbook and process — secret compromise scenario has no response procedure
11. API rate limiting implementation in Step 8 — Step 11 flags it as a review area but it is never implemented
12. PgBouncer / connection pooling specification compatible with PostgreSQL RLS
13. Breach notification workflow implementation (GDPR Art. 33/34 — 72-hour notification window)

### Security Risks

1. Pre-signed S3 URLs (Step 8, 1-hour expiry) do not enforce tenant isolation at the storage layer. A leaked URL is accessible by anyone regardless of JWT. The acceptance criterion 'tenant-scoped prefixes' prevents path collision but does not prevent URL sharing between tenants. Bucket policies must restrict access by tenant prefix using IAM conditions, not just prefix naming.
2. PostgreSQL RLS bypass via SECURITY DEFINER functions: any stored procedure or trigger defined with SECURITY DEFINER runs as the function owner (typically a superuser-equivalent), bypassing all RLS policies silently. The audit_log trigger (Step 6) is likely SECURITY DEFINER — this means the audit trail writer itself can read across tenant boundaries.
3. Seed data injection risk: Step 8 seeds control library JSON from Step 4 'on first boot.' If the seed file path is configurable via environment variable or the file is fetched from an external URL, this is a remote code execution or data poisoning vector. Seed data must be bundled into the container image, not fetched at runtime.
4. JWT secret in environment variable (Step 18 .env.production) with ANTHROPIC_API_KEY and SLACK_BOT_TOKEN — if a single env file is compromised, all secrets are exposed simultaneously. Secrets should be in separate Vault paths with least-privilege access per service component.
5. Evidence file MIME type validation (Step 11) against an allowlist is necessary but insufficient. MIME type sniffing from Content-Type header is trivially spoofed. Validation must use magic byte inspection of the actual file content (e.g., python-magic), not the declared MIME type.
6. RBAC privilege escalation via tenant admin role: the schema includes a 'roles' table with CRUD endpoints (Step 7), meaning a tenant admin can create new roles. If role creation is not strictly scoped to predefined role templates, a tenant admin can construct a role with elevated permissions beyond their own, creating a privilege escalation path.
7. APScheduler (Step 8) running background jobs in the same process as the FastAPI web server creates a DoS risk: a runaway background job (e.g., large cross-tenant evidence expiry scan) can starve web worker threads. Background jobs should run in a separate worker process (Celery/ARQ) isolated from the request-handling process.
8. Control library accuracy as a false confidence risk: if the AI-generated SOC 2 ↔ ISO 27001 cross-walk contains errors (e.g., maps CC6.1 to a non-equivalent ISO control), a CISO using the platform may believe they are SOC 2 compliant when controls are actually unmapped. This is a liability risk unique to GRC products — incorrect mappings cause real audit failures.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.336740
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
