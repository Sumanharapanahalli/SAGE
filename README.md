# SAGE Framework
### *Smart Agentic-Guided Empowerment*

> **The agentic AI framework built for regulated industries.**
> AI proposes. Humans approve. Every decision is auditable, traceable, and compliance-ready.

---

## Why Regulated Industries Need SAGE

Most AI agent frameworks hand the machine a task and let it execute. That works in low-stakes domains. It does not work when a wrong decision can:

- Fail an FDA 21 CFR Part 11 audit
- Violate IEC 62304 software lifecycle requirements
- Trigger an ISO 13485 corrective action
- Cause patient harm, aircraft incidents, or safety-critical failures

**SAGE is built differently.** Every AI proposal — code change, YAML edit, knowledge deletion, agent hire — requires explicit human sign-off before execution. The approval gate is not optional, not configurable, and not bypassable. It is the product.

### The Core Guarantee

```
Agent surfaces signal → Agent proposes action → Human reviews → Human approves → Action executes → Audit log records everything
```

No step is skipped. No action executes without human authorisation. The full chain is immutable and stored in a per-solution SQLite audit log that travels with the solution — not the framework.

---

## Who This Is For

| Industry | Use Case | Key Standards |
|---|---|---|
| Medical devices | Embedded firmware + cloud backend oversight | IEC 62304, ISO 13485, FDA 21 CFR Part 11 |
| Aviation & aerospace | Avionics software development lifecycle | DO-178C, ARP4754A |
| Railways | Safety-critical signalling systems | EN 50128, CENELEC |
| Industrial IoT | Connected device firmware + compliance tooling | ISO 14971, IEC 61508 |
| Pharmaceuticals | Manufacturing execution + CAPA management | FDA 21 CFR Part 11, EU Annex 11 |
| Any regulated domain | AI-assisted development with full audit trail | Your standard here |

SAGE ships with production-quality example solutions for medical devices, avionics, railways, and industrial IoT — not toy demos. Each includes agent prompts tuned for that domain, compliance-aware task types, and a full regulatory document set.

---

## The Human-in-the-Loop Guarantee

This is SAGE's defining principle. It is stated once here and does not change:

**Solution-level agent proposals (`yaml_edit`, `implementation_plan`, `code_diff`, `knowledge_delete`, `agent_hire`) always require human sign-off. No exceptions. Not for demos. Not for "obvious" cases.**

Framework control operations (`config_switch`, `llm_switch`, `module_toggle`) execute immediately — they are the operator's own action, not agent action. The distinction is deliberate and documented.

The approval inbox is the compliance record. Every approval, rejection, and correction is written to `solutions/<name>/.sage/audit_log.db` with a `trace_id`, timestamp, and the human's feedback. This file is the IQ/OQ/PQ evidence trail in regulated deployments.

---

## Solutions

Solutions are **separate from the framework** — each is a folder of 3 YAML files (`project.yaml`, `prompts.yaml`, `tasks.yaml`). No Python. No framework changes.

### Included example solutions

| Solution | Domain | Compliance Focus |
|---|---|---|
| `starter` | Generic template | None — start here |
| `iot_medical` | IoT medical device monitoring | IEC 62304 Class C, ISO 14971, FDA 21 CFR 820 |
| `medtech_team` | Regulated medical device team | IEC 62304, ISO 13485, HIL testing |
| `avionics` | Avionics software team | DO-178C, ARP4754A |
| `railways` | Railway signalling systems | EN 50128, CENELEC |
| `automotive` | Infotainment & telematics | ASPICE, ISO 26262 |
| `meditation_app` | Flutter mobile app | None |
| `four_in_a_line` | Casual game studio | None |
| `board_games` | Cross-platform games platform | None |

### Proprietary solutions (NOT in this repo)

Your solutions live in a **private repository**, mounted at runtime. They never touch this repo.

```bash
SAGE_SOLUTIONS_DIR=/path/to/private-solutions make run PROJECT=my_solution
```

### Add your own solution

```bash
cp -r solutions/starter solutions/my_project
# Edit the three YAML files, then:
make run PROJECT=my_project
```

Or generate from a plain-language description in 30 seconds — see [GETTING_STARTED.md](GETTING_STARTED.md).

