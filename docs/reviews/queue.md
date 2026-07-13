# SAGE Feature Review — `queue`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/queue.py`  
**Frontend:** `Queue.tsx`  
**Review time:** 46s

---

## Verdict
No, this feature is not usable today by a real operator due to severe, illegible color contrast mismatches that render the UI text practically invisible, coupled with a complete lack of human-in-the-loop (HITL) approval gates or audit logging in the task queue.

**Works:** partly | **Score:** 3/10

---

## What Actually Works
* **Status Query Integration:** The `queue.get_status` RPC is fully operational, successfully pulling live parallel configuration from the parallel runner (`parallel_enabled: true`, `max_workers: 4`) and returning a complete status schema.
* **Task Listing API Boundary:** The `queue.list_tasks` RPC correctly returns an empty list `[]` when the system has no active tasks. This empty state indicates the queue is **merely unseeded** rather than broken, because `get_status` successfully executes and verifies that `_queue` is initialized (otherwise `get_status` would have tripped the `_queue is None` guard and returned `parallel_enabled: false`).

---

## System-Level Findings
1. **Critical Compliance Gap (Missing HITL Gatekeeping):** SAGE's core framework law dictates "Agents propose. Humans decide." However, neither the backend `queue.py` task representation nor the frontend `Queue.tsx` card component contains any concept of human approval states, approval tracking, or reviewer identity. This completely bypasses regulatory compliance requirements for an unalterable audit trail.
2. **Lack of Data Isolation:** The `list_queue_tasks` endpoint retrieves and outputs all tasks globally using `_queue.get_all_tasks()`. There is no filtering based on tenant, user session, or role, exposing sensitive agent payloads to any connected client.
3. **Silent Status Drop (Backend Bug):** In `queue.py`, the `get_queue_status` counter loop checks `if key in status`. If an agent records a task status not explicitly hardcoded in the frontend/backend dictionary (e.g. `"done"`, `"success"`, or `"aborted"`), the system silently drops the record from status aggregations rather than raising an validation error or mapping it to an "unknown" bucket.
4. **Missing Status Mappings on Frontend:** The backend statuses include `"blocked"` and `"cancelled"`, but the frontend `STATUS_STYLES` and `STATUS_ICONS` only map `pending`, `in_progress`, `completed`, and `failed`. Tasks in blocked or cancelled states will render with blank icons and generic gray fallback styling.

---

## Usability Findings
1. **Severe Text Invisibility (Theme Hybridization Mismatch):** The task cards in `Queue.tsx` have a hardcoded white background (`background: '#ffffff'`), but the text utilizes dark-theme styling colors (`color: '#e4e4e7'` which is near-white, `#9ca3af` which is extremely light gray, and `#d1d5db`). This results in almost zero contrast, rendering the task titles, IDs, and timestamps completely invisible to operators.
2. **Illegible Active Filter Pills:** When a filter pill is active, the background changes to `#d1d5db` (light gray) with text color `#f4f4f5` (off-white). This is visually unreadable.
3. **Unreadable Subtask Drawer:** The subtask container uses a dark background (`#151517`), but renders description text in `#6b7280` (dark gray), which violates standard accessibility contrast requirements.
4. **No Empty State Affordance:** When `list_tasks` returns an empty array `[]` (as shown in the live evidence), the UI renders a blank list with no visual feedback, leaving the operator with no indication of whether the system is idle or malfunctioning.

---

## Top 3 Fixes (optimizer-ready)

### 1. Fix Severe Styling Mismatches and Text Invisibility
* **Task:** Refactor `Queue.tsx` to resolve the hybrid light/dark theme contrast failures. Modify the card component to use a dark background (e.g., `#18181b`) matching the overall page container, or rewrite all card child text elements (titles, metadata, timestamps) to use dark-gray high-contrast colors (e.g., `#18181b` for titles, `#4b5563` for metadata) to render properly against the white background. Update `FilterPill` active state to use high-contrast styling (e.g., background `#1f2937` with text `#ffffff`).
* **Acceptance Criteria:** Every visible text element on the Queue page must pass a minimum WCAG AA contrast ratio of 4.5:1 against its immediate background.

### 2. Implement HITL Approval Gates and Audit Logging in the Queue
* **Task:** Extend the task schema in `queue.py` and `QueueTask` types in the frontend to support HITL fields (`approval_state`: `pending_approval | approved | rejected`, `actioned_by`: `string`, `actioned_at`: `string`). Render clear "Approve" and "Reject" buttons inside the `TaskRow` component for any tasks marked as pending operator approval, and block execution in the backend task runner until approval is registered.
* **Acceptance Criteria:** Tasks requiring approval cannot transition to `in_progress` until an operator clicks "Approve", which invokes a backend RPC writing the operator's ID to the task's immutable audit log.

### 3. Prevent Silent Status Dropping in Backend Aggregator
* **Task:** Modify `get_queue_status` in `queue.py` to handle unmapped or unexpected statuses. Replace the silent drop logic with a fallback mapping that increments an `"unknown"` counter when `key not in status`, and triggers a warning log.
* **Acceptance Criteria:** If a task with an unmapped status (e.g. `"aborted"`) is present in the queue, `get_status` successfully includes it in an `"unknown"` field in the returned JSON instead of ignoring it.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    queue.get_status
  -> {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "blocked": 0, "cancelled": 0, "parallel_enabled": true, "max_workers": 4}

[LIVE OK]    queue.list_tasks
  -> []
```
