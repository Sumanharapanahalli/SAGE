# SAGE Desktop Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Tauri + Rust + Python-sidecar desktop app at `sage-desktop/` that gives a SAGE operator the HITL approval workflow with zero listening sockets, zero open ports, zero admin — over JSON-RPC 2.0 on NDJSON stdin/stdout.

**Architecture:** Single Tauri `.exe` bundles a React webview, a Rust core, and a bundled Python interpreter. Python sidecar imports SAGE library modules directly (`src/core/proposal_store.py`, `src/memory/audit_logger.py`, `src/core/project_loader.py`, `src/core/llm_gateway.py`, agent classes). Rust and Python communicate over stdin/stdout NDJSON JSON-RPC 2.0. React talks to Rust through Tauri commands (never directly to Python). Shared state lives in the active solution's `.sage/` directory on disk — same files the FastAPI server uses, so decisions made in desktop are visible to web UI / CLI users and vice versa.

**Tech Stack:** Tauri 2.x (Rust), React 18 + TypeScript + Vite, Tailwind CSS, React Query (@tanstack/react-query), React Router 6, Python 3.12, pytest, cargo test, vitest + @testing-library/react, tauri-driver (E2E).

**Spec:** `docs/superpowers/specs/2026-04-16-sage-desktop-phase1-design.md` (commit `7ac2e7d`)

**Branch:** `feature/sage-desktop-phase1` off `main`

**Pages in Phase 1:** Approvals, Agents, Audit, Status. Evolution is Phase 1.5.

---

## File Structure

```
sage-desktop/
├── package.json                          # React/Vite + @tauri-apps/cli scripts
├── vite.config.ts                        # Vite config with Tailwind
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── vitest.config.ts
├── src/                                  # React
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── types.ts
│   │   ├── client.ts                     # invoke wrapper
│   │   ├── approvals.ts
│   │   ├── agents.ts
│   │   ├── audit.ts
│   │   └── status.ts
│   ├── hooks/
│   │   ├── useProposals.ts
│   │   ├── useAgents.ts
│   │   ├── useAudit.ts
│   │   └── useStatus.ts
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── OfflineBanner.tsx
│   │   │   └── ErrorBoundary.tsx
│   │   └── domain/
│   │       ├── ProposalCard.tsx
│   │       ├── RiskBadge.tsx
│   │       ├── ExpiryCountdown.tsx
│   │       └── StatusIndicator.tsx
│   ├── pages/
│   │   ├── Approvals.tsx
│   │   ├── Agents.tsx
│   │   ├── Audit.tsx
│   │   └── Status.tsx
│   └── __tests__/                        # vitest
│       ├── api/
│       ├── hooks/
│       ├── components/
│       └── integration/
├── src-tauri/                            # Rust
│   ├── Cargo.toml
│   ├── build.rs
│   ├── tauri.conf.json
│   ├── capabilities/default.json
│   ├── icons/                            # copied from web/src-tauri/icons/
│   └── src/
│       ├── main.rs
│       ├── lib.rs
│       ├── sidecar.rs
│       ├── rpc.rs
│       ├── errors.rs
│       └── commands/
│           ├── mod.rs
│           ├── approvals.rs
│           ├── agents.rs
│           ├── audit.rs
│           └── status.rs
├── sidecar/                              # Python
│   ├── pyproject.toml
│   ├── __main__.py
│   ├── rpc.py
│   ├── dispatcher.py
│   ├── errors.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── handshake.py
│   │   ├── approvals.py
│   │   ├── agents.py
│   │   ├── audit.py
│   │   └── status.py
│   └── tests/
│       ├── conftest.py
│       ├── test_rpc.py
│       ├── test_dispatcher.py
│       ├── test_handshake.py
│       ├── test_approvals.py
│       ├── test_agents.py
│       ├── test_audit.py
│       └── test_status.py
└── tests/
    ├── fixtures/
    │   ├── test-solution/
    │   │   ├── project.yaml
    │   │   ├── prompts.yaml
    │   │   └── tasks.yaml
    │   ├── rpc-contracts/              # shared by Rust + Python tests
    │   │   ├── handshake.json
    │   │   ├── approve.json
    │   │   ├── reject.json
    │   │   ├── list_pending.json
    │   │   ├── list_agents.json
    │   │   ├── query_audit.json
    │   │   └── get_status.json
    │   └── mock_sidecar.py            # used by Rust integration tests
    └── e2e/
        └── approval_smoke.spec.ts
```

