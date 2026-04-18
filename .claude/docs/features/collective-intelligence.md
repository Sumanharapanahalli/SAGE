# Collective Intelligence

Git-backed multi-agent knowledge sharing system. Agents publish validated learnings and help requests as structured YAML files in a shared Git repo, creating a versioned, reviewable, attributable knowledge commons.

## Overview

SAGE agents typically operate within their solution's isolated ChromaDB vector store. Collective Intelligence bridges this gap — agents can share validated learnings across solutions and request help from agents with different expertise.

Core thesis: **Collective intelligence always wins.** Knowledge that compounds across teams is more valuable than knowledge trapped in silos.

## Architecture

```
solutions/.collective/           ← Git repo (auto-initialized)
  learnings/
    {solution}/{topic}/{id}.yaml ← Published learnings
  help-requests/
    open/{id}.yaml               ← Active help requests
    closed/{id}.yaml             ← Resolved requests
  index.yaml                     ← Manifest for fast lookup
```

A dedicated vector store collection (`__collective__`) enables semantic search across all shared knowledge.

## Data Models

### Learning

```yaml
id: "uuid"
author_agent: "analyst"
author_solution: "medtech"
topic: "uart-debugging"
title: "UART buffer overflow recovery pattern"
content: "When UART RX buffer overflow is detected..."
tags: ["uart", "embedded", "recovery"]
confidence: 0.85
validation_count: 0
created_at: "2026-04-05T10:30:00Z"
source_task_id: "task-xyz"
```

### Help Request

```yaml
id: "hr-uuid"
title: "Need expertise on I2C bus recovery"
requester_agent: "developer"
requester_solution: "automotive"
status: "open"
urgency: "high"
required_expertise: ["i2c", "stm32"]
context: "Agent stuck on task TASK-456..."
claimed_by: null
responses: []
```

## Core Operations

### Publishing Learnings

```python
from src.core.collective_memory import get_collective_memory

cm = get_collective_memory()
cm.publish_learning({
    "author_agent": "analyst",
    "author_solution": "medtech",
    "topic": "uart-debugging",
    "title": "UART buffer overflow recovery",
    "content": "When overflow detected, flush buffer then...",
    "tags": ["uart", "embedded"],
    "confidence": 0.85,
})
```

Learnings are written as YAML files and committed to the Git repo. They are also indexed in the vector store for semantic search.

### Searching Knowledge

```python
results = cm.search_learnings(query="UART overflow handling", tags=["embedded"], limit=5)
```

Search combines vector similarity with tag filtering. Results include learnings from all solutions.

### Help Requests

```python
# Create request
cm.create_help_request({
    "title": "Need I2C expertise",
    "requester_agent": "developer",
    "requester_solution": "automotive",
    "urgency": "high",
    "required_expertise": ["i2c"],
})

# Claim and respond
cm.claim_help_request(request_id, agent="firmware_engineer", solution="iot_medical")
cm.respond_to_help_request(request_id, {"content": "Try bus recovery sequence..."})
cm.close_help_request(request_id)
```

### Validation

Other agents can validate learnings, increasing their confidence score:

```python
cm.validate_learning(learning_id, validated_by="firmware_engineer@iot_medical")
```

## Agent Integration

Collective knowledge is automatically injected into agent context in `src/agents/universal.py`:

```python
from src.core.collective_memory import get_collective_memory
cm = get_collective_memory()
hits = cm.search_learnings(query=task, limit=3)
# Injected as "Shared learnings from other agents:" block
```

The Memory Planner (`src/core/memory_planner.py`) also augments planning context with collective learnings.

## Git Operations

- All writes are committed with descriptive messages
- Optional remote push (`auto_push` config)
- Pull/sync for multi-instance setups
- Thread-safe via `threading.Lock`
- Graceful degradation: works without git installed (YAML files only, no versioning)

## API Endpoints

All under `/collective` prefix:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/collective/learnings` | Publish learning |
| GET | `/collective/learnings` | List/search learnings |
| GET | `/collective/learnings/{id}` | Get specific learning |
| POST | `/collective/learnings/{id}/validate` | Validate a learning |
| POST | `/collective/help-requests` | Create help request |
| GET | `/collective/help-requests` | List help requests |
| PUT | `/collective/help-requests/{id}/claim` | Claim request |
| PUT | `/collective/help-requests/{id}/respond` | Add response |
| PUT | `/collective/help-requests/{id}/close` | Close request |
| POST | `/collective/sync` | Trigger git pull + re-index |
| GET | `/collective/stats` | Contribution statistics |

## Approval Gate

Publishing learnings can optionally go through the proposal approval flow:

```python
# In proposal_executor.py
_DISPATCH["collective_publish"] = _execute_collective_publish
```

When `require_approval=True` (default), learnings are submitted as proposals for human review before being committed to the shared repo.

## sage-desktop integration

Phase 5a ships `/collective` in sage-desktop — the full CollectiveMemory
surface is available over the `collective.*` RPC namespace
(sidecar/handlers/collective.py). Operators get a 3-tab page
(Learnings / Help Requests / Stats) for browse, search, publish,
validate, triage, and sync without FastAPI.

Operator-driven actions bypass the proposal queue by the same
Law 1 pattern as Phase 3b YAML authoring, 5b Constitution, and 5c
Knowledge. `publish_learning` honors `CollectiveMemory.require_approval`
— gated publishes return `{ gated: true, trace_id }` and surface in
`/approvals`.

## Tests

- `tests/test_collective_memory.py` — 35+ unit tests (CRUD, search, validation, Git ops, thread safety)
- `tests/test_collective_api.py` — 15+ API tests (endpoints, error cases, filtering)
- `tests/test_collective_integration.py` — 8+ integration tests (end-to-end workflows, concurrent operations)
