# SAGE Framework — Architecture
### *Smart Agentic-Guided Empowerment*

> Generic autonomous AI agent framework — configure once per project, run anywhere.

---

## 1. Executive Summary

SAGE is a **modular, multi-project autonomous AI agent framework** designed to deploy across any software or hardware engineering domain without code changes. The framework reads a project-specific configuration at startup and all agent behaviours, LLM prompts, task types, and UI labels adapt accordingly.

**Target customers:**

| Customer Segment | Example Project | Primary Value |
|------------------|----------------|---------------|
| Medtech startups | Medical Device Manufacturing | ISO 13485 / IEC 62304 compliance automation |
| CV/ML companies | PoseEngine (human pose estimation) | ML log triage, model metric monitoring |
| Tracking software vendors | Kappture (human tracking analytics) | GDPR Art. 9/35-aware pipeline monitoring |
| Mobile app teams | Flutter mobile companions | Crash log analysis, CI/CD review |
| Any engineering team | Custom project | Configurable prompts and task types |

SAGE achieves project portability through a three-file project definition (`project.yaml`, `prompts.yaml`, `tasks.yaml`) loaded by the `ProjectConfig` singleton at process start. Agents, the API, the task queue dispatcher, and the web UI all read from this singleton — there are no hardcoded domain assumptions anywhere in the core framework.

---

## 2. Multi-Project Architecture

### 2.1 Solutions Directory

```
SystemAutonomousAgent/
└── solutions/
    ├── medtech/
    │   ├── project.yaml    # name, domain, compliance_standards, active_modules, integrations
    │   ├── prompts.yaml    # analyst, developer, planner, monitor system prompts
    │   ├── tasks.yaml      # task_types list, task_descriptions dict, task_payloads dict
    │   ├── mcp_servers/    # 5 MCP servers (GitLab, Teams, Metabase, Spira, J-Link)
    │   ├── tests/          # e2e, validation (IQ/OQ/PQ), mcp, integration
    │   └── docs/           # regulatory docs (ISO 13485, SRS, RISK_MANAGEMENT, etc.)
    ├── poseengine/
    │   ├── project.yaml
    │   ├── prompts.yaml
    │   ├── tasks.yaml
    │   ├── source/         # actual PoseEngine Flutter/ML source code
    │   └── tests/
    └── kappture/
        ├── project.yaml
        ├── prompts.yaml
        ├── tasks.yaml
        └── tests/
```

The solutions directory location is configurable via the `SAGE_SOLUTIONS_DIR` environment variable (default: `solutions`). This allows solutions to live outside the framework root.

### 2.2 ProjectConfig Singleton (`src/core/project_loader.py`)

The `ProjectConfig` class is a singleton that loads the active project at startup. The active project is determined by (in priority order):

1. `--project <name>` CLI flag passed to `src/main.py`
2. `SAGE_PROJECT=<name>` environment variable
3. Default: `medtech`

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

### 2.3 Project Catalog

| Project ID | Name | Domain | Compliance Standards | Task Types |
|-----------|------|--------|---------------------|------------|
| `medtech` | Medical Device Manufacturing | `medtech` | ISO 13485:2016, ISO 14971:2019, IEC 62304:2006+AMD1, FDA 21 CFR Part 11 | ANALYZE_LOG, REVIEW_MR, CREATE_MR, FLASH_FIRMWARE, MONITOR_CHECK, PLAN_TASK |
| `poseengine` | PoseEngine & Flutter | `ml-mobile` | IEEE 730, Google Flutter Style Guide, PEP 8, GDPR (no biometric storage) | ANALYZE_TRAINING_LOG, ANALYZE_INFERENCE_LOG, ANALYZE_CRASH_LOG, ANALYZE_CI_LOG, REVIEW_ML_CODE, REVIEW_FLUTTER_CODE, CREATE_MR, MONITOR_PIPELINE, MONITOR_MODEL_METRICS, PLAN_TASK |
| `kappture` | Kappture Human Tracking | `cv-tracking` | GDPR Art. 9 (biometric data), GDPR Art. 35 (DPIA), IEEE 730, ISO/IEC 25010 | ANALYZE_TRACKING_LOG, ANALYZE_CAMERA_ERROR, ANALYZE_ACCURACY_REPORT, ANALYZE_CI_LOG, REVIEW_TRACKING_CODE, CREATE_MR, MONITOR_PIPELINE, MONITOR_ACCURACY, PLAN_TASK |

