# SAGE Framework — Architecture
### *Smart Agentic-Guided Empowerment*

> Generic autonomous AI agent framework — configure once per project, run anywhere.

---

## 1. Executive Summary

SAGE is a **modular, multi-project autonomous AI agent framework** designed to deploy across any software or hardware engineering domain without code changes. The framework reads a project-specific configuration at startup and all agent behaviours, LLM prompts, task types, and UI labels adapt accordingly.

**Target customers:**

| Customer Segment | Example Domain | Primary Value |
|-----------------|---------------|---------------|
| Regulated engineering teams | Medical devices, aerospace, fintech | Compliance automation — audit trail, CAPA, change control |
| Mobile / game studios | Flutter apps, casual games | Crash triage, CI/CD review, store review analysis |
| SaaS / API teams | B2B platforms | Error triage, MR review, infra alert classification |
| ML / embedded teams | Firmware, computer vision | Log analysis, model metric monitoring, hardware debugging |
| Any engineering team | Custom domain | Configurable prompts, task types, and agent roles |

SAGE achieves project portability through a three-file project definition (`project.yaml`, `prompts.yaml`, `tasks.yaml`) loaded by the `ProjectConfig` singleton at process start. Agents, the API, the task queue dispatcher, and the web UI all read from this singleton — there are no hardcoded domain assumptions anywhere in the core framework.

---

## 2. Multi-Project Architecture

### 2.1 Solutions Directory

```
solutions/
├── starter/                 Generic template — copy this for new domains
│   ├── project.yaml         Identity, modules, standards, integrations
│   ├── prompts.yaml         Per-agent and per-role LLM system prompts
│   ├── tasks.yaml           Task types, descriptions, payload schemas
│   ├── workflows/           LangGraph StateGraph workflows (interrupt → approve)
│   ├── mcp_servers/         FastMCP server files — domain tools
│   └── evals/               Eval YAML test suites for benchmarking
├── meditation_app/          Flutter mobile + Node.js — consumer app example
├── four_in_a_line/          Casual game studio — GDPR/COPPA example
├── medtech_team/            Regulated medical device — ISO 13485/IEC 62304 example
└── <your_solution>/         Private solutions via SAGE_SOLUTIONS_DIR
```

Private/proprietary solutions live in their own separate repositories and are mounted at runtime:
```bash
SAGE_SOLUTIONS_DIR=/path/to/private-solutions make run PROJECT=my_company
```

### 2.2 ProjectConfig Singleton (`src/core/project_loader.py`)

The `ProjectConfig` class is a singleton that loads the active project at startup. The active project is determined by (in priority order):

1. `--project <name>` CLI flag passed to `src/main.py`
2. `SAGE_PROJECT=<name>` environment variable
3. Default: `starter`

Loading sequence:

```
Process Start
     │
     ▼
Read SAGE_PROJECT env var  (or --project flag)
     │
     ▼
Load config/config.yaml               ← base configuration (LLM, memory paths, integrations)
     │
     ▼
Load solutions/<name>/project.yaml    ← domain metadata, compliance standards, active modules
     │
     ▼
Load solutions/<name>/prompts.yaml    ← per-agent LLM system prompts
     │
     ▼
Load solutions/<name>/tasks.yaml      ← valid task types + payload schemas
     │
     ▼
ProjectConfig singleton available     ← all agents and the API read from this
```

Key `ProjectConfig` methods used throughout the codebase:

| Method | Returns | Consumers |
|--------|---------|-----------|
| `project_config.metadata` | Full project dict (name, domain, compliance_standards, …) | `GET /health`, `GET /config/project` |
| `project_config.get_prompts(agent)` | Agent-specific prompts dict | `AnalystAgent`, `DeveloperAgent`, `PlannerAgent`, `MonitorAgent` |
| `project_config.get_task_types()` | List of valid task type strings | `PlannerAgent`, `TaskQueue` dispatcher |
| `project_config.get_task_descriptions()` | Human-readable task descriptions | `GET /config/project` |

### 2.3 Example Solution Catalog

| Solution | Domain | Compliance Standards | Notable Roles |
|---------|--------|---------------------|--------------|
| `starter` | Generic | None (template) | analyst, developer, planner, monitor |
| `meditation_app` | Flutter mobile + Node.js | GDPR, App Store guidelines | product_advisor, qa_analyst, release_manager |
| `four_in_a_line` | Casual game | GDPR, COPPA, App Store | game_designer, monetisation_advisor, ai_opponent_specialist |
| `medtech_team` | Medical device software | ISO 13485, IEC 62304, ISO 14971, FDA 21 CFR Part 11 | embedded_developer, web_developer, devops_engineer, quality_engineer |

### 2.4 Project Selection at Runtime

```bash
# Python direct
python src/main.py api --project meditation_app

# Environment variable
SAGE_PROJECT=four_in_a_line python src/main.py api

# Makefile shorthand
make run PROJECT=medtech_team

# Docker Compose
SAGE_PROJECT=starter docker-compose up --build

# External solutions directory
SAGE_SOLUTIONS_DIR=/path/to/private make run PROJECT=my_company
```

---

## 3. LLM Providers

SAGE supports six inference backends selectable via `config/config.yaml` or the `/llm/switch` endpoint. Only one is active at a time; the `LLMGateway` singleton enforces a thread lock so only one inference call executes concurrently.

### 3.1 Provider Overview

| Provider | Key | Auth | Internet | Best for |
|----------|-----|------|----------|---------|
| Gemini CLI | `gemini` | Browser OAuth (no API key) | Yes | Cloud, latest models, default |
| Claude Code CLI | `claude-code` | `claude` login (no API key) | Yes | Claude models via existing auth |
| Ollama | `ollama` | None | No | Fully offline, any local model |
| Local Llama (GGUF) | `local` | None | No | GPU-direct, air-gapped |
| Generic CLI | `generic-cli` | Configurable | Optional | Any CLI tool with `{prompt}` |
| Claude API | `claude` | `ANTHROPIC_API_KEY` | Yes | Only option requiring an API key |

