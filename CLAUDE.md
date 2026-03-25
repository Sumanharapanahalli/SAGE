# SAGE Framework — Claude Code Instructions

@.claude/SOUL.md

---

## What SAGE Is (30-Second Version)

**Lean development methodology on steroids, powered by agentic AI.**

Agents surface signals, search compounding memory, propose actions, wait for human approval, and learn from every correction. The loop compounds — each decision makes the next one better. Human judgment is always in the loop for agent proposals. This is not optional.

---

## Project Layout (Quick Reference)

```
src/                    Framework Python source
  core/                 LLM gateway, project loader, queue manager, modules
    llm_gateway.py      Providers: Gemini CLI, Claude Code CLI, Ollama, local, generic-cli
    onboarding.py       LLM-powered solution generator from plain-language descriptions
    eval_runner.py      Eval suite runner — keyword scoring, SQLite history
    tenant.py           Multi-tenant context (X-SAGE-Tenant header, ContextVar)
    proposal_store.py   Pending proposals — SQLite-backed, risk-classified, expiry-aware
    proposal_executor.py Dispatch approved proposals to their side-effect handlers
    build_orchestrator.py 0→1→N product build pipeline — domain detection (13 domains),
                         DOMAIN_RULES, WORKFORCE_REGISTRY (19 agents, 5 teams),
                         AdaptiveRouter (Q-learning), 32 task types, anti-drift checkpoints
  agents/               Analyst, Developer, Monitor, Planner, Universal, Critic
    critic.py           Actor-critic reviewer — scores plan, code, and integration quality
  interface/api.py      FastAPI — the only public interface
  memory/               Audit logger, vector memory (CRUD + bulk import), long_term_memory.py
  modules/              Zero-dependency nano-modules
  integrations/         External framework connectors (all graceful degradation)
    mcp_registry.py     MCP tool discovery + invocation
    langgraph_runner.py LangGraph orchestration (interrupt → approve → resume)
    autogen_runner.py   AutoGen code planning + Docker sandboxed execution
    slack_approver.py   Slack Block Kit proposals + /webhook/slack callbacks
    temporal_runner.py  Temporal durable workflows (LangGraph fallback)
    langchain_tools.py  LangChain tool loader per solution
    openswe_runner.py   OpenSWE autonomous coding agent — repo explore, implement, test, PR
    base_runner.py      BaseRunner ABC, RunResult/VerificationReport, runner registry
    openswe_adapter.py  OpenSWE → BaseRunner adapter (wraps existing runner)
    openfw_runner.py    OpenFW firmware runner — cross-compile, static analysis, binary metrics
    openeda_runner.py   OpenEDA PCB runner — schematic, layout, DRC, ERC, Gerber
    opensim_runner.py   OpenSim HW simulation — SPICE, Verilog, waveforms, timing
    openml_runner.py    OpenML machine learning — train, evaluate, experiment track
    opendoc_runner.py   OpenDoc documentation — drafting, compliance, cross-reference
    opendesign_runner.py OpenDesign UX — wireframes, accessibility, design tokens
    openstrategy_runner.py OpenStrategy planning — PRDs, GTM, roadmaps
    openshell_runner.py NVIDIA OpenShell sandboxed execution — YAML policies, SSH-based exec
    sandbox_runner.py   Local repo sandbox — clone, branch isolation, file ops, safe execution

web/src/                React 18 + TypeScript dashboard
  pages/                One file per route
  components/layout/    Sidebar, Header
  components/theme/     ThemeProvider — reads theme: block from project.yaml → CSS vars
  registry/modules.ts   MODULE_REGISTRY — all 16+ modules, visibility, access control
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
  board_games/          Cross-platform board games platform (25+ games, AI opponents)
  automotive/           Automotive infotainment & telematics
  avionics/             Avionics software team
  iot_medical/          IoT medical device monitoring
  railways/             Railway systems engineering
  + 7 more in solutions/  All follow the same 3-YAML pattern
  <your-solution>/      Your solutions live in a SEPARATE private repo, mounted via
                        SAGE_SOLUTIONS_DIR env var — never in this repo.
                        Each solution auto-creates a .sage/ directory at first run:
                          .sage/audit_log.db   ← proposals, approvals, audit trail
                          .sage/chroma_db/     ← vector knowledge store
                        .sage/ is runtime state — gitignored, never committed.

config/config.yaml      Base LLM / memory / integration / GitHub settings
.venv/                  Python virtual environment (Windows: Scripts/, Unix: bin/)
```

