"""
Workflow Engine — Unit Tests
============================
Tests DAG-based workflow execution: graph validation, topological sort,
wave execution, conditional branching, and templates.
"""

import pytest


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def engine():
    from src.core.workflow_engine import WorkflowEngine
    return WorkflowEngine()


@pytest.fixture
def simple_graph():
    """A → B → C linear workflow."""
    from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
    graph = WorkflowGraph(name="simple", description="Linear A→B→C")
    graph.add_node(WorkflowNode(id="A", task_type="ANALYZE_LOG", payload={"log": "test"}))
    graph.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={"task": "fix"}))
    graph.add_node(WorkflowNode(id="C", task_type="REVIEW_MR", payload={"mr": "1"}))
    graph.add_edge(WorkflowEdge(source="A", target="B"))
    graph.add_edge(WorkflowEdge(source="B", target="C"))
    return graph


@pytest.fixture
def diamond_graph():
    """Diamond: A → B, A → C, B → D, C → D."""
    from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
    graph = WorkflowGraph(name="diamond", description="Diamond DAG")
    graph.add_node(WorkflowNode(id="A", task_type="PLAN_TASK", payload={}))
    graph.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
    graph.add_node(WorkflowNode(id="C", task_type="CODE_TASK", payload={}))
    graph.add_node(WorkflowNode(id="D", task_type="REVIEW_MR", payload={}))
    graph.add_edge(WorkflowEdge(source="A", target="B"))
    graph.add_edge(WorkflowEdge(source="A", target="C"))
    graph.add_edge(WorkflowEdge(source="B", target="D"))
    graph.add_edge(WorkflowEdge(source="C", target="D"))
    return graph


# ═══════════════════════════════════════════════════════════════════════
# GRAPH CONSTRUCTION & VALIDATION
# ═══════════════════════════════════════════════════════════════════════

class TestGraphConstruction:

    def test_add_node(self):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode
        g = WorkflowGraph(name="test")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        assert "A" in g.nodes

    def test_add_edge(self):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="test")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="A", target="B"))
        assert len(g.edges) == 1

    def test_add_edge_to_missing_node_raises(self):
        from src.core.workflow_engine import WorkflowGraph, WorkflowEdge
        g = WorkflowGraph(name="test")
        with pytest.raises(ValueError, match="not in graph"):
            g.add_edge(WorkflowEdge(source="X", target="Y"))

    def test_duplicate_node_raises(self):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode
        g = WorkflowGraph(name="test")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        with pytest.raises(ValueError, match="already exists"):
            g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))

    def test_cycle_detection(self):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="test")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="A", target="B"))
        with pytest.raises(ValueError, match="cycle"):
            g.add_edge(WorkflowEdge(source="B", target="A"))


# ═══════════════════════════════════════════════════════════════════════
# TOPOLOGICAL SORT & WAVES
# ═══════════════════════════════════════════════════════════════════════

class TestTopologicalSort:

    def test_linear_sort(self, simple_graph):
        order = simple_graph.topological_sort()
        assert order == ["A", "B", "C"]

    def test_diamond_sort(self, diamond_graph):
        order = diamond_graph.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_wave_assignment_linear(self, simple_graph):
        waves = simple_graph.compute_waves()
        assert waves == {0: ["A"], 1: ["B"], 2: ["C"]}

    def test_wave_assignment_diamond(self, diamond_graph):
        waves = diamond_graph.compute_waves()
        assert waves[0] == ["A"]
        assert set(waves[1]) == {"B", "C"}
        assert waves[2] == ["D"]

    def test_single_node_graph(self):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode
        g = WorkflowGraph(name="single")
        g.add_node(WorkflowNode(id="X", task_type="CODE_TASK", payload={}))
        waves = g.compute_waves()
        assert waves == {0: ["X"]}


# ═══════════════════════════════════════════════════════════════════════
# EXECUTION
# ═══════════════════════════════════════════════════════════════════════

class TestExecution:

    def test_execute_linear(self, engine, simple_graph):
        result = engine.execute(simple_graph)
        assert result["status"] == "completed"
        assert len(result["results"]) == 3
        assert all(r["status"] == "completed" for r in result["results"].values())

    def test_execute_diamond(self, engine, diamond_graph):
        result = engine.execute(diamond_graph)
        assert result["status"] == "completed"
        assert len(result["results"]) == 4

    def test_execute_records_wave_order(self, engine, diamond_graph):
        result = engine.execute(diamond_graph)
        assert result["waves_executed"] == 3

    def test_execute_with_failing_node(self, engine):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="fail_test")
        g.add_node(WorkflowNode(id="good", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="bad", task_type="FAIL_TASK", payload={}))
        g.add_node(WorkflowNode(id="after_bad", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="good", target="bad"))
        g.add_edge(WorkflowEdge(source="bad", target="after_bad"))
        result = engine.execute(g)
        # after_bad should be blocked because bad failed
        assert result["results"]["bad"]["status"] == "failed"
        assert result["results"]["after_bad"]["status"] == "blocked"

    def test_execute_empty_graph(self, engine):
        from src.core.workflow_engine import WorkflowGraph
        g = WorkflowGraph(name="empty")
        result = engine.execute(g)
        assert result["status"] == "completed"
        assert result["waves_executed"] == 0