### 3.2 LLM Gateway Call Flow

```
Agent → LLMGateway.generate(prompt, system_prompt)
              │
              ▼  (threading.Lock acquired — single-lane inference)
        Provider dispatch:
          gemini     → subprocess: gemini -p "<prompt>"
          claude-code→ subprocess: claude -p "<prompt>"
          ollama     → HTTP POST localhost:11434/api/generate
          local      → llama_cpp.Llama(model_path=<GGUF>)(prompt)
          generic-cli→ subprocess: <generic_cli_path> "<prompt>"
          claude     → anthropic.Anthropic().messages.create(...)
              │  (Lock released)
              ▼
        response text returned to agent
```

### 3.3 Switching Providers

Edit `config/config.yaml`:

```yaml
llm:
  provider: "ollama"        # switch here
  ollama_model: "llama3.2"  # any model you've pulled
```

Or switch at runtime (no restart needed):
```bash
curl -X POST http://localhost:8000/llm/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "model": "llama3.2"}'
```

### 3.4 Minimum Hardware Requirements

| Mode | CPU | RAM | GPU | Notes |
|------|-----|-----|-----|-------|
| Gemini CLI (default) | 4-core | 4 GB | Not required | Recommended for most teams |
| Ollama (local) | 4-core | 8 GB | Optional | Easiest offline setup |
| Local Llama (Phi-3.5 Mini Q4) | 8-core | 8 GB | Optional (4 GB VRAM = 10x speed) | Offline / air-gapped |

---

## 4. Three-Tier Memory Architecture

SAGE uses three complementary memory systems. RAG alone is insufficient for regulated or stateful workflows.

### Tier 1 — Operational Memory (State)

- **Technology:** SQLite `task_queue` table (shared database with Tier 3)
- **Location:** `data/audit_log.db`
- **Purpose:** Tracks the state of every active task: pending → in_progress → completed/failed.
- **Key property:** Survives process restart. Pending tasks are automatically restored from SQLite on next startup.
- **Lifetime:** Per-task (row persists for audit; memory cleared on completion).

### Tier 2 — Episodic Memory (History + Learning)

- **Technology:** ChromaDB vector database (`data/chroma_db/`) with LlamaIndex and mem0 optional backends
- **Purpose:** Stores past incidents, AI analyses, and — critically — human corrections.
- **How learning works:** When an engineer rejects an AI proposal and types a correction, `AnalystAgent.learn_from_feedback()` embeds the correction and stores it in the project's ChromaDB collection. On the next similar event, `vector_store.search()` retrieves the relevant correction and injects it into the LLM prompt as context.
- **Collection naming:** Each project uses its own collection (e.g. `meditation_app_knowledge`) to prevent cross-domain contamination. Multi-tenant mode prefixes: `<tenant>_knowledge`.
- **Fallback:** In-memory embedding fallback when ChromaDB is not installed (minimal mode).
- **Lifetime:** Permanent (accumulates across all runs).

### Tier 3 — Audit Memory (Compliance Trail)

- **Technology:** Append-only SQLite (`data/audit_log.db`, table `compliance_audit_log`)
- **Schema:** `(id, timestamp, actor, action_type, input_context, output_content, metadata)`
- **Purpose:** Every LLM call, approval, rejection, webhook receipt, and feature request is recorded immutably.
- **Key property:** No UPDATE or DELETE on audit rows. New events are INSERT-only.
- **Retention:** 7+ years for regulated industries (ISO 13485 / FDA 21 CFR Part 11). Configurable for other domains.
- **Lifetime:** Permanent.

---

## 5. Agent Architecture

All agents share the `LLMGateway` singleton and the `AuditLogger` singleton. Project-specific behaviour comes entirely from the prompts and task types loaded by `ProjectConfig`.

### 5.1 AnalystAgent (`src/agents/analyst.py`)

```
Input (log entry / metric / error text)
         │
         ▼
vector_store.search(input)   ← ChromaDB RAG: retrieve past corrections
         │
         ▼
project_config.get_prompts("analyst")   ← domain-specific system prompt
         │
         ▼
llm_gateway.generate(user_prompt, system_prompt)
         │
         ▼
Parse JSON response: { severity, root_cause_hypothesis, recommended_action, ... }
         │
         ▼
audit_logger.log_event(actor="AnalystAgent", …)
         │
         ▼
Return proposal + trace_id  →  Human review gate
```

When the human **rejects** and provides a correction:

```
analyst.learn_from_feedback(log_entry, human_comment, original_analysis)
         │
         ▼
vector_store.add_document(text=human_comment, metadata={log_entry, …})
         │
         ▼
Next similar event → RAG retrieves correction → better AI output
```

### 5.2 DeveloperAgent (`src/agents/developer.py`)

Implements the ReAct loop (see Section 6) for multi-step MR review. Key capabilities:

- `review_merge_request(project_id, mr_iid)` — ReAct loop over pipeline status + diff
- `create_mr_from_issue(project_id, issue_iid)` — AI-drafted MR title/description
- `list_open_mrs(project_id)` — GitLab/GitHub REST query
- `get_pipeline_status(project_id, mr_iid)` — CI/CD stage-by-stage status
- `propose_code_patch(file_path, error_description, current_code)` — unified diff proposal

All operations produce proposals only. No code is pushed or merged without explicit human approval.

### 5.3 PlannerAgent (`src/agents/planner.py`)

Implements Plan-and-Execute (see Section 7). The planner:

1. Receives a natural-language request.
2. Calls `llm_gateway` with a domain-aware planning prompt (loaded from `project_config`).
3. The LLM returns a JSON array of steps, each with `task_type` validated against the project's `task_types` list.
4. Steps are submitted to `TaskQueue` in order.
5. `TaskWorker` executes them sequentially.

### 5.4 MonitorAgent (`src/agents/monitor.py`)

Polls configured event sources on a schedule. Sources are declared in `project.yaml` under `integrations:`. Each polled event is classified by the LLM using the monitor system prompt from `prompts.yaml`. If `requires_action: true`, the event is submitted to `TaskQueue` as the suggested task type.

### 5.5 UniversalAgent (`src/agents/universal.py`)

Generic agent whose role, persona, and tools are defined entirely by `prompts.yaml` roles. No hardcoded domain logic. Powers the `/agent/roles` and `/agent/run` endpoints.

When a role is invoked:
1. Load role definition from `project_config.get_prompts("roles")[role_key]`
2. Inject task input and RAG context into the system prompt
3. Call `llm_gateway.generate()`
4. Return structured JSON response

### 5.6 Nano-Modules (`src/modules/`)

Zero-dependency utility library used across all agents and the API.

| Module | Purpose |
|--------|---------|
| `severity.py` | Severity level enum and comparison utilities (RED/AMBER/GREEN/UNKNOWN) |
| `json_extractor.py` | Robust JSON extraction from LLM output (handles markdown fences, partial JSON) |
| `trace_id.py` | UUID-based trace ID generation and validation |
| `payload_validator.py` | Task payload validation against `tasks.yaml` schemas |
| `event_bus.py` | Lightweight in-process publish/subscribe for agent-to-agent event routing |

---

## 6. ReAct Loop (Reason + Act)

The `DeveloperAgent._react_loop()` implements the ReAct pattern for multi-step agentic reasoning. The agent iterates Thought → Action → Observation until it produces a `FinalAnswer`.

```
Task Description (e.g. "Review MR !47 in project 12")
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  Step 1                                             │
│  Thought: I should check pipeline status first.     │
│  Action:  get_pipeline_status({"project_id": 12,    │
│                                "mr_iid": 47})        │◄── Tool call
│  Observation: {"status": "failed", "stages": {...}} │
└─────────────────────────┬───────────────────────────┘
                          │  (repeat, max 5 steps)
                          ▼
┌─────────────────────────────────────────────────────┐
│  Step 2                                             │
│  Thought: Pipeline failed. I should inspect diff.   │
│  Action:  get_diff({})                              │◄── Tool call
│  Observation: {"diff": "--- a/src/...\n+++ ..."}    │
└─────────────────────────┬───────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│  Step 3                                             │
│  Thought: I have pipeline result and diff. Done.    │
│  FinalAnswer: {                                     │◄── JSON Output
│    "summary": "...",                                │
│    "issues": [...],                                 │
│    "approved": false                                │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

The agent enforces a maximum of 5 steps. All steps accumulate in a history string so the LLM has full context at every step.

---

## 7. Plan-and-Execute (PlannerAgent)

```
User Request: "Investigate the crash on checkout flow and create a fix MR"
           │
           ▼
  PlannerAgent.plan_and_execute(request)
  ┌───────────────────────────────────────────────────────┐
  │  LLM generates plan using project task types:         │
  │                                                       │
  │  Step 1: ANALYZE_CRASH                                │
  │    payload: { log_text: "…", platform: "iOS" }        │
  │                                                       │
  │  Step 2: REVIEW_BACKEND_CODE                          │
  │    payload: { diff_text: "…" }                        │
  │                                                       │
  │  Step 3: CREATE_MR                                    │
  │    payload: { issue_description: "Fix checkout" }     │
  └────────────────────────┬──────────────────────────────┘
                           │
                           ▼
  task_queue.submit(step_1) → step_2 → step_3
  Each step logged to audit trail with trace_id
  Human reviews each proposal before action executes
```

The PlannerAgent validates all generated task types against `project_config.get_task_types()`. Any step with an invalid task type is rejected before entering the queue.

---

## 8. Human-in-the-Loop

Human review is a **mandatory gate** on every AI proposal. No AI action executes without explicit human approval. This is architecturally enforced — agents return proposals, never execute changes directly.

```
Event Detected (log, metric, MR, webhook, …)
          │
          ▼
  Agent Analyzes  ←──── RAG context (past corrections)
          │
          ▼
  AI Proposal Generated
  { severity, root_cause_hypothesis, recommended_action, trace_id }
          │
          ▼
  ┌───────┴────────────────────────────────┐
  │          HUMAN REVIEW GATE             │
  │  Via: Web UI / Slack Block Kit /       │
  │       REST API POST /approve or        │
  │       POST /reject                     │
  └───────┬────────────────┬───────────────┘
          │                │
     [Approve]          [Reject + Feedback]
          │                │
          ▼                ▼
  Action executed    Correction text embedded
  Audit logged       into ChromaDB (RAG)
                          │
                          ▼
                   Next similar event →
                   AI uses this correction
```

The `trace_id` is a UUID attached to every proposal and all associated audit log entries. It is the immutable link between an AI output, its human decision, and any downstream action.

---

## 9. Integration Modules (`src/integrations/`)

All integrations degrade gracefully — if a dependency is missing or a service is unreachable, SAGE continues running without it.

| Module | Phase | Purpose |
|--------|-------|---------|
| `mcp_registry.py` | 1.5 | MCP tool discovery + invocation for solution-defined tools |
| `langchain_tools.py` | 1 | LangChain tool loader per solution `integrations:` list |
| `long_term_memory.py` | 1 | mem0 multi-session memory (vector store fallback) |
| `langgraph_runner.py` | 3 | LangGraph orchestration (interrupt → approve → resume) |
| `autogen_runner.py` | 4 | AutoGen code planning + Docker sandboxed execution |
| `slack_approver.py` | 8 | Slack Block Kit proposals + `/webhook/slack` callbacks |
| `temporal_runner.py` | 11 | Temporal durable workflows (LangGraph fallback) |

### 9.1 LangGraph Orchestration

Workflows are defined as Python `StateGraph` files in `solutions/<name>/workflows/`. They use `interrupt_before` to pause for human approval.

```
POST /workflow/run    {"workflow_name": "my_workflow", "state": {"task": "..."}}
→ Returns {"status": "awaiting_approval", "run_id": "..."}

