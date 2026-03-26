# SAGE Framework — API Reference

All endpoints are served at `http://localhost:8000`. Every response is JSON.

**Total endpoints: 155** across 25 categories.

---

## Core & Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System health, provider, memory mode, configured integrations |
| GET | `/health/llm` | LLM-specific health: provider reachability, last call time |
| POST | `/shutdown` | Graceful shutdown |
| GET | `/config/project` | Active solution config (metadata, active_modules, theme) |
| GET | `/config/projects` | List all available solutions with metadata and themes |
| POST | `/config/switch` | Switch active solution `{"project": "name"}` |
| POST | `/config/modules` | Enable/disable UI modules `{"modules": ["dashboard", ...]}` |
| GET | `/config/yaml/{file_name}` | Read project/prompts/tasks YAML |
| PUT | `/config/yaml/{file_name}` | Write and hot-reload a solution YAML |
| GET | `/config/skill` | Get current solution skill level |
| POST | `/config/skill` | Set solution skill level |
| GET | `/config/approval-roles` | Get RBAC approval role mappings |
| GET | `/config/dev-users` | List developer user identifiers |
| PATCH | `/config/project/theme` | Update active solution's theme block |

---

## Analysis & Agents

| Method | Path | Description |
|---|---|---|
| POST | `/analyze` | Analyze a log entry (blocking) |
| POST | `/analyze/stream` | Analyze with SSE token streaming |
| POST | `/agent/run` | Run a named agent role (blocking) |
| POST | `/agent/stream` | Run agent with SSE token streaming |
| GET | `/agent/roles` | List available roles for active solution |
| GET | `/agents/status` | Live status of all agents (active/idle, last task, daily counts) |
| GET | `/agents/active` | List currently running agents with task info |
| POST | `/agents/hire` | Propose a new agent role (HITL) |
| POST | `/agents/analyze-jd` | Analyze a job description to extract role definition |
| GET | `/agents/{role_key}/performance` | Performance metrics for a specific agent role |
| GET | `/repo/map` | Returns markdown file tree with symbol extraction for active solution |

---

## HITL — Human-in-the-Loop Approvals

Every AI write action generates a proposal. Nothing executes without human approval.

| Method | Path | Description |
|---|---|---|
| GET | `/proposals/pending` | List all pending proposals, sorted by risk |
| GET | `/proposals/{trace_id}` | Get a specific proposal by trace_id |
| POST | `/proposals/approve-batch` | Batch-approve multiple proposals `{"trace_ids": [...]}` |
| POST | `/approve/{trace_id}` | Approve a pending proposal `{"feedback": "..."}` |
| POST | `/reject/{trace_id}` | Reject with feedback `{"feedback": "reason"}` |
| POST | `/proposals/{trace_id}/undo` | Revert an approved code_diff proposal |

**Risk tiers (low to high):** `INFORMATIONAL` / `EPHEMERAL` / `STATEFUL` / `EXTERNAL` / `DESTRUCTIVE`

Low-risk proposals can be batch-approved. DESTRUCTIVE proposals never expire and require an explicit human note.

---

## Action-Aware Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Send a message — returns plain answer OR action proposal |
| POST | `/chat/execute` | Execute a confirmed chat action |
| POST | `/chat/cancel` | Log a cancelled action to the audit trail |
| DELETE | `/chat/history` | Clear display history (compliance_audit_log is never touched) |

**`POST /chat` — response shape:**
```json
{
  "response_type": "answer",
  "reply": "...",
  "session_id": "...",
  "message_id": "..."
}
```
or (when LLM routes to an action):
```json
{
  "response_type": "action",
  "action": "approve_proposal",
  "params": {"trace_id": "abc123"},
  "confirmation_prompt": "I'll approve the YAML edit for analyst.py — proceed?",
  "session_id": "...",
  "message_id": "..."
}
```

**Available actions:** `approve_proposal` / `reject_proposal` / `undo_proposal` / `submit_task` / `propose_yaml_edit`

Every `/chat/execute` call writes to `compliance_audit_log` with `actor="human_via_chat"`.

---

## Knowledge Base

| Method | Path | Description |
|---|---|---|
| GET | `/knowledge/entries?limit=50` | List stored knowledge entries |
| POST | `/knowledge/add` | Add entry `{"text": "...", "metadata": {}}` |
| DELETE | `/knowledge/entry/{entry_id}` | Delete by entry ID |
| POST | `/knowledge/import` | Bulk import `{"entries": [...]}` |
| POST | `/knowledge/search` | Semantic/keyword search `{"query": "...", "k": 5}` |
| POST | `/knowledge/sync` | Bulk sync files from a directory into the knowledge base |

