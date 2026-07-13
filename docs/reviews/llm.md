# SAGE Feature Review — `llm`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/llm.py`  
**Frontend:** `Settings.tsx`  
**Review time:** 121s

---

## Verdict
The SAGE LLM configuration and switching feature is completely broken and unusable for a real operator today due to severe Python syntax corruption in the backend handler, blocking synchronous event-loop calls that crash the runtime, and a synthetic proposal architecture that bypasses compliant human-in-the-loop (HITL) audit logs.

**Works:** no
**Score:** 1/10

---

## What Actually Works
* **Current LLM Info Retrieval (`llm.get_info`)**: The live runtime output proves that `llm.get_info` executed successfully, returning the active provider (`ClaudeCodeCLI (claude-sonnet-4-6)`), the current model (`claude-sonnet-4-6`), and an available list of 5 providers (`gemini`, `claude-code`, `ollama`, `local`, `claude`).
* **Provider Fallback Safeguard**: The `_switchable_providers()` helper successfully implements a try/except import block that prevents a partial SAGE import failure from taking down the entire settings page by falling back to a hardcoded list of providers.
* **Frontend Settings Layout Structure**: The `Settings` component has clear visual segmentation for "Active solution", "Current LLM", and "Switch LLM" forms, allowing users to view current configurations.

---

## System-Level Findings

### 1. Fatal Syntax Corruption in `llm.py` (High Severity)
Line 51 of `llm.py` contains corrupt, un-compilable text: ` @.platformio\python3\Lib\__pycache__\dataclasses.cpython-311.pyc`. This is a syntax error that prevents the Python interpreter from importing `llm.py` at runtime. The fact that the live run of `llm.get_info` completed successfully indicates it either ran before this file corruption occurred, or is executing against a cached/stale version of the module in memory.

### 2. Broken Class Instantiation due to Missing `@dataclass` Decorator (High Severity)
The class `_SyntheticProposal` is structured as a dataclass, but the `@dataclass` decorator was overwritten by the corrupted platformio cache path string. Because of this, `_SyntheticProposal` is interpreted as a standard class. The call `_SyntheticProposal(payload={...})` in `switch_llm` will fail at runtime with `TypeError: _SyntheticProposal() takes no arguments` because standard Python classes do not automatically generate an initialized constructor matching the typed class attributes. Furthermore, the `field(default_factory=dict)` descriptor will fail to evaluate correctly on an undecorated class.

### 3. Async Event-Loop Blockage & Crash Risk (High Severity)
`switch_llm` invokes `asyncio.run(_run_execute_llm_switch(proposal))`. In modern async application frameworks (where SAGE sidecar typically runs), invoking `asyncio.run()` within an already active event loop raises a fatal `RuntimeError: asyncio.run() cannot be called from a running event loop`. This will instantly crash the request handler.

### 4. Bypassing the Human-in-the-Loop (HITL) Gate & Compliance Audit (Medium Severity)
SAGE's core law mandates: *"Agents propose. Humans decide."* However, `switch_llm` fabricates a `_SyntheticProposal` under the hood and executes it immediately via `asyncio.run(_run_execute_llm_switch(proposal))` instead of routing it through SAGE's standard pending proposal database state transitions. This bypasses the human approval gate entirely and risks failing to record the transaction in the compliance audit trail.

### 5. Static Trace ID Collisions (Medium Severity)
`_SyntheticProposal` hardcodes `trace_id: str = "desktop-switch"`. In a regulated industry audit log, every transaction must have a unique identifier. Hardcoding a static string guarantees ID collisions, meaning subsequent LLM switches will overwrite or corrupt previous entries in the audit trail, compromising compliance records.

### 6. Brittle Gateway Introspection (Low Severity)
The helper `_current_model(gw)` uses a series of dynamic `getattr` guesses on the provider object (`model`, `model_name`, `_model`). This proves there is no strict typing interface or contract for providers in `llm_gateway`, creating high fragility if a provider's internal attributes change.

