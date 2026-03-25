# SAGE Framework — User Guide

> Version 6.0.0 | Last updated: 2026-03-24

This guide covers everything needed to install, configure, run, and operate the SAGE Framework from day to day. It assumes no prior knowledge of the codebase.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Configuration](#2-configuration)
3. [Running a Solution](#3-running-a-solution)
4. [Using the Web UI](#4-using-the-web-ui)
5. [Human-in-the-Loop Approvals Inbox](#5-human-in-the-loop-approvals-inbox)
6. [Intelligence Layer](#6-intelligence-layer)
7. [Domain Solutions](#7-domain-solutions)
8. [Feature Request System](#8-feature-request-system)
9. [Adding a New Solution](#9-adding-a-new-solution)
10. [Solution Theming](#10-solution-theming)
11. [Running Tests](#11-running-tests)
12. [Troubleshooting](#12-troubleshooting)
13. [Action-Aware Chat](#13-action-aware-chat)
14. [Build Orchestrator](#14-build-orchestrator)
15. [Organization & Multi-Solution](#15-organization--multi-solution)

---

## 1. Installation

> **New here?** See [GETTING_STARTED.md](../GETTING_STARTED.md) for the zero-integration path — running in 15 minutes with no credentials.

### 1.1 Prerequisites

| Requirement | Minimum Version | Check |
|---|---|---|
| Python | 3.10 | `python --version` |
| Node.js | 18 | `node --version` |
| npm | 9 | `npm --version` |

### 1.2 Full Installation

```bash
# Clone the repository
git clone <your-repo-url> SAGE
cd SAGE

# Create virtual environment and install all Python dependencies (one-time)
make venv

# Install web UI dependencies
make install-ui
```

`make venv` creates `.venv/` and installs `requirements.txt` automatically. All subsequent `make` commands use `.venv/bin/python` (Linux/macOS) or `.venv/Scripts/python` (Windows).

### 1.3 Minimal Installation (Low-Resource Machines)

Use this on laptops without GPU, or when ChromaDB is not needed. The framework falls back to in-memory embeddings (no RAG persistence between runs).

```bash
make venv-minimal
make install-ui
```

Skips: `chromadb`, `sentence-transformers`, `llama-cpp-python`. All agents remain fully functional.

### 1.4 LLM Provider Setup

SAGE supports six providers. Pick one — none require an API key except `claude`.

| Provider | Setup | Internet | Best for |
|---|---|---|---|
| `gemini` (default) | `npm install -g @google/gemini-cli` then `gemini` (login once) | Yes | Cloud, latest models |
| `claude-code` | `npm install -g @anthropic-ai/claude-code` then `claude` (login once) | Yes | Claude models |
| `ollama` | Install from ollama.com -> `ollama serve` -> `ollama pull llama3.2` | No | Fully offline |
| `local` | `pip install llama-cpp-python` + download GGUF model | No | GPU-direct, air-gapped |
| `generic-cli` | Set `generic_cli_path` in `config/config.yaml` | Optional | Any CLI tool |
| `claude` | Set `ANTHROPIC_API_KEY` in `.env` | Yes | Only option requiring a key |

Set the provider in `config/config.yaml`:

```yaml
llm:
  provider: "ollama"
  ollama_model: "llama3.2"
```

Or switch at runtime without restarting:

```bash
curl -X POST http://localhost:8000/llm/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "model": "llama3.2"}'
```

---

## 2. Configuration

### 2.1 Environment Variables (`.env`)

Copy the template and fill in only the integrations you use. All values are optional — features degrade gracefully when credentials are absent.

```bash
cp .env.example .env
```

**Minimum for basic use (no integrations):**

```env
SAGE_PROJECT=starter
```

That is all. No credentials are needed to run the analyst, planner, or monitor agents with a no-API-key LLM provider.

**Add credentials as you enable integrations:**

```env
# GitLab (for MR review/create)
GITLAB_URL=https://gitlab.your-company.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx
GITLAB_PROJECT_ID=42

# Slack (for two-way approval — see docs/INTEGRATIONS.md)
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_APPROVAL_CHANNEL_ID=C...

# n8n (for external event forwarding)
N8N_WEBHOOK_SECRET=your-secret-here
```

See [docs/INTEGRATIONS.md](INTEGRATIONS.md) for the full reference for each integration.

### 2.2 `config/config.yaml`

Controls the base LLM configuration, integration settings, PII detection, data residency, budget controls, and task routing. Values can use `${ENV_VAR}` interpolation.

Key settings:

```yaml
llm:
  provider: "gemini"              # gemini | claude-code | ollama | local | generic-cli | claude
  gemini_model: "gemini-2.5-flash"
  timeout: 120

  # Multi-LLM Provider Pool
  multi_provider:
    enabled: false
    default_strategy: "fallback"  # voting | fastest | fallback | quality

  # Budget Controls
  budgets:
    enabled: false
    default_monthly_usd: 50.0

  # Task Routing by Task Type
  task_routing:
    enabled: true
    routes:
      BACKEND: "claude-code/claude-sonnet-4-6"
      DOCS:    "gemini/gemini-2.5-flash"

pii:
  enabled: false
  mode: "redact"                  # redact | mask | flag_only

memory:
  backend: "chroma"               # chroma | llamaindex

system:
  log_level: "INFO"
  max_concurrent_tasks: 1
  parallel_enabled: true
  parallel_max_workers: 4
```

### 2.3 Solution Selection

The active solution controls which prompts, task types, and UI modules are used. Select it in one of these ways (highest to lowest priority):

```bash
# 1. CLI flag
python src/main.py api --project meditation_app

# 2. Environment variable
SAGE_PROJECT=four_in_a_line python src/main.py api

# 3. Makefile
make run PROJECT=medtech_team

# 4. Default (if none specified)
# Falls back to: starter
```

Switch solution at runtime without restarting the backend:

```bash
curl -X POST http://localhost:8000/config/switch \
  -H "Content-Type: application/json" \
  -d '{"project": "meditation_app"}'
```

---

## 3. Running a Solution

### 3.1 Included Solutions

| Solution | Domain | Compliance |
|---|---|---|
| `starter` | Generic template | None |
| `meditation_app` | Flutter mobile + Node.js | GDPR |
| `four_in_a_line` | Casual game studio | GDPR, COPPA |
| `medtech_team` | Medical device (embedded + web) | IEC 62304, ISO 14971, FDA 21 CFR 820 |
| `medtech` | Medical device (legacy) | IEC 62304, ISO 14971 |
| `automotive` | Infotainment, ADAS, telematics | ISO 26262, UN ECE WP.29, ISO/SAE 21434 |
| `avionics` | Avionics SW + systems | DO-178C, DO-254, ARP4754A |
| `iot_medical` | IoT medical device (Class C) | IEC 62304, ISO 14971, IEC 62443 |
| `elder_fall_detection` | Elder fall detection IoT | HIPAA, IEC 62304 |
| `fall_detection_firmware` | Fall detection firmware | IEC 62304 |
| `finmarkets` | Financial markets | SOC 2, PCI DSS |
| `kappture` | Point-of-sale | PCI DSS |
| `poseengine` | Pose estimation ML | None |
| `bluedrop_medical` | Medical device | IEC 62304, ISO 13485 |
| `tictac_arena` | Board game | None |
| `sol_a`, `sol_b` | Multi-solution org examples | None |

### 3.2 Starting the Backend

```bash
# Generic starter — works with no credentials
make run PROJECT=starter

# Or any of the example solutions
make run PROJECT=meditation_app
make run PROJECT=medtech_team
make run PROJECT=automotive

# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

Startup log confirms the active solution and LLM provider:

```
INFO     LLM Gateway active: GeminiCLI (gemini-2.5-flash)
INFO     Project loaded: Starter Template (starter v1.0.0)
INFO     Task queue SQLite storage initialised at ./data/audit_log.db
```

### 3.3 Starting the Web UI

In a separate terminal:

```bash
make ui
# Open http://localhost:5173
```

The UI fetches active solution metadata from `GET /config/project` on load and adapts page titles, labels, and task types to the active solution automatically.

### 3.4 Running as a Background Monitor

```bash
# Monitor + API server together
python src/main.py monitor --project starter

# Background monitor daemon (make shorthand)
make monitor PROJECT=meditation_app
```

### 3.5 Docker Deployment

```bash
# Full stack: backend + frontend
SAGE_PROJECT=starter docker-compose up --build

# Run in background
SAGE_PROJECT=medtech_team docker-compose up -d --build

# Stop
docker-compose down
```

When running in Docker: backend on port 8000, frontend (nginx) on port 3000.

### 3.6 Silent Launch (Windows)

Double-click `sage.bat` — starts backend + frontend with no visible terminal windows, then opens your browser. The web UI includes a **Stop SAGE** button.

---

## 4. Using the Web UI

Open `http://localhost:5173`. The sidebar is organised into five areas: **Work**, **Intelligence**, **Knowledge**, **Organization**, and **Admin**. Pages shown depend on your solution's `active_modules` list in `project.yaml`. The header shows the active solution, Cmd+K command palette trigger, and live LLM provider indicator.

**Cmd+K** — press anywhere to open the command palette and jump to any page instantly.

### All 27 UI Pages

| Area | Page | Route | Purpose |
|---|---|---|---|
| **Work** | Approvals | `/approvals` | HITL inbox — every AI proposal, risk-sorted |
| **Work** | Task Queue | `/queue` | Pending/running/completed tasks |
| **Work** | Dashboard | `/` | Project health overview, quick actions |
| **Work** | Build | `/build` | End-to-end product builder |
| **Work** | Live Console | `/live-console` | Streaming agent output |
| **Intelligence** | Agents | `/agents` | Run custom roles, hire agents |
| **Intelligence** | Analyst | `/analyst` | Log/error triage |
| **Intelligence** | Developer | `/developer` | MR review, code diff proposals |
| **Intelligence** | Monitor | `/monitor` | System event monitoring |
| **Intelligence** | Improvements | `/improvements` | Feature request backlog |
| **Intelligence** | Workflows | `/workflows` | Mermaid diagrams auto-generated from LangGraph |
| **Intelligence** | Goals | `/goals` | OKR tracker — objectives + key results |
| **Knowledge** | Vector Store | `/knowledge` | Search and manage knowledge base entries |
| **Knowledge** | Channels | `/activity` | Cross-team knowledge channels |
| **Knowledge** | Audit Log | `/audit` | Full compliance trail |
| **Knowledge** | Costs | `/costs` | Token spend, budget controls |
| **Organization** | Org Graph | `/org-graph` | React Flow graph of solutions and routing |
| **Organization** | Onboarding | `/onboarding` | Conversational wizard + domain template chooser |
| **Admin** | LLM Settings | `/llm` | Provider switch, token stats |
| **Admin** | Config Editor | `/yaml-editor` | Live YAML editing with hot-reload |
| **Admin** | Access Control | `/access-control` | RBAC roles and API keys |
| **Admin** | Integrations | `/integrations` | GitLab, Slack, n8n, Composio status |
| **Admin** | Settings | `/settings` | Solution config |
| **Admin** | Organization | `/settings/organization` | Company mission, vision, values |
| — | Issues | `/issues` | Feature backlog with priority filters |
| — | Guide | `/guide` | Interactive framework guide |
| — | Activity | `/activity` | Real-time audit log timeline |

### 4.1 Dashboard

Default landing page. Shows:

- **Domain Context Card** — solution name, version, and key facts from `project.yaml dashboard.context_items`.
- **Quick Actions** — shortcut buttons from `project.yaml dashboard.quick_actions`.
- **Pending Approvals Panel** — all proposals awaiting human review, with Approve/Reject controls. Auto-refreshes every 10 seconds.
- **System Health Card** — backend status, LLM provider, and active solution.
- **Active Alerts Panel** — recent flagged events from the audit log.
- **Error Trend Chart** — analysis events over the last 7 days.

### 4.2 Analyst Page

Submit logs, metrics, or error text for AI analysis.

1. Paste a log entry or error text into the input field.
2. Click **Analyze** (or use `POST /analyze/stream` for streaming output).
3. A proposal card appears: severity badge (RED/AMBER/GREEN/UNKNOWN), root cause hypothesis, recommended action, and trace ID.
4. Use the approval buttons — see Section 5.

The input label and page title adapt to the active solution via `ui_labels` in `project.yaml`.

### 4.3 Developer Page

Manages GitLab/GitHub merge request operations. Requires a GitLab/GitHub integration to be configured; remove `developer` from `active_modules` if not used.

- **Open MRs** — list open MRs for your project.
- **Review MR** — AI review via the ReAct loop (pipeline -> diff -> analysis).
- **Create MR** — AI-drafted MR title/description from an issue.

### 4.4 Monitor Page

Real-time status of the Monitor Agent's polling threads: last poll times, events detected, queue depth, and recent task table. Auto-refreshes every 30 seconds.

### 4.5 Audit Log Page

Searchable, paginated view of the immutable compliance audit trail. Every analysis, approval, rejection, MR review, MR creation, and webhook receipt is logged here. Click any row to see the full input, output, and metadata via trace ID. Supports CSV export.

### 4.6 Agents Page

Run any solution-defined agent role directly against a task.

1. **Select a role** from the role grid — roles come from `prompts.yaml -> roles:`.
2. Optionally use a **quick template** button (populated from `project.yaml ui_labels.agent_quick_templates`).
3. Enter your task description and optional context.
4. Click **Ask [Role Name]** — the agent responds with analysis, recommendations, and next steps, all requiring human approval before action.

**Hire Agent** — define a new role on the fly without editing files:

1. Click **Hire Agent** (top-right of the page).
2. Choose an icon, enter a name, description, and system prompt.
3. Optionally add task types (written to `tasks.yaml`).
4. Click **Propose Role** -> creates a HITL proposal.
5. Approve it on the Dashboard or via the API — the role appears immediately after approval.

**Analyze JD** — paste a job description and the LLM extracts a role definition automatically.

### 4.7 LLM Settings Page

View current provider, model, session usage, and daily limit. Switch providers at runtime without restarting the backend. Shows PII detection and data residency config. In dual-LLM mode (when configured), shows student/teacher win rates and escalation rates.

### 4.8 Improvements Page

Two tabs — never mix them:

- **Solution Backlog** — features for your application. Log -> AI plan -> approve -> implement.
- **SAGE Framework Ideas** — improvements to SAGE itself. Log here and raise as a GitHub Issue.

### 4.9 YAML Editor Page

Edit `project.yaml`, `prompts.yaml`, or `tasks.yaml` live in the browser. Changes are validated and hot-reloaded without restarting the backend.

### 4.10 Settings Page

Solution-level settings: collection name, max concurrent tasks, UI label overrides.

### 4.11 Live Console Page

Real-time SSE event stream — shows every task submission, agent response, and system event as it happens. Useful for debugging and monitoring agent activity without polling the audit log.

### 4.12 New Solution Page (Onboarding Wizard)

A conversational wizard that generates a complete new solution from a plain-language description.

1. Click **Start Conversation**.
2. Answer the assistant's guided questions about your domain, team, compliance requirements, and integrations.
3. Watch the **Gathered Info** panel fill in as the LLM extracts details from your answers.
4. When enough information has been collected, a **Generate Solution** button appears.
5. Click it — a HITL proposal is created to write `project.yaml`, `prompts.yaml`, and `tasks.yaml`.
6. Approve the proposal on the Dashboard. The solution directory is created immediately.
7. Restart the backend with `make run PROJECT=<your_solution_name>`.

Additional onboarding features:
- **Scan Folder** — point to an existing project folder and the LLM analyzes the codebase to auto-generate YAML.
- **Refine** — iterate on generated YAML with feedback.
- **Domain Templates** — pick from 6 pre-built org structure templates.

### 4.13 Build Console

End-to-end product builder. Describe what you want to build in plain language, and the Build Orchestrator decomposes it into tasks, assigns agents, and builds the product with HITL gates at each phase.

### 4.14 Org Graph Page

React Flow graph showing all solutions in the org, knowledge channels between them, and task routing rules. Manage solutions, channels, and routes directly from this page.

### 4.15 Workflows Page

Auto-generates Mermaid diagrams from every LangGraph `StateGraph` in every solution. Always accurate — never manually drawn.

### 4.16 Goals Page

OKR tracker: define objectives and key results, track progress bars against in-progress work.

### 4.17 Costs Page

Token usage and cost tracking per solution, per provider, per day. Set budget limits and view spend trends.

### 4.18 Access Control Page

Manage RBAC roles and API keys. Create, view, and revoke API keys for programmatic access.

### 4.19 Integrations Page

Status and configuration for all connected integrations: GitLab, Slack, n8n, Teams, Composio.

### 4.20 Organization Settings Page

Company-level settings: mission, vision, and core values. Editable at `/settings/organization`.

---

## 5. Human-in-the-Loop Approvals Inbox

Every AI-initiated write action generates a **Proposal** before anything executes. The Approvals inbox (`/approvals`) is the founder's primary interface.

### 5.1 Risk Tiers

| Tier | Colour | Example | Expiry |
|---|---|---|---|
| INFORMATIONAL | Gray | Read-only query | 1 hour |
| EPHEMERAL | Blue | LLM provider switch | 8 hours |
| STATEFUL | Amber | Knowledge base edit | 7 days |
| EXTERNAL | Orange | GitLab MR creation | 14 days |
| DESTRUCTIVE | Red | Delete knowledge entry | Never |

DESTRUCTIVE proposals show a red warning banner and require an explicit human note before approval.

### 5.2 Approving via the Inbox (Web UI)

1. Open `/approvals` — proposals are sorted by risk (highest first).
2. Click any proposal to see the full payload in the right panel.
3. Enter your name in **Approving as** (for the named-approval audit trail).
4. Add optional feedback, then click **Approve** or **Reject**.
5. For low-risk batches: tick **Select all** -> **Approve all in group**.

### 5.3 Approving via REST API

```bash
# Approve
curl -X POST http://localhost:8000/approve/a1b2c3d4-... \
  -H "Content-Type: application/json" \
  -d '{"feedback": "approved — looks correct"}'

# Reject with correction
curl -X POST http://localhost:8000/reject/a1b2c3d4-... \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Root cause is db pool exhaustion, not network timeout"}'

# List pending
curl http://localhost:8000/proposals/pending

# Batch approve
curl -X POST http://localhost:8000/proposals/approve-batch \
  -H "Content-Type: application/json" \
  -d '{"trace_ids": ["id1", "id2", "id3"]}'

# Undo an approved code_diff
curl -X POST http://localhost:8000/proposals/trace-id-here/undo
```

### 5.4 Slack Block Kit Approval

When `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are configured, proposals are posted to your Slack channel as interactive messages with Approve/Reject buttons. Callback hits `POST /webhook/slack`.

---

## 6. Intelligence Layer

### 6.1 SAGE Intelligence SLM

An on-device small language model (Gemma 3 1B via Ollama) handles meta-questions about the framework itself — zero cloud calls required.

```bash
# Ask the SLM anything about SAGE
curl "http://localhost:8000/sage/ask?question=which+endpoint+switches+the+llm+provider"

# Convert plain intent to API call
curl -X POST http://localhost:8000/sage/intent \
  -d '{"text": "switch to ollama llama3.2"}'

# Lint YAML before saving
curl -X POST http://localhost:8000/sage/lint-yaml \
  -d '{"yaml_content": "roles:\n  - name: analyst"}'
```

Status: `GET /sage/status` — shows `slm_available`, model name, and capabilities. Requires `ollama serve` with `ollama pull gemma3:1b`.

### 6.2 Teacher-Student Distillation

The heavy teacher LLM (Claude/GPT-4) generates analyses; a fast student SLM learns from them. Cost drops over time without quality regression.

```bash
# Check drift stats
curl http://localhost:8000/distillation/starter/stats

# See recent comparisons
curl http://localhost:8000/distillation/starter/comparisons
```

### 6.3 SWE Agent (open-swe pattern)

Submit a coding task and the SWE agent autonomously explores the repo, plans, implements, runs tests, and opens a PR — then pauses for your review.

```bash
curl -X POST http://localhost:8000/swe/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Fix null pointer in CheckoutService", "repo_path": "/path/to/repo"}'
```

### 6.4 Visual Workflow Diagrams

`/workflows` auto-generates Mermaid diagrams from every LangGraph `StateGraph` in every solution.

### 6.5 Parallel Task Execution

Independent tasks run concurrently in waves. Configure at runtime:

```bash
curl -X POST "http://localhost:8000/queue/config?max_workers=4&parallel_enabled=true"
```

Solutions with `compliance_standards` automatically fall back to sequential single-lane execution.

### 6.6 HIL Testing (Hardware-in-the-Loop)

For embedded/IoT products — test on real hardware and generate regulatory evidence:

```bash
# Connect
curl -X POST http://localhost:8000/hil/connect \
  -d '{"transport": "serial", "port": "/dev/ttyUSB0", "baud": 115200}'

# Run a suite
curl -X POST http://localhost:8000/hil/run-suite \
  -d '{"suite_name": "safety_critical", "firmware_path": "build/firmware.bin"}'

# Get regulatory evidence report
curl http://localhost:8000/hil/report/{session_id}
```

Transports: `mock` (no hardware) / `serial` / `jlink` / `can` / `openocd`

### 6.7 Compliance Flags & Gap Assessment

```bash
# List supported domains
curl http://localhost:8000/compliance/domains

# Get checklist for a domain
curl http://localhost:8000/compliance/checklist/medtech

# Assess gaps for active solution
curl -X POST http://localhost:8000/compliance/gap-assessment \
  -d '{"solution_name": "iot_medical", "domain": "medtech"}'
```

Supported domains: `medtech` / `automotive` / `railways` / `avionics` / `iot_ics`

### 6.8 Multi-LLM Provider Pool

Register multiple LLM providers for parallel generation strategies:

```yaml
llm:
  multi_provider:
    enabled: true
    default_strategy: "fallback"    # voting | fastest | fallback | quality
    providers:
      claude-code:
        model: "claude-sonnet-4-6"
      gemini:
        model: "gemini-2.5-flash"
      ollama:
        model: "llama3.2"
```

### 6.9 Task Routing

Route different task types to different LLM providers automatically:

```yaml
llm:
  task_routing:
    enabled: true
    routes:
      BACKEND:  "claude-code/claude-sonnet-4-6"
      DOCS:     "gemini/gemini-2.5-flash"
      SAFETY:   "gemini/gemini-2.5-flash"
```

---

## 7. Domain Solutions

Pre-built agent teams with correct roles, system prompts, task types, and compliance standards for regulated industries.

### 7.1 Choosing a Domain Template

When creating a new solution via the **Onboarding** page (`/onboarding`), the wizard shows domain templates:

| Template | Pre-loaded standards | Agent roles |
|---|---|---|
| General Engineering | None | SWE, Test, Reviewer, Planner, CoS |
| MedTech | IEC 62304, ISO 14971, IEC 60601-1, FDA 21 CFR 820 | Software, QA, Risk, Regulatory, Validation, Safety, System |
| Automotive | ISO 26262, UN ECE WP.29, ISO/SAE 21434 | HMI, ADAS, Telematics, Safety, Cybersecurity, Test, Systems |
| Mobile App | App Store, Google Play, GDPR | iOS, Android, Backend, UX, Security, QA, DevOps |
| Railways | EN 50128, EN 50129, EN 50126 | Signalling, Traction, TCMS, Safety, Verification, Cybersecurity, Systems |
| Avionics | DO-178C, DO-254, ARP4754A | Avionics SW, DAL, Systems, Airworthiness, Test, Cybersecurity, DER |

### 7.2 Using a Domain Solution Directly

```bash
make run PROJECT=automotive    # ISO 26262 team
make run PROJECT=railways      # EN 50128 SIL-4 team
make run PROJECT=avionics      # DO-178C DAL A team
make run PROJECT=iot_medical   # IEC 62304 Class C IoT medical
```

The Agents page will show domain-specific roles immediately. The Analyst page title and input placeholder adapt to the domain automatically.

### 7.3 Org Chart

`/org-graph` shows the full org graph with solutions, knowledge channels, and task routing rules. Manage the multi-solution org from this page.

---

## 8. Feature Request System

Every page has a built-in improvement request system via the `ModuleWrapper` component.

### 8.1 Submitting a Request

1. Navigate to any page.
2. Look for the module name badge (top-left).
3. Click **Request Improvement**.
4. Select a scope:
   - **Solution** — a feature for your application.
   - **SAGE Framework** — an improvement to SAGE itself (also raise as a GitHub Issue).
5. Fill in title, description, and priority. Click **Submit**.

### 8.2 What Happens After Submission

1. Request appears on the **Improvements page** with status `pending`.
2. Click **Generate Plan** -> PlannerAgent decomposes it into implementation tasks.
3. Click **Approve** / **Reject** to update status.

---

## 9. Adding a New Solution

A SAGE solution is three YAML files — no Python code changes required. See [ADDING_A_PROJECT.md](ADDING_A_PROJECT.md) for the full field-by-field guide.

**Quick paths:**

1. **Onboarding wizard** (recommended): `/onboarding` page or `POST /onboarding/generate`
2. **Copy starter template**: `cp -r solutions/starter solutions/my_domain`
3. **Scan existing project**: `POST /onboarding/scan-folder` with your repo path

---

## 10. Solution Theming

Each solution can control its visual identity. Add a `theme:` block to `project.yaml`:

```yaml
theme:
  sidebar_bg:     "#0f172a"
  sidebar_text:   "#94a3b8"
  badge_bg:       "#1e293b"
  badge_text:     "#38bdf8"
```

The sidebar logo becomes the solution name. The browser tab title tracks the active solution. Update at runtime via `PATCH /config/project/theme`.

---

## 11. Running Tests

```bash
make test                    # Framework unit tests
make test-all                # Framework + all solution tests
make test-api                # Only api.py endpoint tests
make test-compliance         # IQ/OQ/PQ validation suite
make test-solution PROJECT=X # Single solution's tests
```

See [TESTING.md](TESTING.md) for the full testing guide.

---

## 12. Troubleshooting

**"Gemini CLI not found"**
```bash
npm install -g @google/gemini-cli
```

**Import errors on startup**
```bash
make venv    # Recreate the virtual environment from scratch
```

**Web UI shows blank or error on a page**
Check which modules are in `active_modules` in your `project.yaml`. If `developer` is listed but GitLab is not configured, that page will error.

**LLM calls timing out**
- Gemini CLI: run `gemini` in a terminal to re-authenticate
- Ollama: check `ollama serve` is running and the model is pulled
- Check `config/config.yaml` — the `provider` key must match what is running

---

## 13. Action-Aware Chat

The chat panel routes natural language to framework actions. Say "approve it" on the approvals page — the system identifies the pending proposal, presents a confirmation card, and executes on your approval.

```bash
# Send a chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "approve the latest proposal", "session_id": "abc"}'

# Execute a confirmed action
curl -X POST http://localhost:8000/chat/execute \
  -H "Content-Type: application/json" \
  -d '{"action": "approve_proposal", "params": {"trace_id": "abc123"}}'
```

Every `/chat/execute` call writes to `compliance_audit_log` with `actor="human_via_chat"`.

---

## 14. Build Orchestrator

End-to-end product build pipeline — from plain-language description to working codebase.

```bash
curl -X POST http://localhost:8000/build/start \
  -H "Content-Type: application/json" \
  -d '{
    "product_description": "A SaaS invoicing platform with Stripe integration",
    "solution_name": "invoicing_saas"
  }'
```

The orchestrator:
1. Detects the product domain from the description (13+ domains)
2. Generates a build plan with components and agents
3. Pauses at HITL gate for plan approval
4. Assigns tasks to agents from the workforce registry (19+ agents, 5 teams)
5. Uses adaptive routing (Q-learning) to pick the best agent per task type
6. Runs anti-drift checkpoints to prevent scope creep

Monitor build status: `GET /build/status/{run_id}`
Approve/reject at gates: `POST /build/approve/{run_id}`

---

## 15. Organization & Multi-Solution

SAGE supports multi-solution organizations where solutions share knowledge and route tasks between teams.

### Org Configuration

The org is defined in `solutions/org.yaml` and managed via the `/org-graph` page or the Org API:

- **Solutions** — register solutions in the org
- **Knowledge Channels** — shared vector store channels between solutions
- **Task Routes** — route specific task types from one solution to another

### API

```bash
# Get org config
curl http://localhost:8000/org

# Add a knowledge channel
curl -X POST http://localhost:8000/org/channels \
  -d '{"name": "security-findings", "solutions": ["sol_a", "sol_b"]}'

# Add a task route
curl -X POST http://localhost:8000/org/routes \
  -d '{"from_solution": "sol_a", "to_solution": "sol_b", "task_type": "SECURITY_REVIEW"}'
```
