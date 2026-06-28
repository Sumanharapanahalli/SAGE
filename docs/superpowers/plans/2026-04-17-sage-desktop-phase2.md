# SAGE Desktop Phase 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship three new vertical slices in `sage-desktop/` — LLM provider switch, feature request submission, and queue/monitor status — reusing existing `src/core/*` modules over the existing NDJSON JSON-RPC pipe. No HTTP, no new infra.

**Architecture:** Extract `FeatureRequestStore` out of `src/interface/api.py` so the sidecar can reuse the exact SQLite schema. Add three sidecar handlers (`llm`, `backlog`, `queue`), three Rust command modules, three React hook modules, two new pages, and one Status tile. Every slice ships with tests at each layer.

**Tech Stack:** Python 3.12 (sidecar), Rust (Tauri 2.x), TypeScript/React 18, vitest, pytest, cargo test.

---

## Task 1: Extract `FeatureRequestStore` from api.py

**Files:**
- Create: `src/core/feature_request_store.py`
- Create: `tests/test_feature_request_store.py`
- Modify: `src/interface/api.py` (replace inline SQL with store methods)

- [ ] **Step 1: Write failing tests for schema initialisation**

```python
# tests/test_feature_request_store.py
import sqlite3
import tempfile
from pathlib import Path

import pytest
from src.core.feature_request_store import FeatureRequestStore


@pytest.fixture
def store(tmp_path: Path) -> FeatureRequestStore:
    s = FeatureRequestStore(str(tmp_path / "fr.db"))
    s.init_schema()
    return s


def test_init_schema_creates_feature_requests_table(store: FeatureRequestStore):
    with sqlite3.connect(store.db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='feature_requests'"
        ).fetchone()
    assert row is not None


def test_init_schema_is_idempotent(store: FeatureRequestStore):
    store.init_schema()  # second call must not raise
    store.init_schema()
```

- [ ] **Step 2: Run tests — expect import error**

Run: `.venv/Scripts/pytest tests/test_feature_request_store.py -v`
Expected: FAIL with "No module named 'src.core.feature_request_store'"

- [ ] **Step 3: Create the minimum module to pass the first two tests**

```python
# src/core/feature_request_store.py
"""SQLite-backed feature request store (Solution + SAGE scoped backlogs).

Extracted from src/interface/api.py so the desktop sidecar can reuse the
exact same schema without importing FastAPI. The schema and column names
are preserved verbatim — existing rows continue to load.
"""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FeatureRequest:
    id: str
    module_id: str
    module_name: str
    title: str
    description: str
    priority: str
    status: str
    requested_by: str
    scope: str
    created_at: str
    updated_at: str
    reviewer_note: str
    plan_trace_id: str

    def to_dict(self) -> dict:
        return asdict(self)


class FeatureRequestStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feature_requests (
                    id           TEXT PRIMARY KEY,
                    module_id    TEXT NOT NULL,
                    module_name  TEXT NOT NULL,
                    title        TEXT NOT NULL,
                    description  TEXT NOT NULL,
                    priority     TEXT DEFAULT 'medium',
                    status       TEXT DEFAULT 'pending',
                    requested_by TEXT DEFAULT 'anonymous',
                    scope        TEXT DEFAULT 'solution',
                    created_at   TEXT,
                    updated_at   TEXT,
                    reviewer_note TEXT,
                    plan_trace_id TEXT
                )
                """
            )
            try:
                conn.execute(
                    "ALTER TABLE feature_requests ADD COLUMN scope TEXT DEFAULT 'solution'"
                )
            except sqlite3.OperationalError:
                pass  # column already exists
            conn.commit()
```

- [ ] **Step 4: Run tests — expect pass**

Run: `.venv/Scripts/pytest tests/test_feature_request_store.py -v`
Expected: PASS (2/2)

- [ ] **Step 5: Write failing tests for `submit`, `list`, `get`, `update`**

```python
# append to tests/test_feature_request_store.py
def test_submit_assigns_uuid_and_defaults(store: FeatureRequestStore):
    fr = store.submit(
        title="Add dark mode",
        description="Users want a dark theme",
    )
    assert len(fr.id) == 36  # uuid4
    assert fr.priority == "medium"
    assert fr.scope == "solution"
    assert fr.status == "pending"
    assert fr.requested_by == "anonymous"


def test_submit_rejects_empty_title(store: FeatureRequestStore):
    with pytest.raises(ValueError, match="title"):
        store.submit(title="", description="body")


def test_submit_rejects_invalid_priority(store: FeatureRequestStore):
    with pytest.raises(ValueError, match="priority"):
        store.submit(title="x", description="y", priority="urgent")


def test_submit_rejects_invalid_scope(store: FeatureRequestStore):
    with pytest.raises(ValueError, match="scope"):
        store.submit(title="x", description="y", scope="global")


def test_list_returns_all_by_default(store: FeatureRequestStore):
    store.submit(title="a", description="a")
    store.submit(title="b", description="b", scope="sage")
    rows = store.list()
    assert len(rows) == 2


def test_list_filters_by_scope(store: FeatureRequestStore):
    store.submit(title="a", description="a")
    store.submit(title="b", description="b", scope="sage")
    assert len(store.list(scope="sage")) == 1
    assert len(store.list(scope="solution")) == 1


def test_list_filters_by_status(store: FeatureRequestStore):
    store.submit(title="a", description="a")
    assert len(store.list(status="pending")) == 1
    assert len(store.list(status="approved")) == 0


def test_get_returns_none_for_unknown_id(store: FeatureRequestStore):
    assert store.get("nope") is None


def test_get_returns_submitted_row(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    fetched = store.get(fr.id)
    assert fetched is not None
    assert fetched.id == fr.id


def test_update_approve_sets_status(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    updated = store.update(fr.id, action="approve", reviewer_note="looks good")
    assert updated.status == "approved"
    assert updated.reviewer_note == "looks good"


def test_update_reject_sets_status(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    updated = store.update(fr.id, action="reject")
    assert updated.status == "rejected"


def test_update_complete_sets_status(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    updated = store.update(fr.id, action="complete")
    assert updated.status == "completed"


def test_update_raises_keyerror_for_unknown_id(store: FeatureRequestStore):
    with pytest.raises(KeyError):
        store.update("nope", action="approve")


def test_update_raises_valueerror_for_unknown_action(store: FeatureRequestStore):
    fr = store.submit(title="t", description="d")
    with pytest.raises(ValueError, match="action"):
        store.update(fr.id, action="zap")
```

- [ ] **Step 6: Run tests — expect fails on missing methods**

Run: `.venv/Scripts/pytest tests/test_feature_request_store.py -v`
Expected: FAIL on each new test (AttributeError: 'FeatureRequestStore' object has no attribute 'submit').

- [ ] **Step 7: Implement the methods**

```python
# append to src/core/feature_request_store.py
    _VALID_PRIORITIES = {"low", "medium", "high", "critical"}
    _VALID_SCOPES = {"solution", "sage"}
    _VALID_ACTIONS = {"approve": "approved", "reject": "rejected", "complete": "completed"}

    def submit(
        self,
        *,
        title: str,
        description: str,
        module_id: str = "general",
        module_name: str = "General",
        priority: str = "medium",
        requested_by: str = "anonymous",
        scope: str = "solution",
    ) -> FeatureRequest:
        if not title or not title.strip():
            raise ValueError("title must be non-empty")
        if priority not in self._VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {sorted(self._VALID_PRIORITIES)}"
            )
        if scope not in self._VALID_SCOPES:
            raise ValueError(f"scope must be one of {sorted(self._VALID_SCOPES)}")

        fr = FeatureRequest(
            id=str(uuid.uuid4()),
            module_id=module_id,
            module_name=module_name,
            title=title,
            description=description,
            priority=priority,
            status="pending",
            requested_by=requested_by,
            scope=scope,
            created_at=_now_iso(),
            updated_at=_now_iso(),
            reviewer_note="",
            plan_trace_id="",
        )
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO feature_requests
                  (id, module_id, module_name, title, description, priority,
                   status, requested_by, scope, created_at, updated_at,
                   reviewer_note, plan_trace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fr.id, fr.module_id, fr.module_name, fr.title, fr.description,
                    fr.priority, fr.status, fr.requested_by, fr.scope,
                    fr.created_at, fr.updated_at, fr.reviewer_note, fr.plan_trace_id,
                ),
            )
            conn.commit()
        return fr

    def list(
        self,
        *,
        status: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> List[FeatureRequest]:
        sql = "SELECT * FROM feature_requests WHERE 1=1"
        args: list = []
        if status:
            sql += " AND status=?"
            args.append(status)
        if scope:
            sql += " AND scope=?"
            args.append(scope)
        sql += " ORDER BY created_at DESC"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, args).fetchall()
        return [self._row_to_fr(r) for r in rows]

    def get(self, feature_id: str) -> Optional[FeatureRequest]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM feature_requests WHERE id=?", (feature_id,)
            ).fetchone()
        return self._row_to_fr(row) if row else None

    def update(
        self, feature_id: str, *, action: str, reviewer_note: str = ""
    ) -> FeatureRequest:
        if action not in self._VALID_ACTIONS:
            raise ValueError(
                f"action must be one of {sorted(self._VALID_ACTIONS.keys())}"
            )
        new_status = self._VALID_ACTIONS[action]
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE feature_requests
                   SET status=?, reviewer_note=?, updated_at=?
                 WHERE id=?
                """,
                (new_status, reviewer_note, _now_iso(), feature_id),
            )
            if cur.rowcount == 0:
                raise KeyError(feature_id)
            conn.commit()
        fetched = self.get(feature_id)
        assert fetched is not None  # we just updated it
        return fetched

    @staticmethod
    def _row_to_fr(row) -> FeatureRequest:
        return FeatureRequest(
            id=row["id"],
            module_id=row["module_id"],
            module_name=row["module_name"],
            title=row["title"],
            description=row["description"],
            priority=row["priority"] or "medium",
            status=row["status"] or "pending",
            requested_by=row["requested_by"] or "anonymous",
            scope=row["scope"] or "solution",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            reviewer_note=row["reviewer_note"] or "",
            plan_trace_id=row["plan_trace_id"] or "",
        )
```

