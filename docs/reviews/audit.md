# SAGE Feature Review — `audit`

**Reviewer:** Gemini (independent, cross-vendor)  
**Solution probed:** four_in_a_line  
**Backend:** `sage-desktop/sidecar/handlers/audit.py`  
**Frontend:** `Audit.tsx`  
**Review time:** 85s

---

## Verdict
The SAGE audit feature is only partly usable today because while it successfully logs and lists events, it fails its core compliance mandate by allowing unsigned, unapproved proposal events to exist without validation, and lacks crucial UI search mechanisms for trace auditing.

**Works:** partly  
**Score:** 5/10

## What Actually Works
* **Audit Event Retrieval:** The backend handler in `audit.py` successfully connects to SQLite and executes `audit.list` to return logged events. The live runtime evidence shows 1 logged event of type `ANALYSIS_PROPOSAL` was successfully returned (`"total": 1`).
* **Statistical Aggregation:** The `audit.stats` handler accurately groups and sums events by their action type, as verified by the live output: `{"total": 1, "by_action_type": {"ANALYSIS_PROPOSAL": 1}}`.
* **Action Type Dropdown Filtering:** The frontend page `Audit.tsx` correctly extracts categories from `stats.data?.by_action_type` to dynamically populate the "Action type" selection element and drives query updates.
* **Chronological Sorting:** The backend handler strictly enforces a descending sort order (`ORDER BY timestamp DESC, rowid DESC` in `list_events`) to show operators the newest compliance events first.

## System-Level Findings
* **Severity 1 (Compliance Bypass): Silent Verification Failures.** SAGE’s absolute rule is "Agents propose. Humans decide." However, the live event output shows an `ANALYSIS_PROPOSAL` in an `OK` status despite having `approved_by: null`, `approver_email: null`, and `verification_signature: null`. The system permits unapproved, unsigned agent proposals to reside in the database as "valid" audit records, completely bypassing compliance validation.
* **Severity 2 (Data Integrity): DB Schema Fragmentation & Performance Degradation.** The `trace_id` column is left `null` because the writer dumps it directly into the `metadata` JSON block. The backend handler `audit.py` is forced to resolve this via SQLite's runtime `json_extract` function. This prevents database index lookup on the primary query column, forcing a full-table scan for every single trace filtering event (`get_by_trace` and `list_events`). This will trigger timeout failures under real-world production volumes.
* **Severity 3 (Audit Timeline Breakage): Orphaned Audit Entries.** The live event returned has no trace ID associated with it (`trace_id: null` in both the column and the metadata block). Without a trace ID, there is no mechanical link connecting the agent's input context (the 12 frame drop error) with any downstream human decision, creating a severe gap in the audit trail.

## Usability Findings
* **Missing Trace Search Input:** Even though `list_events` accepts a `trace_id` parameter, `Audit.tsx` does not expose any search input field for it. An operator looking for a specific transaction trace must manually paginate through hundreds of pages of logs.
* **Dead-End Trace Routing:** When an event has a `trace_id` value of `null` (such as the live event shown), clicking it triggers a dead-end state. The UI either fails silently or attempts to load a trace view with a null/empty string.
* **Lack of Compliance Visual Indicators:** The frontend `AuditTable` receives raw events but does not display badge states for whether an entry is "Signed," "Approved," or "Requires Human Approval." A human reviewer cannot quickly identify which proposals are pending action or which failed validation.
* **No Raw JSON Inspector:** Important operational data (such as the raw JSON structure of proposed fixes in `output_content`) is serialized as a flat string. There is no expander or formatting utility to let an operator read raw payloads cleanly.

## Top 3 Fixes (optimizer-ready)

### 1. Add Trace ID Search Input & Block Null-Trace Routing in Frontend
* **Task:** Modify `Audit.tsx` to add a controlled text input for searching by Trace ID. Update the component to pass this search string to the `useAuditEvents` query hook. In the rendering table, disable the click-to-trace interaction and display a warning tooltip if `event.trace_id` is null or missing.
* **Acceptance Criteria:** 
  1. A text input labeled "Search Trace ID" is visible next to the "Action type" select box.
  2. Input changes trigger a reload of events filtered by the specific trace ID.
  3. Events lacking a trace ID display a red "No Trace" badge, and clicking on them does not transition the screen to `AuditTraceDetail`.

### 2. Implement Automated Signature and Approval Verification in Backend
* **Task:** Update `_row_to_event` in `audit.py` to enforce compliance checks. If `action_type` is `ANALYSIS_PROPOSAL`, confirm that `verification_signature`, `approved_by`, and `approver_email` are not null. If any of these are missing, inject a computed key `"compliance_status": "FAILED_VERIFICATION"` and `"compliance_alerts": ["Missing signature", "No human approver details"]` into the returned dictionary.
* **Acceptance Criteria:**
  1. Raw SQL rows with null signature fields result in JSON payloads containing the compliance alert flags.
  2. Write a unit test that mocks an unsigned event from the DB and asserts that `_row_to_event` flags it as a compliance failure.

### 3. Populating and Indexing the Dedicated `trace_id` Column
* **Task:** Create a migration script (or update the DB initialization) to add a database index on the `trace_id` column of `compliance_audit_log`. Modify the database write-path (or a backfill query) to extract `trace_id` from `metadata` and write it directly to the dedicated `trace_id` column. Update `audit.py`'s `list_events` and `get_by_trace` to query the `trace_id` column directly, completely removing the slow `json_extract` fallback for indexed rows.
* **Acceptance Criteria:**
  1. An index on `trace_id` is verified to exist on the database table.
  2. Running `EXPLAIN QUERY PLAN` on `get_by_trace` confirms the query uses the index rather than performing a scan of the `compliance_audit_log` table.

---

## Live Runtime Evidence (raw)

```
[LIVE OK]    audit.list
  -> {"total": 1, "limit": 50, "offset": 0, "events": [{"id": "42230073-f67c-42e9-bbe1-3f7163c6ac3e", "timestamp": "2026-07-13T19:36:46.997988+00:00", "trace_id": null, "event_type": null, "status": "OK", "actor": "AnalystAgent", "action_type": "ANALYSIS_PROPOSAL", "input_context": "ERROR: game loop dropped 12 frames on move commit; board state desynced from renderer.", "output_content": "{\"severity\": \"AMBER\", \"category\": \"performance\", \"root_cause_hypothesis\": \"Move commit triggers a synchronous board state update that blocks the render thread for 12+ frames, causing the renderer's cached state to fall out of sync with the authoritative game state \\u2014 likely a missing or deferred setState/render flush after the minimax search resolves.\", \"recommended_action\": \"Audit the move-commit code path: ensure board state mutation and renderer update are atomic (or that the renderer subscribes reactively to state changes). If minimax runs on the main thread, move it to a worker/async context and flush the renderer only after state is confirmed committed. Add a frame-time profiler breakpoint at the commit callsite to isolate whether the stall is in AI computation, win-detection, or animation sequencing.\", \"affects_live_players\": true}", "metadata": {}, "verification_signature": null, "approved_by": null, "approver_role": null, "approver_email": null, "approver_provider": null, "request_id": null}]}

[LIVE OK]    audit.stats
  -> {"total": 1, "by_action_type": {"ANALYSIS_PROPOSAL": 1}}
```
