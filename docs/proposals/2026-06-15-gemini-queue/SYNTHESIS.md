# SAGE Improvement Queue — Loop Results + Review Synthesis

**Date:** 2026-06-15
**Pipeline:** Gemini observed the platform → 6 loop-ready findings (`docs/SAGE_GEMINI_OBSERVATIONS.md`) → the **hardened Evaluator-Optimizer loop** (Claude optimizes sandboxed, Gemini sharpens a rubric + grades) produced a proposal per item → an **adversarial review workflow** (11 agents: review → refute → synthesize, each with repo access) verified every proposal against the live code.

> Every item here is a **PROPOSAL**. Nothing has been applied. A human decides what lands, through the approval gate. The candidate code is staged as `NN-*.proposal.txt`; the loop's per-iteration scores are in `NN-*.loop.log`.

## Verdicts

| # | Item | Dimension | Loop score | Review verdict | Conflicts |
|---|------|-----------|-----------|----------------|-----------|
| 4 | Header status/color/label consistency | visual-ui | 4.0 (not converged) | **REVISE** — closest to apply | shares `index.css` with #2 |
| 1 | Kill thread-locked gateway singleton | agent-framework | 3.0 (not converged) | **REVISE** | shares `llm_gateway.py` with #5 |
| 5 | Providers ABC + always-on tracing + retry | agent-framework | 3.0 (not converged) | **REVISE** | shares `llm_gateway.py` with #1 |
| 2 | UI primitives + tokens-via-Tailwind | web-reuse | 10.0 (converged) | **REVISE** | shares `index.css` with #4 |
| 3 | Single-source-of-truth + useProposals hook | web-reuse | 10.0 (converged) | **REJECT** — re-spec | — |
| 6 | Self-sharpening rubrics | agent-framework | — | **ALREADY DONE** (commit `af9aa95`) | — |

**Recommended human review/apply order: #4 → (#1 *or* #5, not both) → #2. #3 is out.**

## ⚠️ Meta-finding: trust the review, not the loop score

The loop's in-loop evaluator (Gemini) grades the candidate against the rubric **in isolation, with no access to the repo**. So it rewarded plausible-looking code that does not actually fit the codebase:

- **#3 scored 10/10 "converged"** but is a **REJECT** — it imports `fetchProposals`, `fetchProject`, `fetchAuditLog` (none exist), calls `approveProposal`/`rejectProposal` with the wrong arity, imports a `components/shared/ToastContainer` that is never created, and misroutes rejection feedback through the shared card's 2-arg `onReject`. 8+ compile failures.
- **#2 scored 10/10 "converged"** but is build-breaking — imports `class-variance-authority` (absent from `web/package.json`) and its full `index.css` rewrite silently deletes `@keyframes sage-spin / sage-cursor-blink / sage-dot-bounce` that `ImportFlow`, `Chat`, and `ChatPanel` actively use.

The independent review stage (Read/Grep against the live repo) caught all of this. **Takeaway:** the Evaluator-Optimizer score is a *necessary but not sufficient* gate; the repo-aware adversarial review is what makes a proposal safe to consider. (A future loop hardening could give the in-loop evaluator repo access, e.g. let Gemini `grep` the imports it depends on.)

## Per-item detail

### #4 — Header status/color/label consistency · REVISE (cleanest, apply first)
- **Real, regression-free, scope-faithful** single-file rewrite of `Header.tsx`. All props/handlers preserved (`onOpenPalette`, chat toggle, Ctrl/Cmd+J). The loop's "fails to preserve original props" critique (score 4.0) was **unfounded** — the review verified it false.
- **Owed before apply:** the candidate references a `--color-*` token vocabulary (`--color-status-success`, `--color-surface`, …) that **does not exist** in `index.css` (which defines only `--sage-*`). It renders correctly *only* through `var(--token, #hexfallback)` fallbacks. To genuinely meet the "via tokens" goal, **add those tokens to `:root` in `index.css`**.
- Apply this first because it touches `index.css` — landing its small edit before any `index.css` rewrite avoids clobbering.

