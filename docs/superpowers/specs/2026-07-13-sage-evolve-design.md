# SAGE Evolve — Design

**Date:** 2026-07-13
**Status:** design, pending approval
**Debated by:** Claude (author) and Gemini (adversarial critic). The debate and its
reconciliation are recorded in §7 — the disagreement is part of the design.

---

## 1. Goal

Point SAGE's optimizer/critic loop at **any project** (first target: pose-engine), with a
**panel of models on both sides**, applying the loop at **every level of work** — from
deriving the team/org structure, to stabilizing each component, to integrating the system.

The organizing thesis, stated by the operator:

> Break the system into small components, let components become stable, then integrate.
> At every level of work let there be a critic and optimizer loop.

## 2. Why (the problem this solves)

The 2026-07-13 audit found SAGE's own failure mode, and it is not a coding problem:

- 24 desktop features, **none ever declared done**; 21/24 rated "partly working".
- Four handlers (`health.py`, `knowledgesync.py`, `activity.py`, `agentrun.py`) written,
  left mid-air, **never committed**. `_PROBE_POOL` was undefined because `health.py` was
  abandoned mid-write — nothing ever compiled it.
- `logs.py` written but **never registered**; `Console.tsx` imports an API that doesn't exist.
- The critic hallucinated a *"Fatal Python Syntax Error"* in a file that compiles cleanly,
  and scored it 1/10 — **the same fabricated detail across two independent runs**.
- A timed-out critic recorded a **phantom 0.0**, which read as "the optimizer produced garbage."

Two root causes: **no definition of done**, and **instruments that lie**. This design attacks
both. Every level gets a mechanical evidence gate (ground truth) *and* a model panel
(judgement), and nothing is accepted on a model's opinion alone.

## 3. What already exists — do NOT rebuild

Verified in the codebase:

- `EvaluatorOptimizerRunner` already supports `evaluator_pool` (N critics) with robust
  **weighted-median** aggregation.
- `OllamaProvider` exists, and the loop's provider builder already handles `"ollama"` — a
  **local Qwen critic needs configuration, not code**.
- `ProposalStore` + HITL gate + audit log + vector memory work end-to-end (verified:
  `PROPOSAL_APPROVED`, `PROPOSAL_REJECTED`, `FEEDBACK_LEARNING`, and feedback retrievable
  from memory).
- Best-of-N optimizer competition exists in `src/agents/coder.py` / `developer.py`.

The genuine gaps are: the loop is **hardcoded to SAGE** (`SAGE_ROOT` + a SAGE-only task
catalogue), there is **no evidence gate**, there is **no component map or org derivation**
(`org.yaml` does not exist; `OrgLoader` degrades to empty), and the optimizer side has **no
panel**.

## 4. Architecture — one primitive, three levels

The loop is **one reusable primitive**, configured differently at each level. Every level has
the same shape:

```
OPTIMIZER PANEL  ->  EVIDENCE GATE  ->  CRITIC PANEL  ->  HITL
 (N models,          (mechanical,       (M models,        (human
  best-of-N,          free, runs         cross-vendor,      decides;
  tournament)         FIRST)             median score)      Law 1)
```

**The evidence gate runs before any critic sees a candidate.** It is free, mechanical, and
eliminates broken candidates up front. Critics may only score **against the evidence bundle**;
a claim the evidence contradicts is discarded. This is the direct fix for the fabricated
syntax error and the phantom 0.0.

| Level | Optimizers propose | Evidence gate (hard) | Critics judge |
|---|---|---|---|
| **0 — Decompose / Org** | component map, agent roster, `org.yaml` | the proposed test & probe commands **actually execute** | does the map match the real repo? are the roles coherent? |
| **1 — Component** | a change to one component | component tests pass, typecheck clean, live probe responds, **and system tests still green** | correctness, design, compliance |
| **2 — System** | integration-level changes | e2e suite passes, the app boots | emergent / integration defects |

**Promotion rule (definition of done):**

```
stable(component)  <=>  evidence.passed  AND  median(critic_scores) >= threshold
```

A component **cannot** be declared stable while breaking the system suite. This merges the
operator's component-first thesis with Gemini's objection that isolated stability is a fantasy.

### Level 0 is what makes the system bootstrappable

Applying the loop to the decomposition itself closes the failure mode Gemini insisted on: a
bad component map poisons everything downstream. Here, the map is not trusted — SAGE
**executes the test and probe commands it proposes and shows the real output**. A map whose
commands do not run is rejected before a human ever sees it.

This is also the org/team feature: one pass over the repo yields both the component map and
the roster that owns it.

## 5. Modules (small, isolated, independently testable)

