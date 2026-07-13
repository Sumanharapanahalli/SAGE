# SAGE Feature Review — `monitor`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/monitor.py`  
**Frontend:** `Monitor.tsx`  
**Review time:** 76s

---

## Verdict
The monitor feature is only partly usable today; while it successfully communicates with the sidecar and reports basic status, it operates as a completely passive, non-actionable dashboard that lacks operator controls to activate subsystems, silently swallows backend initialization errors in the UI, and violates compliance principles by implicitly auto-starting background processing threads without explicit human approval or audit trail logging.

**Works:** partly
**Score:** 5/10

---

## What Actually Works
* **RPC Transport Connectivity:** Both `monitor.status` and `monitor.scheduler_status` RPC methods are live and functional, successfully returning structured JSON payloads without throwing wire-protocol or transport errors.
* **Accurate Inactive State Reporting:** The `monitor.status` handler accurately reports when the `MonitorAgent` is idle (`"running": false`), with all thread counts (`0`), seen messages (`0`), and configuration flags (`false`) matching a fresh or unseeded environment.
* **Lazy Scheduler Instantiation:** The backend `scheduler_status` lazily instantiates and starts a `TaskScheduler` on its first invocation, showing `"running": true` and a valid countdown (`"next_check_in_seconds": 30`).
* **Graceful UI Degradation:** The frontend component `Monitor.tsx` correctly renders the "Not active" fallback messages (`"Not active — no pollers running."`) when the backend subsystems report `running: false`, preventing the application from crashing.

*Note on Empty Lists/Counts:* The live output shows `active_threads: []` and `scheduled_count: 0`. This is **merely unseeded** rather than broken. We can determine this because `"teams_configured": false`, `"metabase_configured": false`, and `"gitlab_configured": false` are all `false`, which explains why no poller threads are active. For the scheduler, `"running": true` is reported alongside `"scheduled_count": 0`, indicating that the scheduler thread is running perfectly but no cron tasks have been queued. To verify this empirically, one would write a configuration file containing dummy credentials for one of the pollers (e.g., GitLab) and push a mock task to `task_queue`, then verify that `active_threads` lists the poller and `scheduled_count` increments to `1`.

---

## System-Level Findings
### 1. Silent Failure Masking and Error Swallowing (High Severity)
Both backend RPC handlers (`status` and `scheduler_status` in `monitor.py`) wrap their entire logic in catch-all `except Exception as e` blocks. If an import fails, a configuration is corrupt, or a database connection times out, the handler silently degrades and returns `{"running": False, "error": str(e)}`. Because this error string is never logged to `stderr` or forwarded to a central diagnostic facility on the backend, critical system failures are completely hidden from system logs.

### 2. Violating "Agents Propose, Humans Decide" via Implicit Side-Effects (High Severity)
In `monitor.py`, calling the passive read-only query `scheduler_status(params)` has the major side-effect of lazily instantiating and immediately starting the scheduler (`sched.start()`). In a regulated framework (such as medical devices or firmware), a background execution thread must never be spawned implicitly as a side-effect of a status polling request. This bypasses the approval gate entirely: background tasks could start running without an explicit human command, leaving no corresponding approval or initiation entry in SAGE's compliance audit log.

### 3. Thread-Safety and Initialization Race Conditions (Medium Severity)
The cached `_scheduler` variable in `monitor.py` is manipulated globally without any thread-locking mechanism. If multiple concurrent RPC requests hit `scheduler_status` simultaneously while `_scheduler` is `None`, multiple `TaskScheduler` instances will be created and started, resulting in leaked background threads running duplicate cron jobs in parallel.

---

## Usability Findings
### 1. Ingested Backend Errors are Hidden from the Operator (High Severity)
When the backend handlers catch an initialization exception, they return `{"running": False, "error": str(e)}`. However, in `Monitor.tsx`, the `MonitorAgentCard` and `SchedulerCard` components only inspect the network/transport-level hook `error` (for sidecar-down scenarios). They completely ignore the payload-level `data.error` field. If the backend fails to initialize due to a Python dependency error or a file-system permission issue, the operator is shown a misleading, calm status message: `"Not active — no pollers running"`, completely masking the system error.

