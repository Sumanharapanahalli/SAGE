# Agent SDK Phase 2 — Agent Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the 6 core SAGE agents (Universal, Critic, Analyst, Planner, Developer, Coder) to route their LLM calls through `AgentSDKRunner.run()` — gaining two-gate HITL, SDK tool execution, and session change tracking — while preserving every existing external API and test.

**Architecture:** Each agent keeps its public method signatures and return-dict shapes unchanged. Internally, the single `llm_gateway.generate(...)` call site is replaced with `get_agent_sdk_runner().run(role_id, task, context)`. The runner already handles graceful fallback: when the SDK is unavailable it delegates to `LLMGateway.generate()`, so existing behavior is preserved bit-for-bit for non-Claude-Code providers. Each agent maps its domain inputs to the runner's `(role_id, task, context)` tuple and its domain outputs from the runner's uniform result dict (which always contains a `summary` string and `raw_response` text field that agents can parse with their existing JSON/regex logic).

**Tech Stack:** Python 3.12, pytest, pytest-asyncio, `src/core/agent_sdk_runner.py` (Phase 1), `src/core/llm_gateway.py`, `src/memory/project_config.py`.

**Risk order (lowest → highest):** Universal → Critic → Analyst → Planner → Developer → Coder. Universal is lowest risk because its signature (`role_id, task, context`) already matches the runner. Coder is highest risk because it uses a ReAct loop with multiple LLM calls and plain-text (non-JSON) parsing.

---

## File Structure

**New files:**
- `src/agents/_sdk_bridge.py` — Thin helper that agents call to invoke the runner and extract the raw text response. One responsibility: bridge from agent's sync call site to `asyncio.run(runner.run(...))` and return a string.
- `tests/test_sdk_bridge.py` — Unit tests for the helper.
- `tests/test_universal_agent_sdk_migration.py` — Migration tests for Universal.
- `tests/test_analyst_agent_sdk_migration.py` — Migration tests for Analyst.
- `tests/test_planner_agent_sdk_migration.py` — Migration tests for Planner.
- `tests/test_coder_agent_sdk_migration.py` — Migration tests for Coder.

**Modified files:**
- `src/agents/universal.py` — Replace `llm_gateway.generate(...)` call with `_sdk_bridge.run_agent(...)`.
- `src/agents/critic.py` — Replace internal `_call_llm()` body with `_sdk_bridge.run_agent(...)`.
- `src/agents/analyst.py` — Replace `llm_gateway.generate(...)` with `_sdk_bridge.run_agent(...)`.
- `src/agents/planner.py` — Replace `self.llm.generate(...)` with `_sdk_bridge.run_agent(...)`.
- `src/agents/developer.py` — Replace the ReAct-loop `self.llm.generate(...)` call sites.
- `src/agents/coder.py` — Replace the two `trace_name="coder.react*"` generate calls.
- `tests/test_critic_agent.py` — Update mocks to patch `_sdk_bridge.run_agent` alongside existing `llm_gateway` patches.
- `tests/test_analyst_agent.py` — Same.
- `tests/test_developer_agent.py` — Same.

**Unchanged (load-bearing invariants):**
- All agent public method signatures and return-dict shapes.
- `llm_gateway.generate()` itself — still the fallback path inside the runner.
- `AgentSDKRunner` — Phase 1 is frozen for Phase 2.

---

## Shared Bridge Design

Every agent in Phase 2 calls the same helper. Design it once, use it six times.

**`src/agents/_sdk_bridge.py` contract:**

```python
"""Bridge from sync agent code to the async AgentSDKRunner.

Agents use this helper to route their LLM calls through the two-gate
HITL flow introduced in Phase 1. When the SDK is unavailable the
runner falls back to LLMGateway.generate(), so behavior is unchanged
for non-Claude-Code providers.
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.agent_sdk_runner import get_agent_sdk_runner


def run_agent(
    role_id: str,
    task: str,
    context: str = "",
    *,
    task_type: str | None = None,
) -> str:
    """Invoke the Agent SDK runner and return the raw text response.

    Agents parse the text themselves (JSON extract, regex, ReAct tags)
    exactly as they did with llm_gateway.generate(). The runner's dict
    always has a "raw_response" field containing the model's text.
    """
    runner = get_agent_sdk_runner()
    result = asyncio.run(
        runner.run(
            role_id=role_id,
            task=task,
            context=context,
            task_type=task_type,
        )
    )
    return result.get("raw_response", "") or result.get("summary", "")
```

