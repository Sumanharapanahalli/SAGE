# SAGE[ai] — ISO 13485 / FDA 21 CFR Part 11 Compliance Documentation

This document describes the compliance architecture of SAGE[ai] as it applies to medical device software development under ISO 13485 and FDA 21 CFR Part 11.

---

## 1. Audit Trail Schema and Usage

### Database

All AI actions, human decisions, and system events are recorded to an immutable SQLite database at `data/audit_log.db`.

### Schema

```sql
CREATE TABLE compliance_audit_log (
    id                    TEXT PRIMARY KEY,        -- UUID v4
    timestamp             DATETIME DEFAULT CURRENT_TIMESTAMP,
    actor                 TEXT NOT NULL,           -- Who performed the action
    action_type           TEXT NOT NULL,           -- What type of action
    input_context         TEXT,                    -- Input that triggered the action
    output_content        TEXT,                    -- AI output or system result
    metadata              JSON,                    -- Structured metadata (TraceID, GitHash, etc.)
    verification_signature TEXT                   -- Reserved for future digital signature
);
```

### Actor Values

| Actor | Description |
|:------|:------------|
| `AnalystAgent` | AI analysis of log entries |
| `DeveloperAgent` | Code review, MR creation, patch proposals |
| `MonitorAgent` | Event detection from Teams, Metabase, GitLab |
| `Human_Engineer` | Approvals, rejections, feedback |
| `System_Trigger` | Automated system events |
| `Teams_Webhook` | Incoming webhook callbacks |

### Action Type Values

| Action Type | Description |
|:------------|:------------|
| `ANALYSIS_PROPOSAL` | AI analysis of a log entry |
| `MR_REVIEW` | AI code review of a merge request |
| `MR_CREATED` | MR created from issue |
| `MR_CREATE_FAILED` | MR creation failure (also logged) |
| `CODE_PATCH_PROPOSAL` | AI-proposed code patch (unified diff) |
| `MR_COMMENT_ADDED` | Comment posted on MR |
| `FEEDBACK_LEARNING` | Human correction ingested to RAG |
| `APPROVAL` | Human approval of AI proposal |
| `REJECTION` | Human rejection with feedback |
| `EVENT_TEAMS_ERROR` | Teams error message detected |
| `EVENT_METABASE_ERROR` | Metabase error detected |
| `EVENT_GITLAB_ISSUE` | GitLab sage-ai issue detected |
| `WEBHOOK_RECEIVED` | Incoming Teams webhook callback |

### Querying the Audit Log

Via API:
```bash
curl http://localhost:8000/audit?limit=50&offset=0
```

Via Python:
```python
import sqlite3
conn = sqlite3.connect("data/audit_log.db")
rows = conn.execute(
    "SELECT * FROM compliance_audit_log ORDER BY timestamp DESC LIMIT 50"
).fetchall()
```

Via SQLite directly:
```bash
sqlite3 data/audit_log.db "SELECT timestamp, actor, action_type FROM compliance_audit_log ORDER BY timestamp DESC LIMIT 20;"
```

---

## 2. Human-in-the-Loop Gates

SAGE[ai] enforces human review before any significant action. The system follows a **propose-then-approve** model:

### Gate Types

| Gate | Location | Trigger | Action if Approved |
|:-----|:---------|:--------|:-------------------|
| Log Analysis Approval | CLI or Teams adaptive card | AI generates analysis proposal | Action recorded; engineer takes manual action |
| MR Creation | `/mr/create` endpoint (API) or Teams card | `sage-ai` issue detected | MR created in GitLab |
| Code Patch | CLI or API | `propose_code_patch()` call | Patch applied by engineer |
| Firmware Flash | Manual only | Task submitted to queue | Firmware flashed via J-Link |

### Approval Flow

```
AI Proposal Generated
        |
        v
Human Notified (CLI prompt OR Teams adaptive card)
        |
   +----+----+
   |         |
Approve    Reject
   |         |
   v         v
Logged    Feedback captured
           |
           v
        Saved to ChromaDB (RAG)
        (improves future proposals)
```

### Compliance Note

AI outputs are **never automatically executed**. Every AI proposal requires an explicit human action (approve, reject, or skip). This is enforced at the architecture level — the `AnalystAgent` and `DeveloperAgent` return proposals; they do not execute actions.

---

## 3. Traceability — TraceID System

Every significant AI action generates a UUID v4 **TraceID** returned in the API response and stored in the audit log.

### TraceID Lifecycle

