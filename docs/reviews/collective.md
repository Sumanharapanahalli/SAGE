# SAGE Feature Review — `collective`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/collective.py`  
**Frontend:** `Collective.tsx`  
**Review time:** 162s

---

## Verdict
The collective intelligence feature is partly usable today; while the backend handlers are fully wired and functional, the frontend lacks essential empty states, has leaky error validation, and exhibits severe row-level loading glitches.

**Works:** partly
**Score:** 5/10

## What Actually Works
* **Active Backend Wiring:** The RPC backend is completely active and successfully wired; the live run shows `collective.list_learnings` and `collective.stats` returning valid JSON instead of sidecar execution errors (`SidecarError`).
* **Git Diagnostics Integration:** The `stats` RPC correctly accesses the git backend to verify git integration (`git_available: true`) and retrieves the exact storage repository path (`C:\sandbox\DL-Sandbox\repo-split-v2\SAGE\solutions\.collective`).
* **Zero-State Resilience:** The backend safely handles unseeded/empty database states, returning an empty list (`"entries": []`) and zero-counts without throwing exceptions.

## System-Level Findings

1. **Critical Scalability & Memory Leak Vulnerability (Severity: High):**
   In `collective.py`, the `list_learnings` RPC handler queries the backend with a hardcoded limit of 10 million records and offset 0:
   ```python
   full = cm.list_learnings(
       solution=solution or None, topic=topic or None, limit=10_000_000, offset=0
   )
   ```
   It then loads all records into memory and slices them locally: `full[offset: offset + limit]`. In a production regulated environment with extensive historic compliance logs, this will cause memory exhaustion and crash the sidecar on every list fetch.

2. **Improper Error Type Raising for Validation Failures (Severity: Medium):**
   In `validate_learning`, `claim_help_request`, `respond_to_help_request`, and `close_help_request`, caught `ValueError` exceptions are raised as generic `RPC_SIDECAR_ERROR` (500) rather than actionable client validation errors (like `RPC_INVALID_PARAMS`):
   ```python
   except ValueError as e:
       raise RpcError(RPC_SIDECAR_ERROR, str(e)) from e
   ```
   This prevents the UI from providing targeted, non-alarmist feedback for expected business-rule violations (e.g., trying to claim an already-claimed ticket).

3. **Audit Trail Accountability Non-Repudiation Risks (Severity: Medium):**
   The UI hardcodes `"operator@desktop"` as both `proposed_by` and `validated_by` instead of pulling the authenticated operator's identity. This compromises the integrity of SAGE’s regulatory audit trail.

## Usability Findings

1. **Dead Ends / Zero Empty-State Feedback:**
   When `learnings.data?.entries` is empty (as in the unseeded live run), the UI renders absolutely nothing underneath the navigation bar. Operators cannot tell if the system is blank, loading, or silently broken.
2. **Global Loading State Interference:**
   In `Collective.tsx`, `isValidating` for *all* row items is mapped to the global `validate.isPending` boolean. Triggering validation on a single record causes a loading spinner to flash across every row simultaneously.
3. **Silently Swallowed Mutation Errors:**
   The page does not render `publish.error` or `sync.error` anywhere. If publishing a learning or triggering a repository sync fails, the user is left with no feedback.
4. **Stale/Sticky Masked Errors:**
   The `helpMutationError` is shared across `claim`, `respond`, and `close`. If a "claim" action fails, its error stays on screen even after a subsequent "close" action succeeds, as there is no state-clearing mechanism.

## Top 3 Fixes (optimizer-ready)

1. **Implement Database-Level Pagination in RPC Handler**
   * **File:** `C:\sandbox\DL-Sandbox\repo-split-v2\SAGE\solutions\collective.py` (or corresponding workspace file)
   * **Task:** Modify the `list_learnings` function to pass the coerced `limit` and `offset` values directly into the backend `cm.list_learnings` call.
   * **Acceptance Criteria:** Eliminate the `10_000_000` limit override and in-memory slicing (`full[offset: offset + limit]`). Verify pagination works seamlessly by calling the RPC with variable limits and offsets.

2. **Isolate Frontend Row Loading States and Decouple Shared Errors**
   * **File:** `Collective.tsx`
   * **Task:** Isolate validation states to the specific item being modified, and separate the shared help mutations.
   * **Acceptance Criteria:** 
     * Implement a local state tracking the specific `id` being validated (e.g., `validatingId`). Only show the spinner inside `LearningRow` if its ID matches.
     * Decouple `helpMutationError` so that separate, isolated error variables exist for `claim`, `respond`, and `close` actions.

3. **Add Empty State UI, Publish, and Sync Error Feedback**
   * **File:** `Collective.tsx`
   * **Task:** Add fallback rendering for unseeded datasets and wire up missing error banners.
   * **Acceptance Criteria:**
     * Render an informative empty state illustration/text (e.g., "No learnings available. Create a learning below to get started.") when `entries.length === 0`.
     * Add an `<ErrorBanner error={publish.error ? toDesktopError(publish.error) : null} />` adjacent to the publish form.
     * Render a validation warning if `sync.error` is triggered.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    collective.list_learnings
  -> {"entries": [], "total": 0, "limit": 50, "offset": 0}

[LIVE OK]    collective.stats
  -> {"learning_count": 0, "help_request_count": 0, "help_requests_closed": 0, "topics": {}, "contributors": {}, "git_available": true, "repo_path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\.collective"}
```