- [ ] **Step 8: Run tests — expect all pass**

Run: `.venv/Scripts/pytest tests/test_feature_request_store.py -v`
Expected: PASS (14/14)

- [ ] **Step 9: Migrate api.py — identify all inline feature_request SQL**

Run: `rg -n 'feature_requests' src/interface/api.py`

Expected matches (all to be replaced by store calls):
- `_init_feature_requests_table()` at line ~427 → `FeatureRequestStore(db).init_schema()`
- `INSERT INTO feature_requests` in `submit_feature_request` ~1910
- `SELECT ... FROM feature_requests` in `list_feature_requests` ~1946+
- `UPDATE feature_requests` in the update endpoint + plan-trace link endpoint

- [ ] **Step 10: Refactor `src/interface/api.py` to use the store**

Replace `_init_feature_requests_table()`:

```python
def _init_feature_requests_table():
    from src.core.feature_request_store import FeatureRequestStore
    try:
        FeatureRequestStore(_get_db_path()).init_schema()
        logger.info("Feature requests table ready.")
    except Exception as exc:
        logger.error("Failed to initialise feature_requests table: %s", exc)
```

Replace the three endpoint handlers' inline SQL with calls to
`FeatureRequestStore(_get_db_path()).submit(...) / .list(...) / .update(...)`.
For the plan-trace-link endpoint (UPDATE with plan_trace_id column), keep
the inline SQL in api.py since that column is not part of the store's
minimum surface — flag as a follow-up.

- [ ] **Step 11: Run existing FastAPI feature request tests — expect pass**

Run: `.venv/Scripts/pytest tests/test_api.py -v -k feature_request`
Expected: PASS (no regressions).

- [ ] **Step 12: Run the full framework test suite**

Run: `.venv/Scripts/pytest tests/ -v`
Expected: All green; new FeatureRequestStore tests + all existing tests pass.

- [ ] **Step 13: Commit**

```bash
git add src/core/feature_request_store.py tests/test_feature_request_store.py src/interface/api.py
git commit -m "refactor(core): extract FeatureRequestStore for reuse by desktop sidecar"
```

---

## Task 2: Sidecar LLM handler

**Files:**
- Create: `sage-desktop/sidecar/handlers/llm.py`
- Create: `sage-desktop/sidecar/tests/test_llm.py`
- Modify: `sage-desktop/sidecar/app.py` (register two new methods)

- [ ] **Step 1: Write failing tests for `get_llm_info`**

```python
# sage-desktop/sidecar/tests/test_llm.py
from unittest.mock import MagicMock
import pytest

from handlers import llm
from rpc import RpcError


class FakeGateway:
    def __init__(self, provider="gemini", model="gemini-2.0-flash-001", cls_name="GeminiCLIProvider"):
        self._provider = provider
        self._model = model
        self._cls = cls_name

    def get_provider_name(self) -> str:
        return self._cls

    def list_providers(self) -> list[str]:
        return ["gemini", "claude-code", "ollama", "local", "claude", "generic-cli"]


@pytest.fixture(autouse=True)
def reset():
    llm._gateway = None
    yield
    llm._gateway = None


def test_get_llm_info_returns_shape(reset):
    fake = FakeGateway()
    llm._gateway = fake
    result = llm.get_llm_info({})
    assert result["provider_name"] == "GeminiCLIProvider"
    assert "claude-code" in result["available_providers"]


def test_get_llm_info_when_gateway_missing_raises_sage_import_error():
    with pytest.raises(RpcError) as exc:
        llm.get_llm_info({})
    assert exc.value.code == -32010  # RPC_SAGE_IMPORT_ERROR
```

- [ ] **Step 2: Run tests — expect import fail**

Run: `cd sage-desktop/sidecar && pytest tests/test_llm.py -v`
Expected: FAIL (No module named 'handlers.llm').

- [ ] **Step 3: Implement `get_llm_info`**

```python
# sage-desktop/sidecar/handlers/llm.py
"""LLM handler — current provider info and runtime switch."""
from __future__ import annotations

from typing import Optional

from rpc import RpcError, RPC_INVALID_PARAMS, RPC_SAGE_IMPORT_ERROR, RPC_SIDECAR_ERROR

_gateway = None  # module-level singleton — wired by app.py


def _require_gateway():
    if _gateway is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "LLM gateway unavailable",
            {"module": "src.core.llm_gateway", "detail": "not initialised"},
        )
    return _gateway


def _current_model(gw) -> str:
    # Best-effort — providers expose model names via different attributes.
    for attr in ("model", "model_name", "_model"):
        value = getattr(getattr(gw, "provider", None), attr, None)
        if isinstance(value, str) and value:
            return value
    return ""


def get_llm_info(_params: dict) -> dict:
    gw = _require_gateway()
    return {
        "provider_name": gw.get_provider_name(),
        "model": _current_model(gw),
        "available_providers": gw.list_providers(),
    }
```

- [ ] **Step 4: Run tests — expect 2/2 pass**

Run: `cd sage-desktop/sidecar && pytest tests/test_llm.py -v`
Expected: PASS (2/2).

- [ ] **Step 5: Write failing tests for `switch_llm`**

```python
# append to sage-desktop/sidecar/tests/test_llm.py
def test_switch_llm_rejects_empty_provider():
    llm._gateway = FakeGateway()
    with pytest.raises(RpcError) as exc:
        llm.switch_llm({"provider": ""})
    assert exc.value.code == -32602  # RPC_INVALID_PARAMS


def test_switch_llm_invokes_executor(monkeypatch):
    llm._gateway = FakeGateway()
    calls = []

    async def fake_execute(proposal):
        calls.append(proposal.payload)
        return {
            "provider": proposal.payload["provider"],
            "provider_name": "OllamaProvider",
            "saved_as_default": proposal.payload.get("save_as_default", False),
        }

    monkeypatch.setattr(llm, "_run_execute_llm_switch", fake_execute)
    result = llm.switch_llm(
        {"provider": "ollama", "model": "llama3.2", "save_as_default": True}
    )
    assert result["provider"] == "ollama"
    assert result["provider_name"] == "OllamaProvider"
    assert result["saved_as_default"] is True
    assert calls[0]["provider"] == "ollama"
    assert calls[0]["model"] == "llama3.2"


def test_switch_llm_wraps_executor_exception(monkeypatch):
    llm._gateway = FakeGateway()

    async def boom(proposal):
        raise RuntimeError("disk full")

    monkeypatch.setattr(llm, "_run_execute_llm_switch", boom)
    with pytest.raises(RpcError) as exc:
        llm.switch_llm({"provider": "ollama"})
    assert exc.value.code == -32000  # RPC_SIDECAR_ERROR
    assert "disk full" in exc.value.message
```

- [ ] **Step 6: Run tests — expect fails on missing `switch_llm`**

Run: `cd sage-desktop/sidecar && pytest tests/test_llm.py -v`
Expected: FAIL (3 new tests missing `switch_llm`).

- [ ] **Step 7: Implement `switch_llm`**