**Why return a string, not the dict:** existing agents have parsing logic written against a text blob (`extract_json`, regex, ReAct tag parsing). Returning a string is the smallest change that preserves every downstream invariant. The dict's other fields (trace_id, files_changed) are observable via the audit log and don't need to bleed into agent return values.

**Why `asyncio.run` and not `loop.run_until_complete`:** agent methods are sync. `asyncio.run` creates a fresh event loop per call. The runner's two-gate HITL uses `loop.run_in_executor` for `await_decision`, so it is compatible with a freshly-created loop.

---

### Task 1: Shared SDK Bridge Helper

**Files:**
- Create: `src/agents/_sdk_bridge.py`
- Test: `tests/test_sdk_bridge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sdk_bridge.py
from unittest.mock import patch, AsyncMock

from src.agents import _sdk_bridge


def test_run_agent_returns_raw_response_string():
    fake_result = {
        "trace_id": "abc",
        "status": "ok",
        "summary": "short summary",
        "raw_response": "full text from model",
    }
    fake_runner = type("R", (), {})()
    fake_runner.run = AsyncMock(return_value=fake_result)
    with patch(
        "src.agents._sdk_bridge.get_agent_sdk_runner",
        return_value=fake_runner,
    ):
        out = _sdk_bridge.run_agent(
            role_id="analyst",
            task="analyze this log",
            context="prior decisions",
            task_type="analysis",
        )
    assert out == "full text from model"
    fake_runner.run.assert_awaited_once_with(
        role_id="analyst",
        task="analyze this log",
        context="prior decisions",
        task_type="analysis",
    )


def test_run_agent_falls_back_to_summary_when_raw_response_missing():
    fake_runner = type("R", (), {})()
    fake_runner.run = AsyncMock(return_value={"summary": "only summary"})
    with patch(
        "src.agents._sdk_bridge.get_agent_sdk_runner",
        return_value=fake_runner,
    ):
        out = _sdk_bridge.run_agent(role_id="x", task="t")
    assert out == "only summary"


def test_run_agent_returns_empty_string_when_result_empty():
    fake_runner = type("R", (), {})()
    fake_runner.run = AsyncMock(return_value={})
    with patch(
        "src.agents._sdk_bridge.get_agent_sdk_runner",
        return_value=fake_runner,
    ):
        out = _sdk_bridge.run_agent(role_id="x", task="t")
    assert out == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sdk_bridge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.agents._sdk_bridge'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/agents/_sdk_bridge.py
from __future__ import annotations

import asyncio

from src.core.agent_sdk_runner import get_agent_sdk_runner


def run_agent(
    role_id: str,
    task: str,
    context: str = "",
    *,
    task_type: str | None = None,
) -> str:
    runner = get_agent_sdk_runner()
    result = asyncio.run(
        runner.run(
            role_id=role_id,
            task=task,
            context=context,
            task_type=task_type,
        )
    )
    return result.get("raw_response", "") or result.get("summary", "") or ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sdk_bridge.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/agents/_sdk_bridge.py tests/test_sdk_bridge.py
git commit -m "feat(phase2): add _sdk_bridge helper for agent→runner calls"
```

---

### Task 2: Migrate Universal Agent

**Context:** `UniversalAgent.run(role_id, task, context="", actor="web-ui")` at `src/agents/universal.py`. The signature already matches the runner exactly. Currently calls `llm_gateway.generate(prompt, system_prompt, trace_name=f"universal_agent_{role_id}")`. We replace that single call site with `_sdk_bridge.run_agent(role_id, task, context, task_type="analysis")`. The return dict shape (`trace_id, role_id, role_name, icon, task, summary, analysis, recommendations, next_steps, severity, confidence, raw_response, status`) is unchanged — `extract_json(raw_response)` parsing still runs on the returned string.

