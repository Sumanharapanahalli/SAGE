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
def _resolve_sage_root() -> Optional[str]:
    """Resolve the SAGE repo root: the SAGE_ROOT env var when it points at a
    real dir, otherwise infer it from the repo layout
    (sage-desktop/sidecar/app.py → repo root). Returns None if neither yields
    a directory that looks like a SAGE checkout (has a ``src/``).

    Evaluated at runtime (not frozen at import) so handler wiring picks up the
    same fallback the sys.path bootstrap uses even when SAGE_ROOT is unset.
    """
    env = os.environ.get("SAGE_ROOT")
    if env and os.path.isdir(env):
        return env
    inferred = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(inferred, "src")):
        return inferred
    return None


_SAGE_ROOT = _resolve_sage_root()
if _SAGE_ROOT and _SAGE_ROOT not in sys.path:
    sys.path.insert(0, _SAGE_ROOT)

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
    analyze,
    approvals,
    audit,
    backlog,
    builds,
    collective,
    compliance,
    constitution,
    costs,
    eval as eval_handler,
    goals,
    handshake,
    knowledge,
    llm,
    monitor,
    onboarding,
    org,
    queue,
    skills,
    solutions,
    status,
    workflow,
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
    d.register("analyze.run", analyze.run)
    d.register("compliance.domains", compliance.domains)
    d.register("compliance.flags", compliance.flags)
    d.register("compliance.checklist", compliance.checklist)
    d.register("compliance.gap_assessment", compliance.gap_assessment)
    d.register("costs.summary", costs.summary)
    d.register("costs.daily", costs.daily)
    d.register("costs.set_budget", costs.set_budget)
    d.register("org.get", org.get)
    d.register("org.update", org.update)
    d.register("org.reload", org.reload)
    d.register("skills.list", skills.list)
    d.register("skills.set_visibility", skills.set_visibility)
    d.register("skills.reload", skills.reload)
    d.register("mcp.tools", skills.mcp_tools)
    d.register("workflow.list_workflows", workflow.list_workflows)
    d.register("workflow.run", workflow.run)
    d.register("workflow.resume", workflow.resume)
    d.register("workflow.status", workflow.status)
    d.register("monitor.status", monitor.status)
    d.register("monitor.scheduler_status", monitor.scheduler_status)
    d.register("goals.list", goals.list)
    d.register("goals.create", goals.create)
    d.register("goals.get", goals.get)
    d.register("goals.update", goals.update)
    d.register("goals.delete", goals.delete)
    d.register("eval.list_suites", eval_handler.list_suites)
    d.register("eval.run", eval_handler.run)
    d.register("eval.history", eval_handler.history)
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
    d.register("backlog.plan", backlog.plan)
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
    d.register("constitution.get", constitution.get)
    d.register("constitution.update", constitution.update)
    d.register("constitution.preamble", constitution.preamble)
    d.register("constitution.check_action", constitution.check_action)
    d.register("knowledge.list", knowledge.list_entries)
    d.register("knowledge.search", knowledge.search)
    d.register("knowledge.add", knowledge.add)
    d.register("knowledge.delete", knowledge.delete)
    d.register("knowledge.stats", knowledge.stats)
    d.register("collective.list_learnings", collective.list_learnings)
    d.register("collective.get_learning", collective.get_learning)
    d.register("collective.search_learnings", collective.search_learnings)
    d.register("collective.publish_learning", collective.publish_learning)
    d.register("collective.validate_learning", collective.validate_learning)
    d.register("collective.list_help_requests", collective.list_help_requests)
    d.register("collective.create_help_request", collective.create_help_request)
    d.register("collective.claim_help_request", collective.claim_help_request)
    d.register("collective.respond_to_help_request", collective.respond_to_help_request)
    d.register("collective.close_help_request", collective.close_help_request)
    d.register("collective.sync", collective.sync)
    d.register("collective.stats", collective.stats)
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
        # Share the same inferred-repo-root fallback as the sys.path bootstrap
        # so solutions.list works even when SAGE_ROOT is unset (standalone launch).
        _sr = _resolve_sage_root()
        solutions._sage_root = Path(_sr) if _sr else None
    except Exception as e:  # noqa: BLE001
        logging.warning("solutions.list wiring unavailable: %s", e)

    # org.yaml is a SAGE_ROOT-level file (not per-solution) — wire before the
    # solution-path guard below so org.* works in standalone mode too.
    _org_sr = _resolve_sage_root()
    org._sage_root = Path(_org_sr) if _org_sr else None

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
        analyze._store = store
        backlog._proposal_store = store
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
        from src.stores.goals_store import GoalsStore

        goals._store = GoalsStore(str(sage_dir / "goals.db"))
    except Exception as e:  # noqa: BLE001
        logging.warning("GoalsStore unavailable: %s", e)

    try:
        from src.core.eval_runner import EvalRunner

        eval_handler._runner = EvalRunner(db_path=str(sage_dir / "eval_runs.db"))
    except Exception as e:  # noqa: BLE001
        logging.warning("EvalRunner unavailable: %s", e)

    try:
        from src.core.project_loader import ProjectConfig, project_config

        pc = ProjectConfig(solution_name)
        agents._project = pc
        status._project = pc
        # eval_runner._get_evals_dir() (and TaskScheduler) read the framework
        # *global* project_config singleton directly rather than an injected
        # instance — reload it in place so those code paths resolve THIS
        # solution, not whatever SAGE_PROJECT/auto-discovery picked at import
        # time. Safe: this sidecar process serves exactly one solution.
        project_config.reload(solution_name)
    except Exception as e:  # noqa: BLE001
        logging.warning("ProjectConfig unavailable: %s", e)

    try:
        from src.core.llm_gateway import llm_gateway as lg

        status._llm = lg
        llm._gateway = lg
    except Exception as e:  # noqa: BLE001
        logging.warning("LLMGateway unavailable: %s", e)

    try:
        from src.core.queue_manager import get_task_queue, parallel_runner

        # A real per-solution db_path — not just a registry cache key — so
        # this solution's queue is genuinely isolated from any other
        # solution's sidecar/web process on the same host, matching
        # ProposalStore / AuditLogger / FeatureRequestStore above.
        queue._queue = get_task_queue(solution_name, db_path=str(sage_dir / "queue.db"))
        # Parallel config lives on the runner, not the bare TaskQueue —
        # mirror api.py:1716-1717 so queue.get_status reports it correctly.
        queue._parallel_runner = parallel_runner
    except Exception as e:  # noqa: BLE001
        logging.warning("TaskQueue unavailable: %s", e)

    try:
        from src.core.constitution import Constitution

        constitution._ctx = Constitution(
            solutions_dir=str(solution_path.parent), solution=solution_name
        )
    except Exception as e:  # noqa: BLE001
        logging.warning("Constitution unavailable: %s", e)

    try:
        from src.memory.vector_store import VectorMemory

        knowledge._vm = VectorMemory(explicit_solution=solution_name)
        knowledge._solution_name = solution_name
    except Exception as e:  # noqa: BLE001
        logging.warning("VectorMemory unavailable: %s", e)

    try:
        from src.core.collective_memory import get_collective_memory

        collective._cm = get_collective_memory()
    except Exception as e:  # noqa: BLE001
        logging.warning("CollectiveMemory unavailable: %s", e)


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
            # If parse_request failed before building the Request, fall back to
            # the id it preserved on the error (e.g. a params-shape violation),
            # so the error frame still carries a correlatable id.
            req_id = req.id if req is not None else e.request_id
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
