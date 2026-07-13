# SAGE Feature Review — `workflow`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/workflow.py`  
**Frontend:** `Workflows.tsx`  
**Review time:** 59s

---

## Verdict
The SAGE workflow feature is only partly usable today because, while the backend RPC plumbing is syntactically sound, the lack of session/run persistence, absence of secure audit logs, and highly volatile, developer-centric UI render it unfit for regulated production environments.

**Works:** partly
**Score:** 4/10

---

## What Actually Works
* **Dynamic Module Lifecycle Integration**: The `workflow.py` backend defer-imports `langgraph_runner` at call-time. This successfully prevents boot-time crashes when the active orchestration engine is not set to `"langgraph"` or when the package is missing.
* **Basic List Retrieval**: `workflow.list_workflows` executes correctly. The live runtime evidence showing `{"workflows": [], "count": 0}` indicates that the backend handles empty-state discovery gracefully. This empty list is **unseeded** (rather than broken); to confirm this empirically, we would verify if `orchestration.engine == "langgraph"` in the configuration and check if the `workflows/` directory contains active Mermaid/LangGraph definitions.
* **Granular Input Validation**: The backend rigorously asserts typing (e.g., checking that `workflow_name` is a string and `state`/`feedback` are dictionaries) and maps custom engine-level error dicts (like `{"error": "..."}`) to typed `RPC_INVALID_PARAMS` errors.
* **Single-Session Run & Resume**: The frontend can parse text inputs, invoke `workflow.run`, track the ensuing `activeRun`'s status, and submit human feedback to resume past approval gates within a single, uninterrupted browser tab session.

---

## System-Level Findings

### 1. Critical Compliance Violation: Absent Audit Trail for Human-in-the-Loop (HITL) Decisions
* **Severity: Block-level / Compliance Failure**
* **Impact**: SAGE's core tenet is "Agents propose. Humans decide." In a regulated environment (such as FDA medical devices), any human decision—specifically resuming a workflow with feedback—must be logged to a secure, tamper-proof audit trail. Currently, `workflow.py`’s `resume` handler accepts the operator's payload and forwards it straight to `langgraph_runner` without writing any record of the action, the supervisor's identity, the feedback contents, or the timestamp to SAGE's audit log. This silently invalidates the system's regulatory compliance.

### 2. Major Security Defect: Total Lack of Tenant and User Isolation
* **Severity: High**
* **Impact**: The backend functions `resume(params)` and `status(params)` query and mutate state machines solely based on a caller-provided string `run_id`. There are no checks to verify that the active session's tenant or user possesses the authorizations required to access or resume that specific run. Any client can hijack or inspect any system-wide workflow run simply by guessing or brute-forcing its `run_id`.

### 3. Reliability Flaw: Brittle Exception Mapping
* **Severity: Medium**
* **Impact**: The backend assumes `langgraph_runner` handles validation internally and signals failure gracefully by returning a dict with an `"error"` key (mapped to `RPC_INVALID_PARAMS`). If a low-level validation error inside `langgraph_runner` raises an unhandled exception instead, `workflow.py` intercepts it as a generic `Exception` and raises `RPC_SIDECAR_ERROR`. This obscures actionable input errors and presents them as system crashes.

---

## Usability Findings

### 1. Ephemeral UI State (Total Loss on Refresh/Navigation)
* **Severity: High**
* **Impact**: The active run state (`baseRun`) is stored exclusively in React component state. If an operator refreshes the page, navigates to another view, or experiences a momentary connection blip, all knowledge of the run is permanently lost from the UI. There is no historical list of active runs, and no way to enter a `run_id` manually to reload or resume an ongoing process.

### 2. High-Friction, Developer-Only Input UX
* **Severity: High**
* **Impact**: Both initial workflow states and human feedback approval payloads require operators to type raw JSON into a `textarea`. If an operator leaves out a comma or quotation mark, the UI halts and throws a syntax warning. Forcing clinical or operations personnel to write raw JSON objects to approve or steer agents is error-prone, slow, and operationally dangerous.

### 3. Missing Auto-Polling / Push Notifications
* **Severity: Medium**
* **Impact**: The frontend disables auto-fetching (`enabled: false` on the status hook). Since there are no WebSockets or SSE integrations, the UI cannot detect when a workflow run transitions from `running` to `awaiting_approval`. Operators are forced to repeatedly click a manual "Refresh status" button to discover if their approval is required.

---

## Top 3 Fixes (optimizer-ready)

### 1. Secure Compliance Audit Logging for Human Resume Decisions
* **Task**: Modify `workflow.resume` in `workflow.py` to record a structured audit log entry before executing the resume. Integrate SAGE's standard audit logger (or write to a dedicated secure compliance log) capturing: `run_id`, timestamp, human identifier, and the `feedback` payload.
* **Acceptance Criteria**: Verify that invoking the `resume` RPC successfully writes a permanent, tamper-resistant log entry. Ensure that if logging fails, the transaction is aborted and a `RPC_SIDECAR_ERROR` is returned without forwarding the resume command to the agent framework.

### 2. Replace Volatile Ephemeral State with URL/Query Parameter Route Persistence
* **Task**: Refactor `Workflows.tsx` to read and write the active `run_id` from the URL query parameters (e.g., `?run_id=...`). Add a "Track Existing Run" text input that allows operators to manually enter a `run_id` to load its status, and render a simple "Recent Runs" list in local storage.
* **Acceptance Criteria**: Trigger a workflow run, copy the `run_id`, refresh the browser, and confirm that the UI reloads the correct active run status and approval gate without starting over. Confirm entering a valid `run_id` manually displays that run's status.

### 3. Implement Smart Status Polling for Active Runs
* **Task**: Update `Workflows.tsx` to conditionally enable auto-polling in TanStack Query (`refetchInterval`) whenever an `activeRun` is in a non-terminal status (e.g., `running` or `pending`). Stop polling once the status transitions to `awaiting_approval`, `completed`, or `error`.
* **Acceptance Criteria**: Run a workflow. Observe that the status badge updates automatically (e.g., every 3 seconds) without pressing the manual "Refresh status" button. Verify that polling stops immediately when the run hits `awaiting_approval` or a terminal state.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    workflow.list_workflows
  -> {"workflows": [], "count": 0}
```
