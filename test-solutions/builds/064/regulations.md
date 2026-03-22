# Regulatory Compliance — Recommendation Engine

**Domain:** ml_ai
**Solution ID:** 064
**Generated:** 2026-03-22T11:53:39.326485
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **ePrivacy Directive**
- **SOC 2**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 17 | SECURITY | Perform threat model and security review for the recommendation system: user dat | Threat modeling, penetration testing |
| Step 19 | SYSTEM_TEST | End-to-end system test and load test: validate sub-100ms p99 latency under reali | End-to-end validation, performance |

**Total tasks:** 22 | **Compliance tasks:** 2 | **Coverage:** 9%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | ePrivacy Directive compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 3 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| data_scientist | 8 | Analysis |
| developer | 7 | Engineering |
| devops_engineer | 3 | Engineering |
| product_manager | 1 | Design |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is a technically sophisticated and architecturally sound plan that demonstrates genuine ML systems expertise — the component selection (Two-Tower + LinUCB + FAISS + dual-store feature store) is appropriate, the latency budget decomposition is the right approach, and the CI/CD canary strategy is production-grade. However, the plan scores 63 because it contains several critical correctness gaps that would cause silent failures in production rather than visible crashes: the absence of propensity logging makes the bandit's offline evaluation mathematically invalid; the missing feature snapshot mechanism guarantees training/serving skew that will degrade model quality over time; the FAISS in-process deployment pattern breaks under horizontal scaling without a coordination mechanism; and the GDPR Parquet deletion claim is not implementable as described. The 100ms online bandit update promise under concurrent load is an unverified performance claim that will likely require fundamental architectural change (async update queue) rather than optimization. None of these are fatal to the overall design — they are tractable engineering problems — but they need explicit resolution before this plan can be executed against the stated acceptance criteria. Recommend addressing the propensity logging, feature snapshot, FAISS pod coordination, and bandit concurrency gaps before committing to the current acceptance criteria.

### Flaws Identified

1. Step 5 claims Flink end-to-end latency of 10ms (event-time to Redis write). Flink's minimum checkpoint interval is typically 100ms–1s, and micro-batch processing adds inherent buffering. 10ms is achievable only with Kafka Streams in per-record mode with zero windowing — the plan conflates processing-time latency with event-time semantics and will fail this acceptance criterion in production.
2. Step 8 requires Neural LinUCB online weight updates within 100ms. At 10k RPS with even 1% CTR, that is 100 reward signals/second each triggering a matrix update (Sherman-Morrison or gradient step). The plan proposes a 'Vowpal Wabbit + custom PyTorch wrapper' — these are fundamentally incompatible paradigms (VW is online-learning native; PyTorch requires explicit gradient management). The wrapper will be a correctness and maintenance liability.
3. Step 9 describes FAISS hot-swap as 'atomic file replace with zero serving downtime.' A file-system atomic replace does not produce an atomic in-memory swap. Each serving pod holds the index in RAM; replacing the file on disk requires explicit reload logic per pod. Under rolling reloads, pods serve from different index versions simultaneously with no version-skew handling described.
4. Step 11's latency budget sums to 40ms best-case (2+5+5+10+15+3). This leaves only 60ms of headroom for p99 at 100ms SLA. It does not account for: Redis cluster network jitter (can spike 20–30ms at p99 under GC pauses), TLS overhead on Redis connections, Python async event loop scheduling overhead, or serialization cost for 100-item feature payloads. The p99 SLA will be violated under realistic production conditions without explicit tail-latency mitigation.
5. Step 8's IPS (Inverse Propensity Score) estimator for offline bandit evaluation requires propensity scores — the probability that each item was shown under the logging policy. Neither Step 11 (serving) nor Step 14 (feedback ingestion) includes propensity logging in the request/response schema. Without stored propensities, the IPS estimator is mathematically invalid and will produce biased offline evaluation results.
6. Step 4 claims 'point-in-time correct feature retrieval' using Redis as the online store with TTL eviction. Redis TTLs will evict features that existed at prediction time before the training pipeline runs. There is no mechanism to snapshot feature values at request time for later training label joins. This creates training/serving skew — a fundamental ML correctness failure that will silently degrade model quality.
7. Step 12 claims mutual exclusion between overlapping experiments is 'enforced' but provides no mechanism. SHA-256 consistent hashing assigns users to buckets deterministically but does not prevent the same user from being in two concurrent experiments simultaneously. Mutual exclusion requires an explicit namespace/layer isolation system (as used by Google/Meta). Without this, experiment contamination will corrupt statistical results.
8. Step 14 triggers bandit online weight updates within 100ms of reward arrival. Under concurrency, multiple feedback events for the same bandit model arrive simultaneously. Neural LinUCB weight matrices are not thread-safe for concurrent updates. The plan does not address locking strategy, update queuing, or eventual consistency semantics — race conditions will corrupt model weights silently.
9. The cold start problem is unaddressed. New users (no interaction history) and new items (no embeddings) are mentioned only as a chaos scenario in Step 19. At production scale, cold-start requests constitute a significant fraction of traffic and require fallback strategies (popularity-based, content-based, or exploration-heavy bandits). The Two-Tower model produces no embedding for unseen entities.
10. FAISS is deployed 'in-process within the serving container' (Step 9) but the serving API scales horizontally on Kubernetes (Step 11). Each pod holds its own FAISS index in RAM. Index rebuilds (Step 9) must propagate atomically to all N pods simultaneously. The plan provides no pod coordination mechanism — pods will serve from stale indices of different ages during rolling updates, breaking recall guarantees.
11. Step 17's GDPR deletion requirement says 'marks Parquet records as deleted.' Parquet is an immutable columnar format — records cannot be deleted in place. Actual deletion requires rewriting affected partitions. At scale (30-day Parquet history across multiple feature groups), this is a multi-hour Spark job per deletion request. The plan underestimates this by an order of magnitude.

