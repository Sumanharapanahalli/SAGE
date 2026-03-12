# SAGE Framework — Setup Guide

Complete installation and configuration guide for the SAGE autonomous developer agent framework.

## Prerequisites

| Requirement | Version | Notes |
|:------------|:--------|:------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | Required for Gemini CLI and GitLab npm MCP |
| npm | 9+ | Bundled with Node.js |
| Gemini CLI | Latest | `npm install -g @google/gemini-cli` |
| J-Link SDK | Latest | Only required if using J-Link hardware |
| Git | Any | For GitLab integration |

---

## 1. Clone and Install Python Dependencies

```bash
cd C:\System-Team-repos
git clone <your-repo-url> SystemAutonomousAgent
cd SystemAutonomousAgent

# Recommended: create and activate virtual environment using Make (one-time)
make venv
# This creates .venv/ and installs all dependencies automatically.
# All subsequent make commands use .venv/Scripts/python (Windows) or .venv/bin/python (Linux/macOS).

# Alternative: manual virtual environment setup
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt

# For low-resource machines (no chromadb/sentence-transformers):
make install-minimal
# Or manually: pip install -r requirements-minimal.txt
```

---

## 2. Environment Variable Configuration

```bash
# Copy the template
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/Mac

# Edit .env with your credentials
notepad .env
```

All required variables are documented in `.env.example`. The key sections are:

- **Teams**: `TEAMS_TENANT_ID`, `TEAMS_CLIENT_ID`, `TEAMS_CLIENT_SECRET`, `TEAMS_INCOMING_WEBHOOK_URL`
- **GitLab**: `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECT_ID`
- **Metabase**: `METABASE_URL`, `METABASE_USERNAME`, `METABASE_PASSWORD`, `METABASE_ERROR_QUESTION_ID`
- **Spira**: `SPIRA_URL`, `SPIRA_USERNAME`, `SPIRA_API_KEY`, `SPIRA_PROJECT_ID`
- **Hardware**: `SERIAL_PORT`, `JLINK_DEVICE`

---

## 3. GitLab Access Token Setup

1. Log in to your GitLab instance
2. Go to **Profile** (top right) > **Edit Profile** > **Access Tokens**
3. Create a new token with these scopes: `api`, `read_user`, `read_repository`
4. Copy the token and set `GITLAB_TOKEN=glpat-...` in your `.env`

For a service account (recommended for production):
- Create a dedicated GitLab user (e.g. `sage-ai-bot`)
- Add it as a **Developer** or **Maintainer** on the relevant projects
- Create the access token from that user's profile

---

## 4. Microsoft Teams Setup (Azure AD App Registration)

### Reading Messages (Graph API)