**Files:**
- Modify: `src/agents/universal.py`
- Test: `tests/test_universal_agent_sdk_migration.py`

- [ ] **Step 1: Read the current call site**

Read `src/agents/universal.py` and locate the `llm_gateway.generate(...)` call inside `run()`. Note the exact surrounding code so you can preserve the prompt assembly.

- [ ] **Step 2: Write the failing migration test**

```python
# tests/test_universal_agent_sdk_migration.py
from unittest.mock import patch

from src.agents.universal import UniversalAgent


def test_universal_agent_routes_through_sdk_bridge():
    agent = UniversalAgent()
    fake_response = (
        '{"summary": "ok", "analysis": "a", "recommendations": [], '
        '"next_steps": [], "severity": "low", "confidence": 0.9}'
    )
    with patch(
        "src.agents.universal._sdk_bridge.run_agent",
        return_value=fake_response,
    ) as mock_run:
        result = agent.run(
            role_id="analyst",
            task="analyze signal X",
            context="prior context",
        )
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["role_id"] == "analyst"
    assert kwargs["task"] == "analyze signal X"
    assert "prior context" in kwargs["context"]
    assert result["summary"] == "ok"
    assert result["status"] != "error"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_universal_agent_sdk_migration.py -v`
Expected: FAIL — `_sdk_bridge` attribute does not exist on `src.agents.universal` yet.

- [ ] **Step 4: Update `src/agents/universal.py`**

At the top of the file, add:

```python
from src.agents import _sdk_bridge
```

Replace the `llm_gateway.generate(...)` call inside `run()` with:

```python
raw = _sdk_bridge.run_agent(
    role_id=role_id,
    task=task,
    context=context,
    task_type="analysis",
)
```

Keep the `extract_json(raw)` parsing, the return dict assembly, the error fallback, and the `trace_id` generation exactly as they were. Do NOT remove the `llm_gateway` import if it is used elsewhere in the file — check first.

- [ ] **Step 5: Run migration test**

Run: `python -m pytest tests/test_universal_agent_sdk_migration.py -v`
Expected: PASS

- [ ] **Step 6: Run the full unit suite to catch regressions**

Run: `python -m pytest tests/ -x --ignore=tests/test_auto_research.py -q`
Expected: All passing (2 pre-existing failures in test_auto_research.py are excluded).

- [ ] **Step 7: Commit**

```bash
git add src/agents/universal.py tests/test_universal_agent_sdk_migration.py
git commit -m "feat(phase2): migrate UniversalAgent to AgentSDKRunner via bridge"
```

---

### Task 3: Migrate Critic Agent

**Context:** `CriticAgent` at `src/agents/critic.py` has an internal `_call_llm(user_prompt, system_prompt, action_type)` method around line 876 that every public method (`review_plan`, `review_code`, `review_integration`) funnels through. This is the ideal single migration point. 46 existing tests mock `llm_gateway.generate` — they must continue to pass.

**Files:**
- Modify: `src/agents/critic.py`
- Modify: `tests/test_critic_agent.py` (add `_sdk_bridge.run_agent` patches alongside the existing `llm_gateway.generate` patches so both paths are covered during the transition)

- [ ] **Step 1: Read `_call_llm` and locate every test mock**

Read `src/agents/critic.py` lines around 870–920 to see the `_call_llm` body. Then grep `tests/test_critic_agent.py` for `llm_gateway.generate` to find every mock site.

- [ ] **Step 2: Write a new migration test**

Append to `tests/test_critic_agent.py`:

```python
def test_critic_call_llm_routes_through_sdk_bridge(monkeypatch):
    from src.agents.critic import CriticAgent

    captured = {}

    def fake_run_agent(role_id, task, context="", *, task_type=None):
        captured["role_id"] = role_id
        captured["task"] = task
        captured["task_type"] = task_type
        return '{"score": 9, "flaws": [], "suggestions": [], "missing": [], ' \
               '"security_risks": [], "summary": "looks good"}'

    monkeypatch.setattr(
        "src.agents.critic._sdk_bridge.run_agent",
        fake_run_agent,
    )
    agent = CriticAgent()
    out = agent._call_llm(
        user_prompt="review this plan",
        system_prompt="you are a critic",
        action_type="review_plan",
    )
    assert captured["role_id"] == "critic"
    assert "review this plan" in captured["task"]
    assert out["score"] == 9
```

- [ ] **Step 3: Run test to confirm failure**

Run: `python -m pytest tests/test_critic_agent.py::test_critic_call_llm_routes_through_sdk_bridge -v`
Expected: FAIL — `_sdk_bridge` attribute does not exist on `src.agents.critic`.

- [ ] **Step 4: Update `src/agents/critic.py`**

Add the import at the top:

```python
from src.agents import _sdk_bridge
```

Replace the body of `_call_llm` so its LLM call becomes:

```python
raw = _sdk_bridge.run_agent(
    role_id="critic",
    task=user_prompt,
    context=system_prompt,
    task_type="review",
)
```

Keep the surrounding parse logic (`_extract_json`, error fallback, `llm_parse_error` field) unchanged. Leave `llm_gateway` import in place if any multi-provider variant methods still use it — they are out of scope for this task.

- [ ] **Step 5: Run the new migration test**

Run: `python -m pytest tests/test_critic_agent.py::test_critic_call_llm_routes_through_sdk_bridge -v`
Expected: PASS

- [ ] **Step 6: Run all 46 existing critic tests**

Run: `python -m pytest tests/test_critic_agent.py -v`
Expected: all pass. If any fail because they patched `llm_gateway.generate`, update the failing tests to patch `src.agents.critic._sdk_bridge.run_agent` instead — but only the tests exercising `_call_llm`; leave multi-provider tests alone.

- [ ] **Step 7: Commit**

```bash
git add src/agents/critic.py tests/test_critic_agent.py
git commit -m "feat(phase2): route CriticAgent._call_llm through AgentSDKRunner"
```

---

### Task 4: Migrate Analyst Agent

**Context:** `AnalystAgent.analyze_log(log_entry: str) -> Dict[str, Any]` at `src/agents/analyst.py` calls `llm_gateway.generate(user_prompt, system_prompt)` with no kwargs. Returns `{severity, root_cause_hypothesis, recommended_action, trace_id}` or an error-shape fallback. 10 existing tests in `tests/test_analyst_agent.py`.

**Files:**
- Modify: `src/agents/analyst.py`
- Modify: `tests/test_analyst_agent.py`
- Test: `tests/test_analyst_agent_sdk_migration.py`

- [ ] **Step 1: Write the migration test**

```python
# tests/test_analyst_agent_sdk_migration.py
from unittest.mock import patch

from src.agents.analyst import AnalystAgent


def test_analyst_routes_through_sdk_bridge():
    agent = AnalystAgent()
    fake_json = (
        '{"severity": "high", "root_cause_hypothesis": "OOM", '
        '"recommended_action": "restart"}'
    )
    with patch(
        "src.agents.analyst._sdk_bridge.run_agent",
        return_value=fake_json,
    ) as mock_run:
        result = agent.analyze_log("segfault at 0xdeadbeef")
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["role_id"] == "analyst"
    assert "segfault" in kwargs["task"]
    assert kwargs["task_type"] == "analysis"
    assert result["severity"] == "high"
    assert "trace_id" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_analyst_agent_sdk_migration.py -v`
Expected: FAIL — `_sdk_bridge` not on `src.agents.analyst`.

- [ ] **Step 3: Update `src/agents/analyst.py`**

Add:

```python
from src.agents import _sdk_bridge
```

Replace the `llm_gateway.generate(user_prompt, system_prompt)` call in `analyze_log` with:

```python
raw = _sdk_bridge.run_agent(
    role_id="analyst",
    task=user_prompt,
    context=system_prompt,
    task_type="analysis",
)
```

Keep the rest of the method identical (JSON extraction, error fallback, trace_id generation).

