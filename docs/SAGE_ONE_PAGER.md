# SAGE[ai] — Smart Agentic-Guided Empowerment
### *One framework. One founder. A billion-dollar operation.*

---

## The North Star

> **1 human sets the vision. An AI agent team runs the company.**
> Every function — engineering, product, marketing, legal, finance, operations — is an agent role.
> The founder only sees decisions that genuinely require human judgment.

SAGE is the operating system for that company.

---

## What SAGE Is

**SAGE is a modular, open-source AI agent framework built on lean development principles.**

- **Agents propose. Humans decide.** Every agent action waits for human approval before execution. Compliance is built-in, not bolted on.
- **Compounding intelligence.** Every approval, rejection, and correction is stored in vector memory. Agents improve with every interaction — no retraining, no cold starts.
- **Domain-agnostic.** Three YAML files define an entire company function. No Python changes. Swap domains, swap teams, swap industries — the framework stays unchanged.
- **Open-source first.** Zero mandatory API keys. Runs fully offline with Ollama. Every dependency has a free, self-hosted alternative.

---

## The Agent Lean Loop

```
  ┌──────────────────────────────────────────────────────────┐
  │   SURFACE → CONTEXTUALIZE → PROPOSE → DECIDE → COMPOUND  │
  │                                                           │
  │  Signal    Vector memory    LLM output   Human gate  ←─┐ │
  │  arrives   searched for    generated    approve or   │  │ │
  │            prior context   with trace   reject + why  │  │ │
  │                                                    └──┘ │
  └──────────────────────────────────────────────────────────┘
             Phase 5 feeds back into Phase 2 — forever
```

---

## Hire Your Agent Team

Any job role becomes an AI agent. The founder hires, configures, and routes work to their AI team:

| Role | Dept | What They Do |
|---|---|---|
| 👩‍💻 Software Engineer | Engineering | Explore codebase → plan → implement → open PR |
| 🧪 Test Engineer | Engineering | TDD Red-Green-Refactor, test coverage, CI |
| 📋 Chief of Staff | Operations | Triage all incoming work, route to right agent |
| 📣 Marketing Strategist | Marketing | GTM, content, campaigns |
| ⚖️ Legal Advisor | Legal | Compliance, contracts, GDPR |
| 💰 Financial Analyst | Finance | Unit economics, forecasting, fundraising |
| 🧭 Strategic Advisor | Strategy | Trade-off analysis, prioritisation |
| ⚙️ Technical Reviewer | Engineering | Architecture, design review, tech debt |
| + Any Role | Any Dept | Hire any title from the Agents page |

---

## Framework Capabilities

| Capability | What It Does |
|---|---|
| **Analyst Agent** | Triages logs, errors, and events → severity + root cause + action |
| **Developer Agent** | AI code review, GitLab MR creation and review |
| **Universal Agent** | Any role defined in YAML — runs against any task |
| **SWE Agent** | Full code implementation loop: explore → plan → implement → PR |
| **Planner Agent** | Decomposes complex requests into ordered subtask sequences |
| **Monitor Agent** | Classifies events from integrated systems, triggers workflows |
| **Hire/Fire Agent** | Add or remove agent roles at runtime via UI or API |
| **Org Chart** | Visual role hierarchy with `reports_to` relationships |
| **Agent Handoff** | Chain from_role → to_role, passing output as context |
| **Continuous Tester** | Background pytest daemon, logs failures to audit trail |
| **TDD Workflow** | PostToolUse hook enforces Red-Green-Refactor discipline |
| **LangGraph Orchestration** | Stateful multi-step workflows with approval gates |
| **AutoGen Code Agent** | Write→run→fix loop in Docker sandbox |
| **MCP Tool Registry** | FastMCP servers — domain-specific tool discovery |
| **Compounding Memory** | LlamaIndex + ChromaDB + mem0 multi-session memory |
| **Eval/Benchmarking** | YAML-defined test suites with keyword scoring + history |
| **Multi-Tenant** | `X-SAGE-Tenant` header scopes vector store + audit log |
| **Slack Approvals** | Two-way approve/reject via Slack Block Kit buttons |
| **n8n Webhooks** | 400+ event sources routed into the agent queue |
| **Temporal Workflows** | Durable, crash-proof workflow execution |
| **Langfuse Observability** | LLM trace, cost tracking, LLM-as-a-Judge evals |
| **Onboarding Wizard** | LLM generates all 3 solution YAML files from a description |
| **SSE Streaming** | Token-streaming for analysis and agent responses |