---

## Key Commands

```bash
make venv               # Create .venv and install all deps (first time)
make venv-minimal       # Low-RAM machine — skips ChromaDB/embeddings
make run PROJECT=xxx    # Start FastAPI backend on :8000
make ui                 # Start Vite frontend on :5173
make test               # Framework unit tests
make test-all           # Framework + all solution tests
make test-api           # Only api.py endpoint tests
make test-compliance    # IQ/OQ/PQ validation suite
make test-solution PROJECT=xxx  # Single solution's tests
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

Or switch at runtime (executes immediately, no approval): `POST /llm/switch {"provider": "ollama", "model": "llama3.2"}`

---

## Available Skills

| Skill | Usage |
|---|---|
| `/run-tests` | Run tests — optionally pass a scope: `all`, `api`, `llm`, or a solution name |
| `/new-solution` | Scaffold a new solution from the starter template: `/new-solution robotics` |
| `/check-api` | Smoke-test all live API endpoints |
| `/edit-solution-yaml` | Edit a solution YAML and hot-reload: `/edit-solution-yaml meditation_app prompts ...` |

---

## Approval Gate — Two Tiers (Read This First)

**Not all actions go through the approval queue. Framework control ops execute immediately. Only solution-level agent proposals require human sign-off.**

| Tier | Operations | Behaviour |
|---|---|---|
| **Framework control** | `POST /config/switch`, `POST /llm/switch`, `POST /config/modules` | **Executes immediately.** No proposal created. Returns `{"status": "switched"}`. |
| **Solution agent proposals** | `yaml_edit`, `implementation_plan`, `code_diff`, `knowledge_*`, `agent_hire` | **Requires HITL approval.** Creates a `Proposal` in the store. Human reviews at `/approvals`. Nothing executes until approved. |

The approval inbox (`/approvals` page) should only contain **solution-level AI proposals** — never routine framework control operations. Keep them separate or user trust erodes.

SAGE-scope feature requests (improvements to the framework itself) are routed to **GitHub Issues/PRs** — not the internal approval queue. Use the "Open GitHub Issue" button on the SAGE Framework Ideas tab.

---

## Integration Phases (what is built and where)

| Phase | Feature | Key files | Config |
|---|---|---|---|
| 0 | Langfuse observability | `llm_gateway.py` | `observability.langfuse_enabled: true` |
| 1 | LlamaIndex + LangChain + mem0 | `vector_store.py`, `langchain_tools.py`, `memory/long_term_memory.py` | `memory.backend: llamaindex` |
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
| 12 | Build Orchestrator (0→1→N) | `build_orchestrator.py`, `critic.py`, `openswe_runner.py` | `POST /build/start` |
| 12.1 | Domain-aware build detection | `build_orchestrator.py` (`DOMAIN_RULES` — 13 domains) | Auto-detected from description |
| 12.2 | Workforce registry + 32 task types | `build_orchestrator.py` (`WORKFORCE_REGISTRY` — 19 agents, 5 teams) | — |
| 12.3 | Adaptive router (Q-learning) | `build_orchestrator.py` (`AdaptiveRouter`) | `GET /build/router/stats` |
| 12.4 | Anti-drift checkpoints | `build_orchestrator.py` | `BUILD_DRIFT_WARNING` audit events |
| 13 | Sandboxed Execution (3-tier cascade) | `openshell_runner.py`, `sandbox_runner.py`, `openswe_runner.py` | See Sandbox Execution section |
| 14 | Domain-Aware Runners (Open\<Role\>) | `base_runner.py`, `openfw_runner.py`, `openeda_runner.py`, `opensim_runner.py`, `openml_runner.py`, `opendoc_runner.py`, `opendesign_runner.py`, `openstrategy_runner.py` | See Domain-Aware Runners section |

---

## Sandboxed Execution — 3-Tier Cascade

Agent code execution uses a three-tier isolation cascade. The orchestrator tries the most isolated tier first and falls back down.

| Tier | Runner | Isolation | When used |
|---|---|---|---|
| **1. OpenShell** | `openshell_runner.py` | NVIDIA container sandbox, YAML security policies, SSH-based exec | Full container isolation available (GPU workloads, untrusted code) |
| **2. SandboxRunner** | `sandbox_runner.py` | Local repo clone, branch isolation, restricted file ops | Container unavailable, local execution acceptable |
| **3. OpenSWE** | `openswe_runner.py` | 3-tier internal cascade: external SWE agent → LangGraph workflow → LLM direct | Autonomous coding tasks (explore → implement → test → PR) |

**OpenShell** (`src/integrations/openshell_runner.py`):
- Connects to NVIDIA OpenShell sandbox environments via SSH
- Security policies defined in YAML (allowed commands, file access, network rules)
- Supports GPU-accelerated execution for ML/training tasks
- Graceful degradation: returns error dict if OpenShell is unavailable

**SandboxRunner** (`src/integrations/sandbox_runner.py`):
- Clones the solution repo into a temporary working directory
- Creates isolated branches for each execution
- Restricts file operations to the sandbox directory
- Provides `execute()`, `read_file()`, `write_file()`, `list_files()` primitives
- Cleanup on completion (configurable retain for debugging)

**OpenSWE** (`src/integrations/openswe_runner.py`):
- Autonomous coding agent: repo explore → implement → test → create PR
- Internal 3-tier fallback: external SWE agent (if available) → LangGraph orchestrated → direct LLM generation
- Each tier produces the same output format: `{files_changed, tests_passed, pr_url}`

---

## Domain-Aware Runners — Open\<Role\> Architecture

The 3-tier isolation cascade (OpenShell → Sandbox → Direct) is orthogonal to the **domain runner**. Each runner encapsulates a complete execution environment for a role family: toolchain, workflow, verification, and experience accumulation.

| Runner | File | Roles | Artifacts | Docker Image |
|---|---|---|---|---|
| **OpenSWE** | `openswe_adapter.py` | developer, qa_engineer, system_tester, devops_engineer, localization_engineer | Source code, tests, PRs | — |
| **OpenFW** | `openfw_runner.py` | firmware_engineer, embedded_tester | ARM binaries, HAL drivers, firmware | `sage/firmware-toolchain` |
| **OpenEDA** | `openeda_runner.py` | pcb_designer | Schematics, PCB layouts, Gerbers, BOMs | `sage/pcb-toolchain` |
| **OpenSim** | `opensim_runner.py` | hardware_sim_engineer | SPICE netlists, Verilog, waveforms | `sage/hw-simulation` |
| **OpenML** | `openml_runner.py` | data_scientist | Models, pipelines, metrics | `sage/ml-toolchain` |
| **OpenDoc** | `opendoc_runner.py` | technical_writer, regulatory_specialist, legal_advisor, safety_engineer, business_analyst, financial_analyst, analyst | Documents, DHFs, compliance reports | `sage/doc-toolchain` |
| **OpenDesign** | `opendesign_runner.py` | ux_designer | Wireframes, design tokens, SVGs | `sage/design-toolchain` |
| **OpenStrategy** | `openstrategy_runner.py` | product_manager, marketing_strategist, operations_manager | PRDs, roadmaps, GTM plans | — |

All runners implement `BaseRunner` (`base_runner.py`) with four required methods:
- `execute(task, workspace, sandbox_handle)` → `RunResult`
- `verify(result, task)` → `VerificationReport`
- `get_exercises(difficulty)` → `list[Exercise]` (for Agent Gym)
- `grade_exercise(exercise, result)` → `ExerciseScore`

The orchestrator selects the correct runner via `get_runner_for_role(agent_role)`. If the role is a software role, OpenSWE handles it. If it's firmware, OpenFW runs cross-compilation. If it's PCB, OpenEDA runs DRC/ERC. Each runner knows what "verified" means in its domain.

---

## Agentic Patterns — 0→1 Greenfield and 1→N Refinement

The Build Orchestrator (`src/core/build_orchestrator.py`) uses 8 agentic patterns that apply to both greenfield builds and incremental refinement. The patterns are the same; the scope differs.

### Core Patterns

| Pattern | Implementation | Purpose |
|---|---|---|
| **ReAct** (Reason+Act) | Per-task agent loop: observe → think → act → observe | Each agent reasons about its task before acting |
| **Hierarchical Task Decomposition** | LLM decomposes description → task graph (32 task types) | Breaks ambiguous goals into concrete, typed tasks |
| **Wave-Based Parallel Execution** | `_compute_waves()` groups independent tasks | Tasks without dependencies run in parallel waves |
| **Adaptive Router** (Q-learning) | `AdaptiveRouter` — `scores[task_type][agent_role]` EMA updates | Routes tasks to best-performing agent, learns over time |
| **Actor-Critic** | `CriticAgent` — `review_plan()`, `review_code()`, `review_integration()` | Scores quality (0-100), identifies flaws before human review |
| **HITL Gates** | `awaiting_plan_approval`, `awaiting_final_approval` states | Human sign-off at plan and integration stages |
| **Iterative Refinement** | Critic score < threshold → retry with critic feedback | Agents improve output based on structured critique |
| **Anti-Drift Checkpoints** | `_checkpoint()` after each state, `_restore_runs()` on startup | Crash recovery + drift detection (`BUILD_DRIFT_WARNING`) |

### 0→1 Greenfield Build

Full pipeline: `POST /build/start` with a product description.

```
Description → Domain Detection (13 domains via DOMAIN_RULES)
  → Workforce Assembly (19 agents, 5 teams from WORKFORCE_REGISTRY)
  → Hierarchical Decomposition (LLM → task graph)
  → Critic reviews plan (score 0-100)
  → HITL approval gate
  → Wave execution (parallel independent tasks)
  → Critic reviews code per task
  → Integration merge
  → Critic reviews integration
  → HITL final approval
  → Completed
