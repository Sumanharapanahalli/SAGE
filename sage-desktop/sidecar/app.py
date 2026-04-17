"""sage-desktop sidecar event loop.

Importable module so integration tests can drive ``run()`` with
``io.StringIO`` streams. The thin ``__main__.py`` wrapper only exists so
the sidecar is runnable as ``python -m sidecar``.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Put the SAGE repo root on sys.path so `from src.core...` resolves when
# the sidecar is spawned from arbitrary working directories (Tauri will
# spawn from the bundle dir, not the SAGE checkout root).
_SAGE_ROOT_ENV = os.environ.get("SAGE_ROOT")
if _SAGE_ROOT_ENV and os.path.isdir(_SAGE_ROOT_ENV):
    if _SAGE_ROOT_ENV not in sys.path:
        sys.path.insert(0, _SAGE_ROOT_ENV)
else:
    # Fallback: infer from repo layout (sage-desktop/sidecar/app.py → repo root)
    _inferred = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(_inferred, "src")) and _inferred not in sys.path:
        sys.path.insert(0, _inferred)

from rpc import (
    RpcError,
    Request,
    build_error,
    build_response,
    parse_request,
    write_ndjson_response,
    RPC_INTERNAL_ERROR,
)
from dispatcher import Dispatcher
from handlers import (
    agents,
    approvals,
    audit,
    backlog,
    builds,
    handshake,
    llm,
    onboarding,
    queue,
    solutions,
    status,
    telemetry,
    yaml_edit,
)


def _configure_logging() -> None:
    """Route logs to stderr so they don't pollute the NDJSON response stream."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _build_dispatcher() -> Dispatcher:
    d = Dispatcher()
    d.register("handshake", handshake.handshake)
    d.register("approvals.list_pending", approvals.list_pending)
    d.register("approvals.get", approvals.get)
    d.register("approvals.approve", approvals.approve)
    d.register("approvals.reject", approvals.reject)
    d.register("approvals.batch_approve", approvals.batch_approve)
    d.register("audit.list", audit.list_events)
    d.register("audit.get_by_trace", audit.get_by_trace)
    d.register("audit.stats", audit.stats)
    d.register("agents.list", agents.list_agents)
    d.register("agents.get", agents.get_agent)
    d.register("status.get", status.get_status)
    d.register("llm.get_info", llm.get_llm_info)
    d.register("llm.switch", llm.switch_llm)
    d.register("backlog.list", backlog.list_feature_requests)
    d.register("backlog.submit", backlog.submit_feature_request)
    d.register("backlog.update", backlog.update_feature_request)
    d.register("queue.get_status", queue.get_queue_status)
    d.register("queue.list_tasks", queue.list_queue_tasks)
    d.register("solutions.list", solutions.list_solutions)
    d.register("solutions.get_current", solutions.get_current)
    d.register("onboarding.generate", onboarding.generate)
    d.register("builds.start", builds.start)
    d.register("builds.list", builds.list_runs)
    d.register("builds.get", builds.get)
    d.register("builds.approve", builds.approve_stage)
    d.register("yaml.read", yaml_edit.read)
    d.register("yaml.write", yaml_edit.write)
    d.register("telemetry.get_status", telemetry.get_status)
    d.register("telemetry.set_enabled", telemetry.set_enabled)
    return d