```python
# append to sage-desktop/sidecar/handlers/llm.py
import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class _SyntheticProposal:
    """Minimum shape for proposal_executor._execute_llm_switch."""
    payload: Dict[str, Any] = field(default_factory=dict)
    action_type: str = "llm_switch"
    trace_id: str = "desktop-switch"


async def _run_execute_llm_switch(proposal):
    from src.core.proposal_executor import _execute_llm_switch

    return await _execute_llm_switch(proposal)


def switch_llm(params: dict) -> dict:
    _require_gateway()
    provider = (params.get("provider") or "").strip()
    if not provider:
        raise RpcError(RPC_INVALID_PARAMS, "provider must be non-empty")

    proposal = _SyntheticProposal(
        payload={
            "provider": provider,
            "model": params.get("model"),
            "save_as_default": bool(params.get("save_as_default", False)),
            "claude_path": params.get("claude_path"),
        }
    )
    try:
        result = asyncio.run(_run_execute_llm_switch(proposal))
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"llm switch failed: {e}") from e
    return result
```

- [ ] **Step 8: Run tests — expect 5/5 pass**

Run: `cd sage-desktop/sidecar && pytest tests/test_llm.py -v`
Expected: PASS (5/5).

- [ ] **Step 9: Wire the handler into app.py**

Edit `sage-desktop/sidecar/app.py`:

Add to import line:
```python
from handlers import agents, approvals, audit, handshake, llm, status
```

Add to `_build_dispatcher`:
```python
    d.register("llm.get_info", llm.get_llm_info)
    d.register("llm.switch", llm.switch_llm)
```

Add to `_wire_handlers` inside the existing LLMGateway try block:
```python
    try:
        from src.core.llm_gateway import llm_gateway as lg
        status._llm = lg
        llm._gateway = lg
    except Exception as e:  # noqa: BLE001
        logging.warning("LLMGateway unavailable: %s", e)
```

- [ ] **Step 10: Run full sidecar test suite**

Run: `cd sage-desktop/sidecar && pytest tests/ -v`
Expected: 82 existing + 5 new = 87 passed.

- [ ] **Step 11: Commit**

```bash
git add sage-desktop/sidecar/handlers/llm.py sage-desktop/sidecar/tests/test_llm.py sage-desktop/sidecar/app.py
git commit -m "feat(sidecar): llm.get_info + llm.switch handlers"
```

---

## Task 3: Sidecar Backlog handler

**Files:**
- Create: `sage-desktop/sidecar/handlers/backlog.py`
- Create: `sage-desktop/sidecar/tests/test_backlog.py`
- Modify: `sage-desktop/sidecar/app.py` (register three new methods)

- [ ] **Step 1: Write failing tests**

```python
# sage-desktop/sidecar/tests/test_backlog.py
from pathlib import Path

import pytest

from handlers import backlog
from rpc import RpcError


@pytest.fixture
def store(tmp_path: Path):
    from src.core.feature_request_store import FeatureRequestStore

    s = FeatureRequestStore(str(tmp_path / "fr.db"))
    s.init_schema()
    return s


@pytest.fixture(autouse=True)
def inject(store):
    backlog._store = store
    yield
    backlog._store = None


def test_submit_feature_request_returns_row():
    result = backlog.submit_feature_request({
        "title": "Add dark mode",
        "description": "Users want a dark theme",
        "scope": "solution",
    })
    assert result["title"] == "Add dark mode"
    assert result["scope"] == "solution"
    assert result["status"] == "pending"
    assert len(result["id"]) == 36


def test_submit_feature_request_missing_title_raises_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.submit_feature_request({"description": "no title"})
    assert exc.value.code == -32602


def test_submit_feature_request_invalid_priority_maps_to_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.submit_feature_request(
            {"title": "t", "description": "d", "priority": "urgent"}
        )
    assert exc.value.code == -32602


def test_list_feature_requests_returns_newest_first():
    backlog.submit_feature_request({"title": "a", "description": "a"})
    backlog.submit_feature_request({"title": "b", "description": "b", "scope": "sage"})
    result = backlog.list_feature_requests({})
    assert isinstance(result, list)
    assert len(result) == 2


def test_list_feature_requests_filters_by_scope():
    backlog.submit_feature_request({"title": "a", "description": "a"})
    backlog.submit_feature_request({"title": "b", "description": "b", "scope": "sage"})
    assert len(backlog.list_feature_requests({"scope": "sage"})) == 1


def test_update_feature_request_approve_sets_status():
    created = backlog.submit_feature_request({"title": "t", "description": "d"})
    updated = backlog.update_feature_request(
        {"id": created["id"], "action": "approve", "reviewer_note": "lgtm"}
    )
    assert updated["status"] == "approved"
    assert updated["reviewer_note"] == "lgtm"


def test_update_feature_request_unknown_id_maps_to_not_found():
    with pytest.raises(RpcError) as exc:
        backlog.update_feature_request({"id": "nope", "action": "approve"})
    assert exc.value.code == -32020  # RPC_FEATURE_REQUEST_NOT_FOUND (new)


def test_update_feature_request_missing_id_is_invalid_params():
    with pytest.raises(RpcError) as exc:
        backlog.update_feature_request({"action": "approve"})
    assert exc.value.code == -32602


def test_store_unavailable_raises_sage_import_error():
    backlog._store = None
    with pytest.raises(RpcError) as exc:
        backlog.list_feature_requests({})
    assert exc.value.code == -32010
```

- [ ] **Step 2: Run tests — expect fails**

Run: `cd sage-desktop/sidecar && pytest tests/test_backlog.py -v`
Expected: FAIL (import error).

- [ ] **Step 3: Add the new error code to rpc.py**

Edit `sage-desktop/sidecar/rpc.py` — append to the SAGE codes block:

```python
RPC_FEATURE_REQUEST_NOT_FOUND = -32020
```

- [ ] **Step 4: Implement the handler**

```python
# sage-desktop/sidecar/handlers/backlog.py
"""Feature request (backlog) handlers."""
from __future__ import annotations

from typing import Any, Dict, Optional

from rpc import (
    RpcError,
    RPC_INVALID_PARAMS,
    RPC_SAGE_IMPORT_ERROR,
    RPC_FEATURE_REQUEST_NOT_FOUND,
)

_store = None  # wired by app.py


def _require_store():
    if _store is None:
        raise RpcError(
            RPC_SAGE_IMPORT_ERROR,
            "feature request store unavailable",
            {"module": "src.core.feature_request_store", "detail": "not initialised"},
        )
    return _store


def submit_feature_request(params: dict) -> dict:
    store = _require_store()
    title = params.get("title") or ""
    description = params.get("description") or ""
    kwargs: Dict[str, Any] = {
        "title": title,
        "description": description,
        "module_id": params.get("module_id", "general"),
        "module_name": params.get("module_name", "General"),
        "priority": params.get("priority", "medium"),
        "requested_by": params.get("requested_by", "anonymous"),
        "scope": params.get("scope", "solution"),
    }
    try:
        fr = store.submit(**kwargs)
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    return fr.to_dict()


def list_feature_requests(params: dict) -> list:
    store = _require_store()
    status: Optional[str] = params.get("status") or None
    scope: Optional[str] = params.get("scope") or None
    return [fr.to_dict() for fr in store.list(status=status, scope=scope)]


def update_feature_request(params: dict) -> dict:
    store = _require_store()
    fid = params.get("id")
    if not fid:
        raise RpcError(RPC_INVALID_PARAMS, "id required")
    action = params.get("action")
    if not action:
        raise RpcError(RPC_INVALID_PARAMS, "action required")
    note = params.get("reviewer_note", "")
    try:
        fr = store.update(fid, action=action, reviewer_note=note)
    except KeyError:
        raise RpcError(
            RPC_FEATURE_REQUEST_NOT_FOUND,
            f"feature request not found: {fid}",
            {"feature_id": fid},
        ) from None
    except ValueError as e:
        raise RpcError(RPC_INVALID_PARAMS, str(e)) from e
    return fr.to_dict()
```

- [ ] **Step 5: Run tests — expect 9/9 pass**

Run: `cd sage-desktop/sidecar && pytest tests/test_backlog.py -v`
Expected: PASS (9/9).

- [ ] **Step 6: Wire into app.py**

Add to imports:
```python
from handlers import agents, approvals, audit, backlog, handshake, llm, status
```

Add to `_build_dispatcher`:
```python
    d.register("backlog.list", backlog.list_feature_requests)
    d.register("backlog.submit", backlog.submit_feature_request)
    d.register("backlog.update", backlog.update_feature_request)
```

Add to `_wire_handlers` after AuditLogger block:
```python
    try:
        from src.core.feature_request_store import FeatureRequestStore

        fr_store = FeatureRequestStore(str(sage_dir / "audit_log.db"))
        fr_store.init_schema()
        backlog._store = fr_store
    except Exception as e:  # noqa: BLE001
        logging.warning("FeatureRequestStore unavailable: %s", e)
```

- [ ] **Step 7: Run full sidecar tests**

