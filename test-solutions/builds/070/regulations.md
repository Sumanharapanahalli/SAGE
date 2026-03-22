# Regulatory Compliance — Translation Service

**Domain:** ml_ai
**Solution ID:** 070
**Generated:** 2026-03-22T11:53:39.327928
**HITL Level:** standard

---

## 1. Applicable Standards

- **GDPR**
- **SOC 2**
- **ISO 17100**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 16 | SECURITY | Conduct security review of the translation service: API authentication hardening | Threat modeling, penetration testing |

**Total tasks:** 22 | **Compliance tasks:** 1 | **Coverage:** 5%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 2 | SOC 2 compliance verified | PENDING | Build plan includes relevant tasks | devops_engineer |
| 3 | ISO 17100 compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 9 | Engineering |
| data_scientist | 7 | Analysis |
| devops_engineer | 2 | Engineering |
| ux_designer | 1 | Design |
| qa_engineer | 1 | Engineering |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 41/100 (FAIL) — 1 iteration(s)

**Summary:** This plan describes a genuinely comprehensive architecture for a production NMT service, and the overall system design — NLLB base + domain adapters + TM + QE + constrained decoding — is directionally correct. However, the plan systematically underestimates the hardest parts: ML training compute and time are unbudgeted, several acceptance criteria are either unachievable (100% terminology enforcement via constrained beam search) or undefined (100% exact match hit rate), and three foundational architectural choices are wrong or unresolved (BM25 for fuzzy TM matching, HuggingFace constrained beam search for terminology enforcement, 'TorchServe or Triton' left undecided). The agentic orchestrator adds latency risk with no quality benefit over deterministic routing. Critical production concerns — observability, GDPR compliance, data licensing, GPU cost modeling, and document-level translation — are entirely absent. As a research prototype or internal tool this could ship at 55-60 quality with the ML gaps accepted as known limitations; as a production commercial service it requires fundamental rework of the ML training strategy, TM backend, constrained decoding approach, and operational design before it is shippable.

### Flaws Identified

1. Training compute is catastrophically underestimated. Meta trained NLLB-200 with thousands of A100s over months. Fine-tuning a 600M distilled model on 50+ language pairs with meaningful domain coverage on '4x A100' is weeks of wall-clock time, not a plan step. No timeline, no cost estimate, no cloud budget. This single gap can sink the entire project.
2. Constrained beam search for terminology enforcement (Step 10) acceptance criterion of '>= 95% of cases' is unachievable and the '100% of cases' in Step 11 is flat wrong. HuggingFace PhrasalConstraint silently relaxes constraints when they produce degenerate outputs, decoding slows 5-10x per constrained phrase, and multi-term constraint composition degrades exponentially. This needs lexically-constrained decoding (Lexi, DESI, or FUDGE), not HuggingFace's beam search — that's a different implementation entirely.
3. BM25 (Elasticsearch) is a keyword relevance algorithm, not a string similarity algorithm. TM fuzzy matching uses edit distance + token overlap, which is what the scoring description says — but BM25 is not a valid index for this. A BM25 'match' on a paraphrased segment scores high even at 40% string similarity. The entire TM backend architectural choice is wrong for the stated use case.
4. Domain adapter loading/unloading for multi-tenant, multi-domain per-request serving is an unsolved engineering problem in this plan. You have 8 domains × 50+ language pairs = 400+ adapters. Triton Inference Server has no native support for dynamic LoRA swapping mid-request. TorchServe requires custom handlers. The '<20ms overhead' claim for adapter load/unload is not achievable without keeping all adapters resident in GPU VRAM simultaneously — which at 16-rank LoRA is feasible but needs explicit GPU memory planning that is absent.
5. ReAct loop for domain disambiguation (Step 14) in a <400ms p95 latency budget is internally contradictory. ReAct requires at minimum 2-3 LLM inference calls for a reasoning loop. At 100-200ms per call, you've blown the budget before NMT inference begins. This will either be a single-shot classifier disguised as ReAct, or it will routinely violate the SLA.
6. Catastrophic forgetting on base model is completely unaddressed. Fine-tuning NLLB-200 on selected language pairs will degrade performance on pairs not included in the fine-tuning batch. No regularization strategy (L2SP, EWC, distillation from frozen teacher) is mentioned. The regression gate in Step 20 catches post-hoc degradation but doesn't prevent it.
7. Data licensing is entirely missing. OPUS corpora have mixed licenses — several are research-only (WikiMatrix, CCAligned have CC-BY or research restrictions). JRC-Acquis is EU public domain; EMEA corpus is from the EMEA official journal. Using these to train a commercial translation service requires legal review for each corpus. This is a legal blocker, not a footnote.
8. Step 3's BiCleaner-AI scoring on 50+ language pairs at scale requires a language-pair-specific model for each pair — BiCleaner-AI is not a universal scorer. Only a subset of language pairs have pretrained BiCleaner-AI models. For low-resource pairs, you fall back to rule-based BiCleaner which has significantly lower quality. The '50K clean pairs minimum' acceptance criterion will silently pass with low-quality data for many pairs.
9. The QE async scoring architecture (Step 12) has a race condition: the API response includes `qe_score` but the Celery task is asynchronous. The acceptance criterion 'QE score present in 100% of translation API responses' contradicts the async architecture. Either QE is synchronous (adding latency) or the score is absent from the initial response and returned later — you cannot have both.
10. Acceptance criterion 'Exact match hit rate >= 100%' in Step 5 is meaningless and unverifiable as written. 100% is a tautology if your test set was built from the same TM — and impossible to guarantee in production where normalization may legitimately miss a match.
11. Step 6 uses both fairseq and HuggingFace Transformers — these are competing frameworks with different checkpoint formats, tokenizer APIs, and generation logic. NLLB-200 official weights are in fairseq format; converting to HuggingFace adds a non-trivial porting step. The plan treats them interchangeably, which they are not.
12. No mention of model quantization strategy. Running NLLB-200-600M in FP16 training is noted, but production inference quantization (INT8 via bitsandbytes, GPTQ, or TensorRT-LLM) is absent. This directly impacts GPU cost, throughput, and batch sizing for the entire service.
13. Language detection on short inputs (<50 chars) is unreliable with fastText, and the plan acknowledges this by restricting the acceptance criterion to '50-char+ inputs.' But real translation workloads are full of short segments (UI strings, labels, headers). No fallback for <50 char inputs is specified.