---

## Usability Findings

### 1. Stale "Current LLM" Display (No Cache Invalidation)
The frontend uses `useLlmInfo()` to display the current provider and model, but the `useSwitchLlm` mutation has no success callback to invalidate or refresh the `llmInfo` query. When an operator successfully switches the LLM, the "Current LLM" box remains stale and unchanged until they manually reload the page.

### 2. Opaque Error Reporting
When the switcher encounters a backend RPC error, the UI merely renders: `Switch failed.` SAGE operators are left completely in the dark regarding whether the failure was due to an invalid path, network timeout, unsupported provider, or a fatal backend syntax error.

### 3. No Solution Switching Loading State / Reconnection Strategy
The frontend allows selecting a new solution which "will respawn the sidecar against the chosen solution." When the sidecar restarts, the network connection is severed. The UI does not handle this transition; there is no warning banner, progress overlay, or auto-reconnection loop, which leaves the operator staring at an unresponsive screen or a "Failed to load LLM info" error.

### 4. Missing Field Validations
`switch_llm` in the backend accepts `claude_path`, but there is no validation in the backend or frontend to verify that this path is valid or exists prior to attempting execution, causing obscure downstream failures.

---

## Top 3 Fixes (optimizer-ready)

### 1. Restore `@dataclass` Decorator and Fix `_SyntheticProposal` Syntax
* **Task**: Open `llm.py`, delete the corrupted line 51 containing ` @.platformio\python3\Lib\__pycache__\dataclasses.cpython-311.pyc`, and replace it with the proper `@dataclass` decorator. Ensure `_SyntheticProposal` is a valid python dataclass.
* **File**: `llm.py`
* **Acceptance Criteria**:
  - The corrupted platformio cached file line must be removed.
  - `@dataclass` must decorate the `_SyntheticProposal` class.
  - Running a Python import test on `llm.py` must succeed without `SyntaxError`.
  - Instantiating `_SyntheticProposal(payload={"provider": "ollama"})` must successfully assign the fields without throwing a `TypeError`.

### 2. Refactor RPC Handler to Support Non-Blocking Async Execution & Dynamic Tracing
* **Task**: Convert `switch_llm` to an asynchronous function (`async def`), replace the synchronous `asyncio.run` wrapper with a native `await` expression to prevent event loop blockages, and dynamically generate a unique `trace_id` for each proposal execution.
* **File**: `llm.py`
* **Acceptance Criteria**:
  - Change signature of `switch_llm(params: dict)` to `async def switch_llm(params: dict)`.
  - Replace `asyncio.run(_run_execute_llm_switch(proposal))` with `await _execute_llm_switch(proposal)`.
  - In `_SyntheticProposal`, replace `trace_id: str = "desktop-switch"` with a dynamically generated UUID (e.g. `uuid.uuid4().hex`) to ensure compliant audit logs.

### 3. Implement Frontend Query Invalidation, Dynamic Error Propagation, and Reconnection States
* **Task**: Update `Settings.tsx` to automatically invalidate query caches upon successful mutations, display the detailed server error message, and handle the sidecar restart gracefully.
* **File**: `Settings.tsx`
* **Acceptance Criteria**:
  - Pass an `onSuccess` handler to the `useSwitchLlm` mutation that calls `queryClient.invalidateQueries({ queryKey: ["llmInfo"] })`.
  - Replace the static text `Switch failed.` with a dynamic error string extracted from `switcher.error` (e.g., `switcher.error.message || "Switch failed."`).
  - Display an overlay or loading modal when `solutionSwitcher.isPending` is true to prevent multiple clicks, and implement a graceful reconnection banner if the sidecar connection drops during respawn.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    llm.get_info
  -> {"provider_name": "ClaudeCodeCLI (claude-sonnet-4-6)", "model": "claude-sonnet-4-6", "available_providers": ["gemini", "claude-code", "ollama", "local", "claude"]}
```
