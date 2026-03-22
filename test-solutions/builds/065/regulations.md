# Regulatory Compliance — Fraud Detection

**Domain:** ml_ai
**Solution ID:** 065
**Generated:** 2026-03-22T11:53:39.326717
**HITL Level:** standard

---

## 1. Applicable Standards

- **PCI DSS**
- **SOC 2**
- **GDPR**
- **Fair Lending Laws**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 14 | SECURITY | Security review for the fraud detection system: authentication/authorization on  | Threat modeling, penetration testing |
| Step 21 | SYSTEM_TEST | End-to-end system test: simulate 10k transactions through Kafka → feature engine | End-to-end validation, performance |

**Total tasks:** 22 | **Compliance tasks:** 2 | **Coverage:** 9%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | PCI DSS compliance verified | PENDING | Build plan includes relevant tasks | safety_engineer |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | Fair Lending Laws compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| data_scientist | 7 | Analysis |
| developer | 6 | Engineering |
| qa_engineer | 3 | Engineering |
| ux_designer | 2 | Design |
| devops_engineer | 2 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 61/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically ambitious plan that demonstrates genuine ML engineering knowledge — temporal holdout, SHAP integration, ensemble stacking, RBAC, and CI/CD model gates are all present and correctly motivated. However, several concrete implementation blockers will halt delivery: TabNet ONNX export and DeepExplainer incompatibility are not theoretical concerns but known library limitations that will require architecture changes; the stacking meta-learner as described will overfit without explicit OOF generation; and the training-serving skew between the streaming pipeline and batch ETL is the most dangerous production failure mode and is entirely unaddressed. The latency targets (100ms p99 with SHAP, <10ms feature assembly at 10k TPS) are aggressive and unvalidated by any measurement. The plan is a solid foundation for an MVP but needs targeted rework on the neural model explainability strategy, sliding window implementation, stacking methodology, and a dedicated training-serving consistency layer before the core ML pipeline can be trusted in production.

### Flaws Identified

1. Step 6 + Step 8: TabNet ONNX export is broken for most versions — the custom sequential attention mechanism uses unsupported ONNX ops. DeepExplainer does not work with TabNet at all; it requires PyTorch models with differentiable operations only. You will hit this wall during implementation, not during planning.
2. Step 7: Stacking meta-learner trained on base model outputs without explicit out-of-fold prediction strategy. If the meta-learner sees in-sample predictions from XGBoost/neural, it will overfit severely. The plan says 'meta-learner on XGBoost + neural outputs' but does not specify OOF cross-validation generation. This is a classic stacking leakage failure.
3. Steps 3 vs 4: Training-serving skew is unaddressed. The streaming feature pipeline (Redis sliding windows via INCR/EXPIRE) and the batch ETL (historical SQL aggregates) will compute velocity features differently — window boundaries, timezone handling, and null imputation will diverge. Models trained in batch will behave differently in production. This is the #1 production failure mode for real-time ML.
4. Step 3: Redis INCR+EXPIRE does not give true sliding windows — it gives fixed tumbling windows that reset at TTL expiry. True 1m/5m/15m sliding windows require ZRANGEBYSCORE on sorted sets with score=timestamp. The acceptance criterion says 'velocity counters update within 50ms' but the data structure choice will produce incorrect counts near window boundaries.
5. Step 3: 10k TPS through Kafka with multiple Redis lookups per transaction (velocity, merchant risk, device trust) + feature assembly in <10ms is not validated by any back-of-envelope math. At 10k TPS that is 10+ Redis round trips per transaction = 100k Redis ops/sec with sub-1ms target per op. Achievable with pipelining, but no pipelining strategy is specified.
6. Step 9: p99 <100ms with 500 concurrent requests is not achievable with SHAP for flagged transactions. Even with the >0.7 threshold gate, DeepExplainer on TabNet takes 50-500ms on CPU. The SHAP 200ms target in step 8 and the scoring service 100ms p99 in step 9 are contradictory for transactions above 0.7.
7. Step 11: 'Incremental retraining' for XGBoost via warm_start/booster.continue_training does not generalize well under concept drift — it compounds existing trees rather than adapting to distribution shifts. For TabNet, incremental learning is not natively supported without continual learning modifications. The plan does not address catastrophic forgetting.
8. Step 11: EMA risk score update strategy only increases scores on confirmed fraud. Analyst dismissals should decrease merchant/device risk scores, but the plan does not specify bidirectional updates. Repeated false positives on a legitimate merchant will permanently inflate their risk score.
9. Step 14: No rate limiting on POST /score. An adversary can probe the model with crafted inputs to reverse-engineer decision boundaries (model extraction attack). The threat model mentions adversarial inputs but the mitigation — rate limiting, input perturbation, confidence withholding — is absent from the security acceptance criteria.
10. Step 5: AUC-PR > 0.85 acceptance criterion is asserted without a baseline or feasibility analysis. With 2% fraud rate (from step 21) and no stated dataset size, this is a guess. If the real dataset has 0.1% fraud rate or significant label noise from chargebacks, 0.85 AUC-PR may be unachievable on the described feature set.

### Suggestions

