# SAGE Framework
### *Smart Agentic-Guided Empowerment*

> Generic autonomous AI agent framework — configure once per project, run anywhere.

**SAGE (Smart Agentic-Guided Empowerment)** is a modular, multi-project autonomous AI developer agent. It monitors systems, analyzes errors and metrics, reviews code, creates merge requests, and surfaces proposals for human approval — all with domain-specific intelligence loaded from a simple three-file project configuration.

---

## Solutions

Solutions are **separate from the framework** — each is a folder of 3 YAML files
(`project.yaml`, `prompts.yaml`, `tasks.yaml`) plus optional tests and tools.

### Open example solutions (MIT licensed, included in this repo)

| Solution | Domain | Standards | Key Integrations |
|---|---|---|---|
| `medtech` | Medical devices | ISO 13485, IEC 62304, ISO 14971 | GitLab, Teams, Metabase, Spira, J-Link |
| `poseengine` | ML + Flutter mobile | — | GitLab, WandB, Firebase, CI/CD |
| `kappture` | Human tracking / CV | GDPR | GitLab, RTSP cameras, Prometheus, Grafana |
| `startup` | Full startup workspace | — | GitLab, GitHub, Slack, Notion, Google Workspace |

### Proprietary solutions (NOT in this repo)

Company-specific solutions live in their own **private repositories** and are
mounted at runtime via `SAGE_SOLUTIONS_DIR`. They never touch this repo.

```bash
# Example: attach a private DFS solution from a separate repo
SAGE_SOLUTIONS_DIR=/path/to/dfs-private-repo SAGE_PROJECT=dfs make run
```

See [`solutions/README.md`](solutions/README.md) for the full licensing model
and instructions for creating your own proprietary solution repo.

### Add your own solution

```bash
cp -r solutions/medtech solutions/my_solution
# Edit the three YAML files, then:
make run PROJECT=my_solution
```

---

## Features

- **Multi-Solution** — switch domain with a single flag; all agent prompts, task types, and UI labels adapt automatically
- **4 LLM Providers** — Gemini CLI (browser OAuth), Claude Code CLI (existing auth), Claude API (Anthropic SDK), Local Llama (offline GGUF)
- **UniversalAgent** — generic agent whose role, persona, and tools are defined entirely by solution YAML — no hardcoded domain logic
- **Human-in-the-Loop** — AI proposes, humans approve or correct; corrections are learned for future use
- **RAG Memory** — ChromaDB-backed vector search with in-memory fallback; project-isolated collections
- **Immutable Audit Trail** — every AI decision logged to SQLite (`data/audit_log.db`)
- **ReAct Loop** — multi-step Reason+Act reasoning for MR review (pipeline → diff → analysis)
- **PlannerAgent** — Plan-and-Execute orchestration for complex multi-step tasks
- **Persistent Task Queue** — SQLite-backed; pending tasks survive process restart
- **Web UI** — React 18 + TypeScript dashboard with AI agents page, solution switcher, LLM switcher, and self-improvement system
- **Nano-Modules** — zero-dependency utility library (`src/modules/`): severity, json_extractor, trace_id, payload_validator, event_bus
- **MCP Servers** — Serial port, J-Link, Metabase, Spira, Teams, GitLab (medtech solution)
- **Docker Ready** — single `docker-compose up` with `SAGE_PROJECT` env var

---

## New Here? Start with the Getting Started Guide

**[GETTING_STARTED.md](GETTING_STARTED.md)** — zero integrations, no API keys, running in 15 minutes. Uses the generic `starter` solution. Start here if you have never used SAGE before.

---

## Quick Start (if you know what you are doing)

```bash
make venv                   # Create .venv and install all deps (one-time)
make run PROJECT=starter    # Generic starter — works with no integrations
make ui                     # React web UI at http://localhost:5173
make test                   # Run framework tests
```

To run an existing domain solution:

```bash
make run PROJECT=medtech    # ISO 13485 medical device example
make run PROJECT=kappture   # Computer vision / human tracking example
make run PROJECT=poseengine # ML + Flutter mobile example
```

> `make venv` creates `.venv/` and installs all dependencies.
> All `make` commands use `.venv/Scripts/python` (Windows) or `.venv/bin/python` (Linux/macOS) automatically.
> Manual setup: `python -m venv .venv && .venv\Scripts\pip install -r requirements.txt`

### Authenticate Gemini CLI (first time only)

```bash
gemini
# Follow the browser OAuth prompt — no API key required
```

---

## Minimum Requirements

SAGE runs on a standard development laptop with no GPU. The minimum configuration uses Gemini CLI (cloud) and skips the heavy ML dependencies.

```bash
# Create venv first (if not done already)
make venv

# Minimal install — no chromadb / sentence-transformers
make install-minimal

# Start backend
make run PROJECT=kappture

# Baseline RAM: ~200 MB (backend ~120 MB + Vite dev server ~80 MB)
```

| Mode | CPU | RAM | GPU | Notes |
|------|-----|-----|-----|-------|
| Gemini CLI (default) | 4-core | 4 GB | Not required | Recommended for most teams |
| Local Llama (Phi-3.5 Mini Q4) | 8-core | 8 GB | Optional (4 GB VRAM for 10x speed) | Offline / air-gapped |

