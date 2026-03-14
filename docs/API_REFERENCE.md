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
| POST | `/approve/{trace_id}` | Approve a pending proposal |
| POST | `/reject/{trace_id}` | Reject with feedback |
| GET | `/audit` | Query audit log |

---

## Knowledge Base

| Method | Path | Description |
|---|---|---|
| GET | `/knowledge/entries?limit=50` | List stored knowledge entries |
| POST | `/knowledge/add` | Add entry `{"text": "...", "metadata": {}}` |
| DELETE | `/knowledge/entry/{id}` | Delete by entry ID |
| POST | `/knowledge/import` | Bulk import `{"entries": [...]}` |
| POST | `/knowledge/search` | Semantic/keyword search `{"query": "...", "k": 5}` |

---

## LLM Provider

| Method | Path | Description |
|---|---|---|
| GET | `/llm/status` | Current provider, model, usage stats |
| POST | `/llm/switch` | Switch provider at runtime |

**Supported providers (no API key):** `gemini`, `claude-code`, `ollama`, `local`, `generic-cli`

---

## Onboarding

| Method | Path | Description |
|---|---|---|
| POST | `/onboarding/generate` | Generate full solution from description |
| GET | `/onboarding/templates` | List bundled solution templates |

**Body for generate:**
```json
{
  "description": "We build surgical robots...",
  "solution_name": "surgical_robotics",
  "compliance_standards": ["ISO 13485"],
  "integrations": ["gitlab", "slack"]
}
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
