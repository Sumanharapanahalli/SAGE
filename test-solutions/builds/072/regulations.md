# Regulatory Compliance — Ai Tutor

**Domain:** edtech
**Solution ID:** 072
**Generated:** 2026-03-22T11:53:39.328519
**HITL Level:** standard

---

## 1. Applicable Standards

- **FERPA**
- **COPPA**
- **GDPR**
- **WCAG 2.1**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | COMPLIANCE | Produce COPPA compliance plan (verifiable parental consent, data minimization, p | Standards mapping, DHF, traceability |
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy (COPPA-compliant with plain-language chil | Privacy, licensing, contracts |
| Step 7 | SECURITY | Produce STRIDE threat model for ai_tutor, define authentication strategy (JWT pl | Threat modeling, penetration testing |
| Step 19 | QA | Design comprehensive QA test plan covering functional, regression, performance,  | Verification & validation |
| Step 20 | SYSTEM_TEST | Execute system-level integration testing: 20-student adaptive learning simulatio | End-to-end validation, performance |
| Step 21 | COMPLIANCE | Produce final COPPA evidence package (consent audit trail, data inventory, delet | Standards mapping, DHF, traceability |
| Step 26 | EMBEDDED_TEST | Write firmware unit tests (Unity framework) and HIL test specification for ai_tu | Hardware-in-the-loop verification |

**Total tasks:** 28 | **Compliance tasks:** 7 | **Coverage:** 25%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FERPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | COPPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| data_scientist | 2 | Analysis |
| devops_engineer | 2 | Engineering |
| business_analyst | 1 | Analysis |
| product_manager | 1 | Design |
| marketing_strategist | 1 | Operations |
| ux_designer | 1 | Design |
| legal_advisor | 1 | Compliance |
| system_tester | 1 | Engineering |
| localization_engineer | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is an extraordinarily ambitious plan that conflates an AI tutoring SaaS, a regulated children's data platform, and a custom hardware device into a single build. The planning discipline is high — dependency ordering is mostly correct, acceptance criteria are specific, and compliance awareness (COPPA/FERPA) is present from the start. However, the plan has several category-level failures that block production readiness. The most critical: there is no curriculum content step, meaning the Socratic tutor and adaptive model have nothing to teach; the ML model trains on synthetic data that cannot produce valid IRT calibration; legal documents are AI-drafted with no attorney review for a product handling children's PII; and a penetration test plan exists without execution. The hardware track (steps 23-25) has its dependency ordering inverted and adds scope that has no place in a software product MVP. For an MVP of just the web-based tutoring product (steps 1-22 minus hardware), removing the synthetic-only ML training path and adding the five missing infrastructure pieces (email, billing, CDN, content authoring, external legal review), this plan could reach 68-72. As written, targeting a production launch with children's data and regulatory exposure, it scores 54 — too many fundamental gaps to ship safely.

### Flaws Identified

1. Hardware simulation (step 24) depends on firmware (step 23), but this is backwards — you simulate the SoC model first and develop firmware against it. Writing firmware before the SystemC model means the simulation validates nothing; it just mirrors assumptions already baked into the firmware.
2. ML model (step 10) trains on 'synthetic_500k_student_interactions' — synthetic data cannot produce a valid IRT calibration. IRT discrimination and difficulty parameters require real item response distributions. A DKT trained on synthetic data will exhibit severe distribution shift on real students. AUC >= 0.82 on a synthetic test split is a meaningless benchmark.
3. Step 13 acceptance criteria grades Socratic question quality via content_critic agent ('scored >= 4/5 by content_critic on 20 benchmark cases') — this is circular AI-grading-AI validation with no human expert review. A language model scoring another language model's pedagogical quality does not constitute educational validation.
4. No curriculum content strategy exists anywhere in 28 steps. Step 9 seeds '20 curriculum nodes per subject' but no step specifies who authors the educational content, how it is reviewed for accuracy, or how it is maintained. The Socratic tutor (step 13) cannot function without high-quality knowledge graph content.
5. COPPA and FERPA legal documents in step 6 are drafted by an 'agent_role: legal_advisor' — AI-generated legal documents for a platform collecting data from children under 13 are not legally defensible. No external attorney review step exists. FTC enforcement actions against COPPA violators have resulted in multi-million dollar fines.
6. Step 7 produces a penetration test plan but no step executes it. For a regulated platform handling child PII, a plan with no execution is compliance theater. The actual pentest must be conducted by qualified third parties before launch.
7. Performance targets are internally inconsistent: step 14 requires p95 <= 200ms under 100 concurrent users; step 20 requires p99 <= 500ms at 500 concurrent users. These are different percentiles at different load levels. The load test does not validate the development acceptance criterion.
8. No payment processing implementation step exists despite step 1 defining B2C and B2B2C pricing tiers and step 6 including a DPA for the payment processor. A subscription product with no billing implementation is unlaunchable.
9. No email infrastructure step. COPPA verifiable parental consent requires email-plus-callback (step 5 specifies this). No SES/SendGrid/Postmark configuration step exists. The parental consent flow in step 14 cannot function without a deployed transactional email service.
10. Step 22 localization accepts 'RTL layout scaffolded and layout does not break at 0% translation coverage for Arabic locale' — this criterion validates nothing. 0% translation coverage is not a shipped locale. This defers real RTL work while claiming it as done.
11. No CDN or media/asset storage step. An educational platform for K-12 with images, diagrams, math notation rendering, and potentially audio requires object storage and CDN configuration. This is absent from both step 17 (infra) and all frontend steps.
12. Step 9 states 'Alembic migrations run idempotently on clean and existing databases' — Alembic migrations are sequential, not idempotent by design. Adding a non-null column without a server default will fail on existing populated databases. This acceptance criterion will fail in staging the first time a data migration is attempted.
13. No database high-availability configuration. Step 17 defines K8s with HPA but no PostgreSQL primary-replica failover, no backup schedule, no point-in-time recovery. A single PostgreSQL instance holding student PII and FERPA audit records has no DR posture.
14. Step 28 defines a DKT accuracy drift alert but no remediation path. When the alert fires (AUC degrades 5%), there is no retraining pipeline, no model versioning, no rollback procedure. The alert tells you the model is broken with no plan to fix it.
15. No GDPR step. The DPA template in step 6 is described as 'GDPR and CCPA compatible' but GDPR compliance for EU students is never explicitly addressed. If the product launches to any EU users, data residency, lawful basis for processing minors' data, and DPO designation are all required.

### Suggestions

1. Swap steps 23 and 24: design and validate the SystemC SoC simulation first, then develop firmware against the validated hardware model. This is standard embedded development practice.
2. Replace synthetic DKT training with a hybrid approach: use a pre-trained open educational DKT checkpoint (e.g., from ASSISTments dataset) as baseline, then plan online learning updates from real user interactions post-launch. Document this limitation explicitly in the model card.
3. Add a step between steps 9 and 10: 'CONTENT_CREATION — curriculum authors (SMEs) produce and review knowledge graph content for 3 subjects, minimum 50 nodes each, validated by a licensed educator.' The ML model and Socratic agent depend on this.
4. Add a step for external legal review: 'LEGAL_REVIEW — licensed COPPA/FERPA attorney reviews privacy policy, ToS, and parental consent flow before launch.' This should gate step 21 (compliance evidence package).
5. Add an actual pentest execution step after step 20: 'PENTEST_EXECUTION — third-party security firm conducts black-box pen test against staging environment, OWASP Top 10 + OWASP LLM Top 10, results remediated before prod deploy.'
6. Add a step for payment implementation: 'BILLING — Stripe subscription integration, B2C and B2B2C pricing tiers, invoice generation, school district PO flow, refund handling.'
7. Add email infrastructure to step 17 or as a separate step: configure transactional email service (SES + custom domain), DKIM/SPF/DMARC, unsubscribe compliance, and delivery monitoring.
8. Replace content_critic AI grading of Socratic quality with a human educator review panel: define a rubric validated by a credentialed educator, have 3 reviewers score 50 benchmark cases, establish inter-rater reliability before using the AI critic as a proxy.
9. Unify latency targets: pick one percentile (p99) and one load level (500 CU) and ensure step 14 acceptance criteria reference the same SLA as step 20 load test.
10. Add PostgreSQL HA to step 17: Patroni or RDS Multi-AZ, automated backups with tested restore, and a documented RTO/RPO target.
11. Step 10 should include a production feedback loop design: how does new student interaction data get incorporated into model updates? Define retraining cadence, shadow mode evaluation, and rollback criteria before deployment.
12. Add GDPR as an explicit compliance scope in step 5, with data residency decision (EU region or adequacy decision), lawful basis for processing, and DPO designation if required by volume.

### Missing Elements

1. Curriculum content authoring and SME review — no human educator creates or validates the educational content that the entire product depends on
2. Payment/billing implementation — no Stripe or equivalent integration despite pricing tiers in the PRD
3. Transactional email infrastructure — required for COPPA parental consent but absent from all steps
4. CDN and object storage — required for images, math notation, audio, and diagrams in educational content
5. External attorney review of COPPA/FERPA legal documents — AI-drafted compliance docs for children's data are not legally defensible
6. Actual penetration test execution — a pentest plan with no execution provides no security assurance
7. Model retraining pipeline — the adaptive ML model has no mechanism for improvement post-deployment despite drift alerting in step 28
8. GDPR compliance — EU student data processing, lawful basis, data residency, DPO designation
9. Database disaster recovery — backup schedule, point-in-time recovery, failover testing
10. Pedagogical validation by credentialed educators — no learning scientist reviews the Socratic approach, turn limits, or mastery thresholds
11. IRB or equivalent ethical review for collecting behavioral data from minors
12. School SSO integration (SAML/OIDC with district IdP) — mentioned in v2 features but required for B2B2C school deals at any meaningful scale
13. Content moderation for student-generated text — the Socratic chat receives free-form student input that needs moderation beyond prompt injection detection

### Security Risks

1. AI-generated COPPA legal documents: if the parental consent mechanism or privacy policy has gaps, FTC enforcement exposure is direct. Children's data requires verified legal review, not LLM drafting.
2. Prompt injection via student input (step 13) relies on 'prompt_injection_guard' defined in YAML config with no implementation step. Guard effectiveness is untested against real adversarial inputs from school-age children who have demonstrated creativity in jailbreaking educational AI tools.
3. Guardian-child relationship enforced 'at middleware layer' (step 14) — if this enforcement is in middleware and not also enforced at the database query level with row-level security, a middleware bypass or query parameter injection could expose cross-family data. Defense-in-depth requires both layers.
4. JWT token handling for parental consent tokens (step 7) — no token revocation mechanism specified. If a parent's email is compromised after consent is granted, there is no path to invalidate the consent token short of account deletion.
5. ML inference service exposed as REST API (step 10) — if the inference endpoint is reachable without authentication, an attacker can probe the adaptive model to enumerate student mastery states or manipulate difficulty calibration by poisoning the inference inputs. No auth requirement on the ML service endpoint is specified.
6. Step 17 NetworkPolicy 'prevents ML inference service from initiating external internet connections' but does not address inbound — the ML service must not be directly reachable from the internet. The policy direction (egress-only) is insufficient; ingress restriction from outside the cluster is also required.
7. FERPA audit_events append-only enforcement relies on 'UPDATE and DELETE privileges revoked at DB level' (step 9) — this is bypassed by a superuser or DBA with ALTER TABLE privileges. True append-only compliance requires immutable storage (WAL-based or external audit log service) that survives even a superuser compromise.
8. No secret rotation plan — step 17 requires secrets injected via K8s Secrets or Vault, but no rotation schedule or automated rotation mechanism is defined. Static LLM API keys, database passwords, and JWT signing keys that never rotate are a long-term compromise vector.
9. Hardware companion device (steps 23-25) has no secure boot, firmware signing, or OTA update authentication specified. An unsigned firmware OTA on a children's device is a critical supply chain attack vector.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.328555
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