**`POST /knowledge/sync` body:**
```json
{"path": "/path/to/docs", "pattern": "*.md", "solution": "starter"}
```

---

## Audit Log

| Method | Path | Description |
|---|---|---|
| GET | `/audit` | Query audit log with pagination (limit, offset, action_type filter) |

---

## LLM Provider

| Method | Path | Description |
|---|---|---|
| GET | `/llm/status` | Current provider, model, usage stats, PII config, data residency |
| POST | `/llm/switch` | Switch provider at runtime `{"provider": "ollama", "model": "llama3.2"}` |
| GET | `/llm/dual-status` | Teacher + student LLM status and confidence thresholds |

**Supported providers (no API key):** `gemini`, `claude-code`, `ollama`, `local`, `generic-cli`

---

## SAGE Intelligence (SLM)

On-device small language model for meta-operations — zero cloud calls for framework questions.

| Method | Path | Description |
|---|---|---|
| GET | `/sage/status` | SLM availability, model, capabilities |
| GET | `/sage/ask?question=...` | Ask the SLM a framework question |
| POST | `/sage/intent` | Convert plain-language intent to API call `{"text": "..."}` |
| POST | `/sage/lint-yaml` | Lint a YAML string `{"yaml_content": "..."}` |

---

## Teacher-Student Distillation

| Method | Path | Description |
|---|---|---|
| GET | `/distillation/{solution}/stats` | Score drift, confidence metrics, sample count |
| GET | `/distillation/{solution}/comparisons` | Recent teacher vs student comparison pairs |

---

## Onboarding

| Method | Path | Description |
|---|---|---|
| POST | `/onboarding/generate` | Generate full solution from description (single-turn) |
| GET | `/onboarding/templates` | List bundled solution templates |
| GET | `/onboarding/org-templates` | Domain org structure templates (6 domains) |
| POST | `/onboarding/session` | Start conversational onboarding session |
| POST | `/onboarding/session/{session_id}/message` | Continue session `{"message": "..."}` |
| POST | `/onboarding/session/{session_id}/generate` | Generate solution YAML from session state |
| GET | `/onboarding/session/{session_id}` | Get session state |
| POST | `/onboarding/scan-folder` | Scan an existing project folder and generate YAML |
| POST | `/onboarding/refine` | Refine generated YAML based on feedback |
| POST | `/onboarding/save-solution` | Save generated solution to disk |

**Single-turn generate body:**
```json
{
  "description": "We build surgical robots...",
  "solution_name": "surgical_robotics",
  "compliance_standards": ["ISO 13485"],
  "integrations": ["gitlab", "slack"]
}
```

**Two-path session start:**
```bash
# Path A — analyze existing local repo
curl -X POST http://localhost:8000/onboarding/session \
  -d '{"path": "A", "existing_path": "/path/to/my/project"}'

# Path B — fresh Q&A wizard
curl -X POST http://localhost:8000/onboarding/session \
  -d '{"path": "B"}'
```

---

## SWE Agent (open-swe pattern)

| Method | Path | Description |
|---|---|---|
| POST | `/swe/task` | Submit coding task — autonomous explore/plan/implement/PR |

**Body:**
```json
{"task": "Fix null pointer in CheckoutService", "repo_path": "/path/to/repo"}
```

**Returns:** `{"run_id": "...", "status": "awaiting_approval", "result": {"pr_url": "..."}}`

Approve via `POST /workflow/resume {"run_id": "...", "feedback": {"approved": true}}`

---

## Visual Workflows

| Method | Path | Description |
|---|---|---|
| GET | `/workflows` | List all LangGraph workflows across all solutions |
| GET | `/workflows/{solution}/{workflow_name}` | Get workflow + Mermaid diagram |

Mermaid diagrams are auto-generated from `StateGraph.draw_mermaid()` — always accurate.

---

## Task Queue

| Method | Path | Description |
|---|---|---|
| GET | `/queue/status` | Queue depth, running tasks, worker count |
| GET | `/queue/tasks` | List tasks with optional status filter |
| POST | `/queue/config` | `?max_workers=4&parallel_enabled=true` |
| POST | `/tasks/submit` | Submit task `{"task_type": "...", "payload": {...}, "priority": 5}` |
| GET | `/tasks/{task_id}/subtasks` | List sub-tasks spawned by a wave-scheduled task |

