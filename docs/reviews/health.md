# SAGE Feature Review — `health`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/health.py`  
**Frontend:** `Status.tsx`  
**Review time:** 71s

---

## Verdict
The health feature is only partly usable; while the UI successfully renders shallow status data from `status.get`, the robust `preflight` diagnostics are entirely absent from the provided frontend page, and the backend implementation contains critical blocking hazards that can freeze the entire sidecar during LLM latency or failures.

**Works:** partly
**Score:** 4/10

## What Actually Works
- **Shallow Status Retrieval (`status.get`):** The live runtime evidence confirms `status.get` returns successfully (`"health": "ok"`) along with the sidecar version (`"0.1.0"`), project name (`"four_in_a_line"`), active LLM configuration (`"ClaudeCodeCLI (claude-sonnet-4-6)"`), and pending approvals count (`1`).
- **UI Landing Page Rendering:** `Status.tsx` successfully binds this shallow state, rendering tiles for "Health", "Sidecar", "Project" (showing `"four_in_a_line"`), "LLM" (showing `"ClaudeCodeCLI (claude-sonnet-4-6) / claude-sonnet-4-6"`), and "Pending approvals" (showing `1` with an active link redirecting to `/approvals`).
- **LLM Thread-Isolated Probing (Structural):** The backend `health.py` defines a `_check_llm` that submits the 1-token probe (`"Reply with the single word: OK"`) to a separate thread pool (`_PROBE_POOL`) to offload the network call.

## System-Level Findings
1. **Critical Concurrency Hazard (Blocks Dispatch Loop):** Although `_check_llm` offloads the LLM generate call to `_PROBE_POOL.submit(...)`, it immediately invokes `future.result(timeout=timeout_ms / 1000.0)` synchronously. Since the NDJSON dispatch loop is single-threaded, this synchronous wait completely blocks the entire sidecar loop for up to 20 seconds (and up to 120 seconds max) if the LLM provider is unresponsive. This completely defeats the purpose of the thread pool and freezes all other incoming desktop requests.
2. **Thread Pool Exhaustion and Permanent Wedging:** The `_PROBE_POOL` has a tiny capacity of `max_workers=2`. Python threads cannot be forcefully killed or interrupted. If two consecutive LLM probes hang, both worker threads are exhausted indefinitely. Any subsequent preflight check will queue its task; the dispatch loop will then block for the full `timeout_ms` waiting on `future.result()`, which will inevitably time out without ever running, freezing the sidecar for every subsequent call even if the LLM recovery happens.
3. **Dead Code / Unused Helper:** The function `_call_with_timeout` is defined but never utilized anywhere in `health.py`, indicating incomplete or abandoned refactoring.
4. **Extreme Performance/Memory Inefficiency in Vector Store Check:** `_check_vector_store` calls `_vm.list_entries(limit=10_000)` and takes the `len()` of the resulting list just to get a count. If the vector store contains large text contents or embeddings, loading up to 10,000 full records into memory is a massive waste of resources, can trigger severe garbage collection pauses, and could easily crash the sidecar process with an Out Of Memory (OOM) error or cause a timeout in production.
5. **Divergent Health Standards (Shallow vs. Deep):** In the live evidence, `status.get` returns `"health": "ok"` and `"project": {"name": "four_in_a_line", "path": null}`. The `path: null` means the project path is unseeded. In `health.py`, `_check_solution()` explicitly asserts `if not _solution_name or _solution_path is None: return "error"`. Because `path` is `null`, the deep `preflight` check would fail (`go: false`), while the shallow `status.get` reports `"health": "ok"`. This inconsistent reporting violates compliance and audit reliability standards. You can tell they are out of sync because `status.get` reports `"health": "ok"` while `preflight` would return `"status": "error"` for the "Solution config" check.

## Usability Findings
1. **Complete Disconnection of Preflight Diagnostics from the UI:** The `Status.tsx` page relies entirely on `status.get`. The extensive diagnostics run by `preflight` (vector store backend verification, skill registry counts, YAML triad file verification) are never rendered on the frontend. If SAGE is failing due to a misconfigured YAML file or missing skills, the operator only sees a generic "Health: ok" or loading state, with no access to the diagnostic errors.
2. **Uninformative LLM Error Display:** In `Status.tsx`, if the LLM is unconfigured, it attempts to fall back to `data.llm.error ?? "unknown"`. However, if the LLM preflight fails or times out, the operator gets no detailed latency metrics, timeout messages, or actionable hints (such as network or API key issues) on the main page.
3. **Lack of Manual Diagnostic Trigger:** The UI lacks any button or interactive mechanism to trigger the deep `preflight` checks or refresh the current status. An operator is stuck with the initial mount state unless they manually reload the entire browser/web view context.

## Top 3 Fixes (optimizer-ready)

1. **Fix: Non-blocking Async Preflight Execution**
   - **Task:** Refactor the `preflight` handler in `health.py` to prevent blocking the single-threaded NDJSON dispatch loop. Instead of blocking synchronously on `future.result(timeout=...)` inside the serial dispatch thread, run the entire `preflight` sequence asynchronously or use an async event loop/non-blocking execution mechanism (such as resolving the handler via a background worker and returning a polling ID, or integrating `asyncio` if supported by the sidecar's NDJSON loop). If threads are kept, do not block the main thread waiting for them; return a "processing" status and let the frontend poll for the completed preflight results.
   - **Acceptance Criteria:**
     - The NDJSON dispatch loop continues processing other incoming RPC requests while an LLM probe is active.
     - A simulated hang in `_llm.generate` of 30 seconds does not delay or block a parallel `status.get` or `preflight` call.
     - Dead code `_call_with_timeout` is either correctly utilized or removed.

2. **Fix: Optimize Vector Store Count Query**
   - **Task:** Modify `_check_vector_store` in `health.py` to avoid loading full entries into memory. Implement or call a dedicated count API on the vector manager `_vm` (e.g., `_vm.count_entries()`), or if listing is required, project only the record IDs or set the limit to a minimal number (or query metadata only) instead of fetching up to 10,000 complete entries.
   - **Acceptance Criteria:**
     - `_check_vector_store` does not call `_vm.list_entries(limit=10_000)` with default full-payload fetches.
     - The vector store check remains functional and returns the correct count of entries.
     - Latency and memory consumption of the vector store check remain constant regardless of the size of the documents stored.

3. **Fix: Expose Preflight Diagnostics in Frontend UI**
   - **Task:** Update `Status.tsx` to display the detailed checks returned by the `preflight` RPC. Integrate a visual grid or list of the individual preflight checks ("Sidecar alive", "Solution config", "LLM provider", "Vector store", "Skill registry") with their respective status indicators (green/amber/red for ok/warning/error), details, and latency. Add a "Run Diagnostic Preflight" button that explicitly invokes the `preflight` RPC with a configurable timeout.
   - **Acceptance Criteria:**
     - A new collapsible or detailed section appears in `Status.tsx` showing the status, detail message, and round-trip latency of each check in the `checks` array.
     - If the project path is `null` (as seen in the live output), the UI prominently displays the "Solution config" error with the specific detail from `_check_solution`.
     - Clicking "Run Diagnostic Preflight" triggers the RPC call and updates the displayed statuses without reloading the page.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    status.get
  -> {"health": "ok", "sidecar_version": "0.1.0", "project": {"name": "four_in_a_line", "path": null}, "llm": {"provider": "ClaudeCodeCLI (claude-sonnet-4-6)", "model": "claude-sonnet-4-6"}, "pending_approvals": 1}
```
