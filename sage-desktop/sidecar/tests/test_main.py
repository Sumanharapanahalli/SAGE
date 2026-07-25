"""Integration tests for the sidecar entry point.

Drives the `run()` event loop with in-memory StringIO streams so we can
assert the full NDJSON round-trip without spawning a subprocess.
"""

from __future__ import annotations

import io
import json

import pytest

import app as sidecar_app


def _drive(stdin_text: str, argv: list[str] | None = None) -> list[dict]:
    """Run the sidecar loop with the given stdin text and return parsed
    responses from stdout."""
    stdin = io.StringIO(stdin_text)
    stdout = io.StringIO()
    sidecar_app.run(stdin=stdin, stdout=stdout, argv=argv or [])
    stdout.seek(0)
    return [json.loads(line) for line in stdout.read().splitlines() if line.strip()]


def _req(id: str, method: str, params: dict | None = None) -> str:
    return json.dumps(
        {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}
    )


# ---------- handshake ----------


def test_handshake_round_trip():
    out = _drive(_req("1", "handshake") + "\n")
    assert len(out) == 1
    assert out[0]["jsonrpc"] == "2.0"
    assert out[0]["id"] == "1"
    result = out[0]["result"]
    assert "sidecar_version" in result
    assert "sage_version" in result
    assert "warnings" in result


# ---------- status ----------


def test_status_round_trip_without_solution():
    out = _drive(_req("s1", "status.get") + "\n")
    assert out[0]["result"]["health"] == "ok"
    # No solution → project is None
    assert out[0]["result"]["project"] is None


# ---------- error handling ----------


def test_unknown_method_returns_method_not_found_error():
    out = _drive(_req("x", "does.not.exist") + "\n")
    assert out[0]["id"] == "x"
    assert out[0]["error"]["code"] == -32601  # RPC_METHOD_NOT_FOUND


def test_bad_json_returns_parse_error_with_null_id():
    out = _drive("this is not json\n")
    assert out[0]["id"] is None
    assert out[0]["error"]["code"] == -32700  # RPC_PARSE_ERROR


def test_missing_id_returns_invalid_request():
    line = json.dumps({"jsonrpc": "2.0", "method": "handshake"})
    out = _drive(line + "\n")
    assert out[0]["id"] is None
    assert out[0]["error"]["code"] == -32600  # RPC_INVALID_REQUEST


def test_invalid_params_shape_error_carries_the_request_id():
    """A frame with a VALID id but non-object params must produce an error
    response carrying that id — else the Rust client (which correlates by
    id) can never match the error frame and hangs."""
    for bad_params in ([1, 2], 42, "nope"):
        line = json.dumps(
            {"jsonrpc": "2.0", "id": "42", "method": "x", "params": bad_params}
        )
        out = _drive(line + "\n")
        assert out[0]["id"] == "42", f"params={bad_params!r} -> {out[0]}"
        assert out[0]["error"]["code"] == -32602  # RPC_INVALID_PARAMS


def test_handler_value_error_becomes_internal_error():
    """If a handler raises a non-RpcError exception, the dispatcher wraps
    it as RPC_INTERNAL_ERROR and the loop still emits a clean response."""
    # Approvals without store will raise RpcError (INVALID_PARAMS)
    out = _drive(_req("a1", "approvals.list_pending") + "\n")
    assert out[0]["id"] == "a1"
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32602  # RPC_INVALID_PARAMS


# ---------- multiple requests on the same stream ----------


def test_multiple_requests_processed_in_order():
    stdin_text = (
        _req("1", "handshake")
        + "\n"
        + _req("2", "status.get")
        + "\n"
        + _req("3", "does.not.exist")
        + "\n"
    )
    out = _drive(stdin_text)
    assert [r["id"] for r in out] == ["1", "2", "3"]
    assert "result" in out[0]
    assert "result" in out[1]
    assert "error" in out[2]


