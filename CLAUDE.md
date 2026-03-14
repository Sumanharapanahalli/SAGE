# SAGE Framework — Claude Code Instructions

@.claude/SOUL.md

---

## What SAGE Is (30-Second Version)

**Lean development methodology on steroids, powered by agentic AI.**

Agents surface signals, search compounding memory, propose actions, wait for human approval, and learn from every correction. The loop compounds — each decision makes the next one better. Human judgment is always in the loop. This is not optional.

---

## Project Layout (Quick Reference)

```
src/                    Framework Python source
  core/                 LLM gateway, project loader, queue manager, modules
    llm_gateway.py      Providers: Gemini CLI, Claude Code CLI, Ollama, local, generic-cli
    onboarding.py       LLM-powered solution generator from plain-language descriptions
    eval_runner.py      Eval suite runner — keyword scoring, SQLite history
    tenant.py           Multi-tenant context (X-SAGE-Tenant header, ContextVar)
  agents/               Analyst, Developer, Monitor, Planner, Universal
  interface/api.py      FastAPI — the only public interface
  memory/               Audit logger, vector memory (CRUD + bulk import)
  modules/              Zero-dependency nano-modules
  integrations/         External framework connectors (all graceful degradation)
    mcp_registry.py     MCP tool discovery + invocation
    langgraph_runner.py LangGraph orchestration (interrupt → approve → resume)
    autogen_runner.py   AutoGen code planning + Docker sandboxed execution
    slack_approver.py   Slack Block Kit proposals + /webhook/slack callbacks
    temporal_runner.py  Temporal durable workflows (LangGraph fallback)
    langchain_tools.py  LangChain tool loader per solution
    long_term_memory.py mem0 multi-session memory (vector store fallback)

web/src/                React 18 + TypeScript dashboard
  pages/                One file per route
  components/layout/    Sidebar, Header
  api/client.ts         All fetch calls — typed

solutions/              Solution configurations (NOT framework code)
  starter/              Generic template — copy this for any new domain
    project.yaml        What this domain IS (declarative agent manifest)
    prompts.yaml        How agents THINK in this domain
    tasks.yaml          What agents CAN DO
    workflows/          LangGraph StateGraph workflows (interrupt → approve)
    mcp_servers/        FastMCP server files — domain tools
    evals/              Eval YAML test suites for benchmarking
  meditation_app/       Flutter + Node.js mobile app example
  four_in_a_line/       Casual game studio example
  medtech_team/         Regulated medical device team (embedded + web + devops)
  <proprietary>/        Company-specific solutions — mount via SAGE_SOLUTIONS_DIR,
                        NEVER stored in this repo

config/config.yaml      Base LLM / memory / integration settings
.venv/                  Python virtual environment (Windows: Scripts/, Unix: bin/)
```

---

## Key Commands

```bash
make venv               # Create .venv and install all deps (first time)
make venv-minimal       # Low-RAM machine — skips ChromaDB/embeddings
make run PROJECT=xxx    # Start FastAPI backend on :8000
make ui                 # Start Vite frontend on :5173
make test               # Framework unit tests (383 passing)
make test-all           # Framework + all solution tests
```

---

## LLM Provider Setup (No API Keys Required)

All providers except `claude` work without API keys. Pick the one that fits.

| Provider | Setup | Best for |
|---|---|---|
| `gemini` (default) | `npm install -g @google/gemini-cli` → `gemini` (login once) | Cloud, latest models |
| `claude-code` | `npm install -g @anthropic-ai/claude-code` → `claude` (login once) | Claude models |
| `ollama` | Install from ollama.com → `ollama serve` → `ollama pull llama3.2` | Fully offline, no login |
| `local` | `pip install llama-cpp-python` + download GGUF model | GPU-direct, air-gapped |
| `generic-cli` | Set `generic_cli_path` in config.yaml | Any CLI tool |
| `claude` | Set `ANTHROPIC_API_KEY` | Only option requiring a key |

Change provider in `config/config.yaml`:
```yaml
llm:
  provider: "ollama"        # switch here
  ollama_model: "llama3.2"  # any model you've pulled
```

Or switch at runtime: `POST /llm/switch {"provider": "ollama", "model": "llama3.2"}`

---

## Available Skills

| Skill | Usage |
|---|---|
| `/run-tests` | Run tests — optionally pass a scope: `all`, `api`, `llm`, or a solution name |
| `/new-solution` | Scaffold a new solution from the starter template: `/new-solution robotics` |
| `/check-api` | Smoke-test all live API endpoints |
| `/edit-solution-yaml` | Edit a solution YAML and hot-reload: `/edit-solution-yaml meditation_app prompts ...` |

---

## The SAGE Lean Loop (commit this to memory)

```
SURFACE → CONTEXTUALIZE → PROPOSE → DECIDE → COMPOUND
```
Every agent task follows this five-phase cycle. Phase 5 (COMPOUND) feeds Phase 2 (CONTEXTUALIZE) for every future task. Never skip a phase.

---

## Integration Phases (what is built and where)

