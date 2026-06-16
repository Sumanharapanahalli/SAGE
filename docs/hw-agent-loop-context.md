# SAGE Hardware Engineer Agent — Optimizer Loop Context

## SAGE Framework Architecture (key constraints)

- Agents are defined ENTIRELY in `solutions/<name>/prompts.yaml` (role + system prompt).
  No new Python agent files are needed for new roles — only YAML.
- Task types are defined in `solutions/<name>/tasks.yaml`.
- MCP servers are declared in `config/config.yaml` under `mcp_servers:`.
- Skills are Markdown instruction files that tell an agent how to do a specific operation.
  SAGE already uses `.claude/` for skill files (see CLAUDE.md).
- The framework is domain-blind — no hardware-specific logic in `src/`.
- Every agent proposal (code diff, yaml_edit, implementation_plan) must go through the
  HITL approval gate in `src/interface/api.py`. This is NON-NEGOTIABLE.
- The `UniversalAgent` in `src/agents/universal.py` reads `roles:` from `prompts.yaml`
  and dispatches accordingly — no Python changes for new roles.
- LLM gateway is a singleton with 6 providers; agents call `self.llm.generate()`.
- Existing MCP infrastructure: SAGE has MCP support in `src/core/` and exposes it via
  the FastAPI interface. New MCP servers are declared, not hardcoded.

## What wrench-board is (https://github.com/Junkz3/wrench-board)

Agent-native PCB diagnostic workbench powered by Claude Opus 4.8.
- Ingests schematic PDFs + boardview files (.kicad_pcb, .brd, .asc, .bdv, 13 formats total)
- 36 custom Claude tools declared in `api/agent/manifest.py`:
  - 12 `bv_*` boardview manipulation tools (highlight pins, trace nets, simulate failures)
  - 24+ query tools (schematics, measurements, validations, technician profiles)
- FastAPI + WebSocket backend, D3.js frontend for boardview visualization
- USB microscope/webcam integration for live board inspection
- 4-layer memory architecture (Anthropic Managed Agents)
- Anti-hallucination: tools return structured responses for unknown components

## KiCad MCP (to be designed)

KiCad has a Python scripting API (`pcbnew` module) that can:
- Open/read/write `.kicad_pcb` and `.kicad_sch` files
- Run DRC (Design Rule Check) and ERC (Electrical Rules Check)
- Generate BOM, netlist, Gerbers
- Query component positions, net connections, copper pours
- Annotate schematics

A KiCad MCP server would wrap `pcbnew` and expose these as MCP tools.

## TestAgent context (separate concern, also needs design)

The existing `testbench/` folder has:
- `testbench/run.py` — config-driven test orchestrator
- `testbench/drivers/`: api.py, browser.mjs, browser.py, embedded.py, load.py, mobile.py,
  screenshot.mjs
- `testbench/configs/_embedded.example.yaml` — config format

Currently the testbench is a standalone CLI. The question is whether to:
a) Keep it as a skill (Markdown instruction file) that existing agents invoke
b) Add a TestAgent role in prompts.yaml that owns test execution + result interpretation

## What the optimizer should produce

Design proposals for:

1. **HardwareEngineerAgent role** — complete `prompts.yaml` role entry (role name, persona,
   system prompt, available tools/skills, task routing). The agent should be able to:
   - Load boardview files and run wrench-board diagnostics
   - Query schematics via KiCad MCP
   - Generate BOMs, run DRC, trace nets
   - Propose hardware fixes as SAGE proposals (HITL-gated)

2. **tasks.yaml entries** — new task types for hardware operations:
   `board_diagnosis`, `schematic_review`, `bom_generation`, `drc_check`, `net_trace`

3. **wrench-board MCP server config** — how to declare wrench-board as an MCP server
   in SAGE's config (URL, tool manifest, auth). Show the config.yaml addition.

4. **KiCad MCP server design** — either point to an existing KiCad MCP server if one
   exists, or specify a minimal `mcp-kicad/server.py` that wraps the pcbnew API for the
   5 most valuable operations: open_project, run_drc, get_bom, trace_net, export_gerbers.

5. **Skill files** — 2-3 Markdown skill files for the hardware engineer agent:
   `diagnose-board.md`, `review-schematic.md`, `run-drc.md`

6. **TestAgent role recommendation** — should testbench be a skill or a TestAgent role?
   Provide the prompts.yaml + tasks.yaml entries for whichever you recommend, with reasoning.

## Evaluation criteria for Gemini to score against

- Fits SAGE's YAML-first, domain-blind architecture (no src/ changes for new roles)
- Hardware engineer role is fully specified in prompts.yaml (system prompt, persona, tools)
- MCP server declarations follow SAGE patterns (config-driven, not hardcoded)
- Skill files are actionable Markdown (not vague instructions)
- HITL approval gate is preserved for all agent proposals
- TestAgent recommendation is clearly justified
- KiCad MCP design is concrete enough to implement in 1 day
- All task types are well-named and follow existing tasks.yaml patterns
- No solution-specific logic bleeds into src/
