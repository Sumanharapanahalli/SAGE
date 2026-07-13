# SAGE Feature Review — `hil`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/hil.py`  
**Frontend:** `Hil.tsx`  
**Review time:** 58s

---

## Verdict
The HIL feature is **partly** usable today by a real operator, but it contains critical architectural shortcuts and UI error-swallowing behaviors that violate safety constraints and compromise the regulatory audit trail.

**Works:** partly
**Score:** 5/10

---

## What Actually Works
* **Initial Status Retrieval:** The live runtime evidence proves that the `hil.status` RPC behaves correctly under normal uninitialized conditions, successfully returning:
  `{"connected": false, "transport": "none", "session_id": null, "tests_run": 0, "message": "No HIL runner initialised. Call hil.connect to start."}`
  This confirms that the status check itself is functional and properly reports when no runner is seeded.
* **Dynamic Form Construction:** The `TransportConfigFields` component in `Hil.tsx` correctly renders customized configurations based on the selected transport (`serial`, `jlink`, `can`, `openocd`).
* **Basic Configuration Validation:** The `connect` and `run_suite` handlers in `hil.py` correctly validate that incoming `config` parameters are dictionary objects.

---

## System-Level Findings

### 1. Compliance Violation: Silent Auto-Connection Bypasses Operator Consent (High Severity)
* **Finding:** SAGE’s core design principle states that connecting to real hardware is an explicit operator action because it can spawn blocking background subprocesses (e.g., `JLinkExe`, `openocd`) or lock real physical serial/CAN interfaces. However, in `hil.py`'s `run_suite`, the backend silently triggers auto-connection if not already connected:
  ```python
  if not runner._connected:
      runner.connect()
  ```
  This bypasses the operator gate entirely, allowing a user (or an autonomous agent) to directly connect to physical hardware simply by triggering a test suite run, risking hardware damage or unexpected state transitions.

### 2. Status Check Swallows System Exceptions (High Severity)
* **Finding:** In `hil.py`'s `status` function, any exception is caught and returned as a standard success payload rather than raising an `RpcError`:
  ```python
  except Exception as e:  # noqa: BLE001
      return {"connected": False, "error": str(e)}
  ```
  Because a standard response is returned, the frontend's `status.error` remains `null`, preventing the `<ErrorBanner error={statusError} />` from displaying the error. Furthermore, `Hil.tsx` only renders `status.data.message` when disconnected:
  ```tsx
  <div className="text-slate-500">Not connected. {status.data?.message ?? ""}</div>
  ```
  Because `status.data.error` is completely ignored, any system-level exception thrown during a status query is swallowed and hidden from the operator.

### 3. Compliance Log Isolation Bypass (Medium Severity)
* **Finding:** As noted in the `hil.py` file header, `hil_runner._write_audit()` imports and uses the global `audit_logger` singleton instead of the localized per-solution `AuditLogger` injected into sidecar handlers. This violates multi-tenant/multi-solution isolation boundaries, creating a risk where HIL test logs bypass the active solution's audit trail and break compliance traceability.

### 4. Configuration Type Mismatches (Medium Severity)
* **Finding:** In `TransportConfigFields`, numerical fields like `baud_rate`, `speed`, and `bitrate` are gathered as text inputs and stored inside a `Record<string, string>`. This raw string configuration is passed directly to `connect()` and `run_suite()`. If the underlying transport engines expect integer types, this will cause casting errors or silent setup failures deep in the hardware integrations.

---

## Usability Findings

### 1. Eager Report Hook Triggers Immediate Error Banner (High Severity)
* **Finding:** The component executes the `useHilReport` hook eagerly on load:
  ```tsx
  const report = useHilReport(reportRequested ? sessionId : "", standard);
  ```
  When the page first loads, `reportRequested` is `false`, causing the hook to query the backend with an empty string as `session_id`. The backend `report` RPC immediately rejects this:
  ```python
  if not session_id:
      raise RpcError(RPC_INVALID_PARAMS, "session_id required")
  ```
  This causes a persistent, confusing error banner to appear in the UI on initial page load before the operator has even attempted to run tests.

### 2. Missing "Disconnect" Capability (Medium Severity)
* **Finding:** There is no frontend button or backend RPC endpoint to disconnect from a hardware transport. Once an operator connects to a physical port (e.g., locking a serial interface), they cannot release the connection short of killing and restarting the desktop sidecar.

### 3. Poor JSON Schema Validation UX (Medium Severity)
* **Finding:** Operators are forced to input raw JSON test cases in a basic textarea. If they make a minor syntax error (e.g., a trailing comma), `parseTestCases` simply fails and sets a generic error: `"Test cases must be valid JSON (an array of objects)."`. It provides no line numbers, column offsets, or syntax hints to help the operator debug their input.

---

## Top 3 Fixes (optimizer-ready)

### 1. Enforce Explicit Connection Gate in `hil.py`
* **Task:** Modify the `run_suite` handler to block execution and return an error if the HIL runner is not already connected, removing the auto-connection bypass.
* **Acceptance Criteria:**
  * In `hil.py` (`run_suite`), replace the auto-connect logic:
    ```python
    # Remove:
    # if not runner._connected:
    #     runner.connect()
    ```
    with:
    ```python
    if not runner._connected:
        raise RpcError(RPC_INVALID_PARAMS, "HIL runner is not connected. Connect to the transport first.")
    ```
  * Verify that attempting to run a suite while disconnected raises an RPC error.

### 2. Correct Status Exception Handling in `hil.py` and `Hil.tsx`
* **Task:** Refactor `status` in `hil.py` to raise a proper `RpcError` on exception, and update `Hil.tsx` to handle warning payloads safely.
* **Acceptance Criteria:**
  * In `hil.py` (`status`), change the exception block to raise a standard RPC error:
    ```python
    except Exception as e:
        raise RpcError(RPC_SIDECAR_ERROR, f"Failed to retrieve HIL status: {e}") from e
    ```
  * In `Hil.tsx`, ensure that any warning `error` payload returned in a 200 response is displayed in the status block if `status.data.message` is absent.

### 3. Disable Eager Execution of the `useHilReport` Hook in `Hil.tsx`
* **Task:** Ensure the report generation hook only queries the backend after a report has been explicitly requested and a valid `session_id` is present.
* **Acceptance Criteria:**
  * Update the react-query options inside the `useHilReport` hook (or the component call site) to set `enabled: !!sessionId && reportRequested`.
  * Verify that navigating to the HIL view on a clean session does not trigger any pre-emptive `RPC_INVALID_PARAMS` errors or display invalid-parameter banners in the UI.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    hil.status
  -> {"connected": false, "transport": "none", "session_id": null, "tests_run": 0, "message": "No HIL runner initialised. Call hil.connect to start."}
```