### Suggestions

1. Replace Flink with Kafka Streams for the real-time feature pipeline (Step 5). Kafka Streams processes records synchronously without checkpointing overhead and can achieve sub-10ms Redis writes. Reserve Flink only if complex windowed aggregations are required.
2. Decouple Neural LinUCB online updates from the feedback ingestion hot path (Step 8/14). Write rewards to a bounded in-memory queue and process updates asynchronously in a single-writer thread. Expose a 'reward freshness' metric rather than promising 100ms synchronous update — this is the correct production architecture for online bandits.
3. Add propensity logging to Step 11 immediately. The serving response should include `{item_id, score, position, propensity}` tuples. Propensities must be persisted alongside feedback events (Step 14) for IPS correctness. This is a schema change that is expensive to retrofit after deployment.
4. Implement feature snapshots for training/serving alignment: when a recommendation request is served, write a snapshot of the feature values used (keyed by trace_id) to a time-limited store (Redis with 7-day TTL). The offline pipeline joins training labels to these snapshots instead of the live feature store, eliminating training/serving skew.
5. Add a model serving sidecar pattern for FAISS: instead of in-process per pod, deploy a shared FAISS service (or use Redis Stack with RediSearch for ANN) that all serving pods query. This eliminates the pod coordination problem for index updates and centralizes memory usage.
6. For A/B mutual exclusion (Step 12), implement an experiment namespace/layer system: each experiment is assigned to an orthogonal dimension, and user assignment is computed as hash(user_id + layer_salt). Users can participate in one experiment per layer simultaneously. Document this in the PRD as a first-class design constraint.
7. Add explicit Redis memory sizing to Step 3/4. At 10M items with 256-dim float32 embeddings: 10M × 256 × 4B = 10GB for item embeddings alone, before user features or interaction data. A 6-node cluster with 16GB/node gives 96GB total — model this explicitly against your feature groups to validate the cluster is sized correctly.
8. Replace 'atomic file replace' in Step 9 with a versioned index endpoint: the serving container polls a model registry (MLflow) for the latest index version and loads it into a shadow slot, then atomically swaps the pointer. Use a read-write lock per pod to prevent serving during swap. Coordinate across pods via a shared 'active_index_version' key in Redis.
9. For GDPR deletion (Step 17), implement a deletion ledger pattern: maintain a `deleted_users` table in PostgreSQL. All Spark training jobs filter against this table at read time. Schedule quarterly full Parquet rewrites to physically remove deleted records. This is the only approach that scales without per-deletion Spark jobs.
10. Add explicit rate limiting (token bucket or leaky bucket) to the serving API (Step 11) with per-user and per-client-id limits. Without this, a single misbehaving client can saturate Redis and blow the p99 SLA for all users.

### Missing Elements

1. Propensity logging schema and storage strategy — required for IPS bandit evaluation in Step 8 to be mathematically valid
2. Cold start strategy for new users and new items — a critical production gap affecting a significant fraction of traffic
3. Feature snapshot mechanism for training/serving alignment — absence guarantees training data bias
4. FAISS index distribution and synchronization strategy across horizontal pod replicas
5. Redis memory budget and eviction policy selection (allkeys-lru vs. volatile-lru) — critical for feature store TTL behavior under memory pressure
6. Canary metric isolation strategy in Step 15 — how are 5% canary request metrics separated from 95% control in Prometheus/Grafana for valid comparison
7. Bandit exploration/exploitation policy for cold-start items with no reward history
8. Network topology and service mesh configuration (how do serving pods discover Redis, feature store, FAISS service)
9. Kafka topic ACLs and broker authentication — no mention of mTLS or SASL between producers and consumers
10. Model rollback strategy beyond binary 'rollback on SLA breach' — what happens to bandit weights that were updated online during a bad model's serving window
11. Data retention and S3 cost model for Parquet offline store — 30-day history with daily partitions across multiple feature groups at scale needs explicit sizing
12. Experiment sample size and power calculation tooling in Step 12 — without minimum detectable effect and required sample size pre-calculation, experiments will be underpowered or run too long

### Security Risks

1. Redis cluster has no mention of TLS in-transit or Redis AUTH. Feature store data contains behavioral signals tied to pseudonymized user IDs. Unencrypted Redis in a multi-tenant Kubernetes cluster is a data exposure risk if network policies are misconfigured.
2. Kafka topics have no ACL specification. Any service that can reach the Kafka brokers can read `raw_feedback` or `bandit_rewards` topics, or inject malicious events that corrupt bandit model weights (model poisoning via feedback injection).
3. FAISS index artifacts are stored in S3 with no integrity verification mentioned. A compromised S3 bucket or misconfigured IAM role allows injection of a poisoned FAISS index, causing the recommendation engine to serve attacker-controlled items to all users.
4. JWT validation in Step 17 is described at the API level but the feature store service (Step 10) handles internal service-to-service calls. If the feature store trusts internal network calls without verifying service identity (mTLS or service account tokens), a compromised pod can exfiltrate all user features.
5. A/B experiment assignment logs contain the full mapping of user_id to experiment variant. If these are stored in plaintext in the audit log alongside behavioral signals, they constitute a behavioral profile that is sensitive under GDPR and could be used to re-identify pseudonymized users.
6. The feedback deduplication mechanism (Step 14) uses Redis SETNX on (user_id, item_id, session_id). An adversary who can predict or enumerate session_ids can replay feedback events after the 24h TTL expires, polluting the bandit reward signal without triggering deduplication.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.326514
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
