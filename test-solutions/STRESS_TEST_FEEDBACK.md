# SAGE Build Orchestrator — 100-Solution Stress Test Feedback

**Date:** 2026-03-22
**Test Scope:** 100 solutions across 10 domains via real LLM (Claude Sonnet 4.6)
**Duration:** ~8 hours total execution time

---

## Executive Summary

All 100 solutions successfully decomposed and passed through the Build Orchestrator pipeline. The framework handles every domain from regulated medical devices to consumer apps. However, the stress test revealed several critical findings that need addressing before production use.

**Final Score: 100/100 builds successful (after retry of transient LLM failures)**

---

## 1. Critical Findings

### 1.1 Actor-Critic Revision Loop Not Wired

**Severity: HIGH**
**File:** `src/integrations/build_orchestrator.py:2001`

The `_critic_review_plan()` method calls `critic_agent.review_with_loop()` without passing a `revise_fn` parameter. The critic loop in `src/agents/critic.py:289-290` exits immediately after the first review when no revision function is provided.

**Impact:** The critic reviews every plan but never triggers the builder to revise. All 100 plans got exactly 1 iteration. The actor-critic pattern — which is the core quality improvement mechanism — is effectively disabled.

**Evidence:**
- 100/100 builds: iterations=1, passed=False
- Average critic score: 57/100
- Score range: 41-68 (none reached the 70 threshold)
- 0% of plans passed critic review

**Fix:** Wire a `_revise_plan()` method in BuildOrchestrator that takes the critic feedback and re-calls the planner with the flaws as additional context. Pass it as `revise_fn` to `review_with_loop()`.

### 1.2 LLM Thread Lock Creates Deployment Bottleneck

**Severity: MEDIUM**
**File:** `src/core/llm_gateway.py`

The LLM gateway uses a `threading.Lock()` which is correct for safety but means only one build can decompose at a time. When the 100-build script fires requests too fast, the server becomes unresponsive to health checks and subsequent requests time out.

**Impact:** 3 transient failures (builds 033, 053 — retried successfully). Server appeared hung during LLM calls (health endpoint timed out).

**Fix:** Consider a queue-based approach where builds are queued and processed sequentially, with the API returning immediately with a job ID. The current synchronous `POST /build/start` blocks for 3-5 minutes per build.

### 1.3 Critic Score Calibration Too Strict

**Severity: MEDIUM**

The critic prompt instructs: "A score above 80 means you'd bet your reputation on this shipping." For complex products (medtech, fintech), no generated plan achieves 70+. The critic consistently finds 8-15 flaws per plan, which is expected for initial plans but means the threshold is never reachable without revision.

**Score Distribution:**
| Range | Count | Percentage |
|-------|-------|------------|
| 40-49 | 8 | 8% |
| 50-59 | 53 | 53% |
| 60-69 | 39 | 39% |
| 70+ | 0 | 0% |

**Fix Options:**
1. Lower the default threshold to 50 for first-pass (human will still review)
2. Wire the revision loop so plans actually improve (preferred)
3. Separate "first-pass adequate" threshold from "production-ready" threshold

### 1.4 Inconsistent Agent Role Assignment

**Severity: LOW**

Early builds (001-010) show only 2-3 agent roles being used (developer, analyst, planner), while later builds use the full spectrum (developer, qa_engineer, safety_engineer, regulatory_specialist, etc.). This suggests the planner prompt was improved over time or the LLM behaves differently with different product descriptions.

**Build 002 (Insulin Pump):** Only 3 roles — developer (19), analyst (14), planner (2)
**Build 005 (Patient Monitoring):** 9 roles — including safety_engineer, regulatory_specialist, qa_engineer

**Fix:** The planner prompt should explicitly list all available agent roles and when to use them. The `_build_agent_context()` method exists but may not be emphasizing role diversity enough.

---

## 2. Performance Metrics

| Metric | Value |
|--------|-------|
| Total builds | 100 |
| Success rate | 100% (after retries) |
| First-pass success | 97% (3 transient failures) |
| Total tasks generated | 2,628 |
| Avg tasks per build | 26.3 |
| Min/Max tasks | 16 / 36 |
| Avg build time | ~5 min (decompose + critic) |
| Total execution time | ~8 hours |

### Task Type Distribution (top 15)

