# SAGE Framework — Claude Code Instructions

@.claude/SOUL.md

---

## What SAGE Is (30-Second Version)

**Lean development methodology on steroids, powered by agentic AI.**

Agents surface signals, search compounding memory, propose actions, wait for human approval, and learn from every correction. The loop compounds — each decision makes the next one better. Human judgment is always in the loop for agent proposals. This is not optional.

---

## Quick Start Commands

```bash
make venv               # Create .venv and install all deps (first time)
make venv-minimal       # Low-RAM machine — skips ChromaDB/embeddings
make run PROJECT=xxx    # Start FastAPI backend on :8000
make ui                 # Start Vite frontend on :5173
make test               # Framework unit tests
make test-all           # Framework + all solution tests

# sage-desktop (Tauri + Python sidecar, no sockets, no ports)
make desktop-install    # One-time npm install in sage-desktop/
make desktop-dev        # Tauri dev loop (Rust + Vite + sidecar)
make test-desktop       # Sidecar (pytest) + Rust (cargo) + React (vitest)
make test-desktop-e2e   # Round-trip real sidecar subprocess
```

## Core Tech Stack

- **Backend**: Python 3.12 + FastAPI + SQLite
- **Frontend**: React 18 + TypeScript + Vite
- **LLM**: Multi-provider (Gemini, Claude Code, Ollama, local)
- **Memory**: ChromaDB vector store + audit logs
- **Testing**: pytest + comprehensive TDD coverage

## Project Structure (Essential)

```
src/core/               LLM gateway, build orchestrator, agent gym, orchestrator intelligence (9 modules)
src/agents/             Universal, Analyst, Developer, Monitor, Planner, Critic, Product Owner
src/interface/api.py    FastAPI — HTTP interface for web UI and VS Code extension
solutions/              Solution configurations (project.yaml, prompts.yaml, tasks.yaml)
web/src/                React dashboard — HTTP interface; reads from FastAPI only
web/src-tauri/          Tauri shell that bundles web/ into a window (still needs :8000)
sage-desktop/           Third interface: Tauri + Python sidecar via stdin/stdout NDJSON.
                        No HTTP, no ports — for port-restricted environments.
                        See .claude/docs/interfaces/desktop-gui.md
.claude/docs/           Claude Code instruction documentation (see below)
```

---

## Documentation Directory (→ Read These for Details)

### 📋 Core Architecture & Design
- **[Architecture](.claude/docs/architecture.md)** — System design, patterns, domain runners, memory architecture
- **[Conventions](.claude/docs/conventions.md)** — Coding standards, file organization, testing guidelines
- **[Setup Guide](.claude/docs/setup.md)** — Installation, LLM providers, environment configuration  
- **[Workflows](.claude/docs/workflows.md)** — SAGE lean loop, approval gates, build orchestrator flows
- **[Technical Decisions](.claude/docs/decisions.md)** — ADRs, rationale, alternatives considered

### 🖥️ Interfaces
- **[Desktop (sage-desktop)](.claude/docs/interfaces/desktop-gui.md)** — No-sockets Tauri + Python sidecar app; when to use vs. web/VS Code. Phase 2 ships Settings + Backlog pages and a queue tile on Status. Phase 3a adds the runtime solution switcher (sidecar respawn + `solution-switched` event). Phase 3c adds the onboarding wizard (`/onboarding` route + `onboarding.generate` RPC) so new solutions can be created without FastAPI. Phase 3d adds the Build Console (`/builds` route + `builds.{start,list,get,approve}` RPC) so the BuildOrchestrator can be driven end-to-end from the desktop. Phase 3b adds the `/yaml` route + `yaml.{read,write}` RPC so the solution's YAML triad is editable without leaving the app (YAML syntax validated sidecar-side before the file is touched). Phase 5b adds the `/constitution` route + `constitution.{get,update,preamble,check_action}` RPC so operators can author per-solution principles, constraints, voice, and decision rules from the desktop (validation runs before disk writes; agent-proposed constitution changes still flow through the `yaml_edit` proposal queue).

### 🔧 Feature Documentation  
- **[Agent Gym](.claude/docs/features/agent-gym.md)** — Self-play training, Glicko-2 ratings, exercise catalog
- **[Regulatory Compliance](.claude/docs/features/regulatory-compliance.md)** — IEC 62304, 21 CFR Part 11, traceability matrices
- **[Orchestrator Intelligence](.claude/docs/features/orchestrator-intelligence.md)** — 9 SOTA modules: reflection, beam search, consensus, event bus, budget, tools, spawner, backtrack, memory planner
- **[Constitution](.claude/docs/features/constitution.md)** — Per-solution blue book: principles, constraints, voice, decision rules, version history
- **[Collective Intelligence](.claude/docs/features/collective-intelligence.md)** — Git-backed multi-agent knowledge sharing: learnings, help requests, semantic search

---

## Universal Coding Standards (Never Violate)

### The Five Laws

1. **Agents propose. Humans decide. Always** — for agent proposals (not framework control)
2. **Eliminate waste at every layer** — No sprint ceremonies, no manual steps agents can do correctly
3. **Compounding intelligence over cold-start lookup** — Every correction feeds vector memory
4. **Vertical slices, not horizontal layers** — Complete flows, not partial implementations
5. **Atomic verification is non-negotiable** — Every proposal must be verifiable before approval