### 2. Lack of Interactive Controls / Dead-Ends (Medium Severity)
When a subsystem is reported as "Not active," the operator has no interactive elements or affordances to resolve this. There are no buttons to "Start Agent," "Trigger Scheduler," or "Reload Configurations." The screen is a read-only dead-end, forcing the operator to drop to a CLI or manually edit configuration files to kick-start the services.

### 3. Non-Actionable Configuration Flags (Low Severity)
The UI displays configuration statuses (e.g., `"Metabase configured: no"`), but does not provide any context or actionable path. There are no tooltips, deep links to a settings page, or instructions indicating which configuration file or environment variables need to be modified to turn these flags to `"yes"`.

---

## Top 3 Fixes (optimizer-ready)

### 1. Stop Implicit Scheduler Starts and Restructure the Instantiation Flow
* **File:** `monitor.py`
* **Task:** Remove the lazy instantiation and `sched.start()` call inside `scheduler_status`. The status RPC must strictly act as a read-only inspector. It should fetch an existing scheduler instance from an explicit application context or daemon manager. If the scheduler is not already running, it must return `{"running": false}`. Create a separate, explicit RPC handler `monitor.start_scheduler` which requires a user payload, logs the start action to SAGE's compliance audit trail, and spins up the singleton using thread-safe double-checked locking.
* **Acceptance Criteria:** 
  1. Calling `monitor.scheduler_status` when the scheduler is stopped returns `{"running": false}` and does *not* spawn any threads.
  2. Calling the new `monitor.start_scheduler` RPC starts the scheduler thread, records an audit log entry, and subsequent calls to `monitor.scheduler_status` return `{"running": true}`.

### 2. Surface and Render Backend Initialization Errors in the UI
* **File:** `Monitor.tsx`
* **Task:** Modify both `MonitorAgentCard` and `SchedulerCard` to check for the presence of `data.error` when `data.running` is false. If `data.error` is populated, render a styled, collapsible inline warning banner displaying the Python exception message (e.g., `"Subsystem failed to start: [Error Detail]"`), rather than displaying the generic and## Verdict
This feature is only partly usable today because while the underlying RPC mechanisms are functional and report status correctly, the UI completely hides critical system-level failures from the operator, and checking the scheduler's status has the highly dangerous side-effect of silently launching a background thread without human consent.

**Works:** partly
**Score:** 5/10

---

## What Actually Works
* **RPC Communication & Payload Delivery:** The frontend successfully fetches status data from the sidecar. The live output for `monitor.status` (`{"running": false, ...}`) and `monitor.scheduler_status` (`{"running": true, ...}`) proves the IPC/RPC bridge is working.
* **Graceful Desktop Fallback:** When the Monitor Agent pollers are unconfigured, `monitor.status` safely returns `running: false`. The frontend correctly renders the calm fallback state: *"Not active — no pollers running."*
* **Active Status Reporting:** When a subsystem is running, the scheduler status correctly reports metrics such as `next_check_in_seconds` (30s) and `scheduled_count` (0). 

*Note on Unseeded vs. Broken:*
* **Monitor Agent is unconfigured:** The live output showing `running: false` with all configuration flags as `false` and no `error` key represents a healthy, unconfigured state (not broken). If it were broken (e.g., failed imports or configuration crashes), the backend `try...except` block would have returned an `error` key, which is absent here.
* **Task Scheduler is unseeded:** The live output showing `running: true` but `scheduled_count: 0` represents a running but unseeded scheduler. It has successfully booted and is polling every 30 seconds, but has no work items registered.

---

## System-Level Findings

### 1. Silent Swallowing of Backend Crashes (High Severity)
* **Evidence:** In `monitor.py`, the `status` and `scheduler_status` handlers catch all exceptions (`except Exception as e`) and format them into a dictionary: `{"running": False, "error": str(e)}`.
* **Impact:** In `Monitor.tsx`, `MonitorAgentCard` and `SchedulerCard` only check the transport-level React Query `error` variable for rendering `ErrorBanner`. If the backend python code crashes and returns `{"running": false, "error": "Database migration failed"}`, the UI ignores `data.error` entirely. The operator is shown a misleading, calm status message: *"Not active — no pollers running."* This masks severe backend crashes as normal unconfigured states, violating compliance and safety visibility.

