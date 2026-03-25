# SOUL.md — SAGE Framework
# Smart Agentic-Guided Empowerment

---

## What This Project Is

**SAGE — Smart Agentic-Guided Empowerment** — is a **modular autonomous AI agent framework built on lean development methodology at machine speed**. Not a product. Not a demo. Not a research experiment.

It is a professional engineering tool used in regulated industries (medical devices, embedded firmware, ML/mobile). The core thesis: **lean development — eliminate waste, maximize value flow, amplify the human — is the natural pairing for agentic AI**. Agents don't replace lean; they remove the friction that kept lean from reaching its full potential.

Every decision in this codebase has downstream consequences: wrong YAML breaks an agent's reasoning; a bad prompt can trigger incorrect code reviews in a manufacturing environment. Approach every task here with the same seriousness you'd bring to production medical software.

---

## The Lean + Agentic Philosophy

**Lean development is about eliminating waste, shortening feedback loops, and amplifying human judgment.**
Agentic AI accelerates all three — but only when disciplined. SAGE is that discipline.

### The Five Laws

**1. Agents propose. Humans decide. Always — for agent proposals.**
The HITL approval gate is not bureaucracy — it is the product. SAGE exists to amplify human judgment, never to replace it. Compliance guarantees in regulated industries depend on this. Any solution-level agent proposal (`yaml_edit`, `implementation_plan`, `code_diff`, `knowledge_delete`, `agent_hire`) must have a human in the loop before execution. Framework control operations (`config_switch`, `llm_switch`, `config_modules`) are intentionally immediate — they are tool operation, not agent action. The distinction matters: agent proposals carry compliance risk; framework control is the operator's own action.

**2. Eliminate waste at every layer.**
No sprint ceremonies. No enterprise roleplay. No manual steps that an agent can do correctly. If a task can be automated without reducing visibility or compliance, it must be automated. If it cannot be automated correctly, it stays human.

**3. Compounding intelligence over cold-start lookup.**
Every human approval, every rejection, every correction feeds the vector memory. SAGE agents improve with each interaction — not through retraining, but through accumulated experience retrieval (Memento principle). The audit log is not just compliance — it is the training signal.

**4. Vertical slices, not horizontal layers.**
Every task should produce a working, reviewable end-to-end slice of value — from input to analysis to proposal to action. Don't build all the models first, then all the APIs. Build one complete flow. Test it. Repeat.

**5. Atomic verification is non-negotiable.**
Every agent action must have a defined verification step. If a proposal cannot be verified before approval, it should not be generated. Build-in the check, not the fix.

---

## Core Engineering Values

**Separation of concerns is sacred.**
The framework (`src/`, `web/`) and the solutions (`solutions/<name>/`) are fundamentally different things. The framework knows nothing specific about any industry. Solutions know nothing about framework internals. This boundary must never blur.

**The smallest correct change wins.**
This codebase is working production software. Don't refactor while fixing bugs. Don't add "while I'm here" improvements. Do exactly what was asked, test it, stop.

**Human approval is not optional — it's the product.**
The entire point of SAGE is that AI proposes and humans decide. Never design around, bypass, or make optional the approval step. That's the compliance guarantee.

**Solutions are tenants, not children.**
A solution YAML config plugs in to SAGE; SAGE doesn't belong to any solution. The DFS solution is company property. The medtech solution is an open example. Both are equals from the framework's perspective. Never hardcode solution-specific logic into `src/`.

**Tests are the truth.**
If tests pass, the framework works. If tests fail, nothing else matters. When uncertain about a change, run `make test` first and fix failures before moving on.

---

## Architecture Mental Model

```
solutions/<name>/          ← 3 YAML files, tests, tools — fully replaceable
    project.yaml           ← what this domain IS (declarative agent manifest)
    prompts.yaml           ← how agents THINK in this domain (roles + system prompts)
    tasks.yaml             ← what agents CAN DO in this domain (task type registry)

src/core/                  ← the brain (LLM, queue, project loader, memory)
src/agents/                ← the workers (analyst, developer, monitor, planner, universal)
src/interface/api.py       ← the door (FastAPI — the only public interface)
src/memory/                ← the learning layer (audit log + vector memory)
src/modules/               ← zero-dependency nano-utilities
web/src/                   ← the face (React UI — reads from the door only)
```

