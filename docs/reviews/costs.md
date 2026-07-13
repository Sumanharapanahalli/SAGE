# SAGE Feature Review — `costs`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/costs.py`  
**Frontend:** `Costs.tsx`  
**Review time:** 40s

---

## Verdict
Yes, the costs feature is usable today by a real operator to view aggregate LLM spending metrics and directly configure monthly budgets, though critical vulnerabilities in file concurrency and a complete lack of compliance audit logging for manual updates severely undermine SAGE's regulatory design.

**Works:** partly
**Score:** 6/10

## What Actually Works
* **Spend Summarization (`costs.summary`):** The backend successfully queries the SQLite database table `llm_costs` and yields detailed statistics: total spending (`$0.027979`), call volume (`130`), input/output token counts (`8747`/`827`), average cost/call (`$0.00021522`), and proper breakdowns by model (`llama3.2`, `claude-sonnet-4-6`, `gemini-2.5-flash`) and solution (`starter`, `four_in_a_line`).
* **Daily Spends breakdown (`costs.daily`):** Returns chronological, daily-grouped cost structures (e.g., 63 calls, `$0.010887` on `2026-07-11` and 67 calls, `$0.017091` on `2026-07-13`).
* **Interactive Frontend Dashboards:** `Costs.tsx` correctly renders summary statistics, structured lists for model and solution costs, and a structured daily table based on the live RPC responses.
* **Direct Budget Writing (`set_budget`):** The backend successfully reads, modifies, and dumps YAML structures back to the config path (e.g., under `llm.budgets.per_solution[key]`) to save configuration state.

## System-Level Findings
* **No Compliance Logging / Audit Trail Bypass (High Severity):** SAGE's foundational design requires a permanent, verifiable audit trail. While the backend bypassed the "proposal queue" for `set_budget` because it represents a direct operator action, it fails to write *any* event to the compliance or audit logs. In regulated industries (medical/firmware), manual budget adjustments represent high-risk operations and must be audit-logged.
* **Concurrent YAML Write Corruption Risk (High Severity):** `costs.py:set_budget` implements a non-atomic read-modify-write cycle on `config.yaml` (`_yaml.safe_load` followed by `_yaml.dump`). Because it lacks any file-locking mechanisms (e.g., exclusive lock / `portalocker`), simultaneous writes by multiple operators or an background agent updating other `config.yaml` keys will result in race conditions, lost updates, or outright configuration file corruption.
* **Incomplete Sandbox Isolation (Medium Severity):** `_resolve_config_path` infers file paths directly from the shell's `SAGE_ROOT` environment variable or walks upward relative to `__file__`. There is no strict verification that the resolved path is confined inside the designated workspace root, exposing the system to potential directory traversal vulnerabilities if `SAGE_ROOT` is malformed or hijacked.

## Usability Findings
* **Truncated Code and Broken Success Affordance (High Severity):** The frontend implementation in `Costs.tsx` is truncated exactly at the success state render block: `Budget set: {f...`. This incomplete syntax means the UI either crashes on render when a budget is set or lacks a closed JSX tag, rendering the form success feedback state broken.
* **Dead-End Parameters in UI (Medium Severity):** The frontend hardcodes `undefined` for `tenant` and `solution` params when executing queries `useCostsSummary(undefined, undefined, periodDays)` and `useCostsDaily(undefined, undefined, periodDays)`. Even though the backend fully supports granular tenant/solution spend querying, the operator is restricted to a global view with no search/filter dropdowns.
* **Unsanitized Key Fallback (Low Severity):** If the user enters an invalid or empty string for `budgetSolution`, the backend silently defaults the budget target key to `tenant` or `"default"`. This can lead to operators accidentally overriding global budgets when they intended to target a specific (but misspelled) solution.

## Top 3 Fixes (optimizer-ready)

1. **Implement Atomic Writes and File Locking for `config.yaml`**
   * *Task:* Modify `set_budget` in `costs.py` to use an exclusive file lock (using standard OS-level locking or a utility wrapper) during the read-modify-write sequence. Write the modified YAML content first to a temporary file in the same directory, then replace the target `config.yaml` atomically.
   * *Acceptance Criteria:* Verify via parallel automated test workers that 10 concurrent calls to `set_budget` result in zero lost writes, zero file corruptions, and a valid `config.yaml` output.

2. **Establish Compliance Audit Trail for Budget Overrides**
   * *Task:* Integrate SAGE's compliance log writer into `costs.py:set_budget`. Whenever a budget is updated, write a structured audit record containing the timestamp, operator identity, previous budget limit, and newly set limit.
   * *Acceptance Criteria:* Executing `costs.set_budget` must successfully append a verifiable compliance entry to the database audit log, raising an `RPC_SIDECAR_ERROR` if the audit write fails.

3. **Complete Frontend Success State and Add Solution Filtering**
   * *Task:* Repair the truncated syntax in `Costs.tsx` to close the JSX layout securely. Replace the hardcoded `undefined` parameters in `useCostsSummary` and `useCostsDaily` with active state variables bound to new tenant/solution selection controls in the UI.
   * *Acceptance Criteria:* The UI compiles without error. Selecting a solution from a dropdown correctly filters both the Summary and Daily spend tables by propagating the filter arguments to the active RPC hook calls.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    costs.summary
  -> {"total_cost_usd": 0.027979, "total_calls": 130, "total_input_tokens": 8747, "total_output_tokens": 827, "avg_cost_per_call": 0.00021522, "by_model": [{"model": "llama3.2", "calls": 21, "cost": 0.018558}, {"model": "claude-sonnet-4-6", "calls": 103, "cost": 0.009414}, {"model": "gemini-2.5-flash", "calls": 6, "cost": 6.7799999999999995e-06}], "by_solution": [{"solution": "starter", "calls": 129, "cost": 0.02270478}, {"solution": "four_in_a_line", "calls": 1, "cost": 0.005274}], "period_days": 30, "tenant": null, "solution": null}

[LIVE OK]    costs.daily
  -> {"daily": [{"date": "2026-07-11", "calls": 63, "cost_usd": 0.010887}, {"date": "2026-07-13", "calls": 67, "cost_usd": 0.017091}], "count": 2, "period_days": 30}
```