def test_blank_lines_are_ignored():
    stdin_text = "\n\n" + _req("1", "handshake") + "\n\n"
    out = _drive(stdin_text)
    assert len(out) == 1
    assert out[0]["id"] == "1"


# ---------- with solution path (end-to-end wiring) ----------

# ---------- solutions ----------


def test_solutions_list_round_trip():
    """Smoke test: `solutions.list` should return a list (possibly empty) —
    the SAGE_ROOT env var and project_loader.list_solutions are wired in
    `_wire_handlers`, so this exercises the full path through the real
    dispatcher."""
    out = _drive(_req("sl", "solutions.list") + "\n")
    assert "result" in out[0], f"got error: {out[0]}"
    assert isinstance(out[0]["result"], list)


def test_solutions_list_works_without_sage_root_env(monkeypatch):
    """Launched standalone (no SAGE_ROOT env), `solutions.list` must still
    enumerate solutions by falling back to the inferred repo root — the same
    fallback the sys.path bootstrap uses. With the bug it returns []."""
    import os

    monkeypatch.delenv("SAGE_ROOT", raising=False)
    sage_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    if not os.path.isdir(os.path.join(sage_root, "solutions", "starter")):
        pytest.skip("starter solution not present on this branch")

    out = _drive(_req("sl0", "solutions.list") + "\n")
    assert "result" in out[0], f"got error: {out[0]}"
    names = [s.get("name") for s in out[0]["result"]]
    assert "starter" in names, (
        f"expected inferred-root fallback to find solutions, got {names}"
    )


def test_solutions_get_current_without_solution_returns_null():
    out = _drive(_req("sc", "solutions.get_current") + "\n")
    assert "result" in out[0]
    # No --solution-name passed, so current is null
    assert out[0]["result"] is None


# ---------- onboarding ----------


def test_onboarding_generate_wires_to_handler():
    """The dispatcher should route to `onboarding.generate` and surface
    InvalidParams when called with no description/solution_name — proves
    the handler is registered and the error mapping works end-to-end."""
    out = _drive(_req("o1", "onboarding.generate", {}) + "\n")
    assert out[0]["id"] == "o1"
    assert "error" in out[0], f"expected error, got {out[0]}"
    assert out[0]["error"]["code"] == -32602


# ---------- queue ----------


def test_queue_status_reports_real_parallel_config(tmp_path):
    """`queue.get_status` must reflect the live ParallelTaskRunner config,
    not the bare TaskQueue (which has no `_config`). This exercises the
    real wiring in `_wire_handlers`; the global ParallelConfig defaults to
    enabled / 4 workers. Asserts only the parallel fields — the global
    sqlite-backed queue may carry leftover task counts."""
    import os

    sage_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    solution_path = os.path.join(sage_root, "solutions", "starter")
    if not os.path.isdir(solution_path):
        pytest.skip("starter solution not present on this branch")

    argv = ["--solution-name", "starter", "--solution-path", str(tmp_path)]
    out = _drive(_req("q1", "queue.get_status") + "\n", argv=argv)
    assert "result" in out[0], f"got error: {out[0]}"
    assert out[0]["result"]["parallel_enabled"] is True
    assert out[0]["result"]["max_workers"] == 4


def test_queue_is_wired_to_this_solutions_own_sage_dir(tmp_path):
    """The queue must be genuinely per-solution-isolated, not the shared
    framework-global _DB_PATH under a different registry key (the prior
    bug — see tests/test_queue_manager.py for the isolation proof itself).
    This asserts the WIRING side specifically: driving the sidecar for a
    solution creates that solution's own .sage/queue.db, the same pattern
    as proposals.db / audit_log.db above it in _wire_handlers.

    Uses a solution-name distinct from "starter" (used by the test above)
    — get_task_queue's registry caches by name alone, so reusing "starter"
    here would silently return that test's already-cached TaskQueue instead
    of exercising this test's own tmp_path wiring."""
    argv = ["--solution-name", "queue-wiring-test", "--solution-path", str(tmp_path)]
    out = _drive(_req("q1", "queue.get_status") + "\n", argv=argv)
    assert "result" in out[0], f"got error: {out[0]}"
    assert (tmp_path / ".sage" / "queue.db").is_file()


