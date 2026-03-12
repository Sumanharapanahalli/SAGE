# SAGE Framework — Claude Code Instructions

@.claude/SOUL.md

---

## Project Layout (Quick Reference)

```
src/                    Framework Python source
  core/                 LLM gateway, project loader, queue manager, modules
  agents/               Analyst, Developer, Monitor, Planner
  interface/api.py      FastAPI — the only public interface
  memory/               Audit logger, vector memory
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
make run PROJECT=xxx    # Start FastAPI backend on :8000
make ui                 # Start Vite frontend on :5173
make test               # Framework unit tests (216 tests)
make test-all           # Framework + all solution tests
```

## Available Skills

| Skill | Usage |
|---|---|
| `/run-tests` | Run tests — optionally pass a scope: `all`, `medtech`, `api`, `llm` |
| `/new-solution` | Scaffold a new solution from template: `/new-solution robotics` |
| `/check-api` | Smoke-test all live API endpoints |
| `/edit-solution-yaml` | Edit a solution YAML and hot-reload: `/edit-solution-yaml medtech prompts ...` |

## Critical Rules (from SOUL.md)

- Never commit `solutions/dfs/` — it is proprietary, blocked by .gitignore
- Never add solution-specific logic to `src/` — solutions plug in via YAML only
- Never bypass the audit log or the human approval step
- Never remove the `threading.Lock` from `LLMGateway`
- Always use `self.logger` not `print()`
- Run `make test` before and after any change to `src/`
