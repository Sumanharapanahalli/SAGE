# Orchestrator Intelligence

9 state-of-the-art agentic modules that enhance agent reasoning, coordination, and self-improvement.

## Modules

### Event Bus (`src/core/event_bus.py`)
In-process pub/sub with SSE streaming. Thread-safe publish/subscribe, bounded history, async `stream()` generator for real-time UI updates. Singleton via `get_event_bus()`.

### Budget Manager (`src/core/budget_manager.py`)
Per-scope token and cost tracking. Configurable limits (`max_tokens`, `max_cost_usd`), soft warnings at threshold, hard stops on exceeded. Emits events via Event Bus. Integrates with `cost_tracker.py` for rate estimation.

### Reflection Engine (`src/core/reflection_engine.py`)
Bounded self-correction loop (Reflexion/LATS pattern). Generator produces output → critic scores it → if below threshold, re-generate with full iteration history as feedback. Stops on: acceptance threshold met, no improvement detected, or max iterations (default 3).

### Plan Selector (`src/core/plan_selector.py`)
Beam search over candidate plans (Tree of Thought). Generates N plans via generator callable, scores each with critic, ranks by score. Optionally applies Reflection Engine to best candidate if score is below threshold.

### Consensus Engine (`src/core/consensus_engine.py`)
Multi-agent voting with three methods: majority, weighted (confidence-weighted — high-confidence minority can win), unanimous. Disagreement ratio above threshold (default 0.5) triggers automatic human escalation.

### Tool Executor (`src/core/tool_executor.py`)
ReAct pattern tool calling. 7 built-in tools: `file_read`, `file_list`, `shell_run` (requires approval), `git_diff`, `git_log`, `search_code`, `run_tests` (requires approval). Custom tools registered via `register()`. Each call tracked with result/error/duration.

### Agent Spawner (`src/core/agent_spawner.py`)
Recursive agent composition. Spawn sub-agents dynamically with depth limit (default 3) and concurrency limit (default 5). Checks budget before spawning. Tracks active/completed/failed counts per parent task.

### Backtrack Planner (`src/core/backtrack_planner.py`)
HTN-style re-planning. Records task failures, triggers backtrack after N failures (default 2). Identifies affected subtree via BFS from failed task. Generates replan with failure context injected. Max backtracks per task configurable (default 3).

### Memory Planner (`src/core/memory_planner.py`)
RAG-in-the-loop planning. Augments task context with: collective learnings (via `CollectiveMemory`), past successful plans (keyword-matched), and domain vector memory. Records successful plans (bounded to 100) for future retrieval.

## API Endpoints

All under `/orchestrator/*` prefix. See `src/interface/routes/orchestrator.py`.

| Group | Endpoints |
|---|---|
| Events | `GET /events/stream` (SSE), `GET /events/history` |
| Budget | `POST /budget`, `GET /budget`, `GET /budget/{scope}`, `POST /budget/record` |
| Reflection | `GET /reflection/stats`, `GET /reflection/recent`, `GET /reflection/{id}` |
| Plans | `GET /plans/stats`, `GET /plans/recent` |
| Spawns | `POST /spawn`, `GET /spawns`, `GET /spawns/stats` |
| Tools | `GET /tools`, `POST /tools/execute`, `GET /tools/history`, `GET /tools/stats` |
| Backtrack | `GET /backtrack/records`, `GET /backtrack/stats` |
| Consensus | `GET /consensus/results`, `GET /consensus/{id}`, `GET /consensus/stats` |
| Combined | `GET /stats` (all modules) |

## Web UI

8-tab dashboard at `/orchestrator`:
1. **Overview** — 3x3 grid of module stat cards
2. **Live Events** — SSE-connected real-time event stream
3. **Budget** — Usage stats + top consumers
4. **Reflection** — Iteration results with accept/reject status
5. **Tools** — Tool call history with success/error indicators
6. **Agents** — Spawned agent list with role, status, depth
7. **Consensus** — Vote results with agreement ratios
8. **Backtrack** — Replan records with failure context

## Tests

87 tests in `tests/test_orchestrator_enhancements.py` covering all 9 modules plus 5 cross-module integration tests.
