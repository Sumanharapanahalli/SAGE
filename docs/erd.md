# SAGE Framework — Entity Relationship Diagram

## Overview

SAGE uses SQLite for runtime state (audit log, proposals, task queue) and ChromaDB for vector memory. Each solution gets its own `.sage/` directory with isolated databases.

---

## Core Data Models (Mermaid)

```mermaid
erDiagram
    compliance_audit_log {
        TEXT    trace_id         PK "UUID v4"
        TEXT    timestamp        "ISO 8601 UTC"
        TEXT    actor            "user | system:<name> | human_via_chat"
        TEXT    action_type      "ANALYSIS_PROPOSAL | APPROVAL | REJECTION | ..."
        TEXT    input_context    "truncated to 500 chars"
        TEXT    output_content   "JSON string"
        TEXT    metadata         "JSON string (nullable)"
    }

    proposal_store {
        TEXT    trace_id         PK "UUID v4"
        TEXT    action_type      "yaml_edit | code_diff | agent_hire | ..."
        TEXT    risk_tier        "INFORMATIONAL | EPHEMERAL | STATEFUL | EXTERNAL | DESTRUCTIVE"
        TEXT    status           "pending | approved | rejected | expired | undone"
        TEXT    payload          "JSON — full proposal content"
        TEXT    created_at       "ISO 8601 UTC"
        TEXT    expires_at       "ISO 8601 UTC (nullable for DESTRUCTIVE)"
        TEXT    approved_by      "user identifier (nullable)"
        TEXT    feedback         "approval/rejection note (nullable)"
    }

    task_queue {
        TEXT    task_id          PK "UUID v4"
        TEXT    task_type        "ANALYZE_LOG | CREATE_MR | PLAN_TASK | ..."
        TEXT    status           "pending | running | completed | failed"
        TEXT    payload          "JSON"
        INTEGER priority         "1-10 (default 5)"
        TEXT    depends_on       "JSON array of task_ids"
        TEXT    metadata         "JSON (wave, parent_task_id, etc.)"
        TEXT    created_at       "ISO 8601 UTC"
        TEXT    completed_at     "ISO 8601 UTC (nullable)"
        TEXT    result           "JSON (nullable)"
        TEXT    error            "error message (nullable)"
    }

    feature_requests {
        TEXT    id               PK "UUID v4"
        TEXT    title            "short description"
        TEXT    description      "full description"
        TEXT    scope            "solution | sage"
        TEXT    status           "pending | planned | approved | rejected | archived"
        TEXT    priority         "low | medium | high | critical"
        TEXT    plan             "JSON — AI-generated implementation plan (nullable)"
        TEXT    created_at       "ISO 8601 UTC"
    }

    vector_store {
        TEXT    id               PK "ChromaDB document ID"
        TEXT    content          "document text"
        BLOB   embedding        "vector embedding (384 dims)"
        TEXT    metadata         "JSON (source, channel, trace_id, etc.)"
    }

    build_runs {
        TEXT    run_id           PK "UUID v4"
        TEXT    status           "planning | awaiting_approval | building | completed | failed"
        TEXT    phase            "plan_review | code_review | final_review"
        REAL   progress          "0.0 to 1.0"
        TEXT    plan             "JSON — components, agents, tasks"
        TEXT    critic_scores    "JSON — plan, code, integration scores"
        TEXT    detected_domain  "one of 13+ domains"
        TEXT    router_stats     "JSON — per-task-type agent scores"
    }

    org_config {
        TEXT    solutions        "JSON array of solution registrations"
        TEXT    channels         "JSON array of knowledge channels"
        TEXT    routes           "JSON array of task routing rules"
        TEXT    mission          "org mission statement"
        TEXT    vision           "org vision statement"
        TEXT    core_values      "JSON array of values"
    }

    compliance_audit_log ||--o{ proposal_store   : "trace_id links"
    compliance_audit_log ||--o{ task_queue        : "logged per task"
    proposal_store       ||--o{ task_queue        : "approved proposals create tasks"
    feature_requests     ||--o{ task_queue        : "planned features become tasks"
    build_runs           ||--o{ task_queue        : "build tasks routed to queue"
```