---

## Task 0: Clean slate — delete scaffold, delete `my_rust_app/`

**Files:**
- Delete: `sage-desktop/` (entire existing mock-data scaffold)
- Delete: `my_rust_app/` (abandoned stub)
- Modify: nothing else

- [ ] **Step 1: Verify we're on the right branch**

```bash
git -C C:/System-Team-repos/SAGE branch --show-current
```

Expected: `feature/sage-desktop-phase1`

- [ ] **Step 2: Delete existing sage-desktop scaffold**

```bash
rm -rf C:/System-Team-repos/SAGE/sage-desktop
```

- [ ] **Step 3: Delete my_rust_app**

```bash
rm -rf C:/System-Team-repos/SAGE/my_rust_app
```

- [ ] **Step 4: Create new sage-desktop directory skeleton**

```bash
mkdir -p C:/System-Team-repos/SAGE/sage-desktop/{src-tauri/src/commands,src-tauri/capabilities,src-tauri/icons,sidecar/handlers,sidecar/tests,src/api,src/hooks,src/components/layout,src/components/domain,src/pages,src/__tests__/api,src/__tests__/hooks,src/__tests__/components,src/__tests__/integration,tests/fixtures/test-solution,tests/fixtures/rpc-contracts,tests/e2e}
```

- [ ] **Step 5: Commit**

```bash
cd C:/System-Team-repos/SAGE && \
git add -A sage-desktop my_rust_app && \
git commit -m "chore: remove sage-desktop mock scaffold and my_rust_app stub"
```

---

## Task 1: Python sidecar — RPC framing (NDJSON + JSON-RPC 2.0)

**Files:**
- Create: `sage-desktop/sidecar/rpc.py`
- Create: `sage-desktop/sidecar/tests/test_rpc.py`
- Create: `sage-desktop/sidecar/tests/conftest.py`
- Create: `sage-desktop/sidecar/pyproject.toml`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
# sage-desktop/sidecar/pyproject.toml
[project]
name = "sage-desktop-sidecar"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
pythonpath = [".", "../../"]  # makes "from src.core.X import Y" work in tests
```

- [ ] **Step 2: Create `conftest.py`**

```python
# sage-desktop/sidecar/tests/conftest.py
import sys
from pathlib import Path

# Ensure sidecar package and SAGE src/ are importable
SIDECAR_ROOT = Path(__file__).parent.parent
SAGE_ROOT = SIDECAR_ROOT.parent.parent
sys.path.insert(0, str(SIDECAR_ROOT))
sys.path.insert(0, str(SAGE_ROOT))
```

- [ ] **Step 3: Write the failing RPC tests**

```python
# sage-desktop/sidecar/tests/test_rpc.py
import json
import io
import pytest
from rpc import (
    parse_request,
    build_response,
    build_error,
    RpcError,
    RPC_PARSE_ERROR,
    RPC_INVALID_REQUEST,
    RPC_METHOD_NOT_FOUND,
    RPC_INVALID_PARAMS,
    RPC_INTERNAL_ERROR,
    read_ndjson_requests,
    write_ndjson_response,
)


def test_parse_request_accepts_valid_jsonrpc_2_0():
    req = parse_request('{"jsonrpc":"2.0","id":"1","method":"handshake","params":{}}')
    assert req.id == "1"
    assert req.method == "handshake"
    assert req.params == {}