### 2.4 Project Selection at Runtime

```bash
# Python direct
python src/main.py api --project kappture

# Environment variable
SAGE_PROJECT=poseengine python src/main.py api

# Makefile shorthand
make run PROJECT=kappture

# Docker Compose
SAGE_PROJECT=kappture docker-compose up --build
```

---

## 3. LLM Providers

SAGE supports two inference backends selectable via `config/config.yaml`. Only one is active at a time; the `LLMGateway` singleton enforces a thread lock so only one inference call executes concurrently.

### 3.1 Gemini CLI (Default — Cloud)

```
Agent → LLMGateway.generate(prompt, system_prompt)
              │
              ▼  (thread lock acquired)
        GeminiCLIProvider
              │
              ▼
        subprocess: gemini -p "<combined prompt>"
              │
              ▼  stdout captured, cached lines filtered
        response text returned
              │  (thread lock released)
              ▼
        Agent processes response
```

- No API key required. Authentication is handled by the locally installed Gemini CLI via browser OAuth (Google account).
- Model: `gemini-2.5-flash` (configurable in `config.yaml`).
- Timeout: 120 seconds (configurable).
- Requires internet access and `gemini` on system PATH (`npm install -g @google/gemini-cli`).

### 3.2 Local Llama (Offline / Air-Gapped)

```
Agent → LLMGateway.generate(prompt, system_prompt)
              │
              ▼  (thread lock acquired)
        LocalLlamaProvider
              │
              ▼
        llama_cpp.Llama(model_path=<GGUF file>)
        n_gpu_layers=-1  (all layers to GPU if available; CPU fallback)
              │
              ▼
        Phi-3 / Llama-3 chat template applied
        model(full_prompt, max_tokens=512)
              │  (thread lock released)
              ▼
        Agent processes response
```

- Recommended model: Phi-3.5 Mini 3.8B Q4 GGUF — fits in 4 GB VRAM.
- Alternative: Qwen 2.5 Coder 1.5B for code-heavy projects.
- Zero network dependency. Suitable for air-gapped or GDPR-restricted environments.
- Install: `pip install llama-cpp-python` (with or without CUDA build flags).

### 3.3 Provider Comparison

| Aspect | Gemini CLI | Local Llama |
|--------|-----------|-------------|
| Internet required | Yes | No |
| API keys | None (browser OAuth) | None |
| Reasoning quality | Full Gemini Pro/Flash | Depends on model size |
| GPU required | No | No (CPU fallback) |
| Latency | ~2–5 s | ~5–30 s (CPU) / ~1–3 s (GPU) |
| Air-gap suitable | No | Yes |
| Best for | Cloud-connected teams | Regulated/offline environments |

### 3.4 Switching Providers

Edit `config/config.yaml`:

```yaml
llm:
  provider: "gemini"    # default
  # provider: "local"   # for offline mode
```

Or override at runtime:

```bash
LLM_PROVIDER=local python src/main.py api --project medtech
```

### 3.5 Minimum Hardware Requirements

| Mode | CPU | RAM | GPU | Disk |
|------|-----|-----|-----|------|
| Gemini CLI (default) | 4-core | 4 GB | None required | ~500 MB |
| Local Llama (Phi-3.5 Mini Q4) | 8-core | 8 GB | Optional (4 GB VRAM speeds up ~10x) | ~3 GB for model |
| Full stack + Docker | 4-core | 4 GB | None required | ~1 GB |

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