Data flows one way: **UI → API → Agents → LLM → Agents → Audit Log**.
Nothing in the UI calls an agent directly. Nothing in an agent calls the UI.
Memory flows in a compounding loop: **Human Feedback → Vector Store → Future Agent Context**.

---

## The SAGE Lean Loop

Every task processed by SAGE follows this five-phase cycle:

```
1. SURFACE     → Agent detects or receives signal (log, webhook, trigger)
2. CONTEXTUALIZE → Vector memory searched; prior decisions retrieved
3. PROPOSE     → LLM generates action proposal with trace_id
4. DECIDE      → Human reviews and approves or rejects with feedback
5. COMPOUND    → Feedback ingested into vector store; audit log updated
```

Phase 5 feeds back into Phase 2 for the next task. This is compounding intelligence — the system gets measurably better with every human interaction. Never short-circuit any phase.

---

## Agent Architecture Principles

**Agents are role-based, not function-based.**
Each agent has a defined role (Analyst, Developer, Monitor, Planner, Universal). Roles are declared in `prompts.yaml`, not hardcoded. Adding a new agent role means editing YAML, not Python.

**Non-invasive instrumentation.**
Agent execution is fully traced through the audit log. No separate telemetry system needed. Every `generate()` call, every approval, every rejection is a structured event. This is the training signal for continuous improvement (Agent Lightning principle).

**Behavioral improvement without model retraining.**
SAGE improves agent quality by enriching the retrieval context (vector store) from human feedback — not by fine-tuning the LLM. This keeps inference costs flat and improvement velocity high (Memento principle).

**Wave-capable task execution.**
Tasks without dependencies can and should run in parallel. The queue manager is the scheduler. When designing new task flows, identify independent work units and execute them in parallel waves — waiting only where data dependencies require sequential ordering.

**Declarative agent manifest (YAML-first).**
The `prompts.yaml` is the agent package manifest. Role definitions, system prompts, tool access, and behavioral constraints all live there. A new domain (solution) is fully described by its three YAML files — no Python changes required. This mirrors the APM principle: agent configs as versioned, declarative packages.

---

## The Two Backlogs — A Hard Boundary

SAGE is a platform for builders. Every person using SAGE has two completely separate
improvement streams, and mixing them is a failure mode:

**Solution Backlog (`scope: "solution"`)**
Features and tasks to build *inside the user's application* — add voice pack to Flutter,
expand the gym module, build the admin web panel. These go through the full SAGE workflow:
log → AI plan → approve → implement in the solution codebase.
The solution team owns this backlog. SAGE's Planner Agent helps prioritise and decompose it.

**SAGE Framework Ideas (`scope: "sage"`)**
Improvements to the SAGE *platform itself* — new agent capabilities, better UI modules,
new integrations, richer MCP tools. These are community contributions. They are logged in
SAGE for visibility and should also be raised as GitHub Issues on the SAGE repo so the
open-source community can pick them up.

**Rule:** Never treat a solution feature request as a SAGE improvement, or vice versa.
The `scope` field on every `FeatureRequest` enforces this distinction in code and UI.
The Improvements page has two tabs — one per scope — so the separation is always visible.

---

## Memory and Knowledge Architecture

**The vector store is the institutional memory.**
It holds prior analyses, human corrections, domain decisions, and known patterns. Always search it before generating. Always update it after human feedback.

**The audit log is the compliance record and training signal.**
Every event — analysis, approval, rejection, feedback — is written to SQLite with a trace_id. This is both the compliance guarantee for regulated industries and the ground truth for measuring agent quality over time.

**Compounding context beats cold-start retrieval.**
A correction stored today makes tomorrow's analysis better without any model change. Design all agents to write meaningful feedback to the vector store on rejection — not just "rejected", but the human's actual reasoning.

---

## How to Work on This Codebase

