# Solution Organizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add org-level solution grouping to SAGE — hierarchical inheritance of prompts/tasks/knowledge, named knowledge channels between teams, and cross-team task routing with explicit permissions.

**Architecture:** A new `OrgLoader` class reads `org.yaml` from `SAGE_SOLUTIONS_DIR` root and provides merged configs. `VectorMemory` gains a factory + org-aware multi-store `query()` that walks the parent chain. `ProjectConfig` is wired to serve merged prompts/tasks via `OrgLoader` when an org is active. Cross-team task dispatch goes through a new `POST /tasks/submit` endpoint. A React org graph page (react-flow v12 / `@xyflow/react`) lets admins configure the org visually.

**Tech Stack:** Python 3.11, FastAPI, ChromaDB, React 18 + TypeScript, @xyflow/react, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-03-19-solution-organizations-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/core/org_loader.py` | **Create** | Load `org.yaml`, cycle detection, merged prompts/tasks, channel resolution |
| `src/core/project_loader.py` | **Modify** | Wire `OrgLoader` into `get_analyst_prompts`, `get_task_types`, `get_task_descriptions` |
| `src/memory/vector_store.py` | **Modify** | `get_vector_memory(solution_name)` factory + org-aware `query_org()` |
| `src/core/queue_manager.py` | **Modify** | `get_task_queue(solution_name)` factory |
| `src/interface/api.py` | **Modify** | `POST /tasks/submit`, 8× `/org/*` endpoints, extend `POST /knowledge/add` |
| `src/core/onboarding.py` | **Modify** | `parent_solution` + `org_name`, `suggested_routes` in response |
| `web/src/pages/OrgGraph.tsx` | **Create** | Visual org graph (react-flow, blue knowledge edges + orange routing edges) |
| `web/src/App.tsx` | **Modify** | Add `/org` route |
| `web/src/components/layout/Sidebar.tsx` | **Modify** | Add "Organization" nav entry |
| `web/src/registry/modules.ts` | **Modify** | Add `org` module entry |
| `web/src/api/client.ts` | **Modify** | Typed fetch functions for all new endpoints |
| `tests/test_org_loader.py` | **Create** | OrgLoader unit tests |
| `tests/test_cross_team_routing.py` | **Create** | Cross-team task routing integration tests |

---

## Task 1: OrgLoader — core (load, validate, merge)

**Files:**
- Create: `src/core/org_loader.py`
- Create: `tests/test_org_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_org_loader.py
import os
import pytest
import yaml

from src.core.org_loader import OrgLoader, OrgLoaderError


@pytest.fixture
def solutions_dir(tmp_path):
    (tmp_path / "company_base").mkdir()
    (tmp_path / "company_base" / "project.yaml").write_text("name: company_base\n")
    (tmp_path / "company_base" / "prompts.yaml").write_text(
        "analyst_system: 'You are company analyst'\nshared_key: 'from_company'\n"
    )
    (tmp_path / "company_base" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'Analyze'\n"
    )

    (tmp_path / "product_level").mkdir()
    (tmp_path / "product_level" / "project.yaml").write_text(
        "name: product_level\nparent: company_base\n"
    )
    (tmp_path / "product_level" / "prompts.yaml").write_text(
        "analyst_system: 'You are product analyst'\n"
    )
    (tmp_path / "product_level" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\n  - REVIEW_MR\n"
        "task_descriptions:\n  ANALYZE_LOG: 'Analyze'\n  REVIEW_MR: 'Review'\n"
    )

    (tmp_path / "team_fw").mkdir()
    (tmp_path / "team_fw" / "project.yaml").write_text(
        "name: team_fw\nparent: product_level\n"
        "cross_team_routes:\n  - target: team_hw\n"
    )
    (tmp_path / "team_fw" / "prompts.yaml").write_text(
        "analyst_system: 'You are firmware analyst'\n"
    )
    (tmp_path / "team_fw" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'FW analyze'\n"
    )

    (tmp_path / "team_hw").mkdir()
    (tmp_path / "team_hw" / "project.yaml").write_text(
        "name: team_hw\nparent: product_level\n"
    )
    (tmp_path / "team_hw" / "prompts.yaml").write_text("analyst_system: 'HW analyst'\n")
    (tmp_path / "team_hw" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'HW analyze'\n"
    )

    org = {
        "org": {
            "name": "test_org",
            "root_solution": "company_base",
            "knowledge_channels": {
                "hw-fw": {"producers": ["team_hw"], "consumers": ["team_fw"]}
            },
        }
    }
    (tmp_path / "org.yaml").write_text(yaml.dump(org))
    return tmp_path


def test_loads_org_yaml(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    assert loader.org_name == "test_org"
    assert loader.root_solution == "company_base"


def test_no_org_yaml_returns_none():
    loader = OrgLoader("/tmp/no_org_here_xyz")
    assert loader.org_name is None


def test_get_parent_chain(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    chain = loader.get_parent_chain("team_fw")
    assert chain == ["team_fw", "product_level", "company_base"]


def test_cycle_detection_raises(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "project.yaml").write_text("name: a\nparent: b\n")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "project.yaml").write_text("name: b\nparent: a\n")
    org = {"org": {"name": "x", "root_solution": "a", "knowledge_channels": {}}}
    (tmp_path / "org.yaml").write_text(yaml.dump(org))
    with pytest.raises(OrgLoaderError, match="cycle"):
        OrgLoader(str(tmp_path))


def test_merged_prompts_child_wins(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    merged = loader.get_merged_prompts("team_fw")
    assert merged["analyst_system"] == "You are firmware analyst"
    assert merged["shared_key"] == "from_company"


def test_merged_tasks_child_wins(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    merged = loader.get_merged_tasks("team_fw")
    assert "FW analyze" in merged.get("task_descriptions", {}).get("ANALYZE_LOG", "")
    assert "REVIEW_MR" in merged.get("task_types", [])


def test_channel_normalization(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    names = loader.get_channel_collection_names("team_fw")
    assert "channel_hw_fw" in names


def test_cross_team_routes_allowed(solutions_dir):
    loader = OrgLoader(str(solutions_dir))
    assert loader.is_route_allowed("team_fw", "team_hw") is True
    assert loader.is_route_allowed("team_fw", "company_base") is False


def test_no_org_is_route_allowed_returns_false():
    loader = OrgLoader("/tmp/no_org_here_xyz")
    assert loader.is_route_allowed("any", "other") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_loader.py -v 2>&1 | head -30
```
Expected: `ImportError` — `OrgLoader` does not exist yet.

- [ ] **Step 3: Implement OrgLoader**

Create `src/core/org_loader.py`:

```python
"""
SAGE Framework — OrgLoader
==========================
Loads org.yaml from SAGE_SOLUTIONS_DIR root and provides:
  - Parent chain resolution
  - Cycle detection (OrgLoaderError on startup)
  - Merged prompts.yaml and tasks.yaml across the parent chain (child wins)
  - Knowledge channel collection name resolution
  - Cross-team routing permission checks

Gracefully degrades: when org.yaml is absent, all methods return empty/False
and existing single-solution behaviour is completely unchanged.
"""
import logging
import os
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


class OrgLoaderError(Exception):
    pass


class OrgLoader:

    def __init__(self, solutions_dir: str):
        self._solutions_dir = solutions_dir
        self._org: dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def org_name(self) -> Optional[str]:
        return self._org.get("org", {}).get("name")

    @property
    def root_solution(self) -> Optional[str]:
        return self._org.get("org", {}).get("root_solution")

    def get_parent_chain(self, solution_name: str) -> list:
        """Return [solution_name, parent, grandparent, ...] up to root."""
        chain = []
        current = solution_name
        visited = set()
        while current:
            if current in visited:
                raise OrgLoaderError(f"Cycle at '{current}' in parent chain")
            visited.add(current)
            chain.append(current)
            project = self._load_yaml(os.path.join(self._solutions_dir, current, "project.yaml"))
            current = project.get("parent")
        return chain

    def get_merged_prompts(self, solution_name: str) -> dict:
        """Merge prompts.yaml root→child. Child key wins on conflict."""
        merged: dict = {}
        for name in reversed(self.get_parent_chain(solution_name)):
            data = self._load_yaml(os.path.join(self._solutions_dir, name, "prompts.yaml"))
            merged.update(data)
        return merged

    def get_merged_tasks(self, solution_name: str) -> dict:
        """
        Merge tasks.yaml root→child.
        task_types: union; descriptions/hooks/policies: child entry replaces parent entirely.
        """
        merged_types: list = []
        merged_desc: dict = {}
        merged_payloads: dict = {}
        merged_hooks: dict = {}
        merged_policies: dict = {}
        for name in reversed(self.get_parent_chain(solution_name)):
            data = self._load_yaml(os.path.join(self._solutions_dir, name, "tasks.yaml"))
            for t in data.get("task_types", []):
                if t not in merged_types:
                    merged_types.append(t)
            merged_desc.update(data.get("task_descriptions", {}))
            merged_payloads.update(data.get("task_payloads", {}))
            merged_hooks.update(data.get("task_hooks", {}))
            merged_policies.update(data.get("task_sandbox_policies", {}))
        result: dict = {"task_types": merged_types}
        if merged_desc:
            result["task_descriptions"] = merged_desc
        if merged_payloads:
            result["task_payloads"] = merged_payloads
        if merged_hooks:
            result["task_hooks"] = merged_hooks
        if merged_policies:
            result["task_sandbox_policies"] = merged_policies
        return result

    def get_channel_collection_names(self, solution_name: str) -> list:
        """Return list of chroma collection names this solution consumes."""
        channels = self._org.get("org", {}).get("knowledge_channels", {})
        return [
            self._normalize_channel(name)
            for name, conf in channels.items()
            if solution_name in conf.get("consumers", [])
        ]

    def get_channel_db_path(self) -> Optional[str]:
        """Path to org root solution's .sage/chroma_db/ for channel collections."""
        root = self.root_solution
        if not root:
            return None
        path = os.path.join(self._solutions_dir, root, ".sage", "chroma_db")
        os.makedirs(path, exist_ok=True)
        return path

    def get_producer_channel_name(self, solution_name: str, channel_label: str) -> Optional[str]:
        """Return normalized collection name if solution is a producer for channel_label."""
        channels = self._org.get("org", {}).get("knowledge_channels", {})
        if channel_label not in channels:
            return None
        if solution_name in channels[channel_label].get("producers", []):
            return self._normalize_channel(channel_label)
        return None

    def is_route_allowed(self, source_solution: str, target_solution: str) -> bool:
        if not self.org_name:
            return False
        project = self._load_yaml(
            os.path.join(self._solutions_dir, source_solution, "project.yaml")
        )
        return any(r.get("target") == target_solution for r in project.get("cross_team_routes", []))

    def get_all_routes(self) -> list:
        """Return all cross_team_routes across all solutions as [{source, target}]."""
        result = []
        if not os.path.isdir(self._solutions_dir):
            return result
        for name in os.listdir(self._solutions_dir):
            sol_dir = os.path.join(self._solutions_dir, name)
            if not os.path.isdir(sol_dir):
                continue
            proj = self._load_yaml(os.path.join(sol_dir, "project.yaml"))
            for r in proj.get("cross_team_routes", []):
                result.append({"source": name, "target": r.get("target", "")})
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self):
        org_path = os.path.join(self._solutions_dir, "org.yaml")
        if not os.path.exists(org_path):
            logger.debug("No org.yaml at %s — org features disabled", org_path)
            return
        self._org = self._load_yaml(org_path)
        self._detect_cycles()
        logger.info("OrgLoader: loaded org '%s'", self.org_name)

    def _detect_cycles(self):
        if not os.path.isdir(self._solutions_dir):
            return
        for name in os.listdir(self._solutions_dir):
            if not os.path.isdir(os.path.join(self._solutions_dir, name)):
                continue
            visited: set = set()
            current: Optional[str] = name
            while current:
                if current in visited:
                    raise OrgLoaderError(
                        f"Circular inheritance cycle detected: '{current}' appears twice "
                        f"in the parent chain starting from '{name}'"
                    )
                visited.add(current)
                project = self._load_yaml(
                    os.path.join(self._solutions_dir, current, "project.yaml")
                )
                current = project.get("parent")

    @staticmethod
    def _normalize_channel(name: str) -> str:
        return "channel_" + name.lower().replace("-", "_")

    @staticmethod
    def _load_yaml(path: str) -> dict:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        return {}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_SOLUTIONS_DIR = os.environ.get(
    "SAGE_SOLUTIONS_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "solutions",
    ),
)

org_loader = OrgLoader(_SOLUTIONS_DIR)


def reload_org_loader() -> "OrgLoader":
    global org_loader
    org_loader = OrgLoader(_SOLUTIONS_DIR)
    return org_loader
```

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_loader.py -v
```
Expected: all 9 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd C:/sandbox/SAGE && git add src/core/org_loader.py tests/test_org_loader.py
git commit -m "feat(org): OrgLoader — org.yaml loading, cycle detection, merge logic, channel resolution"
```

---

## Task 2: Wire OrgLoader into project_loader.py

**Files:**
- Modify: `src/core/project_loader.py`

This is the wiring that makes inheritance visible to agents at runtime. Without it, OrgLoader exists but agents always see only their own flat YAML.

- [ ] **Step 1: Write failing test**

```python
# tests/test_org_project_loader.py
import os
import pytest
import yaml
from unittest.mock import patch, MagicMock


def test_get_task_types_includes_parent_types(tmp_path, monkeypatch):
    """When a parent solution defines REVIEW_MR, child should see it via get_task_types()."""
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))

    (tmp_path / "parent_sol").mkdir()
    (tmp_path / "parent_sol" / "project.yaml").write_text("name: parent_sol\n")
    (tmp_path / "parent_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\n  - REVIEW_MR\n"
        "task_descriptions:\n  ANALYZE_LOG: 'A'\n  REVIEW_MR: 'R'\n"
    )
    (tmp_path / "parent_sol" / "prompts.yaml").write_text("")

    (tmp_path / "child_sol").mkdir()
    (tmp_path / "child_sol" / "project.yaml").write_text(
        "name: child_sol\nparent: parent_sol\n"
    )
    (tmp_path / "child_sol" / "tasks.yaml").write_text(
        "task_types:\n  - ANALYZE_LOG\ntask_descriptions:\n  ANALYZE_LOG: 'Child A'\n"
    )
    (tmp_path / "child_sol" / "prompts.yaml").write_text("")

    org = {"org": {"name": "x", "root_solution": "parent_sol", "knowledge_channels": {}}}
    (tmp_path / "org.yaml").write_text(yaml.dump(org))

    from src.core.org_loader import OrgLoader
    mock_loader = OrgLoader(str(tmp_path))

    with patch("src.core.project_loader.org_loader", mock_loader):
        from src.core.project_loader import ProjectConfig
        pc = ProjectConfig("child_sol")
        types = pc.get_task_types()

    assert "REVIEW_MR" in types
    assert "ANALYZE_LOG" in types
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_project_loader.py -v 2>&1 | head -20
```

- [ ] **Step 3: Wire OrgLoader into project_loader.py**

In `src/core/project_loader.py`, add import at top of file:

```python
# Lazy import to avoid circular dependency; resolved at call time
def _get_org_loader():
    from src.core.org_loader import org_loader
    return org_loader
```

Modify `get_task_types()` in `ProjectConfig`:

```python
def get_task_types(self) -> list:
    # Check if org inheritance is active
    ol = _get_org_loader()
    if ol.org_name and self._name:
        merged = ol.get_merged_tasks(self._name)
        return merged.get("task_types", self._tasks.get("task_types", []))
    return self._tasks.get("task_types", [])
```

Modify `get_task_descriptions()` (or equivalent method that returns task_descriptions):

```python
def get_task_descriptions(self) -> dict:
    ol = _get_org_loader()
    if ol.org_name and self._name:
        merged = ol.get_merged_tasks(self._name)
        return merged.get("task_descriptions", self._tasks.get("task_descriptions", {}))
    return self._tasks.get("task_descriptions", {})
```

Note: Read `project_loader.py` first to find the exact method names for task type and description lookups. Apply the same pattern to any method that reads `self._tasks` for task types or descriptions.

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_project_loader.py -v
```

- [ ] **Step 5: Run full existing suite to verify no regressions**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/ -v --tb=short -q 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
cd C:/sandbox/SAGE && git add src/core/project_loader.py tests/test_org_project_loader.py
git commit -m "feat(org): wire OrgLoader into ProjectConfig — agents see merged task types from parent chain"
```

---

## Task 3: VectorMemory factory + org-aware multi-store query

**Files:**
- Modify: `src/memory/vector_store.py`
- Create: `tests/test_org_vector.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_org_vector.py
import pytest
from unittest.mock import patch, MagicMock


def test_get_vector_memory_factory_returns_instance():
    from src.memory.vector_store import get_vector_memory, VectorMemory
    vm = get_vector_memory("some_solution")
    assert isinstance(vm, VectorMemory)


def test_factory_instances_for_different_solutions_differ():
    from src.memory.vector_store import get_vector_memory
    vm_a = get_vector_memory("sol_a")
    vm_b = get_vector_memory("sol_b")
    # Their resolved db paths should differ
    assert vm_a._get_vector_db_path() != vm_b._get_vector_db_path()


def test_org_query_searches_parent_chain(tmp_path, monkeypatch):
    """org_query() should call vector_store.search() for each solution in the chain."""
    from src.memory.vector_store import org_aware_query

    mock_results_parent = [{"content": "parent knowledge", "distance": 0.2}]
    mock_results_child  = [{"content": "child knowledge",  "distance": 0.1}]

    call_log = []

    def mock_search(self, query, n=5):
        call_log.append(self._explicit_solution)
        if self._explicit_solution == "parent":
            return mock_results_parent
        return mock_results_child

    with patch("src.memory.vector_store.VectorMemory.search", mock_search):
        from src.core.org_loader import OrgLoader
        mock_loader = MagicMock(spec=OrgLoader)
        mock_loader.org_name = "test_org"
        mock_loader.get_parent_chain.return_value = ["child", "parent"]
        mock_loader.get_channel_collection_names.return_value = []

        results = org_aware_query("test query", "child", mock_loader, n_results=5)

    assert len(call_log) == 2  # searched child and parent
    # Results sorted ascending by distance — lowest distance (most relevant) first
    assert results[0]["distance"] <= results[1]["distance"]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_vector.py -v 2>&1 | head -20
```

- [ ] **Step 3: Add factory and org_aware_query to vector_store.py**

At module level in `src/memory/vector_store.py`, add a helper (after imports):

```python
def _get_sage_solutions_dir() -> str:
    return os.environ.get(
        "SAGE_SOLUTIONS_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "solutions"),
    )
```

Add to `VectorMemory.__init__` (before `_initialize_db()` is called):

```python
self._explicit_solution: Optional[str] = None  # set by get_vector_memory factory
```

Add a new constructor parameter and guard — modify `__init__` signature to:

```python
def __init__(self, explicit_solution: str = None):
    self._explicit_solution = explicit_solution
    # ... rest of existing __init__ ...
    self._initialize_db()  # called after _explicit_solution is set
```

Modify `_get_vector_db_path` — insert at top of method (before existing logic):

```python
def _get_vector_db_path(self) -> str:
    # Org-aware override: explicit solution name provided by factory takes priority
    if self._explicit_solution:
        solutions_dir = _get_sage_solutions_dir()
        sage_dir = os.path.join(solutions_dir, self._explicit_solution, ".sage")
        os.makedirs(sage_dir, exist_ok=True)
        return os.path.join(sage_dir, "chroma_db")
    # ... existing logic unchanged below ...
```

Add factory function after the class:

```python
def get_vector_memory(solution_name: str) -> "VectorMemory":
    """Return a VectorMemory scoped to a specific solution's .sage/chroma_db/."""
    return VectorMemory(explicit_solution=solution_name)
```

Add `org_aware_query` function after the factory:

```python
def org_aware_query(
    query_text: str,
    solution_name: str,
    loader,          # OrgLoader instance
    n_results: int = 5,
) -> list:
    """
    Query the parent chain + subscribed channels and return merged results.
    Results are sorted ascending by distance (lower = more relevant).
    Falls back to empty list gracefully on any error.
    """
    all_results: list = []
    try:
        chain = loader.get_parent_chain(solution_name)
        for sol in chain:
            vm = get_vector_memory(sol)
            try:
                results = vm.search(query_text, n=n_results)
                all_results.extend(results)
            except Exception as exc:
                logger.debug("org_aware_query: search failed for %s: %s", sol, exc)

        # TODO (future): also query channel collections from loader.get_channel_collection_names()

        # Deduplicate by content, then sort ascending by distance
        seen: set = set()
        deduped: list = []
        for r in all_results:
            content = r.get("content", r.get("page_content", ""))
            if content not in seen:
                seen.add(content)
                deduped.append(r)

        deduped.sort(key=lambda r: r.get("distance", 0.0))
        return deduped[:n_results]
    except Exception as exc:
        logger.warning("org_aware_query failed (non-fatal): %s", exc)
        return []
```

Note: Check the actual return shape of `VectorMemory.search()` in the existing code to confirm the key names (`content`, `distance`, etc.) before finalising.

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_vector.py -v
```

- [ ] **Step 5: Run full suite for regressions**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/ -q --tb=short 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
cd C:/sandbox/SAGE && git add src/memory/vector_store.py tests/test_org_vector.py
git commit -m "feat(org): VectorMemory factory + org_aware_query — multi-store RAG across parent chain"
```

---

## Task 4: Knowledge channel write — extend POST /knowledge/add

**Files:**
- Modify: `src/interface/api.py`
- Create: `tests/test_knowledge_channel.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_knowledge_channel.py
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


def test_knowledge_add_without_channel_still_works():
    """Existing behaviour is unchanged when no channel is provided."""
    resp = client.post("/knowledge/add", json={"text": "some knowledge"})
    # Should succeed or fail for non-channel reasons (e.g., missing text content) — NOT 400 for channel
    assert resp.status_code != 400 or "not a producer" not in resp.json().get("detail", "")


def test_knowledge_add_with_unknown_channel_returns_400():
    resp = client.post("/knowledge/add", json={
        "text": "some knowledge",
        "channel": "nonexistent-channel-xyz",
    })
    assert resp.status_code == 400
    assert "not a producer" in resp.json().get("detail", "").lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_knowledge_channel.py -v 2>&1 | head -20
```

- [ ] **Step 3: Extend /knowledge/add in api.py**

Read `src/interface/api.py` lines around 2757–2790 to see the exact handler. The body parsing uses `text = body.get("text", "")` — confirm this variable name.

Find `@app.post("/knowledge/add")` handler and add after body parsing:

```python
# --- Channel write (org feature) ---
channel = body.get("channel", "").strip()
if channel:
    import importlib.util
    from src.core.org_loader import org_loader as _org_loader
    _active_sol = _get_active_solution()  # existing no-arg helper
    _col_name = _org_loader.get_producer_channel_name(_active_sol, channel)
    if _col_name is None:
        raise HTTPException(
            status_code=400,
            detail=f"solution '{_active_sol}' is not a producer for channel '{channel}'",
        )
    _channel_db = _org_loader.get_channel_db_path()
    if _channel_db and importlib.util.find_spec("chromadb") is not None:
        _write_to_channel_collection(_channel_db, _col_name, text, body.get("metadata", {}))
# --- end channel write ---
```

Add the helper function near the knowledge endpoints:

```python
def _write_to_channel_collection(db_path: str, collection_name: str, text: str, metadata: dict):
    """Write a knowledge entry to a shared channel chroma collection. Non-fatal on error."""
    try:
        import chromadb
        import uuid
        _client = chromadb.PersistentClient(path=db_path)
        _col = _client.get_or_create_collection(collection_name)
        _col.add(documents=[text], metadatas=[metadata or {}], ids=[str(uuid.uuid4())])
        logger.info("Written to channel collection %s", collection_name)
    except Exception as _exc:
        logger.warning("Channel write failed (non-fatal): %s", _exc)
```

- [ ] **Step 4: Run test**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_knowledge_channel.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/sandbox/SAGE && git add src/interface/api.py tests/test_knowledge_channel.py
git commit -m "feat(org): extend POST /knowledge/add — channel field with producer validation + channel write"
```

---

## Task 5: TaskQueue factory — per-solution queue instances

**Files:**
- Modify: `src/core/queue_manager.py`
- Create: `tests/test_cross_team_routing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cross_team_routing.py
def test_get_task_queue_returns_taskqueue_instance():
    from src.core.queue_manager import get_task_queue, TaskQueue
    q = get_task_queue("solution_a")
    assert isinstance(q, TaskQueue)

def test_get_task_queue_different_solutions_different_instances():
    from src.core.queue_manager import get_task_queue
    assert get_task_queue("sol_x") is not get_task_queue("sol_y")

def test_get_task_queue_same_solution_same_instance():
    from src.core.queue_manager import get_task_queue
    assert get_task_queue("sol_z") is get_task_queue("sol_z")
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_cross_team_routing.py -v 2>&1 | head -20
```

- [ ] **Step 3: Add factory to queue_manager.py**

At the bottom of `src/core/queue_manager.py`, after `task_queue = TaskQueue()`:

```python
import threading as _threading

_queue_registry: dict = {}
_queue_registry_lock = _threading.Lock()


def get_task_queue(solution_name: str) -> "TaskQueue":
    """
    Return (or lazily create) a TaskQueue scoped to a specific solution.
    The active solution continues to use the module-level `task_queue` singleton.
    """
    with _queue_registry_lock:
        if solution_name not in _queue_registry:
            _queue_registry[solution_name] = TaskQueue()
        return _queue_registry[solution_name]
```

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_cross_team_routing.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/sandbox/SAGE && git add src/core/queue_manager.py tests/test_cross_team_routing.py
git commit -m "feat(org): TaskQueue factory — get_task_queue(solution_name) for cross-team dispatch"
```

---

## Task 6: POST /tasks/submit — cross-team routing endpoint

**Files:**
- Modify: `src/interface/api.py`
- Modify: `tests/test_cross_team_routing.py`

- [ ] **Step 1: Add failing tests**

Add to `tests/test_cross_team_routing.py`:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch

def test_submit_task_no_target_queues_to_active_solution():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/tasks/submit", json={
        "task_type": "ANALYZE_LOG",
        "payload": {"log_entry": "test"},
    })
    assert resp.status_code == 200
    assert "task_id" in resp.json()
    assert resp.json()["status"] == "queued"


def test_submit_task_unknown_target_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(tmp_path))
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/tasks/submit", json={
        "task_type": "ANALYZE_LOG",
        "payload": {},
        "target_solution": "nonexistent_xyz",
    })
    assert resp.status_code == 404


def test_submit_task_unpermitted_target_returns_403():
    from src.interface.api import app
    client = TestClient(app)
    with patch("src.interface.api.org_loader") as mock_org:
        mock_org.org_name = "test_org"
        mock_org.is_route_allowed.return_value = False
        with patch("src.interface.api._get_solutions_dir", return_value="/tmp"):
            import os
            os.makedirs("/tmp/target_team", exist_ok=True)
            resp = client.post("/tasks/submit", json={
                "task_type": "ANALYZE_LOG",
                "payload": {},
                "target_solution": "target_team",
                "source_solution": "my_team",
            })
    assert resp.status_code == 403
    assert "not permitted" in resp.json().get("detail", "").lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_cross_team_routing.py::test_submit_task_no_target_queues_to_active_solution -v 2>&1 | head -20
```

- [ ] **Step 3: Add POST /tasks/submit to api.py**

First read `api.py` to find the existing `_get_solutions_dir` function (should be around line 1878). Use it — do NOT add a duplicate. If it doesn't exist with that name, find the equivalent and use it.

Add the endpoint near the task-related endpoints:

```python
@app.post("/tasks/submit")
async def submit_task(request: Request):
    """
    Submit a task to the active solution's queue, or route to another team's queue.
    Body: task_type (required), payload, priority, target_solution, source_solution
    """
    body = await request.json()
    task_type = body.get("task_type", "").strip()
    if not task_type:
        raise HTTPException(status_code=400, detail="task_type is required")

    payload    = body.get("payload", {})
    priority   = int(body.get("priority", 5))
    target_sol = body.get("target_solution", "").strip() or None
    source_sol = body.get("source_solution", "").strip() or None

    from src.core.org_loader import org_loader as _org_loader
    from src.core.queue_manager import get_task_queue, task_queue as _default_queue

    if target_sol:
        # Resolve source identity (spec: 3-step order)
        if not source_sol:
            tenant = request.headers.get("X-SAGE-Tenant", "").strip()
            sols_dir = _get_solutions_dir()  # use EXISTING helper
            if tenant and os.path.isdir(os.path.join(sols_dir, tenant)):
                source_sol = tenant
            else:
                source_sol = _get_project_config().project_name

        # Validate target exists on disk
        if not os.path.isdir(os.path.join(_get_solutions_dir(), target_sol)):
            raise HTTPException(status_code=404, detail=f"target_solution '{target_sol}' not found")

        # Validate routing permission
        if _org_loader.org_name and not _org_loader.is_route_allowed(source_sol, target_sol):
            raise HTTPException(
                status_code=403,
                detail=f"solution '{source_sol}' is not permitted to route tasks to '{target_sol}'",
            )

        queue = get_task_queue(target_sol)
        metadata = {"source_solution": source_sol, "target_solution": target_sol}
    else:
        queue = _default_queue
        metadata = {}

    task_id = queue.submit(
        task_type, payload,
        priority=priority,
        source="cross_team_route" if target_sol else "api",
        metadata=metadata,
    )
    return {
        "task_id": task_id,
        "target_solution": target_sol or _get_project_config().project_name,
        "status": "queued",
    }
```

Also: add cross-team completion notification in `queue_manager.py`'s `TaskWorker._dispatch()`. After the existing task completion logic, add:

```python
# Cross-team completion notification — write to source solution's audit log
source_sol = task.metadata.get("source_solution") if task.metadata else None
target_sol = task.metadata.get("target_solution") if task.metadata else None
if source_sol and target_sol:
    try:
        from src.core.project_loader import _SOLUTIONS_DIR
        import os as _os
        source_db = _os.path.join(_SOLUTIONS_DIR, source_sol, ".sage", "audit_log.db")
        # Only attempt if source solution has a .sage directory
        if _os.path.exists(_os.path.dirname(source_db)):
            from src.memory.audit_logger import AuditLogger
            _source_logger = AuditLogger(source_db)
            _source_logger.log(
                event_type="cross_team_task_completed",
                trace_id=task.task_id,
                input_data={"source_solution": source_sol, "target_solution": target_sol,
                            "task_type": task.task_type},
                output_content=str(result)[:500],
                status="completed",
                agent_name="cross_team",
            )
    except Exception as _ct_exc:
        logger.debug("cross-team notification failed (non-fatal): %s", _ct_exc)
```

Read `queue_manager.py` around `_dispatch()` and `AuditLogger` usage to match exact call signatures before writing.

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_cross_team_routing.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/sandbox/SAGE && git add src/interface/api.py src/core/queue_manager.py tests/test_cross_team_routing.py
git commit -m "feat(org): POST /tasks/submit — cross-team routing + completion notification to source audit log"
```

---

## Task 7: Org CRUD API — 8 new endpoints + enrich GET /org

**Files:**
- Modify: `src/interface/api.py`
- Create: `tests/test_org_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_org_api.py
from fastapi.testclient import TestClient
from src.interface.api import app

client = TestClient(app)


def test_get_org_returns_200():
    resp = client.get("/org")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_get_org_includes_routes_key():
    resp = client.get("/org")
    assert resp.status_code == 200
    # Always has a routes key (may be empty list when no org configured)
    assert "routes" in resp.json()


def test_org_reload_returns_reloaded():
    resp = client.post("/org/reload")
    assert resp.status_code == 200
    assert resp.json().get("status") == "reloaded"


def test_org_routes_post_requires_solution_and_target():
    resp = client.post("/org/routes", json={})
    assert resp.status_code == 400


def test_org_routes_delete_requires_solution_and_target():
    resp = client.request("DELETE", "/org/routes", json={})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_api.py -v 2>&1 | head -20
```

- [ ] **Step 3: Add 8 /org/* endpoints to api.py**

Add near the end of `src/interface/api.py`. All `yaml` usage must use **local imports inside function bodies** (there is no top-level `import yaml` in api.py):

```python
# ============================================================
# Organization endpoints — org.yaml CRUD
# ============================================================

def _get_org_yaml_path() -> str:
    return os.path.join(_get_solutions_dir(), "org.yaml")


@app.get("/org")
async def org_get():
    """Return org.yaml content enriched with cross_team_routes from all solutions."""
    import yaml as _yaml
    path = _get_org_yaml_path()
    data: dict = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
    # Enrich with all cross_team_routes (for orange edges in UI)
    from src.core.org_loader import org_loader as _ol
    data["routes"] = _ol.get_all_routes()
    return data


@app.post("/org/reload")
async def org_reload():
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "reloaded"}


@app.post("/org/channels")
async def org_channels_create(request: Request):
    import yaml as _yaml
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="channel name is required")
    path = _get_org_yaml_path()
    data: dict = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
    data.setdefault("org", {}).setdefault("knowledge_channels", {})[name] = {
        "producers": body.get("producers", []),
        "consumers": body.get("consumers", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        _yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "created", "channel": name}


@app.delete("/org/channels/{name}")
async def org_channels_delete(name: str):
    import yaml as _yaml
    path = _get_org_yaml_path()
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="no org.yaml configured")
    with open(path, "r", encoding="utf-8") as f:
        data = _yaml.safe_load(f) or {}
    channels = data.get("org", {}).get("knowledge_channels", {})
    if name not in channels:
        raise HTTPException(status_code=404, detail=f"channel '{name}' not found")
    del channels[name]
    with open(path, "w", encoding="utf-8") as f:
        _yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "deleted", "channel": name}


@app.post("/org/solutions")
async def org_solutions_add(request: Request):
    import yaml as _yaml
    body = await request.json()
    solution = body.get("solution", "").strip()
    parent   = body.get("parent", "").strip()
    if not solution or not parent:
        raise HTTPException(status_code=400, detail="solution and parent are required")
    proj_path = os.path.join(_get_solutions_dir(), solution, "project.yaml")
    if not os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{solution}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    proj["parent"] = parent
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "added", "solution": solution, "parent": parent}


@app.delete("/org/solutions/{name}")
async def org_solutions_remove(name: str):
    import yaml as _yaml
    proj_path = os.path.join(_get_solutions_dir(), name, "project.yaml")
    if not os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{name}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    proj.pop("parent", None)
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "removed", "solution": name}


@app.post("/org/routes")
async def org_routes_add(request: Request):
    import yaml as _yaml
    body = await request.json()
    solution = body.get("solution", "").strip()
    target   = body.get("target", "").strip()
    if not solution or not target:
        raise HTTPException(status_code=400, detail="solution and target are required")
    proj_path = os.path.join(_get_solutions_dir(), solution, "project.yaml")
    if not os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{solution}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    routes = proj.get("cross_team_routes", [])
    if not any(r.get("target") == target for r in routes):
        routes.append({"target": target})
    proj["cross_team_routes"] = routes
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "added", "solution": solution, "target": target}


@app.delete("/org/routes")
async def org_routes_delete(request: Request):
    import yaml as _yaml
    body = await request.json()
    solution = body.get("solution", "").strip()
    target   = body.get("target", "").strip()
    if not solution or not target:
        raise HTTPException(status_code=400, detail="solution and target are required")
    proj_path = os.path.join(_get_solutions_dir(), solution, "project.yaml")
    if not os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{solution}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    proj["cross_team_routes"] = [
        r for r in proj.get("cross_team_routes", []) if r.get("target") != target
    ]
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "removed", "solution": solution, "target": target}
```

- [ ] **Step 4: Run tests**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_org_api.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/sandbox/SAGE && git add src/interface/api.py tests/test_org_api.py
git commit -m "feat(org): 8 /org/* CRUD endpoints — channels, solutions, routes, reload; GET /org includes routes"
```

---

## Task 8: Onboarding enhancement

**Files:**
- Modify: `src/core/onboarding.py`
- Create: `tests/test_onboarding_org.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_onboarding_org.py
from unittest.mock import patch


def test_onboarding_accepts_parent_solution_field():
    from fastapi.testclient import TestClient
    from src.interface.api import app
    client = TestClient(app)
    with patch("src.core.onboarding.OnboardingWizard.generate") as mock_gen:
        mock_gen.return_value = {
            "project_yaml": "name: fw_team\nparent: product_base\n",
            "prompts_yaml": "",
            "tasks_yaml": "",
            "suggested_routes": ["team_hw"],
        }
        resp = client.post("/onboarding/generate", json={
            "description": "Firmware team",
            "solution_name": "fw_team",
            "parent_solution": "product_base",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "suggested_routes" in data
    assert isinstance(data["suggested_routes"], list)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_onboarding_org.py -v 2>&1 | head -20
```

- [ ] **Step 3: Modify onboarding.py**

Read `src/core/onboarding.py` to understand the existing request model and `generate()` method.

Add `parent_solution: str = ""` and `org_name: str = ""` to the request body parsing.

In `generate()`:
1. If `parent_solution` is non-empty, ensure the generated `project_yaml` contains `parent: <parent_solution>` (inject it post-generation if the LLM omits it)
2. Add to the LLM prompt: "Suggest 2-4 solution names this team should be able to route tasks to, based on the description. Return them as a JSON field `suggested_routes` (list of strings). Use snake_case names."
3. Parse `suggested_routes` from LLM response JSON (default `[]` on parse failure)
4. Include `suggested_routes` in the return dict

If `org_name` is provided and `org.yaml` already exists, call the same write logic as `POST /org/solutions` to add `parent:` to the new solution's `project.yaml`.

- [ ] **Step 4: Run test**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/test_onboarding_org.py -v
```

- [ ] **Step 5: Commit**

```bash
cd C:/sandbox/SAGE && git add src/core/onboarding.py tests/test_onboarding_org.py
git commit -m "feat(org): onboarding — parent_solution, org_name fields + suggested_routes in response"
```

---

## Task 9: Org Graph UI

**Files:**
- Create: `web/src/pages/OrgGraph.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/layout/Sidebar.tsx`
- Modify: `web/src/registry/modules.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Install react-flow**

```bash
cd C:/sandbox/SAGE/web && npm install @xyflow/react
```

- [ ] **Step 2: Add typed fetch functions to client.ts**

Add to `web/src/api/client.ts`:

```typescript
export interface OrgChannel {
  producers: string[];
  consumers: string[];
}

export interface OrgRoute {
  source: string;
  target: string;
}

export interface OrgData {
  org?: {
    name?: string;
    root_solution?: string;
    knowledge_channels?: Record<string, OrgChannel>;
  };
  routes?: OrgRoute[];
}

export async function fetchOrg(): Promise<OrgData> {
  const res = await fetch(`${API_BASE}/org`);
  if (!res.ok) throw new Error("Failed to fetch org");
  return res.json();
}

export async function reloadOrg(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/org/reload`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reload org");
  return res.json();
}

export async function createOrgChannel(
  name: string, producers: string[], consumers: string[]
): Promise<void> {
  await fetch(`${API_BASE}/org/channels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, producers, consumers }),
  });
}

export async function deleteOrgChannel(name: string): Promise<void> {
  await fetch(`${API_BASE}/org/channels/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export async function addOrgRoute(solution: string, target: string): Promise<void> {
  await fetch(`${API_BASE}/org/routes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ solution, target }),
  });
}

export async function removeOrgRoute(solution: string, target: string): Promise<void> {
  await fetch(`${API_BASE}/org/routes`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ solution, target }),
  });
}
```

- [ ] **Step 3: Create OrgGraph.tsx**

```tsx
import React, { useEffect, useCallback } from "react";
import {
  ReactFlow,
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { fetchOrg, reloadOrg, OrgData } from "../api/client";

function buildGraph(org: OrgData): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const channels = org.org?.knowledge_channels ?? {};
  const routes   = org.routes ?? [];
  const root     = org.org?.root_solution;
  const allNames = new Set<string>();

  if (root) allNames.add(root);
  Object.values(channels).forEach(({ producers, consumers }) => {
    producers.forEach((p) => allNames.add(p));
    consumers.forEach((c) => allNames.add(c));
  });
  routes.forEach(({ source, target }) => {
    allNames.add(source);
    allNames.add(target);
  });

  let i = 0;
  allNames.forEach((name) => {
    nodes.push({
      id: name,
      data: { label: name },
      position: { x: (i % 4) * 240, y: Math.floor(i / 4) * 130 },
      style: {
        background: name === root ? "#1e3a5f" : "#1e293b",
        color: "#e2e8f0",
        border: name === root ? "2px dashed #60a5fa" : "1px solid #475569",
        borderRadius: 8,
        padding: "8px 16px",
        fontWeight: name === root ? 700 : 400,
      },
    });
    i++;
  });

  // Blue edges — knowledge channels
  let ei = 0;
  Object.entries(channels).forEach(([chName, { producers, consumers }]) => {
    producers.forEach((producer) => {
      consumers.forEach((consumer) => {
        edges.push({
          id: `ch-${chName}-${ei++}`,
          source: producer,
          target: consumer,
          label: chName,
          style: { stroke: "#3b82f6" },
          labelStyle: { fill: "#93c5fd", fontSize: 10 },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#3b82f6" },
          type: "smoothstep",
        });
      });
    });
  });

  // Orange edges — task routing links
  routes.forEach(({ source, target }, idx) => {
    edges.push({
      id: `route-${source}-${target}-${idx}`,
      source,
      target,
      label: "routes tasks",
      style: { stroke: "#f97316" },
      labelStyle: { fill: "#fdba74", fontSize: 10 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "#f97316" },
      type: "smoothstep",
    });
  });

  return { nodes, edges };
}

export default function OrgGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading]   = React.useState(true);
  const [orgData, setOrgData]   = React.useState<OrgData>({});
  const [error,   setError]     = React.useState<string | null>(null);

  const loadOrg = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchOrg();
      setOrgData(data);
      const { nodes: n, edges: e } = buildGraph(data);
      setNodes(n);
      setEdges(e);
      setError(null);
    } catch {
      setError("Failed to load org configuration");
    } finally {
      setLoading(false);
    }
  }, [setNodes, setEdges]);

  useEffect(() => { loadOrg(); }, [loadOrg]);

  if (loading) return <div style={{ padding: 32, color: "#94a3b8" }}>Loading…</div>;
  if (error)   return <div style={{ padding: 32, color: "#f87171" }}>{error}</div>;

  const isEmpty = !orgData.org?.name;

  return (
    <div style={{ padding: "24px 32px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: "#f1f5f9", margin: 0 }}>
            Organization
          </h1>
          {orgData.org?.name && (
            <p style={{ color: "#64748b", margin: "4px 0 0" }}>{orgData.org.name}</p>
          )}
        </div>
        <button
          onClick={async () => { await reloadOrg(); await loadOrg(); }}
          style={{
            padding: "8px 16px", borderRadius: 6,
            background: "#1e293b", color: "#94a3b8",
            border: "1px solid #334155", cursor: "pointer",
          }}
        >
          Reload
        </button>
      </div>

      {isEmpty ? (
        <div style={{
          padding: 48, textAlign: "center", color: "#64748b",
          border: "1px dashed #334155", borderRadius: 12,
        }}>
          <p style={{ fontSize: 18, marginBottom: 8 }}>No org.yaml configured</p>
          <p style={{ fontSize: 14 }}>
            Create <code>org.yaml</code> in your SAGE_SOLUTIONS_DIR to define your organization.
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: "flex", gap: 24, marginBottom: 16 }}>
            <Legend color="#3b82f6" label="Knowledge channel" />
            <Legend color="#f97316" label="Task routing link" />
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#94a3b8" }}>
              <div style={{ width: 14, height: 14, border: "2px dashed #60a5fa", borderRadius: 2 }} />
              <span>Root solution</span>
            </div>
          </div>

          <div style={{ height: 520, background: "#0f172a", borderRadius: 12, border: "1px solid #1e293b" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
            >
              <Background color="#1e293b" gap={24} />
              <Controls />
              <MiniMap nodeColor="#334155" maskColor="rgba(0,0,0,0.6)" />
            </ReactFlow>
          </div>

          <div style={{ marginTop: 24 }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: "#f1f5f9", marginBottom: 12 }}>
              Knowledge Channels
            </h2>
            {Object.entries(orgData.org?.knowledge_channels ?? {}).map(([name, conf]) => (
              <div key={name} style={{
                padding: "12px 16px", marginBottom: 8,
                background: "#1e293b", borderRadius: 8, border: "1px solid #334155",
                display: "flex", justifyContent: "space-between",
              }}>
                <span style={{ color: "#60a5fa", fontWeight: 600 }}>{name}</span>
                <span style={{ color: "#64748b", fontSize: 13 }}>
                  {conf.producers.join(", ")} → {conf.consumers.join(", ")}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "#94a3b8" }}>
      <div style={{ width: 32, height: 2, background: color }} />
      <span>{label}</span>
    </div>
  );
}
```

- [ ] **Step 4: Wire the page (4 changes)**

**web/src/App.tsx:** Add import and route:
```tsx
import OrgGraph from "./pages/OrgGraph";
// inside <Routes>:
<Route path="/org" element={<OrgGraph />} />
```

**web/src/components/layout/Sidebar.tsx:** Read the file first to see the NAV_GROUPS array structure and which icons are already imported. Add an entry:
```tsx
{ id: "org", label: "Organization", icon: </* appropriate already-imported icon */>, path: "/org" }
```

**web/src/registry/modules.ts:** Add to `MODULE_REGISTRY`:
```typescript
org: {
  id: "org",
  label: "Organization",
  description: "Visualize and configure solution hierarchy, knowledge channels, and cross-team routing",
  defaultVisible: true,
  requiresAdmin: true,
  path: "/org",
},
```

- [ ] **Step 5: Verify UI builds**

```bash
cd C:/sandbox/SAGE/web && npm run build 2>&1 | tail -20
```
Expected: build succeeds, zero TypeScript errors.

- [ ] **Step 6: Commit**

```bash
cd C:/sandbox/SAGE && git add web/src/pages/OrgGraph.tsx web/src/App.tsx \
  web/src/components/layout/Sidebar.tsx web/src/registry/modules.ts web/src/api/client.ts