Run: `cd sage-desktop/sidecar && pytest tests/ -v`
Expected: 82 + 5 + 9 = 96 passed.

- [ ] **Step 8: Commit**

```bash
git add sage-desktop/sidecar/handlers/backlog.py sage-desktop/sidecar/tests/test_backlog.py sage-desktop/sidecar/rpc.py sage-desktop/sidecar/app.py
git commit -m "feat(sidecar): backlog.list/submit/update handlers"
```

---

## Task 4: Sidecar Queue handler

**Files:**
- Create: `sage-desktop/sidecar/handlers/queue.py`
- Create: `sage-desktop/sidecar/tests/test_queue.py`
- Modify: `sage-desktop/sidecar/app.py`

- [ ] **Step 1: Write failing tests**

```python
# sage-desktop/sidecar/tests/test_queue.py
from unittest.mock import MagicMock
import pytest

from handlers import queue
from rpc import RpcError


class FakeQueue:
    def __init__(self, tasks=None, parallel_enabled=True, max_workers=4):
        self._tasks = tasks or []
        self._config = MagicMock()
        self._config.parallel_enabled = parallel_enabled
        self._config.max_workers = max_workers

    def get_all_tasks(self):
        return self._tasks

    def get_pending_count(self):
        return sum(1 for t in self._tasks if t["status"] == "pending")


@pytest.fixture(autouse=True)
def reset():
    queue._queue = None
    yield
    queue._queue = None


def test_get_queue_status_counts_by_status():
    queue._queue = FakeQueue(tasks=[
        {"id": "1", "status": "pending", "task_type": "x"},
        {"id": "2", "status": "pending", "task_type": "x"},
        {"id": "3", "status": "in_progress", "task_type": "y"},
        {"id": "4", "status": "done", "task_type": "z"},
        {"id": "5", "status": "failed", "task_type": "z"},
    ])
    result = queue.get_queue_status({})
    assert result["pending"] == 2
    assert result["in_progress"] == 1
    assert result["done"] == 1
    assert result["failed"] == 1
    assert result["blocked"] == 0
    assert result["parallel_enabled"] is True
    assert result["max_workers"] == 4


def test_get_queue_status_when_unavailable_returns_zeros():
    queue._queue = None
    result = queue.get_queue_status({})
    assert result == {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
        "parallel_enabled": False,
        "max_workers": 0,
    }


def test_list_queue_tasks_applies_status_filter():
    queue._queue = FakeQueue(tasks=[
        {"id": "1", "status": "pending", "task_type": "x"},
        {"id": "2", "status": "done", "task_type": "y"},
    ])
    result = queue.list_queue_tasks({"status": "done"})
    assert len(result) == 1
    assert result[0]["id"] == "2"


def test_list_queue_tasks_limits_results():
    queue._queue = FakeQueue(tasks=[
        {"id": str(i), "status": "done", "task_type": "x"} for i in range(100)
    ])
    result = queue.list_queue_tasks({"limit": 10})
    assert len(result) == 10


def test_list_queue_tasks_when_unavailable_returns_empty():
    queue._queue = None
    assert queue.list_queue_tasks({}) == []


def test_list_queue_tasks_rejects_negative_limit():
    queue._queue = FakeQueue()
    with pytest.raises(RpcError) as exc:
        queue.list_queue_tasks({"limit": -1})
    assert exc.value.code == -32602
```

- [ ] **Step 2: Run tests — expect import fail**

Run: `cd sage-desktop/sidecar && pytest tests/test_queue.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# sage-desktop/sidecar/handlers/queue.py
"""Queue status handlers — read-only view into the task queue."""
from __future__ import annotations

from typing import Any, Dict, List

from rpc import RpcError, RPC_INVALID_PARAMS

_queue = None  # wired by app.py


def _empty_status() -> Dict[str, Any]:
    return {
        "pending": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
        "parallel_enabled": False,
        "max_workers": 0,
    }


def get_queue_status(_params: dict) -> Dict[str, Any]:
    if _queue is None:
        return _empty_status()
    tasks = _queue.get_all_tasks()
    status = _empty_status()
    for t in tasks:
        key = t.get("status")
        if key in status:
            status[key] += 1
    cfg = getattr(_queue, "_config", None)
    if cfg is not None:
        status["parallel_enabled"] = bool(getattr(cfg, "parallel_enabled", False))
        status["max_workers"] = int(getattr(cfg, "max_workers", 0))
    return status


def list_queue_tasks(params: dict) -> List[dict]:
    if _queue is None:
        return []
    limit = params.get("limit", 50)
    if not isinstance(limit, int) or limit < 0:
        raise RpcError(RPC_INVALID_PARAMS, "limit must be a non-negative integer")
    tasks = _queue.get_all_tasks()
    status_filter = params.get("status")
    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]
    return tasks[:limit]
```

- [ ] **Step 4: Run tests — expect 6/6 pass**

Run: `cd sage-desktop/sidecar && pytest tests/test_queue.py -v`
Expected: PASS (6/6).

- [ ] **Step 5: Wire into app.py**

Add to imports:
```python
from handlers import agents, approvals, audit, backlog, handshake, llm, queue, status
```

Add to dispatcher registration:
```python
    d.register("queue.get_status", queue.get_queue_status)
    d.register("queue.list_tasks", queue.list_queue_tasks)
```

Add to `_wire_handlers` inside a new try block:
```python
    try:
        from src.core.queue_manager import get_task_queue

        queue._queue = get_task_queue(solution_name)
    except Exception as e:  # noqa: BLE001
        logging.warning("TaskQueue unavailable: %s", e)
```

- [ ] **Step 6: Run full sidecar tests**

Run: `cd sage-desktop/sidecar && pytest tests/ -v`
Expected: 96 + 6 = 102 passed.

- [ ] **Step 7: Commit**

```bash
git add sage-desktop/sidecar/handlers/queue.py sage-desktop/sidecar/tests/test_queue.py sage-desktop/sidecar/app.py
git commit -m "feat(sidecar): queue.get_status + queue.list_tasks handlers"
```

---

## Task 5: Rust error + command wiring

**Files:**
- Modify: `sage-desktop/src-tauri/src/errors.rs` (new variants + codes)
- Create: `sage-desktop/src-tauri/src/commands/llm.rs`
- Create: `sage-desktop/src-tauri/src/commands/backlog.rs`
- Create: `sage-desktop/src-tauri/src/commands/queue.rs`
- Modify: `sage-desktop/src-tauri/src/commands/mod.rs`
- Modify: `sage-desktop/src-tauri/src/lib.rs` (register handlers)

- [ ] **Step 1: Write failing Rust tests for new error variant**

Edit `sage-desktop/src-tauri/src/errors.rs`, append to the `#[cfg(test)]` block:

```rust
    #[test]
    fn feature_request_not_found_extracts_feature_id() {
        let err = DesktopError::from_rpc(
            RPC_FEATURE_REQUEST_NOT_FOUND,
            "feature request not found: abc".into(),
            Some(json!({"feature_id": "abc"})),
        );
        assert_eq!(
            err,
            DesktopError::FeatureRequestNotFound {
                feature_id: "abc".into()
            }
        );
    }
```

- [ ] **Step 2: Run the Rust tests — expect fail**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features feature_request_not_found`
Expected: FAIL (variant doesn't exist).

- [ ] **Step 3: Add the new variant + code**

Add above `DesktopError`:

```rust
pub const RPC_FEATURE_REQUEST_NOT_FOUND: i32 = -32020;
```

Add to the enum, between `SidecarDown` and `Other`:

```rust
    #[error("feature request not found: {feature_id}")]
    FeatureRequestNotFound { feature_id: String },
```

Add to `from_rpc` match arm, before `_ =>`:

```rust
            RPC_FEATURE_REQUEST_NOT_FOUND => DesktopError::FeatureRequestNotFound {
                feature_id: get_str("feature_id"),
            },
```

- [ ] **Step 4: Run Rust tests — expect 18/18 pass**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features`
Expected: PASS (17 existing + 1 new).

- [ ] **Step 5: Implement command modules**

```rust
// sage-desktop/src-tauri/src/commands/llm.rs
use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_llm_info(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("llm.get_info", json!({})).await
}

#[tauri::command]
pub async fn switch_llm(
    provider: String,
    model: Option<String>,
    save_as_default: Option<bool>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "llm.switch",
            json!({
                "provider": provider,
                "model": model,
                "save_as_default": save_as_default.unwrap_or(false),
            }),
        )
        .await
}
```

