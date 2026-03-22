# Regulatory Compliance — Document Extraction

**Domain:** ml_ai
**Solution ID:** 061
**Generated:** 2026-03-22T11:53:39.325735
**HITL Level:** standard

---

## 1. Applicable Standards

- **SOC 2**
- **GDPR**
- **ISO 27001**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 13 | SECURITY | Perform security review of the document extraction API. Threat model: malicious  | Threat modeling, penetration testing |
| Step 15 | QA | Define and execute a QA test plan covering extraction accuracy benchmarks, edge  | Verification & validation |

**Total tasks:** 16 | **Compliance tasks:** 2 | **Coverage:** 12%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | ISO 27001 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |

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
| data_scientist | 4 | Analysis |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 57/100 (FAIL) — 1 iteration(s)

**Summary:** The plan is well-structured and covers all the right conceptual areas — the dependency graph is logical, acceptance criteria are mostly concrete, and the technology selections are defensible. However, it has several failure modes that will block production delivery, not just slow it down. The most critical: there is no model training step. The plan assumes a fine-tuned LayoutLMv3 materializes by Step 6, but data collection, annotation, and fine-tuning are absent from the entire 16-step plan — this alone could add 4–8 weeks to the timeline. Second, the Celery Chord + SSE architecture for batch progress is technically broken as described and will require a redesign when implemented. Third, the Docker image size constraint (< 2 GB) and the 30s CPU SLA are both physically impossible given the chosen ML stack; these will cause the Step 10 and Step 4 acceptance criteria to fail on day one. The security review in Step 13 is solid in intent but arrives too late — auth and input validation should be in place before Steps 11–12 integration tests, not after. For an MVP where ML model quality targets can be relaxed and the SLA is GPU-qualified, this plan could score in the low 60s; as written, targeting the stated acceptance criteria on CPU infrastructure, it scores 57.

### Flaws Identified

1. Step 6 assumes a fine-tuned LayoutLMv3 exists ('fine-tuned on FUNSD + custom labeled invoices/receipts/contracts') but there is NO step in the plan that covers data labeling, model training, or fine-tuning. FUNSD is a generic form-understanding dataset — it will not hit F1 ≥ 0.88 on domain-specific invoices out of the box. This is the most critical gap in the entire plan.
2. Step 9 uses Celery Chord for fan-out and SSE for per-document progress streaming, but these are architecturally incompatible as described. A Chord callback fires ONCE when ALL subtasks complete, not incrementally per document. To emit per-document SSE events you need workers to write intermediate status to Redis/DB and the SSE endpoint to poll that — not a chord callback. This will not work as written.
3. Step 4 acceptance criterion: '10-page PDF in under 30 seconds on a 2-vCPU machine' is not achievable with EasyOCR + LayoutLMv3 + Table Transformer on CPU. EasyOCR cold-start alone is 5–15s; inference on 10 pages at 300 DPI (10 × ~5MB images) on CPU takes 60–120s. This SLA requires GPU and is not flagged as such.
4. Step 10 acceptance criterion: 'Docker image size < 2 GB (multi-stage build)' is not achievable. PyTorch (required by EasyOCR and transformers) is ~2 GB by itself. Add CUDA libs, Tesseract binaries, spaCy models, LayoutLMv3 weights (~450 MB), Table Transformer weights, and Python deps — the image will be 6–10 GB minimum. This constraint will be failed immediately.
5. Step 3 acceptance criterion: 'JSONB columns validated by a CHECK constraint against a JSON schema' — PostgreSQL CHECK constraints cannot perform JSON Schema validation natively. You would need a PL/pgSQL function or extension (pg_jsonschema). This is non-trivial and not mentioned.
6. Step 8: Celery workers are synchronous by default. Using SQLAlchemy async sessions (asyncpg) inside Celery tasks requires a dedicated event loop per task (asyncio.run()). Mixing FastAPI's async context with Celery's sync workers without explicit loop management causes 'Event loop is closed' errors in production. This is a common failure mode that requires explicit design.
7. Step 8 critic re-routing: 'if score < 0.7, retry with alternate engine' — the plan does not define what happens when both engines fail below threshold, or when EasyOCR is already the engine used (no alternate exists). This creates an infinite loop or silent failure path.
8. Step 9 rate limiting is IP-based ('per client IP'). This fails silently behind corporate NAT, VPNs, or CDNs where hundreds of users share one IP. Step 13 adds API-key-based auth, but these two rate-limiting strategies are never reconciled into a single coherent policy.
9. Steps 11–12 tests are designed before Step 13 auth is implemented. Every test against authenticated endpoints will need to be reworked after auth is added, or tests must mock auth from day one. The dependency ordering creates technical debt in the test suite.
10. EasyOCR downloads models (~1.5 GB) on first use at runtime. In a containerized environment this means the first job submission will block for minutes or fail with a timeout. The Dockerfile in Step 10 does not pre-bake model weights into the image.

### Suggestions