# ═══════════════════════════════════════════════════════════════════════
# CONDITIONAL EDGES
# ═══════════════════════════════════════════════════════════════════════

class TestConditionalEdges:

    def test_condition_true_follows_edge(self, engine):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="cond_test")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="A", target="B", condition="always"))
        result = engine.execute(g)
        assert result["results"]["B"]["status"] == "completed"

    def test_condition_false_skips_edge(self, engine):
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="cond_skip")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="A", target="B", condition="on_failure"))
        result = engine.execute(g)
        # B should be skipped because A succeeded (condition is on_failure)
        assert result["results"]["B"]["status"] == "skipped"


# ═══════════════════════════════════════════════════════════════════════
# TEMPLATES
# ═══════════════════════════════════════════════════════════════════════

class TestTemplates:

    def test_list_templates(self, engine):
        templates = engine.list_templates()
        assert len(templates) >= 2
        names = [t["name"] for t in templates]
        assert "code-review" in names
        assert "bug-triage" in names

    def test_instantiate_template(self, engine):
        graph = engine.from_template("code-review")
        assert isinstance(graph, type(graph))  # WorkflowGraph
        assert len(graph.nodes) >= 2

    def test_instantiate_unknown_template_raises(self, engine):
        with pytest.raises(ValueError, match="Unknown template"):
            engine.from_template("nonexistent-template")


# ═══════════════════════════════════════════════════════════════════════
# SERIALIZATION
# ═══════════════════════════════════════════════════════════════════════

class TestSerialization:

    def test_to_dict(self, simple_graph):
        d = simple_graph.to_dict()
        assert d["name"] == "simple"
        assert len(d["nodes"]) == 3
        assert len(d["edges"]) == 2

    def test_from_dict(self):
        from src.core.workflow_engine import WorkflowGraph
        d = {
            "name": "from_dict",
            "description": "test",
            "nodes": [
                {"id": "X", "task_type": "CODE_TASK", "payload": {}},
                {"id": "Y", "task_type": "CODE_TASK", "payload": {}},
            ],
            "edges": [
                {"source": "X", "target": "Y"},
            ],
        }
        g = WorkflowGraph.from_dict(d)
        assert len(g.nodes) == 2
        assert len(g.edges) == 1

    def test_to_mermaid(self, diamond_graph):
        mermaid = diamond_graph.to_mermaid()
        assert "graph TD" in mermaid
        assert "A" in mermaid
        assert "D" in mermaid

    def test_roundtrip_serialization(self, diamond_graph):
        """to_dict → from_dict produces equivalent graph."""
        from src.core.workflow_engine import WorkflowGraph
        d = diamond_graph.to_dict()
        restored = WorkflowGraph.from_dict(d)
        assert set(restored.nodes.keys()) == set(diamond_graph.nodes.keys())
        assert len(restored.edges) == len(diamond_graph.edges)
        assert restored.to_dict() == d


# ═══════════════════════════════════════════════════════════════════════
# CORNER CASES & ERROR PATHS
# ═══════════════════════════════════════════════════════════════════════

