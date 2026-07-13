# SAGE Feature Review — `builds`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/builds.py`  
**Frontend:** `Builds.tsx`  
**Review time:** 60s

---

## Verdict
This feature is only partly usable today because, while the basic layout and RPC dispatch pipeline compile, the complete lack of operator identity tracking in approvals violates critical regulatory compliance, and the lack of real-time UI polling leaves operators blind to asynchronous build state changes.

**Works:** partly
**Score:** 5/10

---

## What Actually Works
- **RPC Discovery and Basic Connectivity:** The live output `[LIVE OK] builds.list -> []` proves that the SAGE backend successfully wires the handler at startup and dispatches the RPC call, returning a valid empty array response without crashing.
- **Clean State Separation on Unseeded Launch:** The empty list `[]` suggests the system is unseeded (has no runs in database) rather than broken. To confirm this definitively rather than guessing, an operator would need to successfully call the `builds.start` RPC with valid parameters and assert that `builds.list` subsequently returns a non-empty list of runs.
- **Toggleable Forms and Detail Scaffolding:** `Builds.tsx` successfully manages the local state `showForm` to mount/unmount the `StartBuildForm` component, and conditionally handles `selectedId` to toggle between a selection placeholder, a loading state, and the `BuildRunDetailView`.

---

## System-Level Findings

### Severity 1: Critical Compliance & Audit Failure (Anonymous Approval Gates)
SAGE’s core law mandates that every agent proposal must pass a human approval gate, forming the compliance record. However, `builds.py::approve_stage` does not capture, authenticate, or log the identity of the operator performing the approval/rejection. It only tracks `run_id`, `approved`, and `feedback`. Allowing anonymous human-in-the-loop decisions breaks the audit trail, making it completely non-compliant under regulatory standards like FDA 21 CFR Part 11.

### Severity 2: Non-Atomic State Transitions (TOCTOU Race Condition)
In `builds.py::approve_stage`, the handler queries `orch.get_status(run_id)` in Python memory, inspects the `state` string, and then calls either `orch.approve_plan` or `orch.approve_build`. This Time-of-Check to Time-of-Use (TOCTOU) gap is non-atomic. If two operators concurrently review the same run, or if the orchestrator transitions state asynchronously, a stale action will execute and potentially corrupt the run state.

### Severity 3: Silent Exception/Error Masking in `list_runs`
Unlike `start` and `get`, which check if the returned value is a dictionary containing an `"error"` key, `list_runs` simply returns the raw result of `orch.list_runs()`. If the orchestrator follows its return-dict-with-error-key convention and returns `{"error": "Database error"}` instead of raising a Python exception, the RPC will treat this as a successful response. The frontend `Builds.tsx` (which expects an array of runs) will crash attempting to parse this dictionary.

---

## Usability Findings

### 1. No Real-Time Build Progress or State Polling
Build orchestration runs asynchronously in the background. However, `Builds.tsx` invokes `useBuilds()` and `useBuild(selectedId)` as static queries without polling intervals or WebSocket listeners. An operator must manually refresh the page or toggle selected runs to check if a running build has transitioned to an "awaiting approval" state.

### 2. Lack of Loading Feedback on Main List
If the list RPC is slow to return, the operator sees an empty table container with no skeleton loader or spinner. This creates the false impression that there are no builds in the system, when in reality a network request is still pending.

### 3. Evaporating Error States
If starting a build fails, the error is bound to the `StartBuildForm` component through `start.error`. If the operator clicks "Close" (`showForm = false`) to inspect other builds, this error is discarded from view. No persistent error boundary or global toast system warns the operator that their start command failed.

---

## Top 3 Fixes (optimizer-ready)

1. **Implement Operator Identity Capture in Approval Pipeline**
   * **Task:** Modify the `approve_stage` RPC signature in `builds.py` to require an `operator_id` string in the params block. Update `orch.reject`, `orch.approve_plan`, and `orch.approve_build` to accept and log this identity inside the compliance audit trail. Update `Builds.tsx` to supply the active user's identifier.
   * **Acceptance Criteria:** `approve_stage` must throw a `RPC_INVALID_PARAMS` error if `operator_id` is blank or missing. Assert in unit tests that the ID is successfully routed to all three internal orchestrator approval methods.

2. **Add Return-Dict Error Handling to `list_runs`**
   * **Task:** Update `list_runs` in `builds.py` to inspect the response of `orch.list_runs()`. If it is a dictionary containing an `"error"` key, raise an `RpcError` with code `RPC_SIDECAR_ERROR` matching the pattern used in `start` and `get`.
   * **Acceptance Criteria:** Write a unit test where `orch.list_runs()` returns `{"error": "Connection timed out"}`. Verify that the `list_runs` RPC call throws an `RpcError` with code `RPC_SIDECAR_ERROR` and message "Connection timed out".

3. **Configure Automatic Polling for Active Build Pipelines**
   * **Task:** Modify `@/hooks/useBuilds` (or the queries in `Builds.tsx`) to enable `refetchInterval` polling (e.g., every 3000ms) on `useBuilds` and `useBuild` whenever there is an active run in a non-terminal state (e.g., "running", "awaiting_plan", "awaiting_build").
   * **Acceptance Criteria:** When a build run is started, the network tab must demonstrate automatic RPC polling requests every 3 seconds, which automatically cease once the run state becomes terminal ("completed", "failed", or "rejected").

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    builds.list
  -> []
```
