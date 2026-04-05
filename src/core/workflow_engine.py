"""
SAGE Workflow Engine — DAG-Based Multi-Agent Workflow Execution
==============================================================

Pure-Python workflow engine that requires no external dependencies.
Defines workflows as directed acyclic graphs (DAGs) where nodes are
agent tasks and edges are dependencies with optional conditions.

Key features:
  - WorkflowGraph: DAG construction with cycle detection
  - Topological sort → wave-based parallel execution
  - Conditional edges (always, on_success, on_failure)
  - Predefined templates (code-review, bug-triage, feature-plan)
  - Serialization to/from dict and Mermaid diagrams

Integrates with SAGE's existing TaskQueue for actual task dispatch,
but can also run standalone with a simple executor for testing.
"""

import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────────────────────────────


@dataclass
class WorkflowNode:
    """A single step in a workflow DAG."""
    id: str
    task_type: str
    payload: dict = field(default_factory=dict)
    agent_role: str = ""
    description: str = ""
    timeout: int = 300  # seconds

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "payload": self.payload,
            "agent_role": self.agent_role,
            "description": self.description,
            "timeout": self.timeout,
        }


@dataclass
class WorkflowEdge:
    """A dependency between two nodes with optional condition."""
    source: str
    target: str
    condition: str = "on_success"  # always | on_success | on_failure

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "condition": self.condition,
        }


# ──────────────────────────────────────────────────────────────────────
# WorkflowGraph
# ──────────────────────────────────────────────────────────────────────