def test_parse_request_rejects_wrong_version():
    with pytest.raises(RpcError) as exc:
        parse_request('{"jsonrpc":"1.0","id":"1","method":"x"}')
    assert exc.value.code == RPC_INVALID_REQUEST


def test_parse_request_rejects_missing_method():
    with pytest.raises(RpcError) as exc:
        parse_request('{"jsonrpc":"2.0","id":"1"}')
    assert exc.value.code == RPC_INVALID_REQUEST


def test_parse_request_rejects_malformed_json():
    with pytest.raises(RpcError) as exc:
        parse_request('{not json')
    assert exc.value.code == RPC_PARSE_ERROR


def test_build_response_shape():
    resp = build_response(id="42", result={"ok": True})
    assert resp == {"jsonrpc": "2.0", "id": "42", "result": {"ok": True}}


def test_build_error_shape():
    resp = build_error(id="42", code=-32000, message="boom", data={"detail": "x"})
    assert resp == {
        "jsonrpc": "2.0",
        "id": "42",
        "error": {"code": -32000, "message": "boom", "data": {"detail": "x"}},
    }


def test_build_error_without_data_omits_data_field():
    resp = build_error(id="42", code=-32000, message="boom")
    assert "data" not in resp["error"]


def test_read_ndjson_requests_parses_multiple_lines():
    stream = io.StringIO(
        '{"jsonrpc":"2.0","id":"1","method":"a"}\n'
        '{"jsonrpc":"2.0","id":"2","method":"b"}\n'
    )
    reqs = list(read_ndjson_requests(stream))
    assert [r.id for r in reqs] == ["1", "2"]
    assert [r.method for r in reqs] == ["a", "b"]


def test_read_ndjson_requests_skips_blank_lines():
    stream = io.StringIO(
        '{"jsonrpc":"2.0","id":"1","method":"a"}\n'
        '\n'
        '{"jsonrpc":"2.0","id":"2","method":"b"}\n'
    )
    reqs = list(read_ndjson_requests(stream))
    assert len(reqs) == 2


def test_write_ndjson_response_appends_newline():
    out = io.StringIO()
    write_ndjson_response(out, {"jsonrpc": "2.0", "id": "1", "result": 42})
    assert out.getvalue() == '{"jsonrpc": "2.0", "id": "1", "result": 42}\n'
