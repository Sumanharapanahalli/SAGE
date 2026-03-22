# Regulatory Compliance — Image Generation

**Domain:** ml_ai
**Solution ID:** 067
**Generated:** 2026-03-22T11:53:39.327212
**HITL Level:** standard

---

## 1. Applicable Standards

- **Copyright Law**
- **GDPR**
- **Content Safety Guidelines**

## 2. Domain Detection Results

- ml_ai (from solution definition)

## 3. Compliance Task Coverage

Tasks in the build plan that address compliance requirements:

| Task | Type | Description | Compliance Relevance |
|------|------|-------------|---------------------|
| Step 21 | SECURITY | Security review: input validation for uploaded images (file type, size, magic by | Threat modeling, penetration testing |

**Total tasks:** 25 | **Compliance tasks:** 1 | **Coverage:** 4%

## 4. Compliance Checklist

| # | Requirement | Status | Evidence | Responsible Agent |
|---|------------|--------|----------|-------------------|
| 1 | Copyright Law compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |
| 2 | GDPR compliance verified | PENDING | Build plan includes relevant tasks | legal_advisor |
| 3 | Content Safety Guidelines compliance verified | PENDING | Build plan includes relevant tasks | regulatory_specialist |

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
| developer | 13 | Engineering |
| data_scientist | 4 | Analysis |
| devops_engineer | 2 | Engineering |
| qa_engineer | 2 | Engineering |
| analyst | 1 | Analysis |
| ux_designer | 1 | Design |
| system_tester | 1 | Engineering |
| technical_writer | 1 | Operations |

## 7. Critic Review (Actor-Critic Assessment)

**Plan Score:** 51/100 (FAIL) — 1 iteration(s)

**Summary:** This is an architecturally ambitious plan with good structural coverage — the dependency graph is sound, acceptance criteria are specific, and the tech stack choices are reasonable. However, it contains one disqualifying technical incompatibility: the entire style transfer feature is built on SD1.5 ControlNet models wired to an SDXL pipeline, which will fail at the tensor dimension level before a single image is generated. Beyond that blocker, the plan is missing its own authentication issuance flow (JWTs are validated but never issued), has no content safety layer (a hard legal requirement for any non-private deployment), leaves SSE delivery broken under multi-instance scaling, and never designs the SDXL refiner chaining that makes SDXL worth using over SD1.5. The ML benchmarking methodology (FID on 100 samples) is statistically invalid. Fixing the ControlNet model selection, adding the auth flow, and adding NSFW filtering would raise this to a shippable MVP at roughly 68-72. As written, style transfer ships broken and the service is legally undeployable in any public context.

### Flaws Identified

1. CRITICAL: SD1.5 ControlNet models used against SDXL base. Step 2 specifies 'stabilityai/stable-diffusion-xl-base-1.0' but step 10 loads 'lllyasviel/control_v11p_sd15_canny' and SD1.5 depth/openpose models. These are architecturally incompatible — SD1.5 ControlNet conditioning tensors have different shapes than SDXL's dual-encoder UNet. Style transfer will throw a dimension mismatch error at runtime, not a graceful failure.
2. SDXL inpainting model omitted from step 2. The plan lists the base + refiner but 'stabilityai/stable-diffusion-xl-1.0-inpainting-0.1' is a separate fine-tuned model required for SDXL inpainting. Using StableDiffusionXLInpaintPipeline with the base model produces incoherent outputs.
3. No user registration/login endpoints anywhere. Step 4 specifies 'Bearer JWT' auth and step 7 implements JWT validation middleware, but there is no POST /auth/register, POST /auth/login, or POST /auth/refresh. JWTs cannot be issued without these. The entire auth flow is headless.
4. SSE progress delivery under multi-instance API deployment is unresolved. Workers emit progress to Redis Pub/Sub; SSE subscribers are connected to a specific API server instance. Under K8s with 2+ api-server replicas, 50% of SSE clients will receive no events from jobs processed by the other instance. No sticky sessions, no shared SSE broker, no acknowledgment of this problem.
5. VRAM budget for simultaneous model loading is never calculated. SDXL base (fp16) ~6.9GB + refiner ~6.5GB + SDXL ControlNet ~2.5GB + Real-ESRGAN ~0.1GB + GFPGAN ~0.3GB = ~16GB minimum with no active inference tensors. An A10G has 24GB. One concurrent SDXL generation uses ~4GB activation memory. Two workers sharing a GPU (step 3 sets worker_replicas=2 without specifying GPU affinity) will OOM with no explicit model offloading or mutual exclusion strategy.
6. FID on 100 images is statistically invalid. Step 20 acceptance criterion 'FID score for SDXL txt2img < 20 on validation set' uses 100 COCO images. FID requires thousands of samples for stable estimates — the variance on 100-sample FID is so large the number is meaningless. This benchmark will produce wildly different results per run and cannot catch real regressions.
7. Poisson blending (cv2.seamlessClone) on AI-generated inpainted regions frequently produces color bleeding and texture artifacts. The blending boundary algorithm assumes natural photographic content. SDXL-generated fills regularly have stylistic discontinuities that seamlessClone amplifies rather than heals. No fallback or alpha-feathering alternative specified.
8. Redis Streams consumer group failure mode unaddressed. If an sd-worker crashes mid-generation, its pending message stays in the PEL (pending entries list) indefinitely. No XAUTOCLAIM, dead-letter queue, or job requeue-on-timeout logic is specified. Jobs will silently stall.
9. CLIP token counter is wrong for SDXL. SDXL uses a dual text encoder (CLIP-L/14 + OpenCLIP-G/14). Each encoder has a 77-token limit but they are applied independently, and SDXL supports prompt weighting and token padding that effectively allows longer prompts. A single CLIP-L tokenizer count is misleading and will incorrectly warn users on prompts that SDXL handles fine.
10. SDXL refiner integration never designed. The refiner is listed in step 2's model list and noted in the payload, but no step specifies when the refiner fires (typically denoising_end=0.8 on base, then refiner from 0.8), how it's chained in the worker, or how it affects progress reporting. It will either be silently unused or require last-minute implementation that hasn't been tested.
11. MinIO signed URL expiry creates broken asset links. Asset records are stored in PostgreSQL with signed URL references. A user who saves a job result and opens it 2 hours later gets a 403 from MinIO. No URL refresh endpoint, no lazy re-signing on GET /assets, no acknowledgment of this problem.
12. Duplicate detection via full-table pHash scan at 1M assets is O(N). Step 13 specifies 'imagehash pHash Hamming distance < 10' but describes no indexing strategy. A VP-tree, LSH index, or pgvector similarity column would be required to make this sub-second. The current approach will take minutes at 1M records.

### Suggestions

1. Replace SD1.5 ControlNet models in step 10 with SDXL-native equivalents: 'diffusers/controlnet-canny-sdxl-1.0', 'diffusers/controlnet-depth-sdxl-1.0'. Alternatively, downgrade the base model to SD1.5 and drop the refiner — simpler stack, all ControlNet models become compatible.
2. Add step 2 model: 'stabilityai/stable-diffusion-xl-1.0-inpainting-0.1'. This is a distinct HuggingFace repo, not a pipeline variant of the base model.
3. Add POST /auth/register and POST /auth/login to the step 4 OpenAPI spec. They're the prerequisite for every authenticated endpoint and are currently missing.
4. For SSE under multi-instance deployment: have each API server subscribe to a Redis Pub/Sub channel keyed by job_id at the moment a client opens the SSE connection. Workers publish progress to Redis Pub/Sub (not just the Stream). This makes SSE delivery instance-agnostic.
5. Add a VRAM budget table to step 8's model registry (vram_gb field is already there). Enforce at worker startup: sum enabled models' VRAM requirements against available GPU memory and refuse to start if headroom < 4GB. Use diffusers' enable_model_cpu_offload() as fallback.
6. Replace FID-on-100-images with CLIP score (image-text alignment) and aesthetic score as per-sample metrics. These are valid on small sets. Reserve FID for optional nightly runs on 10K+ samples.
7. For inpainting seam quality, replace seamlessClone with alpha-feathered compositing using a Gaussian-blurred mask boundary. More robust for AI content. Only fall back to seamlessClone as an opt-in enhancement.
8. Add dead-letter queue: after XAUTOCLAIM reclaims a message that has been idle > 5 minutes, move it to a 'failed_jobs' stream and mark the GenerationJob as status='failed' with error='worker_timeout'.
9. Add POST /auth/refresh endpoint and implement lazy re-signing: when GET /assets is called, re-sign any URLs older than 55 minutes before returning them. Store the S3 object key (not the signed URL) in PostgreSQL.
10. For pHash duplicate detection at scale: store pHash as a BIGINT column on the assets table, then use a periodic batch job that groups by pHash range (Hamming distance binning) rather than pairwise comparison.

### Missing Elements

1. Content safety / NSFW filtering. No SafetyChecker, no NSFW classifier, no content policy enforcement. Any public deployment of an image generation service without this will generate illegal content and expose the operator to legal liability. This is a hard blocker for any non-private deployment.
2. User registration and authentication flow (POST /auth/register, POST /auth/login, POST /auth/refresh, POST /auth/logout). Referenced everywhere, implemented nowhere.
3. SDXL refiner chaining logic — when to invoke it, how denoising_end/denoising_start split is configured, how it's represented in job progress.
4. GPU affinity / exclusive allocation policy for K8s. With 2 worker replicas and 1 GPU, both workers will try to load full model sets simultaneously. Need nvidia.com/gpu: 1 resource limit per pod and pod anti-affinity or a GPU allocation queue.
5. Model download / caching strategy at container startup. HuggingFace model pulls (25-30GB total) at cold start will timeout any reasonable Kubernetes liveness probe. Need pre-built images with baked-in models or a persistent volume mount with pre-downloaded weights.
6. Job cancellation endpoint (DELETE /jobs/{id}) and worker-side cancellation signal via Redis.
7. Output file size limits. ESRGAN 4x on a 2048x2048 input produces 8192x8192 PNG (~192MB uncompressed). No cap on output resolution or file size is specified.
8. Multi-user data isolation audit. Asset library CRUD, bulk operations, and collection export must enforce user_id ownership checks. The schema has users table but the API layer ownership validation is never explicitly specified.
9. Bias evaluation methodology. Steps 2 and 20 say 'bias evaluation performed' as an acceptance criterion with no specification of what dataset, what axes (demographic representation, style diversity), what tooling, or what constitutes a pass. This is a compliance checkbox with no substance.
10. WebP thumbnail generation pipeline. Step 9 mentions 'PNG + WebP thumbnail' as output format but no step specifies thumbnail dimensions, generation timing, or storage path.

### Security Risks

1. Image upload parsing before magic-byte validation. Step 21 specifies python-magic for MIME validation, but if the image is passed to PIL or cv2 before validation (e.g., for dimension checks in inpainting), a malformed file can trigger CVE-level PIL/libpng parser vulnerabilities. Validation must be the first operation, before any image decoding.
2. Prompt injection into LLM gateway. Step 14's prompt enhancement calls POST /llm/generate with user-supplied prompt text. If the LLM gateway system prompt is not isolated from user input, adversarial prompts can override enhancement behavior, extract system prompts, or cause SAGE's LLM gateway to execute unintended actions. The sanitization in step 21 strips control characters but does not prevent semantic injection.
3. Signed URL SSRF potential. The MinIO signed URL generation uses boto3 with a configurable endpoint. If model_id, hf_repo, or storage paths are user-influenced and not strictly validated, an attacker could potentially redirect signed URL generation to internal services.
4. Redis Streams consumer group with no authentication in Docker Compose. Step 3 scaffolds Redis without specifying requirepass. An unauthenticated Redis instance on the Docker network allows any container (or network-adjacent host) to read generation jobs, inject fake completions, or publish progress events for other users' SSEs.
5. Bulk delete endpoint without ownership validation creates IDOR. POST /assets/bulk with bulk_delete operation and a list of asset IDs — if the service layer doesn't filter by authenticated user_id, any user can delete any other user's assets by guessing UUIDs.
6. ZIP export path traversal risk. Step 13's collection export creates a ZIP with filenames derived from asset metadata. If asset filenames or metadata fields contain '../' sequences and are not sanitized before zipfile.write(), the downloaded ZIP can overwrite files on extraction (Zip Slip vulnerability).
7. No Content Security Policy or CORS policy specified for the frontend. The React app calls the FastAPI backend; without explicit CORS allowlist and CSP headers, XSS in the asset library (e.g., via a crafted prompt string rendered as HTML) can exfiltrate JWTs.


## 8. Audit Trail

- **Generated by:** SAGE Build Orchestrator v2.0
- **Timestamp:** 2026-03-22T11:53:39.327242
- **Pipeline:** Domain Detection → Plan Decompose → Critic Review → HITL Approve → Scaffold → Execute → Integrate → Finalize
- **Approval gates:** All build artifacts subject to HITL approval
- **Critic threshold:** 70/100 (actor-critic review required before human approval)