### Critical Boundaries

- **Framework vs Solutions**: `src/` knows nothing about specific industries. Solutions plug in via YAML.
- **Approval Tiers**: Framework control executes immediately. Agent proposals require HITL approval.
- **Data Isolation**: Each solution gets `.sage/` directory. Framework repo contains no user data.

### What to Never Do

- Never commit proprietary solutions to this repo — mount via `SAGE_SOLUTIONS_DIR`
- Never bypass HITL approval for agent proposals (`yaml_edit`, `implementation_plan`, `code_diff`)
- Never short-circuit feedback ingestion (Phase 5) — every rejection teaches
- Never hardcode solution names in `src/` — framework is domain-blind
- Never use `print()` — use `self.logger` or `logging.getLogger()`

---

## LLM Provider Quick Switch

Default: Gemini CLI (no API key). Switch anytime:

```bash
# Runtime switch (immediate)
curl -X POST http://localhost:8000/llm/switch -d '{"provider": "ollama", "model": "llama3.2"}'

# Or edit config.yaml
llm:
  provider: "ollama"
  ollama_model: "llama3.2"
```

Providers: `gemini` (default), `claude-code`, `ollama`, `local`, `claude` (API key required)

---

## Approval Gate (Critical Understanding)

| Tier | Operations | Behavior |
|---|---|---|
| **Framework Control** | `/config/switch`, `/llm/switch`, `/config/modules` | **Executes immediately** |
| **Agent Proposals** | `yaml_edit`, `implementation_plan`, `code_diff`, `agent_hire` | **Requires human approval** |

The approval inbox (`/approvals`) should only contain agent proposals, never routine framework operations.

---

## New Solution Setup

**Option 1 — Onboarding Wizard (recommended):**
```bash
curl -X POST http://localhost:8000/onboarding/generate \
  -d '{"description": "Medical device software", "solution_name": "medtech"}'
```

**Option 2 — Manual:**
```bash
cp -r solutions/starter solutions/my_domain
# Edit project.yaml, prompts.yaml, tasks.yaml
make run PROJECT=my_domain
```

---

## Available Skills

| Skill | Usage |
|---|---|
| `/run-tests` | Run test suite — scope: `all`, `api`, `llm`, or solution name |
| `/new-solution` | Scaffold new solution: `/new-solution robotics` |
| `/check-api` | Smoke-test all live endpoints |
| `/edit-solution-yaml` | Edit + hot-reload: `/edit-solution-yaml meditation_app prompts ...` |

---

## Testing Standards (TDD Required)

- **Write tests first** for all new features
- **Run `make test`** before and after any change to `src/`
- **Use descriptive names** that explain what is being tested
- **Mock external dependencies** appropriately
- **Follow AAA pattern**: Arrange, Act, Assert

### Test Organization
- Unit tests: `tests/test_*.py`
- Integration tests: Cover complete workflows  
- Use pytest fixtures for common data
- Ensure tests are deterministic

---

## Adding New Components (Checklist)

### New API Endpoint
1. Add to `src/interface/api.py` with lazy import
2. Update `web/src/api/client.ts` with typed fetch
3. Add tests to `tests/test_api.py`

### New UI Page  
1. Create `web/src/pages/MyPage.tsx`
2. Add route in `web/src/App.tsx`
3. Add nav entry in `web/src/components/layout/Sidebar.tsx`
4. Add title mapping in `web/src/components/layout/Header.tsx`

**Example**: Product Backlog Management (`ProductBacklog.tsx`) provides 4-tab workflow for requirements gathering with Product Owner agent integration.

### New Agent Role
1. Add to `solutions/<name>/prompts.yaml` (role + system prompt)
2. Add task type to `solutions/<name>/tasks.yaml` if needed
3. Wire in `src/agents/universal.py` for routing

**Example**: Product Owner agent converts customer inputs to structured product requirements using 5W1H methodology and MoSCoW prioritization.

---

## The Two Backlogs — Critical Distinction

| Scope | Owned by | Workflow | Where tracked |
|---|---|---|---|
| **Solution** | Builder's team | SAGE Improvements → Solution Backlog | Internal approval queue |
| **SAGE Framework** | Open source community | SAGE Improvements → GitHub Issues | External contribution |

Every feature request has a `scope` field. Never mix them.

---

## Common Debugging

- **Python not found**: `source .venv/bin/activate`
- **LLM fails**: Check provider setup in [Setup Guide](.claude/docs/setup.md)
- **Tests fail**: `make test` and fix before proceeding
- **Solution won't load**: Verify YAML syntax and required fields
- **UI won't start**: Check Node.js version and `npm install`

---

## Where to Get Help

- `/help` — Built-in help command
- **Framework Issues**: https://github.com/anthropics/claude-code/issues
- **Architecture Questions**: [.claude/docs/architecture.md](.claude/docs/architecture.md)
- **Setup Problems**: [.claude/docs/setup.md](.claude/docs/setup.md)
- **Workflow Confusion**: [.claude/docs/workflows.md](.claude/docs/workflows.md)

---

**Remember**: This is production software used in regulated industries. Every change has downstream consequences. When in doubt, read the detailed docs linked above.