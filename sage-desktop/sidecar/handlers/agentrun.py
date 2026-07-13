"""Agent-run handler — the desktop's "actually run an agent" surface.

The desktop /agents page is a read-only roster: the operator can see which
roles exist but cannot use one. This handler adds the execution half.

Three deliberate divergences from the web API's equivalents:

* ``agents.run`` — web's ``POST /agent/run`` returns the UniversalAgent result
  with ``status: "pending_review"`` and persists NOTHING. Nothing reads that
  field; no proposal is created; the "pending human review" banner the web UI
  draws from it is cosmetic. Law 1 says an agent proposal is gated by a human.
  So desktop persists the result as a REAL ProposalStore proposal (the Phase-5d
  pattern from handlers/analyze.py) and it shows up in the same Approvals inbox
  as everything else.

* ``agents.hire`` — writing prompts.yaml/tasks.yaml is a mutation, so it only
  ever creates an ``agent_hire`` proposal. src/core/proposal_executor.py
  already registers ``_execute_agent_hire``, which does the YAML write on
  approval. This handler never touches a YAML file itself.

* The per-IP token-bucket rate limiter on ``POST /agent/run`` is not ported —
  it is an HTTP-only concept (there is no client IP over stdin/stdout, and a
  single local operator is not a DoS vector). The task *sanitisation* it sits
  next to IS ported, because that one is about what reaches the LLM.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError

logger = logging.getLogger("sidecar.agentrun")

# Injected by app.py at startup (solution-scoped). Tests monkeypatch these.
_store = None  # type: Optional[object]   # ProposalStore — <solution>/.sage/proposals.db
_project = None  # type: Optional[object] # ProjectConfig for the active solution
_solution_name = ""  # type: str

# Optional test overrides.
_agent_factory = None
_jd_factory = None

# Mirrors api.py's validation: lowercase snake_case, 2-50 chars.
_ROLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,49}$")

_MAX_TASK_CHARS = 4000
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


# ---------- wiring / helpers ----------

def _require_store():
    if _store is None:
        raise RpcError(RPC_INVALID_PARAMS, "proposal store not initialized")
    return _store


def _require_project():
    if _project is None:
        raise RpcError(RPC_SIDECAR_ERROR, "no solution loaded")
    return _project


def _get_agent():
    if _agent_factory is not None:
        return _agent_factory()
    from src.agents.universal import UniversalAgent

    return UniversalAgent()


def _roles() -> dict:
    """UniversalAgent roles declared under ``roles:`` in prompts.yaml."""
    project = _require_project()
    try:
        roles = (project.get_prompts() or {}).get("roles", {})
    except Exception as exc:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"could not read prompts.yaml: {exc}") from exc
    return roles if isinstance(roles, dict) else {}


def _sanitize_task(raw: str) -> str:
    """Strip null bytes / control chars and cap length before it reaches the LLM."""
    return _CONTROL_CHARS.sub("", raw).strip()[:_MAX_TASK_CHARS]


def _require_str(params: dict, key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError(RPC_INVALID_PARAMS, f"missing or empty '{key}'")
    return value


def _solution() -> str:
    return _solution_name or getattr(_require_project(), "project_name", "")


# ---------- handlers ----------

def run(params: dict) -> dict:
    """Run a solution-defined UniversalAgent role and persist a real proposal.

    Returns the agent's structured result AND the pending proposal it created,
    so the page can render result cards and link straight into Approvals.
    """
    role_id = _require_str(params, "role_id")
    task = _sanitize_task(_require_str(params, "task"))
    if not task:
        raise RpcError(RPC_INVALID_PARAMS, "missing or empty 'task'")

    context = params.get("context", "")
    if not isinstance(context, str):
        raise RpcError(RPC_INVALID_PARAMS, "'context' must be a string")
    actor = params.get("actor") or "desktop-operator"

    store = _require_store()
    agent = _get_agent()

    try:
        result = agent.run(role_id=role_id, task=task, context=context, actor=actor)
    except ValueError as exc:
        # UniversalAgent raises ValueError for an unknown role — an operator
        # input error, not a sidecar fault.
        raise RpcError(RPC_INVALID_PARAMS, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"agent run failed: {exc}") from exc

    if not isinstance(result, dict):
        raise RpcError(RPC_SIDECAR_ERROR, "agent returned a non-dict result")

    from src.core.proposal_store import RiskClass

    severity = str(result.get("severity", "UNKNOWN"))
    role_name = str(result.get("role_name", role_id))
    summary = str(result.get("summary") or task)[:160]

    proposal = store.create(
        action_type="agent_run",
        risk_class=RiskClass.INFORMATIONAL,
        payload={
            "role_id": role_id,
            "task": task,
            "context": context,
            "result": result,
        },
        description=f"[{severity}] {role_name}: {summary}",
        reversible=True,
        proposed_by=role_id,
        # Adopt the agent's own trace_id so the proposal is resolvable in
        # audit.get_by_trace — UniversalAgent already logged its events under it.
        trace_id=result.get("trace_id"),
    )
    return {"result": result, "proposal": proposal.model_dump(mode="json")}


def hire(params: dict) -> dict:
    """Propose a new agent role. Never writes YAML — creates an agent_hire proposal."""
    role_id = _require_str(params, "role_id")
    if not _ROLE_ID_RE.match(role_id):
        raise RpcError(
            RPC_INVALID_PARAMS,
            "role_id must be lowercase snake_case, 2-50 chars, starting with a letter",
        )
    name = _require_str(params, "name")
    system_prompt = _require_str(params, "system_prompt")
    description = params.get("description", "")
    icon = params.get("icon") or "🤖"
    task_types = params.get("task_types", []) or []
    if not isinstance(task_types, list) or any(not isinstance(t, str) for t in task_types):
        raise RpcError(RPC_INVALID_PARAMS, "'task_types' must be a list of strings")

    if role_id in _roles():
        raise RpcError(
            RPC_INVALID_PARAMS, f"role '{role_id}' already exists in this solution"
        )

    store = _require_store()

    from src.core.proposal_store import RiskClass

    proposal = store.create(
        action_type="agent_hire",
        risk_class=RiskClass.STATEFUL,
        payload={
            "role_id": role_id,
            "name": name,
            "description": description,
            "icon": icon,
            "system_prompt": system_prompt,
            "task_types": task_types,
            # proposal_executor._execute_agent_hire resolves the YAML files from
            # this key — pass the sidecar's solution explicitly rather than
            # letting it fall back to the framework-global project_config.
            "solution": _solution(),
        },
        description=f"Hire new agent role: {icon} {name} ({role_id})",
        reversible=True,
        proposed_by="desktop-operator",
    )
    return proposal.model_dump(mode="json")


def analyze_jd(params: dict) -> dict:
    """LLM-extract a role config from a job description. Pure read — no mutation."""
    jd_text = _require_str(params, "jd_text")
    solution_context = params.get("solution_context") or ""
    if not isinstance(solution_context, str):
        raise RpcError(RPC_INVALID_PARAMS, "'solution_context' must be a string")
    if not solution_context and _project is not None:
        meta = {}
        try:
            meta = _project.metadata or {}
        except Exception:  # noqa: BLE001
            meta = {}
        solution_context = meta.get("domain") or meta.get("project") or ""

    if _jd_factory is not None:
        jd_to_role_config = _jd_factory()
    else:
        from src.core.agent_factory import jd_to_role_config

    try:
        return jd_to_role_config(jd_text, solution_context=solution_context)
    except ValueError as exc:
        raise RpcError(RPC_INVALID_PARAMS, f"could not extract a role config: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"JD analysis failed: {exc}") from exc


def get_project(params: dict) -> dict:
    """Return the parsed project.yaml for the active solution.

    No RPC returned this at all before, which left the whole YAML-first
    operator surface (ui_labels, dashboard tiles, active_modules, theme)
    unreachable from desktop. ``agents`` carries the UniversalAgent roles from
    prompts.yaml — the runnable roster the /agents/run grid is built from
    (agents.list is a different, audit-annotated view that also includes the
    four core roles, which UniversalAgent.run cannot dispatch to).
    """
    project = _require_project()
    try:
        meta = dict(project.metadata or {})
    except Exception as exc:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"could not read project.yaml: {exc}") from exc

    meta["agents"] = [
        {
            "id": role_id,
            "name": (cfg or {}).get("name", role_id),
            "description": (cfg or {}).get("description", ""),
            "icon": (cfg or {}).get("icon", "🤖"),
        }
        for role_id, cfg in _roles().items()
    ]
    return meta
