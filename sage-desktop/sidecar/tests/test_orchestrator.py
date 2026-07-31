"""Tests for the orchestrator handler — observability over the 9 modules.

Read-only by design, matching what web/src/pages/Orchestrator.tsx actually
consumes: every function it imports is a fetch. The mutating routes on the web
router (`POST /orchestrator/spawn`, `/tools/execute`, `/budget`) are not
surfaced, and `/orchestrator/events/stream` is out of scope under the standing
streaming exclusion — `events/history` gives the same data by polling.

Two RPCs rather than the router's ~25 endpoints: `stats` is already an
aggregate over all nine modules, and the six "recent list" endpoints differ
only by which singleton they call, so they collapse into one parameterised
`recent(module)`.

These subsystems are legitimately idle on a desktop install, so every lookup
degrades to an empty result rather than raising — the same choice monitor.* and
scheduler.* already make.
"""

from __future__ import annotations

import pytest

from handlers import orchestrator as orch
from rpc import RpcError

INVALID_PARAMS = -32602


class FakeModule:
    def __init__(self, stats=None, items=None):
        self._stats = stats or {"count": 1}
        self._items = items if items is not None else [{"id": "x"}]

    def get_stats(self):
        return self._stats

    # The six recent-list singletons expose differently-named readers.
    def list_recent(self, limit=20):
        return self._items[:limit]

    def list_spawns(self, parent_task_id=None, limit=50):
        return self._items[:limit]

    def get_history(self, event_type=None, limit=50):
        return self._items[:limit]

    def list_records(self, limit=20):
        return self._items[:limit]

    def list_results(self, limit=20):
        return self._items[:limit]


@pytest.fixture
def modules(monkeypatch):
    fakes = {name: FakeModule() for name in orch._MODULES}
    monkeypatch.setattr(orch, "_resolver", lambda name: fakes[name])
    return fakes


# ---------- stats ----------


def test_stats_covers_all_nine_modules(modules):
    out = orch.stats({})

    assert set(out["modules"]) == set(orch._MODULES)
    assert len(orch._MODULES) == 9, "the docs promise nine modules"


def test_stats_reports_each_modules_numbers(modules):
    out = orch.stats({})
    assert out["modules"]["budget"] == {"count": 1}


def test_stats_degrades_per_module_instead_of_failing(monkeypatch):
    """One unavailable subsystem must not blank the whole page."""

    def resolver(name):
        if name == "consensus":
            raise ImportError("consensus_engine unavailable")
        return FakeModule()

    monkeypatch.setattr(orch, "_resolver", resolver)
    out = orch.stats({})

    assert out["modules"]["consensus"] == {}
    assert out["modules"]["budget"] == {"count": 1}
    assert "consensus" in out["unavailable"]


def test_stats_lists_nothing_unavailable_when_all_load(modules):
    assert orch.stats({})["unavailable"] == []


# ---------- recent ----------


@pytest.mark.parametrize(
    "module",
    ["events", "reflection", "plans", "spawns", "tools", "backtrack", "consensus"],
)
def test_recent_returns_items_for_every_supported_module(modules, module):
    out = orch.recent({"module": module})
    assert out["module"] == module
    assert out["items"] == [{"id": "x"}]


def test_recent_honours_the_limit(monkeypatch):
    many = [{"id": str(i)} for i in range(10)]
    monkeypatch.setattr(orch, "_resolver", lambda name: FakeModule(items=many))

    assert len(orch.recent({"module": "events", "limit": 3})["items"]) == 3


def test_recent_clamps_an_absurd_limit(monkeypatch):
    many = [{"id": str(i)} for i in range(500)]
    monkeypatch.setattr(orch, "_resolver", lambda name: FakeModule(items=many))

    out = orch.recent({"module": "events", "limit": 10_000})
    assert len(out["items"]) <= orch._MAX_LIMIT


def test_recent_rejects_an_unknown_module(modules):
    with pytest.raises(RpcError) as e:
        orch.recent({"module": "nope"})
    assert e.value.code == INVALID_PARAMS


def test_recent_requires_a_module(modules):
    with pytest.raises(RpcError) as e:
        orch.recent({})
    assert e.value.code == INVALID_PARAMS


def test_recent_rejects_a_stats_only_module(modules):
    """memory_planner exposes stats but no recent list — saying so beats
    returning a silently empty list."""
    with pytest.raises(RpcError) as e:
        orch.recent({"module": "memory_planner"})
    assert e.value.code == INVALID_PARAMS


def test_recent_degrades_to_empty_when_the_module_is_missing(monkeypatch):
    def resolver(name):
        raise ImportError("not installed")

    monkeypatch.setattr(orch, "_resolver", resolver)
    out = orch.recent({"module": "events"})

    assert out["items"] == []
    assert out["available"] is False
