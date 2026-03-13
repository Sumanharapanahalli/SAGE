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
  agents/               Analyst, Developer, Monitor, Planner, Universal
  interface/api.py      FastAPI — the only public interface
  memory/               Audit logger (compliance + training signal), vector memory
  modules/              Zero-dependency nano-modules

web/src/                React 18 + TypeScript dashboard
  pages/                One file per route
  components/layout/    Sidebar, Header
  api/client.ts         All fetch calls — typed

solutions/              Solution configurations (NOT framework code)
  medtech/              ISO 13485 example (MIT)
  poseengine/           ML/mobile example (MIT)
  kappture/             Human tracking example (MIT)
  dfs/                  DFS proprietary — NEVER commit to this repo

config/config.yaml      Base LLM / memory / integration settings
.venv/                  Python virtual environment (Windows: Scripts/, Unix: bin/)
```

## Key Commands

```bash
make venv               # Create .venv and install all deps (first time)
make venv-minimal       # Low-RAM machine — skips ChromaDB/embeddings
make run PROJECT=xxx    # Start FastAPI backend on :8000
make ui                 # Start Vite frontend on :5173
make test               # Framework unit tests
make test-all           # Framework + all solution tests
```

## Available Skills

| Skill | Usage |
|---|---|
| `/run-tests` | Run tests — optionally pass a scope: `all`, `medtech`, `api`, `llm` |
| `/new-solution` | Scaffold a new solution from template: `/new-solution robotics` |
| `/check-api` | Smoke-test all live API endpoints |
| `/edit-solution-yaml` | Edit a solution YAML and hot-reload: `/edit-solution-yaml medtech prompts ...` |

## The SAGE Lean Loop (commit this to memory)

```
SURFACE → CONTEXTUALIZE → PROPOSE → DECIDE → COMPOUND
```
Every agent task follows this five-phase cycle. Phase 5 (COMPOUND) feeds Phase 2 (CONTEXTUALIZE) for every future task. Never skip a phase.

## Adding a New Agent Role (YAML-first)

1. Add role definition + system prompt to `solutions/<name>/prompts.yaml`
2. Add task type(s) to `solutions/<name>/tasks.yaml` if needed
3. Wire role in `UniversalAgent` if task routing requires it
4. No new Python agent files for new roles — roles are YAML

## The Two Backlogs — Never Mix Them

| Scope | Owned by | Workflow | Where tracked |
|---|---|---|---|
| **`solution`** | The builder's team | Log → AI plan → approve → implement in solution | SAGE Improvements → Solution Backlog tab |
| **`sage`** | SAGE community | Log → GitHub Issue → community PR | SAGE Improvements → SAGE Framework Ideas tab |

Every `FeatureRequest` has a `scope` field. Every submission UI has a scope selector.
If someone asks "can you add X", first ask: is X for their solution, or for SAGE itself?

## Critical Rules (from SOUL.md)

- Never commit `solutions/dfs/` — it is proprietary, blocked by .gitignore
- Never add solution-specific logic to `src/` — solutions plug in via YAML only
- Never bypass the audit log or the human approval step
- Never remove the `threading.Lock` from `LLMGateway`
- Always use `self.logger` not `print()`
- Never short-circuit feedback ingestion (Phase 5) — every rejection teaches
- Run `make test` before and after any change to `src/`
