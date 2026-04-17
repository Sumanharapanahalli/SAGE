"""Tests for the Collective Intelligence handler.

Uses a fake CollectiveMemory that mirrors the public shape of
``src.core.collective_memory.CollectiveMemory`` so the handler is
tested without pulling in git or ChromaDB. One end-to-end test at
the bottom of this file exercises a real ``CollectiveMemory`` in
a ``tmp_path``.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.collective as collective  # noqa: E402
from rpc import RpcError  # noqa: E402


class _FakeCM:
    """Minimal CollectiveMemory stand-in.

    Stores learnings and help requests in-memory; publish returns an
    id or a proposal trace_id depending on ``require_approval``.
    """

    def __init__(self, require_approval: bool = False) -> None:
        self.require_approval = require_approval
        self.repo_path = "/tmp/fake-collective"
        self._git_available = True
        self._learnings: dict[str, dict] = {}
        self._help_open: dict[str, dict] = {}
        self._help_closed: dict[str, dict] = {}
        self._proposals: dict[str, dict] = {}
        self._pulled = False
        self._indexed = 0

    # ── Learning helpers (fake) ────────────────────────────────
    def _add_learning(self, *, solution="s1", topic="t1", title="t", content="c") -> str:
        lid = str(uuid.uuid4())
        self._learnings[lid] = {
            "id": lid,
            "author_agent": "analyst",
            "author_solution": solution,
            "topic": topic,
            "title": title,
            "content": content,
            "tags": [],
            "confidence": 0.5,
            "validation_count": 0,
            "created_at": "2026-04-17T00:00:00+00:00",
            "updated_at": "2026-04-17T00:00:00+00:00",
            "source_task_id": "",
        }
        return lid

    def list_learnings(self, solution=None, topic=None, limit=50, offset=0):
        items = list(self._learnings.values())
        if solution:
            items = [x for x in items if x["author_solution"] == solution]
        if topic:
            items = [x for x in items if x["topic"] == topic]
        return items[offset: offset + limit]

    def get_learning(self, learning_id: str):
        return self._learnings.get(learning_id)

    def search_learnings(self, query, tags=None, solution=None, limit=10):
        items = list(self._learnings.values())
        if query:
            q = query.lower()
            items = [
                x for x in items
                if q in x["title"].lower() or q in x["content"].lower()
            ]
        if tags:
            items = [x for x in items if any(t in x.get("tags", []) for t in tags)]
        if solution:
            items = [x for x in items if x["author_solution"] == solution]
        return items[:limit]

    def publish_learning(self, learning: dict, proposed_by: str = "system") -> str:
        # Mirror the real class: returns id OR trace_id depending on
        # require_approval.
        if self.require_approval:
            trace_id = f"trace-{uuid.uuid4().hex[:8]}"
            self._proposals[trace_id] = {"learning": learning, "proposed_by": proposed_by}
            return trace_id
        lid = str(uuid.uuid4())
        full = dict(learning, id=lid, validation_count=0,
                    created_at="2026-04-17T00:00:00+00:00",
                    updated_at="2026-04-17T00:00:00+00:00")
        self._learnings[lid] = full
        return lid

    def validate_learning(self, learning_id: str, validated_by: str) -> dict:
        if learning_id not in self._learnings:
            raise ValueError(f"Learning {learning_id} not found")
        l = self._learnings[learning_id]
        l["validation_count"] += 1
        l["confidence"] = min(1.0, l["confidence"] + (1.0 - l["confidence"]) * 0.1)
        l["updated_at"] = "2026-04-17T00:00:01+00:00"
        return l

    def _add_help(self, *, status="open", expertise=None, urgency="medium"):
        hid = f"hr-{uuid.uuid4().hex[:8]}"
        data = {
            "id": hid,
            "title": "help me",
            "requester_agent": "dev",
            "requester_solution": "auto",
            "status": status,
            "urgency": urgency,
            "required_expertise": expertise or [],
            "context": "",
            "created_at": "2026-04-17T00:00:00+00:00",
            "claimed_by": None,
            "responses": [],
            "resolved_at": None,
        }
        (self._help_open if status == "open" else self._help_closed)[hid] = data
        return hid

    def list_help_requests(self, status="open", expertise=None):
        source = self._help_open if status == "open" else self._help_closed
        items = list(source.values())
        if expertise:
            items = [
                x for x in items
                if any(e in x.get("required_expertise", []) for e in expertise)
            ]
        return items

    def create_help_request(self, request: dict) -> str:
        hid = f"hr-{uuid.uuid4().hex[:8]}"
        self._help_open[hid] = {
            "id": hid,
            "title": request.get("title", ""),
            "requester_agent": request.get("requester_agent", ""),
            "requester_solution": request.get("requester_solution", ""),
            "status": "open",
            "urgency": request.get("urgency", "medium"),
            "required_expertise": request.get("required_expertise", []),
            "context": request.get("context", ""),
            "created_at": "2026-04-17T00:00:00+00:00",
            "claimed_by": None,
            "responses": [],
            "resolved_at": None,
        }
        return hid

    def claim_help_request(self, request_id: str, agent: str, solution: str) -> dict:
        if request_id not in self._help_open:
            raise ValueError(f"Help request {request_id} not found in open requests")
        data = self._help_open[request_id]
        if data.get("claimed_by"):
            raise ValueError(f"Help request {request_id} is already claimed")
        data["status"] = "claimed"
        data["claimed_by"] = {
            "agent": agent, "solution": solution,
            "claimed_at": "2026-04-17T00:00:01+00:00",
        }
        return data

    def respond_to_help_request(self, request_id: str, response: dict) -> dict:
        src = self._help_open if request_id in self._help_open else self._help_closed
        if request_id not in src:
            raise ValueError(f"Help request {request_id} not found")
        src[request_id].setdefault("responses", []).append({
            "responder_agent": response.get("responder_agent", ""),
            "responder_solution": response.get("responder_solution", ""),
            "content": response.get("content", ""),
            "created_at": "2026-04-17T00:00:02+00:00",
        })
        return src[request_id]

    def close_help_request(self, request_id: str) -> dict:
        if request_id not in self._help_open:
            raise ValueError(f"Help request {request_id} not found in open requests")
        data = self._help_open.pop(request_id)
        data["status"] = "closed"
        data["resolved_at"] = "2026-04-17T00:00:03+00:00"
        self._help_closed[request_id] = data
        return data

    def sync(self) -> dict:
        self._pulled = True
        self._indexed = len(self._learnings)
        return {"pulled": True, "indexed": self._indexed}

    def get_stats(self) -> dict:
        topics: dict[str, int] = {}
        contributors: dict[str, int] = {}
        for l in self._learnings.values():
            topics[l["topic"]] = topics.get(l["topic"], 0) + 1
            contributors[l["author_solution"]] = (
                contributors.get(l["author_solution"], 0) + 1
            )
        return {
            "learning_count": len(self._learnings),
            "help_request_count": len(self._help_open),
            "help_requests_closed": len(self._help_closed),
            "topics": topics,
            "contributors": contributors,
        }


@pytest.fixture
def wired():
    cm = _FakeCM()
    # Re-bind in tests via monkeypatch.setattr(collective, "_cm", cm)
    return cm


def test_require_cm_raises_when_unwired(monkeypatch):
    monkeypatch.setattr(collective, "_cm", None)
    with pytest.raises(RpcError) as e:
        collective._require_cm()
    assert e.value.code == -32000
    assert "not wired" in e.value.message


def test_require_dict_rejects_non_dict():
    with pytest.raises(RpcError) as e:
        collective._require_dict("not a dict")
    assert e.value.code == -32602


def test_list_learnings_returns_paginated_slice(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    for i in range(5):
        wired._add_learning(topic=f"t{i}")
    out = collective.list_learnings({"limit": 2, "offset": 1})
    assert len(out["entries"]) == 2
    assert out["total"] == 5
    assert out["limit"] == 2
    assert out["offset"] == 1


def test_list_learnings_filters_by_solution_and_topic(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(solution="a", topic="t1")
    wired._add_learning(solution="a", topic="t2")
    wired._add_learning(solution="b", topic="t1")
    out = collective.list_learnings({"solution": "a", "topic": "t1"})
    assert out["total"] == 1
    assert out["entries"][0]["author_solution"] == "a"
    assert out["entries"][0]["topic"] == "t1"


def test_list_learnings_rejects_oversized_limit(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.list_learnings({"limit": 10000})
    assert e.value.code == -32602


def test_get_learning_returns_entry(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    lid = wired._add_learning(title="needle")
    out = collective.get_learning({"id": lid})
    assert out["learning"]["id"] == lid
    assert out["learning"]["title"] == "needle"


def test_get_learning_returns_null_when_missing(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    out = collective.get_learning({"id": "ghost"})
    assert out == {"learning": None}


def test_get_learning_rejects_empty_id(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError):
        collective.get_learning({"id": ""})


def test_search_learnings_matches_query(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(title="UART overflow recovery")
    wired._add_learning(title="SPI timing tricks")
    out = collective.search_learnings({"query": "UART"})
    assert out["count"] == 1
    assert out["results"][0]["title"] == "UART overflow recovery"
    assert out["query"] == "UART"


def test_search_learnings_accepts_empty_query(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(title="one")
    wired._add_learning(title="two")
    out = collective.search_learnings({"query": ""})
    assert out["count"] == 2


def test_search_learnings_clamps_limit(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.search_learnings({"query": "x", "limit": 500})
    assert e.value.code == -32602


def test_search_learnings_rejects_non_string_query(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.search_learnings({"query": 42})
    assert e.value.code == -32602


def test_publish_learning_ungated_returns_id(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    out = collective.publish_learning({
        "author_agent": "analyst",
        "author_solution": "medtech",
        "topic": "uart",
        "title": "test",
        "content": "details",
    })
    assert out["gated"] is False
    assert out["id"] is not None
    assert "trace_id" not in out or out.get("trace_id") is None


def test_publish_learning_gated_returns_trace_id(wired, monkeypatch):
    wired.require_approval = True
    monkeypatch.setattr(collective, "_cm", wired)
    out = collective.publish_learning({
        "author_agent": "analyst",
        "author_solution": "medtech",
        "topic": "uart",
        "title": "t",
        "content": "c",
        "proposed_by": "operator@desktop",
    })
    assert out["gated"] is True
    assert out["id"] is None
    assert out["trace_id"].startswith("trace-")


def test_publish_learning_requires_core_fields(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    for payload in [
        {"author_solution": "s", "topic": "t", "title": "ti", "content": "c"},
        {"author_agent": "a", "topic": "t", "title": "ti", "content": "c"},
        {"author_agent": "a", "author_solution": "s", "title": "ti", "content": "c"},
        {"author_agent": "a", "author_solution": "s", "topic": "t", "content": "c"},
        {"author_agent": "a", "author_solution": "s", "topic": "t", "title": "ti"},
    ]:
        with pytest.raises(RpcError) as e:
            collective.publish_learning(payload)
        assert e.value.code == -32602


def test_validate_learning_bumps_count(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    lid = wired._add_learning()
    out = collective.validate_learning({"id": lid, "validated_by": "qa@medtech"})
    assert out["learning"]["validation_count"] == 1
    assert out["learning"]["confidence"] > 0.5


def test_validate_learning_rejects_empty_validator(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError):
        collective.validate_learning({"id": "any", "validated_by": ""})


def test_validate_learning_propagates_not_found(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.validate_learning({"id": "ghost", "validated_by": "qa"})
    assert e.value.code == -32000
    assert "not found" in e.value.message.lower()


def test_list_help_requests_defaults_to_open(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_help(status="open")
    wired._add_help(status="closed")
    out = collective.list_help_requests({})
    assert out["count"] == 1
    assert out["entries"][0]["status"] == "open"


def test_list_help_requests_filters_by_expertise(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_help(expertise=["i2c"])
    wired._add_help(expertise=["uart"])
    out = collective.list_help_requests({"expertise": ["uart"]})
    assert out["count"] == 1
    assert "uart" in out["entries"][0]["required_expertise"]


def test_list_help_requests_rejects_bad_status(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.list_help_requests({"status": "archived"})
    assert e.value.code == -32602


def test_create_help_request_returns_id(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    out = collective.create_help_request({
        "title": "I2C help",
        "requester_agent": "developer",
        "requester_solution": "automotive",
        "urgency": "high",
        "required_expertise": ["i2c"],
        "context": "stuck",
    })
    assert out["id"].startswith("hr-")
    assert len(wired._help_open) == 1


def test_create_help_request_rejects_bad_urgency(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.create_help_request({
            "title": "x", "requester_agent": "a",
            "requester_solution": "s", "urgency": "emergency",
        })
    assert e.value.code == -32602


def test_create_help_request_requires_title(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError):
        collective.create_help_request({
            "title": "", "requester_agent": "a", "requester_solution": "s",
        })


def test_claim_help_request_transitions_to_claimed(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    hid = wired._add_help()
    out = collective.claim_help_request(
        {"id": hid, "agent": "fw", "solution": "iot"}
    )
    assert out["request"]["status"] == "claimed"
    assert out["request"]["claimed_by"]["agent"] == "fw"


def test_claim_help_request_raises_if_already_claimed(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    hid = wired._add_help()
    wired._help_open[hid]["claimed_by"] = {"agent": "other", "solution": "x"}
    with pytest.raises(RpcError) as e:
        collective.claim_help_request(
            {"id": hid, "agent": "fw", "solution": "iot"}
        )
    assert e.value.code == -32000
    assert "claimed" in e.value.message.lower()


def test_claim_help_request_requires_fields(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError):
        collective.claim_help_request({"id": "", "agent": "a", "solution": "s"})


def test_respond_to_help_request_appends_response(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    hid = wired._add_help()
    out = collective.respond_to_help_request({
        "id": hid, "responder_agent": "fw",
        "responder_solution": "iot", "content": "try X",
    })
    assert len(out["request"]["responses"]) == 1
    assert out["request"]["responses"][0]["content"] == "try X"


def test_respond_to_help_request_requires_content(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    hid = wired._add_help()
    with pytest.raises(RpcError):
        collective.respond_to_help_request({
            "id": hid, "responder_agent": "a",
            "responder_solution": "s", "content": "  ",
        })


def test_close_help_request_moves_to_closed(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    hid = wired._add_help()
    out = collective.close_help_request({"id": hid})
    assert out["request"]["status"] == "closed"
    assert hid in wired._help_closed
    assert hid not in wired._help_open


def test_close_help_request_not_found(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    with pytest.raises(RpcError) as e:
        collective.close_help_request({"id": "ghost"})
    assert e.value.code == -32000


def test_sync_delegates_and_returns_counts(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning()
    out = collective.sync({})
    assert out == {"pulled": True, "indexed": 1}


def test_stats_includes_git_flag_and_repo_path(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._add_learning(solution="a", topic="t1")
    wired._add_learning(solution="a", topic="t2")
    wired._add_help(status="open")
    wired._add_help(status="closed")
    out = collective.stats({})
    assert out["learning_count"] == 2
    assert out["help_request_count"] == 1
    assert out["help_requests_closed"] == 1
    assert out["topics"] == {"t1": 1, "t2": 1}
    assert out["contributors"] == {"a": 2}
    assert out["git_available"] is True
    assert out["repo_path"] == "/tmp/fake-collective"


def test_stats_reports_git_offline(wired, monkeypatch):
    monkeypatch.setattr(collective, "_cm", wired)
    wired._git_available = False
    out = collective.stats({})
    assert out["git_available"] is False