---

## All CLI Commands

### Direct Python

```bash
# FastAPI backend (production-style)
python src/main.py api --project medtech --host 0.0.0.0 --port 8000

# Interactive CLI with human-in-the-loop prompts
python src/main.py cli --project poseengine

# Background monitor daemon
python src/main.py monitor --project kappture

# Quick integration demo
python src/main.py demo --project medtech
```

### Make Shortcuts

```bash
make run                        # Backend: medtech (default), port 8000
make run PROJECT=poseengine     # Backend: poseengine
make run PROJECT=kappture       # Backend: kappture

make ui                         # React web UI at http://localhost:5173
make cli PROJECT=medtech        # Interactive CLI
make monitor PROJECT=kappture   # Background monitor daemon
make demo PROJECT=poseengine    # Quick demo

make venv                       # Create .venv and install all Python deps (one-time)
make install                    # Re-install Python deps into existing .venv
make install-minimal            # Minimal install (no chromadb/sentence-transformers)
make install-ui                 # Node.js dependencies for web UI
make install-dev                # Full install + test dependencies

make test                       # Framework unit tests
make test-all                   # Framework + medtech solution tests
make test-medtech               # medtech solution tests
make test-solution PROJECT=...  # Any solution's tests
make test-compliance            # Compliance/regulatory test suite
make test-api                   # API endpoint tests

make list-solutions             # Show all available solutions
make docker-up PROJECT=kappture # Start via Docker Compose
make docker-down                # Stop Docker stack
```

### Switch LLM Provider

Switch from the web UI (LLM Settings page) or via config:

```bash
# config/config.yaml
llm:
  provider: "gemini"        # Gemini CLI — browser OAuth, no API key (default)
  # provider: "claude-code" # Claude Code CLI — uses existing claude auth
  # provider: "claude"      # Claude API — needs ANTHROPIC_API_KEY
  # provider: "local"       # Local Llama GGUF — offline/air-gapped

# Or override at runtime
LLM_PROVIDER=claude-code python src/main.py api --project medtech
```

### Silent Launch (Windows)

Double-click `sage.bat` — starts backend + frontend with zero visible terminal windows, then opens your browser. The web UI includes a **Stop SAGE** button to shut everything down.

---

## REST API

Backend API at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service status, active project, LLM provider, integration flags |
| `GET` | `/config/project` | Active project metadata, task types, compliance standards |
| `GET` | `/config/projects` | List all available solutions in the `solutions/` directory (`SAGE_SOLUTIONS_DIR`) |
| `POST` | `/analyze` | Analyze a log/metric/error → AI proposal with `trace_id` |
| `POST` | `/approve/{trace_id}` | Approve a pending proposal |
| `POST` | `/reject/{trace_id}` | Reject with human feedback (triggers learning) |
| `GET` | `/audit` | Query audit log (`?limit=50&offset=0`) |
| `POST` | `/mr/create` | Create GitLab MR from issue |
| `POST` | `/mr/review` | AI MR review via ReAct loop |
| `GET` | `/mr/open` | List open MRs (`?project_id=…`) |
| `GET` | `/mr/pipeline` | CI/CD pipeline status (`?project_id=…&mr_iid=…`) |
| `GET` | `/monitor/status` | Monitor Agent polling status |
| `POST` | `/config/switch` | Switch active solution |
| `GET` | `/llm/status` | Current LLM provider, model, session usage |
| `POST` | `/llm/switch` | Switch LLM provider (gemini/claude-code/claude/local) |
| `GET` | `/agent/roles` | List available AI agent roles from solution prompts.yaml |
| `POST` | `/agent/run` | Run a solution-defined agent role against a task |
| `POST` | `/shutdown` | Stop backend and frontend processes |
| `POST` | `/webhook/teams` | Teams adaptive card approval callback |
| `POST` | `/feedback/feature-request` | Submit UI improvement request |
| `GET` | `/feedback/feature-requests` | List feature requests |
| `POST` | `/feedback/feature-requests/{id}/plan` | Auto-generate implementation plan |
| `PATCH` | `/feedback/feature-requests/{id}` | Update request status |

---

## Adding a New Solution

Create three files in a new `solutions/<name>/` directory:

```
solutions/
└── myproject/
    ├── project.yaml    ← name, domain, compliance_standards, active_modules, integrations
    ├── prompts.yaml    ← analyst, developer, planner, monitor system prompts
    └── tasks.yaml      ← task_types, task_descriptions, task_payloads
```

Then run:

```bash
python src/main.py api --project myproject
# Verify: GET http://localhost:8000/config/project
```

To use solutions stored outside the framework root, set `SAGE_SOLUTIONS_DIR`:

```bash
SAGE_SOLUTIONS_DIR=/path/to/external/solutions make run PROJECT=myproject
```

See `docs/ADDING_A_PROJECT.md` for the complete step-by-step guide with examples from the kappture project configuration.

---

## Docker Deployment