```rust
// sage-desktop/src-tauri/src/commands/backlog.rs
use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn list_feature_requests(
    status: Option<String>,
    scope: Option<String>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call("backlog.list", json!({"status": status, "scope": scope}))
        .await
}

#[tauri::command]
pub async fn submit_feature_request(
    title: String,
    description: String,
    priority: Option<String>,
    scope: Option<String>,
    requested_by: Option<String>,
    module_id: Option<String>,
    module_name: Option<String>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "backlog.submit",
            json!({
                "title": title,
                "description": description,
                "priority": priority.unwrap_or_else(|| "medium".into()),
                "scope": scope.unwrap_or_else(|| "solution".into()),
                "requested_by": requested_by.unwrap_or_else(|| "anonymous".into()),
                "module_id": module_id.unwrap_or_else(|| "general".into()),
                "module_name": module_name.unwrap_or_else(|| "General".into()),
            }),
        )
        .await
}

#[tauri::command]
pub async fn update_feature_request(
    id: String,
    action: String,
    reviewer_note: Option<String>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "backlog.update",
            json!({
                "id": id,
                "action": action,
                "reviewer_note": reviewer_note.unwrap_or_default(),
            }),
        )
        .await
}
```

```rust
// sage-desktop/src-tauri/src/commands/queue.rs
use serde_json::{json, Value};
use tauri::State;

use crate::errors::DesktopError;
use crate::sidecar::Sidecar;

#[tauri::command]
pub async fn get_queue_status(sidecar: State<'_, Sidecar>) -> Result<Value, DesktopError> {
    sidecar.call("queue.get_status", json!({})).await
}

#[tauri::command]
pub async fn list_queue_tasks(
    status: Option<String>,
    limit: Option<i64>,
    sidecar: State<'_, Sidecar>,
) -> Result<Value, DesktopError> {
    sidecar
        .call(
            "queue.list_tasks",
            json!({"status": status, "limit": limit.unwrap_or(50)}),
        )
        .await
}
```

- [ ] **Step 6: Register modules**

Edit `sage-desktop/src-tauri/src/commands/mod.rs`:
```rust
pub mod approvals;
pub mod audit;
pub mod agents;
pub mod status;
pub mod llm;
pub mod backlog;
pub mod queue;
```

- [ ] **Step 7: Register handlers in lib.rs**

Edit `sage-desktop/src-tauri/src/lib.rs` — in `desktop_app::run()`'s `tauri::generate_handler![...]` list, add:

```rust
            commands::llm::get_llm_info,
            commands::llm::switch_llm,
            commands::backlog::list_feature_requests,
            commands::backlog::submit_feature_request,
            commands::backlog::update_feature_request,
            commands::queue::get_queue_status,
            commands::queue::list_queue_tasks,
```

- [ ] **Step 8: Compile check + test run**

Run: `cd sage-desktop/src-tauri && cargo test --lib --no-default-features`
Expected: PASS (18/18), no compile errors.

- [ ] **Step 9: Commit**

```bash
git add sage-desktop/src-tauri/src/errors.rs sage-desktop/src-tauri/src/commands/
git commit -m "feat(desktop-rs): llm/backlog/queue command wrappers + FeatureRequestNotFound"
```

---

## Task 6: React types + client + hooks

**Files:**
- Modify: `sage-desktop/src/api/types.ts` (types + error variant)
- Modify: `sage-desktop/src/api/client.ts` (invoke wrappers)
- Create: `sage-desktop/src/hooks/useLlm.ts`
- Create: `sage-desktop/src/hooks/useBacklog.ts`
- Create: `sage-desktop/src/hooks/useQueue.ts`
- Create: `sage-desktop/src/__tests__/hooks/useLlm.test.ts`
- Create: `sage-desktop/src/__tests__/hooks/useBacklog.test.ts`
- Create: `sage-desktop/src/__tests__/hooks/useQueue.test.ts`

- [ ] **Step 1: Extend types.ts**

Append to `sage-desktop/src/api/types.ts`:

```ts
export interface LlmInfo {
  provider_name: string;
  model: string;
  available_providers: string[];
}

export interface LlmSwitchResult {
  provider: string;
  provider_name: string;
  saved_as_default: boolean;
}

export type FeatureRequestScope = "solution" | "sage";
export type FeatureRequestPriority = "low" | "medium" | "high" | "critical";
export type FeatureRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "completed"
  | "in_progress";

export interface FeatureRequest {
  id: string;
  module_id: string;
  module_name: string;
  title: string;
  description: string;
  priority: FeatureRequestPriority;
  status: FeatureRequestStatus;
  requested_by: string;
  scope: FeatureRequestScope;
  created_at: string;
  updated_at: string;
  reviewer_note: string;
  plan_trace_id: string;
}

export interface FeatureRequestSubmit {
  title: string;
  description: string;
  priority?: FeatureRequestPriority;
  scope?: FeatureRequestScope;
  module_id?: string;
  module_name?: string;
  requested_by?: string;
}

export type FeatureRequestAction = "approve" | "reject" | "complete";

export interface FeatureRequestUpdate {
  id: string;
  action: FeatureRequestAction;
  reviewer_note?: string;
}

export interface QueueStatus {
  pending: number;
  in_progress: number;
  done: number;
  failed: number;
  blocked: number;
  parallel_enabled: boolean;
  max_workers: number;
}

export interface QueueTask {
  id: string;
  task_type: string;
  status: string;
  priority?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
}
```

Extend the `DesktopError` tagged union with the new variant:

```ts
  | { kind: "FeatureRequestNotFound"; detail: { feature_id: string } }
```

- [ ] **Step 2: Extend client.ts**

Append to `sage-desktop/src/api/client.ts`:

```ts
export const getLlmInfo = () => invokeCommand<LlmInfo>("get_llm_info");

export const switchLlm = (req: {
  provider: string;
  model?: string;
  save_as_default?: boolean;
}) => invokeCommand<LlmSwitchResult>("switch_llm", req);

export const listFeatureRequests = (params: {
  status?: FeatureRequestStatus;
  scope?: FeatureRequestScope;
} = {}) => invokeCommand<FeatureRequest[]>("list_feature_requests", params);

export const submitFeatureRequest = (req: FeatureRequestSubmit) =>
  invokeCommand<FeatureRequest>("submit_feature_request", req);

export const updateFeatureRequest = (req: FeatureRequestUpdate) =>
  invokeCommand<FeatureRequest>("update_feature_request", req);

export const getQueueStatus = () => invokeCommand<QueueStatus>("get_queue_status");

export const listQueueTasks = (params: { status?: string; limit?: number } = {}) =>
  invokeCommand<QueueTask[]>("list_queue_tasks", params);
```

Also add the types to the import list at the top of `client.ts`.

- [ ] **Step 3: Write failing tests for useLlm**

```tsx
// sage-desktop/src/__tests__/hooks/useLlm.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useLlmInfo, useSwitchLlm } from "@/hooks/useLlm";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useLlmInfo", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches current provider info", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini", "claude-code"],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useLlmInfo(), { wrapper: wrapperWith(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.provider_name).toBe("GeminiCLIProvider");
  });
});

describe("useSwitchLlm", () => {
  beforeEach(() => vi.resetAllMocks());

  it("invokes switchLlm and invalidates llm cache", async () => {
    vi.mocked(client.switchLlm).mockResolvedValue({
      provider: "ollama",
      provider_name: "OllamaProvider",
      saved_as_default: true,
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useSwitchLlm(), { wrapper: wrapperWith(qc) });
    result.current.mutate({ provider: "ollama", model: "llama3.2", save_as_default: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["llm"] });
  });
});
```

- [ ] **Step 4: Run tests — expect fail**

Run: `cd sage-desktop && npx vitest run src/__tests__/hooks/useLlm.test.ts`
Expected: FAIL (hook not implemented).

- [ ] **Step 5: Implement useLlm**

```tsx
// sage-desktop/src/hooks/useLlm.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";

export const useLlmInfo = () =>
  useQuery({
    queryKey: ["llm", "info"],
    queryFn: client.getLlmInfo,
  });

export const useSwitchLlm = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: { provider: string; model?: string; save_as_default?: boolean }) =>
      client.switchLlm(req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["llm"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
  });
};
```

- [ ] **Step 6: Run tests — expect pass**

Run: `cd sage-desktop && npx vitest run src/__tests__/hooks/useLlm.test.ts`
Expected: PASS (2/2).

- [ ] **Step 7: Write failing tests for useBacklog**