| Phase | Feature | Key files | Config |
|---|---|---|---|
| 0 | Langfuse observability | `llm_gateway.py` | `observability.langfuse_enabled: true` |
| 1 | LlamaIndex + LangChain + mem0 | `vector_store.py`, `langchain_tools.py`, `long_term_memory.py` | `memory.backend: llamaindex` |
| 1.5 | MCP tool registry | `mcp_registry.py` | `solutions/<name>/mcp_servers/` |
| 2 | n8n webhook receiver | `api.py /webhook/n8n` | `N8N_WEBHOOK_SECRET` env var |
| 3 | LangGraph orchestration | `langgraph_runner.py` | `orchestration.engine: langgraph` |
| 4 | AutoGen code agent | `autogen_runner.py` | Docker for sandbox |
| 5 | SSE streaming | `api.py /analyze/stream` `/agent/stream` | — |
| 6 | Onboarding wizard | `onboarding.py` | `POST /onboarding/generate` |
| 7 | Knowledge base CRUD | `vector_store.py` | `GET/POST/DELETE /knowledge/...` |
| 8 | Slack two-way approval | `slack_approver.py` | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` |
| 9 | Eval/benchmarking | `eval_runner.py` | `solutions/<name>/evals/*.yaml` |
| 10 | Multi-tenant isolation | `tenant.py`, middleware | `X-SAGE-Tenant` header |
| 11 | Temporal durable workflows | `temporal_runner.py` | `TEMPORAL_HOST` env var |

---

## New Solution: Two Ways

**1. Onboarding Wizard (recommended for new domains):**
```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -H "Content-Type: application/json" \
  -d '{"description": "We build surgical robots for minimally invasive procedures",
       "solution_name": "surgical_robotics",
       "compliance_standards": ["ISO 13485", "IEC 62304"],
       "integrations": ["gitlab", "slack"]}'
```
This generates all three YAML files using the LLM, creates the directory structure,
and returns immediately loadable YAML. Then: `POST /config/switch {"project": "surgical_robotics"}`.

**2. Manual (from starter template):**
```bash
cp -r solutions/starter solutions/my_domain
# Edit the 3 YAML files, then:
make run PROJECT=my_domain
```

---

## Adding a New Agent Role (YAML-first)

1. Add role definition + system prompt to `solutions/<name>/prompts.yaml`
2. Add task type(s) to `solutions/<name>/tasks.yaml` if needed
3. Wire role in `UniversalAgent` if task routing requires it
4. No new Python agent files for new roles — roles are YAML

---

## LangGraph Workflow Pattern

Create `solutions/<name>/workflows/my_workflow.py`:
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class State(TypedDict, total=False):
    task: str
    result: str
    approved: bool

def analyze(state): ...   # your agent logic
def finalize(state): ...  # runs after approval

graph = StateGraph(State)
graph.add_node("analyze", analyze)
graph.add_node("finalize", finalize)
graph.set_entry_point("analyze")
graph.add_edge("analyze", "finalize")
graph.add_edge("finalize", END)
workflow = graph.compile(interrupt_before=["finalize"])  # pause for approval
```

Then call:
```
POST /workflow/run   {"workflow_name": "my_workflow", "state": {"task": "..."}}
# Returns {"status": "awaiting_approval", "run_id": "..."}
POST /workflow/resume {"run_id": "...", "feedback": {"approved": true}}
```

---

## Eval Suite Format

Create `solutions/<name>/evals/analyst_quality.yaml`:
```yaml
name: "Analyst quality — error logs"
description: "Verify analyst identifies root causes correctly"
cases:
  - id: "null_ptr_001"
    role: "analyst"
    input: "Error: NullPointerException at Service:42"
    expected_keywords: ["null", "pointer", "root cause"]
    max_response_length: 2000
```
Run: `POST /eval/run {"suite": "analyst_quality"}`
History: `GET /eval/history?suite=analyst_quality`

---

## Multi-Tenant Usage

All endpoints accept `X-SAGE-Tenant: <team_name>` header. This scopes:
- Vector store collection: `<tenant>_knowledge`
- Audit log metadata: `tenant_id` field
- Task queue submissions: tagged with tenant

Default (no header): active solution name is used as tenant.

---

## The Two Backlogs — Never Mix Them

| Scope | Owned by | Workflow | Where tracked |
|---|---|---|---|
| **`solution`** | The builder's team | Log → AI plan → approve → implement in solution | SAGE Improvements → Solution Backlog tab |
| **`sage`** | SAGE community | Log → GitHub Issue → community PR | SAGE Improvements → SAGE Framework Ideas tab |

Every `FeatureRequest` has a `scope` field. Every submission UI has a scope selector.
If someone asks "can you add X", first ask: is X for their solution, or for SAGE itself?

---

## Critical Rules (from SOUL.md)

- Never commit proprietary solutions to this repo — mount them via `SAGE_SOLUTIONS_DIR` from a separate private repo
- Never add solution-specific logic to `src/` — solutions plug in via YAML only
- Never bypass the audit log or the human approval step
- Never remove the `threading.Lock` from `LLMGateway`
- Always use `self.logger` not `print()`
- Never short-circuit feedback ingestion (Phase 5) — every rejection teaches
- Run `make test` before and after any change to `src/`
