# Getting Started with SAGE

> Zero integrations required. No API keys. Running in under 15 minutes.

SAGE is a framework for building AI agent systems for any domain. You describe what your project is in three YAML files and agents start working immediately — analyzing logs, reviewing code, monitoring systems, and proposing actions for human approval.

This guide gets you from nothing to a running agent with no external dependencies.

---

## What You Need

| Requirement | Version | Check |
|---|---|---|
| Python | 3.10 or higher | `python --version` |
| Node.js | 18 or higher | `node --version` |

That is all. No API keys, no cloud accounts, no hardware, no external services.

For the LLM, you need **one** of these (pick whichever is easiest):

| Option | Setup | Internet? |
|---|---|---|
| **Gemini CLI** (recommended) | `npm install -g @google/gemini-cli` then `gemini` (one-time browser login) | Yes |
| **Claude Code CLI** | `npm install -g @anthropic-ai/claude-code` then `claude` (one-time login) | Yes |
| **Ollama** (fully offline) | Install from [ollama.com](https://ollama.com) → `ollama serve` → `ollama pull llama3.2` | No |

---

## Step 1 — Install

```bash
# Clone the repo
git clone https://github.com/your-org/sage
cd sage

# Create the Python virtual environment and install dependencies (one-time)
make venv
```

That is the only install step. The `make venv` command creates `.venv/` and installs everything.

If you are on a low-memory machine (under 8 GB RAM):
```bash
make venv-minimal   # Skips ChromaDB and sentence-transformers — still fully functional
```

---

## Step 2 — Run the Starter Solution

The `starter` solution is a generic template that works for any domain out of the box. Run it as-is first, then customize it for your project.

```bash
make run PROJECT=starter
```

You should see:
```
INFO:     SAGE Framework starting — project: starter
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Leave this running and open a second terminal.

---

## Step 3 — Start the Web UI

```bash
make ui
```

Open your browser at **http://localhost:5173**

You will see the SAGE dashboard with the starter project loaded. Every page in the UI talks to the backend you just started.

---

## Step 4 — Send Your First Request

From the **Analyst** page, paste any log entry or error message. For example:

```
TypeError: Cannot read properties of undefined (reading 'user_id') at checkout.js:42
```

Click **Analyze**. The agent will:
1. Search its memory for similar past incidents (empty on first run)
2. Send the log to your LLM
3. Return a severity (RED / AMBER / GREEN), root cause hypothesis, and recommended action

At the bottom you will see **Approve** and **Reject** buttons. This is the human approval gate — every agent proposal waits here. If you reject, you can add a comment explaining why. That comment is stored in the vector memory and improves future analyses.

---

## Step 5 — Make It Yours

The starter solution lives in `solutions/starter/`. It has three files:

```
solutions/starter/
    project.yaml    — what your project IS
    prompts.yaml    — how agents THINK (their system prompts)
    tasks.yaml      — what agents CAN DO (task type registry)
```

### Option A — Edit the starter in place

Open `solutions/starter/project.yaml` and change the name, description, and domain to match your project. Then edit `solutions/starter/prompts.yaml` to give the analyst agent context about your domain.

The backend hot-reloads YAML changes. No restart needed.

### Option B — Copy to a new solution

```bash
cp -r solutions/starter solutions/my_project
# Edit the three YAML files
make run PROJECT=my_project
```

### Option C — Use the onboarding wizard (fastest)

Describe your project in plain language and the LLM generates the YAML for you:

```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -H "Content-Type: application/json" \
  -d '{
    "description": "We build e-commerce software. We need to analyze server errors, review code changes, and track performance regressions.",
    "solution_name": "ecommerce",
    "compliance_standards": [],
    "integrations": ["gitlab"]
  }'
```

This creates `solutions/ecommerce/` with all three YAML files populated. Then:

```bash
make run PROJECT=ecommerce
```

---

## The One Concept to Understand

Every agent action follows this loop — nothing skips a step:

```
SURFACE      — agent receives a signal (log, webhook, manual input)
CONTEXTUALIZE — vector memory is searched for relevant past decisions
PROPOSE      — LLM generates an action proposal
DECIDE       — you approve or reject (with optional feedback)
COMPOUND     — your feedback is stored; future analyses improve
```

The **DECIDE** step is never optional. AI proposes. You decide. This is the design.

---

## What the Three YAML Files Do

### `project.yaml` — Identity

```yaml
name: "E-Commerce Platform"
domain: "ecommerce"
description: >
  AI agent for our e-commerce backend. Analyzes server errors,
  reviews checkout and payment code, monitors deployment health.