POST /workflow/resume {"run_id": "...", "feedback": {"approved": true}}
→ Resumes from the interrupted node
```

### 9.2 AutoGen Code Agent

`autogen_runner.py` coordinates a `UserProxyAgent` + `AssistantAgent` pair. Code execution runs in a Docker sandbox (no host-side code execution). Triggered via `POST /autogen/run`.

### 9.3 Slack Two-Way Approval

When `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are configured, proposals are sent to Slack as interactive Block Kit messages. Engineers click Approve/Reject directly in Slack; the callback hits `POST /webhook/slack`.

### 9.4 n8n Webhook Receiver

n8n can forward events from any external service (Teams, Metabase, Spira, GitHub Actions, PagerDuty, etc.) to `POST /webhook/n8n`. Authentication via `N8N_WEBHOOK_SECRET` header. This removes the need for SAGE to hold credentials for those services.

### 9.5 Temporal Durable Workflows

`temporal_runner.py` wraps LangGraph workflows in Temporal activities, providing durable execution with automatic retries and state persistence across process restarts. Requires `TEMPORAL_HOST` env var. Falls back to direct LangGraph if Temporal is unavailable.

---

## 10. Onboarding Wizard (`src/core/onboarding.py`)

Generates all three solution YAML files from a plain-language description using the active LLM:

```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "We build a SaaS invoicing platform in React and Node.js.",
    "solution_name": "invoicing_saas",
    "compliance_standards": ["SOC 2 Type II", "GDPR"],
    "integrations": ["github", "slack"]
  }'
```

Returns generated YAML content and writes files to `solutions/invoicing_saas/`. Then:
```bash
POST /config/switch {"project": "invoicing_saas"}
```

---

## 11. Eval and Benchmarking (`src/core/eval_runner.py`)

Measures agent quality with deterministic keyword scoring. Eval suites live in `solutions/<name>/evals/*.yaml`.

```yaml
name: "Analyst quality — crash logs"
cases:
  - id: "null_ptr_001"
    role: "analyst"
    input: "NullPointerException at Service:42"
    expected_keywords: ["null", "pointer", "root cause"]
    max_response_length: 2000
```

```bash
POST /eval/run     {"suite": "analyst_quality"}
GET  /eval/history {"suite": "analyst_quality"}
```

Results are stored in SQLite alongside the audit log for trend tracking.

---

## 12. Multi-Tenant Isolation (`src/core/tenant.py`)

All endpoints accept `X-SAGE-Tenant: <team_name>` header. This scopes:
- Vector store collection: `<tenant>_knowledge`
- Audit log metadata: `tenant_id` field
- Task queue submissions: tagged with tenant

Default (no header): active solution name is used as tenant. The tenant context is stored in a `ContextVar` so concurrent requests are fully isolated.

---

## 13. Web UI Architecture

The web frontend is a React 18 application served by Vite, connecting to the FastAPI backend through a development proxy.

```
Browser (http://localhost:5173)
         │
    ┌────┴──────────────────────────────────┐
    │  Vite Dev Server                      │
    │  /api/* → proxy → http://localhost:8000│
    └────┬──────────────────────────────────┘
         │
    ┌────┴──────────────────────────────────┐
    │  React 18 + TypeScript                │
    │  TanStack Query (30s polling)         │
    │                                       │
    │  Pages:                               │
    │   /            Dashboard              │
    │   /analyst     Log Analyzer           │
    │   /developer   Code Reviewer          │
    │   /monitor     Pipeline Monitor       │
    │   /audit       Audit Log              │
    │   /agents      Universal Agent Roles  │
    │   /llm         LLM Provider Switcher  │
    │   /improvements Feature Requests      │
    │   /settings    Solution Settings      │
    │   /yaml-editor Live YAML Editor       │
    └────┬──────────────────────────────────┘
         │  fetch /api/*
         ▼
    FastAPI :8000
    CORS: allow_origins=["*"]
         │
    Agent Core + SQLite + ChromaDB
```

### 13.1 ModuleWrapper Self-Improvement System

Every page is wrapped by `ModuleWrapper`. This component:

- Displays a module name badge and version number.
- Provides an "i" toggle that reveals current features and improvement hints.
- Renders a "Request Improvement" button that opens the `FeatureRequestPanel`.

Feature requests are stored in `data/audit_log.db`. A reviewer can trigger the PlannerAgent to auto-generate an implementation plan via `POST /feedback/feature-requests/{id}/plan`.

The `MODULE_REGISTRY` in `web/src/registry/modules.ts` defines each module's metadata and must match the `active_modules` keys in each solution's `project.yaml`.

### 13.2 The Two Backlogs (Improvements Page)

The Improvements page has two distinct tabs, enforcing a hard boundary:

| Tab | Scope | Owned by | Workflow |
|-----|-------|---------|---------|
| Solution Backlog | `solution` | The builder's team | Log → AI plan → approve → implement in solution |
| SAGE Framework Ideas | `sage` | SAGE community | Log → GitHub Issue → community PR |

Never mix the two. Every `FeatureRequest` has a `scope` field enforced in code and UI.

### 13.3 Frontend Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18 | Component rendering |
| TypeScript | 5 | Type safety |
| Vite | 5 | Build tool and dev proxy |
| TanStack Query | 5 | Server state management, 30s auto-polling |
| Recharts | 2 | Error trend charts on Dashboard |
| Lucide React | Latest | Icon set |
| Tailwind CSS | 3 | Utility-first styling |
| React Router | 6 | Client-side routing |

