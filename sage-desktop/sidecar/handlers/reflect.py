"""Reflection-engine handlers — port ``src.core.reflection_engine`` to desktop.

Exposes the bounded self-correction loop (generate -> critique -> refine) so a
desktop operator can RUN and INSPECT reflections in the app:

    reflect.run     -> run a reflection loop over a task (LLM generator + critic)
    reflect.stats   -> aggregate stats over reflections run this session
    reflect.recent  -> recent reflection results
    reflect.get     -> one reflection result by id

The engine keeps results in an in-process singleton, so stats/recent reflect the
reflections run during THIS sidecar session. ``_llm_factory`` is a test seam
(mirrors analyze.py's ``_analyst_factory``): tests inject a fake LLM so
reflect.run is deterministic and offline.
"""

from __future__ import annotations

import json
import re
import threading
import uuid

import jobs
from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Test seam — override to inject a fake LLM gateway. Defaults to the real one.
_llm_factory = None

# Live-progress buffers, keyed by run_id. A background reflect job appends one
# entry per completed iteration here (see _make_tracked_critic) so the desktop
# can poll reflect.progress and render iterations as they happen — the sidecar
# RPC is request/response, so "live" = a background job + a pollable buffer.
_progress_lock = threading.Lock()
_progress: dict[str, dict] = {}


def reset_progress() -> None:
    """Test hook: drop all in-memory reflect progress buffers."""
    with _progress_lock:
        _progress.clear()


_CRITIC_SYSTEM = (
    "You are a strict critic. Score the OUTPUT from 0.0 to 1.0 for how well it "
    'solves the TASK. Respond ONLY as JSON: {"score": <float>, "feedback": <str>}.'
)


def _get_llm():
    if _llm_factory is not None:
        return _llm_factory()
    from src.core.llm_gateway import llm_gateway

    return llm_gateway


def _get_engine():
    from src.core.reflection_engine import get_reflection_engine

    return get_reflection_engine()


def _parse_critique(raw: str) -> tuple[float, str]:
    """Parse a critic response into (score, feedback), tolerant of noise."""
    try:
        match = re.search(r"\{.*\}", str(raw), re.DOTALL)
        data = json.loads(match.group(0)) if match else json.loads(raw)
        score = max(0.0, min(1.0, float(data.get("score", 0.0))))
        return score, str(data.get("feedback", ""))
    except Exception:  # noqa: BLE001 — any parse failure falls back to a heuristic
        text = str(raw)
        return (0.5 if len(text) > 40 else 0.2), "unparseable critic response"


def _make_generator(llm, task: str):
    def gen(context: str):
        prompt = (
            f"TASK:\n{task}\n\nPrior attempts / feedback:\n{context}\n\n"
            "Produce the best possible answer, improving on any feedback above."
        )
        return llm.generate(
            prompt, "You are a careful problem solver. Improve on prior feedback."
        )

    return gen


def _make_critic(llm, task: str):
    def crit(output):
        raw = llm.generate(
            f"TASK:\n{task}\n\nOUTPUT:\n{output}\n\nScore it.", _CRITIC_SYSTEM
        )
        score, feedback = _parse_critique(raw)
        return {"score": score, "feedback": feedback}

    return crit


def _validate_run_params(params: dict) -> tuple[str, str, int, float]:
    task = params.get("task", "")
    if not isinstance(task, str) or not task.strip():
        raise RpcError(RPC_INVALID_PARAMS, "missing or empty 'task'")

    context = params.get("context", "") or ""
    max_iterations = params.get("max_iterations", 3)
    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or max_iterations < 1
    ):
        raise RpcError(
            RPC_INVALID_PARAMS, "'max_iterations' must be a positive integer"
        )

    threshold = params.get("acceptance_threshold", 0.7)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise RpcError(RPC_INVALID_PARAMS, "'acceptance_threshold' must be a number")

    return task, str(context), max_iterations, float(threshold)


def _make_tracked_critic(llm, task: str, run_id: str):
    """A critic that also records each iteration's score/feedback into the live
    progress buffer, so reflect.progress can stream them as they complete."""
    base = _make_critic(llm, task)
    counter = {"i": 0}

    def crit(output):
        evaluation = base(output)
        counter["i"] += 1
        with _progress_lock:
            buf = _progress.get(run_id)
            if buf is not None:
                buf["iterations"].append(
                    {
                        "iteration": counter["i"],
                        "score": evaluation["score"],
                        "feedback": evaluation["feedback"],
                        "output_preview": str(output)[:800],
                    }
                )
        return evaluation

    return crit