### 2. Mutative Side-Effects in Read-Only Status Calls (High Severity)
* **Evidence:** In `monitor.py`, calling `scheduler_status` executes:
  ```python
  if _scheduler is None:
      ...
      sched = TaskScheduler(...)
      sched.start()  # <--- Mutative launch!
  ```
* **Impact:** A standard UI status poll (GET/Read-only query) automatically instantiates and launches a background worker thread (`sched.start()`). In a regulated environment, background agents must never be launched implicitly by a user simply viewing a status page. This bypasses the SAGE core law of explicit human approval and makes tracing *why* a thread was spawned in the audit trail incredibly difficult.

### 3. Complete Lack of Data Isolation / Scoped Context (Medium Severity)
* **Evidence:** The backend imports the shared global singletons (`from src.core.queue_manager import task_queue`, `from src.core.project_loader import project_config`) directly.
* **Impact:** There is no multi-tenant, multi-workspace, or user-scoped boundary context passed from the frontend to the sidecar. The sidecar assumes a single local machine context, which breaks isolation boundaries if multiple operators are accessing the sidecar concurrently.

---

## Usability Findings

### 1. Masked Initialization Failures (Dead End)
* **Evidence:** If the `MonitorAgent` fails to import or initialize (e.g., due to missing dependency packages on the operator's machine), the UI silently falls back to *"Not active — no pollers running."*
* **Impact:** The operator has no way of knowing their installation is broken vs. merely unconfigured. They are left with a dead end and no guidance on what to install or configure.

### 2. Complete Read-Only Passivity (Missing Affordances)
* **Evidence:** The `Monitor.tsx` page consists of two static cards displaying properties.
* **Impact:** If the operator sees the Monitor Agent is "Not active", there is no "Start Pollers" button, no "Configure Pollers" link, and no diagnostic troubleshooting workflow. The screen is a passive status display that forces the user to jump to CLI or configuration files to make any changes.

### 3. Vague "0 Scheduled Tasks" Empty State
* **Evidence:** The scheduler card displays: `Scheduled tasks: 0`.
* **Impact:** This empty state is uninformative. The operator is given no context on whether 0 is the expected normal state, what cron jobs are registered but dormant, or how to register a scheduled task.

---

## Top 3 Fixes (optimizer-ready)

### 1. Decouple Thread Startup from Status Queries
* **File:** `monitor.py`
* **Task:** Remove the side-effect of lazy initialization and startup from `scheduler_status()`. It must only query and report the status of an existing `_scheduler` instance. If `_scheduler` is not yet running, return `{"running": false}`.
* **Acceptance Criteria:** Calling `scheduler_status` on an unstarted scheduler must return `{"running": false}` and must NOT trigger `sched.start()`. The scheduler should only be started by an explicit lifecycle manager or human-approved "Start" RPC.

### 2. Surfacing Backend Errors to the Operator UI
* **File:** `Monitor.tsx`
* **Task:** Update both `MonitorAgentCard` and `SchedulerCard` to check for the presence of `data.error` in the RPC response. If `data.error` is present and `data.running` is false, render an alert box containing the actual backend error string instead of the generic "Not active" text.
* **Acceptance Criteria:** Verify by mocking an RPC response with `{"running": false, "error": "OperationalError: connection refused"}`. The UI must render a visible warning banner showing `"OperationalError: connection refused"`.

### 3. Expose Active / Dormant Job Registrations
* **Files:** `monitor.py`, `Monitor.tsx`
* **Task:** Extend `monitor.scheduler_status` to return a list of registered task definitions (e.g., task names, target functions, intervals) from the `TaskScheduler`. Update `SchedulerCard` to list these task names in a small sub-table.
* **Acceptance Criteria:** If the scheduler is running but has no queued runs, the UI must list the registered tasks (e.g., "db_cleanup (interval: 1h)") and show their last/next run times, eliminating the uninformative empty state.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    monitor.status
  -> {"running": false, "active_threads": [], "thread_count": 0, "seen_messages": 0, "seen_issues": 0, "teams_configured": false, "metabase_configured": false, "gitlab_configured": false}

[LIVE OK]    monitor.scheduler_status
  -> {"running": true, "scheduled_count": 0, "next_check_in_seconds": 30}
```
