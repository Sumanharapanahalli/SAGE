# Regulatory Compliance — Workflow Automation

**Domain:** enterprise
**Solution ID:** 093
**Generated:** 2026-03-22T11:53:39.336180
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**
- **GDPR**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 4 | LEGAL | Draft Terms of Service, Privacy Policy, Data Processing Agreement (DPA), connect | Privacy, licensing, contracts |
| Step 5 | SECURITY | Produce threat model (STRIDE), define security architecture for credential vault | Threat modeling, penetration testing |
| Step 23 | COMPLIANCE | Produce ISO 27001 Statement of Applicability (SoA), SOC 2 Type II readiness asse | Standards mapping, DHF, traceability |
| Step 26 | QA | Design the master test plan: unit test strategy (≥ 80% coverage), integration te | Verification & validation |
| Step 28 | SYSTEM_TEST | Build end-to-end system test suite: 20 golden-path flow scenarios spanning multi | End-to-end validation, performance |

**Total tasks:** 32 | **Compliance tasks:** 5 | **Coverage:** 16%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
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
| developer | 15 | Engineering |
| devops_engineer | 3 | Engineering |
| regulatory_specialist | 2 | Compliance |
| qa_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| marketing_strategist | 1 | Operations |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |
| technical_writer | 1 | Operations |
| financial_analyst | 1 | Analysis |
| localization_engineer | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 58/100 (FAIL) — 1 iteration(s)

**Summary:** This plan demonstrates solid architectural instincts — PostgreSQL + RLS for multi-tenancy, envelope encryption for credentials, DAG-based execution, actor-critic AI assistant — but it fails on scope realism and several critical dependency ordering errors. The 200+ connector target is the plan's most dangerous fiction: real enterprise connectors (Salesforce, SAP, ServiceNow, Microsoft Graph) each represent weeks of engineering, not items in a batch task. The Celery-vs-Temporal non-decision creates a branching path through the most critical subsystem in the product. Three security gaps (SSRF, OAuth token concurrency, webhook replay) are production-blocking for enterprise buyers. The infra/CI-CD dependency inversion would cause a pipeline configuration sprint that has nowhere to deploy to. Stripped to a realistic MVP scope — flow builder, top-20 connectors, core execution engine, basic monitoring, single-region deployment — this is a 68-point plan. As written, presenting 200+ connectors, ISO 27001, SOC 2 Type II, and multi-region HA as a coherent deliverable sequence, it scores 58: the core is buildable, but the scope promises will cause the project to stall at Step 14 and never recover.

### Flaws Identified

1. Step 25 (Infra) depends on Step 24 (CI/CD) — this is backwards. You cannot run a CI/CD pipeline that deploys to infrastructure that doesn't exist yet. Terraform provisioning must precede pipeline construction, not follow it.
2. Step 28 (System Tests) lists depends_on [14,15,16,17,24] but omits Step 25 (Infra). System tests in staging require production-equivalent infrastructure to be provisioned first.
3. The Celery vs Temporal decision is punted with 'or' syntax in steps 10 and 17. These are architecturally incompatible execution models with different failure semantics, replay guarantees, and operational overhead. Leaving this unresolved creates a fork in the entire execution engine implementation.
4. Step 14's 200+ connector target is catastrophically underscoped as a single task. Salesforce alone requires navigating 4 OAuth flows, 2 API versions, governor limits, and a SOAP fallback. ServiceNow requires tenant-specific instance URLs. Microsoft Graph requires multi-tenant Azure app registration. Auto-scaffolding from OpenAPI specs covers maybe 30% of real connector complexity — the '80% boilerplate' claim is fiction for enterprise APIs.
5. Step 23 (Compliance — ISO 27001 SoA, SOC 2 readiness) depends only on Steps 5 and 7. It should depend on steps 10-21 since you cannot write an accurate Statement of Applicability for a system that hasn't been built yet. The SoA documents controls as-implemented, not as-designed.
6. No step for connector versioning or API change management. When Salesforce deprecates an API version or GitHub changes a webhook payload schema, every flow using that connector silently breaks. This is the #1 operational failure mode for platforms like this and it has zero coverage in the plan.
7. Billing infrastructure (Step 31) comes after system tests (Step 28). If metered billing is a product requirement — and it is, given the consumption-based tier — usage metering must be instrumented in the execution engine (Step 10) from day one. Retrofitting metering into a built execution engine is a significant rework.
8. The plan mentions on-premise deployment as a competitive differentiator (Step 3) but contains zero implementation steps for Helm charts, air-gapped Vault setup, or self-hosted connector registry. This is a promised feature with no delivery path.
9. React Flow 100-node canvas at <16ms frame time is achievable in isolation but the plan adds undo/redo (Zustand), auto-save every 30s, and real-time collaboration state. No performance budget is allocated for the combined load. React Flow has documented edge virtualization issues above ~150 nodes with complex edge routing.

### Suggestions

