# SAGE Framework — User Guide

> Version 2.1.0 | Last updated: 2026-03-12

This guide covers everything needed to install, configure, run, and operate the SAGE Framework from day to day. It assumes no prior knowledge of the codebase.

---

## Table of Contents

1. [Installation](#1-installation)
2. [Configuration](#2-configuration)
3. [Running Each Project](#3-running-each-project)
4. [Using the Web UI](#4-using-the-web-ui)
5. [Human-in-the-Loop Workflow](#5-human-in-the-loop-workflow)
6. [Feature Request System](#6-feature-request-system)
7. [Adding a New Project](#7-adding-a-new-project)
8. [Running Tests](#8-running-tests)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Installation

### 1.1 Full Installation

This installs all features including ChromaDB RAG memory, sentence-transformers embeddings, and all integration libraries.

**Prerequisites:**

| Requirement | Minimum Version | Check |
|-------------|----------------|-------|
| Python | 3.10 | `python --version` |
| Node.js | 18 | `node --version` |
| npm | 9 | `npm --version` |
| Gemini CLI | Latest | `gemini --version` |

**Install Gemini CLI (first time only):**

```bash
npm install -g @google/gemini-cli

# Authenticate (opens browser — no API key needed)
gemini
```

**Install SAGE:**

```bash
# Clone the repository
git clone <your-repo-url> SystemAutonomousAgent
cd SystemAutonomousAgent

# Create virtual environment and install all Python dependencies (one-time)
make venv
# This creates .venv/ using Python 3.12.9 and installs requirements.txt automatically.
# All make commands use .venv/Scripts/python (Windows) or .venv/bin/python (Linux/macOS).

# Install web UI dependencies
make install-ui
```

### 1.2 Minimal Installation (Low-Resource Machines)

Use this on laptops without GPU, or when ChromaDB is not needed. The framework falls back to in-memory embeddings (no RAG persistence between runs).

```bash
make venv            # Create .venv first if not already done
make install-minimal
# Installs: pyyaml, pydantic, fastapi, uvicorn, python-dotenv, requests, httpx
# Skips:    chromadb, sentence-transformers, llama-cpp-python

make install-ui      # Install web UI dependencies
```

The system is fully functional in minimal mode for the Analyst, Developer, Planner, and Monitor agents. The only difference is that correction feedback will not persist across process restarts.

### 1.3 Local LLM (Offline / Air-Gapped)

To run fully offline without the Gemini CLI:

```bash
# Install llama-cpp-python (CPU-only)
pip install llama-cpp-python

# Or with CUDA GPU support (requires CUDA toolkit installed)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python

# Download a GGUF model (run this on a connected machine, then copy)
# Recommended: Phi-3.5-mini-instruct Q4 (~2.2 GB)
# Place the file at:
data/models/Phi-3-mini-4k-instruct-q4.gguf
```

Then edit `config/config.yaml`:

```yaml
llm:
  provider: "local"
  model_path: "./data/models/Phi-3-mini-4k-instruct-q4.gguf"
```

---

## 2. Configuration

### 2.1 Environment Variables (`.env`)

Copy the template and fill in the credentials for the integrations you use. All values are optional — features simply degrade gracefully if credentials are not set.

```bash
cp .env.example .env
# Edit .env with your values
```

**Minimum viable `.env` for each project:**

For **medtech** (GitLab + Teams + Metabase + Spira):

```env
GITLAB_URL=https://gitlab.yourcompany.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx
GITLAB_PROJECT_ID=42
TEAMS_INCOMING_WEBHOOK_URL=https://yourorg.webhook.office.com/...
METABASE_URL=http://metabase.yourcompany.com
METABASE_USERNAME=sage-agent@yourcompany.com
METABASE_PASSWORD=yourpassword
METABASE_ERROR_QUESTION_ID=123
SPIRA_URL=https://spira.yourcompany.com
SPIRA_USERNAME=your.username
SPIRA_API_KEY=your-api-key
SPIRA_PROJECT_ID=1
```

For **poseengine** (GitLab/GitHub + Teams):

```env
GITLAB_URL=https://gitlab.yourcompany.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx
GITLAB_PROJECT_ID=55
TEAMS_INCOMING_WEBHOOK_URL=https://yourorg.webhook.office.com/...
```

For **kappture** (GitLab + Teams — camera monitoring uses Prometheus/Grafana URLs in config):

```env
GITLAB_URL=https://gitlab.yourcompany.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxx
GITLAB_PROJECT_ID=77
TEAMS_INCOMING_WEBHOOK_URL=https://yourorg.webhook.office.com/...
```

### 2.2 `config/config.yaml`

This file sets the base LLM configuration and integration URLs. Values can use `${ENV_VAR}` interpolation.

Key settings:

```yaml
llm:
  provider: "gemini"              # or "local"
  gemini_model: "gemini-2.5-flash"
  timeout: 120                    # seconds to wait for Gemini CLI

memory:
  vector_db_path: "./data/chroma_db"
  audit_db_path: "./data/audit_log.db"

system:
  log_level: "INFO"
  max_concurrent_tasks: 1         # do not change — single-lane by design
```

### 2.3 Project Selection

The active project controls which prompts, task types, and UI modules are used. Select it in one of these ways (highest to lowest priority):

```bash
# 1. CLI flag
python src/main.py api --project kappture

# 2. Environment variable
SAGE_PROJECT=poseengine python src/main.py api

# 3. Makefile
make run PROJECT=kappture

# 4. Default (if none specified)
# Falls back to: medtech
```

---

## 3. Running Each Project

### 3.1 Starting the Backend

```bash
# Recommended: use make (automatically uses .venv)
make run PROJECT=medtech       # medical device manufacturing
make run PROJECT=poseengine    # CV/ML + Flutter
make run PROJECT=kappture      # human tracking platform
# API: http://localhost:8000 | Docs: http://localhost:8000/docs

# Or direct Python (requires venv activated)
python src/main.py api --project medtech
```

The backend starts with the selected project's prompts and task types loaded. You will see a startup log message confirming which project and LLM provider is active:

```
INFO     LLM Gateway active: GeminiCLI (gemini-2.5-flash)
INFO     Project loaded: Kappture Human Tracking (kappture v1.0.0)
INFO     Task queue SQLite storage initialised at ./data/audit_log.db
```

### 3.2 Starting the Web UI

In a separate terminal:

```bash
make ui
# Open http://localhost:5173

# Or directly:
cd web && npm run dev
```

The web UI connects to whichever project is running on port 8000. It fetches project metadata on load via `GET /config/project` and adjusts page titles, labels, and task types automatically.

### 3.3 Running as a Background Monitor

The monitor mode starts background polling threads that watch your configured event sources (Teams, Metabase, GitLab CI/CD, etc.) and automatically queue tasks when events are detected.

```bash
# Monitor with API server also running
python src/main.py monitor --project medtech

# Or start API + monitor together (see main.py --help)
```

### 3.4 Docker Deployment

```bash
# Full stack: backend + frontend
SAGE_PROJECT=kappture docker-compose up --build

# Backend only
SAGE_PROJECT=poseengine docker-compose up --build backend

# Stop
docker-compose down
```

When running in Docker, the frontend is served by nginx on port 3000 and the backend on port 8000. Both services are health-checked and restart automatically on failure.

---

## 4. Using the Web UI

Open `http://localhost:5173` in your browser. The sidebar navigation contains six pages.

### 4.1 Dashboard

The Dashboard is the default landing page. It shows:

- **System Health Card** — current status of the backend, LLM provider, active project name, and configured integrations (green/red indicators for GitLab, Teams, Metabase, Spira).
- **Active Alerts Panel** — pending proposals awaiting human review. Click any alert to jump to the Analyst page.
- **Error Trend Chart** — a line chart of analysis events over the last 7 days, pulled from the audit log.

The Dashboard auto-refreshes every 30 seconds via TanStack Query.

### 4.2 Analyst Page

The Analyst page is where you submit logs, metrics, or error text for AI analysis.

**How to use it:**

1. Paste a log entry or error text into the input field. The label adapts to the active project (e.g. "Training / inference log" for poseengine, "Tracking log, accuracy report, or camera error" for kappture).
2. Click **Analyze**.
3. The Analyst Agent runs RAG lookup + LLM inference. A proposal card appears showing:
   - **Severity** badge (RED / AMBER / GREEN / UNKNOWN)
   - **Root Cause Hypothesis**
   - **Recommended Action**
   - **Trace ID** (UUID for audit linking)
4. Use the approval buttons (see Section 5) to respond.

### 4.3 Developer Page

The Developer page manages GitLab merge request operations.

**Tabs:**

- **Open MRs** — lists all open MRs for your configured GitLab project. Each row shows title, author, source branch, pipeline status, and a Trace ID from any prior AI review.
- **Review MR** — enter a project ID and MR IID to trigger an AI review via the ReAct loop. The review result shows summary, per-line issues, suggestions, and an overall approved/rejected verdict. Every review requires human approval before action.
- **Create MR** — enter a project ID and issue IID. The Developer Agent fetches the issue, generates an AI-drafted MR title and description, and creates the MR in GitLab. The MR URL is returned.

### 4.4 Monitor Page

The Monitor page shows the real-time status of the Monitor Agent's polling threads.

- **Last Poll Time** for each source (Teams, Metabase, GitLab, or project-specific sources).
- **Events Detected** count for the current session.
- **Current Queue Depth** — how many tasks are waiting for the TaskWorker.
- **Queue Status** — a table of recent tasks showing type, status, creation time, and result.

The Monitor page auto-refreshes every 30 seconds.

### 4.5 Audit Log Page

The Audit Log page provides a searchable, paginated view of the immutable compliance audit trail.

- Every AI analysis, approval, rejection, MR review, MR creation, webhook receipt, and feature request is recorded here.
- Each row shows: timestamp, actor, action type, input context (truncated), and a Trace ID.
- Click any row to open the **Trace Detail Modal**, which shows the full input context, output content, and metadata for that event.
- Use the pagination controls to navigate the full log history.

The audit log database (`data/audit_log.db`) is never modified — records are insert-only. For compliance-sensitive projects (medtech), this log must be retained for 7+ years.

### 4.6 Improvements Page

The Improvements page is the hub for the ModuleWrapper self-improvement system.

- Lists all pending, approved, in-planning, and completed feature requests submitted from any page.
- Filter by module or status using the dropdowns.
- Click **Generate Plan** on any pending request to trigger the PlannerAgent to auto-decompose the request into implementation tasks.
- Click **Approve** / **Reject** to update the request status (reviewer workflow).

Feature requests can also be submitted directly from within any page — see Section 6.

---

## 5. Human-in-the-Loop Workflow

Human approval is mandatory for every AI proposal. The system will not execute any action without it.

### 5.1 Approving a Proposal (Web UI)

On the **Analyst page**, after an analysis appears:

1. Read the severity, root cause hypothesis, and recommended action.
2. If you agree, click the green **Approve** button.
   - The backend calls `POST /approve/{trace_id}`.
   - The approval is recorded in the audit log.
   - The action may now be executed (e.g. Teams notification sent, MR created).
3. If the proposal is correct but you want to add context, click **Approve** — then follow up with a Spira incident or Teams message manually.

### 5.2 Rejecting a Proposal with Feedback

If the AI is wrong:

1. Click the red **Reject** button.
2. A text field appears: type your correction. Be specific — for example: "This is not a firmware error, it is a sensor calibration drift. Check sensor_cal.c line 204."
3. Click **Submit Feedback**.
   - The backend calls `POST /reject/{trace_id}` with your feedback.
   - Your correction is embedded and stored in ChromaDB.
   - The next time a similar event appears, the RAG system retrieves your correction and the AI prompt includes it as context.

### 5.3 Approving via REST API

If you are integrating with an external workflow tool:

```bash
# Approve
curl -X POST http://localhost:8000/approve/a1b2c3d4-...

# Reject with feedback
curl -X POST http://localhost:8000/reject/a1b2c3d4-... \
  -H "Content-Type: application/json" \
  -d '{"feedback": "The real cause is a calibration drift in sensor_cal.c"}'
```

### 5.4 Teams Adaptive Card Approval

When the Teams Bot is configured and a proposal is posted as an adaptive card to your Teams channel, the Approve/Reject buttons on the card call back to `POST /webhook/teams`. The webhook handler processes the response and logs it to the audit trail.

---

## 6. Feature Request System

Every page in the web UI has a built-in improvement request system, powered by the ModuleWrapper component.

### 6.1 Submitting a Request

1. Navigate to any page (e.g. the Analyst page).
2. Look at the top-left corner of the page — you will see a small badge showing the module name and version (e.g. `Log Analyzer v1.2.0`).
3. Click the **Request Improvement** button (amber, top-right of the module strip).
4. The improvement request panel slides in. It shows:
   - The module name and description.
   - A list of **Improvement Ideas** (pre-seeded hints from the module registry) — click any hint to pre-fill the request form.
5. Fill in the title, description, and priority (Low / Medium / High / Critical).
6. Enter your name in the "Requested by" field.
7. Click **Submit Request**.

The request is stored in `data/audit_log.db` (table `feature_requests`) and appears on the **Improvements page**.

### 6.2 Viewing the Info Panel

Click the **ⓘ** icon (next to the module name badge) to toggle the info panel. This shows:

- The module's current feature list.
- Improvement ideas — clicking any idea opens the request panel with it pre-filled.

### 6.3 What Happens After Submission

1. The request appears on the **Improvements page** with status `pending`.
2. A reviewer clicks **Generate Plan** to trigger the PlannerAgent, which auto-decomposes the request into implementation tasks.
3. The reviewer clicks **Approve** to promote the request to `approved` (or `Reject` to close it).
4. Engineering implements the changes and updates the status to `completed`.

---

## 7. Adding a New Solution

SAGE makes it straightforward to onboard any new software domain. You need three YAML files — no Python code changes are required.

See the full step-by-step guide in `docs/ADDING_A_PROJECT.md`.

The quick summary:

```
solutions/
└── mysolution/
    ├── project.yaml    ← identity, compliance standards, active modules
    ├── prompts.yaml    ← analyst, developer, planner, monitor system prompts
    └── tasks.yaml      ← task types, descriptions, payload schemas
```

Test your new solution:

```bash
make run PROJECT=mysolution
curl http://localhost:8000/config/project
```

---

## 8. Running Tests

```bash
# Framework tests (216 tests — unit, fast, no external services needed)
make test

# medtech solution tests (32 tests — e2e, IQ/OQ/PQ validation)
make test-medtech

# All tests combined (248 tests)
make test-all

# Nano-module tests only (119 tests, instant)
pytest tests/modules/ -v

# Compliance/validation tests (IQ/OQ/PQ — for QMS sign-off)
pytest -m compliance --tb=long -v
# or:
make test-compliance

# API tests only
make test-api

# Specific test file
pytest tests/test_analyst_agent.py -v

# With coverage
pytest -m unit --cov=src --cov-report=term-missing
```

**Test structure:**

| Suite | Location | Count | Speed | Needs services? |
|-------|----------|-------|-------|-----------------|
| Framework unit tests | `tests/` | 216 | Fast | No |
| Nano-module tests | `tests/modules/` | 119 (subset of 216) | Instant | No |
| medtech solution tests | `solutions/medtech/tests/` | 32 | Medium | Partial |
| MCP server tests | `solutions/medtech/tests/mcp/` | — | Fast | No (mocked) |
| Integration tests | `solutions/medtech/tests/integration/` | — | Slow | Yes (credentials) |
| IQ/OQ/PQ validation | `solutions/medtech/tests/validation/` | — | Medium | No |

> **MCP tests** require `fastmcp`: `pip install fastmcp` (or add to `.venv`).
> **Integration tests** require a configured `.env` with real service credentials and are auto-skipped when variables are absent.

---

## 9. Troubleshooting

### "Gemini CLI not found"

```bash
npm install -g @google/gemini-cli

# Ensure npm global bin is on PATH:
# Windows: add %APPDATA%\npm to PATH
# Linux/Mac: run: export PATH="$(npm root -g)/../bin:$PATH"

# Verify
gemini --version
```

### "Gemini CLI timed out after 120s"

- Check your internet connection.
- Re-authenticate: run `gemini` in a terminal and complete the browser OAuth flow.
- Increase the timeout in `config/config.yaml`: `timeout: 180`

### "Local model not loaded" / "GGUF file not found"

```bash
# Check config.yaml model_path
cat config/config.yaml | grep model_path

# Verify the file exists
ls data/models/
# Expected: Phi-3-mini-4k-instruct-q4.gguf (or similar)
```

### "ChromaDB embedding error" / "sentence-transformers fails"

```bash
# Reinstall sentence-transformers
pip install --upgrade sentence-transformers

# Pre-download the embedding model (needed if running offline later)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

If you do not need persistent RAG memory, use the minimal install (`make install-minimal`) which skips ChromaDB entirely.

### "GitLab API 401 Unauthorized"

- Verify `GITLAB_TOKEN` in `.env` is a valid Personal Access Token with `api` scope.
- Check the token has not expired: GitLab Profile → Access Tokens → check expiry date.
- Ensure `GITLAB_URL` does not have a trailing slash.

### "MSAL token acquisition failed" (Teams)

- Verify all three Teams Azure AD variables: `TEAMS_TENANT_ID`, `TEAMS_CLIENT_ID`, `TEAMS_CLIENT_SECRET`.
- In Azure Portal: App registrations → your app → API permissions → confirm admin consent was granted for `ChannelMessage.Read.All`, `Team.ReadBasic.All`, `Channel.ReadBasic.All`.
- Check the client secret expiry date in Azure Portal → Certificates & secrets.

### "Metabase authentication failed"

- Ensure `METABASE_URL` has no trailing slash.
- Test manually:
  ```bash
  curl -X POST ${METABASE_URL}/api/session \
    -H "Content-Type: application/json" \
    -d '{"username":"your@email.com","password":"yourpassword"}'
  ```

### Web UI shows "Failed to fetch" / blank dashboard

- Confirm the backend is running: `curl http://localhost:8000/health`
- Check there are no CORS errors in browser DevTools (F12 → Network).
- Ensure the Vite proxy target in `web/vite.config.ts` points to `http://localhost:8000`.

### Import errors on startup

```bash
# Check Python version
python --version    # Must be 3.10+

# Reinstall all dependencies
pip install -r requirements.txt

# Verify critical packages
python -c "import fastapi, uvicorn, yaml, chromadb; print('OK')"
```

### "J-Link DLL not found"

- Download and install J-Link Software Pack from [SEGGER](https://www.segger.com/downloads/jlink/).
- On Windows: ensure `JLink_x64.dll` is on system PATH.
- On Linux: ensure `libjlinkarm.so` is accessible.
- Verify: `python -c "import pylink; j = pylink.JLink(); print(j.product_name)"`

### Tasks not processing (queue stuck)

The TaskWorker runs as a daemon thread. Check that:

1. The backend is running in `api` mode (not just imported as a module).
2. No exception is silently killing the worker thread — check the backend logs.
3. The `data/audit_log.db` file is not locked by another process.

```bash
# Check for any pending tasks
curl http://localhost:8000/monitor/status
```

### Resetting the audit database (development only)

```bash
# Stop the backend first
# Delete the database to start fresh
rm data/audit_log.db
rm -rf data/chroma_db/

# Restart — tables are recreated automatically
python src/main.py api --project medtech
```

**Never do this in a production or regulated environment.** The audit log is a compliance artifact.