# ---------- eval ----------


def test_wiring_reloads_global_project_config_for_eval_suite_resolution(tmp_path):
    """eval_runner._get_evals_dir() reads the framework-global
    project_loader.project_config singleton directly, not an injectable
    instance — unlike agents.py/status.py, which get their own
    ProjectConfig(solution_name). Without reloading the global singleton
    too, eval.list_suites would silently resolve whatever solution
    SAGE_PROJECT/auto-discovery picked at import time, not this sidecar's
    actual --solution-name. Assert the wiring side effect directly."""
    import os

    sage_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    solution_path = os.path.join(sage_root, "solutions", "starter")
    if not os.path.isdir(solution_path):
        pytest.skip("starter solution not present on this branch")

    argv = ["--solution-name", "starter", "--solution-path", str(tmp_path)]
    out = _drive(_req("e1", "eval.list_suites") + "\n", argv=argv)
    assert "result" in out[0], f"got error: {out[0]}"

    from src.core.project_loader import project_config

    assert project_config.project_name == "starter"


# ---------- builds ----------


def test_builds_list_round_trip():
    """`builds.list` should return a list (possibly empty) — exercises
    the full dispatcher → orchestrator path."""
    out = _drive(_req("b1", "builds.list") + "\n")
    assert "result" in out[0], f"got error: {out[0]}"
    assert isinstance(out[0]["result"], list)


def test_builds_start_without_description_returns_invalid_params():
    out = _drive(_req("b2", "builds.start", {}) + "\n")
    assert out[0]["id"] == "b2"
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32602


# ---------- yaml authoring ----------


def test_yaml_read_without_solution_returns_sidecar_error():
    out = _drive(_req("y1", "yaml.read", {"file": "project"}) + "\n")
    assert out[0]["id"] == "y1"
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32000


def test_yaml_write_with_invalid_file_name_returns_invalid_params():
    out = _drive(
        _req("y2", "yaml.write", {"file": "secrets", "content": "x: 1\n"}) + "\n"
    )
    assert out[0]["id"] == "y2"
    assert "error" in out[0]
    assert out[0]["error"]["code"] == -32602


def test_sidecar_wires_up_stores_when_solution_path_given(tmp_path):
    """When --solution-path is provided, approvals.list_pending should work
    (returning an empty list, not an INVALID_PARAMS error)."""
    # Use the starter solution that actually exists on main
    import os

    sage_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    solution_path = os.path.join(sage_root, "solutions", "starter")

    # Only run if the solution exists on this branch
    if not os.path.isdir(solution_path):
        pytest.skip("starter solution not present on this branch")

    argv = ["--solution-name", "starter", "--solution-path", str(tmp_path)]
    out = _drive(_req("1", "approvals.list_pending") + "\n", argv=argv)
    assert "result" in out[0], f"got error: {out[0]}"
    assert isinstance(out[0]["result"], list)


# ---------- registration: builds.reject / queue.cancel / queue.retry ----------
#
# This repo has a history of handlers that were written, tested, and never
# registered — dead code that looks like a feature. These assert the wire is
# actually connected.


@pytest.mark.parametrize("method", ["builds.reject", "queue.cancel", "queue.retry"])
def test_operator_recovery_rpcs_are_registered_in_the_dispatcher(method):
    assert method in sidecar_app._build_dispatcher().methods()