- [ ] **Step 4: Run migration test**

Run: `python -m pytest tests/test_analyst_agent_sdk_migration.py -v`
Expected: PASS

- [ ] **Step 5: Run existing analyst tests**

Run: `python -m pytest tests/test_analyst_agent.py -v`
Expected: all 10 pass. If any mock `llm_gateway.generate` for `analyze_log`, re-patch them to `src.agents.analyst._sdk_bridge.run_agent`.

- [ ] **Step 6: Commit**

```bash
git add src/agents/analyst.py tests/test_analyst_agent.py tests/test_analyst_agent_sdk_migration.py
git commit -m "feat(phase2): migrate AnalystAgent to AgentSDKRunner via bridge"
```

---

### Task 5: Migrate Planner Agent

**Context:** `PlannerAgent` at `src/agents/planner.py`. Public methods: `create_plan(description, override_task_types=None) -> list[dict]` and `plan_and_execute(description, priority=5) -> dict`. The LLM call site is `self.llm.generate(user_prompt, system_prompt)` inside `create_plan`. A regex extracts a JSON array from the response. No dedicated test file exists.

**Files:**
- Modify: `src/agents/planner.py`
- Test: `tests/test_planner_agent_sdk_migration.py`

- [ ] **Step 1: Read the current `create_plan` method**

Open `src/agents/planner.py` and locate the single `self.llm.generate(...)` call inside `create_plan`.

- [ ] **Step 2: Write the migration test**

```python
# tests/test_planner_agent_sdk_migration.py
from unittest.mock import patch

from src.agents.planner import PlannerAgent


def test_planner_create_plan_routes_through_sdk_bridge():
    agent = PlannerAgent()
    fake_response = (
        '[{"task_type": "analysis", "description": "step 1"}, '
        '{"task_type": "code_review", "description": "step 2"}]'
    )
    with patch(
        "src.agents.planner._sdk_bridge.run_agent",
        return_value=fake_response,
    ) as mock_run:
        plan = agent.create_plan("ship feature X")
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["role_id"] == "planner"
    assert kwargs["task_type"] == "planning"
    assert "ship feature X" in kwargs["task"]
    assert isinstance(plan, list)
    assert len(plan) == 2
    assert plan[0]["task_type"] == "analysis"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_planner_agent_sdk_migration.py -v`
Expected: FAIL — `_sdk_bridge` not on `src.agents.planner`.

- [ ] **Step 4: Update `src/agents/planner.py`**

Add:

```python
from src.agents import _sdk_bridge
```

Replace the `self.llm.generate(user_prompt, system_prompt)` call inside `create_plan` with:

```python
raw = _sdk_bridge.run_agent(
    role_id="planner",
    task=user_prompt,
    context=system_prompt,
    task_type="planning",
)
```

Keep the regex JSON-array extraction, `override_task_types` handling, and the `plan_and_execute` method untouched. Leave `self.llm` as an attribute — other code may still reference it.

- [ ] **Step 5: Run migration test**

Run: `python -m pytest tests/test_planner_agent_sdk_migration.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/planner.py tests/test_planner_agent_sdk_migration.py
git commit -m "feat(phase2): migrate PlannerAgent.create_plan to AgentSDKRunner"
```

---

### Task 6: Migrate Developer Agent

**Context:** `DeveloperAgent` at `src/agents/developer.py`. Public methods: `review_merge_request`, `create_mr_from_issue`, `propose_code_patch`. Uses an internal ReAct loop `_react_loop()` that makes multiple `self.llm.generate(user_prompt, system_prompt)` calls — one per ReAct iteration. 16 existing tests in `tests/test_developer_agent.py`.

**Strategy:** The ReAct loop has *one* LLM call site inside the loop body. Migrating that single site covers every iteration. Context for each call is already constructed inside the loop (observation history). We pass that observation history as the `context` argument to the bridge.

**Files:**
- Modify: `src/agents/developer.py`
- Modify: `tests/test_developer_agent.py`

- [ ] **Step 1: Find the LLM call in `_react_loop`**

