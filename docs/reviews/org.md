# SAGE Feature Review — `org`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/org.py`  
**Frontend:** `Organization.tsx`  
**Review time:** 62s

---

## Verdict

The "org" feature is barely usable for basic initial configuration, but it is severely compromised by broken UI state synchronization, an inability to clear or delete fields, silent error swallowing on route discovery, and a complete compliance bypass.

**Works:** partly  
**Score:** 4/10

---

## What Actually Works

Based on the live evidence and source code:
* **Initial Profile Loading:** The `org.get` RPC successfully fetched the organization identity (`"name": "Acme Corp"`, `"mission": "Only mission"`, `"vision": "A better world by 2040"`, `"core_values": ["Integrity", "Speed"]`).
* **UI Text Field Population:** The frontend page (`Organization.tsx`) correctly binds and displays these fetched values in the form inputs on the very first render.
* **Saving Structured Updates:** Clicking "Save" triggers the `update` mutation, and `org.py` successfully writes the edited identity fields back to `<sage_root>/solutions/org.yaml` if they contain text.
* **Reload Action:** Clicking "Reload" successfully triggers the `reload` RPC handler on the backend to refresh the `OrgLoader` cache.

---

## System-Level Findings

### 1. Inability to Clear or Delete Fields (Critical severity)
In `org.py`'s `update()` function, the backend updates fields using conditional checks:
```python
if name is not None:
    org_section["name"] = name
```
In `Organization.tsx`, clearing an input field sends `undefined` (e.g., `mission: mission.trim() || undefined`), which translates to a omitted or `None` value in the RPC payload. Because the backend checks `if field is not None`, **cleared fields are silently ignored by the backend.** Once an operator enters a mission, vision, or core value, they can never clear or delete it via the UI; the old value remains locked on disk.

### 2. Silent Failures & Swallowed Exceptions in Route Discovery (Critical severity)
In `org.py`'s `get()`, route enrichment is wrapped in a bare `except Exception` block:
```python
except Exception:  # noqa: BLE001 — routes are best-effort enrichment
    routes = []
```
The live evidence shows `routes: []`. This could mean the system is merely unseeded (no routes are defined in any solutions), or it could mean the backend is completely broken (e.g., `OrgLoader` threw an exception, or `_require_sage_root()` failed). Because the exception is swallowed without logging, reporting, or alerting the client, there is no way for an operator to diagnose structural or syntax issues in the solution files.

### 3. Absolute Audit Trail & Compliance Bypass (High severity)
SAGE's core mandate is: *"Agents propose. Humans decide. Every agent proposal must pass a human approval gate; the audit log is the compliance record."*
The `org.yaml` file *"shapes every solution's onboarding and agent context."* However, `org.py` explicitly bypasses audit logging:
```python
# Operator-driven edits bypass the proposal queue... No audit logging here either...
```
This is a critical regulatory loophole. A human operator can silently and untraceably edit the company mission, vision, or core values directly in the desktop UI. Because these fields define agent context and guardrails, this lack of an audit trail allows silent modification of the safety/alignment baseline without generating a compliance record.

### 4. Unhandled Crash on Corrupted `org.yaml` (Medium severity)
If `org.yaml` is manually edited and contains a non-dictionary root (e.g., a list `[1, 2, 3]` or is empty), `_read_org_yaml()` returns it directly. In `update()`, the code attempts to call:
```python
if not isinstance(existing.get("org"), dict):
```
If `existing` is a list, this will throw an unhandled `AttributeError: 'list' object has no attribute 'get'` and crash the sidecar RPC server.

### 5. Deceptive Reload Success Status (Medium severity)
In `org.py`'s `reload()`, if `reload_org_loader()` throws an exception, it is caught and silently ignored:
```python
except Exception:
    pass
```
The RPC still returns `{"status": "reloaded"}`, falsely assuring the operator that a configuration reload succeeded when it actually failed.

---

## Usability Findings

### 1. Form Inputs Locked on Initial Load (Severe severity)
In `Organization.tsx`, the form relies on a one-time synchronization state `initialized`:
```typescript
const [initialized, setInitialized] = useState(false);
useEffect(() => {
  if (!initialized && query.data) {
    ...
    setInitialized(true);
  }
}, [initialized, query.data]);
```
Once `initialized` is set to `true`, the form is decoupled from the query data. If an operator clicks "Reload" to fetch modified values from disk, the query updates, but the form text inputs do not change. The operator is trapped looking at stale data with no visual indication that the UI is out of sync.

### 2. Blind Core Values Input (Low severity)
Core values are structured as an array of strings in YAML (`["Integrity", "Speed"]`), but the UI forces the operator to edit them in a plain `<textarea>` separated by line breaks. There is no real-time array validation or list UI (e.g., tag chips or a dynamic list input), making formatting errors highly likely.

### 3. Ambiguous Empty Route State (Low severity)
The "Cross-team routes" panel renders "No cross-team routes declared" when `routes` is empty. Because route loader errors are swallowed silently, the operator cannot tell if the zero routes are due to an empty configuration or a broken backend parser.

---

## Top 3 Fixes (optimizer-ready)

### 1. Fix State Locking and Synchronize Form on Reload
* **File:** `Organization.tsx`
* **Task:** Remove the `initialized` state logic. Implement a mechanism to reset/re-initialize the local state inputs (`name`, `mission`, `vision`, `coreValues`) whenever the query successfully refetches (e.g., by checking if `query.isSuccess` or utilizing `query.data` in combination with a React key, or updating values inside a `useEffect` that triggers when the reload mutation succeeds).
* **Acceptance Criteria:** Modifying `solutions/org.yaml` on disk and clicking the "Reload" button in the UI must immediately update the visible text fields with the new values.

### 2. Allow Field Deletion and Prevent Server Crashes in `org.py`
* **File:** `org.py`
* **Task:** 
  1. Modify `update()` to explicitly delete keys from `org_section` (or set them to empty values) if they are sent as `None` or empty strings/arrays, instead of skipping them.
  2. Ensure `existing` is safely validated as a dictionary after reading: if `existing` is not a `dict`, initialize it to `{}` before accessing keys.
* **Acceptance Criteria:** Clearing the "Mission" text field in the UI and clicking "Save" must result in the `"mission"` key being removed or emptied inside `solutions/org.yaml` on disk. Creating a malformed `org.yaml` must not crash the RPC server on subsequent requests.

### 3. Expose Reload/Route Loading Errors to the UI
* **Files:** `org.py`, `Organization.tsx`
* **Task:**
  1. In `org.py`'s `get()`, replace the bare `except Exception` with a try-catch that logs the exception and returns a detailed error message in the payload (e.g., `{"routes": [], "error": str(e)}`).
  2. In `org.py`'s `reload()`, raise an `RpcError` if `reload_org_loader()` fails instead of returning `{"status": "reloaded"}`.
  3. In `Organization.tsx`, display a clear error banner inside the "Cross-team routes" section and above the reload button if an error string is returned by the RPC handlers.
* **Acceptance Criteria:** If a solution file contains a syntax error, the "Cross-team routes" panel must display a warning with the file path and parse error details, and the "Reload" button must display a failure alert instead of reporting a false success.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    org.get
  -> {"org": {"core_values": ["Integrity", "Speed"], "mission": "Only mission", "name": "Acme Corp", "vision": "A better world by 2040"}, "routes": []}
```
