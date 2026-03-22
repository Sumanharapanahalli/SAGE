# Regulatory Compliance — Anomaly Detection

**Domain:** ml_ai
**Solution ID:** 068
**Generated:** 2026-03-22T11:53:39.327444
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 20 | SECURITY | Security review: threat model for ingestion endpoint, API key rotation flow, RBA | Threat modeling, penetration testing |
| Step 23 | SYSTEM_TEST | End-to-end system test: inject synthetic metric stream with embedded anomalies,  | End-to-end validation, performance |

**Total tasks:** 24 | **Compliance tasks:** 2 | **Coverage:** 8%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| developer | 11 | Engineering |
| data_scientist | 5 | Analysis |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically ambitious plan with genuine breadth — 24 steps, concrete acceptance criteria, appropriate technology choices, and a sensible dependency graph in most places. However, it has three architectural failures that would cause measurable production failures, not just technical debt. First, the 10x throughput gap between ingestion (100k/s) and scoring (10k/s) is baked into the design with no resolution — the scoring service will permanently lag the buffer. Second, the alert fingerprint in Step 9 references a cluster_id produced in Step 10, creating an unresolvable circular dependency. Third, Granger causality at the proposed scale is computationally intractable, and the 10-second acceptance criterion will never pass without fundamental algorithm changes. Compounding these are the unauthenticated ingestion write path (a security hole, not a gap), the LSTM nightly retraining window that conflicts with 150 Optuna trials, and the complete serialization of frontend development behind the entire ML pipeline. The plan reads like it was written by someone who knows the domain well but hasn't stress-tested the performance envelope or dependency ordering. Fixing the fingerprint design, the throughput architecture, and the Granger scalability strategy would bring this to a solid 70 for MVP scope. As written, it ships with a broken dedup fingerprint, an always-lagging scorer, and a security hole at the entry point.

### Flaws Identified

1. CRITICAL: Throughput mismatch — Step 5 targets 100k metrics/sec ingestion; Step 8 targets 10k scoring ops/sec. The scoring service is architecturally 10x slower than the feed it consumes. Redis Streams backpressure will spike indefinitely under load. No sampling, downsampling, or sharding strategy is defined to close this gap.
2. CRITICAL: Granger causality is O(n²) pairwise × lag_orders. At 100 metrics and 30 lag orders: 9,900 pairs × 30 = 297,000 regressions per incident. The '< 10s for 100 metrics' acceptance criterion is not achievable in Python without precomputed stationarity checks, vectorized lag matrices, and parallel execution — none of which are specified. At 1,000 metrics this collapses entirely.
3. CRITICAL: Fingerprint collision in dedup engine (Step 9) uses `pattern_cluster_id` from DBSCAN clustering — but DBSCAN clustering is defined in Step 10 (root cause correlation), which depends on Step 9. Step 9 cannot use a cluster_id that Step 10 has not yet computed. This is a circular dependency disguised as a sequential one. The fingerprint design must be reconsidered without forward-referencing Step 10's output.
4. SEVERE: LSTM Autoencoder retraining in nightly 30-minute window (Step 7) is incompatible with Optuna 50 trials per model (150 total evaluations). Each LSTM trial on 7 days of data is minutes of compute. 150 trials = multiple hours, not 30 minutes. No GPU is provisioned in the infra plan. Either the tuning cadence or the nightly window constraint must be dropped.
5. SEVERE: The ingestion endpoint is explicitly called an 'unauthenticated write path' in Step 20, yet Step 5's design includes no auth. Auth is designed in Step 20 (security review) but never retrofitted back into Steps 5, 8, or 11. This means the system ships without ingestion auth and the security review produces a report, not a fix.
6. SEVERE: Granger causality requires stationarity. Infrastructure metrics exhibit trends, seasonality, and regime changes — all violations of stationarity. No ADF/KPSS testing, differencing, or detrending step is specified before Granger tests. Results will be statistically invalid for most real-world metric pairs.
7. MODERATE: Frontend steps (14–17) all block on Step 11 (API complete), which itself blocks on the entire backend + ML chain (Steps 5→7→8→9→10). No contract-first API mocking is specified. This serializes ~6 weeks of frontend work behind the full ML pipeline, destroying any parallelism benefit of the multi-step plan.
8. MODERATE: DBSCAN hyperparameters eps=0.3 and min_samples=3 are hardcoded without justification. The feature vector construction for DBSCAN is undefined — Step 10 says 'feature vectors' but never specifies what they contain or how they're normalized. eps=0.3 in an unspecified feature space is arbitrary and will produce poor clusters in practice.
9. MODERATE: No cold-start strategy for new metrics. A metric with < 7 days of history cannot produce a valid rolling training window. The IsolationForest fallback in Step 8 handles model unavailability but not new-metric bootstrapping. High-churn environments (K8s pods, ephemeral services) will consistently fail to score novel metrics.
10. MODERATE: Redis Streams provide at-least-once delivery. Step 5 specifies a write-ahead buffer but no idempotency key or deduplication at the TimescaleDB write layer. A scoring worker restart mid-batch will produce duplicate anomaly_events rows. TimescaleDB UPSERT strategy on (metric_id, timestamp) is not defined.
11. MODERATE: Step 13 (SAGE config) is wired independently and lists acceptance criteria that require the API from Step 11 — but Step 13 depends only on Step 1. The 'Coordinator pattern wires analyst → data_scientist → developer task chain' cannot be validated without the running API. The dependency graph is incorrect.
12. MODERATE: Alert routing conflict resolution is undefined. Step 12 specifies YAML routing rules (match on tags/severity → channel) but does not define behavior when multiple rules match: first-match, all-match, or priority-ranked. This will cause unpredictable multi-paging in production.
13. MINOR: Step 11 heading says 'REST + WebSocket API' but only SSE is implemented. WebSocket and SSE are not equivalent — bidirectional control is impossible over SSE. If the product description later requires interactive streaming (e.g., live threshold adjustment), this is a rework.
14. MINOR: Cardinality explosion from high-cardinality tags (pod_id, trace_id, request_id) is unaddressed. GIN index on tags in TimescaleDB will degrade severely at >100k unique tag combinations. No ingestion-time cardinality limits or label dropping rules are specified.
15. MINOR: Step 12 notification dispatcher has no circuit breaker for downstream channels. If PagerDuty is degraded, escalation timers will silently fail. No dead-letter queue or fallback channel is specified for notification failures.