def test_builds_reject_round_trip_over_real_ndjson(monkeypatch):
    """Drive builds.reject through the real dispatcher and assert the operator's
    reasoning reaches BOTH the audit log and the vector store (Phase 5)."""
    import src.integrations.build_orchestrator as bo_mod

    import handlers.builds as builds

    audited: list = []
    remembered: list = []

    class _Audit:
        def log_event(self, **kw):
            audited.append(kw)

    class _Memory:
        def remember(self, text, user_id=None, metadata=None):
            remembered.append(text)

    class _Orch:
        def __init__(self):
            self.state = "awaiting_build"

        def get_status(self, run_id):
            return {"run_id": run_id, "state": self.state}

        def reject(self, run_id, feedback=""):
            self.state = "rejected"
            return {"run_id": run_id, "state": "rejected", "error": None}

    # run() → _wire_handlers() re-imports the orchestrator singleton and
    # overwrites builds._orch, so patching the handler attribute alone would be
    # undone before the request is ever dispatched. Patch the source.
    monkeypatch.setattr(bo_mod, "build_orchestrator", _Orch())
    monkeypatch.setattr(builds, "_logger", _Audit())
    monkeypatch.setattr(builds, "_long_term_memory_factory", lambda: _Memory())
    monkeypatch.setattr(
        builds,
        "_operator",
        lambda: {"name": "Ada", "email": "ada@example.com", "provider": "local"},
    )

    out = _drive(
        _req(
            "b1", "builds.reject", {"run_id": "r1", "feedback": "no tests in the plan"}
        )
        + "\n"
    )
    assert "error" not in out[0], out[0]
    assert out[0]["result"]["state"] == "rejected"
    assert audited[0]["action_type"] == "BUILD_STAGE_REJECTED"
    assert audited[0]["actor"] == "Ada"
    assert "no tests in the plan" in remembered[0]


def test_builds_reject_on_a_run_not_at_a_gate_returns_invalid_params(monkeypatch):
    import src.integrations.build_orchestrator as bo_mod

    monkeypatch.setattr(
        bo_mod,
        "build_orchestrator",
        type(
            "O",
            (),
            {
                "get_status": lambda self, r: {"state": "building"},
                "reject": lambda self, r, f="": {},
            },
        )(),
    )
    out = _drive(_req("b2", "builds.reject", {"run_id": "r1", "feedback": "x"}) + "\n")
    assert out[0]["error"]["code"] == -32602


def test_queue_cancel_and_retry_round_trip_over_real_ndjson(monkeypatch):
    """Cancel then retry a real Task through a real TaskQueue, over NDJSON."""
    import handlers.queue as queue_handler

    class _Audit:
        def __init__(self):
            self.events = []

        def log_event(self, **kw):
            self.events.append(kw)

    audit = _Audit()

    class _Q:
        """Records the transitions the real TaskQueue makes."""

        def __init__(self):
            self.status = "pending"

        def get_all_tasks(self):
            return [
                {"task_id": "t1", "status": self.status, "task_type": "ANALYZE_LOG"}
            ]

        def cancel_task(self, task_id):
            if task_id != "t1":
                return {"cancelled": False, "reason": "not_found"}
            self.status = "cancelled"
            return {"cancelled": True, "status": "cancelled", "was_running": False}

        def requeue_task(self, task_id):
            if task_id != "t1":
                return {"requeued": False, "reason": "not_found"}
            self.status = "pending"
            return {"requeued": True, "status": "pending"}

    q = _Q()
    monkeypatch.setattr(queue_handler, "_queue", q)
    monkeypatch.setattr(queue_handler, "_logger", audit)
    monkeypatch.setattr(
        queue_handler,
        "_operator",
        lambda: {"name": "Ada", "email": "ada@example.com", "provider": "local"},
    )

    out = _drive(
        _req("q1", "queue.cancel", {"task_id": "t1"})
        + "\n"
        + _req("q2", "queue.list_tasks", {})
        + "\n"
        + _req("q3", "queue.retry", {"task_id": "t1"})
        + "\n"
        + _req("q4", "queue.cancel", {"task_id": "ghost"})
        + "\n"
    )
    assert out[0]["result"]["cancelled"] is True
    assert out[1]["result"][0]["status"] == "cancelled"
    assert out[2]["result"]["requeued"] is True
    assert out[3]["error"]["code"] == -32602  # unknown task
    assert [e["action_type"] for e in audit.events] == [
        "TASK_CANCELLED",
        "TASK_RETRIED",
    ]
