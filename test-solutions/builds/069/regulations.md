# Regulatory Compliance — Search Engine

**Domain:** ml_ai
**Solution ID:** 069
**Generated:** 2026-03-22T11:53:39.327672
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **SOC 2**
- **Accessibility Standards**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 16 | SECURITY | Security review: input sanitization for search queries and index payloads, rate  | Threat modeling, penetration testing |

**Total tasks:** 18 | **Compliance tasks:** 1 | **Coverage:** 6%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | Accessibility Standards compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 8 | Engineering |
| data_scientist | 3 | Analysis |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| product_manager | 1 | Design |
| ux_designer | 1 | Design |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 63/100 (FAIL) — 1 iteration(s)

**Summary:** This is a well-structured, comprehensive plan with appropriate tech choices and measurable acceptance criteria across most steps. For an MVP semantic search engine it is above average in completeness. However, several architectural decisions will cause production failures rather than just technical debt: the inverted API design dependency (spec after implementation) guarantees schema drift; the autocomplete latency target is physically incompatible with semantic reranking at query time; the A/B framework lacks statistical validity and will produce misleading results; and index consistency between Qdrant and BM25 has no failure handling, making hybrid search correctness non-deterministic under load. The security posture has gaps that are easy to exploit (unauthenticated Qdrant, unauthenticated Redis, XSS in snippet rendering). The plan needs targeted fixes on these six issues before implementation begins — fixing them mid-build is significantly more expensive. Addressing these would bring the score to approximately 75–78 for MVP scope.

### Flaws Identified

1. Step 8 (OpenAPI spec) depends on steps 5–7 (implementation) — this is design-after-code, not design-first. API contracts should be agreed before implementation to prevent schema drift and undocumented edge cases. The entire dependency chain is inverted here.
2. Step 6 autocomplete uses 'redis_prefix_scan + semantic_rerank' but targets < 20ms. Redis SCAN is O(N) and semantic reranking adds 30–80ms per call. These two constraints are physically incompatible unless reranking is fully pre-computed and cached — which is not specified.
3. Step 5 states facet filters are 'applied as pre-filter to vector search and BM25 simultaneously.' Qdrant pre-filtering degrades HNSW recall severely when selectivity is high (< 5% of corpus matches filter). Post-filtering or filtered HNSW (payload-indexed) trade-offs are not addressed — this will silently return poor results for selective filters.
4. Step 7 A/B experiment router has no statistical rigor: no minimum sample size, no significance threshold (p-value or Bayesian), no mechanism to determine when an experiment is conclusive. Traffic split percentage alone does not constitute a valid A/B framework. Shipping ranking changes based on inconclusive experiments is worse than no experiments.
5. Index consistency between Qdrant (vector) and BM25 (disk-serialized inverted index) is never addressed. A partial write failure leaves them diverged with no detection mechanism, no compensating transaction, and no reconciliation process. For hybrid search this is a correctness failure, not a latency issue.
6. Step 3 intent classifier (navigational/informational/transactional) has no training data source specified, no labeling process, no fallback behavior when confidence is low, and no acceptance criterion for the training set size. This is described as a deliverable but has no implementation path.
7. Step 2 claims '1000 docs/min on standard hardware' without specifying hardware. all-MiniLM-L6-v2 encoding on CPU achieves approximately 100–300 docs/min per core depending on chunk size. This target is probably unachievable without GPU or multi-worker parallelism, neither of which is planned.
8. Step 9 (UX design) only depends on step 1, but the relevance tuning console design should also depend on step 7. Technical constraints discovered in step 7 (e.g., hot-reload mechanics, boost rule schema) will force redesign of the console UI, discovered after wireframes are already approved.
9. Cursor-based pagination (step 10) is incompatible with dynamic relevance configs. If a relevance config changes between pages, cursor positions become invalid — documents can be duplicated or skipped across pages. No invalidation strategy is defined.
10. Step 15 regression test 'fails CI if NDCG@10 drops > 2%' requires a stable stored baseline. No mechanism for versioning, storing, or updating the baseline is specified. If the baseline is recomputed each run, the regression gate is meaningless.

### Suggestions