class TestCornerCases:
    """Edge cases for graph construction and execution."""

    def test_executor_exception_is_caught(self, engine):
        """Executor that raises exception → node marked failed."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge, WorkflowEngine

        def exploding_executor(node, context):
            raise RuntimeError("Boom!")

        eng = WorkflowEngine(executor=exploding_executor)
        g = WorkflowGraph(name="explode")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        result = eng.execute(g)
        assert result["results"]["A"]["status"] == "failed"
        assert "Boom!" in result["results"]["A"]["error"]

    def test_on_failure_edge_fires_when_predecessor_fails(self, engine):
        """on_failure edge should execute target when predecessor fails."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="failure_handler")
        g.add_node(WorkflowNode(id="risky", task_type="FAIL_TASK", payload={}))
        g.add_node(WorkflowNode(id="handler", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="risky", target="handler", condition="on_failure"))
        result = engine.execute(g)
        assert result["results"]["risky"]["status"] == "failed"
        assert result["results"]["handler"]["status"] == "completed"

    def test_always_edge_runs_despite_failure(self, engine):
        """'always' edge executes target even when predecessor fails."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="always_test")
        g.add_node(WorkflowNode(id="fail", task_type="FAIL_TASK", payload={}))
        g.add_node(WorkflowNode(id="cleanup", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="fail", target="cleanup", condition="always"))
        result = engine.execute(g)
        assert result["results"]["fail"]["status"] == "failed"
        assert result["results"]["cleanup"]["status"] == "completed"

    def test_wide_graph_parallel_wave(self, engine):
        """Many independent nodes all land in wave 0."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode
        g = WorkflowGraph(name="wide")
        for i in range(10):
            g.add_node(WorkflowNode(id=f"N{i}", task_type="CODE_TASK", payload={}))
        result = engine.execute(g)
        assert result["waves_executed"] == 1
        assert all(r["status"] == "completed" for r in result["results"].values())
        assert len(result["results"]) == 10

    def test_custom_executor_receives_context(self):
        """Custom executor receives workflow_id and predecessor_results in context."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge, WorkflowEngine
        contexts = {}

        def tracking_executor(node, context):
            contexts[node.id] = context
            return {"status": "completed", "output": f"done-{node.id}"}

        eng = WorkflowEngine(executor=tracking_executor)
        g = WorkflowGraph(name="ctx_test")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="A", target="B"))
        eng.execute(g)

        assert "workflow_id" in contexts["A"]
        assert contexts["A"]["wave"] == 0
        assert contexts["B"]["wave"] == 1
        assert "A" in contexts["B"]["predecessor_results"]

    def test_get_predecessors(self, diamond_graph):
        """get_predecessors returns correct parent nodes."""
        preds = diamond_graph.get_predecessors("D")
        assert set(preds) == {"B", "C"}
        assert diamond_graph.get_predecessors("A") == []

    def test_get_edge(self, diamond_graph):
        """get_edge returns edge or None."""
        edge = diamond_graph.get_edge("A", "B")
        assert edge is not None
        assert edge.source == "A"
        assert diamond_graph.get_edge("A", "D") is None

    def test_self_loop_detection(self):
        """Adding a self-loop edge raises ValueError."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="self_loop")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        with pytest.raises(ValueError):
            g.add_edge(WorkflowEdge(source="A", target="A"))

    def test_three_node_cycle_detection(self):
        """Detect cycle in A→B→C→A."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="triangle")
        g.add_node(WorkflowNode(id="A", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="B", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="C", task_type="CODE_TASK", payload={}))
        g.add_edge(WorkflowEdge(source="A", target="B"))
        g.add_edge(WorkflowEdge(source="B", target="C"))
        with pytest.raises(ValueError, match="cycle"):
            g.add_edge(WorkflowEdge(source="C", target="A"))

    def test_partial_status_when_some_succeed_some_fail(self, engine):
        """Overall status is 'partial' when some nodes succeed and some fail."""
        from src.core.workflow_engine import WorkflowGraph, WorkflowNode, WorkflowEdge
        g = WorkflowGraph(name="partial")
        g.add_node(WorkflowNode(id="ok", task_type="CODE_TASK", payload={}))
        g.add_node(WorkflowNode(id="bad", task_type="FAIL_TASK", payload={}))
        result = engine.execute(g)
        assert result["status"] == "partial"

    def test_template_code_review_executes(self, engine):
        """Code-review template can be instantiated and executed."""
        graph = engine.from_template("code-review")
        result = engine.execute(graph)
        assert result["status"] == "completed"
        assert len(result["results"]) == 3

    def test_template_feature_plan_executes(self, engine):
        """Feature-plan template can be instantiated and executed."""
        graph = engine.from_template("feature-plan")
        result = engine.execute(graph)
        assert result["status"] == "completed"
        assert len(result["results"]) == 5

    def test_node_timeout_default(self):
        """WorkflowNode has default timeout of 300."""
        from src.core.workflow_engine import WorkflowNode
        node = WorkflowNode(id="A", task_type="CODE_TASK")
        assert node.timeout == 300

    def test_from_dict_with_missing_optional_fields(self):
        """from_dict handles missing optional fields gracefully."""
        from src.core.workflow_engine import WorkflowGraph
        d = {
            "nodes": [{"id": "X", "task_type": "CODE_TASK"}],
            "edges": [],
        }
        g = WorkflowGraph.from_dict(d)
        assert "X" in g.nodes
        assert g.nodes["X"].payload == {}
        assert g.nodes["X"].timeout == 300
