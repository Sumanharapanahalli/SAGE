# SAGE Framework — User Guide

> Version 5.0.0 | Last updated: 2026-03-20 | Browser-verified ✅

This guide covers everything needed to install, configure, run, and operate the SAGE Framework from day to day. It assumes no prior knowledge of the codebase.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Configuration](#2-configuration)
3. [Running a Solution](#3-running-a-solution)
4. [Using the Web UI](#4-using-the-web-ui)
5. [Human-in-the-Loop Approvals Inbox](#5-human-in-the-loop-approvals-inbox)
6. [Intelligence Layer v1](#6-intelligence-layer-v1)
7. [Domain Solutions](#7-domain-solutions)
8. [Feature Request System](#8-feature-request-system)
9. [Adding a New Solution](#9-adding-a-new-solution)
10. [Solution Theming](#10-solution-theming)
11. [Running Tests](#11-running-tests)
12. [Troubleshooting](#12-troubleshooting)
13. [Action-Aware Chat](#13-action-aware-chat)
14. [SAGE 9 Framework Features](#14-sage-9-framework-features)
15. [Build Orchestrator](#15-build-orchestrator)

---

## 1. Installation

> **New here?** See [GETTING_STARTED.md](../GETTING_STARTED.md) for the zero-integration path — running in 15 minutes with no credentials.

### 1.1 Prerequisites

| Requirement | Minimum Version | Check |
|-------------|----------------|-------|
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

`make venv` creates `.venv/` and installs `requirements.txt` automatically. All subsequent `make` commands use `.venv/Scripts/python` (Windows) or `.venv/bin/python` (Linux/macOS).

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
|----------|-------|----------|---------|
| `gemini` (default) | `npm install -g @google/gemini-cli` then `gemini` (login once) | Yes | Cloud, latest models |
| `claude-code` | `npm install -g @anthropic-ai/claude-code` then `claude` (login once) | Yes | Claude models |
| `ollama` | Install from ollama.com → `ollama serve` → `ollama pull llama3.2` | No | Fully offline |
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

# n8n (for external event forwarding — replaces Teams/Metabase/Spira direct creds)
N8N_WEBHOOK_SECRET=your-secret-here
```

See [docs/INTEGRATIONS.md](INTEGRATIONS.md) for the full reference for each integration.

### 2.2 `config/config.yaml`

Controls the base LLM configuration and integration settings. Values can use `${ENV_VAR}` interpolation.

Key settings:

```yaml
llm:
  provider: "gemini"              # gemini | claude-code | ollama | local | generic-cli | claude
  gemini_model: "gemini-2.5-flash"
  timeout: 120

memory:
  vector_db_path: "./data/chroma_db"
  audit_db_path: "./data/audit_log.db"

system:
  log_level: "INFO"
  max_concurrent_tasks: 1         # single-lane by design — do not change
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
|---------|--------|-----------|
| `starter` | Generic template | None |
| `meditation_app` | Flutter mobile + Node.js | GDPR |
| `four_in_a_line` | Casual game studio | GDPR, COPPA |
| `medtech_team` | Medical device (embedded + web) | IEC 62304, ISO 14971, FDA 21 CFR 820 |
| `automotive` | Infotainment, ADAS, telematics | ISO 26262, UN ECE WP.29, ISO/SAE 21434 |
| `mobile_app` | iOS + Android + Flutter | App Store, Google Play, GDPR |
| `railways` | Signalling, traction, TCMS | EN 50128, EN 50129, EN 50126 |
| `avionics` | Avionics SW + systems | DO-178C, DO-254, ARP4754A |
| `iot_medical` | IoT medical device (Class C) | IEC 62304, ISO 14971, IEC 62443 |

### 3.2 Starting the Backend

```bash
# Generic starter — works with no credentials
make run PROJECT=starter

# Or any of the example solutions
make run PROJECT=meditation_app
make run PROJECT=four_in_a_line
make run PROJECT=medtech_team

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

Open `http://localhost:5173`. The sidebar is organised into four sections: **WORK**, **AGENTS**, **INTELLIGENCE**, **SETTINGS**. Pages shown depend on your solution's `active_modules` list in `project.yaml`. The header shows the active solution, Cmd+K command palette trigger, and live LLM provider indicator.

**Cmd+K** — press anywhere to open the command palette and jump to any of the 22 pages instantly.

### Browser-Verified Pages (tested 2026-03-18)

| Page | Status | Notes |
|------|--------|-------|
| Dashboard | ✅ PASS | Domain context card, quick actions, 630 pending approvals shown |
| Approvals | ✅ PASS | HITL inbox: DESTRUCTIVE/IRREVERSIBLE badges, approve/reject, full payload |
| Agents | ✅ PASS | Domain-specific agent grid (11 automotive agents shown) |
| Org Chart | ✅ PASS | Founder → 6 agents tree, live status, daily task counts |
| Workflows | ✅ PASS | 4 workflows with Mermaid diagrams auto-generated |
| Analyst | ✅ PASS | Domain-adapted title "Vehicle Log & Trace Analyzer" |
| Activity | ✅ PASS | Real-time audit log, All/Tasks/Proposals/LLM/Errors tabs |
| Goals | ✅ PASS | OKR tracker: 2 objectives with progress bars |
| Onboarding | ✅ PASS | 3-step wizard: Describe → Answer → Approve & activate |
| Audit Log | ✅ PASS | Full table: timestamp, actor, action type, trace ID, Export CSV |

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
- **Review MR** — AI review via the ReAct loop (pipeline → diff → analysis).
- **Create MR** — AI-drafted MR title/description from an issue.

### 4.4 Monitor Page

Real-time status of the Monitor Agent's polling threads: last poll times, events detected, queue depth, and recent task table. Auto-refreshes every 30 seconds.

### 4.5 Audit Log Page

Searchable, paginated view of the immutable compliance audit trail. Every analysis, approval, rejection, MR review, MR creation, and webhook receipt is logged here. Click any row to see the full input, output, and metadata via trace ID.

### 4.6 Agents Page

Run any solution-defined agent role directly against a task.

1. **Select a role** from the role grid — roles come from `prompts.yaml → roles:`.
2. Optionally use a **quick template** button (populated from `project.yaml ui_labels.agent_quick_templates`).
3. Enter your task description and optional context.
4. Click **Ask [Role Name]** — the agent responds with analysis, recommendations, and next steps, all requiring human approval before action.

**Hire Agent** — define a new role on the fly without editing files:

1. Click **Hire Agent** (top-right of the page).
2. Choose an icon, enter a name, description, and system prompt.
3. Optionally add task types (written to `tasks.yaml`).
4. Click **Propose Role** → creates a HITL proposal.
5. Approve it on the Dashboard or via the API — the role appears immediately after approval.

### 4.7 LLM Settings Page

View current provider, model, session usage, and daily limit. Switch providers at runtime without restarting the backend. In dual-LLM mode (when configured), shows student/teacher win rates and escalation rates.

### 4.8 Improvements Page

Two tabs — never mix them:

- **Solution Backlog** — features for your application. Log → AI plan → approve → implement.
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

This is the recommended path for any new domain. The direct API endpoint (`POST /onboarding/generate`) is also available for scripted or CI usage — see Section 7.

---

## 5. Human-in-the-Loop Approvals Inbox

Every AI-initiated write action generates a **Proposal** before anything executes. The Approvals inbox (`/approvals`) is the founder's primary interface.

### 5.1 Risk Tiers

| Tier | Colour | Example | Expiry |
|------|--------|---------|--------|
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
5. For low-risk batches: tick **Select all** → **Approve all in group**.

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
```

### 5.4 Slack Block Kit Approval

When `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are configured, proposals are posted to your Slack channel as interactive messages with Approve/Reject buttons. Callback hits `POST /webhook/slack`.

---

## 6. Intelligence Layer v1

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

Enable in `config/config.yaml`:
```yaml
llm_strategy:
  mode: "dual"
  teacher:
    provider: "claude-code"
  student:
    provider: "ollama"
    confidence_threshold: 0.85
  distillation:
    enabled: true
```

### 6.3 SWE Agent (open-swe pattern)

Submit a coding task and the SWE agent autonomously explores the repo, plans, implements, runs tests, and opens a PR — then pauses for your review.

```bash
curl -X POST http://localhost:8000/swe/task \
  -H "Content-Type: application/json" \
  -d '{"task": "Fix null pointer in CheckoutService", "repo_path": "/path/to/repo"}'
# → {"run_id": "...", "status": "awaiting_approval", "result": {"pr_url": "..."}}

# Resume after review
curl -X POST http://localhost:8000/workflow/resume \
  -d '{"run_id": "...", "feedback": {"approved": true}}'
```

### 6.4 Visual Workflow Diagrams

`/workflows` auto-generates Mermaid diagrams from every LangGraph `StateGraph` in every solution. Browser-verified: **4 workflows discovered** (swe_workflow, analysis_workflow, hil_workflow, swe_workflow).

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

Transports: `mock` (no hardware) · `serial` · `jlink` · `can` · `openocd`

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

Supported domains: `medtech` · `automotive` · `railways` · `avionics` · `iot_ics`

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

`/org` shows the full agent team hierarchy with `reports_to` relationships, live status (Active/Idle/Error), and daily task counts. The Founder sits at the top — always "In Control".

---

## 8. Feature Request System

Every page has a built-in improvement request system via the `ModuleWrapper` component.

### 6.1 Submitting a Request

1. Navigate to any page.
2. Look for the module name badge (top-left) — e.g. `Log Analyzer v1.2.0`.
3. Click **Request Improvement** (amber button, top-right of the module strip).
4. The panel slides in. Select a scope:
   - **Solution** — a feature for your application.
   - **SAGE Framework** — an improvement to SAGE itself (also raise as a GitHub Issue).
5. Fill in title, description, and priority. Click **Submit**.

### 6.2 What Happens After Submission

1. Request appears on the **Improvements page** with status `pending`.
2. Click **Generate Plan** → PlannerAgent decomposes it into implementation tasks.
3. Click **Approve** / **Reject** to update status.

---

## 9. Adding a New Solution

A SAGE solution is three YAML files — no Python code changes required.

See [docs/ADDING_A_PROJECT.md](ADDING_A_PROJECT.md) for the full step-by-step guide.

**Option A — Conversational wizard in the web UI (recommended):**

Open the **New Solution** page in the sidebar (wand icon). The wizard guides you through a multi-turn conversation, extracts your domain info, and creates a HITL proposal to generate all three YAML files. Approve it on the Dashboard, then restart with `make run PROJECT=<name>`. See [Section 4.12](#412-new-solution-page-onboarding-wizard) for the step-by-step flow.

**Option B — Direct API call (scripted/CI use):**

```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "We build a SaaS invoicing platform in React and Node.js.",
    "solution_name": "invoicing_saas",
    "compliance_standards": ["SOC 2 Type II"],
    "integrations": ["github", "slack"]
  }'
# Returns a trace_id — approve it, then: make run PROJECT=invoicing_saas
```

**Option C — From the starter template:**

```bash
cp -r solutions/starter solutions/my_project
# Edit the three YAML files, then:
make run PROJECT=my_project
```

---

## 10. Solution Theming

Each solution can have a completely unique visual identity — sidebar colour, accent buttons, header badge — all controlled by the `theme:` block in `project.yaml`. The framework reads these values on startup and applies them as CSS variables across the entire web UI. No React code changes are needed.

### 8.1 Theme Block Format

Add a `theme:` section to your solution's `project.yaml`:

```yaml
theme:
  sidebar_bg:          "#111827"   # sidebar background
  sidebar_text:        "#9ca3af"   # inactive nav item text
  sidebar_active_bg:   "#15803d"   # active nav item background
  sidebar_active_text: "#ffffff"   # active nav item / heading text
  sidebar_hover_bg:    "#1f2937"   # nav item hover background
  sidebar_accent:      "#6366f1"   # badge and icon accent colour
  accent:              "#6366f1"   # primary action buttons
  accent_hover:        "#4f46e5"   # primary button hover
  badge_bg:            "#f3f4f6"   # header domain badge background
  badge_text:          "#374151"   # header domain badge text
```

All values are standard CSS colour strings: `#hex`, `hsl(...)`, `rgb(...)`, or named colours. Omit the `theme:` block entirely to use the default SAGE dark-sidebar theme.

### 8.2 Example Themes

**Medical / clinical (blue sidebar):**
```yaml
theme:
  sidebar_bg:         "#1e3a5f"
  sidebar_active_bg:  "#1d4ed8"
  sidebar_accent:     "#60a5fa"
  accent:             "#2563eb"
  accent_hover:       "#1d4ed8"
```

**Game studio (dark purple):**
```yaml
theme:
  sidebar_bg:         "#1e1b2e"
  sidebar_active_bg:  "#7c3aed"
  sidebar_accent:     "#a78bfa"
  accent:             "#7c3aed"
  accent_hover:       "#6d28d9"
```

**Startup / green growth:**
```yaml
theme:
  sidebar_bg:         "#14532d"
  sidebar_active_bg:  "#166534"
  sidebar_accent:     "#86efac"
  accent:             "#16a34a"
  accent_hover:       "#15803d"
```

### 8.3 Quick Templates for the Agents Page

Populate per-role quick-fill buttons on the Agents page by adding `agent_quick_templates` under `ui_labels`:

```yaml
ui_labels:
  agent_quick_templates:
    analyst:
      - label: "Review latest error"
        task:  "Analyze the most recent error log and identify the root cause"
      - label: "Performance check"
        task:  "Review system performance metrics and suggest optimisations"
    developer:
      - label: "Code review"
        task:  "Review the latest code changes and flag potential issues"
        context: "Focus on security and correctness"
```

Keys map to role IDs in `prompts.yaml`. The framework renders these as clickable chips above the task input — clicking one pre-fills the task (and optional context) field.

### 8.4 How Themes Apply at Runtime

1. `GET /config/project` returns the full `project.yaml` including the `theme:` block.
2. The React `ThemeProvider` component reads `projectData.theme` and writes each key as a CSS custom property on `document.documentElement`.
3. All sidebar, button, and badge styles reference these properties (`var(--sage-sidebar-bg)` etc.).
4. When you switch solutions via the header dropdown, the theme updates instantly — no page reload.

---

## 11. Running Tests

```bash
# Framework tests (397 tests — fast, no external services)
make test

# Example solution tests
make test-medtech-team
make test-meditation-app
make test-four-in-a-line

# Any solution by name
make test-solution PROJECT=my_project

# Full suite: framework + medtech
make test-all

# Phase-specific tests
.venv/Scripts/pytest tests/test_phase3_langgraph.py -v
.venv/Scripts/pytest tests/test_phase5_streaming.py -v
.venv/Scripts/pytest tests/test_phase7_11_features.py -v

# API tests
make test-api

# With coverage
.venv/Scripts/pytest tests/ -m unit --cov=src --cov-report=term-missing
```

**Test structure:**

| Suite | Location | Speed | External services? |
|-------|---------|-------|--------------------|
| Framework unit tests | `tests/` | Fast | No |
| Phase integration tests | `tests/test_phase*.py` | Medium | No (mocked) |
| Solution tests | `solutions/<name>/tests/` | Medium | Partial |
| MCP tests | `solutions/*/tests/mcp/` | Fast | No (mocked) |
| Integration tests | `solutions/*/tests/integration/` | Slow | Yes (credentials) |
| IQ/OQ/PQ validation | `solutions/medtech/tests/validation/` | Medium | No |

---

## 12. Troubleshooting

### "Gemini CLI not found"

```bash
npm install -g @google/gemini-cli

# Ensure npm global bin is on PATH:
# Windows: add %APPDATA%\npm to PATH
# Linux/Mac: export PATH="$(npm root -g)/../bin:$PATH"

gemini --version
```

### "Gemini CLI timed out after 120s"

- Check internet connection.
- Re-authenticate: run `gemini` in a terminal and complete the browser OAuth flow.
- Increase timeout: `config/config.yaml` → `timeout: 180`

### "Ollama connection refused"

```bash
# Start Ollama service
ollama serve

# Pull a model if not already done
ollama pull llama3.2

# Test
curl http://localhost:11434/api/tags
```

### "Local model not loaded" / "GGUF file not found"

```bash
# Check config.yaml model_path
grep model_path config/config.yaml

# Verify the file exists
ls data/models/
```

### "ChromaDB embedding error"

```bash
pip install --upgrade sentence-transformers

# Pre-download the embedding model (for later offline use)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

Use `make venv-minimal` to skip ChromaDB entirely if persistent RAG is not needed.

### "GitLab API 401 Unauthorized"

- Verify `GITLAB_TOKEN` is a valid Personal Access Token with `api` scope and has not expired.
- Ensure `GITLAB_URL` has no trailing slash.

### Web UI shows "Failed to fetch" / blank dashboard

- Confirm backend is running: `curl http://localhost:8000/health`
- Check browser DevTools (F12 → Network) for CORS errors.
- Ensure Vite proxy in `web/vite.config.ts` points to `http://localhost:8000`.

### Import errors on startup

```bash
python --version    # Must be 3.10+
pip install -r requirements.txt
python -c "import fastapi, uvicorn, yaml; print('OK')"
```

### Tasks not processing (queue stuck)

1. Confirm the backend is running in `api` mode (not just imported).
2. Check backend logs for a silently killed worker thread exception.
3. Verify `data/audit_log.db` is not locked by another process.

```bash
curl http://localhost:8000/monitor/status
```

### Resetting the database (development only)

```bash
# Stop the backend first, then:
rm data/audit_log.db
rm -rf data/chroma_db/
# Restart — tables are recreated automatically
make run PROJECT=starter
```

**Never do this in a production or regulated environment.** The audit log is a compliance artifact.

### "J-Link DLL not found"

Install J-Link Software Pack from SEGGER (segger.com/downloads/jlink). Verify: `python -c "import pylink; j = pylink.JLink(); print(j.product_name)"`

---

## 13. Action-Aware Chat

The chat panel (bottom-right of the UI) is an **action-routing assistant** — not just a Q&A window. It understands page context and can execute actions on your behalf after confirmation.

### How it works

1. Type a message — the LLM classifies your intent.
2. If it's a question, you get an inline answer.
3. If it maps to an action, a **confirmation card** appears with an amber border, describing exactly what will happen.
4. Click **Confirm** to execute, or **Cancel** to abort.
5. Every interaction is logged in the chat history and the compliance audit trail.

### Available actions (via natural language)

| What you type | What happens |
|---|---|
| "approve it" / "approve the YAML edit" | `approve_proposal` — approves the pending proposal from page context |
| "reject that" / "reject with reason X" | `reject_proposal` — rejects with your stated reason |
| "undo that" | `undo_proposal` — reverts a code_diff proposal |
| "queue a firmware review for MR !42" | `submit_task` — creates a REVIEW_MR task in the queue |
| "change the analyst prompt to check HIPAA" | `propose_yaml_edit` — creates a yaml_edit proposal in the approvals inbox |
| "what does PRECISERR mean?" | `answer` — inline answer, no confirmation needed |
| "what's in the knowledge base about calibration?" | `query_knowledge` — searches vector store, returns inline |

### Page context enrichment

On the `/approvals` page, the chat automatically knows about pending proposals (trace IDs, descriptions) — so "approve it" refers to the right proposal without you needing to specify the ID.

### Audit trail

- **Every message** is stored in `chat_messages` with a `message_type`: `user`, `answer`, `action_proposed`, `action_confirmed`, `action_cancelled`, `action_executed`
- **Every execution** writes to `compliance_audit_log` with `actor="human_via_chat"`
- Clearing chat history never removes compliance log entries

---

## 14. SAGE 9 Framework Features

Nine production-ready framework features shipped in the SAGE 9 release.

### Feature D — Per-agent budget ceilings

Declare monthly call limits per agent role in `project.yaml`:

```yaml
agent_budgets:
  analyst:
    monthly_calls: 500
  developer:
    monthly_calls: 200
```

When an agent exceeds its limit, `generate()` raises a `RuntimeError` rather than making an additional LLM call. Check usage via `GET /llm/status`.

### Feature J — Undo button per proposal

Approved `code_diff` proposals can be reverted:

```bash
POST /proposals/{trace_id}/undo
```

The UI shows an **Undo** button next to each approved code diff in the Approvals page. Only `code_diff` type supports undo (other types return 400).

### Feature L — Live active-agents panel

```bash
GET /agents/active
```

Returns agents currently processing a task with their task type, start time, and progress. Embedded in the Dashboard as a live panel with 5-second polling.

### Feature A — Pre/post action hooks

Declare shell commands that run before and after any task type in `tasks.yaml`:

```yaml
task_types:
  - name: ANALYZE_LOG
    hooks:
      pre: "echo 'Starting analysis'"
      post: "curl -X POST https://webhook.site/... -d '{\"status\":\"done\"}'"
```

Hooks run in a subprocess. Failures are logged but do not block the task.

### Feature B — Repo map fed to agents

```bash
GET /repo/map
```

Returns a markdown file tree with symbol extraction (functions, classes). The Developer agent injects this into its system prompt for multi-file coherence, similar to Aider's repo map.

### Feature E — YAML-declared scheduled tasks

Define recurring tasks in `tasks.yaml`:

```yaml
scheduled:
  - task_type: ANALYZE_LOG
    cron: "0 9 * * 1"         # Mondays at 9am
    payload: {"log_source": "production"}
    description: "Weekly production log review"
```

The scheduler starts automatically with the backend. Check schedules:

```bash
GET /scheduler/status
```

### Feature F — Git worktree per concurrent proposal

When a `code_diff` proposal is created, SAGE automatically creates an isolated git worktree for it. The diff is applied and committed there. This allows multiple proposals to be in-flight simultaneously without branch conflicts.

### Feature K — Knowledge sync

Bulk-import all files matching a glob pattern into the vector knowledge base:

```bash
POST /knowledge/sync
{"path": "/path/to/docs", "pattern": "*.md", "solution": "starter"}
```

Or queue it as a task:
```yaml
task_types:
  - name: KNOWLEDGE_SYNC
    # auto-registered — no config needed
```

### Feature G — Wave-scheduled subagent spawning

Include `subtasks` in any task payload to run parallel sub-tasks:

```json
{
  "task_type": "ANALYZE_LOG",
  "payload": {
    "subtasks": [
      {"task_type": "ANALYZE_LOG", "input_data": {"log": "service-a.log"}},
      {"task_type": "ANALYZE_LOG", "input_data": {"log": "service-b.log"}}
    ]
  }
}
```

Sub-tasks run in parallel waves. Track them:
```bash
GET /tasks/{task_id}/subtasks
```

---

## 15. Build Orchestrator

The Build Orchestrator is SAGE's end-to-end product construction pipeline. Given a plain-language description of what to build, it decomposes the product into components, assigns work to a workforce of 19 agent roles across 32 task types, and delivers a working codebase — all with human approval gates at critical checkpoints. Domain-aware build detection automatically tailors the pipeline for 13 industry domains.

### 15.1 What It Does (0 to 1 to N)

The Build Orchestrator implements the **0 to 1 to N** pipeline:

- **0 to 1** — Takes a product idea (plain text) and produces a working, tested codebase with CI/CD, documentation, and deployment configuration.
- **1 to N** — Built products come with agentic patterns (monitor agents, analyst agents, scheduled tasks) that continue operating after the initial build, compounding intelligence over time.

### 15.2 Domain-Aware Build Detection

The orchestrator automatically detects the product domain from the description using keyword matching against `DOMAIN_RULES`. Each domain injects required task types, compliance standards, HITL overrides, and extra acceptance criteria into the build plan — no manual domain selection needed.

**13 supported domains:**

| Domain | Keywords (sample) | Required Task Types | Compliance Standards |
|---|---|---|---|
| `medical_device` | medical, clinical, FDA, patient | SAFETY, COMPLIANCE, EMBEDDED_TEST | IEC 62304, ISO 13485, FDA 21 CFR 820 |
| `automotive` | vehicle, ADAS, ECU, automotive | SAFETY, FIRMWARE, HARDWARE_SIM | ISO 26262, ASPICE, ISO/SAE 21434 |
| `avionics` | aircraft, avionics, flight, DO-178C | SAFETY, COMPLIANCE, SYSTEM_TEST | DO-178C, DO-254, ARP4754A |
| `robotics` | robot, actuator, ROS, kinematics | FIRMWARE, SAFETY, HARDWARE_SIM | ISO 10218, ISO/TS 15066 |
| `iot` | IoT, sensor, embedded, gateway | FIRMWARE, SECURITY, EMBEDDED_TEST | IEC 62443, ETSI EN 303 645 |
| `fintech` | payment, banking, trading, KYC | SECURITY, COMPLIANCE, REGULATORY | PCI DSS, SOX, PSD2 |
| `hardware_generic` | PCB, schematic, FPGA, ASIC | PCB_DESIGN, MECHANICAL, HARDWARE_SIM | IPC standards |
| `ml_ai` | machine learning, neural, training | ML_MODEL, DATA, TESTS | — |
| `saas_product` | SaaS, subscription, multi-tenant | BACKEND, FRONTEND, API, INFRA | SOC 2, GDPR |
| `consumer_app` | mobile app, iOS, Android | FRONTEND, BACKEND, UX_DESIGN | App Store, GDPR |
| `enterprise` | enterprise, ERP, CRM, B2B | BACKEND, API, SECURITY | SOC 2, ISO 27001 |
| `ecommerce` | shop, cart, checkout, catalog | FRONTEND, BACKEND, API | PCI DSS, GDPR |
| `healthcare_software` | EHR, HIPAA, telehealth | BACKEND, SECURITY, COMPLIANCE | HIPAA, HL7, FHIR |
| `edtech` | LMS, course, student, learning | FRONTEND, BACKEND, UX_DESIGN | FERPA, COPPA |

Domain detection is automatic. Each domain can override the default HITL level (e.g., `medical_device` forces `strict`) and inject extra acceptance criteria that the Critic Agent checks.

### 15.3 32 Task Types

The orchestrator routes work across 32 task types organised into four categories:

**Software (9):**
`BACKEND` · `FRONTEND` · `TESTS` · `INFRA` · `DOCS` · `DATABASE` · `API` · `CONFIG` · `AGENTIC`

**Hardware / Embedded / Mechanical (7):**
`FIRMWARE` · `HARDWARE_SIM` · `PCB_DESIGN` · `MECHANICAL` · `SAFETY` · `COMPLIANCE` · `EMBEDDED_TEST`

**Cross-cutting (3):**
`SECURITY` · `DATA` · `ML_MODEL`

**Business / Operational (13):**
`QA` · `SYSTEM_TEST` · `REGULATORY` · `BUSINESS_ANALYSIS` · `MARKET_RESEARCH` · `FINANCIAL` · `UX_DESIGN` · `DEVOPS` · `PRODUCT_MGMT` · `LEGAL` · `OPERATIONS` · `TRAINING` · `LOCALIZATION`

Task types are automatically selected based on the detected domain. Regulated domains inject their required task types (e.g., `medical_device` always includes `SAFETY` and `COMPLIANCE`).

### 15.4 19 Agent Roles in 5 Workforce Teams

The `WORKFORCE_REGISTRY` organises 19 agent roles into functional teams, each with a team lead, members, and declared capabilities:

| Team | Lead | Members | Capabilities |
|---|---|---|---|
| **Engineering** | developer | qa_engineer, system_tester, devops_engineer, localization_engineer | Code, test, deploy, localise |
| **Analysis** | analyst | business_analyst, financial_analyst, data_scientist | Research, model, analyse |
| **Design** | ux_designer | product_manager | UX, product strategy |
| **Compliance** | regulatory_specialist | legal_advisor, safety_engineer | Regulatory, legal, safety |
| **Operations** | operations_manager | technical_writer, marketing_strategist | Ops, docs, go-to-market |

The orchestrator assigns agents from the workforce registry based on task type. For example, `SAFETY` tasks route to `safety_engineer`; `UX_DESIGN` tasks route to `ux_designer`.

### 15.5 Adaptive Router (Q-Learning)

The `AdaptiveRouter` learns the best agent for each task type using Q-learning inspired scoring:

- **Exponential moving average** with learning rate 0.3 tracks success/quality scores per agent per task type.
- Requires **3+ observations** before overriding the default agent assignment.
- Falls back to the static `WORKFORCE_REGISTRY` mapping when insufficient data exists.
- Stats available via `GET /build/router/stats`.

Over time, the router shifts work toward higher-performing agents. This is compounding intelligence at the task-routing level — every build makes the next one better.

### 15.6 Anti-Drift Checkpoints

After each wave of agent execution, the orchestrator runs **anti-drift verification** — comparing each component's output against the original task intent. If the output has drifted from the plan:

- A `BUILD_DRIFT_WARNING` audit event is logged.
- The Critic Agent is invoked to assess severity.
- In `strict` HITL mode, the build pauses for human review.

This prevents the common failure mode where autonomous agents gradually diverge from the original product specification.

### 15.7 The ReAct Pattern for Agent Execution

Each build agent uses the **ReAct (Reason + Act)** pattern during code generation. The agent iterates through Thought, Action, and Observation steps — reading existing files, planning changes, writing code, running tests — until the component is complete. This is the same pattern used by the Developer agent for MR review (see Section 6 of ARCHITECTURE.md), extended to multi-file code generation.

### 15.8 The Critic Agent (Actor-Critic Loop)

Every major phase of the build passes through a **Critic Agent** before proceeding. The Critic scores the output on correctness, completeness, and consistency:

```
Agent produces output → Critic reviews → Score ≥ threshold? → Proceed
                                              ↓ (no)
                                        Agent revises → Critic re-reviews
```

The `critic_threshold` parameter (default: 0.7) controls the minimum acceptable score. Scores are returned in `GET /build/status/{run_id}` under `critic_scores` for plan, code, and integration phases.

### 15.9 HITL Gates

The Build Orchestrator supports three levels of human oversight:

| Level | Gates | Best for |
|---|---|---|
| `minimal` | Final build approval only | Trusted domains, prototyping, rapid iteration |
| `standard` | Plan review + final build approval | Default — balanced human oversight |
| `strict` | Plan review + per-component code review + final build approval | Regulated industries, safety-critical products |

At each gate, the build pauses and waits for `POST /build/approve/{run_id}`. Rejection feedback is fed back to the agents for revision. Domain detection can override the HITL level (e.g., `medical_device` forces `strict` regardless of the requested level).

### 15.10 Data Flow

```
Product description (plain text)
     ↓
Domain detection (DOMAIN_RULES keyword matching → 13 domains)
     ↓
Decompose → component list, 32 task types, agent assignments from WORKFORCE_REGISTRY
     ↓
AdaptiveRouter selects best agent per task (Q-learning scores)
     ↓
Critic reviews plan (actor-critic loop)
     ↓
HITL gate: human approves/rejects plan
     ↓
Scaffold → directory structure, configs, CI/CD
     ↓
Execute agents (wave-parallel per component)
     ↓
Anti-drift checkpoint (per wave)
     ↓
Critic reviews generated code (per component in strict mode)
     ↓
Integrate → cross-component wiring, shared types, routing
     ↓
Critic reviews integration
     ↓
HITL gate: human approves/rejects final build
     ↓
Finalize → tests, docs, deployment config
```

### 15.11 3-Tier Degradation for Code Generation

The Build Orchestrator tries three code generation strategies in order:

1. **Open SWE runner** — full autonomous coding agent with repo exploration, test execution, and PR creation (requires `open-swe` integration).
2. **LLM direct generation** — sends component specs to the active LLM provider with structured output parsing.
3. **Template scaffolding** — falls back to language-specific project templates with placeholder implementations.

Each tier produces a working starting point. The Critic Agent evaluates the output regardless of which tier generated it.

### 15.12 Wave-Based Parallel Execution

Components without dependencies are built concurrently in waves, using the same parallel task scheduler as the rest of SAGE (see Section 14, Feature G). For example, a frontend and backend component with no shared code can be built simultaneously, while an API client that depends on the backend schema waits for its wave.

### 15.13 Starting a Build from the Web UI

1. Navigate to the **Build** page (Work area in the sidebar).
2. Enter a product description in plain language.
3. Optionally set the solution name, repo URL, critic threshold, and HITL level.
4. Click **Start Build** — a `run_id` is returned and the build begins.
5. The orchestrator auto-detects the domain and shows the detected domain, required task types, and assigned agents.
6. When the build reaches a HITL gate, a notification appears in the Approvals inbox.
7. Review the plan or code, then approve or reject with feedback.

### 15.14 Starting a Build via the API

```bash
# Start a build
curl -X POST http://localhost:8000/build/start \
  -H "Content-Type: application/json" \
  -d '{
    "product_description": "A task management app with Kanban boards and team collaboration",
    "solution_name": "taskflow",
    "hitl_level": "standard"
  }'
# → {"run_id": "...", "status": "planning"}

# Check status (includes detected_domain, router_stats)
curl http://localhost:8000/build/status/{run_id}

# Approve the plan
curl -X POST http://localhost:8000/build/approve/{run_id} \
  -d '{"approved": true, "feedback": "Plan looks good"}'

# List all builds
curl http://localhost:8000/build/runs

# List supported domains
curl http://localhost:8000/build/domains

# View adaptive router performance
curl http://localhost:8000/build/router/stats
```

### 15.15 Agentic Patterns for Built Products

Products built by the orchestrator are not static codebases — they come pre-wired with SAGE agentic patterns:

- **Monitor agent** — configured to watch logs, metrics, and CI/CD for the built product.
- **Analyst agent** — tuned with domain-specific prompts for the product's error patterns.
- **Scheduled tasks** — recurring health checks and log reviews declared in `tasks.yaml`.
- **Knowledge base** — seeded with the product's architecture decisions and design rationale.

These patterns mean the built product continues to improve through the standard SAGE lean loop after initial construction.