---

## 14. Complete Directory Tree

```
SAGE/
├── config/
│   └── config.yaml                  Base config: LLM provider, memory paths, integration URLs
├── data/
│   ├── models/                      GGUF model files (local LLM only)
│   ├── chroma_db/                   ChromaDB vector store (episodic memory)
│   └── audit_log.db                 SQLite: audit trail + task queue + feature requests + eval history
├── docs/
│   ├── SETUP.md                     Detailed installation guide
│   ├── MCP_SERVERS.md               MCP server reference
│   ├── INTEGRATIONS.md              External system integration guide
│   ├── USER_GUIDE.md                End-user operational guide
│   ├── ADDING_A_PROJECT.md          Developer guide for adding a new solution
│   └── FRAMEWORK_INTEGRATION_STRATEGY.md  Phase-by-phase integration roadmap
├── scripts/
│   └── setup_gemini_mcp.py          Configures ~/.gemini/settings.json for MCP
├── solutions/
│   ├── starter/                     Generic template
│   │   ├── project.yaml
│   │   ├── prompts.yaml
│   │   ├── tasks.yaml
│   │   ├── workflows/               LangGraph StateGraph workflow definitions
│   │   ├── mcp_servers/             FastMCP servers — domain-specific tools
│   │   └── evals/                   Eval YAML test suites
│   ├── meditation_app/              Flutter + Node.js example
│   ├── four_in_a_line/              Casual game example
│   └── medtech_team/                Regulated medical device example
├── src/
│   ├── agents/
│   │   ├── analyst.py               Log/metric analysis + RAG feedback loop
│   │   ├── developer.py             GitLab/GitHub MR operations + ReAct loop
│   │   ├── monitor.py               Event polling and classification
│   │   ├── planner.py               Plan-and-Execute orchestration
│   │   └── universal.py             YAML-driven role execution (no hardcoded domain)
│   ├── core/
│   │   ├── llm_gateway.py           Singleton LLM with thread lock (6 providers)
│   │   ├── project_loader.py        ProjectConfig singleton
│   │   ├── queue_manager.py         SQLite-backed task queue + worker thread
│   │   ├── onboarding.py            LLM-powered solution generator
│   │   ├── eval_runner.py           Eval suite runner — keyword scoring, SQLite history
│   │   └── tenant.py                Multi-tenant context (X-SAGE-Tenant, ContextVar)
│   ├── interface/
│   │   └── api.py                   FastAPI application (all endpoints)
│   ├── integrations/
│   │   ├── mcp_registry.py          MCP tool discovery + invocation
│   │   ├── langchain_tools.py       LangChain tool loader per solution
│   │   ├── long_term_memory.py      mem0 multi-session memory
│   │   ├── langgraph_runner.py      LangGraph orchestration (interrupt → approve)
│   │   ├── autogen_runner.py        AutoGen code planning + Docker sandbox
│   │   ├── slack_approver.py        Slack Block Kit proposals + webhook callbacks
│   │   └── temporal_runner.py       Temporal durable workflows
│   ├── memory/
│   │   ├── audit_logger.py          Append-only SQLite audit trail
│   │   └── vector_store.py          ChromaDB wrapper + knowledge CRUD
│   ├── modules/                     Nano-modules: zero-dependency utility library
│   │   ├── severity.py
│   │   ├── json_extractor.py
│   │   ├── trace_id.py
│   │   ├── payload_validator.py
│   │   └── event_bus.py
│   └── main.py                      Entry point: api / cli / monitor / demo modes
├── tests/                           Framework unit tests (383+ passing)
│   ├── conftest.py
│   ├── modules/                     Nano-module tests (119 tests)
│   ├── test_api.py
│   ├── test_llm_gateway.py
│   ├── test_audit_logger.py
│   ├── test_vector_store.py
│   ├── test_analyst_agent.py
│   ├── test_developer_agent.py
│   ├── test_monitor_agent.py
│   ├── test_queue_manager.py
│   ├── test_phase2_n8n.py
│   ├── test_phase3_langgraph.py
│   ├── test_phase4_autogen.py
│   ├── test_phase5_streaming.py
│   ├── test_phase6_onboarding.py
│   └── test_phase7_11_features.py
├── web/
│   ├── src/
│   │   ├── api/client.ts            All fetch calls — typed
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   ├── analyst/
│   │   │   ├── developer/
│   │   │   ├── audit/
│   │   │   ├── monitor/
│   │   │   ├── agents/
│   │   │   └── shared/              ModuleWrapper, FeatureRequestPanel
│   │   ├── pages/                   One file per route
│   │   ├── hooks/
│   │   ├── registry/
│   │   │   ├── modules.ts           MODULE_REGISTRY — module metadata
│   │   │   └── projects.ts          Per-solution module configs
│   │   └── types/
│   ├── vite.config.ts               Vite config (API proxy to :8000)
│   ├── tailwind.config.ts
│   └── package.json
├── .env                             Live credentials (never committed)
├── .env.example                     Credentials template
├── .mcp.json                        Claude Code MCP server config (auto-detected)
├── GETTING_STARTED.md               Zero-integration newcomer path (start here)
├── ARCHITECTURE.md                  This file
├── README.md
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── pytest.ini
├── requirements.txt
└── requirements-minimal.txt         Minimal deps for low-RAM machines
```

---