```

Key 0→1 specifics:
- Domain detection auto-selects rules (compliance, testing, toolchains)
- Full workforce assembled — all relevant agents activated
- Task graph is complete: architecture → implementation → testing → deployment
- AdaptiveRouter starts with uniform scores, learns during the build

### 1→N Refinement

Same orchestrator, scoped to changes. Triggered by feature requests, bug fixes, or improvement proposals.

Key 1→N differences:
- Domain already known — skips detection
- Workforce is stable — router has learned agent strengths
- Decomposition scoped to the change, not the whole product
- Critic calibration is higher (knows existing quality baseline)
- AdaptiveRouter scores are warm — compounds from prior builds
- Anti-drift checkpoints compare against established baseline

The feedback loop compounds: every 0→1 build teaches the router and critic, making subsequent 1→N refinements faster and higher quality.

## The .sage/ Directory — Solution Runtime Isolation

Every solution gets its own `.sage/` directory, auto-created at first run inside the solution folder. This is the **only place** SAGE writes runtime data. The framework itself writes nothing.

```
your-solutions-repo/
  board_games/
    project.yaml          ← committed to your private repo
    prompts.yaml          ← committed
    tasks.yaml            ← committed
    .sage/                ← auto-created, NEVER committed
      audit_log.db        ← all proposals, approvals, feature requests, audit trail
      chroma_db/          ← vector knowledge store