---

## Features

**Compliance & Audit**
- Immutable per-solution audit log (SQLite, travels with the solution, never in the framework repo)
- Every proposal has a `trace_id`, risk classification, expiry, and full approval chain
- IQ/OQ/PQ validation test suite (`make test-compliance`)
- Per-solution regulatory document set (SRS, Risk Management, SOUP Inventory, V&V Plan, RTM, DHF)

**Human-in-the-Loop**
- Approval inbox with risk badges (DESTRUCTIVE, EPHEMERAL, STANDARD)
- Rejection triggers learning — human feedback is stored in vector memory for future context
- Batch approval, filter by type, expiry warnings
- Slack two-way approval (Block Kit cards + webhook callbacks)

**Agentic Intelligence**
- 5 core agent roles: Analyst, Developer, Monitor, Planner, Universal — plus 19 specialist roles in the Build Orchestrator workforce (Engineering, Analysis, Design, Compliance, Operations teams)
- Roles defined in `prompts.yaml` — no Python required for new roles
- ReAct loop (Reason+Act) for multi-step MR review
- Plan-and-Execute orchestration for complex tasks
- Wave scheduling — independent tasks run in parallel, dependent tasks sequence automatically
- Compounding memory — every correction improves future proposals without model retraining
- **Build Orchestrator** — end-to-end product construction from plain-language description (0→1→N pipeline), with Critic Agent review, configurable HITL gates, domain-aware build detection (13 industries), 32 task types, 19 agent roles in 5 workforce teams, adaptive Q-learning router, and anti-drift checkpoints

**Multi-Solution**
- Switch domains with one click; all agent prompts, task types, and UI labels adapt
- Per-solution knowledge base (ChromaDB vector store, isolated collections)
- Multi-tenant support (`X-SAGE-Tenant` header scopes everything per team)
- Org graph — visualise solution hierarchies, knowledge channels, cross-team task routing

**Integrations**
- GitLab (MR creation, review, pipeline status)
- Slack (two-way approval via Block Kit)
- LangGraph (interrupt → approve → resume workflows)
- AutoGen (code planning + Docker sandboxed execution)
- Temporal (durable workflows)
- MCP servers (serial port, J-Link, Metabase, SpiraTeam, Teams, GitLab)
- n8n webhook receiver

**LLM Providers — No API Key Required**
- Gemini CLI (browser OAuth, no key)
- Claude Code CLI (existing auth, no key)
- Ollama (fully offline, no key)
- Local Llama GGUF (air-gapped, GPU-direct)
- Claude API (Anthropic SDK — only option requiring a key)

---

## New Here? Start with the Getting Started Guide

**[GETTING_STARTED.md](GETTING_STARTED.md)** — zero integrations, no API keys, running in 15 minutes.

---

## Quick Start

```bash
make venv                      # Create .venv and install all deps (one-time)
make run PROJECT=starter       # Generic starter — no integrations required
make ui                        # React web UI at http://localhost:5173
make test                      # Framework unit tests
make test-compliance           # IQ/OQ/PQ validation suite
```

To build a product from scratch (Build Orchestrator):

```bash
curl -X POST http://localhost:8000/build/start \
  -H "Content-Type: application/json" \
  -d '{"product_description": "A task management app with Kanban boards", "solution_name": "taskflow"}'
```

To run a regulated domain solution:

```bash
make run PROJECT=iot_medical   # IoT medical device — IEC 62304 Class C
make run PROJECT=medtech_team  # Medical device team — ISO 13485
make run PROJECT=avionics      # Avionics — DO-178C
make run PROJECT=railways      # Railway signalling — EN 50128
```

> All `make` commands use `.venv/Scripts/python` (Windows) or `.venv/bin/python` (Linux/macOS) automatically.

### Authenticate Gemini CLI (first time only)

```bash
gemini
# Follow the browser OAuth prompt — no API key required
```

---

## Minimum Requirements

SAGE runs on a standard development laptop. No GPU required for cloud providers.

