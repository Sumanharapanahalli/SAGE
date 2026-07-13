# SAGE Feature Review — `goals`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/goals.py`  
**Frontend:** `Goals.tsx`  
**Review time:** 82s

---

## Verdict
The Goals feature is only partly usable today; while operators can view, create, and delete goals, they cannot manage key results, cannot edit existing goal metadata without complete recreation, and will face silent failures on updates alongside a broken UI status selector due to a database/frontend schema mismatch.

**Works:** partly
**Score:** 4/10

## What Actually Works
* **Goal Retrieval Backend and UI Listing:** The live RPC output `goals.list` successfully executes and returns a seeded goal: `[{"id": "e2f97376-42e5-4c5e-a5f1-d91d5bc58350", "user_id": "desktop-operator", "solution": "", "title": "Ship desktop parity", "quarter": "2026-Q3", "status": "active", "owner": "operator", "key_results": [], ...}]`. The frontend page `Goals.tsx` successfully binds this query data to render the goal card with its title, quarter, status, owner, and key result count.
* **Goal Creation Form:** The backend `create()` handler correctly processes `title`, `quarter`, `status`, `owner`, and `key_results`. The frontend "New goal" form captures these fields and submits them via the `create` mutation.
* **Goal Deletion with Confirmation:** The backend `delete()` handler successfully removes goals by ID, and the frontend provides a functional two-step safety check ("Delete" -> "Confirm"/"Cancel") before firing the API request.

## System-Level Findings
1. **Critical Lack of Compliance Logging (High Severity):** SAGE's core law mandates that all changes are auditable. However, `goals.py` contains no audit logging integration. Creating, updating, or deleting goals occurs silently without registering any entries in SAGE's framework audit database.
2. **Split-Brain Database Resolution (High Severity):** The backend handler comment highlights that `goals.py` diverges from the Web API. The Web API (`src/interface/api.py`) resolves `goals.db` in a single shared location next to the audit logger, while the desktop backend resolves `goals.db` inside the per-solution `.sage/` directory. This breaks data isolation guarantees across interfaces.
3. **No Solution Boundary Isolation in UI (Medium Severity):** The backend `list()` filters on exact `solution` equality, defaulting to `""`. The frontend `Goals.tsx` calls `useGoals()` and `useCreateGoal()` without passing the active solution context, forcing all desktop operations into the global empty-string solution namespace instead of isolating goals per workspace.
4. **Absence of Backend Status Validation (Medium Severity):** The backend `create` and `update` handlers accept any arbitrary string as a status. This allowed the live database to be populated with `"status": "active"`, which is an invalid status according to the frontend's hardcoded options.
5. **Silent Update Failures (Low Severity):** The frontend `Goals.tsx` handles errors for creation and deletion (`createError`, `deleteError`), but completely ignores `update.error`. If a status change fails on the backend, the operator receives no feedback.

## Usability Findings
1. **Broken UI State for Pre-existing/Active Goals:** The live database contains a goal with `"status": "active"`. However, `STATUS_OPTIONS` in `Goals.tsx` only contains `["on_track", "at_risk", "off_track", "done"]`. Because `"active"` is missing from the frontend options, the dropdown selector for this goal in the UI cannot match the value, causing it to display incorrectly (blank or defaulting to `"on_track"`).
2. **"Key Results" is a Functional Dead End:** The UI displays `{goal.key_results.length} key results` but provides absolutely no interface elements (inputs, lists, or buttons) to view, add, edit, or delete key results on a goal.
3. **Immutability of Goal Metadata:** Once a goal is created, the only editable field in the UI is its status. An operator cannot fix typos in the title, quarter, or owner fields without deleting the goal and starting over.
4. **Silent Failure on Empty Form Submissions:** The frontend `handleSubmit` intercepts empty title or quarter submissions with a silent `return`. There is no visual feedback (such as validation warnings or highlighted fields) indicating why the form was not submitted.

## Top 3 Fixes (optimizer-ready)

1. **Integrate Compliance Audit Logging in Backend**
   * **Task:** Modify `goals.py` to import SAGE's core `audit_logger` module and record a structured audit entry inside the `create()`, `update()`, and `delete()` handlers. Each log entry must record the executing operator's `user_id`, the active `solution` context, the affected `goal_id`, and the mutated parameters.
   * **Acceptance Criteria:** Modifying any goal via the backend RPCs successfully writes a corresponding record to the SAGE compliance audit trail.

2. **Synchronize and Validate Goal Statuses**
   * **Task:** Update the backend `goals.py` to strictly validate that the `status` parameter is within a defined set of allowed statuses (e.g., `["active", "on_track", "at_risk", "off_track", "done"]`), raising `RPC_INVALID_PARAMS` on failure. Update `Goals.tsx`'s `STATUS_OPTIONS` and TypeScript types to include `"active"` to correctly display and handle the status seen in the live database.
   * **Acceptance Criteria:** Attempting to create or update a goal with an arbitrary status like `"broken"` fails with a backend `RpcError`. The UI dropdown correctly renders and highlights the `"active"` status for the live goal.

3. **Expose Status Update Errors and Pass Solution Context in UI**
   * **Task:** Update `Goals.tsx` to retrieve the current workspace's solution context and pass it as the `solution` parameter to both the `useGoals` and `useCreateGoal` hooks. Also, define `const updateError = update.error ? toDesktopError(update.error) : null;` and render it as `<ErrorBanner error={updateError} />` in the layout.
   * **Acceptance Criteria:** Status update RPC failures are visibly reported to the user via an error banner, and switching solution workspaces in the desktop UI correctly filters the displayed goals list.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    goals.list
  -> [{"id": "e2f97376-42e5-4c5e-a5f1-d91d5bc58350", "user_id": "desktop-operator", "solution": "", "title": "Ship desktop parity", "quarter": "2026-Q3", "status": "active", "owner": "operator", "key_results": [], "created_at": "2026-07-13T19:36:35.959682+00:00", "updated_at": "2026-07-13T19:36:35.959682+00:00"}]
```