1. Replace DeepExplainer with KernelExplainer (model-agnostic, slower) or switch the neural model architecture to a standard MLP where GradientExplainer works reliably. Benchmark SHAP latency before committing to the 200ms SLA.
2. Add a dedicated feature store consistency test: run the same transaction through both the streaming pipeline and the batch ETL and assert feature values are identical within tolerance. Make this a blocking CI gate.
3. For true sliding windows, use Redis sorted sets with ZADD (score=unix_timestamp, member=txn_id) + ZCOUNT/ZRANGEBYSCORE. Document the memory tradeoff vs INCR/EXPIRE.
4. For stacking, explicitly generate out-of-fold predictions using StratifiedKFold on training data, then train the meta-learner on those OOF outputs only. Add a test that verifies meta-learner training data has zero overlap with base model training data.
5. Separate SHAP computation into an async background job for flagged cases rather than inline with the scoring response. Return fraud_score + decision synchronously; explanations are fetched by the UI on case detail load. This removes SHAP from the p99 latency path entirely.
6. Add a model rollback procedure: MLflow model registry supports staging/production/archived stages. Define a runbook for promoting, demoting, and emergency rollback. The CI/CD gate prevents regression but does not handle post-deployment issues.
7. Add schema evolution strategy: version the feature schema in schema.yaml (v1, v2, etc.), store the schema version in model artifacts, and validate at inference time that the feature schema matches the model's expected schema.
8. For the E2E test (step 21), use Testcontainers or docker-compose in CI rather than assuming a live Kafka cluster. The 15-minute CI target in step 16 will be exceeded if Kafka startup is uncontrolled.
9. Add GDPR/CCPA conflict resolution for the immutable audit log: the append-only requirement conflicts with right-to-erasure. Recommended pattern: pseudonymize PII in audit records using a key that can be deleted, preserving audit integrity while enabling erasure compliance.
10. Specify Kafka consumer group configuration, partition count, and backpressure strategy (max.poll.records, pause/resume on Redis saturation) in step 3. The 10k TPS claim needs a partition/consumer scaling model.

### Missing Elements

1. Runtime monitoring: no Prometheus metrics, no Grafana dashboards, no alerting on SLA breach, model score distribution drift, or Redis/Kafka lag. The CI/CD pipeline is defined but production observability is absent.
2. Model rollback runbook: what happens operationally when a deployed model starts producing garbage scores at 2am? MLflow supports it but the procedure is not defined.
3. Cold start strategy: new merchants, new devices, new customers have zero historical data. merchant_fraud_rate_7d returns null. The 'documented fallbacks' mentioned in step 3 are never specified — what is the actual fallback value and what bias does it introduce?
4. Feature schema versioning and backward compatibility: no strategy for deploying a new model with a different feature set without downtime or score inconsistency.
5. PCI DSS compliance scope: a fraud detection system processing card transactions almost certainly falls under PCI DSS. The security step mentions JWT/RBAC and PII masking but does not address PCI DSS requirements (tokenization, network segmentation, key management, quarterly scans).
6. Load test specification for the feature engineering pipeline (step 3): the 10k TPS target has no test harness defined. Without a Kafka load generator and Redis saturation test, this criterion is untestable.
7. Data lineage tracking: if a model makes a wrong fraud decision, analysts need to trace exactly which feature values influenced the prediction at inference time. The plan persists predictions but does not specify feature snapshot storage format or retention.
8. Analyst notification system: step 12 describes SSE for new cases, but there is no mention of escalation paths, SLA timers for unreviewed cases, or analyst workload balancing beyond bulk-assign.

### Security Risks

1. Model extraction via /score endpoint: without rate limiting and query logging, an attacker can submit crafted transactions to map the model's decision boundary and build a surrogate model. Mitigations: per-IP/per-key rate limits, anomaly detection on query patterns, confidence score rounding.
2. Training data poisoning via feedback loop (step 11): an adversary who can trigger chargebacks or influence analyst decisions can inject mislabeled samples into the retraining pipeline. The 500-sample minimum gate in step 11 is insufficient protection. Mitigations: anomaly detection on label batch quality, human review of retraining datasets exceeding a drift threshold.
3. JWT without refresh token rotation: the security step specifies JWT with role claims but not token expiry, refresh strategy, or revocation. A stolen analyst JWT is valid until expiry with no revocation mechanism. Mitigations: short-lived access tokens (15min) + refresh token rotation, token revocation list in Redis.
4. Redis as trust boundary: merchant/device risk scores stored in Redis are modified by the feedback loop. If Redis is compromised or the feedback endpoint is abused, an attacker can suppress fraud scores for known bad actors. Redis should require AUTH, and risk score writes should be validated against expected distribution ranges.
5. SQL injection risk in case search/filter endpoint (GET /cases with filter parameters): if filter values are interpolated into queries rather than parameterized, the audit log and analyst decisions are exposed. Must enforce parameterized queries — not mentioned in security acceptance criteria.
6. SHAP value leakage: returning top-5 SHAP features in API responses reveals which features the model weighs most heavily. Sophisticated fraudsters can use this to craft transactions that score below threshold. Consider returning feature categories rather than raw feature names in external-facing responses.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.326747
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
