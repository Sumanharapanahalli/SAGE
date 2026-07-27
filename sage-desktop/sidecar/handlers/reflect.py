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

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

# Test seam — override to inject a fake LLM gateway. Defaults to the real one.
_llm_factory = None

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


def run(params: dict) -> dict:
    """Run a bounded reflection loop over ``task`` and return the result."""
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

    llm = _get_llm()
    engine = _get_engine()
    from src.core.reflection_engine import ReflectionConfig

    cfg = ReflectionConfig(
        max_iterations=max_iterations, acceptance_threshold=float(threshold)
    )
    try:
        result = engine.reflect(
            generator=_make_generator(llm, task),
            critic=_make_critic(llm, task),
            config=cfg,
            context=str(context),
        )
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"reflect.run failed: {e}") from e

    out = result.to_dict()
    out["final_output"] = result.final_output
    return out


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
