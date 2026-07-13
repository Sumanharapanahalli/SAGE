"""Preflight handler — a NON-MUTATING readiness probe of the whole stack.

Before this handler, the only way to find out from desktop whether the LLM
provider was actually alive was to fire ``analyze.run``, which writes a real
``analysis`` proposal into the ProposalStore. Checking liveness dirtied the
approvals queue. ``health.preflight`` is the read-only alternative: it runs a
1-token probe through the same ``llm_gateway.generate()`` the agents use,
times it, and writes nothing anywhere.

Web's Preflight.tsx checked "Backend API" by hitting ``/health`` — meaningless
on desktop (there is no HTTP). Reframed as "Sidecar alive": if this handler
answered at all, the sidecar process, its sys.path bootstrap, and the NDJSON
dispatch loop are all working.

Every check degrades: a missing optional dependency is a ``warning``, never a
crash. The only ``error`` states are the ones that genuinely stop SAGE from
doing its job (no LLM, no solution config), and those are what drive ``go``.

Resources are injected by ``app._wire_handlers``. Nothing here mutates state.
"""
from __future__ import annotations

import concurrent.futures
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from rpc import RPC_INVALID_PARAMS, RpcError

logger = logging.getLogger(__name__)

# Deliberately short and deterministic — the point is round-trip liveness and
# latency, not output quality. Kept tiny so the probe costs ~nothing in tokens.
_PROBE_PROMPT = "Reply with the single word: OK"
_PROBE_SYSTEM = "You are a health probe. Reply with exactly one word."

_TIMEOUT_MS_DEFAULT = 20_000
_TIMEOUT_MS_MIN = 1_000
_TIMEOUT_MS_MAX = 120_000


class _ProbeTimeout(Exception):
    pass


def _call_with_timeout(fn: Callable[[], Any], timeout_ms: int) -> Any:
    """Run *fn* on a throwaway daemon thread; abandon it on timeout.

    The NDJSON dispatch loop is serial — a provider that hangs forever would
    wedge the entire sidecar, so the handler must be able to walk away from a
    call it cannot cancel.

    A fresh thread per probe (rather than a shared pool) is load-bearing:
    a pooled worker still stuck on a previous hung probe would make every
    subsequent probe time out too, turning one bad provider call into a
    permanently broken preflight. Daemon, so an abandoned probe can never hold
    interpreter shutdown open either.
    """
    box: dict = {}

    def _target() -> None:
        try:
            box["value"] = fn()
        except BaseException as e:  # noqa: BLE001 — relayed to the caller below
            box["error"] = e

    t = threading.Thread(target=_target, name="preflight-llm", daemon=True)
    t.start()
    t.join(timeout_ms / 1000.0)
    if t.is_alive():
        raise _ProbeTimeout()
    if "error" in box:
        raise box["error"]
    return box.get("value")


# Injected at startup by app._wire_handlers. Tests monkey-patch these.
_llm: Optional[Any] = None
_vm: Optional[Any] = None
_project: Optional[Any] = None
_solution_name: Optional[str] = None
_solution_path: Optional[Path] = None

SIDECAR_VERSION = "0.1.0"


def _check(name: str, fn: Callable[[], tuple], ) -> dict:
    """Run one check, time it, and never let it raise."""
    started = time.perf_counter()
    try:
        status, detail = fn()
    except Exception as e:  # noqa: BLE001 — a check crashing is itself a finding
        logger.warning("preflight check '%s' raised: %s", name, e)
        status, detail = "error", f"check failed: {e}"
    elapsed = (time.perf_counter() - started) * 1000.0
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "latency_ms": round(elapsed, 1),
    }


# The LLM probe runs on this pool, never inline: `future.result(timeout=...)` lets a
# hung provider be ABANDONED on its worker thread while the health check still returns.
# Calling _llm.generate() directly would block the single-threaded NDJSON dispatch loop
# for the provider's full timeout, freezing every desktop page, not just Status.
# Daemon threads so a wedged probe can never hold up interpreter shutdown.
_PROBE_POOL = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="health-probe"
)


# ── individual checks ──────────────────────────────────────────────────────

def _check_sidecar() -> tuple:
    import sys

    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return "ok", f"sidecar v{SIDECAR_VERSION} responding (Python {py})"


def _check_llm(timeout_ms: int) -> tuple:
    if _llm is None:
        return "error", "LLM gateway not wired — no provider available"

    try:
        provider = _llm.get_provider_name()
    except Exception:  # noqa: BLE001
        provider = "unknown"
    if not provider or provider == "None":
        return "error", "No LLM provider configured"

    try:
        model = _llm.get_model_info().get("model", "unknown")
    except Exception:  # noqa: BLE001
        model = "unknown"

    future = _PROBE_POOL.submit(
        _llm.generate,
        _PROBE_PROMPT,
        _PROBE_SYSTEM,
    )
    try:
        reply = future.result(timeout=timeout_ms / 1000.0)
    except concurrent.futures.TimeoutError:
        # Abandon the worker; do NOT block the dispatch loop waiting on it.
        return "error", (
            f"{provider} did not respond within {timeout_ms}ms — provider may be "
            "hung or unreachable"
        )
    except Exception as e:  # noqa: BLE001
        return "error", f"{provider} probe failed: {e}"

    if not isinstance(reply, str) or not reply.strip():
        return "warning", f"{provider} ({model}) responded but returned empty output"
    return "ok", f"{provider} — {model}"


