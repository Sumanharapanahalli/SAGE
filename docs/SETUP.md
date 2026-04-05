# SAGE Framework — Setup Guide

> **New to SAGE?** Read [GETTING_STARTED.md](../GETTING_STARTED.md) first. This document covers the full installation including optional integrations. You do not need any of the integrations to get started.

---

## Core Setup (Required for Everyone)

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | `python --version` to check |
| Node.js | 18+ | Required for Gemini CLI / Claude Code CLI |
| npm | 9+ | Bundled with Node.js |

### Install

```bash
# Clone the repo
git clone <your-repo-url>
cd sage

# Create virtual environment and install all dependencies (one-time)
make venv

# Alternative: manual setup
python -m venv .venv
source .venv/bin/activate       # Linux/Mac
# .venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Install web UI dependencies
make install-ui
```

For machines with under 8 GB RAM:
```bash
make venv-minimal    # Skips ChromaDB and sentence-transformers
```

### Run the Starter Solution

```bash
make run PROJECT=starter    # No integrations needed
make ui                     # Web UI at http://localhost:5173
```

Verify:
```bash
curl http://localhost:8000/health
```

### LLM Provider Setup (Pick One)

All options except `claude` work without an API key.

**Gemini CLI (recommended default):**
```bash
npm install -g @google/gemini-cli
gemini    # One-time browser OAuth login
```

**Claude Code CLI:**
```bash
npm install -g @anthropic-ai/claude-code
claude    # One-time Anthropic auth
```

**Ollama (fully offline, no login):**
```bash
# Install from https://ollama.com
ollama serve
ollama pull llama3.2
```
Then set in `config/config.yaml`:
```yaml
llm:
  provider: "ollama"
  ollama_model: "llama3.2"
```

**Claude API (only option requiring an API key):**
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
Then set `provider: "claude"` in `config/config.yaml`.

---

## Make Targets Reference

### Setup

| Target | Description |
|---|---|
| `make venv` | Create `.venv` and install all dependencies |
| `make venv-minimal` | Create `.venv` with minimal deps (low-RAM machines) |
| `make install-ui` | Install Node.js dependencies for the web UI |
| `make install` | Install Python deps into current active env |
| `make install-dev` | Install Python deps + pytest/coverage tools |

### Run

| Target | Description |
|---|---|
| `make run [PROJECT=starter]` | Start FastAPI backend on `:8000` |
| `make ui` | Start React web UI on `:5173` |
| `make cli [PROJECT=...]` | Interactive CLI mode |
| `make monitor [PROJECT=...]` | Background monitor daemon |
| `make demo [PROJECT=...]` | Demo mode |

### Test

| Target | Description |
|---|---|
| `make test` | Framework unit tests |
| `make test-api` | API endpoint tests only |
| `make test-all` | Framework + medtech solution tests |
| `make test-solution PROJECT=X` | Any solution's tests |
| `make test-medtech` | medtech solution tests |
| `make test-medtech-team` | medtech_team solution tests |
| `make test-meditation-app` | meditation_app solution tests |
| `make test-four-in-a-line` | four_in_a_line solution tests |
| `make test-mcp` | MCP server tests (needs fastmcp) |
| `make test-integration` | Integration tests (needs live services) |
| `make test-compliance` | IQ/OQ/PQ validation protocol |

### Deploy

| Target | Description |
|---|---|
| `make docker-up [PROJECT=...]` | Start via Docker Compose |
| `make docker-up-d [PROJECT=...]` | Start via Docker Compose (detached) |
| `make docker-down` | Stop Docker Compose |

### Utilities

| Target | Description |
|---|---|
| `make list-solutions` | List all solution directories |
| `make doctor` | Run health checks |
| `make clean` | Remove `__pycache__` and `.pyc` files |
| `make help` | Show all available targets |

---

## Optional Integrations

The sections below are only needed if you want to connect SAGE to external systems. None of them are required to run the framework.

Configure integrations in a `.env` file at the repo root:
```bash
cp .env.example .env
# Edit .env — only fill in what you use
```

---

### GitLab

Used for: merge request creation, code review, pipeline status.

1. Go to GitLab -> Profile -> Access Tokens
2. Create a token with scopes: `api`, `read_user`, `read_repository`
3. Add to `.env`:

```env
GITLAB_URL=https://gitlab.yourcompany.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxx
GITLAB_PROJECT_ID=123
```