1. Flip step 8 (OpenAPI spec) to be step 1.5 — define the API contract as a design artifact before any backend implementation. Use contract-first development with mock servers so frontend can develop in parallel against real schemas.
2. Replace 'redis_prefix_scan + semantic_rerank' with ZRANGEBYLEX on pre-built prefix keys or a dedicated trie (e.g., pyahocorasick, datrie). Pre-compute semantic scores offline and store ranked candidates per prefix key. Do not rerank at query time.
3. Add explicit HNSW parameter specification to step 4: ef_construct (128–256 for high recall), m (16–32), and ef at query time (64–128). Run a recall-vs-latency sweep on your corpus before setting these. Add acceptance criterion: 'HNSW params produce > 0.95 recall@10 vs brute-force at p95 < 100ms.'
4. Add a Qdrant payload index for every facet field (step 4) and benchmark both pre-filter and post-filter strategies against your expected filter selectivity distribution. Document the crossover point where post-filtering is preferred.
5. Replace the A/B framework in step 7 with a statistically rigorous design: define minimum detectable effect (e.g., 3% NDCG improvement), compute required sample size, implement sequential testing or fixed-horizon test with Bonferroni correction. Add acceptance criterion: 'experiment results include 95% confidence interval and required sample size.'
6. Add a write-coordinator service (or at minimum a saga pattern) to step 5 that ensures Qdrant upsert and BM25 index update are treated as a single logical operation with rollback or retry on partial failure. Log all index operations to the query_logs table for reconciliation.
7. Step 3 query expansion: specify the mechanism explicitly. LLM-based expansion adds 50–200ms and should be async/cached. Synonym dictionary (WordNet + domain-specific) is faster and more predictable. Decide which before implementation.
8. Add data retention and PII handling to step 16. Query logs (step 7) contain user search terms — define retention period, anonymization strategy, and GDPR deletion path before shipping.
9. Step 15 baseline versioning: store baseline run files in git-LFS or an artifact store (S3/GCS) keyed by a hash of the corpus + model version. CI fetches the appropriate baseline by key and stores new baselines only on explicit promotion.
10. Add a warm-up/seed strategy for autocomplete cold start. On first deploy, populate Redis prefix keys from the document corpus (titles, key phrases) so the autocomplete is useful before any query logs exist.

### Missing Elements

1. Multi-language support: all-MiniLM-L6-v2 is trained primarily on English. No language detection, no multilingual model fallback (e.g., paraphrase-multilingual-MiniLM-L12-v2), no acceptance criterion about language coverage.
2. Qdrant authentication and API key management. Qdrant defaults to unauthenticated access. The security review (step 16) mentions JWT for the admin console but never addresses Qdrant's own API key or TLS configuration.
3. Backup and restore testing with acceptance criteria. Step 18 mentions a runbook but no step validates that a backup can actually be restored, or that Qdrant snapshots and BM25 index backups are taken at consistent points in time.
4. Scalability boundary documentation. The plan targets 100k documents but specifies no memory or storage estimates for Qdrant at that scale (384-dim float32 = ~150MB for 100k vectors plus HNSW graph overhead ~2–4x). No guidance on when horizontal sharding is needed.
5. Rate limiting on /autocomplete endpoint. Step 16 specifies limits for /search (100 req/min) and /index (10 req/min) but omits /autocomplete, which fires on every keypress and is the highest-volume endpoint by far.
6. HTTPS/TLS enforcement. No step configures TLS termination. A JWT-protected admin console served over HTTP is trivially compromised.
7. Dwell-time measurement implementation in the frontend. Step 7 lists dwell-time as a feedback signal but no frontend component or beacon API is planned in steps 10–11 to capture it.
8. Definition of 'bias evaluation' in step 3 and step 15. The term appears twice as an acceptance criterion with no methodology: what demographic or query-type bias is being measured, against what ground truth, with what pass/fail threshold?
9. Query deduplication and normalization for autocomplete index. As new queries arrive, misspellings and variations of the same intent will pollute the autocomplete index. No deduplication or normalization pipeline is specified.
10. Qdrant collection migration strategy. If the embedding model is upgraded (step 3 mentions fine-tuning), all 384-dim vectors become invalid and the entire collection must be reindexed. No zero-downtime reindexing strategy or dual-collection approach is defined.

### Security Risks

1. Qdrant runs unauthenticated by default. If the Qdrant port is reachable (even internally), any service can read, modify, or delete the entire vector collection. No authentication is specified in step 4 or step 16.
2. Redis sorted set for autocomplete has no authentication specified. Default Redis deployments have no password. Exposed Redis allows arbitrary key injection, autocomplete poisoning, and cache poisoning attacks.
3. Vector poisoning via the /index endpoint. Step 16 lists this as a review area but provides no mitigation. An attacker with index access (or a compromised upstream system) can inject adversarial documents with crafted embeddings that rank for sensitive queries. Input validation on document content does not prevent this.
4. JWT secret management is unaddressed. The plan specifies JWT for the admin console but does not define where the signing secret lives, how it is rotated, or how tokens are revoked. A hardcoded secret in an env file is a common failure mode.
5. Query logs store raw user search terms in PostgreSQL. If query_logs are not access-controlled separately from the main application DB credentials, any read access to the database exposes the full search history of all users.
6. Payload size limit (10MB on /index) is stated but chunking pipeline in step 2 processes PDFs and HTML. A compressed PDF can expand to 50–100x in text. The limit should apply post-decompression, not to the raw request body, or decompression bombs are possible.
7. No mention of output encoding for snippet highlighting in the frontend (step 10). Search result snippets render matched terms from user query input into the DOM. Without strict output encoding, a stored document containing HTML/JS can trigger XSS when highlighted.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.327699
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
