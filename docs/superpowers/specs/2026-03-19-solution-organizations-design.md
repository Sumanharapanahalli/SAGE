# Solution Organizations — Design Spec
**Date:** 2026-03-19
**Status:** Approved for planning
**Scope:** SAGE Framework (`scope: sage`)

---

## Problem

Every SAGE solution is fully isolated today. In a real company (e.g., an IoT medical device company), multiple teams work toward the same product goal but operate independently. Each team rediscovers the same patterns, their agents have no shared context, and cross-team work requires manual coordination. This creates waste at exactly the scale where SAGE should eliminate it.

---

## Goal

Enable multiple SAGE solutions to be grouped into an **organization** with:
1. **Hierarchical inheritance** — child solutions inherit prompts, task types, and knowledge from parent solutions
2. **Knowledge channels** — named, directional shared knowledge stores between specific teams
3. **Cross-team task routing** — solutions can dispatch tasks into other teams' queues (with explicit permission)
4. **Visual org management** — admin UI to configure the org graph, channels, and routing links

---

## Architecture

### File layout

```
$SAGE_SOLUTIONS_DIR/
  org.yaml                        ← org-level config; always at SAGE_SOLUTIONS_DIR root
  company_base/                   ← root solution
  iot_medtech_product/            ← product-level solution
  medtech_firmware/               ← team solution
  medtech_hardware/
  medtech_clinical/
  medtech_field_support/
  medtech_manufacturing/
  medtech_regulatory/
```

`org.yaml` lives at the root of `SAGE_SOLUTIONS_DIR` (the directory pointed to by the `SAGE_SOLUTIONS_DIR` env var, defaulting to `solutions/`). A SAGE instance has at most one `org.yaml`. Its absence means no org is configured and all solutions behave as today.

### org.yaml schema

```yaml
org:
  name: "iot_medtech_company"
  root_solution: "company_base"   # the top of the inheritance tree

  knowledge_channels:
    hardware-firmware:            # name; normalized to underscores for chroma: channel_hardware_firmware
      producers: [medtech_hardware]
      consumers: [medtech_firmware]
    device-regulatory:
      producers: [medtech_hardware, medtech_firmware]
      consumers: [medtech_regulatory]
    field-support-context:
      producers: [medtech_hardware, medtech_firmware, medtech_manufacturing]
      consumers: [medtech_field_support]
```

**Channel name normalization rule:** channel names in `org.yaml` may use hyphens or underscores. They are normalized to lowercase underscores when used as chroma collection names: `hardware-firmware` → `channel_hardware_firmware`.

### project.yaml extensions (two new fields)

```yaml
# In any solution's project.yaml:
parent: "iot_medtech_product"          # optional — single parent only; no multiple parents

cross_team_routes:                     # optional — task routing permissions (outbound only)
  - target: medtech_firmware
  - target: medtech_hardware
```

### Circular inheritance detection

On `org.yaml` load, `OrgLoader` walks every solution's `parent:` chain. If a cycle is detected (A → B → C → A), it raises `ValueError` with the cycle path and refuses to start. This is checked at startup and on `POST /org/reload`.

---

## Feature 1: Hierarchical Inheritance

### Prompts inheritance

On solution load, `OrgLoader.get_merged_prompts(solution_name)` walks the parent chain bottom-up (child → parent → grandparent → ... → root) and merges `prompts.yaml` files:
- Keys present in the child override the same key in the parent
- Keys present only in the parent are included unchanged
- Merge is a shallow dict merge: each top-level key is either child's or parent's; no deep merge within a key

### Task types inheritance

`OrgLoader.get_merged_tasks(solution_name)` walks the same chain and merges `tasks.yaml`:
- A conflict occurs when the same `task_type` string appears in both child and parent
- On conflict, the child's **entire entry** (description + payload schema + hooks + sandbox policy) replaces the parent's entry — no partial/deep merge
- `task_hooks` and `task_sandbox_policies` are inherited on the same rule (child entry wins entirely)
- New task types in the child are appended to the merged set

### Knowledge inheritance (RAG queries)

When an agent calls `vector_store.query(text, n_results)` the store is resolved as follows:

1. Build the parent chain for the active solution: `[child, parent, grandparent, ...]`
2. For each solution in the chain, instantiate a `VectorMemory` pointing at that solution's `.sage/chroma_db/` path (see VectorMemory factory below)
3. Query each with `n_results` results
4. Merge all result lists: deduplicate by exact content match, then sort **ascending** by chroma distance score (lower distance = more relevant; lowest distance first). Return top `n_results` from the merged list.

**VectorMemory factory:** `VectorMemory` is refactored to accept an explicit `db_path` argument (defaulting to the active solution's `.sage/` path as today). A new `get_vector_memory(solution_name: str) -> VectorMemory` factory in `src/memory/vector_store.py` returns a per-solution instance. The module-level singleton is preserved for backward compatibility but delegates to the factory for the active solution. All org-aware queries instantiate instances directly via the factory — no global state mutation.

---

## Feature 2: Knowledge Channels

### Storage

Each channel's chroma collection lives in the **org root solution's** `.sage/chroma_db/`.

Root solution path: `os.path.join(SAGE_SOLUTIONS_DIR, org_config["root_solution"], ".sage", "chroma_db")`.

Collection name: `channel_<normalized_channel_name>` (e.g. `channel_hardware_firmware`).

### Writing to a channel (producer)

`POST /knowledge/add` gains an optional `channel` field:

```json
{
  "content": "...",
  "metadata": {...},
  "channel": "hardware-firmware"   ← optional
}
```

Behavior:
- If `channel` is omitted: entry written only to the active solution's own collection (no change from today)
- If `channel` is provided and the active solution is a declared producer for that channel: entry written to the solution's own collection **and** the channel collection
- If `channel` is provided but the active solution is **not** a producer for that channel: return `400 Bad Request` with `{"error": "solution is not a producer for channel hardware-firmware"}`

### Reading from a channel (consumer)

At RAG query time, `OrgLoader.get_channel_collections(solution_name)` returns the list of channel chroma collection paths for which this solution is a consumer. These are queried in addition to the inheritance chain. Same merge/rank algorithm as Feature 1. Consumers are read-only — no writes to channel collections via consumer solutions.

---

## Feature 3: Cross-Team Task Routing

### New endpoint

```
POST /tasks/submit
```

Request body:
```json
{
  "task_type": "SWE_TASK",
  "payload": { "task": "Investigate sensor dropout" },
  "priority": 5,
  "target_solution": "medtech_firmware"   ← optional; if omitted, submits to active solution
}
```

Response (success):
```json
{ "task_id": "uuid", "target_solution": "medtech_firmware", "status": "queued" }
```

### Validation

1. Submitting solution identity is resolved in this order: (a) `source_solution` field in the request body if provided; (b) `X-SAGE-Tenant` header value **if** it matches a solution directory name in `SAGE_SOLUTIONS_DIR`; (c) the currently loaded project name. If none of these resolve to a solution with a `cross_team_routes` declaration, `target_solution` is treated as not permitted (403).
2. If `target_solution` is provided, check that `target_solution` appears in the active solution's `cross_team_routes` list
3. If not allowed: `403 Forbidden` with `{"error": "solution medtech_field_support is not permitted to route tasks to medtech_clinical"}`
4. If allowed: the task is submitted to the target solution's `TaskQueue` instance (each solution gets its own queue keyed by solution name — see queue manager changes below)

### Queue manager changes

`TaskQueue` becomes solution-scoped. A `get_task_queue(solution_name: str) -> TaskQueue` factory (analogous to the VectorMemory factory) returns a per-solution instance. The existing `_get_task_queue()` accessor in `api.py` continues to return the active solution's queue. Cross-team routing calls `get_task_queue(target_solution)` directly.

### Notification on completion

When a cross-team task (one carrying `source_solution` metadata) completes, the queue worker writes an additional audit log event to the **source solution's** audit log:

```json
{
  "event_type": "cross_team_task_completed",
  "source_solution": "medtech_field_support",
  "target_solution": "medtech_firmware",
  "task_id": "uuid",
  "result_summary": "..."
}
```

No webhooks or SSE in v1. The submitting solution polls its own audit log or uses the existing `GET /tasks/{task_id}` endpoint to check status. The task record carries `source_solution` and `target_solution` fields visible to both teams.

---

## Feature 4: Admin UI — Org Graph Page

### New page

`/org` — "Organization" added to sidebar (admin-only module, toggled via `active_modules`).

### Visual graph (React + react-flow)

- **Nodes** = solutions (circles, labeled)
- **Blue directed edges** = knowledge channels (label = channel name)
- **Orange directed edges** = task routing links (label = "routes tasks")
- **Dashed border** = root solution
- Parent-child inheritance shown as grey background grouping (parent contains children visually)

### Admin actions (all write to `org.yaml`, then call `POST /org/reload`)

- Add solution: select from loaded solutions not yet in org
- Remove solution: removes from org (does not delete solution files)
- Create knowledge channel: drag from producer node to consumer node → modal to name the channel
- Create task routing link: drag from source to target → writes to source solution's `project.yaml` `cross_team_routes`
- Delete channel or route: click edge → confirm → delete

### New API endpoints

```
GET  /org                        → returns org.yaml content as JSON (or {} if no org.yaml)
POST /org/reload                 → re-reads org.yaml and all parent chains; returns {status: "reloaded"}
POST /org/channels               → create a new channel entry in org.yaml
DELETE /org/channels/{name}      → remove a channel
POST /org/solutions              → add a solution to the org (adds parent: field to its project.yaml)
DELETE /org/solutions/{name}     → remove a solution from the org
POST /org/routes                 → add a cross_team_route; body: {"solution": str, "target": str}
DELETE /org/routes               → remove a cross_team_route; body: {"solution": str, "target": str}
```

### Concurrent edit protection

V1: last-write-wins. Concurrent admin edits may silently overwrite each other. This is an explicit non-goal for v1. A future version may add optimistic locking via an `etag` on `GET /org`.

---

## Feature 5: Onboarding Enhancement

`POST /onboarding/generate` gains two new optional fields:

```json
{
  "description": "...",
  "solution_name": "medtech_firmware",
  "parent_solution": "iot_medtech_product",
  "org_name": "iot_medtech_company"
}
```

When `parent_solution` is provided:
- Generated `project.yaml` includes `parent: iot_medtech_product`
- LLM is prompted to suggest likely `cross_team_routes` based on the solution description; suggestions are returned in the response as `suggested_routes: [...]` (string list) — they are **not** written to `project.yaml` automatically; the caller confirms and submits via `POST /org/routes`
- If `org_name` matches an existing `org.yaml`, the new solution is added to it automatically

---

## What Does Not Change

- Every solution keeps its own `.sage/audit_log.db` (compliance isolation preserved)
- Every solution keeps its own approval queue (HITL is never shared across teams)
- Solutions without `parent:` or without `org.yaml` behave exactly as today (backward compatible)
- Framework is still domain-blind — `org.yaml` is solution-layer config, never in `src/`
- The module-level `vector_memory` singleton continues to work for all non-org single-solution usage

---

## Non-Goals (explicit out of scope for v1)

- Multiple parents (mixins) — single parent chain only
- Shared approval queues across teams — HITL isolation is non-negotiable
- Per-topic knowledge filtering within a channel — channels are all-or-nothing
- Real-time cross-team knowledge sync — eventual consistency on write is acceptable
- Webhooks or SSE for cross-team task completion — polling via audit log only
- Concurrent write protection on `org.yaml` — last-write-wins, deferred to v2
- Cross-solution proposal visibility (regulatory team viewing all teams' proposals) — deferred; regulatory observer pattern is v2

---

## Testing Strategy

- **Unit:** `OrgLoader` merge logic for prompts and tasks; channel name normalization; cycle detection
- **Unit:** `VectorMemory` factory; multi-store query merge/rank
- **Integration:** cross-team task dispatch with `POST /tasks/submit`, validation against `cross_team_routes`
- **Integration:** knowledge channel write (producer) and read (consumer RAG inclusion)
- **API:** all 8 new `/org/*` endpoints; `POST /tasks/submit`; `POST /knowledge/add` with `channel` field
- **UI:** org graph renders, edge creation writes to `org.yaml`, `POST /org/reload` is called