1. Go to [Azure Portal](https://portal.azure.com) > **Azure Active Directory** > **App registrations**
2. Click **New registration**
   - Name: `SAGE[ai] Bot`
   - Supported account types: Single tenant (your org)
3. After creation, note the **Application (client) ID** → `TEAMS_CLIENT_ID`
4. Note the **Directory (tenant) ID** → `TEAMS_TENANT_ID`
5. Go to **Certificates & secrets** > **New client secret** → `TEAMS_CLIENT_SECRET`
6. Go to **API permissions** > **Add a permission** > **Microsoft Graph**:
   - `ChannelMessage.Read.All` (Application permission)
   - `Team.ReadBasic.All`
   - `Channel.ReadBasic.All`
7. Click **Grant admin consent** for your organization

### Sending Messages (Incoming Webhook)

1. In Microsoft Teams, go to your target channel
2. Click **...** > **Connectors** > search for **Incoming Webhook** > **Configure**
3. Give it a name (e.g. "SAGE[ai]"), optionally upload an icon
4. Click **Create** and copy the webhook URL → `TEAMS_INCOMING_WEBHOOK_URL`

### Finding Team and Channel IDs

```bash
# After setting TEAMS_TENANT_ID, TEAMS_CLIENT_ID, TEAMS_CLIENT_SECRET:
python -c "
from mcp_servers.teams_server import get_access_token, list_team_channels
print(get_access_token())
# Then use Graph Explorer: https://developer.microsoft.com/en-us/graph/graph-explorer
# GET https://graph.microsoft.com/v1.0/me/joinedTeams
"
```

---

## 5. Metabase Service Account Setup

1. Log in to Metabase as an admin
2. Go to **Admin** > **People** > **Add someone**
3. Create a service account (e.g. `sage-agent@yourcompany.com`)
4. Assign to a group with **view** access to the error dashboard/question
5. Find the error question ID from the URL when viewing the question: `/question/123` → ID is `123`
6. Set `METABASE_ERROR_QUESTION_ID=123` in `.env`

---

## 6. Spira API Key Setup

1. Log in to SpiraTeam/SpiraTest
2. Go to **My Profile** (top right) > **My API Keys**
3. Click **Add New Key** and copy it → `SPIRA_API_KEY`
4. Find your project ID from **Administration** > **Projects** or from the URL: `/ProjectId/1/`

---

## 7. J-Link SDK Installation

1. Download and install **J-Link Software Pack** from [SEGGER](https://www.segger.com/downloads/jlink/)
2. Add J-Link to system PATH (installer usually handles this)
3. Install the Python binding:
   ```bash
   pip install pylink-square
   ```
4. Verify:
   ```bash
   python -c "import pylink; j = pylink.JLink(); j.open(); print(j.product_name); j.close()"
   ```

---

## 8. Gemini CLI Setup

```bash
# Install Gemini CLI globally
npm install -g @google/gemini-cli

# Authenticate (opens browser)
gemini

# Verify
gemini --version
```

### Configure Gemini CLI MCP Servers

```bash
# Run the setup script (configures ~/.gemini/settings.json)
python scripts/setup_gemini_mcp.py
```

This adds all SAGE[ai] MCP servers (serial, J-Link, Metabase, Spira, Teams) to Gemini CLI's tool palette.

---

## 9. Claude Code MCP Setup

The `.mcp.json` file in the project root is automatically detected by Claude Code. All MCP servers are pre-configured. No additional setup required beyond installing dependencies.

To verify MCP servers are working (medtech solution):
```bash
# Test each server standalone (MCP servers live in solutions/medtech/mcp_servers/)
python solutions/medtech/mcp_servers/serial_port_server.py   # Lists COM ports
python solutions/medtech/mcp_servers/metabase_server.py      # Tests connection
python solutions/medtech/mcp_servers/spira_server.py         # Tests connection
python solutions/medtech/mcp_servers/teams_server.py         # Tests auth
```

---

## 10. Running SAGE

### Recommended: Make shortcuts (uses .venv automatically)

```bash
make run PROJECT=medtech       # FastAPI backend — medtech solution
make run PROJECT=poseengine    # FastAPI backend — poseengine solution
make run PROJECT=kappture      # FastAPI backend — kappture solution
make ui                        # React web UI at http://localhost:5173
make cli PROJECT=medtech       # Interactive CLI
make monitor PROJECT=kappture  # Background monitor daemon
make demo PROJECT=poseengine   # Quick demo
```

### Direct Python (requires venv activated or full path)

```bash
# Activate venv first (if not using make)
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

python src/main.py api --project medtech
# API docs at: http://localhost:8000/docs

python src/main.py cli --project poseengine
python src/main.py monitor --project kappture
python src/main.py demo --project medtech
```

---

## 11. Troubleshooting

### "Gemini CLI not found"
```bash
npm install -g @google/gemini-cli
# Ensure npm global bin is on PATH:
# Windows: %APPDATA%\npm
# Linux/Mac: $(npm root -g)/../bin
```

### "pyserial not installed"
```bash
pip install pyserial
```

### "J-Link DLL not found"
- Install J-Link Software Pack from SEGGER website
- Ensure `JLink_x64.dll` (Windows) or `libjlinkarm.so` (Linux) is on PATH

### "MSAL token acquisition failed"
- Verify `TEAMS_TENANT_ID`, `TEAMS_CLIENT_ID`, `TEAMS_CLIENT_SECRET` are correct
- Ensure admin consent was granted for Graph API permissions in Azure Portal
- Check if the client secret has expired

### "GitLab API 401 Unauthorized"
- Verify `GITLAB_TOKEN` is a valid Personal Access Token with `api` scope
- Check token expiry date in GitLab profile settings

### "Metabase authentication failed"
- Verify `METABASE_URL` does not have a trailing slash
- Test manually: `curl -X POST {METABASE_URL}/api/session -d '{"username":"...","password":"..."}'`

### Import errors on startup
```bash
# Recreate the virtual environment and reinstall
make venv

# Or manually reinstall into existing venv
.venv\Scripts\pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt      # Linux/Mac

# Check Python version (must be 3.10+, repo uses 3.12.9)
python --version
```

### ChromaDB embedding errors
```bash
# If sentence-transformers fails to download models (offline environment):
pip install sentence-transformers
# Pre-download the model on a connected machine:
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```
