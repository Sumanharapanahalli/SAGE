# SAGE Framework — User Guide

> Version 3.1.0 | Last updated: 2026-03-15

This guide covers everything needed to install, configure, run, and operate the SAGE Framework from day to day. It assumes no prior knowledge of the codebase.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Configuration](#2-configuration)
3. [Running a Solution](#3-running-a-solution)
4. [Using the Web UI](#4-using-the-web-ui)
5. [Human-in-the-Loop Workflow](#5-human-in-the-loop-workflow)
6. [Feature Request System](#6-feature-request-system)
7. [Adding a New Solution](#7-adding-a-new-solution)
8. [Solution Theming](#8-solution-theming)
9. [Running Tests](#9-running-tests)
10. [Troubleshooting](#10-troubleshooting)

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

### 3.1 Included Example Solutions

| Solution | Domain | Good for learning |
|---------|--------|------------------|
| `starter` | Generic template | First run, any domain |
| `meditation_app` | Flutter mobile + Node.js | Consumer app, GDPR |
| `four_in_a_line` | Casual game | Game studio, COPPA |
| `medtech_team` | Medical device | Regulated, ISO 13485 |

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

Open `http://localhost:5173`. The sidebar shows pages according to your solution's `active_modules` list in `project.yaml`. The header includes a **solution switcher** dropdown (click the solution name) and an online/offline indicator showing the active LLM provider.

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

## 5. Human-in-the-Loop Workflow

Human approval is mandatory for every AI proposal. The system will not execute any action without it.

### 5.1 Approving a Proposal (Web UI)

1. Read the severity, root cause hypothesis, and recommended action on the Analyst page.
2. Click **Approve** → `POST /approve/{trace_id}` is called → logged to audit trail.

### 5.2 Rejecting with Feedback

1. Click **Reject**.
2. Type your correction — be specific: "This is not a network error, it is a database connection pool exhaustion. Check db_pool.py line 87."
3. Click **Submit Feedback** → `POST /reject/{trace_id}` → your correction is embedded into ChromaDB.
4. The next similar event retrieves your correction as RAG context — the AI improves.

### 5.3 Approving via REST API

```bash
# Approve
curl -X POST http://localhost:8000/approve/a1b2c3d4-...

# Reject with feedback
curl -X POST http://localhost:8000/reject/a1b2c3d4-... \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Root cause is db pool exhaustion, not network timeout"}'
```

### 5.4 Slack Block Kit Approval

When `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are configured, proposals are posted to your Slack channel as interactive messages. Click Approve/Reject directly in Slack — the callback hits `POST /webhook/slack`.

### 5.5 Teams Adaptive Card Approval

When Teams integration is configured, proposals are posted as adaptive cards. Approve/Reject buttons call back to `POST /webhook/teams`.

---

## 6. Feature Request System

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

## 7. Adding a New Solution

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

## 8. Solution Theming

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

## 9. Running Tests

```bash
# Framework tests (383+ tests — fast, no external services)
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

## 10. Troubleshooting

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