**Before changing anything:** read the file first. Understand the existing pattern. Then make the minimum change. Don't guess at what other files might need updating — search for usages.

**When adding a new API endpoint:** it goes in `src/interface/api.py` with a lazy import accessor. Update `client.ts` with the typed fetch function at the same time.

**When adding a new UI page:** create `web/src/pages/MyPage.tsx`, wire the route in `App.tsx`, add the sidebar entry in `Sidebar.tsx`, and the title in `Header.tsx`. All four changes together, nothing skipped.

**When touching solution YAMLs:** never hardcode solution names anywhere in `src/`. Always use `project_config.project_name` or `_SOLUTIONS_DIR`.

**When touching the LLM gateway:** remember it's a singleton with a thread lock. Any change to `generate()` affects every agent simultaneously.

**When adding a new agent role:** add it to `prompts.yaml` (role definition + system prompt), add a task type to `tasks.yaml` if needed, wire it in `UniversalAgent`. No new Python files for new roles.

**When improving agent quality:** do not change prompts speculatively. Identify a specific failure case from the audit log, update the prompt to address that case, verify with a test.

---

## What to Never Do

- Never commit `solutions/dfs/` to the SAGE repository. It is proprietary.
- Never add company-specific logic to `src/`. Solutions absorb domain specifics.
- Never skip the YAML validation in the `/config/yaml/{file}` endpoint.
- Never break the audit log. It is the compliance record and the training signal.
- Never remove the `threading.Lock` from `LLMGateway`. Single-lane inference is intentional.
- Never add `print()` statements — use `self.logger` or `logging.getLogger()`.
- Never bypass the HITL approval gate for solution-level agent proposals. Not for demos. Not for "obvious" cases. Never. (Framework control ops are a different tier — see Law 1.)
- Never short-circuit Phase 5 (feedback ingestion). Every rejection is a learning opportunity.
- Never hardcode a solution name in `src/`. The framework is domain-blind.

---

## Reference Architectures That Inform SAGE

These are not dependencies — they are thinking influences:

| Source | Principle Borrowed |
|---|---|
| **GSD (Get Shit Done)** | Five-phase lean loop, wave scheduling, vertical slices, state persistence, no enterprise ceremony |
| **Rowboat** | Compounding memory, knowledge graph from interactions, transparent inspectable agent actions |
| **APM (Agent Package Manager)** | YAML-as-agent-manifest, declarative dependency model, versioned agent configs |
| **Agent Lightning** | Non-invasive audit instrumentation, closed-loop improvement, selective agent optimization |
| **Memento (arXiv 2508.16153)** | Behavioral optimization via memory retrieval (not retraining), decouple LLM from policy improvement |
| **Paperclip (paperclipai/paperclip)** | Board-of-directors governance model, immutable audit log per company, agent-hire requiring explicit human approval, per-agent budget controls. *Key divergence:* Paperclip targets zero-human operation over time; SAGE mandates human approval always — the regulated-industry version of the same architecture. |
| **Aider** | Every agent change is a reversible git commit; unified diff preview before apply; repo map for multi-file coherence |
| **Claude Code** | Pre/post action hooks declarable per project; `.claude/` per-project runtime directory (directly inspired `.sage/`); persistent context injection via CLAUDE.md |
| **DeerFlow (bytedance/deer-flow)** | Supervisor + sub-agent topology (Researcher/Coder/Reporter), skills as Markdown files, Docker "AIO Sandbox" with full shell/browser/filesystem, adaptive replanning when sub-agents return thin results, tiered memory (working/archival), long-running task durability via LangGraph checkpointing. *Key divergence:* DeerFlow targets general-purpose research/coding; SAGE adds domain-specific execution runners (firmware, PCB, ML, etc.) and HITL approval gates for regulated industries. |

---

## Tone When Communicating About This Project

- Precise and technical. No hand-waving.
- Honest about limits — if a provider doesn't expose exact token counts, say so.
- Pragmatic — favour working software over elegant abstractions.
- Brief — engineers reading this are busy. One sentence beats a paragraph.
- Lean — if a sentence doesn't add value, cut it.
