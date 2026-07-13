# SAGE Feature Review — `solutions`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/solutions.py`  
**Frontend:** `Home.tsx`  
**Review time:** 236s

---

## Verdict
The solutions feature is only partly usable today because, while it successfully lists and identifies the current active solution, the frontend code contains a critical usability flow lock that traps users on the home screen when an active solution is present, and the backend lacks a dynamic mutation handler to execute solution switching.

**Works:** partly
**Score:** 5/10

---

## What Actually Works
Based on the live runtime evidence:
* **Solution Discovery (`solutions.list`):** The backend successfully lists five available solutions from disk, detecting metadata like the path and whether a `.sage` data directory exists (`has_sage_dir: true` for `four_in_a_line` and `starter`; `false` for others).
* **Current Solution Querying (`solutions.get_current`):** The backend successfully identifies the active solution loaded at process startup (`four_in_a_line` at path `C:\sandbox\DL-Sandbox\repo-split-v2\SAGE\solutions\four_in_a_line`).
* **Basic Search/Filtering:** The frontend successfully implements case-insensitive search filtering matching on the solution's `name` string.

---

## System-Level Findings

### 1. Process Lifecycle Disconnect & Missing Switch Handler (Severity: Critical)
* **Evidence:** The backend module `solutions.py` only defines read-only RPCs: `list_solutions` and `get_current`. There is no `switch_solution` handler defined. The docstring notes: *"The sidecar is a single-solution process... solutions.get_current echoes the values wired at spawn time."*
* **Impact:** SAGE is architected as a single-solution process. However, the frontend (`Home.tsx`) attempts to invoke a mutation (`switchSolution.mutate({ name: s.name, path: s.path })`). Since the sidecar's active solution is immutable post-spawn, executing a "switch" must either crash/restart the sidecar or fail silently if the RPC is unhandled. If the sidecar process is restarted by a desktop wrapper, WebSocket disconnects and state loss are highly probable.
* **Compliance/Audit Risk:** SAGE's core law is *"Agents propose. Humans decide. The audit log is the compliance record."* Changing the target workspace (and thus the regulatory boundaries) must write an immutable entry to the compliance audit log. No logging or audit hooks exist in `solutions.py` to capture startup-wired or switched solutions.

### 2. Insecure System Path Disclosure (Severity: Medium)
* **Evidence:** `solutions.list` returns raw absolute system paths (`C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\...`).
* **Impact:** Exposing internal host OS file structures directly to the client violates data isolation. If SAGE is run in any client-server context (outside purely local desktop execution), this leaks directory layouts and system usernames.
* **Path Traversal Risk:** The backend does not sanitize or restrict listed solutions to a specific sandbox root. Any absolute path could potentially be fed to a launcher, posing a path traversal vulnerability.

### 3. Silent Backend Initialization Failures (Severity: Low)
* **Evidence:** In `solutions.py`, `_sage_root`, `_current_name`, and `_current_path` are initialized to `None`/`""`. If the app's wiring fails, `list_solutions` silently returns `[]` and `get_current` silently returns `None`.
* **Impact:** Diagnostic difficulty. Operators or developers see an empty home screen or lack of active workspace with zero logs pointing to a wiring failure.

---

## Usability Findings

### 1. The "Active Solution" Home Trap (Severity: High)
* **Evidence:** In `Home.tsx`, the auto-load hook returns early if an active solution already exists on mount:
  ```typescript
  if (current.data) return; // Returns early and skips switchSolution.mutate()
  ```
  However, the redirect to `/approvals` is bound *only* to the success of `switchSolution`:
  ```typescript
  useEffect(() => {
    if (switchSolution.isSuccess && switchSolution.data) {
      navigate(DEFAULT_LANDING, { replace: true });
    }
  }, [switchSolution.isSuccess, switchSolution.data]);
  ```
* **Impact:** If SAGE starts up with an already active solution (such as `four_in_a_line` in the live run), the user is permanently trapped on the Home screen. They are not auto-redirected to `/approvals`. They must manually click on the list item to force a redundant switch action to bypass the screen.

### 2. Complete Absence of Active Solution Highlighting (Severity: Medium)
* **Evidence:** In the JSX list rendering of `Home.tsx`, list items are mapped without any check against `current.data?.path`. 
* **Impact:** The operator is presented with a list of 5 solutions but has zero visual indicators (e.g., active badge, highlighted border, green checkmark) showing that `four_in_a_line` is the workspace currently running. Operators can easily select the wrong workspace or trigger redundant reloads.

### 3. Brittle Auto-Load Failure Recovery (Severity: Medium)
* **Evidence:** The home screen reads the last solution from localStorage (`getLastSolution()`) and immediately calls `switchSolution.mutate`.
* **Impact:** If a solution directory was deleted or renamed on disk, the mutation will fail. The UI shows an error banner, but the application hangs in a half-loaded state, and the broken localStorage reference is never cleared, triggering the same failure loop on the next application launch.

---

## Top 3 Fixes (optimizer-ready)

### 1. Fix the Active Solution Home Trap & Add Auto-Redirect
* **Task:** Modify the navigation lifecycle in `Home.tsx` to immediately redirect the operator to `/approvals` if an active solution is already loaded on mount.
* **File:** `frontend/src/pages/Home.tsx` (or equivalent path matching the frontend codebase)
* **Acceptance Criteria:**
  1. When `current.isLoading` is false and `current.data` is not null on mount, automatically set `lastSolution` in localStorage and trigger `navigate("/approvals", { replace: true })`.
  2. If `current.data` is null, do not auto-redirect; let the user pick from the list.
  3. If auto-load of `getLastSolution()` is triggered and fails, clear the invalid item from localStorage to prevent failure loops.

### 2. Add Visual Highlight and "Active" Status Badge to Current Workspace
* **Task:** Update the solution list rendering in `Home.tsx` to compare each listed item against the active solution and render a styled status indicator.
* **File:** `frontend/src/pages/Home.tsx`
* **Acceptance Criteria:**
  1. Compare `s.path` with `current.data.path`. If they match, render a green badge with the text `"Active Workspace"`.
  2. Apply a distinctive active background and border style (e.g., `border-sage-500 bg-sage-50/50`) to the active solution list item to differentiate it from the remaining 4 inactive items.

### 3. Implement Strict Path Validation and Compliance Audit Logging
* **Task:** Secure the backend load process by ensuring that the target path is validated, and write a compliance audit log entry on initialization.
* **File:** `backend/solutions.py`
* **Acceptance Criteria:**
  1. On sidecar startup/wiring, assert that the target `_current_path` exists on disk and is a directory. If invalid, throw a clear initialization exception rather than failing silently.
  2. Implement an explicit compliance log statement: `print("[AUDIT] Active solution initialized: {name} ({path})")` (or integrate with the SAGE framework's audit logging utility) so there is a formal compliance record of the active target workspace.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    solutions.list
  -> [{"name": "four_in_a_line", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\four_in_a_line", "has_sage_dir": true}, {"name": "meditation_app", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\meditation_app", "has_sage_dir": false}, {"name": "medtech_sample", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\medtech_sample", "has_sage_dir": false}, {"name": "medtech_team", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\medtech_team", "has_sage_dir": false}, {"name": "starter", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\starter", "has_sage_dir": true}]

[LIVE OK]    solutions.get_current
  -> {"name": "four_in_a_line", "path": "C:\\sandbox\\DL-Sandbox\\repo-split-v2\\SAGE\\solutions\\four_in_a_line"}
```