### Suggestions

1. Replace the 'train from scratch on 50+ pairs' strategy with NLLB-200's published pre-trained weights as a frozen base and restrict fine-tuning to domain adapters only. This reduces Step 6 from 'train a multilingual model' to 'evaluate NLLB-200 baseline + train adapters,' which is achievable on 4x A100.
2. Replace constrained beam search with a post-edit enforcement pass: translate with NMT, then apply terminology substitution using span alignment (fast_align or awesome-align) with a confidence threshold. This is predictable, debuggable, and doesn't blow inference latency. Reserve constrained decoding only for high-confidence, short, single-token terminology.
3. Replace Elasticsearch BM25 for TM fuzzy matching with a dedicated fuzzy string index: either a character-level n-gram inverted index (fast, correct) or segment embeddings via LASER2 (semantic TM matching). Elasticsearch adds operational complexity without being the right tool.
4. Collapse Steps 3 and 4 into a single data pipeline with domain as a label field. The 50+ pairs × 8 domains matrix doesn't need separate pipelines — a single pipeline with domain classifiers and label propagation is sufficient and avoids the artificial dependency chain.
5. The agentic orchestrator (Step 14) should be replaced with a deterministic routing pipeline for the MVP. Domain detection can be a single fastText classifier call (<5ms). ReAct adds latency and non-determinism with no measurable quality benefit over a classifier for this task. Reserve ReAct for human-review escalation decisions, not inline routing.
6. Add a Step 0: compute and storage budget planning. Before any code is written, specify: GPU-hours for each model training step, storage for corpora (estimate 2-10TB), model checkpoints, adapter registry, and operational GPU costs for inference. Without this, the plan has no cost-of-failure boundary.
7. Separate the QE scoring into two modes: synchronous-fast (BLEURT or a tiny 70M QE model, <30ms) for the initial response, and asynchronous-deep (COMETKiwi, full word-level) stored in the DB and available via polling. The current plan conflates both and makes contradictory promises.
8. Add a data licensing audit step before Step 3. Document the license of each corpus, identify research-only restrictions, and get legal sign-off before training on restricted data. This is a blocking dependency that should precede all data work.
9. Add model serving architecture decision (Step 6.5): pick Triton with custom HuggingFace backend vs. vLLM vs. TGI vs. simple FastAPI+Transformers, document the trade-offs, and commit. This decision cascades through Steps 9, 14, and 17 — leaving it as 'TorchServe or Triton' creates forked implementation paths.

### Missing Elements