def _check_vector_store() -> tuple:
    if _vm is None:
        return "warning", (
            "Vector memory unavailable — install the full extras to enable "
            "compounding memory (semantic recall of prior decisions)"
        )

    mode = str(getattr(_vm, "mode", "minimal"))
    # llamaindex is a superset of full for the operator's purposes — both mean
    # semantic search works (mirrors handlers/knowledge.py:_backend_label).
    backend = "full" if mode == "llamaindex" else mode

    count = 0
    try:
        count = len(_vm.list_entries(limit=10_000))
    except Exception as e:  # noqa: BLE001
        return "warning", f"backend={backend}, entry count unavailable: {e}"

    if backend == "minimal":
        return "warning", (
            f"backend=minimal ({count} entries) — keyword fallback only, "
            "semantic search disabled"
        )
    return "ok", f"backend={backend} — {count} entries"


def _check_skills() -> tuple:
    try:
        from src.core.skill_loader import skill_registry
    except Exception as e:  # noqa: BLE001 — optional dep, degrade
        return "warning", f"skill registry unavailable: {e}"

    stats = skill_registry.stats()
    total = int(stats.get("total", 0))
    active = int(stats.get("active", 0))
    if total == 0:
        return "warning", "no skills loaded"
    return "ok", f"{total} skills loaded ({active} active)"


def _triad_report(sol_path: Path) -> tuple:
    """Report on the YAML triad (or the SKILL.md that supersedes it)."""
    skill_md = sol_path / "SKILL.md"
    if skill_md.is_file():
        return "ok", "SKILL.md"
    triad = ["project.yaml", "prompts.yaml", "tasks.yaml"]
    missing = [f for f in triad if not (sol_path / f).is_file()]
    if missing:
        return "error", f"missing {', '.join(missing)}"
    return "ok", "project.yaml, prompts.yaml, tasks.yaml"


def _check_solution() -> tuple:
    if not _solution_name or _solution_path is None:
        return "error", "No solution active — pick one before running SAGE"

    if _project is None:
        return "error", (
            f"'{_solution_name}' selected but its config failed to load "
            "(check the YAML for syntax errors)"
        )

    try:
        loaded = _project.project_name
    except Exception as e:  # noqa: BLE001
        return "error", f"project config unreadable: {e}"

    sol_path = Path(_solution_path)
    if not sol_path.is_dir():
        return "error", f"solution directory not found: {sol_path}"

    status, files = _triad_report(sol_path)
    if status != "ok":
        return "error", f"'{loaded}' — {files}"

    n_tasks = 0
    try:
        n_tasks = len(_project.get_task_types())
    except Exception:  # noqa: BLE001 — informational only
        pass
    return "ok", f"'{loaded}' loaded — {files} · {n_tasks} task types"


# ── RPC method ─────────────────────────────────────────────────────────────

def preflight(params: Any) -> dict:
    """Run every readiness check and return a go/no-go verdict.

    Read-only: no proposal, no audit event, no queue task. Safe to run as
    often as the operator likes — but the LLM probe is a real provider call,
    so the UI runs it on mount and on an explicit button only, never on a
    poll interval.
    """
    p = params or {}
    if not isinstance(p, dict):
        raise RpcError(RPC_INVALID_PARAMS, "params must be an object")

    timeout_ms = p.get("timeout_ms", _TIMEOUT_MS_DEFAULT)
    if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
        raise RpcError(RPC_INVALID_PARAMS, "'timeout_ms' must be an integer")
    if timeout_ms < _TIMEOUT_MS_MIN or timeout_ms > _TIMEOUT_MS_MAX:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"'timeout_ms' must be between {_TIMEOUT_MS_MIN} and {_TIMEOUT_MS_MAX}",
        )

    started = time.perf_counter()
    checks = [
        _check("Sidecar alive", _check_sidecar),
        _check("Solution config", _check_solution),
        _check("LLM provider", lambda: _check_llm(timeout_ms)),
        _check("Vector store", _check_vector_store),
        _check("Skill registry", _check_skills),
    ]
    total_ms = round((time.perf_counter() - started) * 1000.0, 1)

    errors = sum(1 for c in checks if c["status"] == "error")
    warnings = sum(1 for c in checks if c["status"] == "warning")

    return {
        "checks": checks,
        "go": errors == 0,
        "errors": errors,
        "warnings": warnings,
        "total_latency_ms": total_ms,
        "solution": _solution_name or None,
    }