1. Resolve Celery vs Temporal before Step 9. Run a spike (2-3 days): implement a 3-step flow with error handling and replay in both, measure operational complexity. Temporal wins on durability guarantees; Celery wins on simplicity. Pick one and delete the other from the plan.
2. Split Step 14 into at minimum 5 sub-tasks with dedicated owners per API category. Assign a 'connector contract test harness' sub-task first — a standard test fixture that validates auth, pagination, rate limit handling, and error normalization for any connector. Build all 200+ against it, not after it.
3. Flip the dependency: Step 25 (Infra) should be Step 24, and current Step 24 (CI/CD pipelines) should be Step 25. Alternatively, split infra into 'minimal dev infra' (precedes CI/CD) and 'production infra' (follows CI/CD pipeline validation).
4. Add an explicit 'connector health monitoring' step: a background job that pings each connector's auth endpoint on a schedule, detects API schema drift by diffing against the stored JSON Schema, and alerts when a connector's error rate spikes. Without this, 200+ connectors become a silent maintenance liability.
5. Add execution payload encryption as a distinct database requirement. Credentials are encrypted (Step 7), but flow execution payloads can contain PII from connector responses (email bodies, CRM records, payment data). Column-level encryption or application-level encryption of step_outputs is required for GDPR Article 32 compliance.
6. Move billing metering instrumentation to Step 10 (execution engine). Add a 'emit metering event' call at execution completion. The Step 31 Stripe integration can come later, but the metering data must be captured from execution #1 or you have no historical billing data to reconstruct.
7. Add an SSRF protection layer to the HTTP/Webhook connector and any connector that accepts user-supplied URLs. Without it, any tenant can use the HTTP connector to probe your internal VPC: hitting Vault's API, the metadata endpoint (169.254.169.254), or internal Kubernetes service IPs.

### Missing Elements

1. Connector versioning strategy: how do you handle breaking changes in an upstream API without invalidating every flow that uses that connector? Semantic versioning for connectors + migration guide per breaking change is standard practice and entirely absent.
2. OAuth token refresh concurrency control: when 10 parallel flow executions hit a connector whose token has expired, all 10 will attempt a token refresh simultaneously, causing a thundering herd against the connector's token endpoint. A distributed lock per credential is required.
3. Data residency implementation step: GDPR and enterprise buyers require EU data to stay in EU. The plan mentions this in legal (Step 4) and infra (Step 25) but has no implementation step for geo-routing execution data, per-tenant region selection, or cross-region replication controls.
4. Webhook replay attack mitigation: Step 17 requires HMAC signature validation but does not require timestamp validation or nonce tracking. Without replay protection, an attacker who captures a valid signed webhook payload can trigger arbitrary flow executions indefinitely.
5. Database connection pooling (PgBouncer or pgpool): at 1000 concurrent executions (Step 28 load target), each with 3-5 DB operations, PostgreSQL will be saturated without a connection pooler. This is an infrastructure component missing from Step 25.
6. Flow import/export and portability: enterprise buyers require the ability to export flows as JSON/YAML for version control, disaster recovery, and environment promotion (staging → production). Absent from all 32 steps.
7. Connector SDK versioning and backward compatibility policy: third-party connector developers (Step 12) need a stable interface contract with a deprecation timeline. Without this, every framework change breaks third-party connectors.
8. Step-level timeout configuration: a connector that hangs indefinitely will block a Celery worker or Temporal workflow indefinitely. Per-step timeouts with configurable defaults are absent from the execution engine spec.
9. Multi-region active-active or active-passive topology decision: the infra step specifies multi-AZ (single region) but enterprise SLAs at 99.9%+ often require multi-region. This architectural decision affects database replication strategy, Vault HA topology, and Kubernetes federation — it must be decided before Step 25.

### Security Risks

1. SSRF via HTTP connector: no egress filtering mentioned anywhere. A malicious or misconfigured flow can use the HTTP connector to exfiltrate data from internal services, hit cloud metadata endpoints, or probe Vault's API. Mitigate with an egress proxy that blocks RFC 1918 addresses and cloud metadata IPs.
2. Expression injection via CEL: Step 11 mandates 'expression eval in isolated context' but CEL's Go implementation has had sandbox escapes, and the Python CEL implementations have varying security postures. If the sandboxing is implemented incorrectly, any flow builder can execute arbitrary code on the execution engine worker.
3. Connector OAuth token exfiltration: Vault stores tokens per-tenant, but the execution engine must decrypt them at runtime. If execution worker memory is dumped (OOM, core dump, debug endpoint), all in-flight OAuth tokens are exposed. Secure enclave or token proxy pattern is the mitigation.
4. Cross-tenant timing oracle via execution metrics: even with RLS, if the metrics endpoint exposes P95 latency by connector globally (not per-tenant), an attacker can infer what connectors other tenants are using and roughly when their flows execute.
5. Connector callback URL hijacking: OAuth flows require a redirect URI. If the callback URL validation is lenient (prefix match instead of exact match), an attacker can redirect another tenant's OAuth completion to their own endpoint and steal the authorization code.
6. Execution log data retention vs right-to-erasure conflict: execution logs contain step inputs/outputs which may include personal data. The 90-day default retention (Step 16) conflicts with GDPR Article 17 right-to-erasure requests, which must be honored within 30 days. No GDPR erasure implementation step exists.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.336213
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
