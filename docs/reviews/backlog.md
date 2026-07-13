# SAGE Feature Review — `backlog`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/backlog.py`  
**Frontend:** `Backlog.tsx`  
**Review time:** 78s

---

## Verdict
The backlog feature is only partly usable today because while users can list and submit requests, the user interface completely lacks any controls to trigger the planning workflow, and the backend's planning implementation bypasses the SAGE framework's compliance audit trail by performing raw SQL database modifications.

**Works:** partly
**Score:** 4/10

## What Actually Works
Based on the live runtime evidence and provided source code:
* **Listing Feature Requests (`backlog.list`):** The list query successfully returns a list of seeded/submitted feature requests. The live RPC output successfully fetched two pending requests with IDs `5aff2b2c-9218-435a-93ef-5a5539e3a1f7` and `3ae9ab02-b031-4cbe-b783-82c28a17ab14`.
* **Request Scope Toggling (Frontend):** In `Backlog.tsx`, switching between `"solution"` and `"sage"` updates local state and refetches items using `useFeatureRequests({ scope })`.
* **Form Submission (Frontend -> Backend):** The submission form in `Backlog.tsx` captures title, description, and active scope, submitting them through `submit.mutate`. On the backend, `submit_feature_request` handles the parameters, applies defaults (priority: `"medium"`, requested_by: `"anonymous"`), and persists them to `store.submit()`.
* **Reviewer Actions:** The frontend `handleAction` invokes `update.mutate`, which maps to `update_feature_request` on the backend. This successfully calls `store.update(fid, action=action, reviewer_note=note)` and handles standard errors (`RPC_INVALID_PARAMS` and `RPC_FEATURE_REQUEST_NOT_FOUND`).

## System-Level Findings

### 1. Bypassing Compliance Audit Trail with Raw SQL (High Severity)
In `backlog.py`, when `plan()` is executed, it calls `_update_request_status()`. This function imports `sqlite3` and executes a raw SQL write directly against `store.db_path`. This completely bypasses the `FeatureRequestStore`'s wrapper and abstraction layer. In SAGE—where every status transition is a matter of regulatory compliance—direct database writes circumvent audit logs, event hooks, and lifecycle state-machine validations.

### 2. Complete Frontend Decoupling of Planning Flow (High Severity)
The backend implements a highly specialized `plan` RPC endpoint. For SAGE-scoped requests, it builds a GitHub issue URL. For solution-scoped requests, it orchestrates an LLM via `PlannerAgent` and creates a Human-In-The-Loop (HITL) proposal using `proposal_store`. However, `Backlog.tsx` does not import, reference, or invoke this `plan` endpoint. The operator cannot promote any backlog item to an executable plan through the UI; it is a dead-end feature.

### 3. SQLite Concurrent Database Locking (Medium Severity)
`_update_request_status` initializes an independent connection using `sqlite3.connect(db_path)` while the main `store` instance is actively holding context or transactions. In high-concurrency environments or multi-threaded servers, this uncoordinated write-access path can trigger database locked errors (`sqlite3.OperationalError: database is locked`) and crash the planning thread.

### 4. Brittle Startup Dependency Injection (Low Severity)
`_store` and `_proposal_store` are global references that are expected to be injected by the app coordinator at boot time. If an RPC is triggered before initialization completes, the module throws un-hydrated `RpcError` exceptions (`RPC_SAGE_IMPORT_ERROR`), showing a lack of defensive lazy-loading or connection pool verification.

## Usability Findings

### 1. Missing "Plan" Actions in Backlog Rows
An operator navigating the backlog can view items but has no interactive affordance to trigger a plan. Row controls are strictly limited to the `onAction` reviewer actions (approve, reject, complete).

### 2. No Duplicate Submission Prevention
The live runtime evidence reveals two identical feature requests: `"Board renders 4-in-a-line win"` with matching descriptions, submitted two minutes apart (19:34:42 vs 19:36:35). The frontend does not check for duplicates or warn the operator before allowing multiple identical entries to pollute the compliance backlog.

### 3. Implicit and Inflexible Submission Scope
When submitting a request, the scope is implicitly tied to the currently selected view tab (`scope` state variable). An operator cannot easily submit a "SAGE framework" improvement while looking at the "Solution backlog" tab without clicking back and forth.

### 4. Opaque Planning Error Feedback
If the LLM planning engine fails (or if the sidecar fails to respond), the backend raises generic `RPC_SIDECAR_ERROR` exceptions (`"planning failed: {exc}"`). The UI does not provide helpful remediation instructions (such as "Please clarify the requirements in your description").

## Top 3 Fixes (optimizer-ready)

### 1. Integrate Plan Execution in Frontend UI
* **Task:** Integrate the `plan` RPC endpoint on the frontend. Create a `usePlanFeatureRequest` hook in `src/hooks/useBacklog.ts` to call the `plan` RPC. Update `FeatureRequestRow.tsx` and `Backlog.tsx` to display a "Generate Plan" button for pending backlog items. If the scope is `"sage"`, display the returned GitHub issue link as an actionable external URL. If the scope is `"solution"`, show a success toast indicating that the HITL proposal has been queued.
* **Acceptance Criteria:**
  - Verify that clicking "Generate Plan" on a `"sage"` request shows the GitHub link.
  - Verify that clicking "Generate Plan" on a `"solution"` request successfully calls the backend `plan` endpoint, updates the request status, and disables the button.

### 2. Route Status Transitions Through Store Wrapper
* **Task:** Eliminate raw SQL writes in `backlog.py`. Remove `_update_request_status` and `import sqlite3`. Refactor `FeatureRequestStore` to expose a method for safe, audited status updates (or extend `store.update()` to accept internal transitions like `in_planning` and `github_pr`). Update `backlog.py`'s `plan()` to utilize this store method, preserving compliance audit logs.
* **Acceptance Criteria:**
  - No raw `sqlite3` imports or connections are present in `backlog.py`.
  - All status transitions triggered by `plan()` are successfully written to the database and verifiable via standard `store.list()` queries.

### 3. Implement Backlog Deduplication and Validation
* **Task:** Add client-side validation to the submission form in `Backlog.tsx`. Ensure the "Submit" button is disabled unless the title has $\ge 5$ characters and the description has $\ge 10$ characters. Before posting, check the current `list.data` array for any matching titles. If a duplicate title exists, block submission and prompt the user with a confirmation dialog: *"A request with this title already exists. Do you still want to submit?"*
* **Acceptance Criteria:**
  - Form validation blocks trivial/empty submissions.
  - Submitting an exact duplicate title triggers the warning dialog, preventing accidental double-submits.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    backlog.list
  -> [{"id": "5aff2b2c-9218-435a-93ef-5a5539e3a1f7", "module_id": "general", "module_name": "General", "title": "Board renders 4-in-a-line win", "description": "Win detection must highlight the winning line.", "priority": "medium", "status": "pending", "requested_by": "anonymous", "scope": "solution", "created_at": "2026-07-13T19:36:35.984514+00:00", "updated_at": "2026-07-13T19:36:35.984514+00:00", "reviewer_note": "", "plan_trace_id": ""}, {"id": "3ae9ab02-b031-4cbe-b783-82c28a17ab14", "module_id": "general", "module_name": "General", "title": "Board renders 4-in-a-line win", "description": "Win detection must highlight the winning line.", "priority": "medium", "status": "pending", "requested_by": "anonymous", "scope": "solution", "created_at": "2026-07-13T19:34:42.025973+00:00", "updated_at": "2026-07-13T19:34:42.025973+00:00", "reviewer_note": "", "plan_trace_id": ""}]
```