- **Technology:** ChromaDB vector database (`data/chroma_db/`)
- **Purpose:** Stores past incidents, AI analyses, and — critically — human corrections.
- **How learning works:** When an engineer rejects an AI proposal and types a correction, `AnalystAgent.learn_from_feedback()` embeds the correction and stores it in the project's ChromaDB collection. On the next similar event, `vector_store.search()` retrieves the relevant correction and injects it into the LLM prompt as context.
- **Collection naming:** Each project uses its own collection (e.g. `kappture_knowledge`, `poseengine_knowledge`) to prevent cross-domain contamination.
- **Fallback:** In-memory embedding fallback is available when ChromaDB is not installed (minimal mode).
- **Lifetime:** Permanent (accumulates across all runs).

### Tier 3 — Audit Memory (Compliance Trail)

- **Technology:** Append-only SQLite (`data/audit_log.db`, table `compliance_audit_log`)
- **Schema:** `(id, timestamp, actor, action_type, input_context, output_content, metadata)`
- **Purpose:** Every LLM call, approval, rejection, webhook receipt, and feature request is recorded immutably.
- **Key property:** No UPDATE or DELETE on audit rows. New events are INSERT-only.
- **Retention:** 7+ years as required by ISO 13485 / FDA 21 CFR Part 11. For other projects, retention is configurable.
- **Lifetime:** Permanent.

---

## 5. Agent Architecture

All four agents share the `LLMGateway` singleton and the `AuditLogger` singleton. Project-specific behaviour comes entirely from the prompts and task types loaded by `ProjectConfig`.

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
Parse JSON response: { severity, root_cause_hypothesis, recommended_action }
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
- `list_open_mrs(project_id)` — GitLab REST query
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

Polls configured event sources on a schedule. Sources active per project (loaded from solution `project.yaml`):

| Project | Sources |
|---------|---------|
| medtech | Teams, Metabase, GitLab |
| poseengine | GitLab CI/CD, GitHub Actions, Firebase Crashlytics, W&B |
| kappture | RTSP streams, Prometheus/Grafana, GitLab CI/CD, GitHub Actions |

Each polled event is classified by the LLM using the monitor system prompt from `prompts.yaml`. If `requires_action: true`, the event is submitted to `TaskQueue` as the suggested task type.

### 5.5 Nano-Modules (`src/modules/`)

Zero-dependency utility library used across all agents and the API. All modules are independently testable with no external imports.

| Module | Purpose |
|--------|---------|
| `severity.py` | Severity level enum and comparison utilities (RED/AMBER/GREEN/UNKNOWN) |
| `json_extractor.py` | Robust JSON extraction from LLM output (handles markdown fences, partial JSON) |
| `trace_id.py` | UUID-based trace ID generation and validation |
| `payload_validator.py` | Task payload validation against `tasks.yaml` schemas |
| `event_bus.py` | Lightweight in-process publish/subscribe for agent-to-agent event routing |

