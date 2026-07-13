# SAGE Feature Review — `eval`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/eval.py`  
**Frontend:** `Eval.tsx`  
**Review time:** 68s

---

## Verdict
The `eval` feature is not usable today by a real operator in a production environment due to critical system-level configuration leaks and a frontend UX that acts as a complete dead end for troubleshooting.

**Works:** partly
**Score:** 3/10

---

## What Actually Works
Based on the live runtime evidence:
* **RPC Layer & Routing:** The RPC endpoints `eval.list_suites` and `eval.history` are registered and fully functional, returning successful `[LIVE OK]` status codes rather than timeout or routing errors.
* **Database & Runner Initialisation:** Calling `eval.list_suites` and `eval.history` did not throw `RPC_SAGE_IMPORT_ERROR` ("eval runner unavailable"). This proves that `_runner` is successfully initialized and the database connection to the solution's `eval_runs.db` was established.
* **Frontend Component Scaffolding:** `Eval.tsx` successfully binds the UI to the underlying queries (`useEvalSuites`, `useEvalHistory`), gracefully renders the empty states ("No eval suites available", "No runs yet."), and includes basic UI elements like loading texts and standard `ErrorBanner` components.

---

## System-Level Findings

### 1. Global Configuration Leak & Broken Isolation (High Severity)
According to the correctness note in `eval.py`, `EvalRunner.list_suites()` and `run()` resolve the target suites directory by calling `_get_evals_dir()`. This method reads the framework-global `src.core.project_loader.project_config` singleton instead of an injectable per-solution instance. 
* **Impact:** Because this global configuration is built at import time using `SAGE_PROJECT` or auto-discovery (and not the sidecar's `--solution-name`), listing or running suites will silently resolve against the wrong solution's `evals/` directory unless `project_config.reload(solution_name)` is explicitly called in `app._wire_handlers`. This breaks multi-tenant/solution isolation entirely.

### 2. Lack of Audit Integration & Compliance Violation (Medium Severity)
SAGE's core law is *"Agents propose. Humans decide."* with the audit log acting as the compliance record.
* **Impact:** While evaluations run active agent configurations (which may execute actions or generate proposals), these runs are stored in isolation inside a local `.sage/eval_runs.db` database. There is no evidence of integration with the system's global compliance/audit log or any HITL approval gate. Running agents inside an unmonitored evaluation harness creates a blind spot where agent proposals escape human validation and bypass the audit trail.

### 3. Insufficient Database Resolution Diagnostics (Low Severity)
The live outputs for both `list_suites` and `history` returned empty arrays:
```json
{"suites": [], "count": 0}
{"history": [], "count": 0}
```
* **Unseeded vs. Broken:** From this evidence alone, we cannot definitively tell if the system is broken or merely unseeded (meaning no YAML files exist). 
* **How to verify:** We would check the directory `solutions/<active_solution_name>/evals/` on disk. If YAML files are present there but the RPC returns empty, the configuration leak (Finding 1) is actively occurring, causing the runner to look in the default or wrong solution directory. If the directory on disk is physically empty, the system is simply unseeded.

---

## Usability Findings

### 1. Total Failure Analysis Dead End (Major Gap)
The frontend `Eval.tsx` only renders high-level summary statistics for completed runs and history entries:
```tsx
{entry.passed_cases}/{entry.total_cases}
<span>{entry.mean_score.toFixed(1)}</span>
```
* **Impact:** A real operator cannot click on a run or expand a row to see *which* test cases failed, what the agent actually proposed, or what errors were thrown. Summary metrics are useless for debugging regressions; the UI is a complete dead end.

### 2. Stale History UI on Run Completion (Moderate Gap)
When an operator clicks the "Run" button, the mutation `run.mutate(name)` is triggered, but there is no mechanism to invalidate the `history` query upon completion.
* **Impact:** After a successful evaluation run, the "History" list remains stale. The operator is forced to manually reload the page or navigate away and back to see the new entry in the history table.

### 3. Missing Loading and Error Indicators for History
The suites list has explicit loading states (`suites.isLoading`), but the history section lacks loading states entirely. If the history RPC call is slow or hangs, the user is presented with a blank box containing no loading spinner or skeleton state, creating a unresponsive user experience.

---

## Top 3 Fixes (optimizer-ready)

### 1. Reload Project Configuration inside App Handlers Wiring
* **Task:** In the sidecar handler initialization code (where `app._wire_handlers` is defined), import the global `project_config` singleton from `src.core.project_loader` and call `project_config.reload(solution_name)` using the incoming `--solution-name` argument prior to constructing and injecting the `EvalRunner` instance.
* **Files:** Sidecar wiring entrypoint (e.g., `app.py` or similar setup script), `eval.py`.
* **Acceptance Criteria:** Start the sidecar with `--solution-name custom-test`. Create an evaluation file under `solutions/custom-test/evals/test.yaml`. Assert that calling the `eval.list_suites` RPC successfully returns `["test"]` and does not default to the global project's path.

### 2. Extend History Schema and RPC for Detailed Case Results
* **Task:** Modify the `EvalRunner.get_history` method and the `eval.history` RPC handler in `eval.py` to support retrieving detailed test case run traces. Add an optional `run_id` parameter to the `eval.history` handler. If provided, query `eval_runs.db` for all individual test cases belonging to that run (including case name, status, score, raw agent output, and error logs) and return them in a structured `cases` list.
* **Files:** `eval.py`, `src/core/eval_runner.py` (or equivalent backend runner file).
* **Acceptance Criteria:** Calling `eval.history({"run_id": "some-run-uuid"})` returns a payload with a `cases` array containing execution details for every test case in that run. Write a backend unit test verifying that individual case assertions are persisted to `eval_runs.db` during a run and successfully retrieved by the updated RPC.

### 3. Build Collapsible Run Details & Auto-Invalidation in Frontend
* **Task:** Update `Eval.tsx` to automatically refresh the history query when an evaluation completes, and allow users to view detailed test case outputs:
  1. In the `useRunEval` mutation, add an `onSuccess` hook that invalidates the `useEvalHistory` React Query cache.
  2. Implement an expandable details section (accordion) for each row in the history list. When expanded, trigger a query to fetch the individual test case results for that `run_id` (using the updated RPC from Fix 2).
  3. Render failing test cases in red with their associated error traces and agent proposals.
* **Files:** `Eval.tsx`
* **Acceptance Criteria:** Triggering an evaluation run automatically appends the finished run to the history list without requiring a page reload. Clicking on any run row in the history list successfully expands the UI to show a list of specific test cases, clearly highlighting which ones failed and showing their failure logs.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    eval.list_suites
  -> {"suites": [], "count": 0}

[LIVE OK]    eval.history
  -> {"history": [], "count": 0}
```
