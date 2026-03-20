# SAGE Framework — API Reference

All endpoints are served at `http://localhost:8000`. Every response is JSON.

---

## Core

| Method | Path | Description |
|---|---|---|
| GET | `/health` | System health, provider, memory mode |
| POST | `/shutdown` | Graceful shutdown |
| GET | `/config/project` | Active solution config |
| GET | `/config/projects` | List all available solutions |
| POST | `/config/switch` | Switch active solution `{"project": "name"}` |
| GET | `/config/yaml/{file}` | Read project/prompts/tasks YAML |
| PUT | `/config/yaml/{file}` | Write and hot-reload a solution YAML |

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
| GET | `/audit` | Query audit log |
| GET | `/repo/map` | Returns markdown file tree with symbol extraction for the active solution |

---

## HITL — Human-in-the-Loop Approvals

Every AI write action generates a proposal. Nothing executes without human approval.

| Method | Path | Description |
|---|---|---|
| GET | `/proposals/pending` | List all pending proposals, sorted by risk |
| POST | `/approve/{trace_id}` | Approve a pending proposal `{"feedback": "..."}` |
| POST | `/reject/{trace_id}` | Reject with feedback `{"feedback": "reason"}` |
| POST | `/proposals/{trace_id}/undo` | Revert an approved code_diff proposal |

**Risk tiers (low → high):** `INFORMATIONAL` · `EPHEMERAL` · `STATEFUL` · `EXTERNAL` · `DESTRUCTIVE`

Low-risk proposals can be batch-approved. DESTRUCTIVE proposals never expire and require an explicit human note.

---

## Action-Aware Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Send a message — returns plain answer OR action proposal |
| POST | `/chat/execute` | Execute a confirmed chat action |
| POST | `/chat/cancel` | Log a cancelled action to the audit trail |
| GET | `/chat/history` | Retrieve chat history for a session |
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

**`POST /chat/execute` — execute confirmed action:**
```json
// Request
{"action": "approve_proposal", "params": {"trace_id": "abc123"}, "user_id": "...", "session_id": "...", "solution": "..."}

// Response
{"status": "success", "message": "Proposal abc123 approved.", "result": {"trace_id": "abc123"}}
```

**Available actions:** `approve_proposal` · `reject_proposal` · `undo_proposal` · `submit_task` · `propose_yaml_edit`

Every `/chat/execute` call writes to `compliance_audit_log` with `actor="human_via_chat"`.

---

## Knowledge Base

| Method | Path | Description |
|---|---|---|
| GET | `/knowledge/entries?limit=50` | List stored knowledge entries |
| POST | `/knowledge/add` | Add entry `{"text": "...", "metadata": {}}` |
| DELETE | `/knowledge/entry/{id}` | Delete by entry ID |
| POST | `/knowledge/import` | Bulk import `{"entries": [...]}` |
| POST | `/knowledge/search` | Semantic/keyword search `{"query": "...", "k": 5}` |
| POST | `/knowledge/sync` | Bulk sync files from a directory into the knowledge base |

**`POST /knowledge/sync` body:**
```json
{"path": "/path/to/docs", "pattern": "*.md", "solution": "starter"}
```

---

## LLM Provider

| Method | Path | Description |
|---|---|---|
| GET | `/llm/status` | Current provider, model, usage stats |
| POST | `/llm/switch` | Switch provider at runtime |
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
| GET | `/onboarding/session/{session_id}` | Get session state |

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
| POST | `/swe/task` | Submit coding task → autonomous explore/plan/implement/PR |

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
| POST | `/queue/config` | `?max_workers=4&parallel_enabled=true` |
| POST | `/task` | Submit task `{"task_type": "...", "input_data": {...}, "depends_on": []}` |
| GET | `/tasks` | List tasks with optional status filter |
| GET | `/tasks/{task_id}` | Get task details |
| GET | `/tasks/{task_id}/subtasks` | List sub-tasks spawned by a wave-scheduled task |

When a task payload includes `"subtasks": [...]`, the queue manager spawns them in parallel waves.

---

## Task Scheduler

YAML-declared scheduled tasks — defined in `tasks.yaml` under `scheduled:`, executed via the task queue.

| Method | Path | Description |
|---|---|---|
| GET | `/scheduler/status` | Active schedules, next-run times, last-run results |

**Example `tasks.yaml` scheduled block:**
```yaml
scheduled:
  - task_type: ANALYZE_LOG
    cron: "0 9 * * 1"        # every Monday 9am
    payload: {"log_source": "production"}
    description: "Weekly production log review"
```

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
| POST | `/code/plan` | Generate code plan `{"task": "..."}` → `awaiting_approval` |
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

**Supported transports:** `mock` · `serial` · `jlink` · `can` · `openocd`

---

## Compliance

| Method | Path | Description |
|---|---|---|
| GET | `/compliance/domains` | List supported compliance domains |
| GET | `/compliance/flags/{domain}` | Get all compliance flags for a domain |
| GET | `/compliance/checklist/{domain}` | Generate compliance checklist |
| POST | `/compliance/gap-assessment` | Assess gap `{"solution_name": "...", "domain": "..."}` |

**Supported domains:** `medtech` · `automotive` · `railways` · `avionics` · `iot_ics`

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
| POST | `/webhook/n8n` | Receive n8n event → route to task queue |
| POST | `/webhook/teams` | Receive Teams approval callbacks |
| POST | `/webhook/slack` | Receive Slack button click callbacks |

**n8n payload:**
```json
{
  "event_type": "log_alert",     // log_alert | code_review | monitor | any_string
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
| GET | `/temporal/workflow/status/{id}` | Get workflow status |
| GET | `/temporal/workflow/list` | List all tracked runs |

**Environment:** `TEMPORAL_HOST` (default: `localhost:7233`), `TEMPORAL_NAMESPACE`

---

## Multi-Tenant

| Method | Path | Description |
|---|---|---|
| GET | `/tenant/context` | Show resolved tenant for current request |

Add `X-SAGE-Tenant: <team_name>` header to any request to scope it to a team.

---

## Developer (GitLab)

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
| GET | `/monitor/status` | Monitor agent status |

---

## Planner / Improvements

| Method | Path | Description |
|---|---|---|
| POST | `/feedback/feature-request` | Log improvement idea |
| GET | `/feedback/feature-requests` | List improvement requests |
| POST | `/feedback/feature-requests/{id}/plan` | Generate AI plan for a request |

---

## Notes

- All write endpoints that affect shared state go through the **Proposal Store** and require `POST /approve/{trace_id}` before executing.
- Add `X-SAGE-Tenant` header to scope any request to a team/tenant.
- SSE streaming endpoints (`/analyze/stream`, `/agent/stream`) return `text/event-stream`.
- The SWE agent and HIL runner each return a `run_id` for async tracking via `/workflow/status/{run_id}`.