When a task payload includes `"subtasks": [...]`, the queue manager spawns them in parallel waves.

---

## Task Scheduler

YAML-declared scheduled tasks — defined in `tasks.yaml` under `scheduled:`, executed via the task queue.

| Method | Path | Description |
|---|---|---|
| GET | `/scheduler/status` | Active schedules, next-run times, last-run results |

---

## LangGraph Workflows

| Method | Path | Description |
|---|---|---|
| GET | `/workflow/list` | List available workflows |
| POST | `/workflow/run` | Start workflow `{"workflow_name": "...", "state": {}}` |
| POST | `/workflow/resume` | Resume after approval `{"run_id": "...", "feedback": {}}` |
| GET | `/workflow/status/{run_id}` | Get run status |

---

## Code Agent (AutoGen)

| Method | Path | Description |
|---|---|---|
| POST | `/code/plan` | Generate code plan `{"task": "..."}` — `awaiting_approval` |
| POST | `/code/approve` | Approve plan `{"run_id": "...", "comment": ""}` |
| POST | `/code/execute` | Execute approved plan in Docker sandbox |
| GET | `/code/status/{run_id}` | Get run status |

---

## MCP Tools

| Method | Path | Description |
|---|---|---|
| GET | `/mcp/tools` | List registered MCP tools |
| POST | `/mcp/invoke` | Invoke tool `{"tool_name": "...", "args": {}}` |

---

## HIL — Hardware-in-the-Loop Testing

| Method | Path | Description |
|---|---|---|
| GET | `/hil/status` | HIL runner status, active transport |
| POST | `/hil/connect` | Connect to hardware `{"transport": "serial", "port": "/dev/ttyUSB0"}` |
| POST | `/hil/run-suite` | Run test suite `{"suite_name": "...", "firmware_path": "..."}` |
| GET | `/hil/report/{session_id}` | Get regulatory evidence report for session |

**Supported transports:** `mock` / `serial` / `jlink` / `can` / `openocd`

---

## Compliance

| Method | Path | Description |
|---|---|---|
| GET | `/compliance/domains` | List supported compliance domains |
| GET | `/compliance/flags/{domain}` | Get all compliance flags for a domain |
| GET | `/compliance/checklist/{domain}` | Generate compliance checklist |
| POST | `/compliance/gap-assessment` | Assess gap `{"solution_name": "...", "domain": "..."}` |

**Supported domains:** `medtech` / `automotive` / `railways` / `avionics` / `iot_ics`

---

## Eval & Benchmarking

| Method | Path | Description |
|---|---|---|
| GET | `/eval/suites` | List eval suites for active solution |
| POST | `/eval/run` | Run suite `{"suite": "name"}` (omit for all) |
| GET | `/eval/history?suite=name&limit=20` | Historical results |

---

## Webhooks (Inbound)

| Method | Path | Description |
|---|---|---|
| POST | `/webhook/n8n` | Receive n8n event — route to task queue |
| POST | `/webhook/teams` | Receive Teams approval callbacks |
| POST | `/webhook/slack` | Receive Slack button click callbacks |

**n8n payload:**
```json
{
  "event_type": "log_alert",
  "payload": {"log_entry": "..."},
  "source": "pagerduty"
}
```
Set `N8N_WEBHOOK_SECRET` for HMAC validation (`X-SAGE-Signature` header).

---

## Slack

| Method | Path | Description |
|---|---|---|
| POST | `/slack/send-proposal` | Send proposal to Slack channel with Approve/Reject buttons |

**Environment:**
- `SLACK_BOT_TOKEN` — xoxb-... bot token
- `SLACK_CHANNEL` — channel ID (default: `#sage-approvals`)
- `SLACK_SIGNING_SECRET` — for webhook signature verification

---

## Temporal Workflows

| Method | Path | Description |
|---|---|---|
| POST | `/temporal/workflow/start` | Start durable workflow (LangGraph fallback) |
| GET | `/temporal/workflow/status/{workflow_id}` | Get workflow status |
| GET | `/temporal/workflow/list` | List all tracked runs |

**Environment:** `TEMPORAL_HOST` (default: `localhost:7233`), `TEMPORAL_NAMESPACE`

---

## Build Orchestrator