### Suggestions

1. Resolve the throughput gap in Steps 5/8 by defining explicit async scoring semantics: not every metric needs real-time scoring. Implement priority tiers — high-value metrics score every interval, long-tail metrics score every N intervals or on statistical deviation only. Document this in the PRD (Step 1) as a first-class design decision.
2. Replace Granger causality with Transfer Entropy or precomputed cross-correlation on sliding windows for scalability. If Granger is required, enforce a hard cap (e.g., top-50 metrics by anomaly frequency per incident) and use statsmodels vectorized API with joblib parallelization. Add stationarity testing (ADF) as a prerequisite gate.
3. Fix the fingerprint dependency inversion by removing `pattern_cluster_id` from the Step 9 fingerprint. Use `hash(metric_id, severity_bucket, value_bucket)` for initial dedup. Post-correlation, enrich alert records with cluster_id as a separate field. This removes the circular dependency and allows Steps 9 and 10 to be independent.
4. Separate nightly model refresh (load new version from registry) from weekly hyperparameter retuning (full Optuna run). Nightly: swap model weights from MLflow registry (< 2 min). Weekly: full 50-trial Optuna run on a dedicated worker, with GPU provisioned in Helm chart for that job only.
5. Add API contract mocking (Prism or MSW) in Step 2/11 to unblock frontend development from Step 14 onward. Frontend and backend development should be parallelizable from Step 12 onward, halving the critical path.
6. Define a cold-start policy in the data model (Step 3): metrics with < N observations use IsolationForest only, with a `cold_start: true` flag on anomaly events. Track metric age in a `metric_registry` table. This is a one-line schema addition that prevents undefined behavior for new metrics.
7. Add idempotency to TimescaleDB writes: use `INSERT ... ON CONFLICT (metric_id, timestamp) DO NOTHING` as the default write strategy. Document this in Step 4 and test it explicitly in Step 5's acceptance criteria.
8. Add ingestion authentication in Step 5, not Step 20. Prometheus remote_write supports basic auth and TLS. OTLP supports mTLS. Even a shared bearer token per tenant is better than none. The security review (Step 20) should verify the implementation, not originate it.
9. Add a `metric_registry` table to the data model (Step 3) tracking metric_name, first_seen, last_seen, cardinality_count, and owner_tags. This enables cold-start detection, cardinality enforcement, and per-metric model assignment in the UI (Step 17).
10. Specify circuit breaker (tenacity or custom) in Step 12 for all notification channels. Define a dead-letter queue (Redis or DB table) for failed notifications with retry policy and ops alert on DLQ depth.
11. Add a load test step (k6 or Locust) validating 100k metrics/sec ingestion and 10k scoring ops/sec under sustained load before Step 23 (system test). The system test as written uses 50 metrics — this does not validate the core SLAs.