## 15. REST API Endpoint Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service status, LLM provider, active project, integration flags |
| `GET` | `/config/project` | Active project metadata, task types, compliance standards |
| `GET` | `/config/projects` | List all available solutions (`SAGE_SOLUTIONS_DIR`) |
| `POST` | `/config/switch` | Switch active solution (`{"project": "meditation_app"}`) |
| `GET` | `/config/yaml/{file}` | Read raw YAML for project/prompts/tasks |
| `PUT` | `/config/yaml/{file}` | Write updated YAML and hot-reload |
| `POST` | `/analyze` | Analyze a log/metric/error → AI proposal with `trace_id` |
| `POST` | `/analyze/stream` | Same as `/analyze` with SSE streaming response |
| `POST` | `/approve/{trace_id}` | Approve a pending proposal |
| `POST` | `/reject/{trace_id}` | Reject with human feedback (triggers learning) |
| `GET` | `/audit` | Query audit log (`?limit=50&offset=0`) |
| `GET` | `/agent/roles` | List available agent roles from solution `prompts.yaml` |
| `POST` | `/agent/run` | Run a solution-defined agent role against a task |
| `POST` | `/agent/stream` | Same as `/agent/run` with SSE streaming response |
| `GET` | `/llm/status` | Current LLM provider, model, session usage |
| `POST` | `/llm/switch` | Switch LLM provider at runtime |
| `POST` | `/mr/create` | Create GitLab MR from issue |
| `POST` | `/mr/review` | AI MR review via ReAct loop |
| `GET` | `/mr/open` | List open MRs |
| `GET` | `/mr/pipeline` | CI/CD pipeline status |
| `GET` | `/monitor/status` | Monitor Agent polling status |
| `GET` | `/knowledge/` | List knowledge base entries |
| `POST` | `/knowledge/` | Add a document to the knowledge base |
| `DELETE` | `/knowledge/{id}` | Remove a knowledge base entry |
| `POST` | `/knowledge/import` | Bulk import documents |
| `POST` | `/onboarding/generate` | Generate solution YAML from plain-language description |
| `POST` | `/eval/run` | Run an eval suite |
| `GET` | `/eval/history` | Eval run history for a suite |
| `POST` | `/workflow/run` | Start a LangGraph workflow |
| `POST` | `/workflow/resume` | Resume a paused workflow after approval |
| `POST` | `/autogen/run` | Run AutoGen code planning agent |
| `POST` | `/webhook/n8n` | Receive n8n forwarded events |
| `POST` | `/webhook/slack` | Receive Slack Block Kit approval callbacks |
| `POST` | `/webhook/teams` | Receive Teams adaptive card approval callbacks |
| `GET` | `/feedback/feature-requests` | List feature requests |
| `POST` | `/feedback/feature-request` | Submit a UI improvement request |
| `POST` | `/feedback/feature-requests/{id}/plan` | Auto-generate implementation plan |
| `PATCH` | `/feedback/feature-requests/{id}` | Update request status |
| `POST` | `/shutdown` | Stop backend and frontend processes |

Interactive Swagger docs: `http://localhost:8000/docs`

---

## 16. MCP Servers

SAGE exposes domain tools as MCP (Model Context Protocol) servers. These are available to both the Gemini CLI (via `~/.gemini/settings.json`) and Claude Code (via `.mcp.json`).

MCP servers live in `solutions/<name>/mcp_servers/` and are registered via `mcp_registry.py`.

Example servers (medtech_team solution):

| Server | Hardware/Service | Key Tools |
|--------|-----------------|-----------|
| `sage-serial` | COM port / UART | `list_ports`, `send_command`, `read_output` |
| `sage-jlink` | SEGGER J-Link JTAG/SWD | `flash_firmware`, `read_memory`, `read_rtt` |
| `sage-metabase` | Metabase analytics | `query_errors`, `list_dashboards` |
| `sage-spira` | SpiraTeam | `create_incident`, `list_incidents`, `get_test_runs` |
| `sage-teams` | Microsoft Teams | `read_messages`, `send_alert` |
| `gitlab` | GitLab (npm) | `list_mrs`, `review_mr`, `create_issue` |

Configure for Gemini CLI: `python scripts/setup_gemini_mcp.py`

---

## 17. The SAGE Lean Loop

Every task processed by SAGE follows this five-phase cycle. Phase 5 feeds back into Phase 2 — this is the compounding intelligence loop.

```
1. SURFACE       → Agent detects or receives signal (log, webhook, trigger, poll)
2. CONTEXTUALIZE → Vector memory searched; prior decisions and corrections retrieved
3. PROPOSE       → LLM generates action proposal with trace_id
4. DECIDE        → Human reviews and approves or rejects with feedback
5. COMPOUND      → Feedback ingested into vector store; audit log updated
```

Never short-circuit any phase. Phase 5 is not optional — every rejection is a learning event.

---

## 18. Build Orchestrator

The Build Orchestrator is an end-to-end product construction pipeline that transforms a plain-language product description into a working codebase with tests, CI/CD, and documentation. It includes domain-aware build detection (13 domains), an adaptive agent router (Q-learning), 32 task types, 19 agent roles in 5 workforce teams, and anti-drift checkpoints.

### 18.1 Components

| Component | Location | Purpose |
|---|---|---|
| `BuildOrchestrator` | `src/core/build_orchestrator.py` | Pipeline coordinator — domain detection, decompose, schedule, integrate |
| `CriticAgent` | `src/agents/critic.py` | Actor-critic reviewer — scores plan, code, and integration quality |
| `OpenSWERunner` | `src/integrations/openswe_runner.py` | Autonomous coding agent — repo exploration, implementation, test execution |
| `AdaptiveRouter` | `src/core/build_orchestrator.py` | Q-learning router — learns best agent per task type from success/quality scores |
| `DOMAIN_RULES` | `src/core/build_orchestrator.py` | 13 domain rule sets — keywords, required tasks, compliance, HITL overrides |
| `WORKFORCE_REGISTRY` | `src/core/build_orchestrator.py` | 19 agents in 5 functional teams — Engineering, Analysis, Design, Compliance, Operations |

### 18.2 Domain-Aware Build Detection