```

**Why this matters:**
- Two solutions on the same SAGE instance have zero data overlap
- Moving or archiving a solution takes its entire history with it
- The SAGE framework repo contains no user data, ever
- Regulated industries: the `.sage/audit_log.db` is the per-solution compliance record

**Setup for your private solutions repo:**
```bash
export SAGE_SOLUTIONS_DIR=/path/to/your-private-solutions-repo
make run PROJECT=board_games   # .sage/ auto-created on first start
```

Add `.sage/` to your private solutions repo's root `.gitignore`. The `starter/` template ships with this pre-configured.

---

## Solution Branding & Incremental Module Adoption

Each solution can control its **visual identity** and **which modules are active**.

### Custom branding (project.yaml → ThemeProvider → CSS vars)

Add a `theme:` block to any solution's `project.yaml`:
```yaml
theme:
  sidebar_bg:     "#0f172a"   # --sage-sidebar-bg
  sidebar_text:   "#94a3b8"   # --sage-sidebar-text
  badge_bg:       "#1e293b"   # --sage-badge-bg
  badge_text:     "#38bdf8"   # --sage-badge-text
```
The sidebar logo becomes the solution name. The browser tab title tracks the active solution. The fallback is `SAGE[ai]` when no theme is defined.

### Incremental module adoption

`active_modules` in `project.yaml` controls exactly what appears in the sidebar:
```yaml
active_modules:
  - dashboard
  - analyst
  - improvements   # add modules one by one as the team is ready