End-to-end product build pipeline — from plain-language description to working codebase. Includes domain-aware build detection, adaptive agent routing, and anti-drift checkpoints.

| Method | Path | Description |
|---|---|---|
| POST | `/build/start` | Start a new build run |
| GET | `/build/status/{run_id}` | Get build run status, phase, and progress |
| POST | `/build/approve/{run_id}` | Approve or reject a plan or build at a HITL gate |
| GET | `/build/runs` | List all build runs |
| GET | `/build/roles` | List workforce registry roles and agent teams |

**`POST /build/start` body:**
```json
{
  "product_description": "A SaaS invoicing platform with Stripe integration",
  "solution_name": "invoicing_saas",
  "repo_url": "https://github.com/org/invoicing",
  "workspace_dir": "/tmp/builds/invoicing",
  "critic_threshold": 0.7,
  "hitl_level": "standard"
}
```

| Parameter | Required | Default | Description |
|---|---|---|---|
| `product_description` | Yes | — | Plain-language description of what to build |
| `solution_name` | Yes | — | Solution name for YAML generation |
| `repo_url` | No | — | Git repo to clone or work in |
| `workspace_dir` | No | auto | Local directory for build artifacts |
| `critic_threshold` | No | `0.7` | Minimum critic score to pass review (0.0-1.0) |
| `hitl_level` | No | `"standard"` | `"minimal"` / `"standard"` / `"strict"` |

**HITL levels:**

| Level | Gates | Use case |
|---|---|---|
| `minimal` | Final build approval only | Trusted domains, rapid iteration |
| `standard` | Plan review + final build | Default — balanced oversight |
| `strict` | Plan review + per-component code review + final build | Regulated industries |

**Supported domains (13+):** `medical_device` / `automotive` / `avionics` / `robotics` / `iot` / `fintech` / `hardware_generic` / `ml_ai` / `saas_product` / `consumer_app` / `enterprise` / `ecommerce` / `healthcare_software` / `edtech`

---

## Developer (GitLab/GitHub)

| Method | Path | Description |
|---|---|---|
| POST | `/mr/create` | Create MR from issue |
| POST | `/mr/review` | AI review of merge request |
| GET | `/mr/open` | List open MRs |
| GET | `/mr/pipeline` | Pipeline status |

---

## Monitor

| Method | Path | Description |
|---|---|---|
| GET | `/monitor/status` | Monitor agent status and polling threads |

---

## Planner / Improvements

| Method | Path | Description |
|---|---|---|
| POST | `/feedback/feature-request` | Log improvement idea |
| GET | `/feedback/feature-requests` | List improvement requests |
| POST | `/feedback/feature-requests/{req_id}/plan` | Generate AI plan for a request |
| PATCH | `/feedback/feature-requests/{req_id}` | Update request status (approve/reject/archive) |

---

## Organization (Org Graph)

| Method | Path | Description |
|---|---|---|
| GET | `/org` | Get org configuration (solutions, channels, routes) |
| PUT | `/org` | Update full org configuration |
| POST | `/org/reload` | Reload org config from disk |
| POST | `/org/channels` | Create a knowledge channel |
| DELETE | `/org/channels/{name}` | Delete a knowledge channel |
| POST | `/org/solutions` | Register a solution in the org |
| DELETE | `/org/solutions/{name}` | Remove a solution from the org |
| POST | `/org/routes` | Add a task routing rule |
| DELETE | `/org/routes` | Remove a task routing rule |

---

## Composio Integration

| Method | Path | Description |
|---|---|---|
| GET | `/integrations/composio/status` | Composio connection status |
| POST | `/integrations/composio/connect` | Connect to Composio `{"api_key": "..."}` |
| GET | `/integrations/composio/tools` | List available Composio tools |

---

## Authentication & Access Control

| Method | Path | Description |
|---|---|---|
| GET | `/auth/me` | Current authenticated user info |
| POST | `/auth/api-keys` | Create an API key |
| GET | `/auth/api-keys` | List API keys |
| DELETE | `/auth/api-keys/{key_id}` | Revoke an API key |
| GET | `/auth/roles` | List RBAC roles |
| POST | `/auth/roles` | Create/update RBAC role |

---

## Cost Tracking

| Method | Path | Description |
|---|---|---|
| GET | `/costs/summary` | Token usage and cost summary |
| GET | `/costs/daily` | Daily cost breakdown |
| POST | `/costs/budget` | Set budget limits per solution |