The orchestrator automatically classifies the product description against 13 industry domains using keyword matching in `DOMAIN_RULES`. Each domain rule specifies:

- **Keywords** — terms that trigger domain detection (e.g., "medical", "clinical", "FDA" → `medical_device`)
- **Required task types** — injected into the build plan (e.g., `SAFETY`, `COMPLIANCE`)
- **Compliance standards** — propagated to the solution YAML
- **HITL overrides** — regulated domains can force `strict` regardless of the requested level
- **Extra acceptance criteria** — domain-specific checks for the Critic Agent

**Supported domains:** `medical_device` · `automotive` · `avionics` · `robotics` · `iot` · `fintech` · `hardware_generic` · `ml_ai` · `saas_product` · `consumer_app` · `enterprise` · `ecommerce` · `healthcare_software` · `edtech`

### 18.3 Workforce Registry and 32 Task Types

**19 agent roles** are organised into **5 workforce teams**:

| Team | Lead | Members |
|---|---|---|
| Engineering | developer | qa_engineer, system_tester, devops_engineer, localization_engineer |
| Analysis | analyst | business_analyst, financial_analyst, data_scientist |
| Design | ux_designer | product_manager |
| Compliance | regulatory_specialist | legal_advisor, safety_engineer |
| Operations | operations_manager | technical_writer, marketing_strategist |

**32 task types** across four categories:
- **Software (9):** BACKEND, FRONTEND, TESTS, INFRA, DOCS, DATABASE, API, CONFIG, AGENTIC
- **Hardware/Embedded/Mechanical (7):** FIRMWARE, HARDWARE_SIM, PCB_DESIGN, MECHANICAL, SAFETY, COMPLIANCE, EMBEDDED_TEST
- **Cross-cutting (3):** SECURITY, DATA, ML_MODEL
- **Business/Operational (13):** QA, SYSTEM_TEST, REGULATORY, BUSINESS_ANALYSIS, MARKET_RESEARCH, FINANCIAL, UX_DESIGN, DEVOPS, PRODUCT_MGMT, LEGAL, OPERATIONS, TRAINING, LOCALIZATION

### 18.4 Adaptive Router (Q-Learning)

The `AdaptiveRouter` uses Q-learning inspired scoring to learn the best agent for each task type:

```
Task submitted → Router checks observation count for task type
     │
     ├─ < 3 observations → use static WORKFORCE_REGISTRY default
     │
     └─ ≥ 3 observations → select agent with highest EMA score
                            (learning rate: 0.3)
```

After each agent execution, the router updates its score table:
```
new_score = (1 - α) × old_score + α × observed_quality
```

Where `α = 0.3` (learning rate). Over successive builds, the router shifts work toward higher-performing agents. Stats are exposed via `GET /build/router/stats`.

### 18.5 Anti-Drift Checkpoints

After each wave of agent execution, the orchestrator verifies that outputs align with the original task intent:

1. Compare each component's output against the decomposed plan.
2. If drift is detected, log a `BUILD_DRIFT_WARNING` audit event.
3. In `strict` mode, pause for human review.
4. The Critic Agent assesses drift severity and may trigger agent revision.

### 18.6 Data Flow

```
Product Description (plain text)
         │
         ▼
┌─────────────────────────────────┐
│  DOMAIN DETECTION               │
│  DOMAIN_RULES keyword match     │
│  → inject required tasks,       │
│    compliance, HITL overrides   │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  DECOMPOSE                      │
│  LLM breaks product into        │
│  components, 32 task types,     │
│  agent assignments from         │
│  WORKFORCE_REGISTRY             │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  ADAPTIVE ROUTER                │
│  Q-learning selects best agent  │
│  per task type (≥3 observations)│
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  CRITIC — PLAN REVIEW           │
│  CriticAgent scores plan        │
│  on completeness, feasibility   │
│  Score < threshold → revise     │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  HITL GATE (standard/strict)    │
│  Human reviews decomposed plan  │
│  Approve / Reject with feedback │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  SCAFFOLD                       │
│  Create directory structure,    │
│  configs, CI/CD, package files  │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  EXECUTE AGENTS (wave-parallel) │
│  Each component → ReAct agent   │
│  Independent components in      │
│  parallel waves                 │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  ANTI-DRIFT CHECKPOINT          │
│  Verify outputs match plan      │
│  Log BUILD_DRIFT_WARNING if not │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  CRITIC — CODE REVIEW           │
│  Per-component (strict mode)    │
│  or aggregate (standard mode)   │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  INTEGRATE                      │
│  Cross-component wiring:        │
│  shared types, API contracts,   │
│  routing, environment config    │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  CRITIC — INTEGRATION REVIEW    │
│  End-to-end consistency check   │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  HITL GATE (all levels)         │
│  Human reviews final build      │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  FINALIZE                       │
│  Tests, documentation,          │
│  deployment config, agentic     │
│  patterns (monitor, analyst,    │
│  scheduled tasks)               │
└─────────────────────────────────┘
```

### 18.7 3-Tier Code Generation Degradation

The orchestrator tries three strategies in order for each component:

| Tier | Strategy | When used |
|---|---|---|
| 1 | **OpenSWERunner** | Full autonomous agent — repo exploration, multi-file implementation, test execution. Used when `open-swe` integration is available. |
| 2 | **LLM direct generation** | Sends component spec to the active LLM with structured output parsing. Fallback when OpenSWE is unavailable. |
| 3 | **Template scaffolding** | Language-specific project templates with placeholder implementations. Fallback when LLM generation fails or times out. |

Each tier produces a buildable output. The Critic Agent evaluates the result regardless of which tier generated it.

### 18.8 Wave-Based Parallel Execution

Components are grouped into waves based on their dependency graph. Independent components execute concurrently via the `ParallelTaskRunner`. Components with explicit dependencies (e.g., an API client depending on a backend schema) wait for their dependency wave to complete.