```
Empty list (`[]`) means show all modules (framework default). Add more via **Settings → Modules** in the UI — no YAML edit needed. Each module a user enables persists immediately via `POST /config/modules` (no approval required).

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
and returns immediately loadable YAML. Then switch instantly: `POST /config/switch {"project": "surgical_robotics"}`.

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

## Sidebar Nav Architecture (post-redesign)

The sidebar is a 3-column layout: `SolutionRail` (44px) + `Sidebar` (220px) + content.

**SolutionRail** (`[data-tour="solution-rail"]`): 2-letter avatars per solution, "+" opens OnboardingWizard, Building2 icon links to /org-graph.

**SolutionSwitcher**: shows active solution name + ChevronsUpDown. Dropdown lists all solutions. When `isToured(activeId)` is true, shows "Restart tour" option at the bottom.

**StatsStrip** (`[data-tour="stats-strip"]`): 3 tiles (APPROVALS red, QUEUED amber, AGENTS green), 10s polling, side="bottom" tooltips.

**5-area accordion** (one open at a time, auto-expands to match current route):
| Area | Accent | data-tour | Routes |
|---|---|---|---|
| Work | `#ef4444` | `area-work` | `/`, `/approvals`, `/queue`, `/live-console` |
| Intelligence | `#a78bfa` | `area-intelligence` | `/analyst`, `/developer`, `/monitor`, `/agents`, `/improvements`, `/workflows`, `/goals` |
| Knowledge | `#10b981` | `area-knowledge` | `/knowledge`, `/activity`, `/audit`, `/costs` |
| Organization | `#3b82f6` | `area-organization` | `/org-graph`, `/onboarding` |
| Admin | `#475569` | `area-admin` | `/llm`, `/yaml-editor`, `/access-control`, `/integrations`, `/settings` |

**TourContext** (`web/src/context/TourContext.tsx`): wraps the app in `App.tsx`, provides `useTourContext()` with `tourState`, `startTour`, `nextStop`, `prevStop`, `skipTour`, `isToured`, `restartTour`, `wizardOpen`, `openWizard`, `closeWizard`.

**TourOverlay**: 6-stop spotlight using `getBoundingClientRect` + 4 overlay rects. Stops target `[data-tour="stats-strip"]`, `[data-tour="nav-approvals"]`, `[data-tour="nav-queue"]`, `[data-tour="area-intelligence"]`, `[data-tour="area-knowledge"]`, `[data-tour="solution-rail"]`. Stores toured solution IDs in localStorage key `sage_toured_solutions`.

**Tooltip implementation**: Tooltip component uses `position: fixed` with coordinates computed from `getBoundingClientRect()` on the trigger element. This ensures tooltips always render above the nav's `overflow: auto` clipping boundary and are visible over any adjacent panel.

## Adding a New UI Page

All five changes together, nothing skipped:
1. Create `web/src/pages/MyPage.tsx`
2. Add the route in `web/src/App.tsx` (`<Route path="/my-page" element={<MyPage />} />`)
3. Add the nav entry in `web/src/components/layout/Sidebar.tsx` (NAV_AREAS array — pick the correct area)
4. Add the module entry to `web/src/registry/modules.ts` (MODULE_REGISTRY)
5. Add `'/my-page': 'AreaName'` to `ROUTE_TO_AREA` in `web/src/components/layout/Header.tsx`

**Path conflict rule**: every nav item's `to` must be unique across all areas. Two items with the same `to` will cause the first match to be highlighted as active for both routes.

For solution-specific pages, follow the same pattern but put them in `web/src/pages/solutions/<name>/`. Note in CLAUDE.md that framework-agnostic pages go in `web/src/pages/`; solution-specific pages belong in a solution fork.

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
- Never bypass the audit log
- **Never bypass the HITL approval gate for solution-level agent proposals** — `yaml_edit`, `implementation_plan`, `code_diff`, `knowledge_delete`, `agent_hire` must always require human sign-off. Framework control ops (`config_switch`, `llm_switch`, `config_modules`) are intentionally immediate.
- Never remove the `threading.Lock` from `LLMGateway`
- Always use `self.logger` not `print()`
- Never short-circuit feedback ingestion (Phase 5) — every rejection teaches
- Run `make test` before and after any change to `src/`