### Missing Elements

1. Disaster recovery plan: no TimescaleDB backup strategy (pg_dump schedule, WAL archiving to S3, point-in-time recovery). Losing anomaly history for a monitoring platform is operationally catastrophic.
2. Multi-tenancy / team isolation: no tenant scoping for metrics, alerts, or models. An infrastructure monitoring platform serving multiple teams with no data isolation is a non-starter for enterprise use.
3. Load test / performance validation step: the 100k/s and 10k/s SLA targets appear only in acceptance criteria with no dedicated load test plan to validate them against real hardware.
4. Metric cardinality enforcement: no ingestion-time limits on tag cardinality, no label dropping rules, no cardinality budget per metric family.
5. Model artifact integrity verification: no checksum or signature verification when loading model weights from MLflow registry. Model poisoning attack surface unaddressed.
6. SLO definitions and error budgets: the PRD step mentions SLA targets but no error budget policy (what happens when false positive rate exceeds target? who owns the SLO?)
7. Data retention for anomaly events in cold tier: the S3/Parquet cold tier is defined for raw metrics but anomaly_events, alert_records, and correlation_edges retention in cold storage is unspecified.
8. GDPR / data residency: infrastructure metrics can contain PII (usernames in tags, email addresses in alert metadata). No data classification or regional storage policy.
9. Stationarity preprocessing pipeline: required before Granger causality but absent from the entire plan.
10. MLflow model serving / model API versioning: how does the scoring service know to use model v3 for metric A and model v2 for metric B? Per-metric model assignment is mentioned in the UI (Step 17) but not in the scoring service architecture (Step 8).
11. Operational runbook for model drift: Step 24 mentions a model-drift runbook but no automated drift detection (PSI, KL divergence on score distributions) is built in Steps 6-8. The runbook will have no signals to act on.
12. Backpressure strategy when TimescaleDB is degraded: the ingestion buffer (Redis Streams) will fill indefinitely if writes are slow. No overflow eviction policy, no producer-side rate limiting, no operator alert on buffer depth.

### Security Risks

1. Unauthenticated ingestion endpoint: explicitly flagged in Step 20 scope but never remediated in the plan. Any actor on the network can inject arbitrary metrics, poison anomaly scores, trigger false alerts, or exhaust DB storage. This is critical in a monitoring system where fake anomalies can mask real incidents.
2. API key auth with no rotation policy enforced by the system: Step 20 says 'rotation invalidates old key immediately' but no rotation schedule, no compromise detection (rate anomaly on a single key), and no key expiry TTL are specified. A compromised key is valid indefinitely until manually rotated.
3. RBAC designed in Step 20 but not wired in Steps 11/14-17: the API and UI are built without RBAC constraints. Retrofitting auth to 11 endpoints and 4 frontend pages after the fact is a high-risk change with incomplete test coverage.
4. Redis Streams with no auth/TLS in dev: `.env` secrets for dev often get committed. Redis without auth means any process on the Docker network can read or inject into the ingestion buffer.
5. Generic webhook outbound (Step 12) with no HMAC signing: outbound webhook payloads contain alert data. Receiving systems cannot verify payload integrity. Inbound webhook (n8n integration referenced in SAGE) also lacks HMAC verification.
6. MLflow model registry without artifact signing: a compromised MLflow instance or MITM on the registry endpoint can deliver malicious model weights. The scoring service loads and executes these weights with no integrity check.
7. Celery workers with implicit trust: Celery beat and workers communicate over Redis without task signing by default. An attacker with Redis access can inject arbitrary Celery tasks (including model retrain triggers or arbitrary Python execution via task payloads).
8. SBOM scan only on direct dependencies (Step 19): transitive dependency CVEs (the most common supply chain attack vector) are not explicitly covered. Syft produces the SBOM but the scan gate should use Grype or Trivy with a transitive-depth flag.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.327475
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