```tsx
// sage-desktop/src/__tests__/hooks/useBacklog.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useFeatureRequests,
  useSubmitFeatureRequest,
  useUpdateFeatureRequest,
} from "@/hooks/useBacklog";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useFeatureRequests", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists feature requests with filters", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([]);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useFeatureRequests({ scope: "solution" }), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listFeatureRequests).toHaveBeenCalledWith({ scope: "solution" });
  });
});

describe("useSubmitFeatureRequest", () => {
  beforeEach(() => vi.resetAllMocks());

  it("submits and invalidates backlog cache", async () => {
    vi.mocked(client.submitFeatureRequest).mockResolvedValue({
      id: "abc", title: "t", description: "d", status: "pending",
      priority: "medium", scope: "solution", module_id: "general",
      module_name: "General", requested_by: "anon", created_at: "",
      updated_at: "", reviewer_note: "", plan_trace_id: "",
    } as any);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useSubmitFeatureRequest(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ title: "t", description: "d" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["backlog"] });
  });
});

describe("useUpdateFeatureRequest", () => {
  beforeEach(() => vi.resetAllMocks());

  it("updates and invalidates backlog cache", async () => {
    vi.mocked(client.updateFeatureRequest).mockResolvedValue({
      id: "abc", status: "approved",
    } as any);
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useUpdateFeatureRequest(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ id: "abc", action: "approve" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["backlog"] });
  });
});
```

- [ ] **Step 8: Run tests — expect fail**

Run: `cd sage-desktop && npx vitest run src/__tests__/hooks/useBacklog.test.ts`
Expected: FAIL (hook missing).

- [ ] **Step 9: Implement useBacklog**

```tsx
// sage-desktop/src/hooks/useBacklog.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  FeatureRequestScope,
  FeatureRequestStatus,
  FeatureRequestSubmit,
  FeatureRequestUpdate,
} from "@/api/types";

export const useFeatureRequests = (
  params: { status?: FeatureRequestStatus; scope?: FeatureRequestScope } = {},
) =>
  useQuery({
    queryKey: ["backlog", params.status ?? "all", params.scope ?? "all"],
    queryFn: () => client.listFeatureRequests(params),
  });

export const useSubmitFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: FeatureRequestSubmit) => client.submitFeatureRequest(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backlog"] }),
  });
};

export const useUpdateFeatureRequest = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: FeatureRequestUpdate) => client.updateFeatureRequest(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["backlog"] }),
  });
};
```

- [ ] **Step 10: Run tests — expect pass**

Run: `cd sage-desktop && npx vitest run src/__tests__/hooks/useBacklog.test.ts`
Expected: PASS (3/3).

- [ ] **Step 11: Write failing tests for useQueue**

```tsx
// sage-desktop/src/__tests__/hooks/useQueue.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useQueueStatus, useQueueTasks } from "@/hooks/useQueue";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useQueueStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches queue status counts", async () => {
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 2, in_progress: 1, done: 3, failed: 0, blocked: 0,
      parallel_enabled: true, max_workers: 4,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useQueueStatus(), { wrapper: wrapperWith(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pending).toBe(2);
  });
});

describe("useQueueTasks", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists queue tasks with filters", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([]);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useQueueTasks({ status: "pending" }), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listQueueTasks).toHaveBeenCalledWith({ status: "pending" });
  });
});
```

- [ ] **Step 12: Implement useQueue**

```tsx
// sage-desktop/src/hooks/useQueue.ts
import { useQuery } from "@tanstack/react-query";
import * as client from "@/api/client";

export const useQueueStatus = () =>
  useQuery({
    queryKey: ["queue", "status"],
    queryFn: client.getQueueStatus,
    refetchInterval: 5000,
  });

export const useQueueTasks = (params: { status?: string; limit?: number } = {}) =>
  useQuery({
    queryKey: ["queue", "tasks", params.status ?? "all", params.limit ?? 50],
    queryFn: () => client.listQueueTasks(params),
  });
```

- [ ] **Step 13: Run all new hook tests**

Run: `cd sage-desktop && npx vitest run src/__tests__/hooks/useLlm.test.ts src/__tests__/hooks/useBacklog.test.ts src/__tests__/hooks/useQueue.test.ts`
Expected: PASS (7/7).

- [ ] **Step 14: Commit**

```bash
git add sage-desktop/src/api/ sage-desktop/src/hooks/ sage-desktop/src/__tests__/hooks/useLlm.test.ts sage-desktop/src/__tests__/hooks/useBacklog.test.ts sage-desktop/src/__tests__/hooks/useQueue.test.ts
git commit -m "feat(desktop-web): llm/backlog/queue hooks + api client"
```

---

## Task 7: Settings page (LLM switcher)

**Files:**
- Create: `sage-desktop/src/components/domain/LlmProviderForm.tsx`
- Create: `sage-desktop/src/pages/Settings.tsx`
- Create: `sage-desktop/src/__tests__/components/LlmProviderForm.test.tsx`
- Create: `sage-desktop/src/__tests__/pages/Settings.test.tsx`

- [ ] **Step 1: Write failing test for LlmProviderForm**

```tsx
// sage-desktop/src/__tests__/components/LlmProviderForm.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LlmProviderForm } from "@/components/domain/LlmProviderForm";

describe("LlmProviderForm", () => {
  it("submits chosen provider + model", async () => {
    const onSubmit = vi.fn();
    render(
      <LlmProviderForm
        current={{ provider_name: "GeminiCLIProvider", model: "gemini-2.0-flash-001", available_providers: ["gemini", "ollama"] }}
        onSubmit={onSubmit}
        isPending={false}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText(/provider/i), "ollama");
    await userEvent.clear(screen.getByLabelText(/model/i));
    await userEvent.type(screen.getByLabelText(/model/i), "llama3.2");
    await userEvent.click(screen.getByRole("checkbox", { name: /save as default/i }));
    await userEvent.click(screen.getByRole("button", { name: /apply/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      provider: "ollama",
      model: "llama3.2",
      save_as_default: true,
    });
  });

  it("disables submit while pending", () => {
    render(
      <LlmProviderForm
        current={{ provider_name: "X", model: "m", available_providers: ["gemini"] }}
        onSubmit={() => {}}
        isPending={true}
      />,
    );
    expect(screen.getByRole("button", { name: /applying/i })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test — expect fail**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/LlmProviderForm.test.tsx`
Expected: FAIL (component missing).

- [ ] **Step 3: Implement LlmProviderForm**

```tsx
// sage-desktop/src/components/domain/LlmProviderForm.tsx
import { useState } from "react";
import type { LlmInfo } from "@/api/types";

interface Props {
  current: LlmInfo;
  onSubmit: (req: { provider: string; model: string; save_as_default: boolean }) => void;
  isPending: boolean;
}

export function LlmProviderForm({ current, onSubmit, isPending }: Props) {
  const providers = current.available_providers.length > 0
    ? current.available_providers
    : [current.provider_name];
  const [provider, setProvider] = useState(providers[0]);
  const [model, setModel] = useState(current.model);
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ provider, model, save_as_default: saveAsDefault });
      }}
    >
      <label className="block">
        <span className="block text-sm font-medium">Provider</span>
        <select
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {providers.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="block text-sm font-medium">Model</span>
        <input
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={saveAsDefault}
          onChange={(e) => setSaveAsDefault(e.target.checked)}
        />
        <span className="text-sm">Save as default</span>
      </label>
      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-sage-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {isPending ? "Applying…" : "Apply"}
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Run tests — expect 2/2 pass**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/LlmProviderForm.test.tsx`
Expected: PASS.

- [ ] **Step 5: Write failing test for Settings page**

```tsx
// sage-desktop/src/__tests__/pages/Settings.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Settings from "@/pages/Settings";

vi.mock("@/api/client");

describe("Settings page", () => {
  it("renders current provider info", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini", "ollama"],
    });
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Settings />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/GeminiCLIProvider/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 6: Implement Settings page**

```tsx
// sage-desktop/src/pages/Settings.tsx
import { useLlmInfo, useSwitchLlm } from "@/hooks/useLlm";
import { LlmProviderForm } from "@/components/domain/LlmProviderForm";