1. GPU compute budget and training time estimates. Each ML step (6, 7, 8, 20) needs wall-clock time, GPU-hours, and cost estimate. Without these, the plan has no schedule.
2. Model serving architecture decision record. The 'TorchServe or Triton' ambiguity in Step 17 is unresolved and cascades through inference design, API latency guarantees, and adapter swapping strategy.
3. Observability stack: Prometheus metrics, Grafana dashboards, alerting rules for latency SLAs, model drift detection (QE score trend degradation), and error rate alerting. A production translation service with no APM is not operable.
4. GDPR/data privacy design for the translation service itself. Users will translate medical records, legal contracts, and financial documents. There is no data retention policy, no per-user data isolation in TM, and no right-to-deletion implementation. This is a regulatory blocker in EU markets.
5. Storage architecture and sizing. 50+ language pair corpora, model checkpoints, adapter weights, TM entries (potentially 100M+ TUs), and QE history. No storage estimates, no lifecycle management, no archival strategy.
6. Tokenization alignment strategy between NLLB-200's SentencePiece model and new fine-tuning data. If adapting the tokenizer, how are new tokens added without breaking pretrained embeddings? If using the original tokenizer unchanged, the 256K shared vocabulary claim needs verification against the actual NLLB tokenizer.
7. Rollback and A/B testing strategy for model updates. When a new base model or adapter degrades quality for a specific language pair, how do you roll back per-pair without rolling back all pairs? Step 18 mentions Helm rollback on readiness probe failure but this is infrastructure-level, not model-level.
8. Multi-GPU inference batching strategy. Beam search on NLLB-200 is memory-intensive; dynamic batching for mixed-length inputs requires careful padding and masking. No mention of batching library (NVIDIA Triton dynamic batching, vLLM continuous batching, or manual implementation).
9. Adapter registry query performance at scale. With 400+ adapters, the registry API needs indexing on (domain, lang_pair, version). No schema for the adapter registry beyond 'S3 path' is specified.
10. Low-resource language pair handling. Of the 50+ language pairs, some will have <100K clean sentence pairs after filtering (Step 3 requires 100K minimum but this will fail for rare pairs). No fallback strategy (transfer learning, pivot translation, or explicit exclusion) is documented.
11. Translation of long documents beyond single segments. Step 9 has /translate/stream but no document segmentation strategy, paragraph boundary preservation, or cross-segment terminology consistency for multi-sentence documents.
12. Error recovery in the agentic orchestrator (Step 14). If the QE agent times out, if the TM lookup fails, or if the NMT model returns a degenerate output — the orchestrator has no defined fallback or circuit breaker behavior.

### Security Risks

1. Prefix injection via source text: constrained decoding and TM prefix injection (Step 10) create a direct path where attacker-controlled source text can inject arbitrary token prefixes into the NMT decoder. This can cause model behavior manipulation, output poisoning, or DoS via crafted inputs that force exponential beam search expansion. Step 16's 'input sanitization' is insufficient — it must include token-level constraint validation and beam search budget caps.
2. TMX/TBX file upload path traversal and XML entity expansion: TMX and TBX are XML formats. A malicious upload can include XML External Entity (XXE) references, billion-laugh bombs, or path traversal in attributes. Step 16 mentions file upload path traversal but does not specify using a hardened XML parser (defusedxml) with entity expansion disabled.
3. Translation memory poisoning: an authenticated user can import TMX files that inject adversarial TM entries — e.g., entries that map source phrases to malicious or incorrect translations for other users. There is no TM isolation by project/user at the data layer; the schema has a project_id but no enforcement that TM lookups are scoped to the requesting project.
4. JWT algorithm confusion is mentioned in Step 16 but the mitigation ('RS256 enforcement') is incomplete. The API also accepts API keys via X-API-Key header — if key comparison is not constant-time, timing attacks can enumerate valid keys. No mention of key hashing at rest.
5. The Celery worker (QE async scoring) receives translation content over the message broker. If Redis is used as the Celery broker (common default), translation content — potentially sensitive documents — is stored in plaintext in Redis. No mention of broker-level encryption or message TTL for sensitive payloads.
6. Model inference endpoint exposure: if the Triton/TorchServe model server is reachable within the Kubernetes cluster without authentication, any compromised pod can call it directly and bypass rate limiting, API key checks, and audit logging. No mention of service mesh mTLS or network policy restricting model server access to only the API pods.
7. PII detection via Presidio (Step 16) applied only to logs is insufficient. Translation content itself may contain PII that gets stored permanently in the TM (translation_units table). Users querying the TM concordance endpoint could retrieve other users' PII-containing translations if project scoping is misconfigured.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.327956
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