class WorkflowGraph:
    """Directed acyclic graph of workflow nodes and edges."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.nodes: dict[str, WorkflowNode] = {}
        self.edges: list[WorkflowEdge] = []
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._reverse: dict[str, list[str]] = defaultdict(list)
        self._edge_map: dict[tuple[str, str], WorkflowEdge] = {}

    def add_node(self, node: WorkflowNode) -> None:
        """Add a node. Raises ValueError if ID already exists."""
        if node.id in self.nodes:
            raise ValueError(f"Node '{node.id}' already exists in graph")
        self.nodes[node.id] = node

    def add_edge(self, edge: WorkflowEdge) -> None:
        """Add an edge. Raises ValueError if nodes missing or cycle created."""
        if edge.source not in self.nodes:
            raise ValueError(f"Source '{edge.source}' not in graph")
        if edge.target not in self.nodes:
            raise ValueError(f"Target '{edge.target}' not in graph")

        # Check for cycle
        if self._would_create_cycle(edge.source, edge.target):
            raise ValueError(
                f"Edge {edge.source}→{edge.target} would create a cycle"
            )

        self.edges.append(edge)
        self._adjacency[edge.source].append(edge.target)
        self._reverse[edge.target].append(edge.source)
        self._edge_map[(edge.source, edge.target)] = edge

    def _would_create_cycle(self, source: str, target: str) -> bool:
        """Check if adding source→target would create a cycle."""
        # If target can reach source, adding this edge creates a cycle
        visited = set()
        queue = deque([source])
        while queue:
            node = queue.popleft()
            if node == target:
                return False  # target hasn't been reached yet, we're checking reachability
            if node in visited:
                continue
            visited.add(node)
            queue.extend(self._adjacency.get(node, []))

        # Check if target can reach source via existing edges
        visited = set()
        queue = deque([target])
        while queue:
            node = queue.popleft()
            if node == source:
                return True  # cycle!
            if node in visited:
                continue
            visited.add(node)
            queue.extend(self._adjacency.get(node, []))
        return False

    def topological_sort(self) -> list[str]:
        """Kahn's algorithm for topological ordering."""
        in_degree = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        queue = deque(sorted(nid for nid, d in in_degree.items() if d == 0))
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for neighbor in sorted(self._adjacency.get(node, [])):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            raise ValueError("Graph has a cycle (topological sort failed)")

        return result

    def compute_waves(self) -> dict[int, list[str]]:
        """
        Assign each node to an execution wave.
        Wave 0: nodes with no incoming edges.
        Wave N: nodes whose dependencies are all in waves < N.
        """
        if not self.nodes:
            return {}

        in_degree = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            in_degree[edge.target] += 1

        waves: dict[int, list[str]] = {}
        node_wave: dict[str, int] = {}
        queue = deque()

        # Wave 0: all roots
        for nid, d in sorted(in_degree.items()):
            if d == 0:
                node_wave[nid] = 0
                queue.append(nid)

        while queue:
            node = queue.popleft()
            w = node_wave[node]
            waves.setdefault(w, [])
            if node not in waves[w]:
                waves[w].append(node)

            for neighbor in sorted(self._adjacency.get(node, [])):
                in_degree[neighbor] -= 1
                neighbor_wave = max(node_wave.get(neighbor, 0), w + 1)
                node_wave[neighbor] = neighbor_wave
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return waves

    def get_edge(self, source: str, target: str) -> Optional[WorkflowEdge]:
        """Get edge between two nodes."""
        return self._edge_map.get((source, target))

    def get_predecessors(self, node_id: str) -> list[str]:
        """Get all predecessors of a node."""
        return self._reverse.get(node_id, [])

    # ── Serialization ─────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowGraph":
        g = cls(name=data.get("name", ""), description=data.get("description", ""))
        for nd in data.get("nodes", []):
            g.add_node(WorkflowNode(
                id=nd["id"],
                task_type=nd.get("task_type", ""),
                payload=nd.get("payload", {}),
                agent_role=nd.get("agent_role", ""),
                description=nd.get("description", ""),
                timeout=nd.get("timeout", 300),
            ))
        for ed in data.get("edges", []):
            g.add_edge(WorkflowEdge(
                source=ed["source"],
                target=ed["target"],
                condition=ed.get("condition", "on_success"),
            ))
        return g

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram string."""
        lines = ["graph TD"]
        for node in self.nodes.values():
            label = node.description or node.task_type
            lines.append(f"    {node.id}[{label}]")
        for edge in self.edges:
            cond = f"|{edge.condition}|" if edge.condition != "on_success" else ""
            lines.append(f"    {edge.source} -->{cond} {edge.target}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# WorkflowEngine
# ──────────────────────────────────────────────────────────────────────


class WorkflowEngine:
    """Executes workflow graphs wave-by-wave."""

    def __init__(self, executor=None):
        """
        Args:
            executor: Callable(node: WorkflowNode, context: dict) → dict.
                      If None, uses a default no-op executor.
        """
        self._executor = executor or self._default_executor
        self._templates = self._build_templates()

    @staticmethod
    def _default_executor(node: WorkflowNode, context: dict) -> dict:
        """Default executor that simulates task completion."""
        if node.task_type == "FAIL_TASK":
            return {"status": "failed", "error": "Simulated failure"}
        return {"status": "completed", "output": f"Executed {node.id}"}

    def execute(self, graph: WorkflowGraph) -> dict:
        """
        Execute a workflow graph wave-by-wave.

        Returns:
            {
                "workflow_id": str,
                "workflow_name": str,
                "status": "completed" | "partial" | "failed",
                "waves_executed": int,
                "results": {node_id: {status, output/error}, ...},
                "started_at": str,
                "completed_at": str,
            }
        """
        workflow_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        results: dict[str, dict] = {}

        waves = graph.compute_waves()
        if not waves:
            return {
                "workflow_id": workflow_id,
                "workflow_name": graph.name,
                "status": "completed",
                "waves_executed": 0,
                "results": {},
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

        failed_nodes: set[str] = set()
        skipped_nodes: set[str] = set()

        for wave_num in sorted(waves.keys()):
            wave_nodes = waves[wave_num]

            for node_id in wave_nodes:
                node = graph.nodes[node_id]
                predecessors = graph.get_predecessors(node_id)

                # Check if any predecessor failed and this edge depends on success
                should_skip = False
                should_block = False

                for pred_id in predecessors:
                    edge = graph.get_edge(pred_id, node_id)
                    pred_status = results.get(pred_id, {}).get("status", "completed")

                    if edge and edge.condition == "on_failure":
                        if pred_status != "failed":
                            should_skip = True
                    elif edge and edge.condition == "on_success":
                        if pred_status == "failed":
                            should_block = True
                    elif edge and edge.condition == "always":
                        pass  # always execute

                    if pred_id in failed_nodes and (not edge or edge.condition != "on_failure"):
                        should_block = True

                if should_block:
                    results[node_id] = {"status": "blocked", "reason": "predecessor failed"}
                    failed_nodes.add(node_id)
                    continue

                if should_skip:
                    results[node_id] = {"status": "skipped", "reason": "condition not met"}
                    skipped_nodes.add(node_id)
                    continue

                # Execute
                try:
                    context = {
                        "workflow_id": workflow_id,
                        "wave": wave_num,
                        "predecessor_results": {
                            p: results.get(p, {}) for p in predecessors
                        },
                    }
                    result = self._executor(node, context)
                    results[node_id] = result
                    if result.get("status") == "failed":
                        failed_nodes.add(node_id)
                except Exception as exc:
                    results[node_id] = {"status": "failed", "error": str(exc)}
                    failed_nodes.add(node_id)

        # Determine overall status
        if failed_nodes:
            overall = "partial" if any(
                r.get("status") == "completed" for r in results.values()
            ) else "failed"
        else:
            overall = "completed"

        return {
            "workflow_id": workflow_id,
            "workflow_name": graph.name,
            "status": overall,
            "waves_executed": len(waves),
            "results": results,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Templates ─────────────────────────────────────────────────────

    def _build_templates(self) -> dict[str, dict]:
        """Predefined workflow templates."""
        return {
            "code-review": {
                "name": "code-review",
                "description": "Automated code review workflow: analyze → review → report",
                "nodes": [
                    {"id": "analyze", "task_type": "ANALYZE_LOG", "description": "Analyze code changes", "payload": {}},
                    {"id": "review", "task_type": "REVIEW_MR", "description": "Review merge request", "payload": {}},
                    {"id": "report", "task_type": "CODE_TASK", "description": "Generate review report", "payload": {}},
                ],
                "edges": [
                    {"source": "analyze", "target": "review"},
                    {"source": "review", "target": "report"},
                ],
            },
            "bug-triage": {
                "name": "bug-triage",
                "description": "Bug triage workflow: reproduce → diagnose → fix → verify",
                "nodes": [
                    {"id": "reproduce", "task_type": "ANALYZE_LOG", "description": "Reproduce the bug", "payload": {}},
                    {"id": "diagnose", "task_type": "ANALYZE_LOG", "description": "Root cause analysis", "payload": {}},
                    {"id": "fix", "task_type": "CODE_TASK", "description": "Implement fix", "payload": {}},
                    {"id": "verify", "task_type": "REVIEW_MR", "description": "Verify fix with tests", "payload": {}},
                ],
                "edges": [
                    {"source": "reproduce", "target": "diagnose"},
                    {"source": "diagnose", "target": "fix"},
                    {"source": "fix", "target": "verify"},
                ],
            },
            "feature-plan": {
                "name": "feature-plan",
                "description": "Feature planning: brainstorm → plan → design → implement → review",
                "nodes": [
                    {"id": "brainstorm", "task_type": "PLAN_TASK", "description": "Brainstorm approaches", "payload": {}},
                    {"id": "plan", "task_type": "PLAN_TASK", "description": "Create implementation plan", "payload": {}},
                    {"id": "design", "task_type": "CODE_TASK", "description": "Design architecture", "payload": {}},
                    {"id": "implement", "task_type": "CODE_TASK", "description": "Implement feature", "payload": {}},
                    {"id": "review", "task_type": "REVIEW_MR", "description": "Code review", "payload": {}},
                ],
                "edges": [
                    {"source": "brainstorm", "target": "plan"},
                    {"source": "plan", "target": "design"},
                    {"source": "design", "target": "implement"},
                    {"source": "implement", "target": "review"},
                ],
            },
        }

    def list_templates(self) -> list[dict]:
        """List available workflow templates."""
        return [
            {"name": t["name"], "description": t["description"],
             "node_count": len(t["nodes"])}
            for t in self._templates.values()
        ]

    def from_template(self, template_name: str, **overrides) -> WorkflowGraph:
        """Instantiate a workflow graph from a template."""
        tpl = self._templates.get(template_name)
        if not tpl:
            raise ValueError(f"Unknown template: {template_name}")
        data = {**tpl, **overrides}
        return WorkflowGraph.from_dict(data)
