# SAGE Feature Review — `operator`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/operator.py`  
**Frontend:** `Settings.tsx`  
**Review time:** 68s

---

## Verdict
The operator backend is technically functional and correctly enforces read-only provider validation, but the feature is unusable today by a real operator because the frontend `Settings` page completely lacks any user interface elements or form fields to view, input, or save the operator's identity.

**Works:** partly
**Score:** 4/10

---

## What Actually Works
* **Backend Data Resolution (`operator.py::get`):** The sidecar successfully resolves the operator identity from disk. The live runtime evidence proves that calling `operator.get` successfully returns the parsed JSON payload:
  `{"name": "Harish", "email": "harish.gobugari@bluedropmedical.com", "provider": "desktop-operator"}`
* **Provider Mutation Prevention:** The backend successfully guarantees audit trail integrity. Even if an operator manually edits `operator.yaml` to spoof the provider (e.g., trying to elevate privileges to `"oidc"`), `operator.py::get` hardcodes and pins `provider` to `"desktop-operator"`.
* **Blank Signer Validation:** The backend `operator.py::set` correctly raises an `RPC_INVALID_PARAMS` error if an unnamed signer is submitted, preventing blank audit logs.
* **Resilient Non-Blocking Fallback:** `operator.py::current()` successfully handles unset configurations by falling back to `"operator"`, ensuring that agent actions do not deadlock due to an unconfigured file.

---

## System-Level Findings

### 1. Absolute Frontend-Backend Disconnect (Severity: High)
* **Finding:** While the backend implements robust `operator.get` and `operator.set` RPC handlers, the frontend page (`Settings.tsx`) is completely oblivious to them. It imports and manages Active Solution switching and LLM provider configuration, but has no imports, state hooks, forms, or render components for operator management.
* **Impact:** An operator cannot configure, update, or view their identity through the application interface. It requires manual, out-of-band editing of a hidden YAML file in `.sage/operator.yaml` inside the active solution directory.

### 2. Identity Fragmentation Across Solution Switching (Severity: Medium)
* **Finding:** `_path` is injected as a solution-specific path (`<solution>/.sage/operator.yaml`). When an operator switches solutions via `SolutionPicker`, the sidecar is respawned against the new solution folder. 
* **Impact:** Operator identities are sandboxed per-solution. If an operator manages three solutions, they must configure their operator identity three separate times. If they do not, the approvals in new solutions will silently fall back to the weak `"operator"` signature, breaking audit traceability.

### 3. Compliant Sign-off Bypass / Silent Fallback (Severity: Medium)
* **Finding:** To prevent blocking, `operator.py::current()` silently falls back to signing records with the generic name `"operator"` if the identity is unset. 
* **Impact:** Under 21 CFR Part 11 §11.50, a signed record must explicitly name its signer. Silently allowing a fallback to a generic `"operator"` name without forcing a blocking configuration gate or warning the user bypasses compliance requirements. The system permits high-stakes decisions to be authorized by an anonymous generic profile.

---

## Usability Findings

### 1. Complete Dead End in UI
* **Finding:** The operator settings do not exist in the UI. An operator looking to configure their name for audit compliance will navigate to the "Settings" panel (which shows Active Solution and LLM settings) and find no mention of operator credentials or profiles.

### 2. Silent Error Handling of Malformed YAML
* **Finding:** If `operator.yaml` contains invalid syntax or is corrupted, `operator.py::get` silently logs a warning to `sidecar.operator` and returns a blank record `{"name": "", "email": "", "provider": "desktop-operator"}`.
* **Impact:** There is no mechanism in the application to notify the operator that their local settings file is corrupted. The system will simply fall back to generic `"operator"` sign-offs without raising an error in the user interface.

---

## Top 3 Fixes (optimizer-ready)

### 1. Implement Operator Identity Form in `Settings.tsx`
* **Task:** Create a dedicated React component `OperatorIdentityForm` within `Settings.tsx` to display and configure the operator.
* **Acceptance Criteria:**
  * Uses frontend queries/mutations to call `operator.get` on mount.
  * Renders a form with editable text inputs for `Name` and `Email`.
  * Validates that `Name` is not empty on submit, displaying a visible validation error.
  * Calls `operator.set` on submit and displays a green "Operator identity saved successfully" message.

### 2. Implement Global Operator Identity Fallback
* **Task:** Modify `operator.py` to look for a global config file (e.g., in a user-home `.sage/operator.yaml`) if no solution-specific file exists, or automatically clone the current operator identity config file when a new solution is created or initialized.
* **Acceptance Criteria:**
  * When switching solutions via `SolutionPicker`, if the new solution's `.sage/operator.yaml` does not exist, the sidecar automatically seeds it with the active user identity from the previous solution or a global user-level profile.

### 3. Force Identity Verification Gate for Human-in-the-Loop Decisions
* **Task:** Refactor the proposal approval handler (the code that calls `current()`) to block execution if the resolved signer is the generic fallback `"operator"`.
* **Acceptance Criteria:**
  * Any attempt to call `ProposalStore.approve` when `current()["name"] == "operator"` must raise an RPC error indicating that an operator profile is required.
  * The frontend must intercept this error and modal-prompt the user to enter their name and email before allowing them to sign the decision.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    operator.get
  -> {"name": "Harish", "email": "harish.gobugari@bluedropmedical.com", "provider": "desktop-operator"}
```
