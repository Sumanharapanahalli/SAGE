# Regulatory Compliance — Coding Bootcamp

**Domain:** edtech
**Solution ID:** 073
**Generated:** 2026-03-22T11:53:39.328824
**HITL Level:** standard

---

## 1. Applicable Standards

- **FERPA**
- **SOC 2**
- **WCAG 2.1**

## 2. Domain Detection Results

- edtech (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 5 | COMPLIANCE | Produce compliance plan and evidence artifacts for COPPA (users under 13), FERPA | Standards mapping, DHF, traceability |
| Step 6 | LEGAL | Draft Terms of Service, Privacy Policy, Student Data Agreement, and Employer Par | Privacy, licensing, contracts |
| Step 12 | SECURITY | Produce threat model, security architecture review, and penetration test plan. C | Threat modeling, penetration testing |
| Step 28 | QA | Produce the master QA test plan, execute structured test cycles (functional, reg | Verification & validation |
| Step 29 | SYSTEM_TEST | Execute end-to-end system integration tests simulating full student and instruct | End-to-end validation, performance |
| Step 30 | COMPLIANCE | Produce final compliance evidence package: COPPA age-gate test evidence, FERPA d | Standards mapping, DHF, traceability |

**Total tasks:** 32 | **Compliance tasks:** 6 | **Coverage:** 19%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | FERPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | WCAG 2.1 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 14 | Engineering |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 3 | Engineering |
| ux_designer | 2 | Design |
| devops_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| business_analyst | 1 | Analysis |
| marketing_strategist | 1 | Operations |
| product_manager | 1 | Design |
| legal_advisor | 1 | Compliance |
| localization_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is an unusually thorough plan for a complex platform — 32 well-sequenced steps, specific acceptance criteria, real compliance coverage (COPPA/FERPA/WCAG), and a sensible technology stack. The dependency graph is mostly correct and the phased MVP → v1 → v2 roadmap is realistic. However, three critical gaps will cause production failures regardless of how well the rest is implemented: (1) the Docker-per-session IDE model will miss every latency target at scale without a pre-warming pool strategy; (2) WebSocket delivery of grading results will silently fail in any multi-replica Kubernetes deployment without a Redis pub/sub routing layer; and (3) the entire business model lacks a payment and cohort management system. Beyond these blockers, the code review bot has no LLM cost model (a financial risk, not just a technical one), the Rust language support is functionally broken due to the 30-second timeout, and the sandbox security hardening is incomplete for a platform where students are explicitly taught systems programming. The compliance coverage is above average but FERPA is applied only to placement data when it covers all educational records. Score of 63 reflects: strong architecture and process thinking, but three unacceptable gaps for an MVP that claims to handle student records and live code execution.

### Flaws Identified

1. Docker-per-session IDE model will NOT achieve 3-second cold-start at any meaningful scale. Docker image pull + container init for Python/Rust/Go runtimes averages 4-12 seconds on cold nodes. Step 29 demands 100 concurrent sessions with P99 < 5s — at 512MB each that's 50GB RAM minimum, plus EKS node autoscaling adds 2-3 minutes latency. No pre-warming pool, no warm container strategy, no image layer caching policy is specified anywhere.
2. Rust cargo build under a 30-second execution timeout (Step 14) will fail for any non-trivial project. Rust cold-compile times routinely exceed 60-120 seconds for projects with dependencies. This makes the Rust language support effectively useless for project-based curriculum.
3. WebSocket horizontal scaling is unaddressed. FastAPI on EKS with multiple replicas cannot route WebSocket messages to the correct pod without sticky sessions (ALB cookie) or a Redis pub/sub fanout layer. When grading engine webhooks arrive (Step 15), the API has no mechanism to locate and push to the correct client WebSocket. This is a silent failure mode — grading results simply never reach students on multi-replica deployments.
4. Missing payment and enrollment billing system entirely. A coding bootcamp charges tuition — $5k-$15k+ in market. There is no Stripe integration, no payment plan support, no refund workflow, no revenue recognition, and no enrollment gate tied to payment status. This is not a nice-to-have; it is the business.
5. Cohort management is absent. Bootcamps operate in cohorts with fixed start dates, synchronized curriculum pacing, instructor assignment per cohort, and cohort-level graduation tracking. The schema (Step 8) has no cohort entity. The analytics in Step 18 reference 'placement_rate_by_cohort' without a mechanism to define or track cohorts.
6. Step 16 (Code Review Bot) specifies an agentic pattern with generator + critic agent but names zero LLM providers, no cost model, and no rate limiting. At scale — say, 500 students submitting daily — 3 critic iterations per review at GPT-4-class pricing exceeds $10k/month easily. There is no per-student quota, no cost circuit breaker, and no fallback when LLM is unavailable.
7. FERPA compliance is applied inconsistently. Steps 18 and 22 treat FERPA as scoped to placement data only. FERPA covers ALL educational records: grades (Step 15), code reviews (Step 16), submission history (Step 17), instructor notes — every record in the system. The RBAC model doesn't specify which instructor roles have 'legitimate educational interest' exceptions, which is the FERPA mechanism for intra-institutional access.
8. GDPR vs FERPA right-to-erasure conflict is unresolved. GDPR Article 17 requires data deletion on request. FERPA requires educational institutions to retain records for defined periods and restricts arbitrary deletion. Students in EU jurisdictions will trigger both. Step 6 acknowledges both regulations but no conflict resolution strategy or jurisdiction detection is specified.
9. Step 14 sandboxes specify '--network none enforced' but omit critical Linux security controls: --no-new-privileges, --cap-drop ALL, a custom seccomp profile, and AppArmor/SELinux policy. A determined student with 30 seconds of execution time and no capability restrictions has multiple kernel syscall attack surfaces. For a platform explicitly teaching systems programming (Rust, Go), this is a serious gap.
10. Step 17 'git-backed curriculum versions' is architecturally ambiguous. If this means storing actual git repos in the backend, it requires libgit2/pygit2, a separate git storage layer, and conflict resolution for concurrent instructor edits. If it means recording version snapshots in PostgreSQL, 'git-backed' is a misnomer. Either way, the implementation is underspecified and the dependency from Step 17 on Step 13 (basic auth/CRUD) is insufficient — curriculum versioning needs its own design step.
11. Monaco Editor IntelliSense (Step 20) requires language servers (LSP). For Python, this means running Pyright or Pylsp as a WebSocket-accessible backend service. For Rust, rust-analyzer. For Go, gopls. These are non-trivial backend services with their own resource profiles, not a frontend concern. None of these are in the infra plan, the backend steps, or the dependency graph. 'intellisense_basic' is not implementable without them.
12. Step 25 CI pipeline 'completes in under 10 minutes' is not achievable with the defined test suite. testcontainers spin-up alone adds 2-3 minutes. 85% backend coverage + contract tests + Playwright E2E on 3 browsers (Chromium, Firefox, WebKit) on 6 critical flows is realistically 25-45 minutes. Accepting a 10-minute constraint will force teams to skip tests or split CI arbitrarily.
13. Step 18 analytics (placement_rate, median_salary, time_to_hire) run as aggregation queries on the same PostgreSQL RDS instance serving OLTP traffic. No read replica, no materialized views, no ETL pipeline. At bootcamp scale these queries will table-scan millions of rows during peak enrollment periods and degrade API response times.
14. Step 14 accepts 'WebSocket reconnection restores session state within 5 seconds' but the session state lives in an ephemeral container. On reconnect, a NEW container must be started (another 3+ seconds), and the prior container's filesystem is destroyed per spec. There is no session state serialization or checkpoint mechanism defined. This acceptance criterion is contradictory to the filesystem destruction policy.

### Suggestions

1. Replace Docker-per-session with a pre-warmed container pool. Maintain N idle containers per language runtime, assign on session creation (sub-100ms), recycle on session end. Pool size tuned to concurrent user P95. This is how Replit and similar platforms achieve fast session starts.
2. Add a Redis-backed WebSocket session registry. Each WebSocket connection registers its pod IP + session ID in Redis on connect. When grading webhooks arrive, the API looks up the target pod and routes via internal HTTP or uses Redis pub/sub. This solves the multi-replica delivery problem completely.
3. Insert a Step 0 or pre-step for payment/billing: Stripe integration, enrollment flow, payment plan support, and subscription state tied to course access. This gates everything else.
4. Add a 'cohorts' entity to the database schema (Step 8) with start_date, end_date, instructor_assignment, and enrollment cap. Cascade cohort_id into submissions, grades, and placement records from the start.
5. Define an LLM cost budget and rate limiting policy in Step 16. Specify: max LLM calls per submission, daily per-student quota, monthly hard cap with alerting at 80%, and a fallback mode (linting-only review) when LLM is rate-limited or budget-exceeded.
6. Separate the 'FERPA legitimate educational interest' access model into a dedicated RBAC layer. Define exactly which roles can access which student records, log every access with purpose field, and enforce via middleware — not just application logic.
7. Add a GDPR-FERPA conflict resolution policy document to Step 6 legal artifacts. Minimally: jurisdiction detection by IP/signup country, different consent flows for EU vs US students, and a 'retention hold' mechanism that blocks erasure when FERPA retention applies.
8. Harden Step 14 sandboxes with explicit seccomp profile (deny all syscalls except approved list), --cap-drop ALL, --security-opt no-new-privileges, and consider gVisor (runsc) as the container runtime for defense-in-depth against kernel exploits.
9. Add language server services (Pyright, rust-analyzer, gopls) as dedicated backend microservices in the infra plan (Step 11) and API design (Step 9). These need resource limits, health checks, and connection pooling to the Monaco frontend.
10. Extend the Rust language timeout to at minimum 120 seconds for compilation, or separate 'build' from 'run' as distinct operations with independent timeouts. Document expected build times per language in the acceptance criteria.
11. Add a materialized view or nightly ETL job for placement analytics. Query the OLTP database for operational reports; query the materialized/analytical layer for aggregate dashboards. Add a read replica to the RDS configuration in Step 11.
12. Define session state serialization for IDE reconnection: checkpoint the container filesystem (tar snapshot to S3) on disconnect, restore on reconnect within a TTL window (e.g., 30 minutes). Amend the filesystem destruction policy to: 'destroyed after TTL or explicit session end, whichever comes first.'

### Missing Elements

1. Payment and billing system: Stripe/payment processor integration, tuition collection, enrollment gate, refund workflow, revenue reconciliation
2. Cohort management entity and lifecycle: cohort creation, enrollment cap, pacing calendar, graduation criteria
3. Email notification system: grade notifications, job match alerts, instructor announcements, COPPA parental consent emails
4. Language Server Protocol (LSP) backend services for Monaco IntelliSense: Pyright (Python), rust-analyzer (Rust), gopls (Go), typescript-language-server (JS)
5. Secret management solution: AWS Secrets Manager or HashiCorp Vault configuration, secret rotation policy, zero-secrets-in-env-vars enforcement
6. LLM provider specification and cost model for Code Review Bot (Step 16)
7. Container pre-warming pool design and idle container management strategy
8. Dead letter queue and back-pressure handling for grading queue (what happens when queue depth exceeds threshold)
9. Refresh token storage mechanism (HttpOnly cookie vs localStorage) and revocation strategy on logout
10. Row-level security (RLS) policy in PostgreSQL to prevent students from querying each other's submission rows directly
11. Incident response runbook: who gets paged, escalation path, rollback decision criteria
12. Data archival and retention policy: audit_logs and session_logs will grow unboundedly — no partitioning or archival schedule defined
13. Feature flag system for gradual rollout of code review bot and auto-grading to avoid all-or-nothing failures
14. GDPR-FERPA jurisdiction conflict resolution and right-to-erasure retention-hold mechanism
15. Dependabot or Renovate configuration for automated dependency CVE patching (SBOM is generated in Step 12 but no remediation automation exists)
16. Mobile strategy: browser IDE on 375px viewport (Step 22) is acknowledged as a constraint but no degraded mobile experience or native app strategy is defined for a platform where students may learn on phones

### Security Risks

1. Container sandbox insufficient hardening: --network none alone does not prevent privilege escalation. Missing: --cap-drop ALL, --no-new-privileges, custom seccomp profile denying dangerous syscalls (ptrace, mount, kexec_load). A student with Rust/Go execution access and 30 seconds can attempt kernel CVE exploitation. Consider gVisor (runsc) as the container runtime for the grading and IDE sandboxes.
2. JWT refresh token XSS exposure: Step 13 specifies 'refresh token rotation' but storage mechanism is unspecified. If stored in localStorage (common default), any XSS vulnerability (including via student-submitted code rendered in the UI) gives full session hijack. Mandate HttpOnly SameSite=Strict cookies for refresh tokens.
3. WebSocket authentication gap: initial WebSocket handshake can carry JWT in query param or header, but there is no per-message authentication or mid-session token refresh mechanism specified. A token that expires during an active IDE session will silently fail to push grading results.
4. Docker socket mount risk: if the container orchestrator (Step 14) runs inside a pod with Docker socket access, a sandbox escape gives root on the host. The architecture must specify that container orchestration uses Kubernetes Job API or a dedicated out-of-band orchestrator, never a mounted Docker socket.
5. Employer portal enumeration: employer API gives access to candidate profiles with explicit FERPA consent. No rate limiting per employer account is specified. A malicious employer could enumerate all consenting students via paginated API calls to harvest student data for off-platform recruitment.
6. Static analysis tools in Code Review Bot (Step 16) run against student code. If the static analysis tools themselves execute code (some do), the bot must run them in an isolated sandbox — not in the API process. This is unspecified and creates a code execution vector into the platform backend.
7. Curriculum version rollback (Step 17) with git-backed storage: if curriculum content is served directly from a git repo checkout, path traversal attacks via crafted lesson file paths could expose server filesystem contents. Requires strict input sanitization on all path parameters in content delivery.
8. COPPA age gate bypassability: the age gate is a UI/form-level control. Without backend-enforced age verification (requiring credit card proxy or parental email confirmation loop), any user can lie about their age. The compliance artifact (Step 30) needs to document the technical limitation and the accepted risk, or implement actual age verification.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.328883
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