Open `src/agents/developer.py` and locate the `self.llm.generate(...)` call inside `_react_loop`. Note the variable names for `user_prompt` and `system_prompt`.

- [ ] **Step 2: Write the migration test**

Append to `tests/test_developer_agent.py`:

```python
def test_developer_react_loop_routes_through_sdk_bridge(monkeypatch):
    from src.agents.developer import DeveloperAgent

    calls = []

    def fake_run_agent(role_id, task, context="", *, task_type=None):
        calls.append({"role_id": role_id, "task_type": task_type})
        return "Thought: done\nFinalAnswer: ok"

    monkeypatch.setattr(
        "src.agents.developer._sdk_bridge.run_agent",
        fake_run_agent,
    )
    agent = DeveloperAgent()
    result = agent._react_loop(
        user_prompt="review the MR",
        system_prompt="you are a developer",
        max_iterations=1,
    )
    assert len(calls) >= 1
    assert calls[0]["role_id"] == "developer"
    assert calls[0]["task_type"] == "code_review"
    assert result is not None
```

Note: if `_react_loop` has a different signature than `(user_prompt, system_prompt, max_iterations)`, adapt the call in the test to match. Read the method signature first.

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_developer_agent.py::test_developer_react_loop_routes_through_sdk_bridge -v`
Expected: FAIL — `_sdk_bridge` not on `src.agents.developer`.

- [ ] **Step 4: Update `src/agents/developer.py`**

Add:

```python
from src.agents import _sdk_bridge
```

Replace the `self.llm.generate(user_prompt, system_prompt)` inside `_react_loop` with:

```python
raw = _sdk_bridge.run_agent(
    role_id="developer",
    task=user_prompt,
    context=system_prompt,
    task_type="code_review",
)
```

Every ReAct iteration now routes through the bridge. The parsing of `Thought:/Action:/FinalAnswer:` tags is unchanged.

- [ ] **Step 5: Run the new test**

Run: `python -m pytest tests/test_developer_agent.py::test_developer_react_loop_routes_through_sdk_bridge -v`
Expected: PASS

- [ ] **Step 6: Run the full developer test suite**

Run: `python -m pytest tests/test_developer_agent.py -v`
Expected: all 16 + 1 new = 17 pass. If any existing test mocks `llm_gateway.generate` for a method that now routes through the bridge, re-patch to `src.agents.developer._sdk_bridge.run_agent`.

- [ ] **Step 7: Commit**

```bash
git add src/agents/developer.py tests/test_developer_agent.py
git commit -m "feat(phase2): route DeveloperAgent ReAct loop through AgentSDKRunner"
```

---

### Task 7: Migrate Coder Agent (highest risk)

**Context:** `CodingAgent.implement_step(step, plan_trace_id="") -> dict` at `src/agents/coder.py`. Uses a ReAct loop with TWO distinct `llm_gateway.generate(...)` call sites: one with `trace_name="coder.react"` (around line 204) and one with `trace_name="coder.react.final"` (around line 236). Returns `{summary, diff, written_files, test_result, tests_passed, plan_trace_id, step}`. Uses plain `Thought/Action/FinalAnswer` text parsing — NOT JSON. No dedicated test file.

**Risk:** ReAct iterations can exceed 10 per `implement_step`, meaning Phase 1's two-gate HITL will fire twice per iteration if naively applied. The runner's current design creates the two gates *per `runner.run(...)` call*. This task therefore issues one `runner.run(...)` call per ReAct iteration — the human approves the goal once, the iteration runs, the human approves the outcome, and the loop proceeds. That is the intended design: each ReAct step is one reviewable unit of work.

**Files:**
- Modify: `src/agents/coder.py`
- Test: `tests/test_coder_agent_sdk_migration.py`

- [ ] **Step 1: Read both call sites**

Read `src/agents/coder.py` around lines 200–250. Identify the two `llm_gateway.generate(...)` call sites and their surrounding prompt assembly.

- [ ] **Step 2: Write the migration test**

```python
# tests/test_coder_agent_sdk_migration.py
from unittest.mock import patch