### #1 — Kill thread-locked gateway singleton · REVISE
- **Complete, well-engineered** full rewrite of `llm_gateway.py`: removes the global inference lock, gates only local-GPU lanes with a real `Semaphore` (cloud providers → `nullcontext`, fully concurrent), makes the gateway injectable while keeping the module-level `llm_gateway` instance for all ~38 call sites. Also fixes a pre-existing `generate_for_task` provider-swap race.
- **Owed before apply (the loop never converged for exactly these reasons):**
  - Breaks 3 tests that hard-code the OLD contract — `test_singleton_pattern` (identity), `test_class_lock_still_exists_for_singleton`, `test_provider_concurrency_map_exists` (expects gemini/claude > 1). Update them + `docs/TESTING.md` UT-LLM-001 in the same change.
  - **Hidden production regression the review caught:** `proposal_executor.py:71` does `gw = LLMGateway()` then mutates `gw.provider` to switch the model at runtime (reachable via `POST /llm/switch`). Under the old singleton that mutated the shared live instance; with the singleton gone it mutates a throwaway → the runtime switch becomes a **silent no-op** (its e2e test mocks the gateway, so CI won't catch it). Must be fixed alongside.

### #5 — Providers ABC + always-on tracing + retry · REVISE
- **Good architectural direction** (provider ABC, injectable mock, pluggable tracing, backoff retry) — aligned with the documented intent.
- **Owed before apply:** whole-module rewrite **drops module-level `generate_parallel`** (used by `src/agents/critic.py:520/554/587` — untouched production code → `ImportError` at import) and **`_init_langfuse`/`_langfuse_client`** (asserted by `test_llm_gateway.py`). Also switched config from YAML (`config/config.yaml`) to `config.json` → real config silently not loaded, and rewrote `_MODEL_LIMITS` with stale model IDs. Re-export shims + restore YAML before it can land.

### #2 — UI primitives + tokens-via-Tailwind · REVISE
- **Token mapping is correct and hex-free** (`tailwind.config.ts` maps every `--sage-*`; Card/Modal/Select consume `bg-sage-*` etc.). Modal has focus-trap + portal + Escape + scroll-lock.
- **Owed before apply:**
  - **Build break:** the 3 new primitives `import { cva } from 'class-variance-authority'`, which is **not** in `web/package.json` (repo uses `clsx` + `tailwind-merge`). Add the dep *or* drop CVA to match repo convention.
  - **Dropped keyframes:** the full `index.css` rewrite deletes `@keyframes sage-spin / sage-cursor-blink / sage-dot-bounce` — confirmed live consumers in `ImportFlow.tsx`, `Chat.tsx`, `ChatPanel.tsx`. Preserve them.
  - **Paradigm mismatch:** the goal said match `Button.tsx`'s inline-`var()` convention; the candidate introduces CVA + Tailwind utility classes instead, and omits `Button.tsx` (a named target).
  - Trim the `index.css` rewrite to value-preserving token swaps (it changed scrollbar colors), and rebase onto #4's edit.

### #3 — Single-source-of-truth + useProposals hook · REJECT (re-spec, don't patch)
- Looks complete (adds `lib/date.ts`, a `useProposals` hook, rewrites both pages) but is built on **imports and signatures that don't exist**: `fetchProposals` (real: `fetchPendingProposals`), `fetchProject`/`fetchAuditLog` (absent), 3-arg `approveProposal`/`rejectProposal` (real: 1-arg/2-arg; 3-arg variants are `*Full`), a `components/shared/ToastContainer` it imports in **both** pages but never creates, wrong paths for `ModuleWrapper`/`ActiveAgentsPanel`, and a misrouted `onReject(traceId, approver, feedback)` vs the shared card's `(traceId, feedback)`. It also **deletes working Dashboard behavior** (action_type grouping, approving-as identity, per-group batch approve, `useProjectConfig`, Live Console link). 8+ independent compile failures → redo from a narrow spec.

## Conflicts (do not apply blindly)

1. **#1 ↔ #5 both rewrite `src/core/llm_gateway.py`** and partly contradict. Pick ONE as the base. Either take #5's ABC/tracing/retry structure and fold in #1's concurrency change, or apply #1 and reject #5. Not both as-is.
2. **#2 ↔ #4 both modify `web/src/index.css`** (#2 full rewrite, #4 targeted edit). Apply **#4 first**, then rebase #2 onto the result.
3. **#3 is reject**, so no live web conflict with #2 — but if #3 is re-specced later, re-check overlap with #2's new primitives.

## How this was produced (reproducible)
- Loops: `make optimize` / `python -m src.core.evaluator_optimizer` per item, `--max-iterations 2`, with the right context file(s). Hardened loop = sandboxed optimizer (no repo writes) + rubric sharpening + STDIN prompt + 600s gen timeout (commits `af9aa95`, `c13289b`).
- Review: an 11-agent adversarial workflow (`C:/tmp/sage_loop/review_workflow.js`) — per item: reviewer → adversarial verifier (tries to refute the verdict, defaults conservative) → final synthesis.
