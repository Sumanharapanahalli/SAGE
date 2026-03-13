# reflect solution — Claude Code Instructions

@.claude/SOUL.md

## What This Solution Represents

SAGE is the **development assistant** for building Reflect. SAGE does NOT replace
Reflect's own agents (`/home/shetty/sandbox/Reflect/agents/`) — those run inside
the Reflect runtime. SAGE helps you *build* Reflect: code review, test runs,
build advice, specification management, and progress tracking.

Source repo: `/home/shetty/sandbox/Reflect`

## Available Skills

| Skill | Usage |
|---|---|
| `/run-solution-tests` | Run reflect solution tests |

## Quick Start

```bash
make run PROJECT=reflect    # SAGE backend on :8000
make ui                     # SAGE frontend on :5173

# Seed platform knowledge (run once after setup)
SAGE_PROJECT=reflect python solutions/reflect/scripts/seed_knowledge.py
```

## Key Files in This Solution

```
project.yaml     Domain metadata, activity modules, tenants
prompts.yaml     10 agent roles + analyst/developer/planner/monitor prompts
tasks.yaml       32 task types — all Reflect workflows
specs/           GSD specification documents (PROJECT, REQUIREMENTS, ROADMAP, STATE)
scripts/         seed_knowledge.py
mcp_servers/     codebase_server.py — real-time gap analysis
tests/           Solution tests
```

## GSD Specification Workflow

The `specs/` folder maintains living specification documents:

```
REVIEW_PROGRESS task → reads STATE.md vs ROADMAP.md → surfaces next priority
UPDATE_SPEC task     → updates the relevant spec file after decisions
PLAN_PHASE task      → creates a wave-scheduled implementation plan
```

Keep STATE.md up to date after completing each phase. It is the ground truth
for what SAGE's tech_lead role reads when proposing next steps.

## Reflect Codebase Layout

```
/home/shetty/sandbox/Reflect/
  extract_engine/   Python extract pipeline (MediaPipe → skill pack)
  pose_engine/      C++ scoring engine (CMake)
  flutter_app/      Flutter cross-platform app
  agents/           Reflect's own 10 SAGE agents
  activity_modules/ 7 modules (yoga, gym, PT, pilates, tai_chi, qigong, barre)
  platform_sdk/     Python SDK (53 tests)
  tools/            Python tools (130 tests)
  sage_platform/    Reflect's SAGE runtime (SageRuntime)
  specs/            (this solution's specs live in SAGE, not Reflect)
```