git commit -m "feat(org): Org Graph UI — react-flow visualization with blue knowledge + orange routing edges"
```

---

## Task 10: Full test suite pass

- [ ] **Step 1: Run full suite**

```bash
cd C:/sandbox/SAGE && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all existing tests pass + all new org tests pass. Zero regressions.

- [ ] **Step 2: Fix any failures**

Common issues to watch for:
- `VectorMemory.__init__` signature change — check all call sites in tests (they call `VectorMemory()` with no args — the new `explicit_solution=None` default keeps this backward-compatible)
- `_get_active_solution()` called somewhere with an arg — search `api.py` for all usages
- `_get_solutions_dir` name — verify it exists in `api.py` before using it in new endpoints; if the existing function has a different name, use that
- `task_queue.submit()` `metadata` param — confirm it exists in `TaskQueue.submit()` signature

- [ ] **Step 3: Commit fixes if needed**

```bash
cd C:/sandbox/SAGE && git add -A && git commit -m "fix(org): resolve test suite regressions after org feature integration"
```

---

## Already-pending tasks (not in this plan)

These were pending before this feature and are tracked separately:

1. **OpenShell shallow wiring** — `queue_manager._dispatch()` checks `task_sandbox_policies`, creates sandbox context, stores handle in thread-local
2. **Browser test** — smoke-test all SAGE features via board_games solution in Chrome
