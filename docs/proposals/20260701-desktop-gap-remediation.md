# SAGE Desktop — Gap Remediation (2026-07-01)

Source: three parallel code reviews (desktop UX, demo-path robustness incl. a live
sidecar run against an external solution, framework gaps). This doc is the tracked
work list. Status markers: `[ ]` todo, `[~]` in progress, `[DONE]`.

Context: sage-desktop is becoming the **only** interface. A VC + QA demo runs this
weekend driving the external `poseengine` solution (`C:\sandbox\SAGE\solutions\poseengine`)
via `make desktop-dev-solution`.

---

## Tier 1 — Demo blockers (fix first)

- [DONE] **T1.1 `llm.get_info` crashes on a real gateway.** Fixed: handler no longer calls the
  nonexistent `gw.list_providers()`; uses new `llm_gateway.SWITCHABLE_PROVIDERS` constant (with a
  hardcoded fallback). Root-cause fix: sidecar test fakes now mirror the real `LLMGateway` surface;
  added a `MagicMock(spec=LLMGateway)` regression test that physically cannot expose methods the
  real class lacks — catches this bug class at test time, not via a live run.
- [DONE] **T1.2 Status LLM tile always "unknown".** Fixed: `handlers/status.py._llm_info` now reads
  the provider from `get_provider_name()` (get_model_info has no `provider` key). Status test fake
  corrected to the real surface.
- [DONE] **T1.3 `SAGE_PYTHON` never set by Makefile.** Both `desktop-dev` and `desktop-dev-solution`
  now export `SAGE_PYTHON=$(abspath $(PYTHON))` so the sidecar always spawns the venv interpreter.
- [DONE] **T1.4 Approvals card decides blind.** `ApprovalCard` now shows an expandable payload
  viewer (`<details>` + `<pre>` JSON), a Reversible/Irreversible badge, and a two-step reject that
  captures optional feedback (`onReject(trace_id, feedback)`); the page forwards feedback to the RPC
  and shows a success confirmation after each decision.
- [DONE] **T1.5 New proposals not discoverable.** `useApprovals` polls (`refetchInterval: 5000`);
  the sidebar shows a red pending-count badge on the Approvals entry.
- [DONE] **T1.6 Constitution page spins forever on error.** Error branch now precedes the
  loading/`!draft` guard.
- [ ] **T1.7 Silent-failure pages.** Backlog, Costs, Compliance, Eval, Goals, Knowledge, Onboarding,
  Collective swallow query/mutation errors. Backlog worst (failed submit just sits there).
- [MITIGATED] **T1.8 Startup latency ~41s** (measured live). Diagnosis refined: the dominant cost
  is the one-time `torch`/sentence-transformers **process import (~31s)** plus ~30 HuggingFace
  network revalidation calls — NOT the second `VectorMemory` instance (collapsing it saves only a
  few seconds). Demo-day guarantee is operational and zero-code-risk: **warm-run once** (pre-pays
  the torch + model load and populates the HF cache), then run with **`HF_HUB_OFFLINE=1`** (removes
  the ~30 network revalidations). `SAGE_MINIMAL=1` gives near-instant startup if semantic Knowledge
  search isn't being demoed (keyword fallback). **Deferred (post-demo):** making
  `VectorMemory.__init__` truly lazy (defer embedding load to first query/add) — a framework-wide
  change to a widely-imported singleton; not worth the pre-demo risk for a few seconds when the
  operational path removes the larger network cost. See pre-demo checklist below.

## Tier 2 — Product gaps ("only interface" credibility)

- [ ] **T2.1 The loop doesn't loop.** `TaskWorker` constructed (`queue_manager.py:1216`) but never
  `.start()`ed in production; queued tasks persist and sit forever. No autonomy runtime runs
  monitor + scheduler + worker together in the normal process.
- [ ] **T2.2 Inbox doesn't notify.** Poll-only UI; only push event is crash status. Operator never
  learns a new proposal landed.
- [ ] **T2.3 Goals can't be marked done.** `useUpdateGoal` + Rust command wired; `Goals.tsx` imports
  only list/create/delete.
- [ ] **T2.4 Cost recorded per trace but invisible.** `llm_costs.trace_id` populated; nothing joins
  cost to a proposal in any UI.
- [ ] **T2.5 Audit drill-down missing on desktop.** One exact-match filter, fixed limit 100, traces
  not clickable; sidecar handler already supports more (limit/offset/action_type/trace_id).
- [ ] **T2.6 No `.sage` export/backup.**
- [DONE] **T2.7 Header titles missing for 10 routes.** Added `/analyze`, `/compliance`, `/costs`,
  `/workflows`, `/skills`, `/organization`, `/monitor`, `/goals`, `/eval`, `/hil` to `Header.tsx`.
- [ ] **T2.8 Built-but-dead capabilities** — `useBatchApprove`, `useApproval`, `useAuditByTrace`,
  `useAuditStats` wired, unused.

## Tier 3 — Polish / maturity (post-demo)

- [ ] **T3.1 Sidebar grouping** (21 flat entries → sections).
- [ ] **T3.2 App icon** is stock Tauri logo; no About/version surface.
- [ ] **T3.3 Undefined Tailwind shades** (`sage-400/300/800`) silently no-op.
- [ ] **T3.4 Two competing error-display systems**; 4 duplicated `errorMessage()` helpers.
- [ ] **T3.5 Relative timestamps, refresh consistency, pagination beyond Knowledge.**
- [ ] **T3.6 Audit record signing** (placeholder column never populated).
- [ ] **T3.7 Installer packaging** (bundle Python + `src/` + deps; largest deferred item).
- [ ] **T3.8 `window.prompt` in Collective** may be a no-op in WebView2; hardcoded actor identities
  (`operator@desktop`, solution "desktop").

---

## Pre-demo checklist (demo machine)

1. Warm-run once (populates HF cache, runs `.sage` migrations, creates `.collective`).
2. `SAGE_PYTHON` = venv python (or guaranteed PATH).
3. `claude -p "hi"` from `sage-desktop/` as demo user (trust-dialog gotcha).
4. Run make from Git Bash.
5. First Analyze click: 30–90s (synchronous CLI). Crash recovery single-shot.
6. `HF_HUB_OFFLINE=1` on demo day.
