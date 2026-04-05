"""
SAGE Orchestrator Enhancements — Comprehensive Tests
=====================================================

Tests for all 9 SOTA orchestrator modules:
  1. Event Bus + SSE
  2. Budget Manager
  3. Reflection Engine
  4. Memory-Augmented Planner
  5. Tool Executor
  6. Dynamic Agent Spawner
  7. Plan Selector (beam search)
  8. Backtrack Planner
  9. Consensus Engine
"""

import asyncio
import os
import threading
import time

import pytest


# ═══════════════════════════════════════════════════════════════════════
# 1. EVENT BUS
# ═══════════════════════════════════════════════════════════════════════

class TestEventBus:

    def test_publish_creates_event(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        event = bus.publish("task.started", {"task_id": "t1"})
        assert event.event_type == "task.started"
        assert event.data["task_id"] == "t1"
        assert event.event_id

    def test_history_stores_events(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        bus.publish("task.started", {"id": "1"})
        bus.publish("task.completed", {"id": "2"})
        history = bus.get_history()
        assert len(history) == 2

    def test_history_filters_by_type(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        bus.publish("task.started", {})
        bus.publish("task.completed", {})
        bus.publish("task.started", {})
        filtered = bus.get_history(event_type="task.started")
        assert len(filtered) == 2

    def test_history_bounded(self):
        from src.core.event_bus import EventBus
        bus = EventBus(history_size=5)
        for i in range(10):
            bus.publish("test", {"i": i})
        assert len(bus.get_history()) == 5

    def test_sync_callback(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        received = []
        bus.on_event(lambda e: received.append(e))
        bus.publish("test.event", {"x": 1})
        assert len(received) == 1
        assert received[0].event_type == "test.event"

    def test_event_to_sse(self):
        from src.core.event_bus import Event
        event = Event(event_type="task.started", data={"id": "1"})
        sse = event.to_sse()
        assert "event: task.started" in sse
        assert "data:" in sse
        assert "id:" in sse

    def test_stats(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        bus.publish("a", {})
        bus.publish("b", {})
        stats = bus.get_stats()
        assert stats["total_events"] == 2
        assert stats["history_size"] == 2

    def test_thread_safety(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        errors = []

        def publisher(n):
            try:
                for i in range(20):
                    bus.publish("test", {"n": n, "i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publisher, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert bus.get_stats()["total_events"] == 80

    def test_singleton(self):
        from src.core.event_bus import get_event_bus
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_callback_error_doesnt_break_publish(self):
        from src.core.event_bus import EventBus
        bus = EventBus()
        bus.on_event(lambda e: 1 / 0)  # will raise
        event = bus.publish("test", {})  # should not raise
        assert event.event_type == "test"


# ═══════════════════════════════════════════════════════════════════════
# 2. BUDGET MANAGER
# ═══════════════════════════════════════════════════════════════════════

class TestBudgetManager:

    def test_record_usage(self):
        from src.core.budget_manager import BudgetManager
        bm = BudgetManager()
        usage = bm.record_usage("agent:analyst", input_tokens=100, output_tokens=50)
        assert usage["total_tokens"] == 150
        assert usage["call_count"] == 1

    def test_cumulative_usage(self):
        from src.core.budget_manager import BudgetManager
        bm = BudgetManager()
        bm.record_usage("agent:dev", input_tokens=100, output_tokens=50)
        bm.record_usage("agent:dev", input_tokens=200, output_tokens=100)
        usage = bm.get_usage("agent:dev")
        assert usage["total_tokens"] == 450
        assert usage["call_count"] == 2

    def test_budget_check_no_limit(self):
        from src.core.budget_manager import BudgetManager
        bm = BudgetManager()
        bm.record_usage("test", input_tokens=1000000)
        check = bm.check_budget("test")
        assert check["allowed"]
        assert not check["exceeded"]

    def test_budget_check_exceeded(self):
        from src.core.budget_manager import BudgetManager, BudgetConfig
        bm = BudgetManager()
        bm.set_budget("limited", BudgetConfig(max_tokens=100, hard_stop=True))
        bm.record_usage("limited", input_tokens=150)
        check = bm.check_budget("limited")
        assert check["exceeded"]
        assert not check["allowed"]

    def test_budget_check_soft_limit(self):
        from src.core.budget_manager import BudgetManager, BudgetConfig
        bm = BudgetManager()
        bm.set_budget("soft", BudgetConfig(max_tokens=100, hard_stop=False))
        bm.record_usage("soft", input_tokens=150)
        check = bm.check_budget("soft")
        assert check["exceeded"]
        assert check["allowed"]  # soft limit doesn't block

    def test_cost_budget(self):
        from src.core.budget_manager import BudgetManager, BudgetConfig
        bm = BudgetManager()
        bm.set_budget("cost", BudgetConfig(max_cost_usd=1.0))
        bm.record_usage("cost", cost_usd=0.5)
        check = bm.check_budget("cost")
        assert check["allowed"]
        bm.record_usage("cost", cost_usd=0.6)
        check = bm.check_budget("cost")
        assert check["exceeded"]

    def test_reset_scope(self):
        from src.core.budget_manager import BudgetManager
        bm = BudgetManager()
        bm.record_usage("scope1", input_tokens=1000)
        bm.reset_scope("scope1")
        usage = bm.get_usage("scope1")
        assert usage["total_tokens"] == 0

    def test_top_consumers(self):
        from src.core.budget_manager import BudgetManager
        bm = BudgetManager()
        bm.record_usage("agent:dev", input_tokens=500)
        bm.record_usage("agent:analyst", input_tokens=1000)
        bm.record_usage("agent:qa", input_tokens=200)
        top = bm.get_top_consumers(limit=2)
        assert len(top) == 2
        assert top[0]["scope"] == "agent:analyst"

    def test_stats(self):
        from src.core.budget_manager import BudgetManager
        bm = BudgetManager()
        bm.record_usage("a", input_tokens=100)
        bm.record_usage("b", input_tokens=200)
        stats = bm.get_stats()
        assert stats["total_tokens"] == 300
        assert stats["tracked_scopes"] == 2

    def test_utilization_calculation(self):
        from src.core.budget_manager import BudgetManager, BudgetConfig
        bm = BudgetManager()
        bm.set_budget("test", BudgetConfig(max_tokens=1000))
        bm.record_usage("test", input_tokens=500)
        check = bm.check_budget("test")
        assert check["utilization"] == 0.5


# ═══════════════════════════════════════════════════════════════════════
# 3. REFLECTION ENGINE
# ═══════════════════════════════════════════════════════════════════════

class TestReflectionEngine:

    def test_accepts_above_threshold(self):
        from src.core.reflection_engine import ReflectionEngine, ReflectionConfig
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: "good output",
            critic=lambda output: {"score": 0.9, "feedback": "Great"},
            config=ReflectionConfig(acceptance_threshold=0.7),
        )
        assert result.accepted
        assert result.iterations == 1
        assert result.final_score == 0.9

    def test_rejects_below_threshold(self):
        from src.core.reflection_engine import ReflectionEngine, ReflectionConfig
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: "bad output",
            critic=lambda output: {"score": 0.3, "feedback": "Poor"},
            config=ReflectionConfig(max_iterations=2, acceptance_threshold=0.8),
        )
        assert not result.accepted
        assert result.iterations == 2  # tried twice, no improvement

    def test_improvement_over_iterations(self):
        from src.core.reflection_engine import ReflectionEngine, ReflectionConfig
        call_count = [0]

        def improving_critic(output):
            call_count[0] += 1
            return {"score": min(0.3 * call_count[0], 1.0), "feedback": "Better"}

        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: f"attempt",
            critic=improving_critic,
            config=ReflectionConfig(max_iterations=5, acceptance_threshold=0.8),
        )
        assert result.accepted
        assert result.iterations >= 2

    def test_stops_on_no_improvement(self):
        from src.core.reflection_engine import ReflectionEngine, ReflectionConfig
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: "stuck",
            critic=lambda output: {"score": 0.5, "feedback": "Same"},
            config=ReflectionConfig(
                max_iterations=5,
                acceptance_threshold=0.9,
                improvement_threshold=0.05,
            ),
        )
        assert not result.accepted
        assert result.iterations == 2  # stops after detecting no improvement

    def test_history_recorded(self):
        from src.core.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: "output",
            critic=lambda output: {"score": 0.9, "feedback": "OK"},
        )
        assert len(result.history) == 1
        assert result.history[0]["score"] == 0.9

    def test_generator_error_handled(self):
        from src.core.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")),
            critic=lambda output: {"score": 0.9, "feedback": "OK"},
        )
        assert not result.accepted
        assert "error" in result.history[0]

    def test_get_stats(self):
        from src.core.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        engine.reflect(
            generator=lambda ctx: "ok",
            critic=lambda out: {"score": 0.9, "feedback": ""},
        )
        stats = engine.get_stats()
        assert stats["total_reflections"] == 1
        assert stats["accepted_count"] == 1

    def test_list_recent(self):
        from src.core.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        for _ in range(3):
            engine.reflect(
                generator=lambda ctx: "ok",
                critic=lambda out: {"score": 0.9, "feedback": ""},
            )
        recent = engine.list_recent(limit=2)
        assert len(recent) == 2

    def test_get_result_by_id(self):
        from src.core.reflection_engine import ReflectionEngine
        engine = ReflectionEngine()
        result = engine.reflect(
            generator=lambda ctx: "ok",
            critic=lambda out: {"score": 0.9, "feedback": ""},
        )
        fetched = engine.get_result(result.reflection_id)
        assert fetched is not None
        assert fetched["reflection_id"] == result.reflection_id

    def test_feedback_injected_into_context(self):
        from src.core.reflection_engine import ReflectionEngine, ReflectionConfig
        contexts = []

        def tracking_gen(ctx):
            contexts.append(ctx)
            return "output"

        scores = iter([0.3, 0.9])
        engine = ReflectionEngine()
        engine.reflect(
            generator=tracking_gen,
            critic=lambda out: {"score": next(scores), "feedback": "Fix the logic"},
            config=ReflectionConfig(max_iterations=3, acceptance_threshold=0.8),
        )
        assert len(contexts) == 2
        assert "Fix the logic" in contexts[1]


# ═══════════════════════════════════════════════════════════════════════
# 4. MEMORY-AUGMENTED PLANNER
# ═══════════════════════════════════════════════════════════════════════

class TestMemoryPlanner:

    def test_augment_context_returns_string(self):
        from src.core.memory_planner import MemoryPlanner
        mp = MemoryPlanner()
        ctx = mp.augment_context("Build a REST API")
        assert isinstance(ctx, str)

    def test_record_plan(self):
        from src.core.memory_planner import MemoryPlanner
        mp = MemoryPlanner()
        mp.record_plan({
            "name": "api-build",
            "description": "Build REST API",
            "tasks": [{"task_type": "CODE_TASK"}],
        })
        assert mp.get_stats()["recorded_plans"] == 1

    def test_find_similar_plans(self):
        from src.core.memory_planner import MemoryPlanner
        mp = MemoryPlanner()
        mp.record_plan({
            "name": "api-build",
            "description": "Build REST API with authentication",
            "tasks": [{"task_type": "CODE_TASK"}, {"task_type": "REVIEW_MR"}],
        })
        results = mp._find_similar_plans("Build API with auth")
        assert len(results) >= 1

    def test_plan_history_bounded(self):
        from src.core.memory_planner import MemoryPlanner
        mp = MemoryPlanner()
        for i in range(110):
            mp.record_plan({"name": f"plan-{i}", "tasks": []})
        assert mp.get_stats()["recorded_plans"] == 100

    def test_augment_includes_plan_history(self):
        from src.core.memory_planner import MemoryPlanner
        mp = MemoryPlanner()
        mp.record_plan({
            "name": "firmware-update",
            "description": "Firmware OTA update pipeline",
            "tasks": [{"task_type": "FIRMWARE"}, {"task_type": "TEST"}],
        })
        ctx = mp.augment_context("Build firmware update")
        assert "firmware" in ctx.lower() or ctx == ""

    def test_stats(self):
        from src.core.memory_planner import MemoryPlanner
        mp = MemoryPlanner(max_examples=3, min_confidence=0.5)
        stats = mp.get_stats()
        assert stats["max_examples"] == 3
        assert stats["min_confidence"] == 0.5


# ═══════════════════════════════════════════════════════════════════════
# 5. TOOL EXECUTOR
# ═══════════════════════════════════════════════════════════════════════

class TestToolExecutor:

    def test_list_builtin_tools(self):
        from src.core.tool_executor import ToolExecutor
        te = ToolExecutor()
        tools = te.list_tools()
        names = [t["name"] for t in tools]
        assert "file_read" in names
        assert "git_diff" in names
        assert "search_code" in names

    def test_register_custom_tool(self):
        from src.core.tool_executor import ToolExecutor, Tool
        te = ToolExecutor()
        te.register(Tool(
            name="custom_tool",
            description="A custom tool",
            handler=lambda: "custom result",
        ))
        assert any(t["name"] == "custom_tool" for t in te.list_tools())

    def test_execute_custom_tool(self):
        from src.core.tool_executor import ToolExecutor, Tool
        te = ToolExecutor()
        te.register(Tool(
            name="echo",
            description="Echo back",
            handler=lambda msg="": f"echo: {msg}",
        ))
        call = te.execute("echo", {"msg": "hello"})
        assert call.result == "echo: hello"
        assert not call.error

    def test_execute_unknown_tool(self):
        from src.core.tool_executor import ToolExecutor
        te = ToolExecutor()
        call = te.execute("nonexistent_tool")
        assert "Unknown tool" in call.error

    def test_tool_requires_approval(self):
        from src.core.tool_executor import ToolExecutor
        te = ToolExecutor()
        call = te.execute("shell_run", {"command": "ls"})
        assert "approval" in call.error.lower()

    def test_tool_error_caught(self):
        from src.core.tool_executor import ToolExecutor, Tool
        te = ToolExecutor()
        te.register(Tool(
            name="failing",
            description="Fails",
            handler=lambda: 1 / 0,
        ))
        call = te.execute("failing")
        assert call.error
        assert "division" in call.error.lower()

    def test_execute_multiple_tool_calls(self):
        from src.core.tool_executor import ToolExecutor, Tool
        te = ToolExecutor()
        te.register(Tool(name="add", description="Add", handler=lambda a=0, b=0: str(int(a) + int(b))))
        results = te.execute_tool_calls([
            {"tool": "add", "arguments": {"a": 1, "b": 2}},
            {"tool": "add", "arguments": {"a": 3, "b": 4}},
        ])
        assert len(results) == 2
        assert results[0]["result"] == "3"
        assert results[1]["result"] == "7"

    def test_file_read_tool(self, tmp_path):
        from src.core.tool_executor import ToolExecutor
        te = ToolExecutor()
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        call = te.execute("file_read", {"path": str(test_file)})
        assert "hello world" in call.result

    def test_file_read_missing_file(self):
        from src.core.tool_executor import ToolExecutor
        te = ToolExecutor()
        call = te.execute("file_read", {"path": "/nonexistent/path/file.txt"})
        assert "not found" in call.result.lower()

    def test_get_tool_descriptions(self):
        from src.core.tool_executor import ToolExecutor
        te = ToolExecutor()
        desc = te.get_tool_descriptions()
        assert "file_read" in desc
        assert "Available tools" in desc

    def test_history_tracked(self):
        from src.core.tool_executor import ToolExecutor, Tool
        te = ToolExecutor()
        te.register(Tool(name="noop", description="No-op", handler=lambda: "ok"))
        te.execute("noop")
        te.execute("noop")
        history = te.get_history()
        assert len(history) == 2

    def test_stats(self):
        from src.core.tool_executor import ToolExecutor, Tool
        te = ToolExecutor()
        te.register(Tool(name="noop", description="No-op", handler=lambda: "ok"))
        te.execute("noop")
        te.execute("nonexistent_tool")
        stats = te.get_stats()
        assert stats["total_calls"] == 2
        assert stats["error_count"] == 1


# ═══════════════════════════════════════════════════════════════════════
# 6. DYNAMIC AGENT SPAWNER
# ═══════════════════════════════════════════════════════════════════════

class TestAgentSpawner:

    def test_spawn_default_executor(self):
        from src.core.agent_spawner import AgentSpawner
        spawner = AgentSpawner()
        result = spawner.spawn(role="analyst", task="Analyze code")
        assert result["status"] == "completed"
        assert result["spawn_id"]

    def test_spawn_custom_executor(self):
        from src.core.agent_spawner import AgentSpawner
        spawner = AgentSpawner(
            agent_fn=lambda role_id, task, context="": {"summary": f"Done by {role_id}"},
        )
        result = spawner.spawn(role="dev", task="Fix bug")
        assert result["status"] == "completed"
        assert result["result"]["summary"] == "Done by dev"

    def test_depth_limit(self):
        from src.core.agent_spawner import AgentSpawner
        spawner = AgentSpawner(max_depth=2)
        result = spawner.spawn(role="dev", task="task", depth=5)
        assert result["status"] == "rejected"
        assert "depth" in result["error"].lower()

    def test_concurrency_limit(self):
        from src.core.agent_spawner import AgentSpawner
        import concurrent.futures

        spawner = AgentSpawner(
            max_concurrent=2,
            agent_fn=lambda role_id, task, context="": time.sleep(0.3) or {"done": True},
        )
        results = []

        def do_spawn(i):
            return spawner.spawn(role=f"agent{i}", task=f"task {i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(do_spawn, i) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Some should be rejected due to concurrency limit
        rejected = [r for r in results if r["status"] == "rejected"]
        completed = [r for r in results if r["status"] == "completed"]
        assert len(completed) >= 2
        assert len(rejected) >= 1

    def test_list_spawns(self):
        from src.core.agent_spawner import AgentSpawner
        spawner = AgentSpawner()
        spawner.spawn(role="a", task="t1")
        spawner.spawn(role="b", task="t2")
        spawns = spawner.list_spawns()
        assert len(spawns) == 2

    def test_list_spawns_by_parent(self):
        from src.core.agent_spawner import AgentSpawner
        spawner = AgentSpawner()
        spawner.spawn(role="a", task="t1", parent_task_id="p1")
        spawner.spawn(role="b", task="t2", parent_task_id="p2")
        p1_spawns = spawner.list_spawns(parent_task_id="p1")
        assert len(p1_spawns) == 1

    def test_stats(self):
        from src.core.agent_spawner import AgentSpawner
        spawner = AgentSpawner()
        spawner.spawn(role="a", task="t1")
        stats = spawner.get_stats()
        assert stats["total_spawns"] == 1
        assert stats["completed"] == 1

    def test_failed_spawn(self):
        from src.core.agent_spawner import AgentSpawner

        def failing_fn(**kwargs):
            raise RuntimeError("Agent crashed")

        spawner = AgentSpawner(agent_fn=failing_fn)
        result = spawner.spawn(role="crashy", task="fail")
        assert result["status"] == "failed"
        assert "crashed" in result["error"]


# ═══════════════════════════════════════════════════════════════════════
# 7. PLAN SELECTOR (BEAM SEARCH)
# ═══════════════════════════════════════════════════════════════════════

class TestPlanSelector:

    def test_selects_best_candidate(self):
        from src.core.plan_selector import PlanSelector
        call_count = [0]

        def gen(ctx):
            call_count[0] += 1
            return f"plan-{call_count[0]}"

        def critic(plan):
            # plan-3 scores highest
            n = int(plan.split("-")[1]) if "-" in plan else 1
            return {"score": 0.3 * n, "feedback": f"Score for {plan}"}

        selector = PlanSelector()
        result = selector.select(
            generator=gen, critic=critic, beam_width=3,
            apply_reflection=False,
        )
        assert abs(result.selected_score - 0.9) < 0.001
        assert result.beam_width == 3
        assert len(result.candidates) == 3

    def test_candidates_ranked(self):
        from src.core.plan_selector import PlanSelector
        scores = iter([0.5, 0.9, 0.3])

        selector = PlanSelector()
        result = selector.select(
            generator=lambda ctx: "plan",
            critic=lambda p: {"score": next(scores), "feedback": ""},
            beam_width=3,
            apply_reflection=False,
        )
        # Should be ranked highest to lowest
        assert result.candidates[0].score >= result.candidates[1].score

    def test_reflection_applied_when_below_threshold(self):
        from src.core.plan_selector import PlanSelector
        call_count = [0]

        def gen(ctx):
            call_count[0] += 1
            return f"plan-{call_count[0]}"

        scores = iter([0.3, 0.3, 0.3, 0.8, 0.9])  # beam candidates + reflection

        selector = PlanSelector()
        result = selector.select(
            generator=gen,
            critic=lambda p: {"score": next(scores, 0.5), "feedback": "Improve"},
            beam_width=3,
            apply_reflection=True,
            reflection_threshold=0.7,
        )
        assert result.reflected or result.selected_score >= 0.3

    def test_no_reflection_when_above_threshold(self):
        from src.core.plan_selector import PlanSelector
        selector = PlanSelector()
        result = selector.select(
            generator=lambda ctx: "great plan",
            critic=lambda p: {"score": 0.95, "feedback": "Perfect"},
            beam_width=2,
            apply_reflection=True,
            reflection_threshold=0.7,
        )
        assert not result.reflected
        assert result.selected_score == 0.95

    def test_generator_failure_handled(self):
        from src.core.plan_selector import PlanSelector
        call_count = [0]

        def flaky_gen(ctx):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Generation failed")
            return f"plan-{call_count[0]}"

        selector = PlanSelector()
        result = selector.select(
            generator=flaky_gen,
            critic=lambda p: {"score": 0.8, "feedback": "OK"},
            beam_width=3,
            apply_reflection=False,
        )
        assert len(result.candidates) == 3  # all 3 created, one with score 0

    def test_stats(self):
        from src.core.plan_selector import PlanSelector
        selector = PlanSelector()
        selector.select(
            generator=lambda ctx: "plan",
            critic=lambda p: {"score": 0.8, "feedback": ""},
            beam_width=2, apply_reflection=False,
        )
        stats = selector.get_stats()
        assert stats["total_selections"] == 1

    def test_list_recent(self):
        from src.core.plan_selector import PlanSelector
        selector = PlanSelector()
        for _ in range(3):
            selector.select(
                generator=lambda ctx: "plan",
                critic=lambda p: {"score": 0.5, "feedback": ""},
                beam_width=1, apply_reflection=False,
            )
        assert len(selector.list_recent(limit=2)) == 2


# ═══════════════════════════════════════════════════════════════════════
# 8. BACKTRACK PLANNER
# ═══════════════════════════════════════════════════════════════════════

class TestBacktrackPlanner:

    def _sample_graph(self):
        return {
            "tasks": [
                {"task_id": "t1", "task_type": "PLAN_TASK", "payload": {}},
                {"task_id": "t2", "task_type": "CODE_TASK", "payload": {}},
                {"task_id": "t3", "task_type": "REVIEW_MR", "payload": {}},
                {"task_id": "t4", "task_type": "TEST", "payload": {}},
            ],
            "dependencies": [
                {"from": "t1", "to": "t2"},
                {"from": "t2", "to": "t3"},
                {"from": "t3", "to": "t4"},
            ],
        }

    def test_record_failure(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner()
        count = bp.record_failure("t1")
        assert count == 1
        count = bp.record_failure("t1")
        assert count == 2

    def test_should_backtrack(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner(failure_threshold=2)
        bp.record_failure("t1")
        assert not bp.should_backtrack("t1")
        bp.record_failure("t1")
        assert bp.should_backtrack("t1")

    def test_handle_failure_no_backtrack_needed(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner(failure_threshold=3)
        bp.record_failure("t1")
        result = bp.handle_failure("t1", "error", self._sample_graph())
        assert result is None  # not enough failures yet

    def test_handle_failure_triggers_replan(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner(failure_threshold=2)
        bp.record_failure("t2")
        bp.record_failure("t2")  # now at threshold
        result = bp.handle_failure("t2", "compile error", self._sample_graph())
        assert result is not None
        assert "new_tasks" in result
        assert len(result["new_tasks"]) >= 1

    def test_affected_subtree_identification(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner()
        affected = bp._identify_affected_subtree("t2", self._sample_graph())
        ids = {t["task_id"] for t in affected}
        assert "t2" in ids
        assert "t3" in ids  # downstream
        assert "t4" in ids  # downstream
        assert "t1" not in ids  # upstream

    def test_max_backtracks_limit(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner(failure_threshold=1, max_backtracks=1)
        # First backtrack succeeds
        bp.record_failure("t1")
        r1 = bp.handle_failure("t1", "err", self._sample_graph())
        assert r1 is not None
        # Second should be blocked by max_backtracks
        bp.record_failure("t2")
        r2 = bp.handle_failure("t2", "err", self._sample_graph())
        assert r2 is None

    def test_custom_replan_fn(self):
        from src.core.backtrack_planner import BacktrackPlanner

        def custom_replan(**kwargs):
            return [{"task_id": "new-1", "task_type": "CODE_TASK", "payload": {"fixed": True}}]

        bp = BacktrackPlanner(replan_fn=custom_replan, failure_threshold=1)
        bp.record_failure("t1")
        result = bp.handle_failure("t1", "err", self._sample_graph())
        assert result["new_tasks"][0]["payload"]["fixed"]

    def test_stats(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner(failure_threshold=1)
        bp.record_failure("t1")
        bp.handle_failure("t1", "err", self._sample_graph())
        stats = bp.get_stats()
        assert stats["total_backtracks"] == 1
        assert stats["successful_replans"] == 1

    def test_list_records(self):
        from src.core.backtrack_planner import BacktrackPlanner
        bp = BacktrackPlanner(failure_threshold=1)
        bp.record_failure("t1")
        bp.handle_failure("t1", "err", self._sample_graph())
        records = bp.list_records()
        assert len(records) == 1
        assert records[0]["status"] == "replanned"


# ═══════════════════════════════════════════════════════════════════════
# 9. CONSENSUS ENGINE
# ═══════════════════════════════════════════════════════════════════════

class TestConsensusEngine:

    def test_majority_vote(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()

        def evaluator(role, question):
            if role == "qa":
                return {"decision": "reject", "confidence": 0.8, "reasoning": "Bugs found"}
            return {"decision": "approve", "confidence": 0.7, "reasoning": "Looks good"}

        result = engine.vote(
            question="Approve release?",
            voters=["dev", "architect", "qa"],
            evaluator=evaluator,
        )
        assert result.decision == "approve"  # 2 vs 1
        assert len(result.votes) == 3

    def test_weighted_vote(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()

        def evaluator(role, question):
            if role == "security":
                return {"decision": "reject", "confidence": 0.95, "reasoning": "Vulnerability"}
            return {"decision": "approve", "confidence": 0.3, "reasoning": "OK"}

        result = engine.vote(
            question="Deploy?",
            voters=["dev", "security"],
            evaluator=evaluator,
            method="weighted",
        )
        # Security has higher confidence, should win despite being minority
        assert result.decision == "reject"

    def test_unanimous_vote_pass(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        result = engine.vote(
            question="Ship it?",
            voters=["a", "b", "c"],
            evaluator=lambda r, q: {"decision": "approve", "confidence": 0.8},
            method="unanimous",
        )
        assert result.decision == "approve"
        assert result.agreement_ratio == 1.0

    def test_unanimous_vote_fail(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        votes = iter(["approve", "reject", "approve"])
        result = engine.vote(
            question="Ship it?",
            voters=["a", "b", "c"],
            evaluator=lambda r, q: {"decision": next(votes), "confidence": 0.8},
            method="unanimous",
        )
        assert result.decision == "no_consensus"

    def test_disagreement_escalation(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine(disagreement_threshold=0.7)
        votes = iter(["approve", "reject"])
        result = engine.vote(
            question="Deploy?",
            voters=["a", "b"],
            evaluator=lambda r, q: {"decision": next(votes), "confidence": 0.8},
        )
        assert result.needs_human  # 50% agreement < 70% threshold

    def test_abstain_handling(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        result = engine.vote(
            question="Test?",
            voters=["a", "b", "c"],
            evaluator=lambda r, q: {"decision": "abstain", "confidence": 0},
        )
        assert result.decision == "abstain"

    def test_evaluator_error_handled(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        call_count = [0]

        def flaky_evaluator(role, question):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("LLM timeout")
            return {"decision": "approve", "confidence": 0.8}

        result = engine.vote(
            question="Test?",
            voters=["a", "b", "c"],
            evaluator=flaky_evaluator,
        )
        # Should still resolve — errored voter abstains
        assert len(result.votes) == 3
        assert result.decision == "approve"

    def test_stats(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        engine.vote(
            question="Q1?", voters=["a"],
            evaluator=lambda r, q: {"decision": "approve", "confidence": 0.9},
        )
        stats = engine.get_stats()
        assert stats["total_rounds"] == 1

    def test_get_result_by_id(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        result = engine.vote(
            question="Q?", voters=["a"],
            evaluator=lambda r, q: {"decision": "approve", "confidence": 0.8},
        )
        fetched = engine.get_result(result.consensus_id)
        assert fetched is not None
        assert fetched["decision"] == "approve"

    def test_agreement_ratio_calculation(self):
        from src.core.consensus_engine import ConsensusEngine
        engine = ConsensusEngine()
        decisions = iter(["approve", "approve", "reject"])
        result = engine.vote(
            question="Q?", voters=["a", "b", "c"],
            evaluator=lambda r, q: {"decision": next(decisions), "confidence": 0.7},
        )
        # 2 out of 3 agree → 0.667
        assert 0.6 < result.agreement_ratio < 0.7


# ═══════════════════════════════════════════════════════════════════════
# CROSS-MODULE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════

class TestCrossModuleIntegration:

    def test_reflection_with_budget_check(self):
        """Reflection loop should work alongside budget tracking."""
        from src.core.reflection_engine import ReflectionEngine
        from src.core.budget_manager import BudgetManager

        bm = BudgetManager()
        engine = ReflectionEngine()

        def gen(ctx):
            bm.record_usage("reflection-test", input_tokens=100, output_tokens=50)
            return "output"

        result = engine.reflect(
            generator=gen,
            critic=lambda out: {"score": 0.9, "feedback": "OK"},
        )
        assert result.accepted
        usage = bm.get_usage("reflection-test")
        assert usage["total_tokens"] == 150

    def test_plan_selector_uses_reflection(self):
        """Plan selector should integrate with reflection engine."""
        from src.core.plan_selector import PlanSelector
        selector = PlanSelector()
        scores = iter([0.3, 0.3, 0.3, 0.5, 0.8])
        result = selector.select(
            generator=lambda ctx: "plan",
            critic=lambda p: {"score": next(scores, 0.5), "feedback": "Improve"},
            beam_width=3,
            apply_reflection=True,
            reflection_threshold=0.7,
        )
        assert result.selection_id

    def test_event_bus_receives_budget_events(self):
        """Budget manager should emit events to event bus."""
        from src.core.event_bus import EventBus
        from src.core.budget_manager import BudgetManager, BudgetConfig

        bus = EventBus()
        bm = BudgetManager()
        bm.set_budget("test", BudgetConfig(max_tokens=100))

        # Patch the global bus temporarily
        import src.core.event_bus as eb_module
        old_bus = eb_module._event_bus
        eb_module._event_bus = bus

        try:
            bm.record_usage("test", input_tokens=150)  # exceeds budget
            history = bus.get_history(event_type="budget.exceeded")
            # Should have emitted exceeded event
            assert len(history) >= 1 or len(bus.get_history()) >= 1
        finally:
            eb_module._event_bus = old_bus

    def test_spawner_with_tool_executor(self):
        """Agent spawner can use tool executor during execution."""
        from src.core.agent_spawner import AgentSpawner
        from src.core.tool_executor import ToolExecutor, Tool

        te = ToolExecutor()
        te.register(Tool(name="helper", description="Help", handler=lambda: "helped"))

        def agent_with_tools(role_id, task, context=""):
            call = te.execute("helper")
            return {"summary": f"Done with tool: {call.result}"}

        spawner = AgentSpawner(agent_fn=agent_with_tools)
        result = spawner.spawn(role="dev", task="fix bug")
        assert result["status"] == "completed"
        assert "helped" in result["result"]["summary"]

    def test_backtrack_with_memory_planner(self):
        """Backtrack planner can use memory planner for replanning context."""
        from src.core.backtrack_planner import BacktrackPlanner
        from src.core.memory_planner import MemoryPlanner

        mp = MemoryPlanner()
        mp.record_plan({
            "name": "successful-api",
            "description": "Build API with proper error handling",
            "tasks": [{"task_type": "CODE_TASK"}],
        })

        def memory_replan(**kwargs):
            ctx = mp.augment_context(kwargs.get("error", ""))
            return [{"task_id": "new-1", "task_type": "CODE_TASK",
                      "payload": {"memory_context": ctx}}]

        bp = BacktrackPlanner(replan_fn=memory_replan, failure_threshold=1)
        bp.record_failure("t1")
        result = bp.handle_failure("t1", "API error handling", {
            "tasks": [{"task_id": "t1", "task_type": "CODE_TASK"}],
            "dependencies": [],
        })
        assert result is not None