---

## Architecture in 30 Seconds

```
┌─────────────────────────────────────────────────────────────────────┐
│  solutions/<name>/         3 YAML files — fully replaceable per domain │
│    project.yaml            What this domain IS                       │
│    prompts.yaml            How agents THINK (roles + system prompts) │
│    tasks.yaml              What agents CAN DO (task type registry)   │
│    workflows/              LangGraph StateGraph (agent-first by default) │
│    mcp_servers/            FastMCP domain tools                      │
├─────────────────────────────────────────────────────────────────────┤
│  src/core/                 LLM Gateway · Project Loader · Queue      │
│  src/agents/               Analyst · Developer · Monitor · Universal  │
│  src/memory/               Audit Log (SQLite) · Vector Store (Chroma) │
│  src/integrations/         LangGraph · AutoGen · Slack · n8n · MCP   │
│  src/interface/api.py      FastAPI — single public interface          │
│  web/src/                  React 18 + TypeScript dashboard           │
└─────────────────────────────────────────────────────────────────────┘
  Data flow:  UI → API → Agents → LLM → Agents → Audit Log
  Memory loop: Human Feedback → Vector Store → Future Agent Context
```

---

## 5-Minute Quick Start

```bash
# 1 — Install
git clone https://github.com/your-org/sage && cd sage
make venv

# 2 — Start (backend + frontend in one click)
./launch.sh starter

# 3 — Pick a free LLM (no API key)
# Ollama:  ollama serve && ollama pull llama3.2  (fully local)
# Gemini:  npm install -g @google/gemini-cli && gemini  (free Google login)

# 4 — Open http://localhost:5173
# 5 — Go to Agents → Hire Agent → describe any job role
```

---

## Agent-First. Compliance by Exception.

| Mode | Default | When |
|---|---|---|
| **Agent-first** | ✅ Yes | Standard solutions — agents execute autonomously |
| **Compliance gates** | ❌ No (opt-in) | Regulated solutions with `compliance_standards` → `interrupt_before` on critical nodes |

> "It's an agent team running the company. Humans review and approve only where regulation requires it."

---

## Solution Examples

| Solution | Domain | Compliance |
|---|---|---|
| `starter` | Generic template — any domain | None |
| `medtech_team` | Medical device (embedded + web + devops) | ISO 13485, IEC 62304 |
| `meditation_app` | Flutter + Node.js mobile app | GDPR |
| `four_in_a_line` | Casual game studio | GDPR, COPPA |
| `your_company` | Mount via `SAGE_SOLUTIONS_DIR` | Whatever you need |

---

## Open-Source Stack

| Layer | Technology | License |
|---|---|---|
| LLM (local) | Ollama + llama3.2, Mistral, Phi-3 | MIT/Apache |
| LLM (cloud, free) | Gemini CLI, Claude Code CLI | Free tier |
| Orchestration | LangGraph | MIT |
| Code Agent | AutoGen | MIT |
| Vector Memory | ChromaDB + LlamaIndex | Apache 2.0 |
| Long-term Memory | mem0 | Apache 2.0 |
| Tools Standard | FastMCP | MIT |
| Observability | Langfuse (self-hosted) | MIT |
| Workflows | Temporal.io | MIT |
| API | FastAPI + Uvicorn | MIT |
| UI | React 18 + Vite + Tailwind | MIT |

**Zero mandatory API keys. Zero vendor lock-in.**

---

## The Five Laws

1. **Agents propose. Humans decide. Always.** The approval gate is not bureaucracy — it is the product.
2. **Eliminate waste at every layer.** If a task can be automated correctly, it must be.
3. **Compounding intelligence over cold-start.** Every correction feeds the vector store. SAGE gets better with use.
4. **Vertical slices, not horizontal layers.** Every task produces a working, reviewable end-to-end slice of value.
5. **Atomic verification is non-negotiable.** Every agent action has a defined verification step before approval.

---

*SAGE Framework — Open Source · Self-Hosted · Agent-First*
*github.com/your-org/sage*