```
Wave 1: [backend_api, frontend_ui, docs]          ← concurrent
Wave 2: [api_client (depends on backend_api)]      ← sequential after wave 1
Wave 3: [integration_tests (depends on all)]       ← sequential after wave 2
```

---

## 19. Roadmap

### Phases 0–4 — Core Framework (Complete)


| Phase | Feature | Key files |
|-------|---------|-----------|
| 0 | Langfuse observability | `llm_gateway.py` |
| 1 | LlamaIndex + LangChain + mem0 | `vector_store.py`, `langchain_tools.py`, `long_term_memory.py` |
| 1.5 | MCP tool registry | `mcp_registry.py`, `solutions/*/mcp_servers/` |
| 2 | n8n webhook receiver | `api.py /webhook/n8n` |
| 3 | LangGraph orchestration | `langgraph_runner.py` |
| 4 | AutoGen code agent + Docker sandbox | `autogen_runner.py` |

### Phases 5–11 — Platform Features (Complete)

| Phase | Feature | Key files |
|-------|---------|-----------|
| 5 | SSE streaming (`/analyze/stream`, `/agent/stream`) | `api.py` |
| 6 | Onboarding wizard | `onboarding.py`, `POST /onboarding/generate` |
| 7 | Knowledge base CRUD | `vector_store.py`, `GET/POST/DELETE /knowledge/` |
| 8 | Slack two-way approval | `slack_approver.py`, `POST /webhook/slack` |
| 9 | Eval/benchmarking | `eval_runner.py`, `solutions/*/evals/*.yaml` |
| 10 | Multi-tenant isolation | `tenant.py`, `X-SAGE-Tenant` header |
| 11 | Temporal durable workflows | `temporal_runner.py` |

### Intelligence Layer v1 (Complete)

| Feature | Key files | Description |
|---------|-----------|-------------|
| **HITL ProposalStore** | `src/core/proposal_store.py`, `src/core/proposal_executor.py` | All write operations converted to proposals; `RiskClass` enum (INFORMATIONAL→DESTRUCTIVE); approve/reject triggers `ProposalExecutor` dispatch |
| **SAGEIntelligence SLM** | `src/core/sage_intelligence.py` | Gemma 3 1B via Ollama classifies task tier (LIGHT/STANDARD/HEAVY), lints YAML, converts intent to API calls, answers framework Q&A |
| **Teacher-Student LLM** | `src/integrations/dual_llm_runner.py` | Dual LLM strategies: `teacher_only`, `student_first`, `parallel_compare`, `student_only`; distillation logs to `data/distillation/` |
| **Conversational Onboarding** | `src/core/onboarding.py`, `src/core/onboarding_analyzer.py` | Two-path wizard: Path A analyzes existing repo (local or GitHub URL), Path B fresh Q&A; SQLite-persisted sessions; generates all 3 YAML files |
| **Parallel Wave Scheduler** | `src/core/queue_manager.py` `ParallelTaskRunner` | Groups independent tasks into waves; `ThreadPoolExecutor` concurrent dispatch; compliance solutions fall back to sequential; runtime config via `POST /queue/config` |
| **open-swe SWE Workflow** | `solutions/starter/workflows/swe_workflow.py` | LangGraph 6-node pipeline: explore→plan→implement→verify→propose_pr→[HITL gate]→finalize; auto-detects stack; opens real GitHub PR; `POST /swe/task` |
| **Visual Workflows** | `src/interface/api.py GET /workflows`, `web/src/pages/Workflows.tsx` | Auto-generates Mermaid diagrams from LangGraph `draw_mermaid()`; regex fallback parser; rendered in dashboard with mermaid.js |

### Paperclip Dashboard (Complete)

Full Paperclip-style founder command center. One human + AI agent team, everything visible from one screen.

| Page | Route | Description |
|------|-------|-------------|
| **Approvals** | `/approvals` | HITL inbox — risk-sorted proposals, batch approve, auto-poll, sidebar count badge |
| **Issues** | `/issues` | Feature backlog with priority, status filters, slide-over detail |
| **Activity** | `/activity` | Real-time audit log timeline — color-coded by event type, auto-refresh 5s |
| **Goals** | `/goals` | OKR tracker — objectives + key results, progress bars, localStorage persistence |
| **Org Chart** | `/org` | Agent team hierarchy — Founder → 6 roles, live status dots, task counts |
| **Workflows** | `/workflows` | Mermaid diagram viewer — one card per workflow, full-screen modal, copy button |

**UI changes:** CompanyRail (far-left solution switcher), sharp zero-radius zinc aesthetic, Cmd+K command palette (all 16 routes), sidebar grouped WORK/AGENTS/INTELLIGENCE/SETTINGS.

### Phase 12 — Build Orchestrator (Complete)

| Phase | Feature | Key files |
|-------|---------|-----------|
| 12 | Build Orchestrator (0→1→N pipeline) | `build_orchestrator.py`, `critic.py`, `openswe_runner.py` |
| 12.1 | Domain-aware build detection (13 domains) | `build_orchestrator.py` (`DOMAIN_RULES`) |
| 12.2 | 32 task types, 19 agent roles, 5 workforce teams | `build_orchestrator.py` (`WORKFORCE_REGISTRY`) |
| 12.3 | Adaptive router (Q-learning) | `build_orchestrator.py` (`AdaptiveRouter`) |
| 12.4 | Anti-drift checkpoints | `build_orchestrator.py` (wave-level drift verification) |

### Next — Platform Expansion

- **Marketplace** — community-contributed solution YAML bundles
- **SaaS delivery** — hosted SAGE with solution selection at sign-up
- **Compliance report generation** — per-solution audit export in regulatory formats (ISO 13485, FDA 21 CFR Part 11)
