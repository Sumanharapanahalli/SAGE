# SAGE Feature Review — `status`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/status.py`  
**Frontend:** `Status.tsx`  
**Review time:** 49s

---

## Verdict
The status feature is partly usable today, providing a high-level overview of the SAGE system state and pending approvals, but it suffers from silent exception swallowing on the backend and incomplete error presentation on the frontend that compromises the compliance transparency required for regulated environments.

**Works:** partly  
**Score:** 7/10

## What Actually Works
- **Retrieving Overall Health & Version Info:** The RPC `status.get` successfully returns health (`"health": "ok"`) and the sidecar version (`"sidecar_version": "0.1.0"`), which the frontend correctly displays.
- **Retrieving LLM Configuration Info:** The RPC correctly returns `"provider": "ClaudeCodeCLI (claude-sonnet-4-6)"` and `"model": "claude-sonnet-4-6"`. The frontend properly formats this into `"ClaudeCodeCLI (claude-sonnet-4-6) / claude-sonnet-4-6"`.
- **Project Name Retrieval:** The RPC correctly returns `"name": "four_in_a_line"` and the frontend handles missing values gracefully with a fallback (`data.project?.name ?? "—"`).
- **Pending Approvals Count & Navigation:** The backend retrieves the correct number of pending approvals (`"pending_approvals": 1`). The frontend dynamically enables a clickable link to `/approvals` only when the count is greater than zero.

## System-Level Findings
1. **Critical: Silent Error Swallowing in Pending Approvals (`status.py`)**
   - **Finding:** In `_pending_count()`, the `except Exception:` block silently catches all errors and returns `0`.
   - **Impact:** If the underlying store is corrupt, disconnected, or locked, the UI will display `0` pending approvals instead of raising an alert. An operator would be falsely assured that no actions are pending, silently bypassing the human-approval compliance gate and compromising the integrity of the audit log.
2. **High: Masked Project Retrieval Errors (`status.py` & `Status.tsx`)**
   - **Finding:** If `_project_info()` catches an exception, it returns `{"error": str(e)}`. However, the frontend only reads `data.project?.name`. 
   - **Impact:** If retrieving project info fails, `data.project.name` is undefined, and the UI displays a fallback dash (`"—"`). The system-level error is completely hidden from the operator, masking a critical system malfunction as "no project loaded".
3. **Medium: Fragile LLM Error Representation (`Status.tsx`)**
   - **Finding:** If an exception occurs in `_llm_info()`, it returns `{"error": str(e)}`. The frontend displays `data.llm.error`, but it renders in the standard text color without any warning state or error indicators. The operator might mistake an error message for a valid provider name.

## Usability Findings
1. **Hidden Project Path:** The backend payload returns `"path": null` (unseeded/not loaded in this run, but would be a string if a project path is configured). However, the frontend never renders this path anyway, leaving the operator unable to verify which exact directory is active.
2. **Opaque Queue Status State:** The frontend renders `<QueueTile status={queue.data} />` only if `queue.isSuccess` is true. If the queue retrieval is loading or encounters an error, the UI remains entirely silent with no spinner or error banner.
3. **Unstyled Empty/Error States in Tiles:** The `Tile` component lacks a dedicated style variant for errors or empty states. All states use the same standard border and grey/slate typography.

## Top 3 Fixes (optimizer-ready)

### 1. Stop Silent Error Masking for Pending Approvals
- **Task:** Refactor the backend to propagate pending approvals errors, and update the frontend to display an error state instead of falsely reporting `0`.
- **Files:** `status.py`, `Status.tsx`
- **Acceptance Criteria:**
  - In `status.py`, modify `get_status` payload to separate the count and error: return `{"count": count, "error": None}` on success, or `{"count": None, "error": str(e)}` on failure.
  - In `Status.tsx`, if `pending_approvals.error` is present, render the tile in an error style (red background/border) with the error message and disable the navigation link.
  - Write a unit test verifying that `get_status` returns the error details when `_store.get_pending()` raises an exception.

### 2. Standardize Tile Error Visualization and State
- **Task:** Enhance the frontend `Tile` component to accept an optional `error` prop and render an explicit warning state.
- **Files:** `Status.tsx`
- **Acceptance Criteria:**
  - Add an optional `error?: string` parameter to the `Tile` component signature.
  - If `error` is present, style the tile with a warning border/background (e.g., `border-red-200 bg-red-50 text-red-700`) and display the error message.
  - Map errors from `data.project?.error` and `data.llm?.error` to this new prop.

### 3. Expose Active Project Path and Loading States
- **Task:** Update the Project tile to display the project directory path if loaded, and handle empty states clearly.
- **Files:** `Status.tsx`
- **Acceptance Criteria:**
  - If `data.project?.path` is present, display it as secondary code-styled text inside the Project tile.
  - If `data.project` is completely null, display "No project loaded" instead of a dash `"—"`.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    status.get
  -> {"health": "ok", "sidecar_version": "0.1.0", "project": {"name": "four_in_a_line", "path": null}, "llm": {"provider": "ClaudeCodeCLI (claude-sonnet-4-6)", "model": "claude-sonnet-4-6"}, "pending_approvals": 1}
```
