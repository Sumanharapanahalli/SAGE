# Agent SDK Integration

SAGE can optionally leverage the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)
for built-in tool execution (Read/Edit/Write/Bash/Grep/Glob/WebSearch/WebFetch),
subagent parallelism, and session continuity. This is an **opt-in augmentation**
that activates only when all three conditions are met:

1. The `claude-agent-sdk` package is installed
2. The active LLM provider is `claude-code`
3. The Claude Code CLI is authenticated

When any condition fails, SAGE falls back to the existing `LLMGateway.generate()`
path — zero behavior change for other providers.

## Architecture

- `src/core/agent_sdk_runner.py` — `AgentSDKRunner` bridge layer (singleton)
- `src/core/sdk_hooks.py` — Compliance hook callbacks (async)
- `src/core/sdk_change_tracker.py` — Per-session file change accumulator

Agents call `AgentSDKRunner.run(role_id, task, context)`. The runner:

1. Loads the role from `prompts.yaml`
2. Detects SDK availability via `LLMGateway.sdk_available`
3. If SDK unavailable → delegates to `LLMGateway.generate()` (fallback)
4. If SDK available → runs the two-gate HITL flow

## Two-Gate HITL Model

Phase 1 replaces per-tool-call HITL gates with two meaningful gates:

- **Gate 1: Goal Alignment** — Before execution, the runner creates a
  `goal_alignment` proposal (`risk_class=STATEFUL`) with the role, task,
  intended approach, and tools requested. Human approves the *direction*
  before work begins. Rejection aborts execution immediately.

- **Gate 2: Result Approval** — After SDK execution completes, the runner
  reads accumulated file changes from `SDKChangeTracker` and creates a
  `result_approval` proposal with files created/modified/deleted, commands
  run, and a result summary. Human approves the *outcome* before it is
  finalized. Rejection feedback is fed into `vector_memory` for compounding
  intelligence.

Between gates, the SDK runs with `permission_mode="acceptEdits"`. Observational
hooks (`audit_logger_hook`, `change_tracker_hook`) capture every action without
blocking. Hard-blocking hooks (`destructive_op_hook`, `budget_check_hook`)
still deny dangerous operations regardless of HITL state.

## Hook Wiring

| Hook | Phase | Behavior |
|---|---|---|
| `destructive_op_hook` | PreToolUse | Hard-blocks `rm -rf /`, `git push --force`, `DROP TABLE`, `mkfs`, etc. |
| `budget_check_hook` | PreToolUse | Hard-blocks when tenant/solution budget exceeded |
| `pii_filter_hook` | PreToolUse | Scrubs PII via `scrub_text` when `pii_config.enabled=true` |
| `audit_logger_hook` | PostToolUse | Records every tool call to `compliance_audit_log` |
| `change_tracker_hook` | PostToolUse | Accumulates Write/Edit/Bash into session tracker for Gate 2 |

## Per-Role `sdk_tools` Field

Solutions can specify per-role SDK tool sets in `prompts.yaml`:

```yaml
roles:
  clinical_reviewer:
    name: "Clinical Reviewer"
    system_prompt: "..."
    sdk_tools: ["Read", "Grep", "WebSearch", "WebFetch"]
```

If `sdk_tools` is omitted, the runner falls back to a task-type default mapping
(see `_TASK_TYPE_TOOLS` in `agent_sdk_runner.py`). Task types include
`analysis`, `review`, `code_review`, `implementation`, `code_generation`,
`testing`, `research`, `investigation`, `planning`, `decomposition`.

## Graceful Degradation

Every SDK code path is guarded by `try/except ImportError`. If
`claude_agent_sdk` is not installed at runtime, the runner transparently
routes through `_run_via_gateway` — existing agents see no behavior change.

## Migrated Agents (Phase 2)

The following SAGE agents route their LLM calls through `AgentSDKRunner`:

- **Universal Agent** (`role_id="analyst"`, `task_type="analysis"`) - General-purpose analysis and signal processing
- **Critic Agent** (`role_id="technical_reviewer"`, `task_type="review"`) - Code and plan reviews
- **Analyst Agent** (`role_id="analyst"`, `task_type="analysis"`) - Log analysis and root cause investigation
- **Planner Agent** (`role_id="planner"`, `task_type="planning"`) - Task planning and decomposition
- **Developer Agent** (`role_id="developer"`, `task_type="code_review"`) - ReAct loop for merge requests
- **Coder Agent** (`role_id="coder"`, `task_type="code_generation"`) - ReAct loop for step implementation

All agents fall back gracefully to `LLMGateway.generate()` when the Claude Agent SDK is unavailable, ensuring zero behavior change for non-Claude-Code providers.

## Related

- Parent spec: `docs/superpowers/specs/2026-04-10-agent-sdk-evolutionary-integration-design.md`
- Phase 1 plan: `docs/superpowers/plans/2026-04-10-agent-sdk-phase-1-foundation.md`
- Upcoming phases: agent migration (Phase 2), ProgramDatabase + Evolvers (Phase 3-5), Regulatory Primitives (Phase 6)