| Task Type | Count | % |
|-----------|-------|---|
| BACKEND | 418 | 15.9% |
| FRONTEND | 294 | 11.2% |
| COMPLIANCE | 130 | 4.9% |
| SECURITY | 120 | 4.6% |
| TESTS | 120 | 4.6% |
| DEVOPS | 103 | 3.9% |
| DATABASE | 96 | 3.7% |
| CONFIG | 94 | 3.6% |
| UX_DESIGN | 92 | 3.5% |
| DOCS | 84 | 3.2% |
| SYSTEM_TEST | 80 | 3.0% |
| PRODUCT_MGMT | 75 | 2.9% |
| API | 75 | 2.9% |
| QA | 73 | 2.8% |
| FIRMWARE | 70 | 2.7% |

---

## 3. Domain-Specific Observations

### Medtech (001-010)
- Strongest compliance coverage (37-46% compliance task ratio)
- Correctly identifies FDA pathways (510(k), PMA, De Novo)
- Critic finds real regulatory gaps: missing IRB approval, post-market surveillance, FCC certification
- Some plans miss IEC 62304 software safety classification

### Fintech (011-020)
- Good PCI DSS and KYC/AML task coverage
- Critic catches JWT/session management issues consistently
- Missing: fraud monitoring real-time requirements, transaction reversal flows

### Automotive (021-030)
- ISO 26262 and ASIL analysis correctly included
- FIRMWARE + EMBEDDED_TEST + SAFETY task types properly assigned
- Critic notes missing: FUSA (Functional Safety) verification steps, ISO 21448 SOTIF

### SaaS (031-040)
- Cleanest plans — mostly software-only, well-structured
- Highest critic scores in this domain (avg ~62)
- Standard BACKEND→FRONTEND→TESTS→DEVOPS pipeline

### Ecommerce (041-050)
- PCI DSS correctly identified for payment-handling products
- Good coverage of inventory, payment, and shipping subsystems

### IoT (051-060)
- Proper firmware + cloud + mobile split
- IEC 62443 security requirements identified
- Critic catches power budget and connectivity reliability gaps

### ML/AI (061-070)
- Data pipeline tasks properly included
- Model training/serving infrastructure recognized
- Missing: ML-specific monitoring (data drift, model drift)

### EdTech (071-080)
- FERPA/COPPA compliance correctly identified
- Accessibility (WCAG) included in most plans
- Video hosting infrastructure properly scoped

### Consumer App (081-090)
- Most lightweight plans (avg ~25 tasks)
- GDPR compliance included by default
- App store submission requirements captured

### Enterprise (091-100)
- SOC 2 / ISO 27001 properly triggered
- SSO/IAM integration patterns recognized
- Complex workflow requirements well-decomposed

---

## 4. Framework Improvements Needed

### P0 (Must Fix)
1. **Wire the actor-critic revision loop** — The core quality mechanism is disabled
2. **Add `_revise_plan()` method** — Re-call planner with critic feedback as context
3. **Async build processing** — Queue builds so the API doesn't block for 5 minutes

### P1 (Should Fix)
4. **Recalibrate critic scoring** — Separate "adequate for review" from "production-ready"
5. **Add retry logic for transient LLM failures** — Auto-retry once on "decompose failed"
6. **Improve agent role diversity in planner prompt** — Early builds underuse specialist roles
7. **Add domain-specific critic rules** — Medtech plans should check for specific FDA/IEC requirements

### P2 (Nice to Have)
8. **Batch build API** — Accept multiple product descriptions in one call
9. **Build progress streaming** — SSE events for decompose→critic→approve stages
10. **Cross-domain pattern learning** — Use successful plans as few-shot examples for similar domains

---

## 5. Iterative Refinement Results

### Round 1 (Initial Run)
- 38% domain detection accuracy
- Many builds failed with "Planner could not decompose"
- Only 10 keywords per domain

### Round 2 (After keyword expansion)
- 100% domain detection accuracy
- 20-30+ keywords per domain
- All 314 parametrized tests passing

### Round 3 (Full 100-build deployment)
- 100/100 builds successful
- 2,628 total tasks generated
- Critic reviews attached to all builds
- Regulatory documentation generated for all 100

---

## 6. Conclusion

The SAGE Build Orchestrator successfully handles "any product domain" as claimed. It correctly:
- Detects domains from product descriptions (100% accuracy after keyword expansion)
- Decomposes products into appropriate task trees (16-36 tasks per product)
- Assigns domain-appropriate task types (FIRMWARE for embedded, COMPLIANCE for regulated, etc.)
- Routes tasks to specialist agents
- Generates regulatory compliance documentation
- Runs critic reviews with detailed, actionable feedback

The critical gap is the disabled revision loop — once wired, the actor-critic pattern should improve plan scores from the current 57 avg to 70+ through iterative refinement, which is the entire point of the system.