export default function Settings() {
  const info = useLlmInfo();
  const switcher = useSwitchLlm();

  if (info.isLoading) return <div className="p-6">Loading…</div>;
  if (info.isError) return <div className="p-6 text-red-700">Failed to load LLM info.</div>;
  const current = info.data!;

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <section className="rounded border border-gray-200 p-4">
        <h2 className="mb-2 font-semibold">Current LLM</h2>
        <p className="text-sm">Provider: <span className="font-mono">{current.provider_name}</span></p>
        <p className="text-sm">Model: <span className="font-mono">{current.model || "(default)"}</span></p>
      </section>
      <section className="rounded border border-gray-200 p-4">
        <h2 className="mb-4 font-semibold">Switch LLM</h2>
        <LlmProviderForm
          current={current}
          isPending={switcher.isPending}
          onSubmit={(req) => switcher.mutate(req)}
        />
        {switcher.isSuccess && (
          <p className="mt-2 text-sm text-green-700">
            Switched to {switcher.data.provider_name}
            {switcher.data.saved_as_default ? " (saved as default)" : ""}.
          </p>
        )}
        {switcher.isError && (
          <p className="mt-2 text-sm text-red-700">Switch failed.</p>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 7: Run page test — expect pass**

Run: `cd sage-desktop && npx vitest run src/__tests__/pages/Settings.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add sage-desktop/src/components/domain/LlmProviderForm.tsx sage-desktop/src/pages/Settings.tsx sage-desktop/src/__tests__/components/LlmProviderForm.test.tsx sage-desktop/src/__tests__/pages/Settings.test.tsx
git commit -m "feat(desktop-web): Settings page with LLM switcher"
```

---

## Task 8: Backlog page

**Files:**
- Create: `sage-desktop/src/components/domain/FeatureRequestRow.tsx`
- Create: `sage-desktop/src/pages/Backlog.tsx`
- Create: `sage-desktop/src/__tests__/components/FeatureRequestRow.test.tsx`
- Create: `sage-desktop/src/__tests__/pages/Backlog.test.tsx`

- [ ] **Step 1: Write failing tests for FeatureRequestRow**

```tsx
// sage-desktop/src/__tests__/components/FeatureRequestRow.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeatureRequestRow } from "@/components/domain/FeatureRequestRow";
import type { FeatureRequest } from "@/api/types";

const fr: FeatureRequest = {
  id: "abc",
  module_id: "general",
  module_name: "General",
  title: "Add dark mode",
  description: "Users want it",
  priority: "high",
  status: "pending",
  requested_by: "alice",
  scope: "solution",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  reviewer_note: "",
  plan_trace_id: "",
};

describe("FeatureRequestRow", () => {
  it("renders title, priority and status", () => {
    render(<FeatureRequestRow item={fr} onAction={() => {}} isPending={false} />);
    expect(screen.getByText("Add dark mode")).toBeInTheDocument();
    expect(screen.getByText(/high/i)).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });

  it("emits approve action with id", async () => {
    const onAction = vi.fn();
    render(<FeatureRequestRow item={fr} onAction={onAction} isPending={false} />);
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onAction).toHaveBeenCalledWith("abc", "approve");
  });

  it("hides action buttons when not pending", () => {
    const approved: FeatureRequest = { ...fr, status: "approved" };
    render(<FeatureRequestRow item={approved} onAction={() => {}} isPending={false} />);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement FeatureRequestRow**

```tsx
// sage-desktop/src/components/domain/FeatureRequestRow.tsx
import type { FeatureRequest, FeatureRequestAction } from "@/api/types";

const PRIORITY_STYLES: Record<FeatureRequest["priority"], string> = {
  low: "bg-gray-100 text-gray-800",
  medium: "bg-blue-100 text-blue-800",
  high: "bg-amber-100 text-amber-800",
  critical: "bg-red-100 text-red-800",
};

const STATUS_STYLES: Record<FeatureRequest["status"], string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-gray-100 text-gray-800",
  completed: "bg-emerald-100 text-emerald-800",
  in_progress: "bg-indigo-100 text-indigo-800",
};

interface Props {
  item: FeatureRequest;
  onAction: (id: string, action: FeatureRequestAction) => void;
  isPending: boolean;
}

export function FeatureRequestRow({ item, onAction, isPending }: Props) {
  return (
    <article className="rounded border border-gray-200 p-4">
      <header className="flex items-center justify-between">
        <h3 className="font-semibold">{item.title}</h3>
        <div className="flex gap-2 text-xs">
          <span className={`rounded px-2 py-0.5 ${PRIORITY_STYLES[item.priority]}`}>
            {item.priority}
          </span>
          <span className={`rounded px-2 py-0.5 ${STATUS_STYLES[item.status]}`}>
            {item.status}
          </span>
        </div>
      </header>
      <p className="mt-2 text-sm text-gray-700">{item.description}</p>
      <p className="mt-2 text-xs text-gray-500">
        by {item.requested_by} · {item.scope}
      </p>
      {item.status === "pending" && (
        <div className="mt-3 flex gap-2">
          <button
            disabled={isPending}
            onClick={() => onAction(item.id, "approve")}
            className="rounded bg-green-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            Approve
          </button>
          <button
            disabled={isPending}
            onClick={() => onAction(item.id, "reject")}
            className="rounded bg-gray-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            Reject
          </button>
          <button
            disabled={isPending}
            onClick={() => onAction(item.id, "complete")}
            className="rounded bg-emerald-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            Complete
          </button>
        </div>
      )}
    </article>
  );
}
```

- [ ] **Step 3: Write failing tests for Backlog page**

```tsx
// sage-desktop/src/__tests__/pages/Backlog.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Backlog from "@/pages/Backlog";

vi.mock("@/api/client");

describe("Backlog page", () => {
  it("renders feature request list", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([{
      id: "1", title: "Dark mode", description: "",
      priority: "medium", status: "pending", scope: "solution",
      module_id: "general", module_name: "General", requested_by: "a",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "",
    }] as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Dark mode")).toBeInTheDocument());
  });

  it("submits a new feature request", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([]);
    vi.mocked(client.submitFeatureRequest).mockResolvedValue({
      id: "new", title: "new item", description: "body",
      priority: "medium", status: "pending", scope: "solution",
      module_id: "general", module_name: "General", requested_by: "anonymous",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "",
    } as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByLabelText(/title/i), "new item");
    await userEvent.type(screen.getByLabelText(/description/i), "body");
    await userEvent.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() =>
      expect(client.submitFeatureRequest).toHaveBeenCalledWith(
        expect.objectContaining({ title: "new item", description: "body" }),
      ),
    );
  });
});
```

- [ ] **Step 4: Implement Backlog page**

```tsx
// sage-desktop/src/pages/Backlog.tsx
import { useState } from "react";
import {
  useFeatureRequests,
  useSubmitFeatureRequest,
  useUpdateFeatureRequest,
} from "@/hooks/useBacklog";
import { FeatureRequestRow } from "@/components/domain/FeatureRequestRow";
import type { FeatureRequestAction, FeatureRequestScope } from "@/api/types";

