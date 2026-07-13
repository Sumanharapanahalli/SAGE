# SAGE Feature Review — `agents`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/agents.py`  
**Frontend:** `Agents.tsx`  
**Review time:** 68s

---

## Verdict
While SAGE successfully retrieves and lists core and custom agents, the critical compliance metrics (approvals and rejections) are calculated using a fragile, unsafe substring-matching implementation on the agent's own logs, making the audit trail highly unreliable and unsafe for a regulated environment.

**Works:** partly
**Score:** 5/10

---

## What Actually Works
* **Agent Enumeration (`agents.list`):** The RPC successfully retrieves both hardcoded SAGE core roles (`analyst`, `developer`, `planner`, `monitor`) and merges them with custom roles defined in `prompts.yaml` (`game_designer`, `monetisation_advisor`, `ai_opponent_specialist`).
* **Single Agent Fetching (`agents.get`):** Successfully retrieves a single agent schema (e.g., fetching `"analyst"` returns its structural definition).
* **UI Structure and Selection (`Agents.tsx`):** The frontend correctly maps the retrieved agents into a grid of `AgentCard` components and manages selection states to fetch performance data on demand.
* **Graceful Degradation of Performance Queries:** The `performance` backend handler catches connection/query errors gracefully via a wide try/except block, returning zeroed/empty stats instead of crashing when `_logger` is not yet wired.

---

## System-Level Findings

### 1. Critical HITL & Compliance Violation (False Positive Approvals via Substring Matching)
The `performance` handler classifies whether a proposal was approved or rejected by checking if `"APPROVE"` or `"REJECT"` are substrings in the actor's *own* audit-log row:
```python
approved = sum(
    1 for r in rows
    if "APPROVE" in (r[0] or "").upper() or "approved" in (r[1] or "").lower()
)
```
* **The Bug:** If an agent outputs a proposal containing the word `"approved"` (e.g., `"Drafted clinical firmware changes; these are now approved for local testing"`), SAGE will misclassify this as a human-approved proposal.
* **The Bypass:** This query explicitly excludes human activities (`actor != 'human_via_chat'`). Consequently, it is parsing the *agent's output* rather than looking for the actual, signed *human decision record*. This defeats SAGE's core "Agents propose. Humans decide." law and constitutes a severe compliance failure under FDA/ISO guidelines.

### 2. Unhandled Operational Crash on Unseeded Databases
In `_activity_by_actor`, there is no `try/except` guard around the database query or connection initialization:
```python
def _activity_by_actor() -> dict[str, dict]:
    ...
    conn = sqlite3.connect(_logger.db_path)
    # ... executes query ...
```
If the database table `compliance_audit_log` does not exist yet (e.g., on a fresh development setup or early bootstrap phase), the query throws a `sqlite3.OperationalError`. This propagates straight to the UI, completely crashing the `agents.list` RPC rather than degrading to a list with `event_count: 0`.

### 3. Loose Actor-to-Agent Mapping (SQL Wildcard Matching)
The `performance` handler matches rows using loose wildcards:
```sql
WHERE actor != 'human_via_chat'
  AND (input_context LIKE ? OR metadata LIKE ?)
```
Querying for `"analyst"` with `"%analyst%"` will matching metadata or contexts containing unrelated values like `"co-analyst"`, `"analyst_senior"`, or even `"catalyst"`. This cross-contaminates audit metrics across agents, destroying audit trail accuracy.

### 4. Missing "Pending" State in Totals
The performance response yields `total_proposals`, `approved`, and `rejected`. Since there is no classification for "pending" proposals (those awaiting human signature), the numbers in the UI will frequently not add up (e.g., `Total: 10`, `Approved: 2`, `Rejected: 1`, leaving 7 unaccounted for). In medical compliance, keeping track of outstanding proposals is just as important as logged decisions.

---

## Usability Findings

### 1. Zero-Activity Empty State Lacks Operator Guidance
In a fresh installation (as seen in the live output, where all agents show `event_count: 0` and `last_active: null`), the UI shows "No history yet" and zeroed metrics. It provides no instructional hints or actionable prompts to guide the compliance officer on how to trigger a proposal or wire the agent activities.

### 2. Lack of Visual Separation Between Core and Custom Agents
The UI treats SAGE's hardcoded "core" agents (which control system execution and monitoring) identically to domain-specific "custom" agents (e.g., `game_designer`). The operator has no visual cues pointing out which agents have security/compliance authority and which are general-purpose utilities.

---

## Top 3 Fixes (optimizer-ready)

### 1. Shift Performance Counting to Explicit Human Decision Actions
* **File:** `agents.py`
* **Task:** Rewrite the `performance` SQL query to target explicit human decision rows (e.g., where `action_type IN ('APPROVE_PROPOSAL', 'REJECT_PROPOSAL')` or looking up decision events specifically mapped to the agent's proposal ID in the audit log). Remove all substring-based parsing of the agent's `output_content`.
* **Acceptance Criteria:**
  1. No substring searches (`"approved"` or `"rejected"`) are performed on `output_content`.
  2. The query specifically checks human compliance actions linked to the specific agent's identifier.
  3. Automated test ensures that an agent returning text containing the word `"approved"` does not increment the approval metrics.

### 2. Protect `_activity_by_actor` from SQLite Execution Errors
* **File:** `agents.py`
* **Task:** Wrap the sqlite connection and execution block in `_activity_by_actor` in a robust `try/except sqlite3.Error` block. If the table is missing or the database is locked, catch the error, log a warning via `_logger` (if initialized), and return an empty dictionary `{}`.
* **Acceptance Criteria:**
  1. Deleting the sqlite file or dropping the `compliance_audit_log` table does not cause `list_agents` to crash.
  2. Under database failure conditions, `list_agents` successfully returns the full agent list with `event_count: 0` and `last_active: null`.

### 3. Enforce Strict Agent Name Matching in Audit Queries
* **File:** `agents.py`
* **Task:** Replace loose `LIKE '%role_key%'` query checks in `performance` with precise JSON/structured queries or strict equivalence on a dedicated structured column (e.g., `json_extract(metadata, '$.agent_role') = :role_key` or matching an exact identifier).
* **Acceptance Criteria:**
  1. Performance stats for `"analyst"` do not include audit data from entries belonging to `"co-analyst"` or `"senior_analyst"`.
  2. Query results match the targeted agent role with 100% precision.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    agents.list
  -> [{"name": "analyst", "kind": "core", "description": "", "system_prompt": "", "event_count": 0, "last_active": null}, {"name": "developer", "kind": "core", "description": "", "system_prompt": "", "event_count": 0, "last_active": null}, {"name": "planner", "kind": "core", "description": "", "system_prompt": "", "event_count": 0, "last_active": null}, {"name": "monitor", "kind": "core", "description": "", "system_prompt": "", "event_count": 0, "last_active": null}, {"name": "game_designer", "kind": "custom", "description": "Game balance, difficulty curve, and player progression design", "system_prompt": "", "event_count": 0, "last_active": null}, {"name": "monetisation_advisor", "kind": "custom", "description": "IAP, ads, and subscription strategy for a casual game", "system_prompt": "", "event_count": 0, "last_active": null}, {"name": "ai_opponent_specialist", "kind": "custom", "description": "Game AI tuning \u2014 minimax, difficulty levels, and hint generation", "system_prompt": "", "event_count": 0, "last_active": null}]

[LIVE OK]    agents.get
  -> {"name": "analyst", "kind": "core", "description": "", "system_prompt": "", "event_count": 0, "last_active": null}
```
