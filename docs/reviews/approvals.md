# SAGE Feature Review — `approvals`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/approvals.py`  
**Frontend:** `Approvals.tsx`  
**Review time:** 76s

---

## Verdict
The approvals feature is only partly usable today because, while pending proposals can be successfully fetched and listed, critical system failures—such as a missing/failing audit logger or a failed code-diff rollback on rejection—are silently swallowed, allowing unauthorized executions and leaving unrejected dirty state on disk.

**Works:** partly
**Score:** 5/10

## What Actually Works
* **Pending Approvals Listing:** The live RPC call `approvals.list_pending` successfully fetched and returned one seeded pending analytical proposal (`trace_id: "42230073-f67c-42e9-bbe1-3f7163c6ac3e"`) indicating that the fetch loop and serialization of proposal records are functional.
* **Schema Mapping:** The backend translates the internal `ProposalStore` records to JSON format via `p.model_dump(mode="json")`, including full nested structures (e.g., `payload.analysis`).
* **Operator Sign-off Binding:** The backend automatically resolves `decided_by` using the sidecar operator context (`_operator()["name"]`), which prevents the frontend from forging a different user's signature.

## System-Level Findings

### 1. Critical Audit Log Bypass (Severity: High)
* **Finding:** In `_audit`, if the `_logger` is uninitialized (`_logger is None`) or if writing to the log raises an exception, the backend logs a warning/error but silently swallows the failure and returns. 
* **Impact:** The approval transaction completes and executes `_execute(p)` with zero compliance trail. This violates SAGE's Core Law ("Agents propose. Humans decide") because an unrecorded decision is indistinguishable from an un-gated agent bypass.

### 2. Silent Code Revert Failure on Rejection (Severity: High)
* **Finding:** When a `code_diff` proposal is rejected, the handler attempts to rollback the workspace changes using `_get_revert()(p)`. If this revert operation fails (`outcome["state"] == "failed"` or an exception is raised), SAGE logs an error but completes the rejection API call successfully.
* **Impact:** The backend reports the proposal as successfully rejected, but the actual rejected files remain modified in the working tree, bypassing the approval gate entirely.

### 3. State Desynchronization in Feature Tracking (Severity: Medium)
* **Finding:** In `_advance_linked_feature_request`, if the update to the SQLite database fails (e.g., database lock, invalid schema), the exception is swallowed via `except Exception` and logged as a warning.
* **Impact:** The operator's decision is applied, but the corresponding backlog item is left stranded in `"in_planning"` indefinitely, desynchronizing the desktop workflow from the core database state.

## Usability Findings

### 1. Hard Dead Ends in the UI
* **Finding:** In `Approvals.tsx`, the status banners and empty states tell the operator that "The decision is recorded in the Audit log" and "Approved and rejected decisions go to the Audit log," but there are no links, buttons, or navigation affordances to navigate to the Audit Log.
* **Impact:** The operator must manually click through unrelated tabs to verify compliance, causing unnecessary friction and creating a UI dead end.

### 2. Lack of Feedback Capture for Approvals
* **Finding:** In `Approvals.tsx`, the `onApprove` callback only passes `trace_id` to `approve.mutate`, entirely omitting the `feedback` parameter. However, `approvals.py`'s `approve()` handler accepts and logs `feedback`.
* **Impact:** Operators cannot supply context, justifications, or constraints during approvals, which limits compliance tracking to raw sign-offs without qualitative notes.

### 3. Transient Single-Action Success Banner
* **Finding:** The success banner is tied to the reactive states of the `approve` and `reject` mutation hooks (`approve.isSuccess`, `reject.isSuccess`).
* **Impact:** If an operator is working through a list of multiple approvals, deciding on a second item or refreshing the component immediately wipes out the confirmation banner of the first decision. There is no persistent "recent history" log within the view.

## Top 3 Fixes (optimizer-ready)

### 1. Enforce Atomic Audit Log Writes
* **Task:** Modify `approvals.py` so that `_audit` raises a blocking `RpcError` if `_logger` is `None` or if a database exception occurs, thereby stopping the transaction before any approval/rejection can execute.
* **Files:** `approvals.py`
* **Acceptance Criteria:**
  1. If `_logger` is `None`, calling `approve` or `reject` must immediately abort the transaction and raise a `RpcError` with code `RPC_INVALID_PARAMS` or a custom compliance code.
  2. If the call to `_logger.log_event` raises a database or system exception, the exception must propagate (or be wrapped), blocking `_execute(p)` and `_advance_linked_feature_request(p)` from running.

### 2. Escalate Code Revert Failures to the UI
* **Task:** Update the `reject` handler in `approvals.py` to abort or return a dedicated error structure if a `code_diff` revert fails, and modify `Approvals.tsx` to render a high-severity error banner instructing manual cleanup.
* **Files:** `approvals.py`, `Approvals.tsx`
* **Acceptance Criteria:**
  1. In `approvals.py`, if `outcome["state"] == "failed"` is returned by the revert job, raise a custom `RpcError` indicating the directory is in an unstable state.
  2. In `Approvals.tsx`, parse this revert failure error and display a persistent, prominent warning banner (e.g., yellow/red border) warning the operator that the rejected files are still dirty on disk.

### 3. Add Deep-Linking to Audit Log in UI
* **Task:** Add navigation links/buttons inside the `decided` status banner and the `isEmpty` state container in `Approvals.tsx` that route the operator directly to the Audit Log view.
* **Files:** `Approvals.tsx`
* **Acceptance Criteria:**
  1. The transient `decided` status banner contains a clickable action link (e.g., "View in Audit Log").
  2. The empty state ("Nothing pending...") contains a secondary action button to "Open Audit Log".

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    approvals.list_pending
  -> [{"trace_id": "42230073-f67c-42e9-bbe1-3f7163c6ac3e", "created_at": "2026-07-13T19:36:47.003020+00:00", "action_type": "analysis", "risk_class": "INFORMATIONAL", "reversible": true, "proposed_by": "desktop-operator", "description": "[AMBER] Move commit triggers a synchronous board state update that blocks the render thread for 12+ frames, causing the renderer's cached state to fall out of sync with the authoritative game state \u2014 likely a missing or deferred setState/render flush after the minimax search resolves.", "payload": {"log_entry": "ERROR: game loop dropped 12 frames on move commit; board state desynced from renderer.", "analysis": {"severity": "AMBER", "category": "performance", "root_cause_hypothesis": "Move commit triggers a synchronous board state update that blocks the render thread for 12+ frames, causing the renderer's cached state to fall out of sync with the authoritative game state \u2014 likely a missing or deferred setState/render flush after the minimax search resolves.", "recommended_action": "Audit the move-commit code path: ensure board state mutation and renderer update are atomic (or that the renderer subscribes reactively to state changes). If minimax runs on the main thread, move it to a worker/async context and flush the renderer only after state is confirmed committed. Add a frame-time profiler breakpoint at the commit callsite to isolate whether the stall is in AI computation, win-detection, or animation sequencing.", "affects_live_players": true, "trace_id": "42230073-f67c-42e9-bbe1-3f7163c6ac3e"}}, "status": "pending", "decided_by": null, "decided_at": null, "feedback": null, "expires_at": "2026-07-13T20:36:47.003020+00:00", "required_role": null, "approved_by": "", "approver_role": "", "approver_email": ""}]
```