1. Insert a 'ML_DATA' step between Steps 1 and 6: define data labeling schema, collect 500+ annotated documents per type, fine-tune LayoutLMv3, and run evaluation. Without this, Step 6 F1 targets are aspirational, not achievable.
2. Replace the Celery Chord + SSE pattern: have each Celery subtask write status updates to a Redis hash keyed by batch_id, and have the SSE endpoint poll that hash every 1s. Remove the chord pattern entirely for batch progress tracking.
3. Add a GPU/CPU tiering note to the SLA: state '30 seconds on 2-vCPU with Tesseract-only path; 60 seconds with EasyOCR on CPU; GPU required for < 15s'. Separate the SLAs by code path.
4. Split the Docker image: create a 'cpu-slim' image (Tesseract + spaCy only, ~1.5 GB) and a 'gpu-full' image (+ PyTorch + EasyOCR + transformers). Most document pipelines can start with cpu-slim and upgrade selectively.
5. Pre-download all ML model weights into the Docker image during build (using a dedicated RUN layer after pip install) so workers start cold in < 30 seconds.
6. Add an explicit step for the document classifier: Step 4 mentions 'lightweight CNN or zero-shot LLM classifier' but neither path is designed. Zero-shot via an LLM adds ~2–5s latency and cost per document. A fine-tuned DistilBERT on 3 classes is 30ms inference and should be the primary path.
7. Add a webhook/callback endpoint: polling-only APIs force clients into polling loops. Add POST /extract with optional callback_url parameter — far more efficient for batch consumers.
8. Define a data retention and purge policy in Step 3. Extracted text from invoices and contracts is PII-dense. The DELETE /jobs/{job_id} endpoint must cascade-delete all derived artifacts (entities, tables, stored file).
9. Resolve the Celery serializer explicitly: set task_serializer='json', result_serializer='json', accept_content=['json'] in Celery config. Default pickle is a code execution vector if Redis is reachable from untrusted networks.
10. Add a 'decompression bomb' guard: a 100KB PDF can expand to gigabytes. Add a size check after pdf2image conversion, not just on the upload.

### Missing Elements

1. Model training pipeline: data collection, annotation tooling (Label Studio or Prodigy), fine-tuning script, and model registry. Without this, LayoutLMv3 will not meet F1 targets.
2. OCR bounding-box format translation layer: pytesseract returns (left, top, width, height) in pixels; EasyOCR returns [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]; LayoutLMv3 expects normalized [x0,y0,x1,y1] in 0–1000 range. The conversion logic is non-trivial and completely absent from the plan.
3. Graceful worker shutdown: in-flight Celery tasks during a rolling deploy or scale-down. No SIGTERM handler defined; jobs will be orphaned.
4. Password-protected PDF handling: mentioned only as a negative test in Step 15 but no pipeline handling is designed. Should return a structured error at ingestion stage, not propagate to OCR.
5. Multi-language support: Step 5 mentions 'language packs: eng + any configured locales' but there is no configuration surface, no locale detection, and no NER model selection per language. This is a stub that will break for any non-English document.
6. Memory pressure management: a 50 MB PDF converted at 300 DPI produces ~300 MB of PIL images. With 10 concurrent workers, this is 3 GB of in-memory image data. No worker memory cap or per-job memory limit is defined.
7. API versioning: no /v1/ prefix, no deprecation strategy. Breaking changes to the JSON output schema (e.g., entity type renames after model updates) will silently break consumers.
8. Encryption at rest: raw PDFs and extracted entities (names, financials, legal parties) are stored unencrypted. For any real deployment processing business documents this is a compliance gap.
9. Token/cost budget for LLM-based document classifier if used: no rate limit, no cost tracking, no fallback if the LLM endpoint is down.

### Security Risks

1. Multipart batch upload (Step 9) accepts up to 100 files at 50 MB each = 5 GB per request. File size validation in Step 13 fires after reading, not before. A single request can exhaust disk or memory before rejection. Enforce Content-Length header limit at the reverse proxy and per-file size limit during streaming ingestion.
2. Celery default serializer (pickle) allows arbitrary Python object deserialization. If Redis is exposed or compromised, a crafted task message achieves remote code execution on all workers. Must set task_serializer='json' explicitly — this is not mentioned anywhere in the plan.
3. The Redis instance in the Docker Compose stack has no password configured. In any environment where Redis is not 100% network-isolated (cloud VMs, shared dev environments), this is an unauthenticated RCE surface via Celery task injection.
4. PDF content can include embedded JavaScript, URI actions, and launch actions. Neither pdfplumber nor pdf2image is immune to malicious PDFs. No mention of sandboxing the PDF processing workers (e.g., seccomp profile, no-network container policy, or running in a gVisor/Firecracker VM).
5. PII leakage surface is broader than Step 13 addresses: extracted entity values will appear in Celery task arguments, Redis result backend, PostgreSQL extraction_results, and potentially in exception tracebacks. The log scrubber alone is insufficient — need field-level encryption or result backend TTL.
6. SSRF via webhook callback_url (not in this plan but a natural next feature): if a callback_url field is added later without SSRF protection, the extraction service becomes a proxy for internal network scanning.
7. Job UUID v4 prevents sequential enumeration but does not prevent a compromised API key from listing all jobs for all users. No tenant isolation or job ownership model is defined — any authenticated client can poll any job_id if they guess it.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.325762
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