1. **Generated**: When `analyst_agent.analyze_log()`, `developer_agent.review_merge_request()`, or `developer_agent.propose_code_patch()` is called
2. **Stored**: In `compliance_audit_log.id` field
3. **Returned**: In the API response for client tracking
4. **Referenced**: When human approves/rejects, the TraceID links the decision to the AI proposal
5. **Retrievable**: Via `GET /audit` or direct DB query

### Linking MRs to Issues to Audit Records

```
GitLab Issue #45
    |
    v
TraceID: a1b2c3d4-... (MR creation audit record)
    |
    v
GitLab MR !7 created
    |
    v
TraceID: e5f6g7h8-... (MR review audit record)
    |
    v
Human approval (linked by trace_id in metadata)
```

---

## 4. Data Retention Policy

### Requirements

Per ISO 13485 Section 4.2.5 and FDA 21 CFR Part 820.180:
- Quality records must be retained for the lifetime of the device or a minimum period specified by regulation (typically 5-15 years depending on device classification)
- For Class II medical devices: minimum 2 years
- For Class III or life-supporting devices: minimum duration per regulation

### Implementation

The `data/audit_log.db` SQLite file is append-only in normal operation. There is no automatic deletion.

**Backup strategy** (to be implemented per your organization's DMS):
1. Copy `data/audit_log.db` to your Document Management System nightly
2. Tag backups with software version and date
3. Retain per regulatory requirements for the device classification

### Archive Query

```sql
-- Find all actions in a date range
SELECT * FROM compliance_audit_log
WHERE timestamp BETWEEN '2026-01-01' AND '2026-12-31'
ORDER BY timestamp;

-- Find all actions for a specific log error
SELECT * FROM compliance_audit_log
WHERE input_context LIKE '%ErrorCode=0x4F%';

-- Audit trail for a specific TraceID
SELECT * FROM compliance_audit_log
WHERE id = 'your-trace-id-here'
   OR metadata LIKE '%your-trace-id-here%';
```

---

## 5. Validation Requirements

### Software Validation (IQ/OQ/PQ)

**Installation Qualification (IQ)**:
- Verify all Python dependencies are installed: `pip install -r requirements.txt`
- Verify configuration file loads correctly
- Verify database initializes: `python -c "from src.memory.audit_logger import audit_logger; print('OK')"`

**Operational Qualification (OQ)**:
- Run analysis on known test log entries and verify output format
- Verify audit log entries are created for each action
- Verify RAG memory stores and retrieves feedback correctly

**Performance Qualification (PQ)**:
- Run 50 consecutive analyses and verify all are logged
- Verify human feedback is retrieved on subsequent similar queries
- Test approval/rejection flows end-to-end

### Test Script

```python
# validation/validate_audit_trail.py (create as needed)
from src.memory.audit_logger import audit_logger
from src.agents.analyst import analyst_agent

# OQ Test 1: Audit record created for every analysis
trace_id = audit_logger.log_event(
    actor="Validation_Script",
    action_type="VALIDATION_TEST",
    input_context="IQ/OQ/PQ test run",
    output_content="System validation in progress",
    metadata={"validation_step": "OQ-001"}
)
assert trace_id is not None, "Audit log must return a trace ID"
print(f"OQ-001 PASS: Audit log operational (trace_id={trace_id})")

# OQ Test 2: Analysis produces required fields
result = analyst_agent.analyze_log("Test error for validation")
required_fields = ["severity", "root_cause_hypothesis", "recommended_action", "trace_id"]
for field in required_fields:
    assert field in result, f"Missing required field: {field}"
print("OQ-002 PASS: Analysis output contains all required fields")
```

---

## 6. AI Decision Records

Every AI decision is recorded with full context for regulatory review.

### What is Recorded

For each `ANALYSIS_PROPOSAL`:
- Full log entry text (input)
- AI severity classification
- AI root cause hypothesis
- AI recommended action
- Past context retrieved from RAG (if any)
- Timestamp
- TraceID

For each `MR_REVIEW`:
- Project ID and MR IID
- MR title and source/target branches
- Full diff (truncated to 8KB for very large changes)
- AI summary, issues found, suggestions
- Approval recommendation (boolean)

For each `CODE_PATCH_PROPOSAL`:
- File path
- Error description
- Full unified diff proposal
- AI confidence level (high/medium/low)

### Reviewing AI Decisions

All decisions can be reviewed via:
1. `GET /audit?limit=100` — paginated list
2. Direct SQLite query (see section 4)
3. Any SQLite GUI tool (e.g. DB Browser for SQLite)

---

## 7. Change Control — MR Review Process

All code changes that touch the medical device software must go through the SAGE[ai] MR review process for enhanced traceability.

### Change Control Workflow

```
1. Engineer creates feature branch
        |
        v
2. Code changes committed and pushed
        |
        v
3. MR opened in GitLab (against main/release branch)
        |
        v
4. DeveloperAgent.review_merge_request() called
   (manually, via API, or triggered by monitor)
        |
        v
5. AI review posted as MR comment
   - Summary of changes
   - Issues and concerns flagged
   - Suggestions for improvement
   - Approved: true/false
        |
        v
6. Human engineer reviews AI comments
   (AI review is advisory, not blocking)
        |
        v
7. Second human reviewer approves MR in GitLab
        |
        v
8. MR merged → audit trail updated
```

### Traceability Matrix

| Artifact | Links To |
|:---------|:---------|
| GitLab Issue (requirement) | MR (implementation) via "Closes #N" |
| MR | Spira requirement via label or description |
| SAGE[ai] TraceID | MR IID and Issue IID in audit metadata |
| Spira incident | GitLab MR via incident description or custom field |

### SOUP (Software of Unknown Provenance) Tracking

When AI-generated patches are incorporated:
1. The `CODE_PATCH_PROPOSAL` TraceID is recorded
2. The patch is applied by a human (not automatically)
3. Human engineer verifies the patch is correct
4. MR is created for the patched code
5. MR review includes the AI-patch origin in the description

---

## 8. Configuration Management

### Version Control

All SAGE[ai] source files are under Git version control. The `data/` directory (containing databases) is excluded via `.gitignore`.

### Configuration Integrity

`config.yaml` is tracked in Git. Changes to configuration require a new commit and are therefore traceable.

Environment variables (`.env`) are **NOT** tracked in Git. They must be managed via your organization's secrets management system (e.g., Azure Key Vault, HashiCorp Vault, or encrypted configuration management).

### Change Log

All significant changes to SAGE[ai] system behavior should be documented in a CHANGELOG and linked to Spira change request records. Formal change control is governed by `docs/regulatory/CHANGE_CONTROL.md`.

---

## 9. SOUP (Software of Unknown Provenance)

All third-party software components used by SAGE[ai] are identified and tracked in the SOUP Inventory in accordance with **IEC 62304:2006+AMD1:2015 §8.1.2**.

See: [`docs/regulatory/SOUP_INVENTORY.md`](regulatory/SOUP_INVENTORY.md)

Key SOUP items include:
- **FastAPI / Uvicorn** — REST API framework
- **ChromaDB / LangChain** — Vector RAG memory
- **Sentence Transformers** — Embedding model (all-MiniLM-L6-v2)
- **llama-cpp-python** (optional) — Local LLM inference
- **React 18 / TanStack Query / Recharts** — Web UI

All SOUP versions are pinned in `requirements.txt` and `web/package.json`. SOUP anomaly monitoring is conducted monthly.

---

## 10. Regulatory Documentation Index

The complete Design History File (DHF) and regulatory documentation suite is located in `docs/regulatory/`:

| Document | Purpose | Standard |
|:---------|:--------|:---------|
| [SRS.md](regulatory/SRS.md) | Software Requirements Specification | ISO 13485 §7.3 |
| [RISK_MANAGEMENT.md](regulatory/RISK_MANAGEMENT.md) | Risk analysis and controls | ISO 14971:2019 |
| [SOUP_INVENTORY.md](regulatory/SOUP_INVENTORY.md) | Third-party software inventory | IEC 62304 §8.1.2 |
| [VV_PLAN.md](regulatory/VV_PLAN.md) | Verification & Validation Plan | IEC 62304 §5.6-5.7 |
| [RTM.md](regulatory/RTM.md) | Requirements Traceability Matrix | ISO 13485 §7.3 |
| [DHF_INDEX.md](regulatory/DHF_INDEX.md) | Design History File Index | FDA 21 CFR 820.30 |
| [TEST_REPORT_TEMPLATE.md](regulatory/TEST_REPORT_TEMPLATE.md) | Test execution report template | IEC 62304 §5.6 |
| [CHANGE_CONTROL.md](regulatory/CHANGE_CONTROL.md) | Change control procedure | ISO 13485 §7.3.9 |
| [CONFIG_MGMT_PLAN.md](regulatory/CONFIG_MGMT_PLAN.md) | Configuration management | IEC 62304 §8 |
| [SECURITY_PLAN.md](regulatory/SECURITY_PLAN.md) | Cybersecurity controls | FDA Cybersecurity Guidance 2023 |