def _execute_reflection(
    run_id: str, task: str, context: str, max_iterations: int, threshold: float
) -> None:
    """Run the loop and record the outcome in the progress buffer (worker thread)."""
    from src.core.reflection_engine import ReflectionConfig

    llm = _get_llm()
    engine = _get_engine()
    cfg = ReflectionConfig(
        max_iterations=max_iterations, acceptance_threshold=threshold
    )
    try:
        result = engine.reflect(
            generator=_make_generator(llm, task),
            critic=_make_tracked_critic(llm, task, run_id),
            config=cfg,
            context=context,
        )
    except Exception as e:  # noqa: BLE001 — a failed job must be reported, not raised
        with _progress_lock:
            _progress[run_id]["state"] = "failed"
            _progress[run_id]["error"] = str(e)
        return

    out = result.to_dict()
    out["final_output"] = result.final_output
    with _progress_lock:
        _progress[run_id]["state"] = "succeeded"
        _progress[run_id]["result"] = out


def run(params: dict) -> dict:
    """Run a bounded reflection loop synchronously and return the result."""
    task, context, max_iterations, threshold = _validate_run_params(params)
    llm = _get_llm()
    engine = _get_engine()
    from src.core.reflection_engine import ReflectionConfig

    cfg = ReflectionConfig(
        max_iterations=max_iterations, acceptance_threshold=threshold
    )
    try:
        result = engine.reflect(
            generator=_make_generator(llm, task),
            critic=_make_critic(llm, task),
            config=cfg,
            context=context,
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"reflect.run failed: {e}") from e

    out = result.to_dict()
    out["final_output"] = result.final_output
    return out


def start(params: dict) -> dict:
    """Start a reflection loop as a BACKGROUND job and return a run_id to poll.

    Iterations stream into the progress buffer as they complete; the desktop
    polls reflect.progress until state != 'running'."""
    task, context, max_iterations, threshold = _validate_run_params(params)
    run_id = str(uuid.uuid4())
    with _progress_lock:
        _progress[run_id] = {
            "run_id": run_id,
            "task": task,
            "state": "running",
            "iterations": [],
            "result": None,
            "error": None,
        }

    async def _coro():
        _execute_reflection(run_id, task, context, max_iterations, threshold)
        return {"run_id": run_id}

    jobs.submit("reflect", _coro(), label=f"reflect: {task[:40]}")
    return {"run_id": run_id, "state": "running"}


def progress(params: dict) -> dict:
    """Return the live progress (iterations so far + final result) for a run_id."""
    run_id = params.get("run_id")
    if not run_id or not isinstance(run_id, str):
        raise RpcError(RPC_INVALID_PARAMS, "missing or invalid 'run_id'")
    with _progress_lock:
        buf = _progress.get(run_id)
        if buf is None:
            raise RpcError(
                RPC_INVALID_PARAMS,
                f"unknown run_id '{run_id}'",
                {"run_id": run_id},
            )
        # Copy under the lock — the worker thread may append concurrently.
        return {**buf, "iterations": list(buf["iterations"])}


def stats(params: dict) -> dict:
    try:
        return _get_engine().get_stats()
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"reflect.stats failed: {e}") from e


def recent(params: dict) -> dict:
    limit = params.get("limit", 20)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise RpcError(RPC_INVALID_PARAMS, "'limit' must be an integer")
    try:
        items = _get_engine().list_recent(limit=limit)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"reflect.recent failed: {e}") from e
    return {"reflections": items, "count": len(items)}


def get(params: dict) -> dict:  # noqa: A001 - mirrors goals.py builtin-shadow precedent
    reflection_id = params.get("reflection_id")
    if not reflection_id:
        raise RpcError(RPC_INVALID_PARAMS, "reflection_id required")
    try:
        res = _get_engine().get_result(reflection_id)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"reflect.get failed: {e}") from e
    if res is None:
        raise RpcError(
            RPC_INVALID_PARAMS,
            f"reflection not found: {reflection_id}",
            {"reflection_id": reflection_id},
        )
    return res