```bash
# Start full stack (backend + frontend)
SAGE_PROJECT=kappture docker-compose up --build

# Run in background
SAGE_PROJECT=poseengine docker-compose up -d --build

# Stop
docker-compose down
```

Services:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000` (nginx-served production build)

---

## Environment Variables

Copy `.env.example` to `.env`. Only configure the integrations you use — all are optional for basic operation.

| Variable | Service | Required for |
|----------|---------|-------------|
| `GITLAB_URL` | GitLab | MR operations |
| `GITLAB_TOKEN` | GitLab | Personal Access Token |
| `GITLAB_PROJECT_ID` | GitLab | Default project ID |
| `TEAMS_TENANT_ID` | Azure AD | Reading Teams messages |
| `TEAMS_CLIENT_ID` | Azure AD | Reading Teams messages |
| `TEAMS_CLIENT_SECRET` | Azure AD | Reading Teams messages |
| `TEAMS_TEAM_ID` | Teams | Channel monitoring |
| `TEAMS_CHANNEL_ID` | Teams | Channel monitoring |
| `TEAMS_INCOMING_WEBHOOK_URL` | Teams | Sending notifications |
| `METABASE_URL` | Metabase | Error dashboard polling |
| `METABASE_USERNAME` | Metabase | Service account |
| `METABASE_PASSWORD` | Metabase | Service account |
| `METABASE_ERROR_QUESTION_ID` | Metabase | Error query card ID |
| `SPIRA_URL` | SpiraTeam | Incident management |
| `SPIRA_USERNAME` | SpiraTeam | Login username |
| `SPIRA_API_KEY` | SpiraTeam | API key |
| `SPIRA_PROJECT_ID` | SpiraTeam | Default project ID |
| `SERIAL_PORT` | Hardware | COM port (e.g. COM3) |
| `JLINK_DEVICE` | Hardware | Target MCU name |
| `LLM_PROVIDER` | LLM | Override config.yaml provider |
| `SAGE_PROJECT` | Framework | Active project (overrides --project flag) |

---

## MCP Servers

SAGE exposes hardware and external systems as MCP tools for both Gemini CLI and Claude Code.

| Server | Purpose | Key Tools |
|--------|---------|-----------|
| `sage-serial` | Serial port / COM port communication | list_ports, send_command, read_output |
| `sage-jlink` | J-Link JTAG/SWD debugger | flash_firmware, read_memory, read_rtt |
| `sage-metabase` | Metabase analytics | query_errors, list_dashboards |
| `sage-spira` | SpiraTeam test management | create_incident, list_incidents, get_test_runs |
| `sage-teams` | Microsoft Teams | read_messages, send_alert |
| `gitlab` | GitLab (npm-based) | list_mrs, review_mr, create_issue |

Configure for Gemini CLI:

```bash
python scripts/setup_gemini_mcp.py
```

Claude Code picks up `.mcp.json` from the project root automatically.

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system design, agent architecture, ReAct/Plan diagrams, roadmap |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | End-user operational guide (installation → daily use) |
| [docs/ADDING_A_PROJECT.md](docs/ADDING_A_PROJECT.md) | Step-by-step guide for adding a new project |
| [docs/SETUP.md](docs/SETUP.md) | Detailed installation and integration setup |
| [docs/MCP_SERVERS.md](docs/MCP_SERVERS.md) | MCP server reference |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | External system integration guide |
| [solutions/medtech/docs/COMPLIANCE.md](solutions/medtech/docs/COMPLIANCE.md) | ISO 13485 / FDA 21 CFR Part 11 compliance details |

### Regulatory Documentation (`solutions/medtech/docs/regulatory/`) — medtech solution

| Document | Standard |
|----------|---------|
| [SRS.md](solutions/medtech/docs/regulatory/SRS.md) | Software Requirements Specification |
| [RISK_MANAGEMENT.md](solutions/medtech/docs/regulatory/RISK_MANAGEMENT.md) | ISO 14971 Risk Management |
| [SOUP_INVENTORY.md](solutions/medtech/docs/regulatory/SOUP_INVENTORY.md) | IEC 62304 §8.1.2 SOUP Inventory |
| [VV_PLAN.md](solutions/medtech/docs/regulatory/VV_PLAN.md) | Verification and Validation Plan |
| [RTM.md](solutions/medtech/docs/regulatory/RTM.md) | Requirements Traceability Matrix |
| [DHF_INDEX.md](solutions/medtech/docs/regulatory/DHF_INDEX.md) | Design History File Index |
| [TEST_REPORT_TEMPLATE.md](solutions/medtech/docs/regulatory/TEST_REPORT_TEMPLATE.md) | Software Test Report Template |
| [CHANGE_CONTROL.md](solutions/medtech/docs/regulatory/CHANGE_CONTROL.md) | Change Control Procedure |
| [CONFIG_MGMT_PLAN.md](solutions/medtech/docs/regulatory/CONFIG_MGMT_PLAN.md) | Configuration Management Plan |
| [SECURITY_PLAN.md](solutions/medtech/docs/regulatory/SECURITY_PLAN.md) | Cybersecurity Plan |

---

## License

MIT