| Mode | CPU | RAM | GPU | Notes |
|------|-----|-----|-----|-------|
| Gemini CLI (default) | 4-core | 4 GB | Not required | Recommended — no key needed |
| Claude Code CLI | 4-core | 4 GB | Not required | Uses existing `claude` auth |
| Ollama (local) | 8-core | 8 GB | Optional | Fully offline, air-gapped |
| Local GGUF | 8-core | 8 GB | Optional (4 GB VRAM = 10x) | Air-gapped, no network |

```bash
# Low-RAM machines — skip ChromaDB/embeddings
make venv-minimal
SAGE_MINIMAL=1 make run PROJECT=starter
```

---

## Architecture

```
solutions/<name>/          Three YAML files — fully replaceable per domain
  project.yaml             What this domain IS
  prompts.yaml             How agents THINK in this domain
  tasks.yaml               What agents CAN DO
  .sage/                   Runtime state — auto-created, never committed
    audit_log.db           Immutable compliance record + training signal
    chroma_db/             Per-solution vector knowledge store

src/core/                  LLM gateway, project loader, queue manager, modules
src/agents/                Analyst, Developer, Monitor, Planner, Universal
src/interface/api.py       FastAPI — the only public interface
src/memory/                Audit logger + vector memory
web/src/                   React 18 + TypeScript dashboard
```

Full design: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## REST API

Backend at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service status, active project, LLM provider |
| `GET` | `/config/project` | Active project metadata, task types, compliance standards |
| `POST` | `/analyze` | Analyze log/metric/error → AI proposal |
| `POST` | `/approve/{trace_id}` | Approve a pending proposal |
| `POST` | `/reject/{trace_id}` | Reject with human feedback (triggers learning) |
| `GET` | `/proposals/pending` | List pending proposals with risk classifications |
| `GET` | `/audit` | Query immutable audit log |
| `POST` | `/config/switch` | Switch active solution |
| `POST` | `/llm/switch` | Switch LLM provider |
| `GET` | `/knowledge/search` | Semantic search across solution knowledge base |
| `POST` | `/knowledge/add` | Add entry to solution knowledge base |
| `POST` | `/onboarding/generate` | Generate solution YAML from plain-language description |
| `POST` | `/build/start` | Start end-to-end product build from description |
| `GET` | `/build/status/{run_id}` | Get build run status and progress |
| `GET` | `/org` | Get org structure |
| `GET` | `/eval/run` | Run evaluation suite |
| `POST` | `/shutdown` | Stop backend and frontend |

---

## Regulatory Documentation

### Framework compliance test suite

```bash
make test-compliance   # IQ/OQ/PQ validation protocol
```

### Per-solution regulatory documents (`solutions/medtech/docs/regulatory/`)

| Document | Standard |
|----------|---------|
| [SRS.md](solutions/medtech/docs/regulatory/SRS.md) | Software Requirements Specification |
| [RISK_MANAGEMENT.md](solutions/medtech/docs/regulatory/RISK_MANAGEMENT.md) | ISO 14971 Risk Management |
| [SOUP_INVENTORY.md](solutions/medtech/docs/regulatory/SOUP_INVENTORY.md) | IEC 62304 §8.1.2 SOUP Inventory |
| [VV_PLAN.md](solutions/medtech/docs/regulatory/VV_PLAN.md) | Verification and Validation Plan |
| [RTM.md](solutions/medtech/docs/regulatory/RTM.md) | Requirements Traceability Matrix |
| [DHF_INDEX.md](solutions/medtech/docs/regulatory/DHF_INDEX.md) | Design History File Index |
| [CHANGE_CONTROL.md](solutions/medtech/docs/regulatory/CHANGE_CONTROL.md) | Change Control Procedure |
| [SECURITY_PLAN.md](solutions/medtech/docs/regulatory/SECURITY_PLAN.md) | Cybersecurity Plan |

---

## Documentation

| Document | Description |
|----------|-------------|
| [GETTING_STARTED.md](GETTING_STARTED.md) | Zero-to-running in 15 minutes |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Full system design, agent architecture, data flows |
| [CLAUDE.md](CLAUDE.md) | Developer reference — codebase conventions, rules, patterns |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | End-user operational guide |
| [docs/SETUP.md](docs/SETUP.md) | Detailed installation and integration setup |
| [docs/MCP_SERVERS.md](docs/MCP_SERVERS.md) | MCP server reference |

---

## License

MIT