```

- [ ] **Step 4: Run tests — expect all to fail**

```bash
cd C:/System-Team-repos/SAGE/sage-desktop/sidecar && python -m pytest tests/test_rpc.py -v
```

Expected: ImportError on `from rpc import ...` — module doesn't exist yet.

- [ ] **Step 5: Implement `rpc.py`**

```python
# sage-desktop/sidecar/rpc.py
"""JSON-RPC 2.0 over NDJSON framing for the SAGE desktop sidecar."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional, TextIO

# JSON-RPC 2.0 standard error codes
RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_INTERNAL_ERROR = -32603

# SAGE-specific error codes (per spec §6.1)
RPC_SIDECAR_ERROR = -32000
RPC_PROPOSAL_EXPIRED = -32001
RPC_RBAC_DENIED = -32002
RPC_PROPOSAL_NOT_FOUND = -32003
RPC_SOLUTION_UNAVAILABLE = -32004
RPC_ALREADY_DECIDED = -32005
RPC_SAGE_IMPORT_ERROR = -32010


class RpcError(Exception):
    """Raised to signal an RPC-level error with a structured code."""

    def __init__(self, code: int, message: str, data: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass
class Request:
    id: str
    method: str
    params: dict


def parse_request(line: str) -> Request:
    """Parse one NDJSON line as a JSON-RPC 2.0 request."""
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as e:
        raise RpcError(RPC_PARSE_ERROR, f"parse error: {e}")
    if not isinstance(obj, dict):
        raise RpcError(RPC_INVALID_REQUEST, "request must be a JSON object")
    if obj.get("jsonrpc") != "2.0":
        raise RpcError(RPC_INVALID_REQUEST, "jsonrpc must be '2.0'")
    if "method" not in obj or not isinstance(obj["method"], str):
        raise RpcError(RPC_INVALID_REQUEST, "method required")
    params = obj.get("params", {})
    if not isinstance(params, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")
    req_id = obj.get("id")
    if req_id is None:
        raise RpcError(RPC_INVALID_REQUEST, "id required (notifications not supported)")
    return Request(id=str(req_id), method=obj["method"], params=params)


def build_response(id: str, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def build_error(id: Optional[str], code: int, message: str, data: Optional[dict] = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": err}


def read_ndjson_requests(stream: TextIO) -> Iterable[Request]:
    """Yield Request objects for each non-blank line on the stream."""
    for raw in stream:
        line = raw.strip()
        if not line:
            continue
        yield parse_request(line)


def write_ndjson_response(stream: TextIO, resp: dict) -> None:
    stream.write(json.dumps(resp) + "\n")
    stream.flush()
```

- [ ] **Step 6: Run tests — expect all pass**

```bash
cd C:/System-Team-repos/SAGE/sage-desktop/sidecar && python -m pytest tests/test_rpc.py -v
```

Expected: 10 passed.

- [ ] **Step 7: Commit**

```bash
cd C:/System-Team-repos/SAGE && \
git add sage-desktop/sidecar/ && \
git commit -m "feat(sidecar): JSON-RPC 2.0 over NDJSON framing with tests"
```

---

## Task 2: Python sidecar — Dispatcher + error mapping

**Files:**
- Create: `sage-desktop/sidecar/dispatcher.py`
- Create: `sage-desktop/sidecar/errors.py`
- Create: `sage-desktop/sidecar/tests/test_dispatcher.py`

- [ ] **Step 1: Write failing dispatcher tests**

```python
# sage-desktop/sidecar/tests/test_dispatcher.py
import pytest
from dispatcher import Dispatcher
from rpc import (
    Request,
    RpcError,
    RPC_METHOD_NOT_FOUND,
    RPC_INVALID_PARAMS,
    RPC_INTERNAL_ERROR,
)


def test_dispatch_unknown_method_returns_method_not_found():
    d = Dispatcher()
    with pytest.raises(RpcError) as exc:
        d.dispatch(Request(id="1", method="nope", params={}))
    assert exc.value.code == RPC_METHOD_NOT_FOUND


def test_dispatch_calls_registered_handler_and_returns_result():
    d = Dispatcher()
    d.register("ping", lambda params: {"pong": True})
    out = d.dispatch(Request(id="1", method="ping", params={}))
    assert out == {"pong": True}


def test_dispatch_passes_params_to_handler():
    d = Dispatcher()
    seen = {}
    def handler(params):
        seen.update(params)
        return "ok"
    d.register("echo", handler)
    d.dispatch(Request(id="1", method="echo", params={"a": 1, "b": 2}))
    assert seen == {"a": 1, "b": 2}


def test_dispatch_wraps_unexpected_exception_as_internal_error():
    d = Dispatcher()
    def boom(params):
        raise ValueError("kaboom")
    d.register("boom", boom)
    with pytest.raises(RpcError) as exc:
        d.dispatch(Request(id="1", method="boom", params={}))
    assert exc.value.code == RPC_INTERNAL_ERROR
    assert "kaboom" in exc.value.message


def test_dispatch_propagates_rpc_error_unchanged():
    d = Dispatcher()
    def raises_rpc(params):
        raise RpcError(RPC_INVALID_PARAMS, "bad field", {"field": "x"})
    d.register("bad", raises_rpc)
    with pytest.raises(RpcError) as exc:
        d.dispatch(Request(id="1", method="bad", params={}))
    assert exc.value.code == RPC_INVALID_PARAMS
    assert exc.value.data == {"field": "x"}


def test_register_twice_overwrites():
    d = Dispatcher()
    d.register("x", lambda p: 1)
    d.register("x", lambda p: 2)
    assert d.dispatch(Request(id="1", method="x", params={})) == 2


def test_methods_list_includes_registered():
    d = Dispatcher()
    d.register("a", lambda p: None)
    d.register("b", lambda p: None)
    assert set(d.methods()) == {"a", "b"}
```

- [ ] **Step 2: Run — expect import failure**

```bash
cd C:/System-Team-repos/SAGE/sage-desktop/sidecar && python -m pytest tests/test_dispatcher.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `dispatcher.py`**

```python
# sage-desktop/sidecar/dispatcher.py
"""Method-name → handler registry for the sidecar."""
from __future__ import annotations

from typing import Callable, Dict, List

from rpc import (
    Request,
    RpcError,
    RPC_METHOD_NOT_FOUND,
    RPC_INTERNAL_ERROR,
)

Handler = Callable[[dict], object]


class Dispatcher:
    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}

    def register(self, method: str, handler: Handler) -> None:
        self._handlers[method] = handler

    def methods(self) -> List[str]:
        return list(self._handlers.keys())

    def dispatch(self, req: Request) -> object:
        handler = self._handlers.get(req.method)
        if handler is None:
            raise RpcError(RPC_METHOD_NOT_FOUND, f"method not found: {req.method}")
        try:
            return handler(req.params)
        except RpcError:
            raise
        except Exception as e:  # noqa: BLE001 — we want to wrap everything else
            raise RpcError(RPC_INTERNAL_ERROR, f"internal error: {e}") from e
```

- [ ] **Step 4: Run — expect 7 pass**

```bash
cd C:/System-Team-repos/SAGE/sage-desktop/sidecar && python -m pytest tests/test_dispatcher.py -v
```

- [ ] **Step 5: Create `errors.py` — Python exception → JSON-RPC code mapping**

```python
# sage-desktop/sidecar/errors.py
"""Central place to map SAGE/SQLite exceptions to JSON-RPC error codes."""
from __future__ import annotations

from rpc import (
    RpcError,
    RPC_PROPOSAL_NOT_FOUND,
    RPC_PROPOSAL_EXPIRED,
    RPC_ALREADY_DECIDED,
    RPC_RBAC_DENIED,
    RPC_SOLUTION_UNAVAILABLE,
    RPC_SAGE_IMPORT_ERROR,
)


class ProposalNotFound(RpcError):
    def __init__(self, trace_id: str):
        super().__init__(RPC_PROPOSAL_NOT_FOUND, f"proposal not found: {trace_id}",
                         {"trace_id": trace_id})


class ProposalExpired(RpcError):
    def __init__(self, trace_id: str):
        super().__init__(RPC_PROPOSAL_EXPIRED, f"proposal expired: {trace_id}",
                         {"trace_id": trace_id})


class AlreadyDecided(RpcError):
    def __init__(self, trace_id: str, status: str):
        super().__init__(RPC_ALREADY_DECIDED, f"proposal already {status}: {trace_id}",
                         {"trace_id": trace_id, "status": status})


class RbacDenied(RpcError):
    def __init__(self, required_role: str):
        super().__init__(RPC_RBAC_DENIED, f"RBAC: role required: {required_role}",
                         {"required_role": required_role})


class SolutionUnavailable(RpcError):
    def __init__(self, detail: str):
        super().__init__(RPC_SOLUTION_UNAVAILABLE, f"solution unavailable: {detail}",
                         {"detail": detail})


class SageImportError(RpcError):
    def __init__(self, module: str, detail: str):
        super().__init__(RPC_SAGE_IMPORT_ERROR, f"cannot import {module}: {detail}",
                         {"module": module, "detail": detail})
```

- [ ] **Step 6: Commit**

```bash
cd C:/System-Team-repos/SAGE && \
git add sage-desktop/sidecar/ && \
git commit -m "feat(sidecar): dispatcher and SAGE-specific RPC error classes"
```

---