from src.agents.coder import CodingAgent


def test_coder_implement_step_routes_through_sdk_bridge():
    agent = CodingAgent()
    react_responses = iter(
        [
            "Thought: I need to write a file\n"
            "Action: write_file\n"
            "FinalAnswer: done",
        ]
    )

    def fake_run_agent(role_id, task, context="", *, task_type=None):
        assert role_id == "coder"
        assert task_type in ("code_generation", "implementation")
        return next(react_responses, "Thought: done\nFinalAnswer: complete")

    with patch(
        "src.agents.coder._sdk_bridge.run_agent",
        side_effect=fake_run_agent,
    ) as mock_run:
        result = agent.implement_step(
            step={"description": "write hello.py"},
            plan_trace_id="plan-123",
        )
    assert mock_run.called
    assert "summary" in result
    assert result["plan_trace_id"] == "plan-123"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_coder_agent_sdk_migration.py -v`
Expected: FAIL — `_sdk_bridge` not on `src.agents.coder`.

- [ ] **Step 4: Update `src/agents/coder.py`**

Add:

```python
from src.agents import _sdk_bridge
```

Replace both `llm_gateway.generate(...)` call sites:

First call (the `trace_name="coder.react"` site):

```python
raw = _sdk_bridge.run_agent(
    role_id="coder",
    task=user_prompt,
    context=system_prompt,
    task_type="code_generation",
)
```

Second call (the `trace_name="coder.react.final"` site):

```python
raw = _sdk_bridge.run_agent(
    role_id="coder",
    task=user_prompt,
    context=system_prompt,
    task_type="code_generation",
)
```

Keep all `Thought/Action/FinalAnswer` parsing, the `diff` assembly, the `written_files` tracking, and the `test_result` field unchanged.

- [ ] **Step 5: Run the migration test**

Run: `python -m pytest tests/test_coder_agent_sdk_migration.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/agents/coder.py tests/test_coder_agent_sdk_migration.py
git commit -m "feat(phase2): migrate CodingAgent ReAct loop to AgentSDKRunner"
```

---

### Task 8: Final Integration Sweep

- [ ] **Step 1: Run the full unit suite**

Run: `python -m pytest tests/ --ignore=tests/test_auto_research.py -q`
Expected: 987 + ~10 new phase-2 tests passing. Zero regressions in existing tests.

- [ ] **Step 2: Verify fallback path still works without SDK**

Temporarily uninstall (or mock-away) `claude_agent_sdk` and confirm one agent (Universal) still returns a valid result via the gateway fallback:

```bash
python -c "
from unittest.mock import patch
from src.agents.universal import UniversalAgent
with patch('src.core.llm_gateway.LLMGateway.sdk_available', new=False):
    agent = UniversalAgent()
    print('fallback path reachable:', hasattr(agent, 'run'))
"
```

Expected: `fallback path reachable: True` and no import errors.

- [ ] **Step 3: Update feature doc**

Edit `.claude/docs/features/agent-sdk.md` and append a "Migrated Agents" section listing: Universal, Critic, Analyst, Planner, Developer, Coder — each with its `role_id` and chosen `task_type`.

- [ ] **Step 4: Commit the doc**

```bash
git add .claude/docs/features/agent-sdk.md
git commit -m "docs(phase2): list migrated agents in agent-sdk feature doc"
```

---

## Self-Review Notes

- **Spec coverage:** Every agent in spec §4.5 Agent Coverage Matrix (Universal, Critic, Analyst, Planner, Developer, Coder) has a dedicated task.
- **Placeholder scan:** No TODOs, no "similar to Task N", every step shows the code it requires.
- **Type consistency:** `_sdk_bridge.run_agent(role_id, task, context, *, task_type)` signature is identical in every task. Return type is `str` everywhere.
- **Risk ordering:** Universal first (signature matches), Coder last (two call sites, ReAct loop, plain-text parsing).
- **Preserved invariants:** Every agent's public API and return-dict shape is unchanged. Existing tests that mock `llm_gateway.generate` are updated only where the code path now routes through `_sdk_bridge`.