---

## Multi-Tenant

| Method | Path | Description |
|---|---|---|
| GET | `/tenant/context` | Show resolved tenant for current request |

Add `X-SAGE-Tenant: <team_name>` header to any request to scope it to a team.

---

## Sandbox

| Method | Path | Description |
|---|---|---|
| GET | `/sandbox/status` | OpenShell sandbox availability and config |

---

## SSE Streaming

| Method | Path | Description |
|---|---|---|
| GET | `/logs/stream` | Real-time server-sent events for backend log output |

---

## Agent Gym — Self-Play Skill Training

MuZero-inspired training engine with Glicko-2 ratings, spaced repetition, and adaptive exercise selection. Agents improve through practice loops: play → grade → critique → reflect → compound.

| Method | Path | Description |
|---|---|---|
| POST | `/gym/train` | Start a single training session for one agent role |
| POST | `/gym/train/batch` | Parallel training across multiple roles |
| GET | `/gym/session/{session_id}` | Get training session details (memory + SQLite fallback) |
| GET | `/gym/ratings` | Leaderboard — all agent roles ranked by Glicko-2 rating |
| GET | `/gym/ratings/{role}` | Ratings breakdown for a specific agent role |
| GET | `/gym/history` | Recent training sessions (default limit: 50) |
| GET | `/gym/analytics` | Comprehensive analytics: score trends, weakness map, improvement rate |
| GET | `/gym/curriculum/{role}` | Curriculum status — current difficulty, progress, spaced repetition queue |

**`POST /gym/train` body:**
```json
{
  "role": "firmware_engineer",
  "difficulty": "intermediate",
  "enable_peer_review": false
}
```

**`POST /gym/train/batch` body:**
```json
{
  "roles": ["firmware_engineer", "developer", "data_scientist"],
  "difficulty": "intermediate",
  "sessions_per_role": 3
}
```

**`GET /gym/analytics` query params:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `role` | No | — | Filter analytics to a specific role |
| `skill` | No | — | Filter to a specific skill name |

**Glicko-2 rating fields:** `rating` (skill estimate), `rating_deviation` (confidence — lower = more certain), `volatility` (consistency of performance), `confidence_interval` (95% CI bounds).

---

## Exercise Catalog

Scalable exercise catalog: ~160 seed exercises across 8 domains, expandable to 10,000+ via LLM variant generation along domain-specific axes.

| Method | Path | Description |
|---|---|---|
| GET | `/gym/catalog` | Catalog stats — total exercises, per-domain counts, variant axes |
| GET | `/gym/catalog/{domain}` | List exercises for a domain, optionally filtered by difficulty |
| POST | `/gym/catalog/generate` | Generate LLM-powered exercise variants from seed exercises |

**`GET /gym/catalog/{domain}` query params:**

| Parameter | Required | Default | Description |
|---|---|---|---|
| `difficulty` | No | — | Filter by difficulty level: `beginner`, `intermediate`, `advanced`, `expert` |

**`POST /gym/catalog/generate` body:**
```json
{
  "domain": "openfw",
  "count": 100,
  "difficulty": "intermediate"
}
```

**Supported domains:** `openfw`, `openswe`, `openml`, `openeda`, `opensim`, `opendoc`, `opendesign`, `openstrategy`

---

## Skills Marketplace

Modular YAML-based skill registry with visibility tiers (public/private/disabled) and hot-reload.

| Method | Path | Description |
|---|---|---|
| GET | `/skills` | List all loaded skills with stats |
| GET | `/skills/{name}` | Get a specific skill by name |
| GET | `/skills/role/{role}` | Skills available to an agent role |
| GET | `/skills/runner/{runner}` | Skills for a runner family |
| GET | `/skills/search` | Search skills by keyword (`?q=embedded`) |
| POST | `/skills/visibility` | Change skill visibility tier (framework control — immediate) |
| POST | `/skills/reload` | Hot-reload all skills from disk |

---

## Notes

- All write endpoints that affect shared state go through the **Proposal Store** and require `POST /approve/{trace_id}` before executing.
- Add `X-SAGE-Tenant` header to scope any request to a team/tenant.
- SSE streaming endpoints (`/analyze/stream`, `/agent/stream`, `/logs/stream`) return `text/event-stream`.
- The SWE agent and HIL runner each return a `run_id` for async tracking via `/workflow/status/{run_id}`.