active_modules:
  - dashboard
  - analyst
  - developer
  - monitor
  - audit

compliance_standards:
  - "PCI DSS"    # Add any standards that apply — or leave empty

integrations:
  - gitlab       # Only list what you actually use
```

### `prompts.yaml` — How Agents Think

This is where you give the analyst domain expertise. Change the system prompt to describe your domain:

```yaml
analyst:
  system_prompt: |
    You are a Senior Backend Engineer for an e-commerce platform.
    Analyze the provided server log, error trace, or performance alert.
    You understand: checkout flows, payment processing, inventory,
    database connection pooling, and Node.js/Python microservices.

    Output STRICT JSON with keys:
      severity              : "RED" | "AMBER" | "GREEN" | "UNKNOWN"
      root_cause_hypothesis : string
      recommended_action    : string
    No markdown. No prose outside the JSON object.
```

The more specific you are about your stack and domain, the better the analysis.

### `tasks.yaml` — What Agents Can Do

This defines the task types your agents handle. Keep `CREATE_MR` and `PLAN_TASK` — everything else is yours to define:

```yaml
task_types:
  - ANALYZE_SERVER_ERROR
  - ANALYZE_PERFORMANCE_REGRESSION
  - REVIEW_PAYMENT_CODE
  - CREATE_MR
  - PLAN_TASK

task_descriptions:
  ANALYZE_SERVER_ERROR:        "Triage server error logs for root cause"
  ANALYZE_PERFORMANCE_REGRESSION: "Analyze slow query or latency spike"
  REVIEW_PAYMENT_CODE:         "Security and correctness review of payment flows"
  CREATE_MR:                   "Create a GitLab merge request"
  PLAN_TASK:                   "Decompose a complex request into subtasks"
```

---

## Switching the LLM Provider

Edit `config/config.yaml`:

```yaml
llm:
  provider: "ollama"       # Switch here — no code change
  ollama_model: "llama3.2"
```

Or switch at runtime from the **LLM Settings** page in the web UI, or via API:

```bash
curl -X POST http://localhost:8000/llm/switch \
  -H "Content-Type: application/json" \
  -d '{"provider": "ollama", "model": "llama3.2"}'
```

Available providers — none require an API key except `claude`:

| Provider | Config value | Notes |
|---|---|---|
| Gemini CLI | `gemini` | Browser login once |
| Claude Code CLI | `claude-code` | Anthropic auth once |
| Ollama | `ollama` | Fully local, no login |
| Local GGUF | `local` | llama-cpp-python + GGUF file |
| Generic CLI | `generic-cli` | Any CLI tool |
| Claude API | `claude` | Only option needing an API key |

---

## Verify Everything Works

```bash
make test           # Framework unit tests (should all pass)
```

Check the API is healthy:
```bash
curl http://localhost:8000/health
```

Expected:
```json
{
  "status": "healthy",
  "project": "starter",
  "llm_provider": "gemini"
}
```

---

## Common Questions

**Do I need GitLab, Teams, Metabase, or Spira?**

No. Those are optional integrations. You can ignore all of them and SAGE works fully without them. The starter solution only lists `gitlab` as an integration but even that does nothing if `GITLAB_TOKEN` is not set — it just means the MR creation features are inactive.

**Where does the AI run?**

On your machine or wherever you run SAGE. No data is sent anywhere except to the LLM provider you configure. With Ollama, nothing leaves your machine at all.

**The web UI is showing an error on the developer page**

The developer page requires GitLab to be configured. Either set `GITLAB_TOKEN` in a `.env` file, or remove `developer` from `active_modules` in your `project.yaml` if you do not use GitLab.

**How do I add a new agent role?**

Add a block under `roles:` in `prompts.yaml`. No Python required. See `solutions/starter/prompts.yaml` for examples — `analyst_expert`, `strategic_advisor`, and `technical_reviewer` are already there.

**How do I see what the agent remembered from my feedback?**

Go to the **Knowledge Base** page in the web UI, or:
```bash
curl http://localhost:8000/knowledge/entries | python -m json.tool
```

---

## Next Steps

| Goal | Read |
|---|---|
| Add GitLab, Slack, n8n integrations | `docs/INTEGRATIONS.md` |
| Full API reference | `docs/API_REFERENCE.md` |
| Build a multi-step workflow with approval gates | `docs/ADDING_A_PROJECT.md` |
| Run evals to benchmark your agent quality | `docs/API_REFERENCE.md#eval` |
| Deploy with Docker | `README.md#docker-deployment` |
| Understand the full architecture | `ARCHITECTURE.md` |