## Data Flow Summary

| Store | Location | Purpose |
|---|---|---|
| `compliance_audit_log` | `.sage/audit_log.db` | Immutable append-only compliance record |
| `proposal_store` | `.sage/audit_log.db` (same DB) | Pending HITL proposals with risk tiers |
| `task_queue` | `.sage/audit_log.db` (same DB) | Task scheduling and execution tracking |
| `feature_requests` | `.sage/audit_log.db` (same DB) | Improvement backlog per solution |
| `vector_store` | `.sage/chroma_db/` | ChromaDB vector knowledge store |
| `build_runs` | In-memory (BuildOrchestrator) | Build pipeline state |
| `org_config` | `solutions/org.yaml` | Multi-solution org configuration |

## Per-Solution Isolation

Every solution gets its own `.sage/` directory:

```
solutions/
  medtech_team/
    project.yaml
    prompts.yaml
    tasks.yaml
    .sage/                    # auto-created, gitignored
      audit_log.db            # proposals, approvals, audit trail
      chroma_db/              # vector knowledge store
  automotive/
    .sage/                    # completely separate databases
      audit_log.db
      chroma_db/
```

Two solutions on the same SAGE instance have zero data overlap.

## Key Relationships

- **trace_id** links audit log entries to proposals and back to vector memory feedback
- **task_id** connects queue entries to their subtasks (wave scheduling)
- **parent_task_id** in task metadata links subtasks to parent wave tasks
- **solution name** scopes all data — audit log, vector store, proposals, feature requests
- **X-SAGE-Tenant header** further scopes within a solution for multi-team isolation

## Audit Log Action Types

| Action Type | Source | Description |
|---|---|---|
| `ANALYSIS_PROPOSAL` | POST /analyze | Agent generated analysis proposal |
| `APPROVAL` | POST /approve | Human approved a proposal |
| `REJECTION` | POST /reject | Human rejected a proposal |
| `FEEDBACK_LEARNING` | POST /reject | Rejection feedback stored in vector memory |
| `MR_REVIEW` | POST /mr/review | AI code review completed |
| `MR_CREATED` | POST /mr/create | Merge request created |
| `MR_CREATE_FAILED` | POST /mr/create | MR creation failed |
| `WEBHOOK_RECEIVED` | POST /webhook/* | Inbound webhook processed |
| `TASK_SUBMITTED` | POST /tasks/submit | Task added to queue |
| `TASK_COMPLETED` | Queue worker | Task execution completed |
| `KNOWLEDGE_ADDED` | POST /knowledge/add | Knowledge entry added |
| `KNOWLEDGE_DELETED` | DELETE /knowledge/entry | Knowledge entry removed |
| `BUILD_STARTED` | POST /build/start | Build run initiated |
| `BUILD_DRIFT_WARNING` | Build orchestrator | Anti-drift checkpoint fired |
| `CHAT_ACTION` | POST /chat/execute | Chat-initiated action executed |
| `AGENT_HIRED` | POST /agents/hire | New agent role proposed |

## Elder Fall Detection ERD

For the `elder_fall_detection` solution, a PostgreSQL schema with HIPAA-compliant encryption is defined. See `solutions/elder_fall_detection/` for the full schema including:

- `users` — PII encrypted via pgcrypto (name, email, phone, emergency contacts)
- `devices` — device registry with owner/status tracking
- `fall_events` — fall detection events with encrypted GPS coords
- `gps_history` — continuous telemetry with encrypted lat/lon
- `audit_log` — solution-specific append-only audit trail
- Row-Level Security (RLS) policies per role (admin, wearer, caregiver, system)
