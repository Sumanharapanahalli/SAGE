# SAGE Framework Architecture

## System Design Overview

SAGE follows a modular, agent-based architecture built on lean development principles.

## Core Architecture Patterns

### 0→1 Greenfield and 1→N Refinement

The Build Orchestrator (`src/core/build_orchestrator.py`) uses 8 agentic patterns that apply to both greenfield builds and incremental refinement.

#### Core Patterns

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

### Domain-Aware Runners — Open\<Role\> Architecture

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
| **OpenBrowser** | `openbrowser_runner.py` | qa_engineer*, system_tester*, ux_designer* | QA reports, screenshots, a11y audits | — (gstack) |
| **OpenStrategy** | `openstrategy_runner.py` | product_manager, marketing_strategist, operations_manager | PRDs, roadmaps, GTM plans | — |
| **OpenTerminal** | `openterminal_runner.py` | terminal_operator, shell_expert | Command output, scripts, reports | — (tmux) |
| **AutoResearch** | `auto_research.py` | research_engineer, ml_researcher | Experiment results, metrics, git checkpoints | — |

### Sandboxed Execution — 3-Tier Cascade

Agent code execution uses a three-tier isolation cascade. The orchestrator tries the most isolated tier first and falls back down.

| Tier | Runner | Isolation | When used |
|---|---|---|---|
| **1. OpenShell** | `openshell_runner.py` | NVIDIA container sandbox, YAML security policies, SSH-based exec | Full container isolation available (GPU workloads, untrusted code) |
| **2. SandboxRunner** | `sandbox_runner.py` | Local repo clone, branch isolation, restricted file ops | Container unavailable, local execution acceptable |
| **3. OpenSWE** | `openswe_runner.py` | 3-tier internal cascade: external SWE agent → LangGraph workflow → LLM direct | Autonomous coding tasks (explore → implement → test → PR) |

## Memory and Knowledge Architecture

**The vector store is the institutional memory.**
It holds prior analyses, human corrections, domain decisions, and known patterns. Always search it before generating. Always update it after human feedback.

**The audit log is the compliance record and training signal.**
Every event — analysis, approval, rejection, feedback — is written to SQLite with a trace_id. This is both the compliance guarantee for regulated industries and the ground truth for measuring agent quality over time.

**Compounding context beats cold-start retrieval.**
A correction stored today makes tomorrow's analysis better without any model change. Design all agents to write meaningful feedback to the vector store on rejection — not just "rejected", but the human's actual reasoning.

## The .sage/ Directory — Solution Runtime Isolation

Every solution gets its own `.sage/` directory, auto-created at first run inside the solution folder. This is the **only place** SAGE writes runtime data.

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

## Reference Architectures

These are not dependencies — they are thinking influences:

| Source | Principle Borrowed |
|---|---|
| **GSD (Get Shit Done)** | Five-phase lean loop, wave scheduling, vertical slices, state persistence, no enterprise ceremony |
| **Rowboat** | Compounding memory, knowledge graph from interactions, transparent inspectable agent actions |
| **APM (Agent Package Manager)** | YAML-as-agent-manifest, declarative dependency model, versioned agent configs |
| **Agent Lightning** | Non-invasive audit instrumentation, closed-loop improvement, selective agent optimization |
| **Memento (arXiv 2508.16153)** | Behavioral optimization via memory retrieval (not retraining), decouple LLM from policy improvement |
| **Paperclip (paperclipai/paperclip)** | Board-of-directors governance model, immutable audit log per company, agent-hire requiring explicit human approval, per-agent budget controls |
| **Aider** | Every agent change is a reversible git commit; unified diff preview before apply; repo map for multi-file coherence |
| **Claude Code** | Pre/post action hooks declarable per project; `.claude/` per-project runtime directory; persistent context injection via CLAUDE.md |
| **DeerFlow (bytedance/deer-flow)** | Supervisor + sub-agent topology, skills as Markdown files, Docker "AIO Sandbox", adaptive replanning, tiered memory, long-running task durability via LangGraph checkpointing |