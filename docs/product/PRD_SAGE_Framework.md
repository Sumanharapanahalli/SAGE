# SAGE Framework — Product Requirements Document
**Version:** 2.0
**Date:** 2026-03-28
**Branch:** feature/domain-runners
**Status:** Active Development
**Owner:** SAGE Product Team

---

## Table of Contents

1. [Executive Summary & Vision](#1-executive-summary--vision)
2. [Problem Statement](#2-problem-statement)
3. [Target Users & Personas](#3-target-users--personas)
4. [Goals & Success Metrics](#4-goals--success-metrics)
5. [Feature Inventory](#5-feature-inventory)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Constraints & Dependencies](#7-constraints--dependencies)
8. [Appendix: Integration Matrix](#8-appendix-integration-matrix)

---

## 1. Executive Summary & Vision

### Vision Statement

**One human. One AI agent team. A billion-dollar company.**

SAGE (Smart Agentic-Guided Empowerment) is a lean development methodology platform powered by agentic AI. It is not a chatbot, a copilot, or a demo. It is a professional engineering tool that allows a single operator — or a small team — to build, ship, and operate production software at the speed and scale previously requiring organizations of hundreds.

### Core Thesis

Lean development — eliminate waste, maximize value flow, amplify human judgment — is the natural pairing for agentic AI. Agents do not replace lean methodology; they remove the friction that kept lean from reaching its full potential. Every ceremony removed, every feedback loop shortened, and every manual step automated translates directly into value flow for the operator.

### What Makes SAGE Different

| Dimension | Traditional Dev Tools | AI Copilots | SAGE |
|---|---|---|---|
| Scope | Task-level assistance | Code completion | End-to-end product building |
| Memory | None | Session-only | Compounding vector memory |
| Compliance | None | None | HITL gates, audit log |
| Domain awareness | Generic | Generic | 13 domains, 19 specialized agents |
| Improvement | Static | Static | Self-play gym, Glicko-2 ratings |
| Isolation | None | None | 3-tier sandboxed execution |
| Human oversight | Optional | Optional | Mandatory (compliance-grade) |

### Strategic Positioning

SAGE targets the intersection of three converging trends:
1. **Agentic AI maturation** — LLMs can now reliably plan, execute, and verify multi-step tasks
2. **Regulated industry adoption** — Medical, firmware, and aerospace teams need AI with auditable human oversight
3. **Solo founder / small team leverage** — The marginal cost of adding domain expertise via an agent approaches zero

---

## 2. Problem Statement

### The Core Problem

Building and maintaining software products at scale requires deep domain expertise, cross-functional coordination, and continuous feedback loops. Today, this requires large teams, long cycles, and significant waste — status meetings, handoff delays, rework from miscommunication, and manual verification steps that slow every release.

Existing AI tools address isolated tasks (code completion, documentation generation) but do not close the loop. They produce artifacts. They do not build products.

### Problems SAGE Solves

**P1 — Domain expertise is expensive and scarce.**
A single founder cannot be a firmware engineer, PCB designer, ML researcher, UX designer, and technical writer simultaneously. Domain-aware runners (OpenFW, OpenEDA, OpenML, OpenDoc, OpenDesign, OpenStrategy) make specialized expertise available on demand without hiring.

**P2 — AI proposals without oversight create compliance risk.**
Regulated industries (medical devices: ISO 13485, IEC 62304; automotive: ISO 26262; aerospace: DO-178C) require every AI-generated artifact to have a documented human review. AI copilots that execute directly cannot be used in these environments. SAGE's HITL approval gate is compliance-grade by design.

**P3 — Intelligence does not compound in existing tools.**
Every session with an AI copilot starts from scratch. Every correction is thrown away. SAGE's vector memory captures every human approval, rejection, and correction — making every future proposal better informed by the history of the product it is working on.

**P4 — Agent quality is unmeasured and unimproved.**
No existing tool can tell you whether an AI's code review quality improved over the last 30 sessions. The Agent Gym with Glicko-2 ratings gives SAGE operators measurable, comparable skill levels for every agent role — and a training loop that improves those ratings.

**P5 — Multi-domain products require orchestration, not point tools.**
A medical device product involves firmware, regulatory documentation, ML signal processing, PCB design, and web dashboards simultaneously. SAGE's Build Orchestrator (13 domains, 19 agents, 5 teams) coordinates all of them under a single workflow with dependency-aware wave execution.

---

## 3. Target Users & Personas

### Persona 1 — The Regulated Industry Engineer

**Name:** Maya, Senior Embedded Systems Engineer
**Industry:** Medical devices / Automotive firmware
**Company Size:** 50–500 employees
**Technical Level:** Expert (10+ years embedded C, RTOS, safety standards)

**Jobs to be Done:**
- Generate IEC 62304-compliant software documentation without writing boilerplate
- Get automated DRC/ERC checks on PCB designs before sending to fabrication
- Cross-reference regulatory requirements against implementation artifacts
- Produce DHF (Device History File) entries automatically from completed tasks

**Pain Points:**
- Documentation overhead consumes 30–40% of engineering time
- Compliance reviews require manually tracing requirements to code
- PCB toolchain (KiCad, Altium) has no AI integration
- Every agent action needs a paper trail for auditors

**SAGE Value:**
- OpenFW, OpenEDA, OpenDoc runners handle domain-specific execution
- Audit log produces compliance-grade trail automatically
- HITL gates satisfy regulatory requirement for human review
- DHF generation via OpenDoc runner from task history

**Success Looks Like:** Maya's team ships a new firmware version 40% faster with full DHF generated automatically.

---

### Persona 2 — The Startup Founder / Solo Builder

**Name:** Alex, Technical Solo Founder
**Industry:** B2B SaaS / Consumer app
**Company Size:** 1–5 people
**Technical Level:** Strong generalist (full-stack, some ML, no firmware/PCB)

**Jobs to be Done:**
- Build a working MVP from a plain-language product description
- Get code reviewed without hiring a senior engineer
- Maintain multiple products simultaneously without dropping quality
- Track what each AI agent is good and bad at

**Pain Points:**
- Can't afford specialists (ML engineer, UX designer, technical writer)
- No process for reviewing AI-generated code at scale
- Context loss between sessions — repeating the same instructions
- No visibility into which AI proposals were good vs. bad

**SAGE Value:**
- `POST /build/start` turns a description into a running product pipeline
- N-Provider Multi-Critic reviews every artifact before it reaches the human
- Vector memory retains all context between sessions
- Agent Gym leaderboard shows which agent roles are strongest

**Success Looks Like:** Alex ships three products in parallel with a team of 1, maintaining quality metrics comparable to a 5-person team.

---

### Persona 3 — The AI Researcher / Platform Builder

**Name:** Jordan, AI Systems Researcher
**Industry:** AI/ML research, platform engineering
**Company Size:** 10–200 people
**Technical Level:** Expert (LLMs, agent architectures, ML pipelines)

**Jobs to be Done:**
- Benchmark agent performance across task types and domains
- Run self-play training experiments to measure skill acquisition rates
- Build domain-specific agent teams without writing framework code
- Integrate multiple LLM providers and compare output quality

**Pain Points:**
- Existing agent frameworks have no built-in evaluation infrastructure
- Skill ratings are anecdotal — no Glicko-2 or comparable statistical model
- Hard to swap LLM providers without rewriting prompts
- No native support for regulated-industry workflow constraints

**SAGE Value:**
- Agent Gym with Glicko-2 provides statistically rigorous skill measurement
- 470+ seed exercises, 50,000+ via LLM variants — immediate benchmark dataset
- N-Provider Multi-Critic enables systematic provider comparison
- BaseRunner ABC makes adding new domain runners straightforward

**Success Looks Like:** Jordan publishes a paper using SAGE Gym data showing measurable skill acquisition rates across 8 domains and 6 LLM providers.

---

### Persona 4 — The Enterprise DevOps / Platform Engineer

**Name:** Sam, Platform Engineering Lead
**Industry:** Enterprise software / Financial services
**Company Size:** 500+ employees
**Technical Level:** Strong (CI/CD, Kubernetes, Python, cloud infrastructure)

**Jobs to be Done:**
- Run AI-assisted development at team scale with proper access control
- Isolate each product team's AI memory and proposals
- Integrate SAGE into existing GitHub/GitLab/Slack workflows
- Enforce security policies on AI code execution

**Pain Points:**
- Multi-tenant isolation is an afterthought in most AI tools
- No way to apply security policies to what AI agents execute
- Slack-based approval workflows don't exist in most frameworks
- No audit trail that satisfies SOC 2 / enterprise security requirements

**SAGE Value:**
- Multi-tenant isolation via `X-SAGE-Tenant` header — zero data overlap between teams
- OpenShell runner enforces YAML security policies on all agent execution
- Slack two-way approval (Block Kit proposals + webhook callbacks)
- SQLite audit log per solution — immutable compliance record

**Success Looks Like:** Sam deploys SAGE to 5 product teams with isolated memory, Slack-based approvals, and a monthly audit report generated automatically.

---

## 4. Goals & Success Metrics

### Strategic Goals

| ID | Goal | Horizon |
|---|---|---|
| G1 | Enable a single operator to manage a complete product build across 13 domains | 2026-Q2 |
| G2 | Make agent quality measurable and improvable through self-play training | 2026-Q3 |
| G3 | Achieve compliance-grade adoption in at least one regulated industry (medical/automotive) | 2026-Q4 |
| G4 | Build a self-sustaining skill marketplace with community contributions | 2027-Q1 |
| G5 | Demonstrate 10x productivity improvement vs. traditional team for a 0→1 build | 2027-Q2 |

### Key Performance Indicators

#### Product Quality KPIs

| KPI | Baseline | Target (6mo) | Target (12mo) | Measurement |
|---|---|---|---|---|
| Build completion rate (0→1 pipeline) | — | 70% success on valid descriptions | 85% | `/build/{id}` status |
| Critic score mean | — | >70/100 on merged artifacts | >80/100 | `GET /gym/analytics` |
| Agent Gym improvement rate | — | +5 Glicko-2 pts/session avg | +8 pts/session | `GET /gym/ratings` |
| HITL approval rate | — | >60% first-pass approval | >75% | Audit log |
| Vector memory retrieval relevance | — | >0.75 cosine similarity | >0.85 | Vector store metrics |

#### Adoption KPIs

| KPI | Target (3mo) | Target (6mo) | Target (12mo) |
|---|---|---|---|
| Active solutions deployed | 10 | 50 | 200 |
| Domains covered in production | 5 | 9 | 13 |
| Community skill submissions | 0 | 20 | 100 |
| Regulated industry deployments | 0 | 2 | 10 |
| Agent Gym training sessions run | 100 | 1,000 | 10,000 |

#### Developer Experience KPIs

| KPI | Target |
|---|---|
| Time from description to first build plan | <30 seconds |
| New solution scaffold time (onboarding wizard) | <2 minutes |
| API response latency (p95, non-LLM endpoints) | <200ms |
| LLM provider switch time | <5 seconds |
| Test suite pass rate | >98% on `make test` |

---

## 5. Feature Inventory

All 19+ integration phases are listed below with current status and owner runner/module.

### Phase 0 — Observability (Langfuse)

**Description:** Trace every LLM call through Langfuse — latency, token cost, quality scores.
**Key Files:** `src/core/llm_gateway.py`
**Config:** `observability.langfuse_enabled: true`
**Status:** Implemented

### Phase 1 — Memory Stack (LlamaIndex + LangChain + mem0)

**Description:** Vector store for domain knowledge, LangChain tool loader per solution, long-term memory via mem0.
**Key Files:** `src/memory/vector_store.py`, `src/integrations/langchain_tools.py`, `src/memory/long_term_memory.py`
**Config:** `memory.backend: llamaindex`
**Status:** Implemented

### Phase 1.5 — MCP Tool Registry

**Description:** Model Context Protocol tool discovery and invocation. Solutions expose domain tools via FastMCP servers.
**Key Files:** `src/integrations/mcp_registry.py`, `solutions/<name>/mcp_servers/`
**Status:** Implemented

### Phase 2 — n8n Webhook Receiver

**Description:** Receive n8n workflow events at `POST /webhook/n8n` for external automation triggers.
**Key Files:** `src/interface/api.py`
**Config:** `N8N_WEBHOOK_SECRET` env var
**Status:** Implemented

### Phase 3 — LangGraph Orchestration

**Description:** StateGraph workflows with interrupt-before nodes for human-in-the-loop approval gates.
**Key Files:** `src/integrations/langgraph_runner.py`, `solutions/<name>/workflows/`
**Config:** `orchestration.engine: langgraph`
**Status:** Implemented

### Phase 4 — AutoGen Code Agent

**Description:** AutoGen code planning with Docker sandboxed execution. Autonomous code generation and test running.
**Key Files:** `src/integrations/autogen_runner.py`
**Config:** Docker required for sandbox
**Status:** Implemented

### Phase 5 — SSE Streaming

**Description:** Server-sent events for real-time agent output streaming. `/analyze/stream` and `/agent/stream` endpoints.
**Key Files:** `src/interface/api.py`
**Status:** Implemented

### Phase 6 — Onboarding Wizard

**Description:** LLM-powered solution generator from plain-language descriptions. Produces all three YAML files.
**Key Files:** `src/core/onboarding.py`
**Endpoint:** `POST /onboarding/generate`
**Status:** Implemented

### Phase 7 — Knowledge Base CRUD

**Description:** Full CRUD API for solution knowledge base. Bulk import, search, and deletion with tenant isolation.
**Key Files:** `src/memory/vector_store.py`
**Endpoints:** `GET/POST/DELETE /knowledge/...`
**Status:** Implemented

### Phase 8 — Slack Two-Way Approval

**Description:** Slack Block Kit proposals with `/webhook/slack` callback for approvals without leaving Slack.
**Key Files:** `src/integrations/slack_approver.py`
**Config:** `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`
**Status:** Implemented

### Phase 9 — Eval / Benchmarking

**Description:** YAML-defined eval suites with keyword scoring and SQLite history. Compare provider quality over time.
**Key Files:** `src/core/eval_runner.py`, `solutions/<name>/evals/*.yaml`
**Endpoints:** `POST /eval/run`, `GET /eval/history`
**Status:** Implemented

### Phase 10 — Multi-Tenant Isolation

**Description:** `X-SAGE-Tenant` header scopes vector store collections, audit log metadata, and task queue submissions.
**Key Files:** `src/core/tenant.py`
**Status:** Implemented

### Phase 11 — Temporal Durable Workflows

**Description:** Long-running durable workflows via Temporal with LangGraph fallback.
**Key Files:** `src/integrations/temporal_runner.py`
**Config:** `TEMPORAL_HOST` env var
**Status:** Implemented

### Phase 12 — Build Orchestrator (0→1→N Pipeline)

**Description:** Complete product build pipeline from description to deployable software.

**Sub-features:**
- 12.1: Domain detection (13 domains via DOMAIN_RULES)
- 12.2: Workforce registry (19 agents, 5 teams, 32 task types)
- 12.3: Adaptive router (Q-learning, EMA score updates per task_type × agent_role)
- 12.4: Anti-drift checkpoints (crash recovery, drift detection)

**Key Files:** `src/core/build_orchestrator.py`, `src/agents/critic.py`, `src/integrations/openswe_runner.py`
**Endpoint:** `POST /build/start`
**Status:** Implemented

### Phase 13 — Sandboxed Execution (3-Tier Cascade)

**Description:** Three-tier isolation for agent code execution.

| Tier | Runner | Isolation Level |
|---|---|---|
| 1 | OpenShell | NVIDIA container, YAML security policies, SSH |
| 2 | SandboxRunner | Local repo clone, branch isolation |
| 3 | OpenSWE | 3-tier internal: external SWE → LangGraph → LLM direct |

**Key Files:** `src/integrations/openshell_runner.py`, `src/integrations/sandbox_runner.py`, `src/integrations/openswe_runner.py`
**Status:** Implemented

### Phase 14 — Domain-Aware Runners (Open\<Role\> Architecture)

**Description:** Eight specialized runners, each encapsulating a complete execution environment for a role family.

| Runner | Roles | Key Artifacts |
|---|---|---|
| OpenSWE | developer, qa_engineer, devops_engineer | Source code, tests, PRs |
| OpenFW | firmware_engineer, embedded_tester | ARM binaries, HAL drivers |
| OpenEDA | pcb_designer | Schematics, layouts, Gerbers |
| OpenSim | hardware_sim_engineer | SPICE, Verilog, waveforms |
| OpenML | data_scientist | Models, pipelines, metrics |
| OpenDoc | technical_writer, regulatory_specialist | Documents, DHFs, compliance |
| OpenDesign | ux_designer | Wireframes, design tokens |
| OpenStrategy | product_manager, marketing_strategist | PRDs, roadmaps, GTM |

**Key Files:** `src/integrations/base_runner.py` + all Open\<Role\> runner files
**Status:** Implemented

### Phase 15 — Modular Skill Marketplace

**Description:** YAML-based skills with public/private/disabled visibility tiers. JD-sourced prompts. Hot-reload.

**Sub-features:**
- 15.1: JD-sourced skills across 8 families (firmware, PCB, hardware sim, ML, technical writing, UX, product strategy, software)
- 15.2: Visibility tiers with `SAGE_SKILLS_DIR` env var for private skills

**Key Files:** `src/core/skill_loader.py`, `skills/public/*.yaml`
**Endpoints:** Full CRUD at `/skills/*`
**Status:** Implemented

### Phase 16 — N-Provider Multi-Critic

**Description:** Parallel review by any number of LLM providers. Weighted aggregation, disagreement flagging, flaw deduplication.

**Sub-features:**
- 16.1: Auto-discover Gemini CLI as critic provider

**Key Files:** `src/agents/critic.py`
**Method:** `multi_critic_review()`, `dual_critic_review()` (alias)
**Status:** Implemented

### Phase 17 — Agent Gym (Self-Play Training)

**Description:** MuZero/AlphaZero-inspired training loop: play → grade → critique → reflect → compound.

**Sub-features:**
- 17.1: Glicko-2 skill ratings (rating, RD, volatility, confidence intervals)
- 17.2: MuZero-style 5-phase reflection loop
- 17.3: Spaced repetition for failed exercises (+1, +3, +7, +15, +30 session schedule)
- 17.4: Adaptive exercise selection (3-tier: spaced rep → optimal zone → unseen)
- 17.5: SQLite persistence, score trends, weakness analysis, improvement rate
- 17.6: Batch training and peer review

**Key Files:** `src/core/agent_gym.py`
**Endpoints:** Full suite at `/gym/*`
**Status:** Implemented

### Phase 18 — Exercise Catalog (Scalable)

**Description:** ~470 industry-grade seed exercises across 9 domains, expandable to 50,000+ via LLM variants.

**Sub-features:**
- 18.1: Seed exercises across openfw, openswe, openml, openeda, opensim, opendoc, opendesign, openbrowser, openstrategy
- 18.2: LLM-generated variants (10 variant axes per domain)

**Key Files:** `src/core/exercise_catalog.py`
**Endpoints:** `GET /gym/catalog`, `POST /gym/catalog/generate`
**Status:** Implemented

### Phase 19 — gstack Browser Integration

**Description:** Real browser QA via gstack (persistent Chromium daemon). Supplementary runner for qa_engineer, system_tester, ux_designer roles.

**Sub-features:**
- 19.1: Real browser QA via `$B` gstack commands (~100ms/command)
- 19.2: 60 browser exercise seeds across 4 difficulty tiers
- 19.3: Security audit skill (OWASP Top 10 + STRIDE threat model)

**Key Files:** `src/integrations/openbrowser_runner.py`, `skills/public/security_audit.yaml`
**Status:** Implemented

---

## 6. Non-Functional Requirements

### 6.1 Security

| Requirement | Specification |
|---|---|
| **Encryption at rest** | `.sage/audit_log.db` and `.sage/chroma_db/` — LUKS/BitLocker at OS level or SQLCipher for SQLite. Config: `encryption.at_rest: true` |
| **Encryption in transit** | TLS 1.2+ enforced at reverse-proxy. Config: `encryption.in_transit: true` |
| **Execution sandboxing** | All agent code execution through 3-tier cascade (OpenShell → Sandbox → Direct). YAML security policies govern allowed commands, file access, and network rules |
| **API authentication** | All endpoints require authentication. Multi-tenant header `X-SAGE-Tenant` must be validated |
| **Secrets management** | No API keys in config files. All keys via env vars (`ANTHROPIC_API_KEY`, `SLACK_BOT_TOKEN`, etc.) |
| **Audit immutability** | Audit log entries are append-only. No UPDATE/DELETE operations on logged events |
| **OWASP Top 10** | Security audit skill covers all 10 categories via OpenBrowser runner |

### 6.2 Compliance

| Standard | Coverage |
|---|---|
| **IEC 62304** | Medical device software lifecycle — via OpenDoc DHF generation, audit trail, HITL gates |
| **ISO 13485** | Medical device quality management — via proposal store risk classification, approval workflow |
| **ISO 26262** | Automotive functional safety — via OpenFW safety constraints, critic safety scoring |
| **DO-178C** | Avionics software — via OpenFW with avionics domain rules |
| **SOC 2** | Audit log per solution, multi-tenant isolation, encryption at rest and in transit |
| **GDPR** | Per-solution data isolation, `.sage/` directory contains no cross-solution data |
| **WCAG 2.1** | OpenBrowser runner accessibility audit via gstack `$B snapshot -a` |

### 6.3 Performance

| Requirement | Target |
|---|---|
| API response latency (non-LLM, p95) | <200ms |
| API response latency (LLM-backed, p95) | <30s (provider-dependent) |
| Build Orchestrator plan generation | <60s for typical description |
| Agent Gym exercise turn (play + grade) | <120s |
| Vector memory retrieval | <500ms |
| Skill hot-reload | <2s |
| LLM provider switch | <5s |
| UI page load (initial) | <2s |
| SSE streaming first token | <3s |

### 6.4 Reliability

| Requirement | Specification |
|---|---|
| **Anti-drift recovery** | Build Orchestrator checkpoints after every state; `_restore_runs()` on startup recovers in-progress builds |
| **Graceful degradation** | All integrations (LangGraph, AutoGen, Temporal, gstack) degrade gracefully if unavailable |
| **Provider fallback** | N-Provider pool falls back to primary-only if secondary providers are unavailable |
| **Thread safety** | `LLMGateway` singleton protected by `threading.Lock` — single-lane inference is intentional |
| **Test coverage** | `make test` must pass at >98% before any merge to main |

### 6.5 Scalability

| Requirement | Specification |
|---|---|
| **Multi-tenant** | Each tenant scoped independently — vector store collection, audit log, task queue |
| **Solution isolation** | Each solution's `.sage/` directory is fully independent |
| **Wave parallelism** | Independent tasks run in parallel waves — linear scaling with task count |
| **Exercise catalog** | Scalable to 50,000+ exercises via LLM variant generation |
| **Skill registry** | Hot-reload supports unlimited skills from `SAGE_SKILLS_DIR` |

### 6.6 Usability

| Requirement | Specification |
|---|---|
| **Zero API key default** | Gemini CLI, Claude Code CLI, and Ollama all work without API keys |
| **3-YAML solution pattern** | Any new domain expressible as `project.yaml` + `prompts.yaml` + `tasks.yaml` |
| **Onboarding wizard** | New solution from plain-language description in <2 minutes |
| **Runtime provider switch** | `POST /llm/switch` changes provider immediately — no restart |
| **Sidebar module adoption** | Each module can be enabled individually via Settings — no YAML edit required |

---

## 7. Constraints & Dependencies

### Technical Constraints

| Constraint | Detail |
|---|---|
| **Python 3.10+** | Required for TypedDict, match statements, and modern async features |
| **Single-lane LLM** | `threading.Lock` on `LLMGateway` — intentional for predictable context window management |
| **SQLite for audit** | Per-solution SQLite is the compliance record — not replaceable with a remote DB without audit validation |
| **Docker for sandboxed runners** | OpenFW, OpenEDA, OpenSim, OpenML runners require Docker for toolchain containers |
| **gstack for real browser** | OpenBrowser Tier 1 requires gstack installation (`~/.claude/skills/gstack`) |
| **Node.js for CLI providers** | Gemini CLI and Claude Code CLI require Node.js 18+ |

### External Dependencies

| Dependency | Type | Risk | Mitigation |
|---|---|---|---|
| LLM providers (Gemini, Claude, Ollama) | Core | Medium | Multi-provider pool + local fallback (Ollama) |
| LangGraph | Orchestration | Low | Temporal fallback; direct LLM fallback |
| ChromaDB | Vector memory | Medium | LlamaIndex abstraction layer |
| Temporal | Durable workflows | Low | LangGraph fallback |
| Docker | Sandboxing | Medium | SandboxRunner local fallback |
| gstack | Browser testing | Low | LLM simulation fallback |
| Slack | Approval delivery | Low | Feature is additive; web UI approval always available |

### Organizational Constraints

| Constraint | Detail |
|---|---|
| **Solution separation** | Proprietary solutions must never be committed to the SAGE repo. Mount via `SAGE_SOLUTIONS_DIR` |
| **HITL gates non-negotiable** | Solution-level agent proposals must always require human sign-off — no exceptions, no demos mode |
| **Framework domain-blindness** | No solution-specific logic in `src/`. Solutions absorb domain specifics via YAML |
| **Audit log immutability** | Append-only. Required for compliance record integrity |
| **Private skills confidentiality** | Skills with `visibility: private` must never be exported or committed to the public repo |

---

## 8. Appendix: Integration Matrix

| Phase | Feature | Key Files | Config | Status |
|---|---|---|---|---|
| 0 | Langfuse observability | `llm_gateway.py` | `observability.langfuse_enabled` | Done |
| 1 | LlamaIndex + LangChain + mem0 | `vector_store.py`, `langchain_tools.py` | `memory.backend` | Done |
| 1.5 | MCP tool registry | `mcp_registry.py` | `solutions/<name>/mcp_servers/` | Done |
| 2 | n8n webhook | `api.py` | `N8N_WEBHOOK_SECRET` | Done |
| 3 | LangGraph orchestration | `langgraph_runner.py` | `orchestration.engine` | Done |
| 4 | AutoGen code agent | `autogen_runner.py` | Docker | Done |
| 5 | SSE streaming | `api.py` | — | Done |
| 6 | Onboarding wizard | `onboarding.py` | — | Done |
| 7 | Knowledge base CRUD | `vector_store.py` | — | Done |
| 8 | Slack two-way approval | `slack_approver.py` | `SLACK_BOT_TOKEN` | Done |
| 9 | Eval/benchmarking | `eval_runner.py` | `solutions/<name>/evals/` | Done |
| 10 | Multi-tenant isolation | `tenant.py` | `X-SAGE-Tenant` | Done |
| 11 | Temporal durable workflows | `temporal_runner.py` | `TEMPORAL_HOST` | Done |
| 12 | Build Orchestrator | `build_orchestrator.py` | — | Done |
| 13 | 3-tier sandboxed execution | `openshell_runner.py`, `sandbox_runner.py` | — | Done |
| 14 | Domain-Aware Runners | `base_runner.py` + Open\<Role\> files | — | Done |
| 15 | Modular Skill Marketplace | `skill_loader.py`, `skills/public/` | `SAGE_SKILLS_DIR` | Done |
| 16 | N-Provider Multi-Critic | `critic.py` | `ProviderPool` | Done |
| 17 | Agent Gym | `agent_gym.py` | — | Done |
| 18 | Exercise Catalog | `exercise_catalog.py` | — | Done |
| 19 | gstack Browser Integration | `openbrowser_runner.py` | gstack install | Done |

---

*Document maintained in `/docs/product/PRD_SAGE_Framework.md`. Update when features change status or new phases are added.*