export default function Backlog() {
  const [scope, setScope] = useState<FeatureRequestScope>("solution");
  const list = useFeatureRequests({ scope });
  const submit = useSubmitFeatureRequest();
  const update = useUpdateFeatureRequest();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const handleAction = (id: string, action: FeatureRequestAction) => {
    update.mutate({ id, action });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    submit.mutate(
      { title, description, scope },
      {
        onSuccess: () => {
          setTitle("");
          setDescription("");
        },
      },
    );
  };

  return (
    <div className="p-6">
      <div className="mb-4 flex gap-2">
        {(["solution", "sage"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`rounded px-3 py-1 text-sm ${
              scope === s ? "bg-sage-600 text-white" : "bg-gray-100"
            }`}
          >
            {s === "solution" ? "Solution backlog" : "SAGE framework"}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="mb-6 space-y-3 rounded border border-gray-200 p-4">
        <h2 className="font-semibold">Submit request</h2>
        <label className="block">
          <span className="block text-sm font-medium">Title</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Description</span>
          <textarea
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <button
          type="submit"
          disabled={submit.isPending}
          className="rounded bg-sage-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {submit.isPending ? "Submitting…" : "Submit"}
        </button>
      </form>

      <div className="space-y-3">
        {list.isLoading && <p>Loading…</p>}
        {list.isSuccess && list.data.length === 0 && (
          <p className="text-sm text-gray-500">No feature requests.</p>
        )}
        {list.data?.map((fr) => (
          <FeatureRequestRow
            key={fr.id}
            item={fr}
            onAction={handleAction}
            isPending={update.isPending}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run page + component tests**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/FeatureRequestRow.test.tsx src/__tests__/pages/Backlog.test.tsx`
Expected: PASS (5/5).

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src/components/domain/FeatureRequestRow.tsx sage-desktop/src/pages/Backlog.tsx sage-desktop/src/__tests__/components/FeatureRequestRow.test.tsx sage-desktop/src/__tests__/pages/Backlog.test.tsx
git commit -m "feat(desktop-web): Backlog page with submit + approve/reject"
```

---

## Task 9: QueueTile on Status page

**Files:**
- Create: `sage-desktop/src/components/domain/QueueTile.tsx`
- Modify: `sage-desktop/src/pages/Status.tsx`
- Create: `sage-desktop/src/__tests__/components/QueueTile.test.tsx`
- Modify: `sage-desktop/src/__tests__/pages/Status.test.tsx`

- [ ] **Step 1: Write failing test for QueueTile**

```tsx
// sage-desktop/src/__tests__/components/QueueTile.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueueTile } from "@/components/domain/QueueTile";

describe("QueueTile", () => {
  it("renders queue counts", () => {
    render(
      <QueueTile
        status={{
          pending: 3, in_progress: 1, done: 5, failed: 0, blocked: 0,
          parallel_enabled: true, max_workers: 4,
        }}
      />,
    );
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement**

```tsx
// sage-desktop/src/components/domain/QueueTile.tsx
import type { QueueStatus } from "@/api/types";

interface Props { status: QueueStatus; }

const CELLS: [keyof QueueStatus, string][] = [
  ["pending", "Pending"],
  ["in_progress", "In progress"],
  ["done", "Done"],
  ["failed", "Failed"],
  ["blocked", "Blocked"],
];

export function QueueTile({ status }: Props) {
  return (
    <section className="rounded border border-gray-200 p-4">
      <h3 className="mb-3 text-sm font-semibold">Task queue</h3>
      <dl className="grid grid-cols-5 gap-4 text-center">
        {CELLS.map(([key, label]) => (
          <div key={key}>
            <dt className="text-xs uppercase text-gray-500">{label}</dt>
            <dd className="text-2xl font-semibold">{status[key] as number}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-gray-500">
        {status.parallel_enabled
          ? `Parallel: max ${status.max_workers} workers`
          : "Parallel disabled"}
      </p>
    </section>
  );
}
```

- [ ] **Step 3: Modify Status page**

Open `sage-desktop/src/pages/Status.tsx`. Add import:

```tsx
import { useQueueStatus } from "@/hooks/useQueue";
import { QueueTile } from "@/components/domain/QueueTile";
```

Inside the component, add:

```tsx
const queue = useQueueStatus();
```

Append after existing tiles (inside the main container):

```tsx
{queue.isSuccess && <QueueTile status={queue.data} />}
```

- [ ] **Step 4: Update Status page test to stub queue call**

Open `sage-desktop/src/__tests__/pages/Status.test.tsx` and add to the existing `vi.mocked(client.getStatus)` setup inside both tests:

```tsx
vi.mocked(client.getQueueStatus).mockResolvedValue({
  pending: 0, in_progress: 0, done: 0, failed: 0, blocked: 0,
  parallel_enabled: false, max_workers: 0,
});
```

- [ ] **Step 5: Run tests — expect pass**

Run: `cd sage-desktop && npx vitest run src/__tests__/components/QueueTile.test.tsx src/__tests__/pages/Status.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sage-desktop/src/components/domain/QueueTile.tsx sage-desktop/src/pages/Status.tsx sage-desktop/src/__tests__/components/QueueTile.test.tsx sage-desktop/src/__tests__/pages/Status.test.tsx
git commit -m "feat(desktop-web): queue tile on Status page"
```

---

## Task 10: Routing + Sidebar entries

**Files:**
- Modify: `sage-desktop/src/App.tsx`
- Modify: `sage-desktop/src/components/layout/Sidebar.tsx`
- Modify: `sage-desktop/src/components/layout/Header.tsx`
- Modify: `sage-desktop/src/__tests__/App.test.tsx`

- [ ] **Step 1: Add routes**

Edit `sage-desktop/src/App.tsx` — inside the `<Routes>` block:

```tsx
<Route path="/settings" element={<Settings />} />
<Route path="/backlog" element={<Backlog />} />
```

Add imports at top:

```tsx
import Settings from "@/pages/Settings";
import Backlog from "@/pages/Backlog";
```

- [ ] **Step 2: Add Sidebar entries**

Edit `sage-desktop/src/components/layout/Sidebar.tsx`:

```tsx
const ITEMS = [
  { to: "/approvals", label: "Approvals" },
  { to: "/agents", label: "Agents" },
  { to: "/audit", label: "Audit" },
  { to: "/status", label: "Status" },
  { to: "/backlog", label: "Backlog" },
  { to: "/settings", label: "Settings" },
];
```

- [ ] **Step 3: Add titles in Header**

Edit `sage-desktop/src/components/layout/Header.tsx`'s `TITLE_MAP`:

```tsx
  "/settings": "Settings",
  "/backlog": "Backlog",
```

- [ ] **Step 4: Update App routing test**

Open `sage-desktop/src/__tests__/App.test.tsx` — add two cases:

```tsx
it("navigates to /settings", async () => {
  vi.mocked(client.getLlmInfo).mockResolvedValue({
    provider_name: "X", model: "y", available_providers: ["gemini"],
  });
  // render App at /settings ...
});
```

(Follow the existing pattern from other routing tests; mock the client
calls the page fires on mount.)

- [ ] **Step 5: Run full React suite**

Run: `cd sage-desktop && npm run test`
Expected: 50 existing + ~17 new = 67+ passing.

- [ ] **Step 6: typecheck + build**

Run: `cd sage-desktop && npm run typecheck && npm run build`
Expected: no type errors, vite build succeeds.

- [ ] **Step 7: Commit**

```bash
git add sage-desktop/src/App.tsx sage-desktop/src/components/layout/Sidebar.tsx sage-desktop/src/components/layout/Header.tsx sage-desktop/src/__tests__/App.test.tsx
git commit -m "feat(desktop-web): wire Settings + Backlog routes and sidebar entries"
```

---

## Task 11: E2E smoke + docs

**Files:**
- Modify: `sage-desktop/e2e/smoke.mjs` (add three new method round-trips)
- Modify: `.claude/docs/interfaces/desktop-gui.md`
- Modify: `CLAUDE.md`
- Modify: `.claude/docs/architecture.md`

- [ ] **Step 1: Extend smoke test**

Edit `sage-desktop/e2e/smoke.mjs`. After the existing `list_pending_approvals` request, add:

```js
send(proc, { jsonrpc: "2.0", id: "e2e-3", method: "llm.get_info", params: {} });
send(proc, { jsonrpc: "2.0", id: "e2e-4", method: "backlog.list", params: {} });
send(proc, { jsonrpc: "2.0", id: "e2e-5", method: "queue.get_status", params: {} });
```

Extend the `expected` object and the completion check accordingly — all five ids must be observed before resolving.

- [ ] **Step 2: Run e2e**

Run: `cd sage-desktop && npm run test:e2e`
Expected: "sage-desktop e2e smoke: OK" — all five round-trip.

- [ ] **Step 3: Update docs**

Edit `.claude/docs/interfaces/desktop-gui.md`. Append to the RPC contract table:

```
| `llm.get_info` | Current provider name, model, and list of available providers |
| `llm.switch` | Runtime provider/model swap (framework control — no HITL) |
| `backlog.list` | List solution or framework feature requests, filterable by status/scope |
| `backlog.submit` | Create a new feature request; validates priority + scope |
| `backlog.update` | Approve / reject / complete an existing request |
| `queue.get_status` | Pending / in-progress / done / failed / blocked counts + parallel config |
| `queue.list_tasks` | Paginated task list (≤50 by default), optional status filter |
```

Add a new subsection:

```
### Phase 2 methods

- Shares one SQLite file with the FastAPI Web UI (`/features/list` returns the same rows).
- LLM switch reuses `src/core/proposal_executor._execute_llm_switch` so CLI, Web UI, and
  desktop all land on the same runtime state.
- New error variant: `FeatureRequestNotFound { feature_id: string }` (RPC code `-32020`).
```

Edit `CLAUDE.md` — in "Quick Start Commands", add a desktop-related mention if missing (existing desktop block already lists commands). In the "Interfaces" section, add:

"Phase 2 ships Settings + Backlog pages and a queue tile on Status."

Edit `.claude/docs/architecture.md` — in the two-backlogs section note:

"sage-desktop submits solution feature requests directly to `.sage/audit_log.db` via `FeatureRequestStore` — no HTTP. The same rows appear in the FastAPI Web UI."

- [ ] **Step 4: Commit docs**

```bash
git add .claude/docs/interfaces/desktop-gui.md CLAUDE.md .claude/docs/architecture.md sage-desktop/e2e/smoke.mjs
git commit -m "docs(phase2): desktop RPC contract + architecture notes"
```

---

## Task 12: Full verification

- [ ] **Step 1: Python tests** — `.venv/Scripts/pytest tests/test_api.py tests/test_feature_request_store.py -v` → all green.
- [ ] **Step 2: Sidecar tests** — `cd sage-desktop/sidecar && pytest tests/ -v` → ≥ 102.
- [ ] **Step 3: Rust tests** — `cd sage-desktop/src-tauri && cargo test --lib --no-default-features` → ≥ 18.
- [ ] **Step 4: React tests** — `cd sage-desktop && npm run test` → ≥ 67.
- [ ] **Step 5: E2E smoke** — `cd sage-desktop && npm run test:e2e` → OK.
- [ ] **Step 6: Build** — `cd sage-desktop && npm run build` → succeeds.
- [ ] **Step 7: Check branch is clean** — `git status` → nothing to commit.

Acceptance when all seven steps succeed.