| Module | Responsibility | Depends on |
|---|---|---|
| `src/core/model_panel.py` | Build N providers from config (Claude / Gemini / Ollama-Qwen). Selection = best-of-N for optimizers; robust median for critics. | existing `llm_gateway` |
| `src/core/evidence.py` | `EvidenceRunner` → `EvidenceReport{passed, checks[], raw_output}`. Runs tests / typecheck / probe in an **isolated worktree**. | git worktree, subprocess |
| `src/core/project_decomposer.py` | Scan a target repo → propose `ComponentMap` + roster + `org.yaml`; verify proposed commands execute. | `model_panel`, `evidence`, `ProposalStore` |
| `src/core/evolve.py` | Orchestrator: level 0 → level 1 per component → level 2. | all of the above |
| `evaluator_optimizer.py` (extend) | Add `optimizer_pool` (tournament) + evidence injection into critic prompts. | — |

**Critical correction from the debate:** optimizer outputs are **selected, not aggregated**.
You can median three *scores*; you cannot median three *refactorings*. The optimizer panel is
a winner-take-all tournament scored by the critic panel.

## 6. Configuration — panel policy is the operator's choice

Full panel is the **default**. The operator selects the policy per level or per task, exactly
as they select the org structure. Nothing is hardcoded.

```yaml
evolve:
  target: /path/to/pose-engine        # any repo; SAGE stays domain-blind
  solution: pose_engine               # data lands in <solution>/.sage/
  panel_policy: full                  # full | cascade | single
  policies:
    full:      # DEFAULT — maximum rigor
      optimizers: [claude-opus-4-8, gpt, qwen-local]
      critics:    [claude-sonnet-4-6, gemini-3.5-flash, qwen-local]
    cascade:   # cost-bounded: free gate -> free local critic -> paid critics on survivors
      optimizers: [claude-opus-4-8]
      critics:    [qwen-local, gemini-3.5-flash, claude-sonnet-4-6]
      escalate_on: contested          # paid critics only when cheap ones disagree
    single:    # smallest tasks
      optimizers: [claude-opus-4-8]
      critics:    [gemini-3.5-flash]
  threshold: 8.0
  max_rounds: 3
```

This also delivers the **model bake-off**: the `full` policy runs Claude, GPT, and Qwen as
competing optimizers on identical tasks, judged by the same panel — producing the evidence
needed to answer "is Claude the right model?" with data rather than argument.

## 7. The debate — Claude vs Gemini (recorded)

Gemini scored the first draft **3/10**. Its hits, and the resolution:

| Gemini's objection | Verdict | Resolution |
|---|---|---|
| "Code cannot be median-aggregated — N optimizers is a winner-take-all fork, not an aggregation." | **Correct.** The draft lazily mirrored the critic panel. | Optimizer panel is an explicit **tournament** (best-of-N), not a median. |
| "Live probes on candidate code will pollute the environment — shared DBs, ports, race conditions." | **Correct.** | Every candidate is evaluated in an **isolated git worktree**. |
| "Combinatorial cost: N×M×components×rounds = hours and astronomical cost." | **Correct.** | Evidence gate (free) eliminates candidates before any model runs; `cascade` policy puts the **free local Qwen critic first**; operator picks the policy. |
| "Isolated component stability is a fantasy — integration forces interface changes back." | **Half correct.** | Tiers retained (focus + cost), but the **component gate includes the system suite** — stability cannot mean "green alone, broken together." |
| "HITL flood: the operator drowns in out-of-context micro-proposals." | **Fair risk.** | HITL fires **once per component at promotion** (not per iteration), and the proposal carries the full transcript plus integration evidence. |
| **INSISTED:** "Replace LLM-generated component mapping with a human-written `sage.yaml`." | **Rejected — with its concern absorbed.** | This would delete the requested feature (SAGE deriving team/org from the project), and it misreads the design: the map was never autonomous — it is a **HITL proposal**. The end state *is* a declarative config; the only question is who types the first draft. Gemini's real worry — a bad map poisons everything — is answered by **Level 0**: the decomposition is itself optimizer/critic'd, and its proposed commands must **actually execute** before the map is offered. |

## 8. Invariants (non-negotiable)

- **Nothing auto-applies.** Every artifact — component map, org.yaml, code change — goes
  through the HITL gate (Law 1).
- **Critics score only against evidence.** An unverifiable claim is dropped, not acted on.
- **Panels are cross-vendor.** No model grades its own output.
- **Evidence truncation must be labelled.** A silently truncated JSON blob previously caused a
  fabricated "malformed JSON / completely unusable" finding. Never hand a critic damaged
  evidence unlabelled.
- **The framework stays domain-blind.** No pose-engine specifics in `src/` (SOUL.md).
- **Rejections teach.** Feedback flows to vector memory, so the next decomposition is better.

## 9. Testing

- `model_panel`: fake providers; assert tournament selection and median aggregation.
- `evidence`: a component whose tests fail must NOT pass the gate; worktree isolation asserted.
- `project_decomposer`: a map with a non-executing test command must be rejected.
- `evolve`: a candidate that passes component tests but breaks the system suite must NOT be
  promoted to stable.
- End-to-end: run level 0 against a real small repo and assert a `ComponentMap` proposal
  reaches `ProposalStore`.

## 10. Out of scope (v1)

- Auto-applying approved changes (still human-applied).
- GPT provider wiring, if no OpenAI key is configured — the panel degrades to available models.
- Distributed/parallel execution across machines.