def _wire_handlers(solution_name: str, solution_path: Optional[Path]) -> None:
    """Instantiate shared resources and inject into handler modules.

    Failures are logged but non-fatal — the handshake probe list surfaces
    the gap and the UI can degrade gracefully.
    """
    handshake._SOLUTION_NAME = solution_name
    handshake._SOLUTION_PATH = solution_path

    yaml_edit._solution_name = solution_name or None
    yaml_edit._solution_path = solution_path

    solutions._current_name = solution_name
    solutions._current_path = solution_path
    try:
        from src.core.project_loader import list_solutions as _lf

        solutions._list_fn = _lf
        _sr = os.environ.get("SAGE_ROOT")
        solutions._sage_root = Path(_sr) if _sr else None
    except Exception as e:  # noqa: BLE001
        logging.warning("solutions.list wiring unavailable: %s", e)

    try:
        from src.core.onboarding import generate_solution as _gs

        onboarding._generate_fn = _gs
    except Exception as e:  # noqa: BLE001
        logging.warning("onboarding.generate wiring unavailable: %s", e)

    try:
        from src.integrations.build_orchestrator import build_orchestrator as _bo

        builds._orch = _bo
    except Exception as e:  # noqa: BLE001
        logging.warning("build_orchestrator wiring unavailable: %s", e)

    if not solution_path:
        logging.info("No solution path provided — running in minimal mode.")
        return

    sage_dir = solution_path / ".sage"
    try:
        sage_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        logging.warning("Could not create .sage/ dir at %s: %s", sage_dir, e)
        return

    try:
        from src.core.proposal_store import ProposalStore

        store = ProposalStore(str(sage_dir / "proposals.db"))
        approvals._store = store
        status._store = store
    except Exception as e:  # noqa: BLE001
        logging.warning("ProposalStore unavailable: %s", e)

    try:
        from src.memory.audit_logger import AuditLogger

        audit_logger = AuditLogger(db_path=str(sage_dir / "audit_log.db"))
        audit._logger = audit_logger
        agents._logger = audit_logger
    except Exception as e:  # noqa: BLE001
        logging.warning("AuditLogger unavailable: %s", e)

    try:
        from src.core.feature_request_store import FeatureRequestStore

        fr_store = FeatureRequestStore(str(sage_dir / "audit_log.db"))
        fr_store.init_schema()
        backlog._store = fr_store
    except Exception as e:  # noqa: BLE001
        logging.warning("FeatureRequestStore unavailable: %s", e)

    try:
        from src.core.project_loader import ProjectConfig

        pc = ProjectConfig(solution_name)
        agents._project = pc
        status._project = pc
    except Exception as e:  # noqa: BLE001
        logging.warning("ProjectConfig unavailable: %s", e)

    try:
        from src.core.llm_gateway import llm_gateway as lg

        status._llm = lg
        llm._gateway = lg
    except Exception as e:  # noqa: BLE001
        logging.warning("LLMGateway unavailable: %s", e)

    try:
        from src.core.queue_manager import get_task_queue

        queue._queue = get_task_queue(solution_name)
    except Exception as e:  # noqa: BLE001
        logging.warning("TaskQueue unavailable: %s", e)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="sage-desktop-sidecar")
    p.add_argument("--solution-name", default=os.environ.get("SAGE_SOLUTION_NAME", ""))
    p.add_argument("--solution-path", default=os.environ.get("SAGE_SOLUTION_PATH", ""))
    return p.parse_args(argv)


def run(stdin=None, stdout=None, argv: Optional[list[str]] = None) -> int:
    """NDJSON event loop. Returns an exit code when stdin reaches EOF."""
    _configure_logging()
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    solution_path = Path(args.solution_path) if args.solution_path else None

    dispatcher = _build_dispatcher()
    _wire_handlers(args.solution_name, solution_path)

    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        req: Optional[Request] = None
        try:
            req = parse_request(line)
            result = dispatcher.dispatch(req)
            write_ndjson_response(stdout, build_response(req.id, result))
        except RpcError as e:
            req_id = req.id if req is not None else None
            write_ndjson_response(
                stdout, build_error(req_id, e.code, e.message, e.data)
            )
        except Exception as e:  # noqa: BLE001
            logging.exception("unhandled handler error")
            req_id = req.id if req is not None else None
            write_ndjson_response(
                stdout,
                build_error(req_id, RPC_INTERNAL_ERROR, f"internal error: {e}"),
            )
    return 0