Nano-module tests live in `tests/modules/` (119 tests, run in under 3 seconds).

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
│  Thought: I have pipeline result and diff. I can    │
│           now produce a complete review.            │
│  FinalAnswer: {                                     │◄── JSON Output
│    "summary": "...",                                │
│    "issues": [...],                                 │
│    "suggestions": [...],                            │
│    "approved": false                                │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

**Available tools during MR review:**

| Tool | Description |
|------|-------------|
| `get_pipeline_status` | CI/CD status for the MR, including per-stage job results |
| `get_diff` | Unified diff of all code changes (truncated to 6000 chars) |
| `get_mr_info` | MR title, author, source/target branches, description |

The agent enforces a maximum of 5 steps. If reached, the LLM is forced to produce a `FinalAnswer` immediately. All steps are accumulated in a history string so the LLM has full context at every step.

---

## 7. Plan-and-Execute (PlannerAgent)

The `PlannerAgent` handles complex multi-step user requests by decomposing them into a sequence of atomic tasks that are dispatched to the `TaskQueue`.

```
User Request: "Investigate the accuracy drop on camera-03 and create a fix MR"
           │
           ▼
  PlannerAgent.plan_and_execute(request)
  ┌───────────────────────────────────────────────────────┐
  │  LLM generates plan using project task types:         │
  │                                                       │
  │  Step 1: ANALYZE_CAMERA_ERROR                         │
  │    payload: { camera_id: "camera-03",                 │
  │               log_text: "…" }                         │
  │                                                       │
  │  Step 2: ANALYZE_ACCURACY_REPORT                      │
  │    payload: { report_text: "…",                       │
  │               baseline_mota: 0.75 }                   │
  │                                                       │
  │  Step 3: CREATE_MR                                    │
  │    payload: { issue_description: "Fix camera-03" }    │
  └────────────────────────┬──────────────────────────────┘
                           │
                           ▼
  task_queue.submit(step_1)  →  task_queue.submit(step_2)  →  task_queue.submit(step_3)
                           │
                           ▼
  TaskWorker processes steps sequentially (single-lane)
  Each step logged to audit trail with trace_id
                           │
                           ▼
  Human reviews each proposal before action executes
```

The PlannerAgent validates all generated task types against `project_config.get_task_types()`. Any step with an invalid task type is rejected before entering the queue.

---

## 8. Human-in-the-Loop

Human review is a **mandatory gate** on every AI proposal. No AI action executes without explicit human approval. This is architecturally enforced — agents return proposals, never execute changes directly.

```
Event Detected (log, metric, MR, camera error, …)
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
  │  Via: Web UI button / Teams card /     │
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

## 9. Web UI Architecture

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
    │   /improvements Feature Requests      │
    └────┬──────────────────────────────────┘
         │  fetch /api/*
         ▼
    FastAPI :8000
    CORS: allow_origins=["*"]
         │
    Agent Core + SQLite + ChromaDB
```

### 9.1 ModuleWrapper Self-Improvement System

Every page in the web UI is wrapped by `ModuleWrapper`. This component:

- Displays a module name badge and version number in the top-left corner of each page.
- Provides an "i" toggle that reveals the module's current features and improvement ideas.
- Renders a "Request Improvement" button (when `ImprovementMode = 'open'`).
- On button click, opens the `FeatureRequestPanel` slide-in drawer, pre-populated with the module's improvement hints.

Feature requests are stored in the `feature_requests` table in `data/audit_log.db`. From the Improvements page, a reviewer can trigger the PlannerAgent to auto-generate an implementation plan for any pending request via `POST /feedback/feature-requests/{id}/plan`.

The `MODULE_REGISTRY` in `web/src/registry/modules.ts` defines each module's `id`, `name`, `version`, `features[]`, and `improvementHints[]`. This registry is read by `ModuleWrapper` and must match the `active_modules` keys in each project's `project.yaml`.

### 9.2 Frontend Libraries

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

## 10. Complete Directory Tree

```
SystemAutonomousAgent/
├── config/
│   └── config.yaml                  Base config: LLM provider, memory paths, integration URLs
├── data/
│   ├── models/                      GGUF model files (local LLM only)
│   ├── chroma_db/                   ChromaDB vector store (episodic memory)
│   └── audit_log.db                 SQLite: audit trail + task queue + feature requests
├── docs/
│   ├── SETUP.md                     Detailed installation guide
│   ├── MCP_SERVERS.md               MCP server reference
│   ├── INTEGRATIONS.md              External system integration guide
│   ├── USER_GUIDE.md                End-user operational guide
│   ├── ADDING_A_PROJECT.md          Developer guide for adding a new solution
│   └── TESTING.md                   Test strategy and reference
├── scripts/
│   └── setup_gemini_mcp.py          Configures ~/.gemini/settings.json
├── solutions/
│   ├── medtech/
│   │   ├── project.yaml             Identity, compliance standards, active modules
│   │   ├── prompts.yaml             Per-agent LLM system prompts
│   │   ├── tasks.yaml               Task types, descriptions, payload schemas
│   │   ├── mcp_servers/             5 MCP servers (serial, jlink, metabase, spira, teams)
│   │   ├── tests/                   32 tests: e2e, IQ/OQ/PQ validation, mcp, integration
│   │   └── docs/                    Regulatory docs (SRS, RISK_MANAGEMENT, SOUP, VV_PLAN, …)
│   ├── poseengine/
│   │   ├── project.yaml
│   │   ├── prompts.yaml
│   │   ├── tasks.yaml
│   │   ├── source/                  PoseEngine Flutter/ML source code
│   │   └── tests/
│   └── kappture/
│       ├── project.yaml
│       ├── prompts.yaml
│       ├── tasks.yaml
│       └── tests/
├── src/
│   ├── agents/
│   │   ├── analyst.py               Log/metric analysis + RAG feedback loop
│   │   ├── developer.py             GitLab MR operations + ReAct loop
│   │   ├── monitor.py               Event polling (Teams, Metabase, GitLab, …)
│   │   └── planner.py               Plan-and-Execute orchestration
│   ├── core/
│   │   ├── llm_gateway.py           Singleton LLM with thread lock
│   │   ├── project_loader.py        ProjectConfig singleton
│   │   └── queue_manager.py         SQLite-backed task queue + worker thread
│   ├── interface/
│   │   ├── api.py                   FastAPI application (all endpoints)
│   │   └── teams_bot.py             Teams adaptive card notifications
│   ├── memory/
│   │   ├── audit_logger.py          Append-only SQLite audit trail
│   │   └── vector_store.py          ChromaDB wrapper (RAG + feedback)
│   ├── modules/                     Nano-modules: zero-dependency utility library
│   │   ├── severity.py              Severity enum and comparison
│   │   ├── json_extractor.py        Robust JSON extraction from LLM output
│   │   ├── trace_id.py              UUID trace ID generation and validation
│   │   ├── payload_validator.py     Task payload validation against tasks.yaml schemas
│   │   └── event_bus.py             In-process publish/subscribe event routing
│   └── main.py                      Entry point: api / cli / monitor / demo modes
├── tests/                           Framework unit tests (216 tests total)
│   ├── conftest.py
│   ├── modules/                     Nano-module tests (119 tests)
│   ├── test_api.py
│   ├── test_llm_gateway.py
│   ├── test_audit_logger.py
│   ├── test_vector_store.py
│   ├── test_analyst_agent.py
│   ├── test_developer_agent.py
│   ├── test_monitor_agent.py
│   └── test_queue_manager.py
├── web/
│   ├── src/
│   │   ├── components/
│   │   │   ├── dashboard/           SystemHealthCard, ActiveAlertsPanel, ErrorTrendChart
│   │   │   ├── analyst/             LogAnalysisForm, ProposalCard, ApprovalButtons
│   │   │   ├── developer/           MRCreateForm, MRReviewPanel, OpenMRsList
│   │   │   ├── audit/               AuditLogTable, TraceDetailModal
│   │   │   ├── monitor/             MonitorStatusPanel
│   │   │   └── shared/              ModuleWrapper, FeatureRequestPanel
│   │   ├── hooks/
│   │   │   └── useProjectConfig.ts  Fetches /config/project on load
│   │   ├── registry/
│   │   │   ├── modules.ts           MODULE_REGISTRY — module metadata for self-improvement
│   │   │   └── projects.ts          Per-solution module configs
│   │   ├── types/
│   │   │   └── module.ts            TypeScript types: ModuleMetadata, FeatureRequest
│   │   └── main.tsx                 React app entry point
│   ├── vite.config.ts               Vite config (API proxy to :8000)
│   ├── tailwind.config.ts
│   └── package.json
├── .env                             Live credentials (never committed)
├── .env.example                     Credentials template
├── .mcp.json                        Claude Code MCP server config (auto-detected)
├── .venv/                           Python 3.12.9 virtual environment (created by make venv)
├── Dockerfile                       Backend container
├── docker-compose.yml               Full stack deployment
├── Makefile                         Developer shortcuts (venv-aware)
├── pytest.ini
├── requirements.txt
├── requirements-minimal.txt         Minimal deps for low-RAM machines
├── ARCHITECTURE.md                  This file
└── README.md
```

---

## 11. REST API Endpoint Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service status, LLM provider, active project metadata, integration flags |
| `GET` | `/config/project` | Active project: name, domain, compliance_standards, active_modules, task_types, task_descriptions |
| `GET` | `/config/projects` | List all solutions available in the `solutions/` directory (`SAGE_SOLUTIONS_DIR`) |
| `POST` | `/analyze` | Submit a log/metric/error text to the Analyst Agent; returns proposal + `trace_id` |
| `POST` | `/approve/{trace_id}` | Approve a pending proposal; records approval in audit log |
| `POST` | `/reject/{trace_id}` | Reject a proposal with feedback text; feedback is embedded into ChromaDB |
| `GET` | `/audit` | Query compliance audit log (`?limit=50&offset=0`) |
| `POST` | `/mr/create` | Create a GitLab MR from an issue (`project_id`, `issue_iid`) |
| `POST` | `/mr/review` | AI review of a GitLab MR via ReAct loop (`project_id`, `mr_iid`) |
| `GET` | `/mr/open` | List open MRs for a GitLab project (`?project_id=…`) |
| `GET` | `/mr/pipeline` | CI/CD pipeline status for an MR (`?project_id=…&mr_iid=…`) |
| `GET` | `/monitor/status` | Monitor Agent polling status and last poll timestamps |
| `POST` | `/webhook/teams` | Receive Teams adaptive card approval callbacks |
| `POST` | `/feedback/feature-request` | Submit a UI module improvement request |
| `GET` | `/feedback/feature-requests` | List feature requests (`?module_id=…&status=…`) |
| `POST` | `/feedback/feature-requests/{id}/plan` | Trigger PlannerAgent to generate an implementation plan |
| `PATCH` | `/feedback/feature-requests/{id}` | Update a feature request status (approve / reject / complete) |

Interactive Swagger docs: `http://localhost:8000/docs`

---

## 12. MCP Servers

SAGE exposes hardware and external systems as MCP (Model Context Protocol) tool servers. These are available to both the Gemini CLI (via `~/.gemini/settings.json`) and Claude Code (via `.mcp.json`).

MCP servers for the medtech solution are located in `solutions/medtech/mcp_servers/`.

| Server | Module | Hardware/Service | Key Tools |
|--------|--------|-----------------|-----------|
| `sage-serial` | `solutions/medtech/mcp_servers/serial_port_server.py` | COM port / UART | `list_ports`, `send_command`, `read_output` |
| `sage-jlink` | `solutions/medtech/mcp_servers/jlink_server.py` | SEGGER J-Link JTAG/SWD | `connect_jlink`, `flash_firmware`, `read_memory`, `read_rtt` |
| `sage-metabase` | `solutions/medtech/mcp_servers/metabase_server.py` | Metabase analytics | `query_errors`, `list_dashboards` |
| `sage-spira` | `solutions/medtech/mcp_servers/spira_server.py` | SpiraTeam | `create_incident`, `list_incidents`, `get_test_runs` |
| `sage-teams` | `solutions/medtech/mcp_servers/teams_server.py` | Microsoft Teams | `read_messages`, `send_alert` |
| `gitlab` | npm MCP (`@modelcontextprotocol/server-gitlab`) | GitLab | `list_mrs`, `review_mr`, `create_issue` |

---

## 13. Minimum Configuration (Low-Resource Deployment)

SAGE can run on a basic development laptop with no GPU and no external services configured.

### Step 1 — Create virtual environment and minimal install

```bash
make venv            # Creates .venv/ and installs full dependencies
# Or for minimal (no chromadb/sentence-transformers):
make install-minimal
# Installs: pyyaml, pydantic, fastapi, uvicorn, python-dotenv, requests, httpx
# Does NOT install: chromadb, sentence-transformers, llama-cpp-python
```

Without ChromaDB, the vector store falls back to in-memory embeddings (no persistence between runs). All other functionality is unaffected.

### Step 2 — No credentials required for basic use

With Gemini CLI authenticated via browser OAuth, no `.env` credentials are needed for the analyst, developer, or planner agents. Integration features (Teams, GitLab, Metabase, Spira) will be disabled until the relevant environment variables are set.

### Step 3 — Start the system

```bash
# Terminal 1: Backend
make run PROJECT=kappture

# Terminal 2: Web UI
make ui
```

### Resource footprint in minimal mode

| Component | RAM |
|-----------|-----|
| Python (FastAPI + agents) | ~120 MB |
| React dev server (Vite) | ~80 MB |
| Total baseline | ~200 MB |

---

## 14. Roadmap

### Phase 1 — Core (Complete)
- LLM Gateway with dual providers (Gemini CLI + Local Llama)
- Audit Logger (SQLite, append-only)
- Analyst Agent with RAG and human feedback learning
- Human-in-the-loop CLI

### Phase 2 — Integration (Complete)
- Developer Agent (GitLab MR create/review/pipeline)
- MCP Servers (Serial, J-Link, Metabase, Spira, Teams)
- Single-lane Task Queue
- Monitor Agent (Teams, Metabase, GitLab polling)
- FastAPI REST interface
- Teams Bot (adaptive cards, approval flows)

### Phase 3 — Communication (Complete)
- Full Teams notification and webhook approval flow
- FastAPI dashboard endpoints
- Multi-mode entry point (`api` / `cli` / `monitor` / `demo`)

### Phase 4 — Web UI + Agentic Patterns (Complete)
- React 18 + TypeScript web UI (6 pages)
- ReAct loop in DeveloperAgent
- PlannerAgent (Plan-and-Execute)
- SQLite-backed persistent task queue
- Multi-project architecture (`ProjectConfig` singleton, `solutions/` directory)
- ModuleWrapper self-improvement system + Feature Request API
- Full regulatory documentation suite (`solutions/medtech/docs/`)
- Makefile, Dockerfile, docker-compose.yml

### Phase 5 — Framework Hardening (Complete)
- Renamed `projects/` → `solutions/`; MCP servers moved into `solutions/medtech/mcp_servers/`
- Nano-modules library (`src/modules/`): severity, json_extractor, trace_id, payload_validator, event_bus
- Python virtual environment: `.venv/` at repo root; all Makefile commands venv-aware
- Test suite expanded: 216 framework tests + 32 medtech solution tests = 248 total
- `SAGE_SOLUTIONS_DIR` env var for external solution directories
- `requirements-minimal.txt` for low-resource deployments

### Phase 6 — Autonomy (Planned)
- Multi-project UI switcher (select active solution from the web UI without restart)
- Webhook push subscriptions (Teams Graph API, GitLab webhooks — replace polling)
- Heartbeat scheduler (periodic automated scanning)
- Spira deep integration (auto-create incidents from detected errors)
- Self-improving RAG (auto-index new incidents from integrated services)
- GitLab CI/CD trigger (auto-queue MR reviews on new merge requests)

### Phase 7 — Platform (Planned)
- Marketplace of solution configurations (community-contributed `project.yaml` bundles)
- SaaS delivery model (hosted SAGE with solution selection at sign-up)
- Role-based access control on Feature Request system
- Per-solution compliance report generation
- Multi-tenant audit log isolation
