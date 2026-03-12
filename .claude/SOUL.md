# SOUL.md — SAGE Framework
# Smart Agentic-Guided Empowerment

## What This Project Is

**SAGE — Smart Agentic-Guided Empowerment** — is a **modular autonomous AI agent framework** — not a product, not a demo, not a research
experiment. It is a professional engineering tool used in real regulated industries
(medical devices, embedded firmware, ML/mobile). Every decision in this codebase has
downstream consequences: wrong YAML breaks an agent's reasoning; a bad prompt can trigger
incorrect code reviews in a manufacturing environment.

Approach every task here with the same seriousness you'd bring to production medical software.

---

## Core Engineering Values

**Separation of concerns is sacred.**
The framework (`src/`, `web/`) and the solutions (`solutions/<name>/`) are fundamentally
different things. The framework knows nothing specific about any industry. Solutions know
nothing about framework internals. This boundary must never blur.

**The smallest correct change wins.**
This codebase is working production software. Don't refactor while fixing bugs. Don't add
"while I'm here" improvements. Do exactly what was asked, test it, stop.

**Human approval is not optional — it's the product.**
The entire point of SAGE is that AI proposes and humans decide. Never design around, bypass,
or make optional the approval step. That's the compliance guarantee.

**Solutions are tenants, not children.**
A solution YAML config plugs in to SAGE; SAGE doesn't belong to any solution. The DFS
solution is company property. The medtech solution is an open example. Both are equals from
the framework's perspective. Never hardcode solution-specific logic into `src/`.

**Tests are the truth.**
If tests pass, the framework works. If tests fail, nothing else matters. When uncertain about
a change, run `make test` first and fix failures before moving on.

---

## Architecture Mental Model

```
solutions/<name>/          ← 3 YAML files, tests, tools — fully replaceable
    project.yaml           ← what this domain IS
    prompts.yaml           ← how agents THINK in this domain
    tasks.yaml             ← what agents CAN DO in this domain

src/core/                  ← the brain (LLM, queue, project loader, memory)
src/agents/                ← the workers (analyst, developer, monitor, planner)
src/interface/api.py       ← the door (FastAPI — the only public interface)
web/src/                   ← the face (React UI — reads from the door only)
```

Data flows one way: UI → API → Agents → LLM → Agents → Audit Log.
Nothing in the UI calls an agent directly. Nothing in an agent calls the UI.

---

## How to Work on This Codebase

**Before changing anything:** read the file first. Understand the existing pattern.
Then make the minimum change. Don't guess at what other files might need updating —
search for usages.

**When adding a new API endpoint:** it goes in `src/interface/api.py` with a lazy import
accessor. Update `client.ts` with the typed fetch function at the same time.

**When adding a new UI page:** create `web/src/pages/MyPage.tsx`, wire the route in
`App.tsx`, add the sidebar entry in `Sidebar.tsx`, and the title in `Header.tsx`.
All four changes together, nothing skipped.

**When touching solution YAMLs:** never hardcode solution names anywhere in `src/`.
Always use `project_config.project_name` or `_SOLUTIONS_DIR`.

**When touching the LLM gateway:** remember it's a singleton with a thread lock.
Any change to `generate()` affects every agent simultaneously.

---

## What to Never Do

- Never commit `solutions/dfs/` to the SAGE repository. It is proprietary.
- Never add company-specific logic to `src/`. Solutions absorb domain specifics.
- Never skip the YAML validation in the `/config/yaml/{file}` endpoint.
- Never break the audit log. It is the compliance record.
- Never remove the `threading.Lock` from `LLMGateway`. Single-lane inference is intentional.
- Never add `print()` statements — use `self.logger` or `logging.getLogger()`.

---

## Tone When Communicating About This Project

- Precise and technical. No hand-waving.
- Honest about limits — if Gemini CLI doesn't expose exact token counts, say so.
- Pragmatic — favour working software over elegant abstractions.
- Brief — engineers reading this are busy. One sentence beats a paragraph.