For a service account (recommended for production): create a dedicated GitLab user, add it as Developer or Maintainer on relevant projects, and create the token from that account.

---

### Slack

Used for: two-way proposal approval (Block Kit buttons in a Slack channel).

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable **Incoming Webhooks** and **Interactivity**
3. Add Bot Token Scopes: `chat:write`, `channels:read`
4. Set the **Request URL** for interactivity to: `https://your-sage-host/webhook/slack`
5. Add to `.env`:

```env
SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxx
SLACK_SIGNING_SECRET=xxxxxxxxxxxxxxxx
SLACK_CHANNEL_ID=C0123456789
```

---

### n8n Webhook

Used for: receiving events from n8n automation workflows and routing them to SAGE agents.

SAGE receives POST requests at `/webhook/n8n`. Secure with a shared secret:

```env
N8N_WEBHOOK_SECRET=your-shared-secret
```

In your n8n workflow, add a Header Auth credential with `X-SAGE-Signature` set to the HMAC-SHA256 signature of the payload body using this secret.

---

### Microsoft Teams

Used for: reading channel messages, sending notifications and approval requests.

1. Go to [Azure Portal](https://portal.azure.com) -> Azure Active Directory -> App registrations -> New registration
2. Note the **Application (client) ID** and **Directory (tenant) ID**
3. Create a client secret under Certificates & secrets
4. Add Microsoft Graph API permissions: `ChannelMessage.Read.All`, `Team.ReadBasic.All`, `Channel.ReadBasic.All` (Application permissions) and grant admin consent
5. For sending messages: in Teams, go to a channel -> ... -> Connectors -> Incoming Webhook -> Configure

```env
TEAMS_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TEAMS_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TEAMS_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TEAMS_TEAM_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
TEAMS_CHANNEL_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TEAMS_INCOMING_WEBHOOK_URL=https://yourcompany.webhook.office.com/...
```

---

### Metabase

Used for: polling error dashboards and routing anomalies to the analyst agent.

1. Log in to Metabase as admin
2. Create a service account with view access to your error dashboard
3. Find the question ID from the URL when viewing it: `/question/123` -> ID is `123`

```env
METABASE_URL=https://metabase.yourcompany.com
METABASE_USERNAME=sage-agent@yourcompany.com
METABASE_PASSWORD=xxxxxxxxxxxx
METABASE_ERROR_QUESTION_ID=123
```

---

### SpiraTeam

Used for: creating and reading incidents in SpiraTeam / SpiraTest.

1. Log in to SpiraTeam -> My Profile -> My API Keys -> Add New Key
2. Find your project ID from Administration -> Projects

```env
SPIRA_URL=https://spira.yourcompany.com
SPIRA_USERNAME=your-username
SPIRA_API_KEY=xxxxxxxxxxxxxxxxxxxx
SPIRA_PROJECT_ID=1
```

---

### Temporal (Durable Workflows)

Used for: running workflows that survive server restarts and need automatic retry.

1. Install the Temporal server: [docs.temporal.io](https://docs.temporal.io/self-hosted-guide)
2. Or use Temporal Cloud: [cloud.temporal.io](https://cloud.temporal.io)

```env
TEMPORAL_HOST=localhost:7233
```

If `TEMPORAL_HOST` is not set or the server is unreachable, SAGE automatically falls back to LangGraph for workflow execution.

---

### J-Link Hardware Debugger

Used for: flashing firmware and reading memory on embedded targets (medtech solution only).

1. Download and install **J-Link Software Pack** from [SEGGER](https://www.segger.com/downloads/jlink/)
2. Install the Python binding:

```bash
pip install pylink-square
```

```env
JLINK_DEVICE=STM32F4    # Your target MCU name
SERIAL_PORT=COM3         # Serial port for UART output (Windows example)
```

---

### Composio

Used for: multi-tenant tool integrations (500+ pre-built tools with per-user OAuth).

Connect via the API:
```bash
curl -X POST http://localhost:8000/integrations/composio/connect \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-composio-key"}'
```

Check status: `GET /integrations/composio/status`

---

## Environment Variable Reference

| Variable | Service | Required for |
|---|---|---|
| `GITLAB_URL` | GitLab | MR operations |
| `GITLAB_TOKEN` | GitLab | Personal Access Token |
| `GITLAB_PROJECT_ID` | GitLab | Default project ID |
| `SLACK_BOT_TOKEN` | Slack | Sending proposals |
| `SLACK_SIGNING_SECRET` | Slack | Verifying callbacks |
| `SLACK_CHANNEL_ID` | Slack | Target channel |
| `N8N_WEBHOOK_SECRET` | n8n | Webhook HMAC verification |
| `TEAMS_TENANT_ID` | Azure AD | Teams integration |
| `TEAMS_CLIENT_ID` | Azure AD | Teams integration |
| `TEAMS_CLIENT_SECRET` | Azure AD | Teams integration |
| `TEAMS_TEAM_ID` | Teams | Channel monitoring |
| `TEAMS_CHANNEL_ID` | Teams | Channel monitoring |
| `TEAMS_INCOMING_WEBHOOK_URL` | Teams | Sending notifications |
| `METABASE_URL` | Metabase | Dashboard polling |
| `METABASE_USERNAME` | Metabase | Service account |
| `METABASE_PASSWORD` | Metabase | Service account |
| `METABASE_ERROR_QUESTION_ID` | Metabase | Error query card ID |
| `SPIRA_URL` | SpiraTeam | Incident management |
| `SPIRA_USERNAME` | SpiraTeam | Login username |
| `SPIRA_API_KEY` | SpiraTeam | API key |
| `SPIRA_PROJECT_ID` | SpiraTeam | Default project ID |
| `TEMPORAL_HOST` | Temporal | Durable workflows |
| `SERIAL_PORT` | Hardware | COM port (e.g. COM3) |
| `JLINK_DEVICE` | Hardware | Target MCU name |
| `ANTHROPIC_API_KEY` | Claude API | Only if using `provider: "claude"` |
| `LLM_PROVIDER` | Framework | Override config.yaml provider at runtime |
| `SAGE_PROJECT` | Framework | Active project (overrides --project flag) |
| `SAGE_SOLUTIONS_DIR` | Framework | Path to solutions outside the repo root |
| `SAGE_MINIMAL` | Framework | Set to `1` for minimal mode (no ChromaDB) |

---

## Troubleshooting

**"Gemini CLI not found"**
```bash
npm install -g @google/gemini-cli
# Make sure npm global bin is on PATH:
# Windows: %APPDATA%\npm
# Linux/Mac: $(npm root -g)/../bin
```

**Import errors on startup**
```bash
make venv    # Recreate the virtual environment from scratch
```

**"No module named chromadb"**
```bash
# If you used make venv-minimal and want full vector search:
.venv/bin/pip install chromadb sentence-transformers
```

**Web UI shows blank or error on a page**

Check which modules are in `active_modules` in your `project.yaml`. If `developer` is listed but GitLab is not configured, that page will error. Remove the module from `active_modules` or configure the integration.

**LLM calls timing out**
- Gemini CLI: run `gemini` in a terminal to re-authenticate
- Ollama: check `ollama serve` is running and the model is pulled (`ollama list`)
- Check `config/config.yaml` — the `provider` key must match what is running

**ChromaDB embedding errors in offline environments**
```bash
# Pre-download the model on a connected machine first:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# The model is cached and works offline after this
```

---

## Desktop Application (Tauri)

SAGE includes a native desktop wrapper built on Tauri v2 for Windows, macOS, and Linux.

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Rust | 1.77.2+ | Install via [rustup.rs](https://rustup.rs/) |
| Platform deps | — | See [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) |

On **Windows**: Visual Studio C++ Build Tools + WebView2 (pre-installed on Windows 10/11).
On **Linux**: `sudo apt install libwebkit2gtk-4.1-dev build-essential libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev`.
On **macOS**: Xcode Command Line Tools (`xcode-select --install`).

### Build

```bash
cd web
npm install                # Install JS + Tauri CLI deps
npm run tauri:dev          # Development mode with hot reload
npm run tauri:build        # Production build → platform installer
```

### Output Locations

| Platform | Format | Path |
|---|---|---|
| Windows | `.msi` + `.exe` | `web/src-tauri/target/release/bundle/msi/` |
| macOS | `.dmg` | `web/src-tauri/target/release/bundle/dmg/` |
| Linux | `.deb` / `.AppImage` | `web/src-tauri/target/release/bundle/deb/` |

The desktop app wraps the web UI and connects to the backend at `http://localhost:8000`. Start the backend separately via `make run PROJECT=starter` or `./start.sh`.
