# SAGE[ai] — Smart Agentic-Guided Empowerment

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![GitHub Stars](https://img.shields.io/github/stars/Sumanharapanahalli/sage?style=social)](https://github.com/Sumanharapanahalli/sage)
[![GitHub Forks](https://img.shields.io/github/forks/Sumanharapanahalli/sage?style=social)](https://github.com/Sumanharapanahalli/sage/fork)

### *One framework. One founder. A billion-dollar operation.*
### *Open Source — Community-Driven — Transparent — Auditable*
### *2026-03-24*

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
- **Open-source first.** Licensed under Apache 2.0. Zero mandatory API keys. Runs fully offline with Ollama. Every dependency has a free, self-hosted alternative. The framework is fully open on GitHub; your proprietary solutions stay in a private repo mounted via `SAGE_SOLUTIONS_DIR`.

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

## Intelligence Layer v1 (NEW)

| Feature | What It Does |
|---|---|
| **Approvals Inbox** | Risk-ranked HITL inbox — every AI write action surfaces here before execution. 5 risk tiers: INFORMATIONAL → EPHEMERAL → STATEFUL → EXTERNAL → DESTRUCTIVE. Batch-approve low-risk items. |
| **SAGE Intelligence SLM** | On-device Gemma 3 1B via Ollama answers framework questions, classifies task tiers (LIGHT/STANDARD/HEAVY), lints YAML, converts intent to API calls — zero cloud calls for meta-operations. |
| **Teacher-Student LLM** | Heavy teacher LLM generates rich analyses; fast student SLM learns from them. Distillation logs saved to JSONL. Score drift tracked in `/distillation/<solution>/stats`. |
| **Conversational Onboarding** | Two-path wizard: (A) point to an existing repo → LLM analyzes stack + CI + compliance hints and generates all 3 YAML files; (B) guided Q&A → same output. SQLite-persisted session state. |
| **Domain Org Structure Chooser** | Pick a pre-built agent team template for 6 domains. Enable/disable individual roles. YAML generated with right prompts, task types, and compliance standards pre-loaded. |
| **Visual Workflow Diagrams** | `/workflows` page auto-generates Mermaid diagrams from every LangGraph StateGraph. Always accurate — never manually drawn. |
| **Parallel Task Execution** | Wave scheduler runs independent tasks concurrently via ThreadPoolExecutor. Compliance solutions auto-fall back to sequential single-lane execution. |
| **SWE Agent (open-swe)** | 6-node LangGraph pipeline: explore → plan → implement → verify → propose_pr → finalize. Opens a real GitHub PR and pauses for founder review before marking complete. |
| **HIL Testing** | Hardware-in-the-loop runner: 5 transports (mock, serial, J-Link, CAN, OpenOCD). Generates regulatory evidence reports from test results. |
| **Compliance Flags** | Automated compliance checklist generation for 5 regulated industries. Gap assessment against active solution's declared standards. |
| **Org Chart** | Agent team hierarchy with `reports_to` relationships. Live status shows active/idle/error per agent. Daily task counts, last activity. |

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
| **Org Chart** | Visual role hierarchy with `reports_to` relationships and live status |
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
| **Onboarding Wizard** | LLM generates all 3 solution YAML files from a description or existing repo |
| **SSE Streaming** | Token-streaming for analysis and agent responses |

---

## Dashboard (27 Pages)

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
| **Knowledge** | Vector Store | `/knowledge` | Search and manage knowledge base |
| **Knowledge** | Channels | `/activity` | Cross-team knowledge channels |
| **Knowledge** | Audit Log | `/audit` | Full compliance trail |
| **Knowledge** | Costs | `/costs` | Token spend, budget controls |
| **Organization** | Org Graph | `/org-graph` | Solutions, channels, task routing graph |
| **Organization** | Onboarding | `/onboarding` | Conversational wizard + domain template chooser |
| **Admin** | LLM Settings | `/llm` | Provider switch, token stats |
| **Admin** | Config Editor | `/yaml-editor` | Live YAML editing with hot-reload |
| **Admin** | Access Control | `/access-control` | RBAC roles and API keys |
| **Admin** | Integrations | `/integrations` | GitLab, Slack, n8n, Composio |
| **Admin** | Settings | `/settings` | Solution config |
| **Admin** | Organization | `/settings/organization` | Company mission, vision, values |
| — | Issues | `/issues` | Feature backlog with priority filters |
| — | Guide | `/guide` | Interactive framework guide |
| — | Activity | `/activity` | Real-time audit log timeline |

Cmd+K opens the command palette to jump to any page instantly.

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
git clone https://github.com/Sumanharapanahalli/sage && cd sage
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

## Regulated Domain Solutions

Pre-built agent teams with correct roles, system prompts, task types, and compliance standards:

| Solution | Domain | Compliance Standards |
|---|---|---|
| `starter` | Generic template — any domain | None |
| `medtech_team` | Medical device (embedded + web + devops) | IEC 62304, ISO 14971, IEC 60601-1, FDA 21 CFR 820 |
| `automotive` | Infotainment + telematics + ADAS | ISO 26262, UN ECE WP.29, ISO/SAE 21434 |
| `avionics` | Avionics SW + systems + airworthiness | DO-178C, DO-254, ARP4754A, FAA Part 25 |
| `iot_medical` | IoT medical device (IEC 62304 Class C) | IEC 62304, ISO 14971, IEC 62443 |
| `elder_fall_detection` | Elder fall detection IoT | HIPAA, IEC 62304 |
| `finmarkets` | Financial markets | SOC 2, PCI DSS |
| `bluedrop_medical` | Medical device startup | IEC 62304, ISO 13485 |
| `meditation_app` | Flutter mobile + Node.js | GDPR |
| `four_in_a_line` | Casual game studio | GDPR, COPPA |
| + 7 more | Various domains | See `solutions/` directory |
| `your_company` | Mount via `SAGE_SOLUTIONS_DIR` (private repo) | Whatever you need |

---

## Open-Source Stack

| Layer | Technology | License |
|---|---|---|
| LLM (local) | Ollama + llama3.2, Mistral, Phi-3, Gemma 3 | MIT/Apache |
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
| Diagrams | Mermaid.js (auto-generated) | MIT |

**Zero mandatory API keys. Zero vendor lock-in.**

---

## The Five Laws

1. **Agents propose. Humans decide. Always.** The approval gate is not bureaucracy — it is the product.
2. **Eliminate waste at every layer.** If a task can be automated correctly, it must be.
3. **Compounding intelligence over cold-start.** Every correction feeds the vector store. SAGE gets better with use.
4. **Vertical slices, not horizontal layers.** Every task produces a working, reviewable end-to-end slice of value.
5. **Atomic verification is non-negotiable.** Every agent action has a defined verification step before approval.

---

*SAGE Framework — Open Source (Apache 2.0) · Self-Hosted · Agent-First · Community-Driven*
*github.com/Sumanharapanahalli/sage*

---

## Open-Source Model

SAGE follows an **open-core** approach:

- **Framework (this repo):** Fully open source under Apache 2.0. All 136 API endpoints, 27 UI pages, 17+ solution templates, and the complete agent architecture are public, auditable, and forkable.
- **Your solutions (private):** Mount via `SAGE_SOLUTIONS_DIR` from a separate private repository. Your proprietary YAML configs, domain knowledge, and `.sage/` runtime data never touch the public repo.
- **Community contributions welcome:** File issues, submit PRs, propose new solution templates, or build MCP tool servers. See `CONTRIBUTING.md` for guidelines.
- **Transparent by design:** Every agent decision, every approval, every rejection is logged in an immutable audit trail. The codebase itself is public for security review and regulatory confidence.

---

## What's Shipped (SAGE 10 — March 2026)

### Intelligence Layer v3
- **Action-Aware Chat** — chat panel routes natural language to framework actions with audit trail
- **Multi-LLM Provider Pool** — parallel generation strategies (voting, fastest, fallback, quality)
- **Task Routing** — route different task types to different LLM providers automatically
- **Build Orchestrator** — end-to-end product builder with 13+ domain detection, 19+ agents, 5 teams, Q-learning adaptive router, anti-drift checkpoints

### SAGE 10 Framework Features
- **136 API endpoints** across 22 categories
- **27 UI pages** in 5-area sidebar (Work, Intelligence, Knowledge, Organization, Admin)
- **17+ bundled solutions** covering medical, automotive, avionics, IoT, fintech, and more
- **53 test files** including 58 system E2E tests for full API lifecycle
- **Agent budgets** — Monthly call ceilings per role with hard/soft cutoff
- **Undo** — Revert approved code diffs with one click
- **Live agents panel** — Real-time active-agent visibility
- **Task hooks** — Pre/post shell hooks per task type
- **Repo map** — File tree + symbols fed to Developer agent context
- **Scheduled tasks** — Cron-declared recurring tasks in `tasks.yaml`
- **Git worktrees** — Isolated workspace per concurrent code proposal
- **Knowledge sync** — Bulk-import docs into the vector store
- **Knowledge channels** — Cross-team knowledge sharing via org config
- **Wave execution** — Parallel subtask fan-out from a single queue entry
- **Org Graph** — React Flow graph of solutions, channels, and task routing
- **PII detection** — Presidio-based PII scrubbing with redact/mask/flag modes
- **Data residency** — Region-aware provider routing (EU providers for EU data)
- **OpenShell sandbox** — Sandboxed code execution for SWE tasks
- **Folder scanner** — Scan existing codebases to auto-generate solution YAML

### UX Redesign
Complete navigation overhaul: 5-area accordion sidebar, 44px solution rail, live stats strip, resizable panels, per-solution accent colors, hover color previews, 6-stop onboarding tour, ChatPanel overlay.
