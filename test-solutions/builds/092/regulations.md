# Regulatory Compliance — Data Warehouse

**Domain:** enterprise
**Solution ID:** 092
**Generated:** 2026-03-22T11:53:39.335884
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **ISO 27001**
- **GDPR**
- **CCPA**

## 2. Domain Detection Results

- enterprise (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 3 | LEGAL | Draft terms of service, privacy policy, data processing agreements (DPA), and op | Privacy, licensing, contracts |
| Step 4 | COMPLIANCE | Map ISO 27001 and SOC 2 Type II controls to product architecture. Produce a cont | Standards mapping, DHF, traceability |
| Step 5 | SECURITY | Produce threat model (STRIDE), security architecture document, encryption-at-res | Threat modeling, penetration testing |
| Step 23 | QA | Produce a quality assurance test plan: test strategy, test case inventory, data  | Verification & validation |
| Step 26 | SYSTEM_TEST | Execute system-level end-to-end test suites: full ETL-to-query flow (ingest CSV  | End-to-end validation, performance |
| Step 27 | COMPLIANCE | Collect and package ISO 27001 and SOC 2 evidence artifacts: access control revie | Standards mapping, DHF, traceability |

**Total tasks:** 30 | **Compliance tasks:** 6 | **Coverage:** 20%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 4 | CCPA compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 12 | Engineering |
| devops_engineer | 4 | Engineering |
| regulatory_specialist | 3 | Compliance |
| qa_engineer | 2 | Engineering |
| technical_writer | 2 | Operations |
| product_manager | 1 | Design |
| business_analyst | 1 | Analysis |
| legal_advisor | 1 | Compliance |
| ux_designer | 1 | Design |
| data_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| operations_manager | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 54/100 (FAIL) — 1 iteration(s)

**Summary:** This is an architecturally ambitious and well-structured plan that correctly identifies the six core domains of a cloud data warehouse and sequences most dependencies logically. The compliance coverage (ISO 27001, SOC 2, GDPR) is thorough, the API design is sound, and the observability/CI-CD choices are production-grade. However, the plan contains several critically underscoped components that will cause significant rework: the Python UDF sandbox is a named RCE risk with no implementation, column-level SQL lineage is treated as a straightforward parsing problem when it is a known hard problem in the industry, and the BI connector step conflates five distinct certification-level integrations into a single sprint-sized task. More structurally, three foundational architectural decisions are missing entirely — the Iceberg catalog backend, the multi-tenant isolation model per data store, and the data residency enforcement mechanism — and these decisions unblock or invalidate work in at least 10 downstream steps. The plan is not ready to execute as written; it needs the missing architectural decisions resolved and the three high-risk components (UDF sandbox, lineage parser, BI drivers) broken out into their own scoped sub-plans before any code is committed. Score reflects a well-intentioned comprehensive plan with fundamental execution risks that make the 54 generous — the UDF sandboxing and lineage gaps alone could each derail the product.

### Flaws Identified

1. Step 12 specifies 'Python UDF sandbox prevents filesystem and network access' with zero implementation detail. No sandboxing technology is named (gVisor, Firecracker, seccomp profiles, nsjail). This is the highest-severity RCE vector in the entire plan and is treated as a one-line acceptance criterion. Production UDF sandboxing is a multi-sprint effort in itself.
2. Step 15 column-level lineage from ANTLR SQL parsing is massively underscoped. The acceptance criterion of '50 representative SQL patterns including JOINs, CTEs, and window functions' is a toy benchmark. Commercial lineage tools (Alation, Atlan, OpenMetadata) with years of engineering still fail on dynamic SQL, stored procedures, MERGE statements, lateral joins, and dialect variations. This will be the #1 source of post-launch bugs.
3. Step 16 builds JDBC/ODBC drivers and native connectors for Tableau, Power BI, Looker, Metabase, and Superset as a single plan step. Each of these is a substantial engineering project: Tableau has its own connector SDK and certification process, Power BI DirectQuery requires specific query folding semantics, Looker LookML export requires understanding the LookML schema model. This is 6-12 months of work presented as one step.
4. Step 13 performance SLA ('SELECT query on 1B row Iceberg table returns first page within 5 seconds') is an unqualified promise. It doesn't specify cluster size, query shape, partition pruning, whether data is cached, cold vs warm path, or network topology. This will be used in sales materials and will fail for non-trivial queries.
5. Multi-tenant isolation is mentioned throughout but never architecturally resolved. How does Trino enforce tenant isolation at query runtime? Separate catalogs per tenant? Shared catalog with row-filter policies? What happens to the query result cache in Redis — are keys namespaced per tenant? Elasticsearch: index-per-tenant or document-level security? These gaps are where cross-tenant leakage actually happens.
6. Step 8 specifies 7+ data stores: PostgreSQL, Elasticsearch, Neo4j/Neptune, TimescaleDB, Redis, S3, and the query engine's own storage. No single step addresses the operational burden of running all of these. The Docker Compose in Step 9 will be enormous and slow. The on-call burden is proportional to the number of distinct stores.
7. The Iceberg catalog backend is never decided. The plan uses Iceberg throughout (Steps 10, 13, 14) but never selects a metastore: AWS Glue, Hive Metastore, Iceberg REST Catalog, or Project Nessie. This choice affects the query engine, ETL engine, and catalog service at their foundation. It's a day-one architectural decision that's missing.
8. Step 9 specifies HashiCorp Vault as a hard startup dependency for all services with no Vault HA topology, no agent sidecar pattern, and no documented fallback. If Vault is unavailable at startup, every service fails to boot. This creates a single point of failure that invalidates the 99.9% availability SLO from Step 25.
9. Step 26 load test profile (100 concurrent query users, 10 ETL pipelines, 30 minutes) is inadequate for a product positioning against Snowflake and BigQuery. It proves nothing about production headroom. No mention of data volume at test time, no ramp-up simulation, no spike scenarios, and no test of cache cold-start behavior.
10. Step 3 and Step 4 establish GDPR/CCPA data residency requirements for US and EU regions, but zero steps in the plan implement data residency enforcement at the query or storage layer. No geo-fencing of Iceberg table locations, no query routing by tenant region, no enforcement mechanism. This is a GDPR hard requirement that will block EU customers.
11. Step 17 AI feature acceptance criterion ('Natural language to SQL converts at least 80% of test queries') is unverifiable without a defined, adversarial test set. 80% on a hand-picked test set routinely drops to 40-50% on real user queries. No benchmark dataset (Spider, BIRD, WikiSQL) is referenced, and no evaluation methodology is defined.
12. Step 22 targets 80% line coverage but for a distributed data system with complex failure modes, line coverage is a poor proxy. No property-based testing, no chaos/fault injection tests, no data correctness tests that verify ETL output against source checksums. A passing test suite here would give false confidence.
13. Dependency order error: Step 15 (lineage) depends on Step 14 (catalog), but ETL execution lineage capture is part of Step 12 (ETL engine). Lineage events emitted by ETL need a store to write to before the catalog exists. The dependency graph forces lineage to be bolted on after ETL is built, guaranteeing a refactor of the ETL engine.
14. No API rate limiting or query resource governance at the API gateway layer. Step 13 specifies per-user memory/CPU quotas inside Trino, but nothing prevents a tenant from submitting 10,000 concurrent query submissions to the API layer, exhausting the query queue and starving other tenants before Trino-level governance activates.
15. No backup and restore implementation step exists. Step 28 defines DR procedures with RTO 4h / RPO 1h, but no step actually implements automated backups of PostgreSQL metadata, Elasticsearch indices, Neo4j graph data, or Iceberg table snapshots. DR procedures without tested restore tooling are documentation theater.

### Suggestions

1. Add an explicit architectural decision step (before Step 8) that resolves: Iceberg catalog backend, multi-tenant isolation model at each layer (Trino, Elasticsearch, Redis, PostgreSQL RLS), and data residency enforcement mechanism. These decisions block multiple downstream steps and their absence will cause rework.
2. Decompose Step 16 (BI connectors) into at minimum three steps: (1) Arrow Flight SQL server + SQLAlchemy dialect, (2) JDBC/ODBC via existing wire protocol compatibility, (3) native connectors for Tableau/Power BI. Descope Looker LookML export from MVP — it requires deep semantic layer integration that is disproportionately complex.
3. Replace Step 12's UDF sandbox acceptance criterion with a concrete design decision: select gVisor or Firecracker as the execution environment, define the resource limits (memory, CPU, wall-clock timeout), specify the syscall allowlist, and add a security review gate before merging UDF execution code.
4. For Step 15 column-level lineage, consider adopting OpenLineage as the event standard rather than building a custom ANTLR parser. This gives you integrations with dbt, Spark, Airflow out of the box and reduces the scope of the custom parser to SQL typed directly in the query editor only.
5. Add a cost metering and billing step. The ROI analysis in Step 2 positions this against Snowflake/BigQuery, both of which have consumption-based pricing. Without a metering system, you cannot bill customers or surface cost attribution per team/pipeline — a must-have for enterprise buyers.
6. Separate the load test in Step 26 into two distinct scenarios: (1) sustained load at expected p50 concurrency, (2) burst load at 10x p50. Also add a cold-start query scenario (no cached Iceberg metadata, no result cache) to validate the worst-case p95 the SLA must cover.
7. Step 9's Docker Compose will become unmaintainable with 8 services plus PostgreSQL, Elasticsearch, Neo4j, Redis, Vault, and Kafka. Consider splitting the local dev environment into a 'core' profile (API, auth, catalog) and a 'full' profile, with documented expectations for RAM requirements per profile.
8. Add tenant provisioning and offboarding to the RBAC step (Step 11). Offboarding requires cascading deletion of: Elasticsearch index, Neo4j subgraph, Iceberg namespace, PostgreSQL RLS policies, and audit log archival. Missing this creates GDPR right-to-erasure compliance gaps.
9. The observability stack (Step 25) should be deployed before system tests (Step 26), which it is — but it should also be instrumented before any backend service is considered 'done'. Add observability instrumentation as an acceptance criterion on Steps 11-16 rather than treating it as a post-integration concern.

### Missing Elements

1. Iceberg catalog backend selection and justification (AWS Glue vs. Iceberg REST Catalog vs. Nessie) — affects Steps 8, 10, 12, 13, 14
2. Data residency enforcement mechanism for EU/US tenant separation at storage and query layers (required for GDPR Article 46)
3. Backup and restore implementation for all persistent stores (PostgreSQL, Elasticsearch, Neo4j, Iceberg snapshots) — the DR procedure in Step 28 has nothing to restore from
4. Cost metering and usage attribution system — without this, enterprise billing is impossible and the Snowflake/BigQuery comparison in the ROI analysis is not actionable
5. Schema registry for Kafka sources (Step 12 lists Kafka as a source but does not address schema evolution, Avro/Protobuf deserialization, or consumer group management)
6. Change data capture (CDC) connector design — ETL sources include PostgreSQL and MySQL but CDC (Debezium-style) is not addressed; polling-based ETL for OLTP sources at scale creates unacceptable source load
7. Tenant provisioning and offboarding workflow with cascading data deletion (GDPR right-to-erasure compliance)
8. API rate limiting and abuse prevention layer at the gateway (separate from Trino-level resource governance)
9. Per-tenant encryption key management (envelope encryption with tenant-specific KMS keys) — mentioned as a risk in Step 5 but never implemented
10. Data migration and import tooling for customers moving from Snowflake, BigQuery, or Redshift — this is a sales-cycle blocker and not in scope anywhere
11. Chaos engineering / fault injection test plan for distributed failure modes (Trino coordinator failure, Elasticsearch shard unavailability, Vault unreachability)

### Security Risks

1. Python UDF execution without a named, audited sandbox technology is a remote code execution vulnerability. If the sandbox is implemented incorrectly, a malicious UDF can read other tenants' Iceberg data, exfiltrate credentials from the Vault agent sidecar, or pivot to the Kubernetes control plane. This is the highest severity risk in the plan.
2. Shared Redis query result cache with tenant-namespaced keys relies on correct key construction in application code. A single bug in cache key generation leaks one tenant's query results to another. The acceptance criterion ('concurrent queries from different tenants do not share result cache entries') needs adversarial testing, not just a happy-path check.
3. ANTLR SQL parser (Step 15) can be DoS'd with adversarial SQL inputs — deeply nested CTEs, recursive queries, or pathologically complex join trees that trigger exponential parse time. No input validation or parse timeout is specified.
4. BI connector credentials (per-tool service accounts) are long-lived secrets that have read access to warehouse data. If a Tableau or Power BI service account credential is leaked, it can exfiltrate bulk data without triggering per-user quotas. Vault dynamic secrets rotation is listed but credential scope (read-all vs. read-specific-schema) is not defined.
5. Elasticsearch cluster is frequently misconfigured to be reachable from unintended networks. The plan puts it in private subnets but Step 14's schema inference from Glue Catalog sync could expose metadata to the Elasticsearch cluster from a broader network boundary. No Elasticsearch authentication model (API key vs. SAML) is specified.
6. OAuth 2.0 client credentials for service-to-service calls (in addition to mTLS) creates dual authentication paths. If the OAuth path is not disabled in production and mTLS is the intended enforcement mechanism, an attacker who compromises a client_secret bypasses mTLS entirely. The plan does not specify whether mTLS replaces or supplements OAuth for internal traffic.
7. Iceberg REST Catalog (if selected) exposes a metadata API that reveals table schemas and partition statistics to anyone with catalog-level access. Column-level RBAC at the query layer does not prevent schema enumeration at the catalog layer — a low-privilege user can infer sensitive data existence from column names and statistics without querying the data.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.335927
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
