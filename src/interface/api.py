"""
SAGE[ai] - FastAPI REST Interface
===================================
HTTP API for dashboard, webhook receivers, and external integrations.

Endpoints:
  GET  /health                - System health and provider info
  POST /analyze               - Analyze a log entry
  POST /approve/{trace_id}    - Approve a pending proposal
  POST /reject/{trace_id}     - Reject with feedback
  GET  /audit                 - Query audit log
  POST /mr/create             - Create MR from issue
  POST /mr/review             - Review a merge request
  GET  /monitor/status        - Monitor agent status
  POST /webhook/teams         - Receive Teams webhook notifications
  POST /swe/task              - Submit autonomous SWE task (open-swe pattern)
"""

import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SAFE_SOLUTION_NAME = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

# ---------------------------------------------------------------------------
# Sub-routers
# ---------------------------------------------------------------------------
from src.interface.routes.data_transformation import router as _data_transformation_router  # noqa: E402
from src.interface.routes.voice_data import router as _voice_data_router  # noqa: E402
from src.interface.routes.gym import router as _gym_router  # noqa: E402
from src.interface.routes.research import router as _research_router  # noqa: E402
from src.interface.routes.critic import router as _critic_router  # noqa: E402
from src.interface.routes.product_owner import router as _product_owner_router  # noqa: E402
from src.interface.routes.cds_compliance import router as _cds_compliance_router  # noqa: E402
from src.interface.routes.regulatory_compliance import router as _regulatory_compliance_router  # noqa: E402
from src.interface.routes.functional_safety import router as _functional_safety_router  # noqa: E402

# Module-level import so tests can patch src.interface.api.reload_org_loader
try:
    from src.core.org_loader import reload_org_loader
except Exception:  # pragma: no cover
    def reload_org_loader():  # type: ignore
        pass


app = FastAPI(
    title="SAGE Framework REST API",
    description="SAGE (Smart Agentic-Guided Empowerment) — Generic Autonomous AI Agent Framework. HTTP interface for dashboard and integrations.",
    version="2.0.0",
)

# Allow web frontend (e.g. http://localhost:5173) to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Rate Limiting Middleware
# ---------------------------------------------------------------------------

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
import time as _time
import collections as _collections

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory sliding-window rate limiter.
    Limits per client IP. Returns 429 with Retry-After header when exceeded.
    Default: 120 requests per minute for write endpoints, 300 for reads.
    """

    def __init__(self, app, write_limit: int = 120, read_limit: int = 300, window: int = 60):
        super().__init__(app)
        self._write_limit = write_limit
        self._read_limit = read_limit
        self._window = window
        self._hits: dict[str, list[float]] = _collections.defaultdict(list)

    async def dispatch(self, request: StarletteRequest, call_next):
        client_ip = request.client.host if request.client else "unknown"
        # Skip rate limiting for test clients and localhost testing
        if client_ip in ("testclient", "unknown"):
            return await call_next(request)
        now = _time.time()
        cutoff = now - self._window

        # Clean old entries
        self._hits[client_ip] = [t for t in self._hits[client_ip] if t > cutoff]

        is_write = request.method in ("POST", "PUT", "PATCH", "DELETE")
        limit = self._write_limit if is_write else self._read_limit
        remaining = max(0, limit - len(self._hits[client_ip]))

        if len(self._hits[client_ip]) >= limit:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "Retry-After": str(self._window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(cutoff + self._window)),
                },
            )

        self._hits[client_ip].append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
        response.headers["X-RateLimit-Reset"] = str(int(now + self._window))
        return response


app.add_middleware(RateLimitMiddleware)

app.include_router(_data_transformation_router)
app.include_router(_voice_data_router)
app.include_router(_gym_router)
app.include_router(_research_router)
app.include_router(_critic_router)
app.include_router(_product_owner_router)
app.include_router(_cds_compliance_router)
app.include_router(_regulatory_compliance_router)
app.include_router(_functional_safety_router)


# ---------------------------------------------------------------------------
# Multi-Tenant Middleware (Phase 10)
# ---------------------------------------------------------------------------


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extracts X-SAGE-Tenant header and sets the per-request tenant context.
    This runs before every request, enabling tenant-scoped vector store
    and audit log queries downstream.
    """
    async def dispatch(self, request: StarletteRequest, call_next):
        tenant = request.headers.get("X-SAGE-Tenant", "").strip()
        if tenant:
            from src.core.tenant import set_tenant
            set_tenant(tenant)
        response = await call_next(request)
        return response


app.add_middleware(TenantMiddleware)

# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    log_entry: str


class RejectRequest(BaseModel):
    feedback: str


class MRCreateRequest(BaseModel):
    project_id: int
    issue_iid: int
    source_branch: Optional[str] = None


class MRReviewRequest(BaseModel):
    project_id: int
    mr_iid: int


class AgentRunRequest(BaseModel):
    role_id: str
    task: str
    context: str = ""
    actor: str = "web-ui"


class AgentHireRequest(BaseModel):
    role_id: str           # snake_case unique key, e.g. "security_reviewer"
    name: str              # Display name, e.g. "Security Reviewer"
    description: str       # One-line description
    icon: str = "🤖"       # Emoji icon
    system_prompt: str     # Full system prompt for this role
    task_types: List[str] = []   # Optional task type IDs to add to tasks.yaml


class AgentAnalyzeJDRequest(BaseModel):
    jd_text: str
    solution_context: str = ""


class FeatureRequestCreate(BaseModel):
    module_id: str = "general"
    module_name: str = "General"
    title: str
    description: str
    priority: str = "medium"       # low / medium / high / critical
    requested_by: str = "anonymous"
    scope: str = "solution"        # "solution" = build in your app | "sage" = improve the framework


class FeatureRequestUpdate(BaseModel):
    action: str                    # approve / reject / complete
    reviewer_note: str = ""


class ApproveProposalRequest(BaseModel):
    decided_by: str = "human"
    feedback: str = ""             # Optional approval note


class RejectProposalRequest(BaseModel):
    decided_by: str = "human"
    feedback: str = ""             # Required for DESTRUCTIVE proposals


class ChatRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    session_id: str = ""
    page_context: Optional[str] = None
    solution: str = ""


class ChatExecuteRequest(BaseModel):
    action: str
    params: dict = {}
    user_id: str = "anonymous"
    session_id: str = ""
    solution: str = ""


class BuildStartRequest(BaseModel):
    product_description: str = Field(..., min_length=10, max_length=10000)
    solution_name: str = Field("", max_length=64, pattern=r'^[a-zA-Z0-9_-]*$')
    repo_url: str = ""
    workspace_dir: str = ""
    critic_threshold: int = Field(70, ge=0, le=100)
    hitl_level: str = Field("standard", pattern=r'^(minimal|standard|strict)$')


class BuildApproveRequest(BaseModel):
    approved: bool = True
    feedback: str = ""


class ScanFolderRequest(BaseModel):
    folder_path: str
    intent: str
    solution_name: str


class RefineRequest(BaseModel):
    solution_name: str
    current_files: dict[str, str]  # {"project.yaml": str, "prompts.yaml": str, "tasks.yaml": str}
    feedback: str


class SaveSolutionRequest(BaseModel):
    solution_name: str
    files: dict[str, str]  # {"project.yaml": str, "prompts.yaml": str, "tasks.yaml": str}


# ---------------------------------------------------------------------------
# Lazy singleton accessors
# ---------------------------------------------------------------------------

def _get_analyst():
    from src.agents.analyst import analyst_agent
    return analyst_agent


def _get_developer():
    from src.agents.developer import developer_agent
    return developer_agent


def _get_monitor():
    from src.agents.monitor import monitor_agent
    return monitor_agent


def _get_audit_logger():
    from src.memory.audit_logger import audit_logger
    return audit_logger


def _get_task_queue():
    from src.core.queue_manager import task_queue
    return task_queue


def _get_proposal_store():
    from src.core.proposal_store import get_proposal_store
    return get_proposal_store()


def _get_llm_gateway():
    from src.core.llm_gateway import llm_gateway
    return llm_gateway


def _get_project_config():
    from src.core.project_loader import project_config
    return project_config


def _get_planner():
    from src.agents.planner import planner_agent
    return planner_agent


def _get_db_path() -> str:
    from src.memory.audit_logger import audit_logger
    return audit_logger.db_path


def _get_active_solution() -> str:
    try:
        return _get_project_config().project_name
    except Exception:
        return os.environ.get("SAGE_PROJECT", "default")


def _get_build_orchestrator():
    from src.integrations.build_orchestrator import build_orchestrator
    return build_orchestrator


_task_scheduler = None

def _get_task_scheduler():
    global _task_scheduler
    if _task_scheduler is None:
        from src.core.task_scheduler import TaskScheduler
        from src.core.project_loader import project_config
        _task_scheduler = TaskScheduler(
            queue_manager=_get_task_queue(),
            project_config=project_config,
        )
        _task_scheduler.start()
    return _task_scheduler


# ---------------------------------------------------------------------------
# RBAC helpers — role-based approval enforcement
# ---------------------------------------------------------------------------

def _get_required_role(action_type: str) -> Optional[str]:
    """Look up the required role for an action_type from config.yaml."""
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "config", "config.yaml")
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("approval_roles", {}).get(action_type)
    except Exception:
        return None


def _check_approver_permission(action_type: str, decided_by: str) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Passes if:
    - No required_role configured for this action_type, OR
    - The decided_by identity is in the approvers list for the required role, OR
    - The role's approvers list contains "any"
    """
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "config", "config.yaml")
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        required_role = cfg.get("approval_roles", {}).get(action_type)
        if not required_role:
            return True, ""
        approvers_cfg = cfg.get("approvers", {})
        allowed_list = approvers_cfg.get(required_role, [])
        if "any" in allowed_list:
            return True, ""
        # Hierarchical: admin can approve anything
        # Check all roles that include this user
        for role, members in approvers_cfg.items():
            if decided_by in members and role == "admin":
                return True, ""
        if decided_by in allowed_list:
            return True, ""
        return False, f"Action '{action_type}' requires role '{required_role}'. '{decided_by}' is not authorised."
    except Exception:
        return True, ""  # fail open if config unreadable


# ---------------------------------------------------------------------------
# Feature request DB initialisation (called at startup)
# ---------------------------------------------------------------------------

def _init_feature_requests_table():
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute("""
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
        """)
        # Migration: add scope column to existing databases that predate this field
        try:
            conn.execute("ALTER TABLE feature_requests ADD COLUMN scope TEXT DEFAULT 'solution'")
            conn.commit()
            logger.info("Migrated feature_requests table: added scope column.")
        except Exception:
            pass  # Column already exists
        conn.commit()
        conn.close()
        logger.info("Feature requests table ready.")
    except Exception as exc:
        logger.error("Failed to initialise feature_requests table: %s", exc)


# Register lifespan after all helpers are defined
from contextlib import asynccontextmanager

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _init_feature_requests_table()
    # Initialise ProposalStore (creates proposals table if needed)
    try:
        _get_proposal_store()
        logger.info("ProposalStore ready.")
    except Exception as exc:
        logger.warning("ProposalStore init skipped: %s", exc)
    # Initialise auth tables (api_keys, user_roles) so they're ready on first request
    try:
        from src.core.api_keys import _ensure_table as _ensure_api_keys
        from src.core.rbac import _ensure_table as _ensure_user_roles
        _ensure_api_keys()
        _ensure_user_roles()
        logger.info("Auth tables ready.")
    except Exception as exc:
        logger.warning("Auth table init skipped: %s", exc)
    yield

app.router.lifespan_context = _lifespan

# ---------------------------------------------------------------------------
# In-memory pending approvals store
# ---------------------------------------------------------------------------
_pending_proposals: dict = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/shutdown")
async def shutdown(request: Request):
    """
    Gracefully stop the SAGE backend and the Vite frontend dev server.
    Called by the web UI Stop button. Requires ADMIN role (T-D-03).
    """
    from src.core.auth import get_current_user as _get_current_user
    from src.core.rbac import require_role as _require_role, Role as _Role
    user = await _get_current_user(request)
    await _require_role(_Role.ADMIN)(user)
    import threading
    import subprocess

    def _do_shutdown():
        # Kill the Vite dev server on port 5173
        try:
            result = subprocess.run(
                ["powershell", "-NonInteractive", "-Command",
                 "Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue "
                 "| Select-Object -ExpandProperty OwningProcess "
                 "| ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"],
                timeout=5,
            )
        except Exception:
            pass
        # Exit the backend process itself
        import os
        os._exit(0)

    threading.Timer(0.3, _do_shutdown).start()
    return {"shutdown": True}


@app.get("/health")
async def health():
    """
    Health check endpoint. Returns system status and configured LLM provider.
    """
    try:
        llm = _get_llm_gateway()
        provider = llm.get_provider_name()
    except Exception as e:
        provider = f"error: {e}"

    pc = _get_project_config()
    return {
        "status": "ok",
        "service": "SAGE Framework",
        "version": "2.0.0",
        "project": pc.metadata,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "llm_provider": provider,
        "environment": {
            "gitlab_configured":  bool(os.environ.get("GITLAB_URL")),
            "teams_configured":   bool(os.environ.get("TEAMS_INCOMING_WEBHOOK_URL")),
            "metabase_configured": bool(os.environ.get("METABASE_URL")),
            "spira_configured":   bool(os.environ.get("SPIRA_URL")),
        },
    }


@app.get("/health/llm")
async def health_llm():
    """
    Heartbeat — actually pings the configured LLM with a minimal test call.
    Returns connected=True only when the LLM responds successfully.
    This is the Paperclip-style heartbeat: proves the LLM is alive, not just configured.
    """
    import time
    llm = _get_llm_gateway()
    provider = "unknown"
    try:
        provider = llm.get_provider_name()
    except Exception:
        pass

    start = time.monotonic()
    try:
        # Minimal test prompt — we just need any valid response
        response = llm.generate(
            prompt="Reply with the single word: ok",
            system_prompt="You are a health check. Reply with exactly one word.",
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        connected = bool(response and len(response.strip()) > 0)
        return {
            "connected":   connected,
            "provider":    provider,
            "latency_ms":  latency_ms,
            "detail":      "ok" if connected else "empty response",
        }
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "connected":  False,
            "provider":   provider,
            "latency_ms": latency_ms,
            "detail":     str(exc)[:200],
        }


@app.get("/config/project")
async def get_project_config():
    """
    Returns the active project's metadata: name, version, domain,
    active_modules, compliance_standards, integrations, and task_types.
    The web UI uses this to show domain-appropriate labels and modules.
    """
    pc = _get_project_config()
    return {
        **pc.metadata,
        "task_types": pc.get_task_types(),
        "task_descriptions": pc.get_task_descriptions(),
    }


@app.get("/config/projects")
async def list_projects():
    """Lists all available solutions in the solutions/ directory."""
    from src.core.project_loader import _SOLUTIONS_DIR
    import os as _os
    import yaml as _yaml
    if not _os.path.isdir(_SOLUTIONS_DIR):
        return {"projects": [], "active": _get_project_config().metadata.get("project", "")}
    projects = []
    for name in sorted(_os.listdir(_SOLUTIONS_DIR)):
        proj_yaml = _os.path.join(_SOLUTIONS_DIR, name, "project.yaml")
        if _os.path.isfile(proj_yaml):
            try:
                with open(proj_yaml, "r") as fh:
                    meta = _yaml.safe_load(fh) or {}
                projects.append({
                    "id": name,
                    "name": meta.get("name", name),
                    "domain": meta.get("domain", "general"),
                    "version": meta.get("version", "1.0.0"),
                    "description": str(meta.get("description", "")).strip(),
                    "active_modules": meta.get("active_modules", []),
                    "theme": meta.get("theme", {}),
                })
            except Exception:
                projects.append({"id": name, "name": name, "domain": "general",
                                  "version": "1.0.0", "description": "", "active_modules": [], "theme": {}})
    active = _get_project_config().metadata.get("project", "")
    return {"projects": projects, "active": active}


class SwitchProjectRequest(BaseModel):
    project: str


class SetModulesRequest(BaseModel):
    modules: list[str]


@app.post("/config/switch")
async def switch_project(req: SwitchProjectRequest):
    """
    Switch the active solution at runtime. Executes immediately — no approval gate.
    Framework-level control operations bypass the proposal queue; solution-level
    agent proposals retain full HITL approval.
    """
    from src.core.project_loader import _SOLUTIONS_DIR, project_config as _pc
    import os as _os
    proj_dir = _os.path.join(_SOLUTIONS_DIR, req.project)
    if not _os.path.isdir(proj_dir):
        raise HTTPException(status_code=404, detail=f"Solution '{req.project}' not found in {_SOLUTIONS_DIR}")
    current_project = _get_project_config().project_name
    _pc.reload(req.project)
    logger.info("Solution switched: %s → %s", current_project, req.project)
    return {
        "status":           "switched",
        "previous_project": current_project,
        "project":          req.project,
    }



@app.post("/config/modules")
async def set_modules(req: SetModulesRequest):
    """
    Update the active modules list for the current solution. Executes immediately.
    Framework control operations bypass the proposal queue.
    """
    from src.core.project_loader import project_config as _pc
    current_modules = _get_project_config().metadata.get("active_modules", [])
    _pc.set_active_modules(req.modules)
    logger.info("Modules updated: %s → %s", current_modules, req.modules)
    return {
        "status":           "updated",
        "previous_modules": current_modules,
        "active_modules":   req.modules,
    }


@app.get("/config/yaml/{file_name}")
async def read_yaml_file(file_name: str):
    """
    Read a solution YAML config file (project | prompts | tasks).
    Returns raw YAML text so the web editor can display it.
    """
    allowed = {"project", "prompts", "tasks"}
    if file_name not in allowed:
        raise HTTPException(status_code=400, detail=f"file_name must be one of: {sorted(allowed)}")
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    path = os.path.join(_SOLUTIONS_DIR, project_config.project_name, f"{file_name}.yaml")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"{file_name}.yaml not found for solution '{project_config.project_name}'")
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    return {"file": file_name, "solution": project_config.project_name, "content": content}


class YamlWriteRequest(BaseModel):
    content: str


@app.put("/config/yaml/{file_name}")
async def write_yaml_file(file_name: str, req: YamlWriteRequest):
    """
    Propose overwriting a solution YAML config file (project | prompts | tasks).
    Returns a STATEFUL proposal with a diff — actual write happens on POST /approve/{trace_id}.
    """
    import yaml as _yaml
    allowed = {"project", "prompts", "tasks"}
    if file_name not in allowed:
        raise HTTPException(status_code=400, detail=f"file_name must be one of: {sorted(allowed)}")
    try:
        _yaml.safe_load(req.content)
    except _yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    from src.core.proposal_store import RiskClass
    path = os.path.join(_SOLUTIONS_DIR, project_config.project_name, f"{file_name}.yaml")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"{file_name}.yaml not found for solution '{project_config.project_name}'")
    with open(path, "r", encoding="utf-8") as fh:
        current = fh.read()
    # Simple line-count diff summary
    old_lines = current.splitlines()
    new_lines = req.content.splitlines()
    diff_summary = f"+{len([l for l in new_lines if l not in old_lines])} / -{len([l for l in old_lines if l not in new_lines])} lines"
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "yaml_edit",
        risk_class    = RiskClass.STATEFUL,
        payload       = {
            "file":     file_name,
            "content":  req.content,
            "solution": project_config.project_name,
            "previous_content": current,
        },
        description   = f"Edit {file_name}.yaml ({diff_summary})",
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("yaml_edit"),
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
        "diff_summary": diff_summary,
        "message":     "Review the change and POST /approve/{trace_id} to apply.",
    }


@app.get("/config/skill")
async def read_skill_md():
    """
    Return the SKILL.md content for the active solution.
    Returns 404 if the solution does not use SKILL.md format.
    """
    from src.core.project_loader import project_config
    path = project_config.skill_md_path
    if not path or not os.path.isfile(path):
        raise HTTPException(
            status_code=404,
            detail=f"SKILL.md not found for solution '{project_config.project_name}'"
        )
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    return {"solution": project_config.project_name, "content": content}


class SkillWriteRequest(BaseModel):
    content: str


@app.post("/config/skill")
async def write_skill_md(req: SkillWriteRequest):
    """
    Propose overwriting the SKILL.md for the active solution and reload.
    The write is applied immediately (no approval gate) so the editor
    gets instant feedback — SKILL.md edits are lower-risk than production
    YAML changes because the file is version-controlled alongside the solution.
    """
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    path = os.path.join(_SOLUTIONS_DIR, project_config.project_name, "SKILL.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(req.content)
    project_config.reload(project_config.project_name)
    return {
        "saved": True,
        "solution": project_config.project_name,
        "message": "SKILL.md saved and solution reloaded.",
    }


@app.get("/config/approval-roles")
async def get_approval_roles():
    """Return configured approval roles and who belongs to each."""
    try:
        import yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "config", "config.yaml")
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}
        return {
            "approval_roles": cfg.get("approval_roles", {}),
            "approvers": cfg.get("approvers", {}),
        }
    except Exception as exc:
        return {"approval_roles": {}, "approvers": {}, "error": str(exc)}


@app.get("/agent/roles")
async def agent_roles():
    """List all UniversalAgent roles defined in the current solution's prompts.yaml."""
    from src.core.project_loader import project_config
    roles_cfg = project_config.get_prompts().get("roles", {})
    return {
        "roles": [
            {
                "id":          role_id,
                "name":        cfg.get("name", role_id),
                "description": cfg.get("description", ""),
                "icon":        cfg.get("icon", "🤖"),
            }
            for role_id, cfg in roles_cfg.items()
        ]
    }


@app.post("/agent/run")
async def agent_run(req: AgentRunRequest):
    """Run a UniversalAgent role against a task. Requires human approval after."""
    from src.agents.universal import UniversalAgent
    try:
        agent = UniversalAgent()
        result = agent.run(
            role_id=req.role_id,
            task=req.task,
            context=req.context,
            actor=req.actor,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("UniversalAgent run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/hire")
async def agents_hire(req: AgentHireRequest):
    """
    Propose hiring (creating) a new agent role in this solution.
    Creates a STATEFUL HITL proposal — actual YAML write on POST /approve/{trace_id}.
    """
    import re
    from src.core.proposal_store import RiskClass

    # Validate role_id format
    if not re.match(r'^[a-z][a-z0-9_]{1,49}$', req.role_id):
        raise HTTPException(
            status_code=400,
            detail="role_id must be lowercase snake_case, 2-50 chars, starting with a letter."
        )

    # Check for duplicate role
    roles_cfg = _get_project_config().get_prompts().get("roles", {})
    if req.role_id in roles_cfg:
        raise HTTPException(
            status_code=409,
            detail=f"Role '{req.role_id}' already exists in this solution."
        )

    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "agent_hire",
        risk_class    = RiskClass.STATEFUL,
        payload       = {
            "role_id":       req.role_id,
            "name":          req.name,
            "description":   req.description,
            "icon":          req.icon,
            "system_prompt": req.system_prompt,
            "task_types":    req.task_types,
            "solution":      _get_project_config().project_name,
        },
        description   = f"Hire new agent role: {req.icon} {req.name} ({req.role_id})",
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("agent_hire"),
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
        "expires_at":  proposal.expires_at.isoformat() if proposal.expires_at else None,
        "message":     "POST /approve/{trace_id} to add this role to prompts.yaml + tasks.yaml.",
    }


@app.post("/agents/analyze-jd")
async def agents_analyze_jd(req: AgentAnalyzeJDRequest):
    """
    Extract a structured agent role config from a job description using the LLM.
    Returns a preview dict ready to be passed to POST /agents/hire.
    """
    if not req.jd_text.strip():
        raise HTTPException(status_code=422, detail="jd_text must not be empty")
    try:
        from src.core.agent_factory import jd_to_role_config
        ctx = req.solution_context or ""
        if not ctx:
            try:
                pc = _get_project_config()
                ctx = getattr(pc, "domain", None) or getattr(pc, "project_name", None) or ""
            except Exception:
                pass
        config = jd_to_role_config(req.jd_text, solution_context=ctx)
        return config
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("analyze-jd error: %s", exc)
        raise HTTPException(status_code=500, detail="JD analysis failed")


@app.get("/agents/{role_key}/performance")
async def agent_performance(role_key: str):
    """
    Return approval/rejection performance stats for a specific agent role.
    Queries the compliance_audit_log for proposals associated with this role.
    """
    try:
        audit = _get_audit_logger()
        conn = sqlite3.connect(audit.db_path)
        rows = conn.execute(
            """SELECT action_type, output_content, metadata
               FROM compliance_audit_log
               WHERE actor != 'human_via_chat'
                 AND (input_context LIKE ? OR metadata LIKE ?)
               ORDER BY id DESC LIMIT 200""",
            (f"%{role_key}%", f"%{role_key}%"),
        ).fetchall()
        conn.close()
    except Exception as exc:
        logger.warning("agent_performance query error: %s", exc)
        rows = []

    total = len(rows)
    approved = sum(1 for r in rows if "APPROVE" in (r[0] or "").upper() or "approved" in (r[1] or "").lower())
    rejected = sum(1 for r in rows if "REJECT" in (r[0] or "").upper() or "rejected" in (r[1] or "").lower())

    return {
        "role_key": role_key,
        "total_proposals": total,
        "approved": approved,
        "rejected": rejected,
        "approval_rate": round(approved / total * 100, 1) if total > 0 else None,
    }


@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """
    Analyzes a log entry using the Analyst Agent.

    Request body: {"log_entry": "..."}

    Returns AI analysis proposal with trace_id for approval/rejection.
    """
    if not request.log_entry.strip():
        raise HTTPException(status_code=400, detail="log_entry cannot be empty.")

    try:
        analyst = _get_analyst()
        result = analyst.analyze_log(request.log_entry)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Store for potential approval
        trace_id = result.get("trace_id")
        if trace_id:
            _pending_proposals[trace_id] = {
                "type": "analysis",
                "proposal": result,
                "log_entry": request.log_entry,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
            }
            # Notify Teams for approval (best-effort)
            try:
                from src.interface.teams_bot import teams_bot
                teams_bot.send_approval_request(trace_id, result, "http://localhost:8000")
            except Exception:
                pass

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analyze endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/proposals/pending")
async def get_pending_proposals():
    """
    Returns all proposals currently awaiting human approval.
    Used by the Dashboard Pending Approvals panel.
    """
    store = _get_proposal_store()
    proposals = store.get_pending()
    return {
        "proposals": [p.model_dump() for p in proposals],
        "count": len(proposals),
    }


@app.get("/proposals/{trace_id}")
async def get_proposal(trace_id: str):
    """
    Returns a single proposal by trace_id (any status).
    Used by the Improvements page to show plan details.
    """
    store = _get_proposal_store()
    proposal = store.get(trace_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
    return proposal.model_dump()


class BatchApproveRequest(BaseModel):
    trace_ids: list[str]
    decided_by: str = "human"
    feedback: str = ""


@app.post("/proposals/approve-batch")
async def approve_batch(body: BatchApproveRequest):
    """
    Approve multiple proposals at once. Skips any that fail role checks.
    Returns per-proposal results.
    """
    from src.core.proposal_executor import execute_approved_proposal
    store = _get_proposal_store()
    results = []
    for trace_id in body.trace_ids:
        proposal = store.get(trace_id)
        if not proposal or proposal.status != "pending":
            results.append({"trace_id": trace_id, "status": "skipped", "reason": "not found or not pending"})
            continue
        allowed, reason = _check_approver_permission(proposal.action_type, body.decided_by)
        if not allowed:
            results.append({"trace_id": trace_id, "status": "forbidden", "reason": reason})
            continue
        try:
            approved = store.approve(trace_id, decided_by=body.decided_by, feedback=body.feedback)
            result = await execute_approved_proposal(approved)
            results.append({"trace_id": trace_id, "status": "approved", "result": result})
        except Exception as exc:
            results.append({"trace_id": trace_id, "status": "error", "reason": str(exc)})
    return {"results": results, "count": len(results)}


@app.post("/approve/{trace_id}")
async def approve(trace_id: str, request: Request, body: ApproveProposalRequest = ApproveProposalRequest(),
                  background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Approve a pending proposal.

    For analysis proposals: records approval in audit log.
    For action proposals (yaml_edit, llm_switch, etc.): executes the action.
    For long-running actions (implementation_plan, code_diff): execution fires in background.

    Args:
        trace_id: The trace ID from a previous proposal response.
    """
    from src.modules.trace_id import is_valid as _is_valid_trace
    if not _is_valid_trace(trace_id):
        raise HTTPException(status_code=400, detail="Invalid trace_id format — must be a valid UUID.")
    from src.core.proposal_executor import execute_approved_proposal
    from src.core.auth import optional_auth as _optional_auth

    # Capture identity when auth is enabled (transparent when auth.enabled: false)
    auth_user = await _optional_auth(request)

    # Long-running action types that must run in background to avoid blocking the request
    _BACKGROUND_TYPES = {"implementation_plan", "code_diff"}

    # --- Check ProposalStore first (HITL action proposals) ---
    store = _get_proposal_store()
    proposal = store.get(trace_id)
    if proposal and proposal.status == "pending":
        # Role-based approval check
        allowed, reason = _check_approver_permission(proposal.action_type, body.decided_by)
        if not allowed:
            raise HTTPException(status_code=403, detail=reason)
        approved = store.approve(trace_id, decided_by=body.decided_by, feedback=body.feedback, user=auth_user)

        # Auto-update linked feature_request to in_progress
        try:
            db_path = _get_db_path()
            _conn = sqlite3.connect(db_path)
            _conn.execute(
                "UPDATE feature_requests SET status='in_progress', updated_at=? WHERE plan_trace_id=?",
                (datetime.now(timezone.utc).isoformat(), trace_id),
            )
            _conn.commit()
            _conn.close()
        except Exception as _e:
            logger.warning("Could not auto-update feature request for trace_id=%s: %s", trace_id, _e)

        if approved.action_type in _BACKGROUND_TYPES:
            # Fire-and-forget: return immediately, run execution in background
            async def _bg_exec():
                try:
                    result = await execute_approved_proposal(approved)
                    _get_audit_logger().log_event(
                        actor=body.decided_by,
                        action_type="PROPOSAL_APPROVED",
                        input_context=f"trace_id={trace_id} action={approved.action_type}",
                        output_content=json.dumps(result),
                        metadata={"trace_id": trace_id, "risk_class": approved.risk_class.value},
                        approved_by=auth_user.name if auth_user else body.decided_by,
                        approver_role=auth_user.role if auth_user else "",
                        approver_email=auth_user.email if auth_user else "",
                        approver_provider=auth_user.provider if auth_user else "",
                    )
                except Exception as exc:
                    logger.error("Background execution failed for %s: %s", trace_id, exc)

            import asyncio
            asyncio.ensure_future(_bg_exec())
            return {
                "status": "approved",
                "trace_id": trace_id,
                "action_type": approved.action_type,
                "result": {"message": "Execution started in background. Check Dashboard for code_diff proposals."},
            }

        # Execute the action synchronously (fast actions)
        try:
            result = await execute_approved_proposal(approved)
        except Exception as exc:
            logger.error("Proposal execution failed after approval: %s", exc)
            raise HTTPException(status_code=500, detail=f"Proposal approved but execution failed: {exc}")
        # Audit the approval
        try:
            _get_audit_logger().log_event(
                actor=body.decided_by,
                action_type="PROPOSAL_APPROVED",
                input_context=f"trace_id={trace_id} action={approved.action_type}",
                output_content=json.dumps(result),
                metadata={"trace_id": trace_id, "risk_class": approved.risk_class.value},
                approved_by=auth_user.name if auth_user else body.decided_by,
                approver_role=auth_user.role if auth_user else "",
                approver_email=auth_user.email if auth_user else "",
                approver_provider=auth_user.provider if auth_user else "",
            )
        except Exception as e:
            logger.error("Audit log failed on approve: %s", e)
        return {
            "status": "approved",
            "trace_id": trace_id,
            "action_type": approved.action_type,
            "result": result,
        }

    # --- Fallback: legacy in-memory analysis proposals ---
    if trace_id not in _pending_proposals:
        raise HTTPException(status_code=404, detail=f"Trace ID '{trace_id}' not found or already processed.")

    proposal_entry = _pending_proposals[trace_id]
    proposal_entry["status"] = "approved"
    try:
        audit = _get_audit_logger()
        audit.log_event(
            actor=body.decided_by,
            action_type="APPROVAL",
            input_context=f"trace_id={trace_id}",
            output_content=json.dumps(proposal_entry["proposal"]),
            metadata={"trace_id": trace_id, "approved_via": "api"},
        )
    except Exception as e:
        logger.error("Audit log failed on approve: %s", e)

    del _pending_proposals[trace_id]
    logger.info("Analysis proposal approved: trace_id=%s", trace_id)
    return {
        "status": "approved",
        "trace_id": trace_id,
        "message": "Proposal approved and logged.",
    }


@app.post("/reject/{trace_id}")
async def reject(trace_id: str, http_request: Request, request: RejectRequest):
    """
    Reject a pending proposal with human feedback.

    For analysis proposals: stores feedback in vector memory for learning.
    For action proposals: marks rejected, no action taken.

    Request body: {"feedback": "The real root cause is..."}
    """
    from src.modules.trace_id import is_valid as _is_valid_trace
    if not _is_valid_trace(trace_id):
        raise HTTPException(status_code=400, detail="Invalid trace_id format — must be a valid UUID.")
    from src.core.auth import optional_auth as _optional_auth

    # Capture identity when auth is enabled (transparent when auth.enabled: false)
    auth_user = await _optional_auth(http_request)

    # --- Check ProposalStore first (HITL action proposals) ---
    store = _get_proposal_store()
    proposal = store.get(trace_id)
    if proposal and proposal.status == "pending":
        rejected = store.reject(trace_id, decided_by="human", feedback=request.feedback, user=auth_user)
        try:
            _get_audit_logger().log_event(
                actor="human",
                action_type="PROPOSAL_REJECTED",
                input_context=f"trace_id={trace_id} action={proposal.action_type}",
                output_content=request.feedback,
                metadata={"trace_id": trace_id, "risk_class": proposal.risk_class.value},
                approved_by=auth_user.name if auth_user else "human",
                approver_role=auth_user.role if auth_user else "",
                approver_email=auth_user.email if auth_user else "",
                approver_provider=auth_user.provider if auth_user else "",
            )
        except Exception as e:
            logger.error("Audit log failed on reject: %s", e)
        # Store rejection feedback in long-term memory for compounding intelligence
        if request.feedback:
            try:
                from src.memory.long_term_memory import long_term_memory
                long_term_memory.remember(
                    f"Rejected {proposal.action_type}: {request.feedback}",
                    user_id=auth_user.name if auth_user else "human",
                    metadata={"trace_id": trace_id, "action_type": proposal.action_type},
                )
            except Exception:
                pass  # long-term memory is non-critical
        # If rejecting a code_diff proposal, revert the working tree
        if rejected and rejected.action_type == "code_diff":
            try:
                from src.core.proposal_executor import _revert_code_diff
                import asyncio
                asyncio.create_task(_revert_code_diff(rejected))
            except Exception as _rev_exc:
                logger.warning("code_diff revert failed: %s", _rev_exc)
        return {
            "status": "rejected",
            "trace_id": trace_id,
            "feedback_recorded": True,
        }

    # --- Fallback: legacy in-memory analysis proposals ---
    if trace_id not in _pending_proposals:
        raise HTTPException(status_code=404, detail=f"Trace ID '{trace_id}' not found or already processed.")

    proposal_entry = _pending_proposals[trace_id]
    proposal_entry["status"] = "rejected"
    try:
        analyst = _get_analyst()
        analyst.learn_from_feedback(
            log_entry=proposal_entry.get("log_entry", ""),
            human_comment=request.feedback,
            original_analysis=proposal_entry.get("proposal", {}),
        )
    except Exception as e:
        logger.error("Learning from feedback failed: %s", e)

    del _pending_proposals[trace_id]
    logger.info("Analysis proposal rejected: trace_id=%s", trace_id)
    return {
        "status": "rejected",
        "trace_id": trace_id,
        "feedback_recorded": True,
        "message": "Feedback learned and stored for future improvements.",
    }


@app.post("/proposals/{trace_id}/undo")
async def undo_proposal(trace_id: str):
    """
    Undo an approved proposal. Currently supports code_diff action type.
    Returns 404 if not found, 409 if still pending (not yet approved).
    """
    store = _get_proposal_store()
    proposal = store.get(trace_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
    if proposal.status == "pending":
        raise HTTPException(status_code=409, detail="Cannot undo a pending proposal. Reject it instead.")
    if proposal.action_type == "code_diff":
        try:
            from src.core.proposal_executor import _revert_code_diff
            import asyncio
            asyncio.ensure_future(_revert_code_diff(proposal))
            _get_audit_logger().log_event(
                actor="human",
                action_type="PROPOSAL_UNDONE",
                input_context=f"trace_id={trace_id} action={proposal.action_type}",
                output_content="Undo requested for approved code_diff",
                metadata={"trace_id": trace_id},
            )
            return {"status": "undo_triggered", "trace_id": trace_id, "action_type": proposal.action_type}
        except Exception as exc:
            logger.error("Undo failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))
    return {"status": "not_undoable", "trace_id": trace_id, "reason": f"{proposal.action_type} is not reversible via undo."}


@app.get("/audit")
async def get_audit(limit: int = 50, offset: int = 0):
    """
    Returns audit log entries.

    Query params:
      limit:  Number of records (default 50, max 500)
      offset: Pagination offset (default 0)
    """
    limit = min(limit, 500)

    try:
        import sqlite3
        audit = _get_audit_logger()
        conn = sqlite3.connect(audit.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM compliance_audit_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        total = cursor.execute("SELECT COUNT(*) FROM compliance_audit_log").fetchone()[0]
        conn.close()

        return {
            "entries": rows,
            "count": len(rows),
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error("Audit query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mr/create")
async def create_mr(request: MRCreateRequest):
    """
    Creates a GitLab merge request from an issue using the Developer Agent.

    Request body: {"project_id": 123, "issue_iid": 45}
    """
    try:
        dev = _get_developer()
        result = dev.create_mr_from_issue(
            project_id=request.project_id,
            issue_iid=request.issue_iid,
            source_branch=request.source_branch,
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        # Notify Teams channel about new MR (best-effort)
        try:
            from src.interface.teams_bot import teams_bot
            teams_bot.send_mr_created(
                mr_url=result.get("web_url", ""),
                issue_title=result.get("title", f"Issue #{request.issue_iid}"),
            )
        except Exception:
            pass  # Teams notification is non-critical

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("MR create endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mr/review")
async def review_mr(request: MRReviewRequest):
    """
    Reviews a GitLab merge request using the Developer Agent.

    Request body: {"project_id": 123, "mr_iid": 7}
    """
    try:
        dev = _get_developer()
        result = dev.review_merge_request(
            project_id=request.project_id,
            mr_iid=request.mr_iid,
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("MR review endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/monitor/status")
async def monitor_status():
    """
    Returns the current status of the Monitor Agent and its polling threads.
    """
    try:
        monitor = _get_monitor()
        return monitor.get_status()
    except Exception as e:
        logger.error("Monitor status endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduler/status")
async def get_scheduler_status():
    """Returns task scheduler running state and schedule count."""
    try:
        sched = _get_task_scheduler()
        return sched.status()
    except Exception as exc:
        return {"running": False, "error": str(exc)}


@app.post("/webhook/teams")
async def teams_webhook(request: Request):
    """
    Receives incoming Teams webhook notifications (approval callbacks).
    Called when a user clicks Approve/Reject buttons in a Teams adaptive card.
    """
    try:
        body = await request.json()
        logger.info("Teams webhook received: %s", json.dumps(body)[:200])

        # Audit the incoming webhook
        try:
            audit = _get_audit_logger()
            audit.log_event(
                actor="Teams_Webhook",
                action_type="WEBHOOK_RECEIVED",
                input_context=json.dumps(body)[:500],
                output_content="Webhook processed",
                metadata={"source": "teams"},
            )
        except Exception:
            pass

        return {"status": "received", "message": "Webhook processed by SAGE[ai]."}

    except Exception as e:
        logger.error("Teams webhook processing error: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {e}")


# ---------------------------------------------------------------------------
# n8n Webhook Receiver (Phase 2)
# ---------------------------------------------------------------------------

@app.post("/webhook/n8n")
async def n8n_webhook(request: Request):
    """
    Receives event payloads from n8n workflows and routes them to the
    SAGE task queue. Replaces manual polling for any system n8n can watch.

    Expected body (all fields optional except event_type):
      {
        "event_type": "log_alert" | "code_review" | "monitor" | "custom",
        "payload":    { ... task-specific arguments ... },
        "source":     "string — which n8n workflow or system fired this",
        "priority":   1-10  (default: 5)
      }

    HMAC validation: If N8N_WEBHOOK_SECRET env var is set, the request
    must include X-SAGE-Signature: sha256=<hmac> header.
    """
    import hashlib
    import hmac as hmac_lib

    # --- HMAC signature validation ---
    secret = os.environ.get("N8N_WEBHOOK_SECRET", "").encode()
    if secret:
        sig_header = request.headers.get("X-SAGE-Signature", "")
        raw_body   = await request.body()
        expected   = "sha256=" + hmac_lib.new(secret, raw_body, hashlib.sha256).hexdigest()
        if not hmac_lib.compare_digest(sig_header, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        body = json.loads(raw_body)
    else:
        body = await request.json()

    event_type = body.get("event_type", "")
    payload    = body.get("payload", {})
    source     = body.get("source", "n8n")
    priority   = int(body.get("priority", 5))

    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")

    # Map n8n event types to SAGE task types
    _EVENT_TO_TASK = {
        "log_alert":    "ANALYZE_LOG",
        "code_review":  "REVIEW_MR",
        "create_mr":    "CREATE_MR",
        "monitor":      "MONITOR_CHECK",
        "plan":         "PLAN_TASK",
        "workflow":     "WORKFLOW",
        "code_task":    "CODE_TASK",
    }

    task_type = _EVENT_TO_TASK.get(event_type, event_type.upper())

    # Audit first — log before touching the queue
    try:
        audit = _get_audit_logger()
        audit.log_event(
            actor=f"n8n_webhook/{source}",
            action_type="WEBHOOK_RECEIVED",
            input_context=json.dumps(body)[:500],
            output_content=f"Routing to task_type={task_type}",
            metadata={"source": source, "event_type": event_type, "priority": priority},
        )
    except Exception as e:
        logger.warning("Audit log failed for n8n webhook: %s", e)

    # Submit to task queue
    try:
        queue = _get_task_queue()
        task_id = queue.submit(task_type=task_type, payload=payload, priority=priority)
        logger.info("n8n webhook → task %s queued (id: %s)", task_type, task_id)
        return {
            "status": "queued",
            "task_id": task_id,
            "task_type": task_type,
            "source": source,
        }
    except Exception as e:
        logger.error("n8n webhook queue submission failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {e}")


@app.get("/queue/tasks")
async def list_queue_tasks(
    status: str = None,
    source: str = None,
    limit: int = 100,
):
    """
    List all tasks in the task queue, with optional status/source filters.
    Joins with feature_requests on plan_trace_id to include feature title and scope.
    """
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        where_clauses = []
        params: list = []
        if status:
            where_clauses.append("t.status = ?")
            params.append(status)
        if source:
            where_clauses.append("t.source = ?")
            params.append(source)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        params.append(limit)

        rows = conn.execute(
            f"""
            SELECT
                t.task_id, t.task_type, t.payload, t.priority,
                t.status, t.created_at, t.started_at, t.completed_at,
                t.result, t.error, t.plan_trace_id, t.source,
                fr.title  AS feature_title,
                fr.scope  AS feature_scope
            FROM task_queue t
            LEFT JOIN feature_requests fr ON fr.plan_trace_id = t.plan_trace_id
                AND t.plan_trace_id IS NOT NULL AND t.plan_trace_id != ''
            {where_sql}
            ORDER BY t.created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        conn.close()

        tasks = []
        for row in rows:
            task = dict(row)
            # Decode JSON payload safely
            try:
                task["payload"] = json.loads(task["payload"]) if task["payload"] else {}
            except Exception:
                task["payload"] = {}
            # Decode JSON result safely
            try:
                task["result"] = json.loads(task["result"]) if task["result"] else None
            except Exception:
                task["result"] = task["result"]
            tasks.append(task)

        return tasks
    except Exception as exc:
        # Return empty list if table doesn't exist yet (no tasks submitted)
        if "no such table" in str(exc):
            return []
        logger.error("list_queue_tasks error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/tasks/{task_id}/subtasks")
async def get_task_subtasks(task_id: str):
    """Return all tasks that were spawned as subtasks of task_id."""
    try:
        qm = _get_task_queue()
        all_tasks = qm.get_all_tasks()   # returns list of dicts
        children = [
            {
                "task_id":    t["task_id"],
                "task_type":  t["task_type"],
                "status":     t["status"],
                "wave":       (t.get("metadata") or {}).get("wave", 0),
                "depends_on": t.get("depends_on", []),
            }
            for t in all_tasks
            if (t.get("metadata") or {}).get("parent_task_id") == task_id
        ]
        return {"task_id": task_id, "subtasks": children}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/tasks/submit")
async def submit_task(request: Request):
    """
    Submit a task to the active solution's queue, or route to another team's queue.
    Requires cross_team_routes permission for cross-team routing.
    """
    body = await request.json()
    task_type = body.get("task_type", "").strip()
    if not task_type:
        raise HTTPException(status_code=400, detail="task_type is required")

    payload    = body.get("payload", {})
    priority   = int(body.get("priority", 5))
    target_sol = body.get("target_solution", "").strip() or None
    source_sol = body.get("source_solution", "").strip() or None

    from src.core.org_loader import org_loader as _org_loader
    from src.core.queue_manager import get_task_queue, task_queue as _default_queue

    if target_sol:
        # Resolve solutions dir live so env-var overrides (e.g. in tests) are respected
        from src.core.project_loader import _PROJECT_ROOT as _proj_root
        _sols_dir = os.environ.get(
            "SAGE_SOLUTIONS_DIR",
            os.path.join(_proj_root, "solutions"),
        )

        # Resolve source identity (3-step per spec)
        if not source_sol:
            tenant = request.headers.get("X-SAGE-Tenant", "").strip()
            if tenant and os.path.isdir(os.path.join(_sols_dir, tenant)):
                source_sol = tenant
            else:
                source_sol = _get_active_solution()

        # Validate target exists on disk
        if not os.path.isdir(os.path.join(_sols_dir, target_sol)):
            raise HTTPException(status_code=404, detail=f"target_solution '{target_sol}' not found")

        # Validate routing permission
        if _org_loader.org_name and not _org_loader.is_route_allowed(source_sol, target_sol):
            raise HTTPException(
                status_code=403,
                detail=f"solution '{source_sol}' is not permitted to route tasks to '{target_sol}'",
            )

        queue = get_task_queue(target_sol)
        task_id = queue.submit(
            task_type, payload,
            priority=priority,
            source="cross_team_route",
            metadata={"source_solution": source_sol, "target_solution": target_sol},
        )
        return {"task_id": task_id, "target_solution": target_sol, "status": "queued"}
    else:
        task_id = _default_queue.submit(task_type, payload, priority=priority, source="api")
        from src.core.project_loader import project_config as _pc
        return {"task_id": task_id, "target_solution": _pc.project_name, "status": "queued"}


@app.get("/queue/status")
async def get_queue_status():
    """
    Returns real-time queue summary including parallel execution state.

    Response fields:
      pending_count:   Tasks waiting to be dispatched.
      parallel_mode:   Whether parallel wave execution is currently active.
      active_wave:     Current wave number (0 when idle).
      wave_size:       Number of tasks in the current wave (0 when idle).
      parallel_enabled: Whether the parallel runner is configured as enabled.
      max_workers:     Configured thread pool size.
    """
    try:
        from src.core.queue_manager import task_queue, parallel_runner
        return {
            "pending_count": task_queue.get_pending_count(),
            "parallel_mode": parallel_runner.parallel_active,
            "active_wave": parallel_runner.active_wave,
            "wave_size": parallel_runner.wave_size,
            "parallel_enabled": parallel_runner.config.parallel_enabled,
            "max_workers": parallel_runner.config.max_workers,
        }
    except Exception as exc:
        logger.error("queue/status error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/queue/config")
async def set_queue_config(max_workers: int = 4, parallel_enabled: bool = True):
    """
    Adjust parallel execution settings at runtime.

    Query / body params:
      max_workers:      Max threads in the wave executor pool (min 1).
      parallel_enabled: Set false to revert all solutions to single-lane
                        sequential execution (compliance solutions are always
                        sequential regardless of this flag).

    Returns the updated configuration.
    """
    try:
        from src.core.queue_manager import parallel_runner
        parallel_runner.config.max_workers = max_workers
        parallel_runner.config.parallel_enabled = parallel_enabled
        logger.info(
            "Queue config updated: max_workers=%d parallel_enabled=%s",
            parallel_runner.config.max_workers,
            parallel_runner.config.parallel_enabled,
        )
        return {
            "status": "updated",
            "config": parallel_runner.config.to_dict(),
        }
    except Exception as exc:
        logger.error("queue/config error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/mr/open")
async def list_open_mrs(project_id: int):
    """
    Lists all open merge requests for a GitLab project.

    Query params:
      project_id: GitLab project numeric ID
    """
    try:
        dev = _get_developer()
        result = dev.list_open_mrs(project_id=project_id)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MR open list endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/mr/pipeline")
async def get_pipeline_status(project_id: int, mr_iid: int):
    """
    Returns the CI/CD pipeline status for a merge request.

    Query params:
      project_id: GitLab project numeric ID
      mr_iid:     Merge Request internal ID (IID)
    """
    try:
        dev = _get_developer()
        result = dev.get_pipeline_status(project_id=project_id, mr_iid=mr_iid)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MR pipeline status endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/developer/propose-patch")
async def developer_propose_patch(request: Request):
    """
    Use the Developer Agent to propose a code patch for a file error.

    Request body: {"file_path": "src/foo.py", "error_description": "...", "current_code": "..."}
    """
    body = await request.json()
    file_path = body.get("file_path", "")
    error_description = body.get("error_description", "")
    current_code = body.get("current_code", "")
    if not file_path or not error_description:
        raise HTTPException(status_code=422, detail="file_path and error_description are required")
    try:
        dev = _get_developer()
        result = dev.propose_code_patch(file_path, error_description, current_code)
        return result
    except Exception as e:
        logger.error("Propose patch error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/mr/comment")
async def mr_add_comment(request: Request):
    """
    Post a comment on a GitLab merge request.

    Request body: {"project_id": 123, "mr_iid": 7, "comment": "LGTM"}
    """
    body = await request.json()
    project_id = body.get("project_id")
    mr_iid = body.get("mr_iid")
    comment = body.get("comment", "")
    if not project_id or not mr_iid or not comment:
        raise HTTPException(status_code=422, detail="project_id, mr_iid, and comment are required")
    try:
        dev = _get_developer()
        result = dev.add_mr_comment(int(project_id), int(mr_iid), comment)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MR comment error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/planner/status")
async def planner_plan_status(request: Request):
    """
    Get the execution status of plan tasks.

    Request body: {"task_ids": ["tid-001", "tid-002", ...]}
    """
    body = await request.json()
    task_ids = body.get("task_ids", [])
    if not task_ids:
        raise HTTPException(status_code=422, detail="task_ids list is required")
    try:
        from src.agents.planner import planner_agent
        return {"statuses": planner_agent.get_plan_status(task_ids)}
    except Exception as e:
        logger.error("Plan status error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Module Improvement / Feature Request Endpoints
# ---------------------------------------------------------------------------

@app.post("/feedback/feature-request")
async def submit_feature_request(request: FeatureRequestCreate):
    """
    Submit a UI module improvement request from any user.

    During development this is open to all. Post-release, wrap with
    authentication middleware to enforce role-based access.
    """
    req_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT INTO feature_requests
               (id, module_id, module_name, title, description, priority,
                status, requested_by, scope, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (req_id, request.module_id, request.module_name, request.title,
             request.description, request.priority, request.requested_by,
             request.scope, now, now),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to store feature request: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    # Audit trail
    try:
        audit = _get_audit_logger()
        audit.log_event(
            actor=request.requested_by,
            action_type="FEATURE_REQUEST_SUBMITTED",
            input_context=f"scope={request.scope} module={request.module_id} title={request.title}",
            output_content=request.description,
            metadata={"request_id": req_id, "module_id": request.module_id,
                      "priority": request.priority, "scope": request.scope},
        )
    except Exception as e:
        logger.warning("Audit log failed for feature request: %s", e)

    return {
        "id": req_id,
        "status": "pending",
        "message": "Feature request submitted. The engineering team will review it.",
    }


@app.get("/feedback/feature-requests")
async def list_feature_requests(
    module_id: Optional[str] = None,
    status: Optional[str] = None,
    scope: Optional[str] = None,   # "solution" | "sage"
):
    """
    List feature requests, optionally filtered by module_id, status, or scope.
    scope="solution" returns items for the active solution's backlog.
    scope="sage"     returns SAGE framework improvement ideas.
    """
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM feature_requests WHERE 1=1"
        params: list = []
        if module_id:
            query += " AND module_id = ?"
            params.append(module_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if scope:
            query += " AND scope = ?"
            params.append(scope)
        query += " ORDER BY created_at DESC"

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        conn.close()
        return {"requests": rows, "count": len(rows)}

    except Exception as e:
        logger.error("Feature request list error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback/feature-requests/{req_id}/plan")
async def generate_plan_for_request(req_id: str):
    """
    Triggers the Planner Agent to generate an implementation plan for a
    feature request. Sets the request status to 'in_planning'.
    """
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM feature_requests WHERE id = ?", (req_id,)
        ).fetchone()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Feature request not found.")

        req = dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    scope = req.get('scope', 'solution')
    now = datetime.now(timezone.utc).isoformat()

    # SAGE framework improvements go through GitHub PRs, not the internal approval queue.
    if scope == "sage":
        import urllib.parse
        from src.core.config_loader import load_config as _load_cfg
        _cfg = _load_cfg()
        github_repo = (
            _cfg.get("github", {}).get("repo_url", "").rstrip("/")
            or "https://github.com/Sumanharapanahalli/SAGE"
        )
        issue_title = urllib.parse.quote(req["title"])
        issue_body = urllib.parse.quote(
            f"## Description\n{req['description']}\n\n"
            f"**Priority:** {req['priority']}\n\n"
            f"---\n*Submitted via SAGE Improvements*"
        )
        github_url = f"{github_repo}/issues/new?title={issue_title}&body={issue_body}&labels=enhancement"
        try:
            db_path = _get_db_path()
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE feature_requests SET status='github_pr', updated_at=? WHERE id=?",
                (now, req_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("DB update failed for github_pr status: %s", e)
        return {
            "request_id":       req_id,
            "status":           "github_pr",
            "github_issue_url": github_url,
            "message":          "SAGE framework improvements are contributed via GitHub. Use the link to open an issue or PR.",
        }

    # Solution-scope: run planner and create a HITL approval proposal as normal.
    planner_task = (
        "This is a SOLUTION feature — implement in the active solution's codebase.\n"
        f"Title: {req['title']}\n"
        f"Description: {req['description']}\n"
        f"Priority: {req['priority']}"
    )

    try:
        planner = _get_planner()
        steps = planner.create_plan(planner_task)
    except Exception as e:
        logger.error("Planner failed for feature request %s: %s", req_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    if not steps:
        raise HTTPException(status_code=422, detail="LLM could not produce an executable plan. Try rephrasing the description.")

    from src.core.proposal_store import RiskClass
    store = _get_proposal_store()
    proposal = store.create(
        action_type="implementation_plan",
        risk_class=RiskClass.STATEFUL,
        payload={
            "description": planner_task,
            "steps": steps,
            "scope": scope,
            "feature_request_id": req_id,
        },
        description=f"Implementation plan: {req['title']}",
        reversible=False,
        proposed_by="PlannerAgent",
        required_role=_get_required_role("implementation_plan"),
    )

    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE feature_requests SET status='in_planning', plan_trace_id=?, updated_at=? WHERE id=?",
            (proposal.trace_id, now, req_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("DB update failed after planning: %s", e)

    return {
        "request_id": req_id,
        "status":     "in_planning",
        "trace_id":   proposal.trace_id,
        "step_count": len(steps),
        "plan":       steps,
    }


@app.patch("/feedback/feature-requests/{req_id}")
async def update_feature_request(req_id: str, body: FeatureRequestUpdate):
    """
    Update the status of a feature request (approve / reject / complete).
    """
    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "complete": "completed",
    }
    new_status = status_map.get(body.action.lower(), "pending")
    now = datetime.now(timezone.utc).isoformat()

    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE feature_requests SET status=?, reviewer_note=?, updated_at=? WHERE id=?",
            (new_status, body.reviewer_note, now, req_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        audit = _get_audit_logger()
        audit.log_event(
            actor="Human_Engineer",
            action_type="FEATURE_REQUEST_UPDATED",
            input_context=f"req_id={req_id} action={body.action}",
            output_content=body.reviewer_note,
            metadata={"request_id": req_id, "new_status": new_status},
        )
    except Exception as e:
        logger.warning("Audit log failed for feature request update: %s", e)

    return {"id": req_id, "status": new_status, "reviewer_note": body.reviewer_note}


# ===========================================================================
# LLM Management Endpoints
# ===========================================================================

@app.get("/llm/status")
async def llm_status():
    """
    Returns current LLM provider info and session usage statistics.
    Token counts are estimated (Gemini CLI does not expose exact usage).
    """
    from src.core.llm_gateway import llm_gateway
    from datetime import datetime, timezone

    usage = llm_gateway.get_usage()
    model_info = llm_gateway.get_model_info()
    now = datetime.now(timezone.utc).isoformat()

    # --- PII filter status ---
    import yaml as _yaml
    _config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "config.yaml",
    )
    _full_cfg: dict = {}
    try:
        with open(_config_path, "r") as _f:
            _full_cfg = _yaml.safe_load(_f) or {}
    except Exception:
        pass
    _pii_cfg = _full_cfg.get("pii", {})
    _dr_cfg = _full_cfg.get("data_residency", {})

    return {
        "provider": llm_gateway.get_provider_name(),
        "model_info": model_info,
        "session": {
            "started_at": usage["started_at"],
            "current_time": now,
            "calls_made": usage["calls"],
            "calls_today": usage["calls_today"],
            "day_started_at": usage["day_started_at"],
            "estimated_tokens": usage["estimated_tokens"],
            "errors": usage["errors"],
        },
        "config": {
            "minimal_mode": bool(os.environ.get("SAGE_MINIMAL", "") in ("1", "true", "yes")),
            "project": _get_project_config().project_name or os.environ.get("SAGE_PROJECT", ""),
        },
        "pii_filter": {
            "enabled":          _pii_cfg.get("enabled", False),
            "mode":             _pii_cfg.get("mode", "redact"),
            "entities":         _pii_cfg.get("entities", []),
            "fail_on_detection": _pii_cfg.get("fail_on_detection", False),
        },
        "data_residency": {
            "enabled": _dr_cfg.get("enabled", False),
            "region":  _dr_cfg.get("region", "us"),
        },
    }


@app.get("/llm/routing-stats")
async def llm_routing_stats():
    """Return complexity-based routing statistics."""
    from src.core.llm_gateway import llm_gateway
    stats = getattr(llm_gateway, "_routing_stats", {"low": 0, "medium": 0, "high": 0})
    total = sum(stats.values())
    return {
        "routing_stats": stats,
        "total_classified": total,
        "distribution": {k: round(v / total * 100, 1) if total > 0 else 0 for k, v in stats.items()},
    }


class LLMSwitchRequest(BaseModel):
    provider: str   # "gemini" | "local" | "claude-code" | "claude"
    model: Optional[str] = None   # gemini model name, GGUF path, or claude model name
    api_key: Optional[str] = None  # Anthropic API key (claude only, stored in env)
    claude_path: Optional[str] = None  # Custom path to claude.exe (claude-code only)
    save_as_default: bool = False  # If True, persist selection to config.yaml


@app.post("/llm/switch")
async def llm_switch(req: LLMSwitchRequest):
    """
    Switch the LLM provider at runtime. Executes immediately — no approval gate.
    Framework control operations bypass the proposal queue.
    """
    from types import SimpleNamespace
    from src.core.proposal_executor import _execute_llm_switch as _do_llm_switch
    allowed = ("gemini", "local", "claude-code", "claude", "ollama", "generic-cli")
    if req.provider not in allowed:
        raise HTTPException(status_code=400, detail=f"provider must be one of: {allowed}")
    current_provider = _get_llm_gateway().get_provider_name()
    fake = SimpleNamespace(payload={
        "provider":        req.provider,
        "model":           req.model,
        "api_key":         req.api_key,
        "claude_path":     req.claude_path,
        "save_as_default": req.save_as_default,
    })
    result = await _do_llm_switch(fake)
    logger.info("LLM switched: %s → %s", current_provider, req.provider)
    return {"status": "switched", "previous_provider": current_provider, **result}


# ---------------------------------------------------------------------------
# MCP Registry endpoints (Phase 1.5)
# ---------------------------------------------------------------------------

@app.get("/mcp/tools")
async def mcp_list_tools():
    """
    List all MCP tools available for the active solution.
    Discovers tools from solutions/<name>/mcp_servers/*.py.
    """
    from src.integrations.mcp_registry import mcp_registry
    tools = mcp_registry.list_tools()
    return {"tools": tools, "count": len(tools)}


@app.post("/mcp/invoke")
async def mcp_invoke_tool(request: Request):
    """
    Invoke a registered MCP tool by name.
    Body: { "tool_name": str, "args": dict, "trace_id": str (optional) }
    Every invocation is audit-logged.
    """
    body = await request.json()
    tool_name = body.get("tool_name", "")
    args      = body.get("args", {})
    trace_id  = body.get("trace_id")

    if not tool_name:
        raise HTTPException(status_code=400, detail="tool_name is required")

    from src.integrations.mcp_registry import mcp_registry
    result = mcp_registry.invoke(tool_name, args, trace_id=trace_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Workflow Diagram Endpoints — visual Mermaid diagrams for all solutions
# ---------------------------------------------------------------------------

def _build_mermaid_from_source(source: str) -> str:
    """
    Fallback: parse a LangGraph workflow Python source file and build a
    Mermaid flowchart string from add_node / add_edge / set_entry_point calls.
    """
    import re
    nodes = re.findall(r'graph\.add_node\(["\'](\w+)["\']', source)
    raw_edges = re.findall(r'graph\.add_edge\(["\'](\w+)["\'],\s*["\'](\w+)["\']', source)
    entry = re.findall(r'graph\.set_entry_point\(["\'](\w+)["\']', source)
    # END edges
    end_edges = re.findall(r'graph\.add_edge\(["\'](\w+)["\'],\s*END\b', source)

    if not nodes:
        return "graph TD\n    A[No nodes found]"

    lines = ["graph TD"]
    # entry → first node label
    if entry:
        lines.append(f"    __start__(( )) --> {entry[0]}")
    for src, dst in raw_edges:
        lines.append(f"    {src} --> {dst}")
    for src in end_edges:
        lines.append(f"    {src} --> __end__(( ))")

    # Label each node
    node_labels = "\n    ".join(f'{n}["{n}"]' for n in nodes)
    lines.append(f"    {node_labels}")
    return "\n".join(lines)


def _get_solutions_dir() -> str:
    try:
        from src.core.project_loader import _SOLUTIONS_DIR
        return _SOLUTIONS_DIR
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "solutions")


def _discover_all_workflow_diagrams() -> list:
    """
    Walk solutions/*/workflows/*.py, load each workflow, and extract a
    Mermaid diagram string. Returns a list of workflow descriptor dicts.
    """
    import importlib.util
    import sys

    solutions_dir = _get_solutions_dir()
    results = []

    if not os.path.isdir(solutions_dir):
        return results

    for solution_name in sorted(os.listdir(solutions_dir)):
        solution_path = os.path.join(solutions_dir, solution_name)
        if not os.path.isdir(solution_path):
            continue

        # Check project.yaml for manual workflow_diagram override
        project_yaml_path = os.path.join(solution_path, "project.yaml")
        yaml_diagram_override = None
        try:
            import yaml
            with open(project_yaml_path) as f:
                pdata = yaml.safe_load(f) or {}
            yaml_diagram_override = pdata.get("workflow_diagram")
        except Exception:
            pass

        workflows_dir = os.path.join(solution_path, "workflows")
        if not os.path.isdir(workflows_dir):
            continue

        for filename in sorted(os.listdir(workflows_dir)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            workflow_name = filename[:-3]
            workflow_path = os.path.join(workflows_dir, filename)

            # Read source for fallback parsing and description extraction
            try:
                with open(workflow_path, encoding="utf-8", errors="replace") as f:
                    source = f.read()
            except Exception:
                continue

            if "StateGraph" not in source:
                continue

            mermaid_diagram = None
            node_count = 0

            # 1. Try yaml override (per-solution, applies to all workflows)
            if yaml_diagram_override:
                mermaid_diagram = str(yaml_diagram_override)

            # 2. Try draw_mermaid() from the compiled workflow object
            if not mermaid_diagram:
                try:
                    # Ensure solution dir is importable
                    if solution_path not in sys.path:
                        sys.path.insert(0, solution_path)

                    spec = importlib.util.spec_from_file_location(
                        f"_sage_wf_preview_{solution_name}_{workflow_name}",
                        workflow_path,
                    )
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    graph = getattr(mod, "workflow", None)
                    if graph is not None:
                        mermaid_diagram = graph.get_graph().draw_mermaid()
                        # Count nodes
                        try:
                            node_count = len(graph.get_graph().nodes)
                        except Exception:
                            pass
                except Exception:
                    pass  # Fall through to static parse

            # 3. Static regex fallback
            if not mermaid_diagram:
                mermaid_diagram = _build_mermaid_from_source(source)

            # Count nodes from Mermaid string if not already set
            if node_count == 0:
                import re
                node_count = len(re.findall(r'\b\w+\[', mermaid_diagram))

            # Extract description from module docstring
            import re
            description = ""
            docmatch = re.match(r'"""(.*?)"""', source, re.DOTALL)
            if docmatch:
                first_line = docmatch.group(1).strip().split("\n")[0].strip()
                description = first_line[:200] if first_line else ""

            results.append({
                "solution": solution_name,
                "workflow_name": workflow_name,
                "mermaid_diagram": mermaid_diagram,
                "node_count": node_count,
                "description": description,
            })

    return results


@app.get("/workflows")
async def list_workflow_diagrams():
    """
    Discover all LangGraph workflow files across all solutions and return
    their Mermaid diagrams. Diagrams are generated from the compiled
    StateGraph (draw_mermaid) or parsed from source as a fallback.

    Returns: list of {solution, workflow_name, mermaid_diagram, node_count, description}
    """
    try:
        workflows = _discover_all_workflow_diagrams()
        return {"workflows": workflows, "count": len(workflows)}
    except Exception as exc:
        logger.error("Failed to discover workflow diagrams: %s", exc)
        return {"workflows": [], "count": 0, "error": str(exc)}


@app.get("/workflows/{solution}/{workflow_name}")
async def get_workflow_diagram(solution: str, workflow_name: str):
    """Get a single workflow Mermaid diagram by solution + workflow_name."""
    try:
        all_workflows = _discover_all_workflow_diagrams()
        for wf in all_workflows:
            if wf["solution"] == solution and wf["workflow_name"] == workflow_name:
                return wf
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_name}' not found in solution '{solution}'",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get workflow diagram %s/%s: %s", solution, workflow_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# LangGraph Workflow Endpoints (Phase 3)
# ---------------------------------------------------------------------------

@app.get("/workflow/list")
async def workflow_list():
    """
    List available LangGraph workflows for the active solution.
    Returns empty list when orchestration.engine != "langgraph" or langgraph
    is not installed.
    """
    from src.integrations.langgraph_runner import langgraph_runner
    workflows = langgraph_runner.list_workflows()
    return {"workflows": workflows, "count": len(workflows)}


@app.post("/workflow/run")
async def workflow_run(request: Request):
    """
    Start a LangGraph workflow run.
    Body: { "workflow_name": str, "state": dict (optional) }
    Returns: { run_id, status, workflow_name, result }
    status = "completed" | "awaiting_approval" | "error"
    """
    body = await request.json()
    workflow_name = body.get("workflow_name", "")
    initial_state = body.get("state", {})

    if not workflow_name:
        raise HTTPException(status_code=400, detail="workflow_name is required")

    from src.integrations.langgraph_runner import langgraph_runner
    result = langgraph_runner.run(workflow_name, initial_state)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.post("/workflow/resume")
async def workflow_resume(request: Request):
    """
    Resume a workflow paused at an approval gate.
    Body: { "run_id": str, "feedback": dict (optional) }
    Feedback dict is merged into graph state (e.g. {"approved": true, "comment": "LGTM"}).
    """
    body = await request.json()
    run_id  = body.get("run_id", "")
    feedback = body.get("feedback", {})

    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    from src.integrations.langgraph_runner import langgraph_runner
    result = langgraph_runner.resume(run_id, feedback)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/workflow/status/{run_id}")
async def workflow_status(run_id: str):
    """Get current status of a workflow run by run_id."""
    from src.integrations.langgraph_runner import langgraph_runner
    result = langgraph_runner.get_status(run_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Build Orchestrator Endpoints — 0→1→N pipeline with Critic Agent
# ---------------------------------------------------------------------------

@app.post("/build/start")
async def build_start(req: BuildStartRequest):
    """
    Start a new build pipeline. Decomposes a product description into tasks,
    runs critic review, and returns a plan for human approval.

    Body:
      product_description : str  — plain-English description of what to build
      solution_name       : str  — name for the solution (optional)
      repo_url            : str  — git URL (optional)
      workspace_dir       : str  — local workspace path (optional)
      critic_threshold    : int  — minimum critic score to pass (default: 70)

    Returns:
      run_id, state, plan, critic_scores
    """
    orchestrator = _get_build_orchestrator()
    result = orchestrator.start(
        product_description=req.product_description,
        solution_name=req.solution_name,
        repo_url=req.repo_url,
        workspace_dir=req.workspace_dir,
        critic_threshold=req.critic_threshold,
        hitl_level=req.hitl_level,
    )
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/build/status/{run_id}")
async def build_status(run_id: str):
    """Get current status of a build run."""
    orchestrator = _get_build_orchestrator()
    result = orchestrator.get_status(run_id)
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/build/approve/{run_id}")
async def build_approve(run_id: str, req: BuildApproveRequest):
    """
    Approve a build stage. Routes to approve_plan or approve_build
    depending on the current state.
    """
    if not req.approved:
        orchestrator = _get_build_orchestrator()
        result = orchestrator.reject(run_id, req.feedback)
        if result.get("error") and "not found" in result["error"].lower():
            raise HTTPException(status_code=404, detail=result["error"])
        return result

    orchestrator = _get_build_orchestrator()
    status = orchestrator.get_status(run_id)

    if status.get("error"):
        raise HTTPException(status_code=404, detail=status["error"])

    state = status.get("state", "")
    if state == "awaiting_plan":
        result = orchestrator.approve_plan(run_id, feedback=req.feedback)
    elif state == "awaiting_build":
        result = orchestrator.approve_build(run_id, feedback=req.feedback)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (state: {state})",
        )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/build/runs")
async def build_runs():
    """List all build runs."""
    orchestrator = _get_build_orchestrator()
    runs = orchestrator.list_runs()
    return {"runs": runs, "count": len(runs)}


@app.get("/build/roles")
async def build_roles():
    """List all hireable agent roles with skills, tools, and MCP capabilities."""
    from src.integrations.build_orchestrator import get_hireable_roles
    roles = get_hireable_roles()
    return {"roles": roles, "count": len(roles)}


@app.get("/build/router/stats")
async def build_router_stats():
    """Adaptive router Q-learning statistics — scores per task_type × agent_role."""
    orchestrator = _get_build_orchestrator()
    return orchestrator.router.get_stats()


@app.get("/llm/dual-stats")
async def dual_llm_stats():
    """Teacher-student LLM generation stats (requests, agreement rate, distillation count)."""
    try:
        from src.integrations.dual_llm_runner import DualLLMRunner
        import yaml as _yaml
        _cfg_path = os.path.join("config", "config.yaml")
        _raw_cfg = {}
        if os.path.exists(_cfg_path):
            with open(_cfg_path) as _f:
                _raw_cfg = _yaml.safe_load(_f) or {}
        strategy_cfg = _raw_cfg.get("llm_strategy", {})
        pc = _get_project_config()
        runner = DualLLMRunner(strategy_cfg, solution_name=pc.project_name if pc else "starter")
        return runner.get_stats()
    except Exception as e:
        return {"error": str(e), "stats": {}}


# /research/program moved to src/interface/routes/research.py


# ---------------------------------------------------------------------------
# Skills Marketplace Endpoints
# ---------------------------------------------------------------------------

@app.get("/skills")
async def list_skills(include_disabled: bool = False):
    """List all registered skills with visibility filtering."""
    from src.core.skill_loader import skill_registry
    skills = skill_registry.list_all(include_disabled=include_disabled)
    return {
        "skills": [s.to_dict() for s in skills],
        "stats": skill_registry.stats(),
    }


@app.get("/skills/{name}")
async def get_skill(name: str):
    """Get a specific skill by name."""
    from src.core.skill_loader import skill_registry
    skill = skill_registry.get_including_disabled(name)
    if not skill:
        return {"error": f"Skill '{name}' not found"}
    return skill.to_dict()


@app.get("/skills/role/{role}")
async def skills_for_role(role: str):
    """Get all active skills for an agent role."""
    from src.core.skill_loader import skill_registry
    skills = skill_registry.get_for_role(role)
    return {"role": role, "skills": [s.to_dict() for s in skills], "count": len(skills)}


@app.get("/skills/runner/{runner}")
async def skills_for_runner(runner: str):
    """Get all active skills for a runner."""
    from src.core.skill_loader import skill_registry
    skills = skill_registry.get_for_runner(runner)
    return {"runner": runner, "skills": [s.to_dict() for s in skills], "count": len(skills)}


class SkillVisibilityRequest(BaseModel):
    name: str
    visibility: str  # "public", "private", "disabled"


@app.post("/skills/visibility")
async def set_skill_visibility(req: SkillVisibilityRequest):
    """Change a skill's visibility tier. Framework control — no approval needed."""
    from src.core.skill_loader import skill_registry
    if req.visibility not in {"public", "private", "disabled"}:
        return {"error": f"Invalid visibility: {req.visibility}"}
    ok = skill_registry.set_visibility(req.name, req.visibility)
    if not ok:
        return {"error": f"Skill '{req.name}' not found"}
    return {"status": "updated", "name": req.name, "visibility": req.visibility}


@app.post("/skills/reload")
async def reload_skills():
    """Hot-reload all skills from disk. Framework control — no approval needed."""
    from src.core.skill_loader import skill_registry
    count = skill_registry.reload()
    return {"status": "reloaded", "skills_loaded": count, "stats": skill_registry.stats()}


@app.get("/skills/search")
async def search_skills(q: str = ""):
    """Search skills by name, description, or keywords."""
    from src.core.skill_loader import skill_registry
    if not q:
        return {"error": "query parameter 'q' is required"}
    results = skill_registry.search(q)
    return {"query": q, "results": [s.to_dict() for s in results], "count": len(results)}


# ---------------------------------------------------------------------------
# Runners Endpoints
# ---------------------------------------------------------------------------

@app.get("/runners")
async def list_runners():
    """List all registered domain runners and their capabilities."""
    from src.integrations.base_runner import list_runners as _list_runners
    runners = _list_runners()
    return {"runners": runners, "count": len(runners)}


@app.get("/runners/{name}/skills")
async def runner_skills(name: str):
    """Get skills registered for a specific runner."""
    from src.integrations.base_runner import get_runner_by_name
    runner = get_runner_by_name(name)
    if not runner:
        return {"error": f"Runner '{name}' not found"}
    return {"runner": name, "skills": runner.get_skills()}


# ---------------------------------------------------------------------------
# Agent Gym Endpoints — self-play training
# ---------------------------------------------------------------------------

# ── Gym & Catalog endpoints moved to src/interface/routes/gym.py ──


# ── Meta-Optimizer & AutoResearch endpoints moved to src/interface/routes/research.py ──


# ---------------------------------------------------------------------------
# SWE Agent Endpoint — open-swe pattern
# ---------------------------------------------------------------------------

class SWETaskRequest(BaseModel):
    task: str
    repo_path: str = "."
    repo_url: Optional[str] = None
    solution_name: Optional[str] = None


@app.post("/swe/task")
async def swe_task(req: SWETaskRequest):
    """
    Submit an autonomous SWE task.

    The agent will:
      1. Explore the repository (README, AGENTS.md, file tree)
      2. Plan minimal, targeted changes
      3. Implement the changes file by file
      4. Verify with tests related to changed files only
      5. Commit to a branch and propose a PR

    The workflow pauses before `finalize` for human approval.
    Use POST /workflow/resume with the returned run_id to approve or reject.

    Body:
      task        : str  — natural language task description
      repo_path   : str  — path to local repo (default: ".")
      repo_url    : str  — git URL to clone (optional; overrides repo_path)
      solution_name: str — solution context (optional)

    Returns:
      run_id, status ("awaiting_approval"), workflow result with PR proposal
    """
    from src.integrations.langgraph_runner import langgraph_runner

    initial_state = {
        "task": req.task,
        "repo_path": os.path.abspath(req.repo_path) if req.repo_path else ".",
    }
    if req.repo_url:
        initial_state["repo_url"] = req.repo_url
    if req.solution_name:
        initial_state["solution_name"] = req.solution_name

    result = langgraph_runner.run("swe_workflow", initial_state)

    if "error" in result and "not found" in str(result.get("error", "")):
        raise HTTPException(status_code=404, detail=result["error"])
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Code Agent Endpoints (Phase 4 — AutoGen + sandbox)
# ---------------------------------------------------------------------------

@app.post("/code/plan")
async def code_plan(request: Request):
    """
    Generate a code plan for a task using AutoGen (or LLM fallback).
    Returns status=awaiting_approval with the plan and extracted code block.
    Human must call POST /code/approve before execute() is permitted.

    Body: { "task": str, "trace_id": str (optional) }
    """
    body = await request.json()
    task = body.get("task", "")
    trace_id = body.get("trace_id")

    if not task:
        raise HTTPException(status_code=400, detail="task is required")

    from src.integrations.autogen_runner import autogen_runner
    result = autogen_runner.plan(task, trace_id=trace_id)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


@app.post("/code/approve")
async def code_approve(request: Request):
    """
    Approve a code plan, enabling sandboxed execution.
    This is the mandatory SAGE approval gate — never bypassed.

    Body: { "run_id": str, "comment": str (optional) }
    """
    body = await request.json()
    run_id  = body.get("run_id", "")
    comment = body.get("comment", "")

    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    from src.integrations.autogen_runner import autogen_runner
    result = autogen_runner.approve(run_id, comment=comment)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.post("/code/execute")
async def code_execute(request: Request):
    """
    Execute an approved code plan in a Docker sandbox (or local subprocess fallback).
    Returns stdout, stderr, returncode, and sandbox type.

    Body: { "run_id": str }
    """
    body = await request.json()
    run_id = body.get("run_id", "")

    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")

    from src.integrations.autogen_runner import autogen_runner
    result = autogen_runner.execute(run_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@app.get("/code/status/{run_id}")
async def code_status(run_id: str):
    """Get current status of a code run by run_id."""
    from src.integrations.autogen_runner import autogen_runner
    result = autogen_runner.get_status(run_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Real-time SSE Streaming Endpoints (Phase 5)
# ---------------------------------------------------------------------------

def _sse_event(data: dict) -> str:
    """Format a dict as a Server-Sent Events data line."""
    import json
    return f"data: {json.dumps(data)}\n\n"


@app.post("/analyze/stream")
async def analyze_stream(request: Request):
    """
    Stream an agent analysis response token-by-token via Server-Sent Events.

    Body: { "log_entry": str, "system_prompt": str (optional) }

    SSE event shapes:
      {"type": "token",  "content": "..."}   — incremental text chunk
      {"type": "meta",   "trace_id": "..."}  — sent first with trace context
      {"type": "done",   "content": ""}      — stream finished
      {"type": "error",  "content": "..."}   — terminal error
    """
    body = await request.json()
    log_entry    = body.get("log_entry", "")
    system_prompt = body.get(
        "system_prompt",
        "You are a precise analyst. Identify the root cause, risk level, and next steps.",
    )

    if not log_entry:
        raise HTTPException(status_code=400, detail="log_entry is required")

    import uuid as _uuid
    trace_id = str(_uuid.uuid4())

    async def _event_stream():
        from src.core.llm_gateway import llm_gateway
        from src.memory.audit_logger import audit_logger

        yield _sse_event({"type": "meta", "trace_id": trace_id})

        full_response = []
        try:
            for chunk in llm_gateway.generate_stream(
                prompt=log_entry,
                system_prompt=system_prompt,
                trace_name="analyze_stream",
            ):
                full_response.append(chunk)
                yield _sse_event({"type": "token", "content": chunk})
        except Exception as exc:
            logger.error("SSE stream error: %s", exc)
            yield _sse_event({"type": "error", "content": str(exc)})
            return

        result_text = "".join(full_response)

        # Audit the completed analysis
        try:
            audit_logger.log_event(
                actor="analyze_stream",
                action_type="ANALYZE_STREAM",
                input_context=log_entry[:300],
                output_content=result_text[:500],
                metadata={"trace_id": trace_id, "streaming": True},
            )
        except Exception:
            pass

        yield _sse_event({"type": "done", "content": "", "trace_id": trace_id})

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disable nginx buffering
        },
    )


@app.post("/agent/stream")
async def agent_stream(request: Request):
    """
    Stream a universal agent response via Server-Sent Events.

    Body: { "role": str, "task": str, "context": str (optional) }

    Same SSE event shapes as /analyze/stream.
    """
    body = await request.json()
    role = body.get("role", "")
    task = body.get("task", "")
    context = body.get("context", "")

    if not role or not task:
        raise HTTPException(status_code=400, detail="role and task are required")

    import uuid as _uuid
    trace_id = str(_uuid.uuid4())

    async def _agent_event_stream():
        from src.core.llm_gateway import llm_gateway
        from src.core.project_loader import project_config
        from src.memory.audit_logger import audit_logger

        yield _sse_event({"type": "meta", "trace_id": trace_id})

        try:
            prompts = project_config.get_prompts()
            role_cfg = prompts.get(role, {})
            system_prompt = role_cfg.get(
                "system_prompt",
                f"You are an expert {role} agent. Complete the task concisely.",
            )
        except Exception:
            system_prompt = f"You are an expert {role} agent. Complete the task concisely."

        prompt = task
        if context:
            prompt = f"Context:\n{context}\n\nTask:\n{task}"

        full_response = []
        try:
            for chunk in llm_gateway.generate_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                trace_name=f"agent_stream_{role}",
            ):
                full_response.append(chunk)
                yield _sse_event({"type": "token", "content": chunk})
        except Exception as exc:
            logger.error("Agent SSE stream error: %s", exc)
            yield _sse_event({"type": "error", "content": str(exc)})
            return

        result_text = "".join(full_response)

        try:
            audit_logger.log_event(
                actor=f"agent_stream/{role}",
                action_type="AGENT_STREAM",
                input_context=task[:300],
                output_content=result_text[:500],
                metadata={"trace_id": trace_id, "role": role, "streaming": True},
            )
        except Exception:
            pass

        yield _sse_event({"type": "done", "content": "", "trace_id": trace_id})

    return StreamingResponse(
        _agent_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Live Log Streaming — makes CLI/agent activity visible in the Web UI
# ---------------------------------------------------------------------------

import asyncio
import queue as _queue
import threading

_ORG_YAML_LOCK = threading.Lock()


class _SSELogHandler(logging.Handler):
    """
    Logging handler that pushes every log record into a per-connection queue.
    The queue is attached to a GET /logs/stream SSE connection.
    """
    _listeners: list["_SSELogHandler"] = []
    _lock = threading.Lock()

    def __init__(self):
        super().__init__()
        self.q: _queue.Queue = _queue.Queue(maxsize=500)
        with _SSELogHandler._lock:
            _SSELogHandler._listeners.append(self)

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.q.put_nowait({
                "level":   record.levelname,
                "name":    record.name,
                "message": msg,
                "ts":      datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            })
        except _queue.Full:
            pass  # drop oldest if consumer is slow

    def close(self):
        with _SSELogHandler._lock:
            try:
                _SSELogHandler._listeners.remove(self)
            except ValueError:
                pass
        super().close()


def _attach_log_handler() -> "_SSELogHandler":
    """Create and attach a new SSE log handler to the root logger."""
    handler = _SSELogHandler()
    handler.setFormatter(logging.Formatter("%(name)s — %(message)s"))
    handler.setLevel(logging.INFO)
    logging.getLogger().addHandler(handler)
    return handler


@app.get("/logs/stream")
async def logs_stream():
    """
    SSE endpoint — streams Python logging output to the browser in real time.
    Open this from the Live Console page to see all agent/framework activity.

    Event shape: data: {"level": "INFO", "name": "src.agents.analyst", "message": "...", "ts": "..."}
    """
    handler = _attach_log_handler()

    async def _generator():
        try:
            # Send a heartbeat immediately so the browser knows we're connected
            yield "data: {\"level\":\"INFO\",\"name\":\"sage\",\"message\":\"Live console connected.\",\"ts\":\"" + datetime.now(timezone.utc).isoformat() + "\"}\n\n"
            while True:
                try:
                    record = handler.q.get(timeout=0.5)
                    payload = json.dumps(record, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                except _queue.Empty:
                    # heartbeat every 15 s to keep connection alive
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass
        finally:
            handler.close()

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Onboarding Wizard (Phase 6)
# ---------------------------------------------------------------------------

ORG_TEMPLATES = [
    {
        "id": "starter",
        "name": "General Engineering Team",
        "description": "Analyst, Developer, Planner, Monitor — works for any software domain",
        "role_count": 4,
        "compliance_standards": [],
        "icon": "⚙️",
        "roles": [
            {"key": "analyst",   "name": "Signal Analyst",  "description": "Triage logs and errors"},
            {"key": "developer", "name": "Code Reviewer",   "description": "Review MRs and code changes"},
            {"key": "planner",   "name": "Task Planner",    "description": "Decompose complex requests"},
            {"key": "monitor",   "name": "Monitor",         "description": "Watch systems and alert"},
        ],
    },
    {
        "id": "medtech",
        "name": "Medical Device Team",
        "description": "Regulatory affairs, firmware, QA, clinical specialist — ISO 13485 / IEC 62304",
        "role_count": 7,
        "compliance_standards": ["ISO 13485", "IEC 62304", "ISO 14971"],
        "icon": "🏥",
        "roles": [
            {"key": "regulatory_affairs_lead", "name": "Regulatory Affairs Lead",  "description": "FDA/CE submissions and DHF"},
            {"key": "biomedical_engineer",      "name": "Biomedical Engineer",      "description": "Class II/III device hardware/firmware"},
            {"key": "software_qa_engineer",     "name": "Software QA Engineer",     "description": "IEC 62304 V&V, traceability"},
            {"key": "clinical_specialist",      "name": "Clinical Specialist",      "description": "CER, post-market surveillance"},
            {"key": "quality_management_lead",  "name": "Quality Management Lead",  "description": "CAPA, audits, nonconformance"},
            {"key": "embedded_firmware_dev",    "name": "Embedded Firmware Dev",    "description": "Safety-critical C/C++ for medical hardware"},
            {"key": "cybersecurity_analyst",    "name": "Cybersecurity Analyst",    "description": "FDA cybersecurity guidance"},
        ],
    },
    {
        "id": "automotive",
        "name": "Automotive Infotainment & Telematics",
        "description": "HMI, ADAS, telematics, functional safety — ISO 26262 / UN ECE WP.29",
        "role_count": 7,
        "compliance_standards": ["ISO 26262", "UN ECE WP.29", "ISO/SAE 21434"],
        "icon": "🚗",
        "roles": [
            {"key": "hmi_engineer",               "name": "HMI Engineer",               "description": "IVI UI/UX, AUTOSAR HMI"},
            {"key": "telematics_engineer",         "name": "Telematics Engineer",         "description": "V2X, CAN/LIN, OBD-II"},
            {"key": "adas_engineer",               "name": "ADAS Engineer",               "description": "Sensor fusion, ISO 26262 ASIL"},
            {"key": "functional_safety_engineer",  "name": "Functional Safety Engineer",  "description": "FTA/FMEA, ASIL decomposition"},
            {"key": "connectivity_engineer",       "name": "Connectivity Engineer",       "description": "4G/5G, OTA updates"},
            {"key": "audio_video_engineer",        "name": "Audio/Video Engineer",        "description": "Codec, media framework"},
            {"key": "cybersecurity_engineer",      "name": "Cybersecurity Engineer",      "description": "TARA, HSM, secure boot"},
        ],
    },
    {
        "id": "mobile_app",
        "name": "Mobile App Development",
        "description": "iOS, Android, Flutter engineers with QA, DevOps, and App Store specialist",
        "role_count": 7,
        "compliance_standards": ["Apple App Store Guidelines", "Google Play Policy", "GDPR"],
        "icon": "📱",
        "roles": [
            {"key": "ios_engineer",               "name": "iOS Engineer",               "description": "Swift/SwiftUI, App Store"},
            {"key": "android_engineer",           "name": "Android Engineer",           "description": "Kotlin/Jetpack, Google Play"},
            {"key": "flutter_engineer",           "name": "Flutter Engineer",           "description": "Dart/Flutter cross-platform"},
            {"key": "mobile_qa_engineer",         "name": "Mobile QA Engineer",         "description": "Device farm, UI automation"},
            {"key": "mobile_devops_engineer",     "name": "Mobile DevOps",              "description": "Fastlane, CI/CD, signing"},
            {"key": "mobile_performance_engineer","name": "Performance Engineer",       "description": "Memory, battery, network"},
            {"key": "app_store_specialist",       "name": "App Store Specialist",       "description": "ASO, review management"},
        ],
    },
    {
        "id": "railways",
        "name": "Railway Systems & Signalling",
        "description": "Signalling, traction, TCMS, safety assurance — EN 50128 / EN 50129",
        "role_count": 7,
        "compliance_standards": ["EN 50128", "EN 50129", "EN 50126"],
        "icon": "🚂",
        "roles": [
            {"key": "signalling_engineer",         "name": "Signalling Engineer",         "description": "ETCS/ERTMS, interlocking, SIL"},
            {"key": "traction_engineer",           "name": "Traction Engineer",           "description": "Propulsion, energy recovery"},
            {"key": "onboard_systems_engineer",    "name": "Onboard Systems Engineer",    "description": "TCMS, door systems, PIS"},
            {"key": "safety_assurance_engineer",   "name": "Safety Assurance Engineer",   "description": "RAMS, HAZOP, safety case"},
            {"key": "communications_engineer",     "name": "Communications Engineer",     "description": "GSM-R/FRMCS, train radio"},
            {"key": "maintenance_engineer",        "name": "Maintenance Engineer",        "description": "CBM, fault codes, SCADA"},
            {"key": "test_verification_engineer",  "name": "Test & Verification Engineer","description": "HIL/SIL, test specifications"},
        ],
    },
    {
        "id": "avionics",
        "name": "Avionics & Aerospace",
        "description": "DO-178C avionics software, systems engineering, airworthiness — FAA/EASA",
        "role_count": 7,
        "compliance_standards": ["DO-178C", "DO-254", "ARP4754A", "FAA Part 25"],
        "icon": "✈️",
        "roles": [
            {"key": "avionics_software_engineer", "name": "Avionics Software Engineer", "description": "DO-178C DAL, ARINC 653"},
            {"key": "systems_engineer",           "name": "Systems Engineer",           "description": "ARP4754A, FHA/PSSA/SSA"},
            {"key": "flight_test_engineer",       "name": "Flight Test Engineer",       "description": "Flight data analysis, PIREP"},
            {"key": "airworthiness_engineer",     "name": "Airworthiness Engineer",     "description": "FAA Part 25, EASA CS-25, STC"},
            {"key": "navigation_engineer",        "name": "Navigation Engineer",        "description": "ILS/VOR/GNSS, FMS"},
            {"key": "certification_specialist",   "name": "Certification Specialist",   "description": "DER coordination, compliance matrix"},
            {"key": "hardware_design_assurance",  "name": "Hardware Design Assurance",  "description": "DO-254, FPGA/ASIC review"},
        ],
    },
]


@app.post("/onboarding/generate")
async def onboarding_generate(request: Request):
    """
    Generate a complete SAGE solution (3 YAML files + directory structure)
    from a plain-language description of the user's domain.

    Body: {
        "description": str,              — what the solution does (required)
        "solution_name": str,            — snake_case folder name (required)
        "compliance_standards": [str],   — optional list
        "integrations": [str],           — optional list (default: ["gitlab"])
        "parent_solution": str,          — optional parent solution name
        "org_name": str                  — optional org to register the solution under
    }

    Returns: { solution_name, path, status, files, message, suggested_routes }
    status = "created" | "exists"
    """
    body = await request.json()
    description      = body.get("description", "").strip()
    solution_name    = body.get("solution_name", "").strip()
    compliance       = body.get("compliance_standards", [])
    integrations     = body.get("integrations", ["gitlab"])
    parent_solution  = body.get("parent_solution", "").strip()
    org_name         = body.get("org_name", "").strip()

    if not description:
        raise HTTPException(status_code=400, detail="description is required")
    if not solution_name:
        raise HTTPException(status_code=400, detail="solution_name is required")

    # Load org context (mission/vision/values) to enrich the LLM prompt
    try:
        _od = _read_org_yaml()
        _org_section = _od.get("org", {}) if isinstance(_od, dict) else {}
        _org_context = ""
        if _org_section.get("mission"):
            _parts = [f"Mission: {_org_section['mission']}"]
            if _org_section.get("vision"):
                _parts.append(f"Vision: {_org_section['vision']}")
            if _org_section.get("core_values"):
                _vals = "\n  - ".join(_org_section["core_values"])
                _parts.append(f"Core values:\n  - {_vals}")
            _org_context = "\n".join(_parts)
    except Exception:
        _org_context = ""

    try:
        from src.core.onboarding import generate_solution
        result = generate_solution(
            description=description,
            solution_name=solution_name,
            compliance_standards=compliance,
            integrations=integrations,
            parent_solution=parent_solution,
            org_name=org_name,
            org_context=_org_context,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Onboarding generation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@app.post("/onboarding/session")
async def onboarding_session_create():
    """
    Start a new conversational onboarding session.
    Returns: {session_id, state, messages: [{role, content, ts}]}
    """
    from src.core.onboarding_session import create_session
    session = create_session()
    return session.to_dict()


@app.post("/onboarding/session/{session_id}/message")
async def onboarding_session_message(session_id: str, request: Request):
    """
    Send a user message to the onboarding conversation.
    Body: {"message": str}
    Returns: {reply, state, info, session_id}
    """
    from src.core.onboarding_session import send_message
    body = await request.json()
    user_msg = body.get("message", "").strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="message is required")
    result = send_message(session_id, user_msg)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/onboarding/session/{session_id}/generate")
async def onboarding_session_generate(session_id: str):
    """
    Trigger YAML generation for the gathered info.
    Creates a HITL proposal — approve it to write the solution files.
    Returns: {trace_id, description, solution_name, state}
    """
    from src.core.onboarding_session import request_generate
    result = request_generate(session_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/onboarding/session/{session_id}")
async def onboarding_session_get(session_id: str):
    """Get the current state of an onboarding session."""
    from src.core.onboarding_session import get_session
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return session.to_dict()


@app.get("/onboarding/org-templates")
async def get_org_templates():
    """Return available pre-built org structures for onboarding."""
    return {"templates": ORG_TEMPLATES}


@app.get("/onboarding/templates")
async def onboarding_templates():
    """
    Return a list of pre-built solution templates available for use.
    These are the bundled solutions in the solutions/ directory.
    """
    from src.core.project_loader import _SOLUTIONS_DIR
    templates = []
    try:
        for name in sorted(os.listdir(_SOLUTIONS_DIR)):
            project_file = os.path.join(_SOLUTIONS_DIR, name, "project.yaml")
            if os.path.isfile(project_file):
                try:
                    import yaml as _yaml
                    with open(project_file) as f:
                        proj = _yaml.safe_load(f) or {}
                    templates.append({
                        "solution_name": name,
                        "display_name":  proj.get("name", name),
                        "domain":        proj.get("domain", name),
                        "description":   proj.get("description", ""),
                    })
                except Exception:
                    templates.append({"solution_name": name})
    except Exception as e:
        logger.warning("Could not list templates: %s", e)
    return {"templates": templates, "count": len(templates)}


@app.post("/onboarding/analyze")
async def onboarding_analyze(request: Request):
    """
    Analyze a project description, local path, or GitHub URL to auto-detect
    stack, CI, compliance requirements, and suggest SAGE configuration.

    Body: {"text": str} or {"path": str} or {"url": str}
    Returns: ProjectSignals dict with detected_stack, detected_ci, compliance_hints, etc.
    """
    body = await request.json()
    from src.core.onboarding_analyzer import OnboardingAnalyzer
    analyzer = OnboardingAnalyzer()

    text = body.get("text", "")
    path = body.get("path", "")
    url = body.get("url", "")

    if url:
        signals = analyzer.analyze_github_repo(url)
    elif path:
        signals = analyzer.analyze_local_path(path)
    elif text:
        signals = analyzer.analyze_text(text)
    else:
        raise HTTPException(400, detail="Provide 'text', 'path', or 'url'")

    return signals.to_dict()


@app.post("/onboarding/scan-folder")
async def onboarding_scan_folder(req: ScanFolderRequest):
    """Scan a local folder and generate solution YAML using the LLM."""
    from src.core.folder_scanner import FolderScanner

    try:
        scanner = FolderScanner()
        folder_content = scanner.scan(req.folder_path)
    except FileNotFoundError:
        raise HTTPException(400, detail={"error": "folder_not_found", "message": f"Folder not found: {req.folder_path}"})

    if not folder_content.strip():
        raise HTTPException(400, detail={"error": "folder_empty", "message": "No readable files found in this folder."})

    org_context = _load_org_context()

    system_prompt = (
        "You are a SAGE solution architect. Generate three YAML files for a SAGE solution: "
        "project.yaml, prompts.yaml, and tasks.yaml. "
        "Return ONLY a JSON object with keys 'project.yaml', 'prompts.yaml', 'tasks.yaml' — "
        "each value is the full YAML content as a string. No other text."
    )
    user_prompt_parts = []
    if org_context:
        user_prompt_parts.append(f"Company context:\n{org_context}\n")
    user_prompt_parts.append(f"Intent: {req.intent}")
    user_prompt_parts.append(f"Solution name: {req.solution_name}")
    user_prompt_parts.append(f"\nCodebase content:\n{folder_content}")
    user_prompt = "\n\n".join(user_prompt_parts)

    llm = _get_llm_gateway()
    try:
        raw = llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception as exc:
        logger.error("LLM error in scan-folder: %s", exc)
        raise HTTPException(503, detail={"error": "llm_unavailable", "message": "Could not reach the LLM."})

    files, summary = _parse_generated_files(raw)

    _get_audit_logger().log_event(
        actor="human_via_onboarding",
        action_type="ONBOARDING_SCAN",
        input_context=req.intent,
        output_content=str(files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": req.solution_name, "folder_path": req.folder_path},
    )

    return {"solution_name": req.solution_name, "files": files, "summary": summary}


@app.post("/onboarding/refine")
async def onboarding_refine(req: RefineRequest):
    """Refine previously generated solution YAML based on user feedback."""
    org_context = _load_org_context()

    system_prompt = (
        "You are a SAGE solution architect. Refine the provided YAML files based on the feedback. "
        "Return ONLY a JSON object with keys 'project.yaml', 'prompts.yaml', 'tasks.yaml' — "
        "each value is the full YAML content as a string. No other text."
    )
    user_prompt_parts = []
    if org_context:
        user_prompt_parts.append(f"Company context:\n{org_context}\n")
    user_prompt_parts.append(f"Solution name: {req.solution_name}")
    user_prompt_parts.append(f"Feedback: {req.feedback}")
    user_prompt_parts.append(
        f"\nCurrent YAML files:\n"
        + "\n---\n".join(f"# {k}\n{v}" for k, v in req.current_files.items())
    )
    user_prompt = "\n\n".join(user_prompt_parts)

    llm = _get_llm_gateway()
    try:
        raw = llm.generate(system_prompt=system_prompt, user_prompt=user_prompt)
    except Exception as exc:
        logger.error("LLM error in refine: %s", exc)
        raise HTTPException(503, detail={"error": "llm_unavailable", "message": "Could not reach the LLM."})

    files, summary = _parse_generated_files(raw)

    _get_audit_logger().log_event(
        actor="human_via_onboarding",
        action_type="ONBOARDING_REFINE",
        input_context=req.feedback,
        output_content=str(files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": req.solution_name},
    )

    return {"solution_name": req.solution_name, "files": files, "summary": summary}


@app.post("/onboarding/save-solution")
async def onboarding_save_solution(req: SaveSolutionRequest):
    """Write generated YAML files to disk under SAGE_SOLUTIONS_DIR/<solution_name>/."""
    if not _SAFE_SOLUTION_NAME.match(req.solution_name):
        raise HTTPException(400, detail={"error": "invalid_solution_name",
                                         "message": "solution_name must be 1-64 alphanumeric characters, underscores, or hyphens."})
    solution_dir = os.path.join(_get_solutions_dir(), req.solution_name)
    solutions_root = os.path.realpath(_get_solutions_dir())
    if not os.path.realpath(solution_dir).startswith(solutions_root + os.sep):
        raise HTTPException(400, detail={"error": "invalid_solution_name",
                                         "message": "Resolved path escapes solutions directory."})
    os.makedirs(solution_dir, exist_ok=True)
    for filename, content in req.files.items():
        if filename not in {"project.yaml", "prompts.yaml", "tasks.yaml"}:
            continue
        with open(os.path.join(solution_dir, filename), "w", encoding="utf-8") as f:
            f.write(content)
    _get_audit_logger().log_event(
        actor="human_via_onboarding",
        action_type="ONBOARDING_COMPLETE",
        input_context=req.solution_name,
        output_content=str(req.files.get("project.yaml", ""))[:2000],
        metadata={"solution_name": req.solution_name},
    )
    return {"status": "saved", "solution_name": req.solution_name}


# ---------------------------------------------------------------------------
# Knowledge Base CRUD (Phase 7)
# ---------------------------------------------------------------------------

@app.get("/knowledge/entries")
async def knowledge_list(limit: int = 50):
    """
    List stored knowledge entries with their IDs.
    Returns [{id, text, metadata}, ...].
    """
    from src.memory.vector_store import vector_memory
    return {"entries": vector_memory.list_entries(limit=limit), "count": limit}


def _write_to_channel_collection(db_path: str, collection_name: str, text: str, metadata: dict):
    """Write a knowledge entry to a shared channel chroma collection. Non-fatal on error."""
    try:
        import importlib.util
        if importlib.util.find_spec("chromadb") is None:
            return
        import chromadb
        import uuid as _uuid
        _client = chromadb.PersistentClient(path=db_path)
        _col = _client.get_or_create_collection(collection_name)
        _col.add(documents=[text], metadatas=[metadata or {}], ids=[str(_uuid.uuid4())])
        logger.info("Written to channel collection %s", collection_name)
    except Exception as _exc:
        logger.warning("Channel write failed (non-fatal): %s", _exc)


@app.post("/knowledge/add")
async def knowledge_add(request: Request):
    """
    Propose adding a knowledge entry to the vector store.
    Returns STATEFUL proposal — actual add on POST /approve/{trace_id}.
    Body: { "text": str, "metadata": dict (optional), "channel": str (optional) }
    """
    body = await request.json()
    text = (body.get("text") or body.get("content") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required (also accepts 'content')")
    metadata = body.get("metadata", {})

    # --- Org channel write (optional) ---
    channel = body.get("channel", "").strip() if body else ""
    if channel:
        from src.core.org_loader import org_loader as _org_loader
        _active_sol = _get_active_solution()
        _col_name = _org_loader.get_producer_channel_name(_active_sol, channel)
        if _col_name is None:
            raise HTTPException(
                status_code=400,
                detail=f"solution '{_active_sol}' is not a producer for channel '{channel}'",
            )
        _channel_db = _org_loader.get_channel_db_path()
        if _channel_db:
            import os as _os
            _os.makedirs(_channel_db, exist_ok=True)
            _write_to_channel_collection(_channel_db, _col_name, text, metadata)
    # --- end channel write ---

    from src.core.proposal_store import RiskClass
    preview = text[:120] + ("..." if len(text) > 120 else "")
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "knowledge_add",
        risk_class    = RiskClass.STATEFUL,
        payload       = {"text": text, "metadata": metadata},
        description   = f"Add knowledge entry: \"{preview}\"",
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("knowledge_add"),
    )
    return {
        "status":   "pending_approval",
        "trace_id": proposal.trace_id,
        "preview":  preview,
        "message":  "POST /approve/{trace_id} to add to knowledge base.",
    }


@app.delete("/knowledge/entry/{entry_id}")
async def knowledge_delete(entry_id: str, note: str = ""):
    """
    Propose deleting a knowledge entry (DESTRUCTIVE — never expires).
    Pass ?note=reason to provide context for the approval.
    """
    from src.memory.vector_store import vector_memory
    from src.core.proposal_store import RiskClass
    # Verify entry exists before proposing
    entries = vector_memory.list_entries(limit=1000)
    found = next((e for e in entries if str(e.get("id")) == entry_id), None)
    if not found:
        raise HTTPException(status_code=404, detail=f"Entry '{entry_id}' not found")
    preview = str(found.get("text", ""))[:80]
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "knowledge_delete",
        risk_class    = RiskClass.DESTRUCTIVE,
        payload       = {"entry_id": entry_id, "preview": preview},
        description   = f"DELETE knowledge entry {entry_id}: \"{preview}\"",
        reversible    = False,
        proposed_by   = "user",
        required_role = _get_required_role("knowledge_delete"),
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
        "warning":     "This action is IRREVERSIBLE. POST /approve/{trace_id} with a note to confirm.",
    }


@app.post("/knowledge/import")
async def knowledge_import(request: Request):
    """
    Propose bulk-importing knowledge entries.
    Returns STATEFUL proposal — actual import on POST /approve/{trace_id}.
    Body: { "entries": [{"text": str, "metadata": dict}, ...] }
    """
    body = await request.json()
    entries = body.get("entries", [])
    if not isinstance(entries, list) or not entries:
        raise HTTPException(status_code=400, detail="entries must be a non-empty list")
    from src.core.proposal_store import RiskClass
    sample = entries[0].get("text", "")[:80] if entries else ""
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "knowledge_import",
        risk_class    = RiskClass.STATEFUL,
        payload       = {"entries": entries},
        description   = f"Bulk import {len(entries)} knowledge entries (sample: \"{sample}\")",
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("knowledge_import"),
    )
    return {
        "status":   "pending_approval",
        "trace_id": proposal.trace_id,
        "count":    len(entries),
        "sample":   sample,
    }


@app.post("/knowledge/search")
async def knowledge_search(request: Request):
    """
    Semantic/keyword search of the knowledge base.
    Body: { "query": str, "k": int (default 5) }
    """
    body = await request.json()
    query = body.get("query", "").strip()
    k     = min(int(body.get("k", 5)), 20)
    org_filter = body.get("org_filter", False)
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    if org_filter:
        # Org-aware search scoped to the active solution tenant
        from src.memory.vector_store import org_aware_query
        from src.core.project_loader import project_config
        results = org_aware_query(query, solution_name=project_config.project_name, limit=k)
    else:
        from src.memory.vector_store import vector_memory
        results = vector_memory.search(query, k=k)
    return {"results": results, "count": len(results), "query": query}


class KnowledgeSyncRequest(BaseModel):
    directory: str = ""   # default: active solution dir


@app.post("/knowledge/sync")
async def trigger_knowledge_sync(req: KnowledgeSyncRequest = KnowledgeSyncRequest()):
    """
    Walk the solution directory and import text files into the vector store.
    Returns count of imported chunks.
    """
    from src.core.knowledge_syncer import sync_directory
    from src.core.project_loader import project_config, _SOLUTIONS_DIR

    root = req.directory or os.path.join(_SOLUTIONS_DIR, project_config.project_name)
    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail=f"Directory not found: {root}")
    try:
        count = sync_directory(root)
        return {"status": "ok", "chunks_imported": count, "directory": root}
    except Exception as exc:
        logger.error("knowledge_sync failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Slack Two-Way Approval (Phase 8)
# ---------------------------------------------------------------------------

@app.post("/slack/send-proposal")
async def slack_send_proposal(request: Request):
    """
    Send an agent proposal to the configured Slack channel.
    Body: { "trace_id": str, "summary": str, "action_type": str, "actor": str }
    """
    body = await request.json()
    trace_id    = body.get("trace_id", "")
    summary     = body.get("summary", "").strip()
    action_type = body.get("action_type", "PROPOSE")
    actor       = body.get("actor", "SAGE Agent")

    if not trace_id or not summary:
        raise HTTPException(status_code=400, detail="trace_id and summary are required")

    from src.integrations.slack_approver import send_proposal
    result = send_proposal({
        "trace_id":    trace_id,
        "summary":     summary,
        "action_type": action_type,
        "actor":       actor,
    })
    return result


@app.post("/webhook/slack")
async def slack_webhook(request: Request):
    """
    Receive Slack interactive action callbacks (button clicks).
    Validates the Slack signature, then routes approve/reject decisions
    back into the SAGE approval gate.

    Slack sends: application/x-www-form-urlencoded with 'payload' field.
    """
    from src.integrations.slack_approver import verify_slack_signature, parse_action_payload

    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    # Slack sends form-encoded payload
    try:
        from urllib.parse import parse_qs
        form = parse_qs(body.decode("utf-8"))
        payload_str = form.get("payload", ["{}"])[0]
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse Slack payload")

    action = parse_action_payload(payload_str)
    trace_id = action.get("trace_id", "")
    decision = action.get("decision", "")
    user     = action.get("user", "slack_user")

    if not trace_id or decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Invalid action payload")

    # Route to SAGE approval gate
    try:
        audit = _get_audit_logger()
        audit.log_event(
            actor=f"slack/{user}",
            action_type=f"SLACK_{decision.upper()}",
            input_context=f"trace_id={trace_id}",
            output_content=f"Decision: {decision} by {user}",
            metadata={"trace_id": trace_id, "decision": decision, "user": user},
        )
        logger.info("Slack %s for trace_id=%s by %s", decision, trace_id, user)
    except Exception as e:
        logger.warning("Audit log for Slack action failed: %s", e)

    return {"status": "received", "trace_id": trace_id, "decision": decision}


# ---------------------------------------------------------------------------
# Evaluation & Benchmarking (Phase 9)
# ---------------------------------------------------------------------------

@app.get("/eval/suites")
async def eval_list_suites():
    """List available eval suites for the active solution."""
    from src.core.eval_runner import eval_runner
    suites = eval_runner.list_suites()
    return {"suites": suites, "count": len(suites)}


@app.post("/eval/run")
async def eval_run(request: Request):
    """
    Run an eval suite (or all suites).
    Body: { "suite": str (optional — omit to run all) }
    Returns: { run_id, suite, total_cases, passed_cases, mean_score, results }
    """
    body = await request.json()
    suite = body.get("suite")

    from src.core.eval_runner import eval_runner
    result = eval_runner.run(suite=suite)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@app.get("/eval/history")
async def eval_history(suite: str = None, limit: int = 20):
    """Return historical eval run summaries for trend tracking."""
    from src.core.eval_runner import eval_runner
    history = eval_runner.get_history(suite=suite, limit=limit)
    return {"history": history, "count": len(history)}


# ---------------------------------------------------------------------------
# Temporal Durable Workflows (Phase 11)
# ---------------------------------------------------------------------------

@app.post("/temporal/workflow/start")
async def temporal_start(request: Request):
    """
    Start a Temporal durable workflow.
    Falls back to LangGraph runner when Temporal is unavailable.

    Body: { "workflow_name": str, "args": dict (optional), "workflow_id": str (optional) }
    """
    body = await request.json()
    workflow_name = body.get("workflow_name", "")
    args          = body.get("args", {})
    workflow_id   = body.get("workflow_id")

    if not workflow_name:
        raise HTTPException(status_code=400, detail="workflow_name is required")

    from src.integrations.temporal_runner import temporal_runner
    result = temporal_runner.start(workflow_name, args=args, workflow_id=workflow_id)

    if result.get("status") == "error" and not result.get("fallback"):
        raise HTTPException(status_code=500, detail=result.get("reason", "Unknown error"))

    return result


@app.get("/temporal/workflow/status/{workflow_id}")
async def temporal_status(workflow_id: str):
    """Get the current status of a Temporal workflow run."""
    from src.integrations.temporal_runner import temporal_runner
    result = temporal_runner.get_status(workflow_id)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@app.get("/temporal/workflow/list")
async def temporal_list():
    """List all workflow runs tracked in this process session."""
    from src.integrations.temporal_runner import temporal_runner
    return {"runs": temporal_runner.list_runs(), "count": len(temporal_runner.list_runs())}


# ---------------------------------------------------------------------------
# Multi-Tenant Context (Phase 10)
# ---------------------------------------------------------------------------

@app.get("/tenant/context")
async def tenant_context(request: Request):
    """
    Return the resolved tenant context for the current request.
    Pass X-SAGE-Tenant header to override the default (active solution name).
    """
    from src.core.tenant import get_tenant_id, tenant_scoped_collection
    tenant = await get_tenant_id(request)
    return {
        "tenant_id":  tenant,
        "collection": tenant_scoped_collection(),
        "header_set": "X-SAGE-Tenant" in request.headers,
    }


# ---------------------------------------------------------------------------
# Composio integration endpoints
# ---------------------------------------------------------------------------

class ComposioConnectRequest(BaseModel):
    app: str                    # e.g. "github", "jira", "slack"
    redirect_url: str = ""      # Optional URL to redirect after OAuth


@app.get("/integrations/composio/status")
async def composio_status():
    """
    Returns Composio availability and list of connected apps.
    """
    from src.integrations.composio_tools import is_available, list_connected_apps
    available = is_available()
    connected = list_connected_apps() if available else []
    return {
        "available": available,
        "api_key_set": bool(os.environ.get("COMPOSIO_API_KEY", "")),
        "connected_apps": connected,
        "count": len(connected),
    }


@app.post("/integrations/composio/connect")
async def composio_connect(req: ComposioConnectRequest):
    """
    Initiate a Composio OAuth connection for an app.
    Returns the URL the user should visit to authorise access.
    This creates a HITL proposal — the connection URL is provided for human action.
    """
    from src.integrations.composio_tools import get_connection_url, is_available
    from src.core.proposal_store import get_proposal_store, RiskClass

    if not is_available():
        raise HTTPException(
            status_code=503,
            detail="Composio unavailable. Install composio-langchain and set COMPOSIO_API_KEY."
        )

    redirect = req.redirect_url or None
    url = get_connection_url(req.app, redirect_url=redirect)
    if not url:
        raise HTTPException(
            status_code=400,
            detail=f"Could not get connection URL for '{req.app}'. "
                   "Ensure the app name is valid and your API key has permission."
        )

    store = get_proposal_store()
    proposal = store.create(
        action_type="composio_connect",
        risk_class=RiskClass.EXTERNAL,
        reversible=True,
        proposed_by="web-ui",
        description=f"Connect Composio app: {req.app}",
        payload={"app": req.app, "connection_url": url},
        required_role=_get_required_role("composio_connect"),
    )
    return {
        "status": "pending_approval",
        "trace_id": proposal.trace_id,
        "app": req.app,
        "connection_url": url,
        "message": f"Visit the connection_url to authorise {req.app}. "
                   "Then approve this proposal to register the integration.",
    }


@app.get("/integrations/composio/tools")
async def composio_tools_list():
    """
    List tools loaded for the active solution's composio:* integrations.
    """
    from src.core.project_loader import project_config
    integrations = project_config.metadata.get("integrations", [])
    composio_apps = [i[len("composio:"):] for i in integrations if i.startswith("composio:")]

    if not composio_apps:
        return {"tools": [], "apps": [], "message": "No composio:* entries in project.yaml integrations."}

    from src.integrations.composio_tools import get_composio_tools, is_available
    if not is_available():
        return {"tools": [], "apps": composio_apps, "available": False,
                "message": "Composio unavailable — install composio-langchain and set COMPOSIO_API_KEY."}

    tool_dict = get_composio_tools(composio_apps)
    return {
        "available": True,
        "apps": composio_apps,
        "tools": [
            {"name": name, "description": getattr(t, "description", "")}
            for name, t in tool_dict.items()
        ],
        "count": len(tool_dict),
    }


@app.get("/integrations/langchain/tools")
async def langchain_tools_list():
    """
    List LangChain tool integrations enabled for the active solution.
    Reads the integrations list from project.yaml and loads matching tool loaders.
    """
    from src.core.project_loader import project_config
    try:
        from src.integrations.langchain_tools import get_tools_for_solution
        tool_dict = get_tools_for_solution(project_config.project_name)
        return {
            "solution": project_config.project_name,
            "tools": [
                {"name": name, "description": getattr(t, "description", str(type(t).__name__))}
                for name, t in tool_dict.items()
            ],
            "count": len(tool_dict),
        }
    except Exception as e:
        logger.warning("LangChain tools listing failed: %s", e)
        return {"solution": project_config.project_name, "tools": [], "count": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Authentication & Access Control (T1-001)
# ---------------------------------------------------------------------------

class CreateApiKeyRequest(BaseModel):
    name:     str
    email:    str
    solution: str = ""
    role:     str = "operator"


class AssignRoleRequest(BaseModel):
    email:    str
    solution: str = ""
    role:     str


@app.get("/auth/me")
async def auth_me(request: Request):
    """
    Return the current user's identity.
    When auth is disabled, returns the anonymous admin identity.
    Useful for the UI to know who is authenticated and what role they have.
    """
    from src.core.auth import get_current_user as _get_current_user
    user = await _get_current_user(request)
    return {
        "sub":      user.sub,
        "email":    user.email,
        "name":     user.name,
        "role":     user.role,
        "provider": user.provider,
    }


@app.post("/auth/api-keys")
async def create_api_key_endpoint(req: CreateApiKeyRequest, request: Request):
    """
    Create a new API key. Requires ADMIN role.
    Returns { id, key, name } — key is shown once, store it securely.
    """
    from src.core.auth import get_current_user as _get_current_user
    from src.core.rbac import require_role, Role
    from src.core.api_keys import create_api_key
    from fastapi import Depends

    user = await _get_current_user(request)
    from src.core.rbac import _ROLE_RANK
    if _ROLE_RANK.get(user.role, 0) < _ROLE_RANK.get("admin", 3):
        raise HTTPException(status_code=403, detail="ADMIN role required to create API keys.")

    solution = req.solution or _get_active_solution()
    plain_key, key_id = create_api_key(
        name=req.name,
        email=req.email,
        solution=solution,
        role=req.role,
    )
    logger.info("API key created by %s: id=%s name=%s", user.email, key_id, req.name)
    return {"id": key_id, "key": plain_key, "name": req.name}


@app.get("/auth/api-keys")
async def list_api_keys_endpoint(request: Request):
    """
    List all API keys for the active solution. Requires ADMIN role.
    Key hashes are never returned.
    """
    from src.core.auth import get_current_user as _get_current_user
    from src.core.api_keys import list_api_keys
    from src.core.rbac import _ROLE_RANK

    user = await _get_current_user(request)
    if _ROLE_RANK.get(user.role, 0) < _ROLE_RANK.get("admin", 3):
        raise HTTPException(status_code=403, detail="ADMIN role required.")

    solution = _get_active_solution()
    keys = list_api_keys(solution)
    return {"api_keys": keys, "count": len(keys)}


@app.delete("/auth/api-keys/{key_id}")
async def revoke_api_key_endpoint(key_id: str, request: Request):
    """Revoke an API key by ID. Requires ADMIN role."""
    from src.core.auth import get_current_user as _get_current_user
    from src.core.api_keys import revoke_api_key
    from src.core.rbac import _ROLE_RANK

    user = await _get_current_user(request)
    if _ROLE_RANK.get(user.role, 0) < _ROLE_RANK.get("admin", 3):
        raise HTTPException(status_code=403, detail="ADMIN role required.")

    revoked = revoke_api_key(key_id, revoked_by=user.email or user.name)
    if not revoked:
        raise HTTPException(status_code=404, detail=f"API key '{key_id}' not found or already revoked.")
    return {"revoked": True, "id": key_id}


@app.get("/auth/roles")
async def list_roles_endpoint(request: Request):
    """List user role assignments for the active solution. Requires ADMIN role."""
    from src.core.auth import get_current_user as _get_current_user
    from src.core.rbac import list_roles, _ROLE_RANK

    user = await _get_current_user(request)
    if _ROLE_RANK.get(user.role, 0) < _ROLE_RANK.get("admin", 3):
        raise HTTPException(status_code=403, detail="ADMIN role required.")

    solution = _get_active_solution()
    roles = list_roles(solution)
    return {"roles": roles, "count": len(roles)}


@app.post("/auth/roles")
async def assign_role_endpoint(req: AssignRoleRequest, request: Request):
    """Assign a role to a user for the active solution. Requires ADMIN role."""
    from src.core.auth import get_current_user as _get_current_user
    from src.core.rbac import assign_role, Role, _ROLE_RANK

    user = await _get_current_user(request)
    if _ROLE_RANK.get(user.role, 0) < _ROLE_RANK.get("admin", 3):
        raise HTTPException(status_code=403, detail="ADMIN role required.")

    try:
        role_enum = Role(req.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role '{req.role}'. Valid: viewer, operator, approver, admin.")

    solution = req.solution or _get_active_solution()
    assign_role(email=req.email, solution=solution, role=role_enum, granted_by=user.email or user.name)
    return {"assigned": True, "email": req.email, "solution": solution, "role": req.role}


# ===========================================================================
# Cost Tracking Endpoints (T1-004)
# ===========================================================================

class BudgetSetRequest(BaseModel):
    tenant: Optional[str] = None
    solution: Optional[str] = None
    monthly_usd: float


@app.get("/costs/summary")
async def costs_summary(
    tenant: Optional[str] = None,
    solution: Optional[str] = None,
    period_days: int = 30,
):
    """
    Return aggregated LLM cost summary.

    Query params:
      tenant:      Filter by tenant (optional)
      solution:    Filter by solution (optional)
      period_days: Rolling window in days (default 30)
    """
    try:
        from src.core import cost_tracker
        return cost_tracker.get_summary(tenant=tenant, solution=solution, period_days=period_days)
    except Exception as e:
        logger.error("costs/summary failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/costs/daily")
async def costs_daily(
    tenant: Optional[str] = None,
    solution: Optional[str] = None,
    period_days: int = 30,
):
    """
    Return daily cost breakdown for charting.

    Query params:
      tenant:      Filter by tenant (optional)
      solution:    Filter by solution (optional)
      period_days: Rolling window in days (default 30)
    """
    try:
        from src.core import cost_tracker
        rows = cost_tracker.get_daily(tenant=tenant, solution=solution, period_days=period_days)
        return {"daily": rows, "count": len(rows), "period_days": period_days}
    except Exception as e:
        logger.error("costs/daily failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/costs/budget")
async def costs_set_budget(req: BudgetSetRequest):
    """
    Set a monthly budget limit for a tenant/solution.
    Persists to the llm.budgets.per_solution section of config.yaml.
    """
    import yaml

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "config.yaml",
    )
    try:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}

        llm_section = cfg.setdefault("llm", {})
        budget_section = llm_section.setdefault("budgets", {})
        per_solution = budget_section.setdefault("per_solution", {})

        key = req.solution or req.tenant or "default"
        per_solution[key] = req.monthly_usd

        with open(config_path, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

        return {
            "saved": True,
            "key": key,
            "monthly_usd": req.monthly_usd,
            "message": f"Budget of ${req.monthly_usd:.2f}/month set for '{key}'.",
        }
    except Exception as e:
        logger.error("costs/budget POST failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# SAGE Intelligence (SLM) Endpoints
# ===========================================================================

@app.get("/sage/status")
async def sage_intelligence_status():
    """Return SAGEIntelligence SLM configuration and availability."""
    try:
        from src.core.sage_intelligence import SAGEIntelligence
        si = SAGEIntelligence()
        available = False
        if si.enabled:
            try:
                import urllib.request
                urllib.request.urlopen(f"{si.host}/api/tags", timeout=2)
                available = True
            except Exception:
                available = False
        return {
            "enabled": si.enabled,
            "model": si.model,
            "provider": si.provider,
            "ollama_host": si.host,
            "light_task_threshold": si.light_task_threshold,
            "slm_available": available,
            "fallback_on_error": si.fallback_on_error,
        }
    except Exception as e:
        return {"enabled": False, "error": str(e)}


@app.get("/sage/ask")
async def sage_ask(question: str):
    """Answer a question about the SAGE framework using the SLM."""
    try:
        from src.core.sage_intelligence import SAGEIntelligence
        si = SAGEIntelligence()
        answer = si.answer_framework_question(question)
        return {"question": question, "answer": answer, "slm_used": si.enabled}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class IntentRequest(BaseModel):
    input: str
    solution_context: Optional[dict] = None


@app.post("/sage/intent")
async def sage_intent(req: IntentRequest):
    """Convert natural language user input into a structured SAGE API call."""
    try:
        from src.core.sage_intelligence import SAGEIntelligence
        si = SAGEIntelligence()
        ctx = req.solution_context or {}
        if not ctx:
            pc = _get_project_config()
            ctx = {"task_types": pc.get_task_types() if pc else []}
        result = si.convert_to_api_call(req.input, ctx)
        if result is None:
            return {"success": False, "message": "SAGEIntelligence not enabled or SLM unavailable."}
        return {"success": True, "api_call": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sage/lint-yaml")
async def sage_lint_yaml(file_name: str, content: str):
    """Lint a SAGE YAML configuration file for common mistakes."""
    try:
        from src.core.sage_intelligence import SAGEIntelligence
        si = SAGEIntelligence()
        errors = si.lint_yaml(file_name, content)
        return {"file": file_name, "errors": errors, "valid": len(errors) == 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Dual LLM / Teacher-Student Endpoints
# ===========================================================================

@app.get("/llm/dual-status")
async def dual_llm_status():
    """Return teacher-student LLM configuration for the active solution."""
    try:
        from src.integrations.dual_llm_runner import DualLLMRunner
        import yaml as _yaml
        pc = _get_project_config()
        solution = pc.project_name if pc else "starter"
        # Load llm_strategy from config.yaml if present
        _cfg_path = os.path.join("config", "config.yaml")
        _raw_cfg = {}
        if os.path.exists(_cfg_path):
            with open(_cfg_path) as _f:
                _raw_cfg = _yaml.safe_load(_f) or {}
        strategy_cfg = _raw_cfg.get("llm_strategy", {})
        runner = DualLLMRunner(strategy_cfg, solution_name=solution)
        return {
            "solution": solution,
            "dual_mode_active": strategy_cfg.get("mode") == "dual",
            "mode": strategy_cfg.get("mode", "single"),
            "strategy": runner.default_strategy,
            "confidence_threshold": runner.confidence_threshold,
            "distillation_enabled": runner.distillation_enabled,
            "teacher_provider": strategy_cfg.get("teacher", {}).get("provider"),
            "student_provider": strategy_cfg.get("student", {}).get("provider"),
        }
    except Exception as e:
        return {"dual_mode_active": False, "error": str(e)}


@app.get("/distillation/{solution}/stats")
async def distillation_stats(solution: str):
    """Return distillation statistics for a solution."""
    try:
        base = os.path.join("data", "distillation", solution)
        result = {"solution": solution, "comparisons": 0, "escalations": 0, "observations": 0}
        for fname, key in [("comparisons.jsonl", "comparisons"),
                           ("escalations.jsonl", "escalations"),
                           ("shadow_observations.jsonl", "observations")]:
            path = os.path.join(base, fname)
            if os.path.exists(path):
                with open(path) as f:
                    result[key] = sum(1 for line in f if line.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/distillation/{solution}/comparisons")
async def distillation_comparisons(solution: str, limit: int = 20):
    """Return recent teacher-student comparison records."""
    try:
        import json as _json
        path = os.path.join("data", "distillation", solution, "comparisons.jsonl")
        if not os.path.exists(path):
            return {"comparisons": [], "total": 0}
        records = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(_json.loads(line))
                    except Exception:
                        pass
        records = records[-limit:]
        return {"comparisons": records, "total": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/distillation/{solution}/export")
async def distillation_export(solution: str, fmt: str = "alpaca"):
    """Export teacher-student distillation data in Alpaca or ShareGPT format for fine-tuning."""
    try:
        from src.integrations.dual_llm_runner import DualLLMRunner
        import yaml as _yaml
        _cfg_path = os.path.join("config", "config.yaml")
        _raw_cfg = {}
        if os.path.exists(_cfg_path):
            with open(_cfg_path) as _f:
                _raw_cfg = _yaml.safe_load(_f) or {}
        strategy_cfg = _raw_cfg.get("llm_strategy", {})
        runner = DualLLMRunner(strategy_cfg, solution_name=solution)
        data = runner.export_training_data(fmt=fmt)
        return {"solution": solution, "format": fmt, "records": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Agent Status Endpoint
# ===========================================================================

@app.get("/agents/status")
async def agents_status():
    """
    Return live status for all known agent roles in the active solution.
    Reads recent audit log to determine active/idle state and last task.
    """
    try:
        from src.memory.audit_logger import AuditLogger
        from src.core.project_loader import get_project_config as _gpc
        import time

        pc = _gpc()
        prompts = pc.metadata.get("roles", {}) if pc else {}
        audit = AuditLogger()

        # Query last 100 audit entries to derive per-role stats
        entries = audit.get_entries(limit=100)
        today_start = time.strftime("%Y-%m-%d")

        role_stats: dict[str, dict] = {}
        for entry in entries:
            actor = entry.get("actor", "")
            ts = entry.get("timestamp", "")
            action = entry.get("action_type", "")
            if not actor:
                continue
            if actor not in role_stats:
                role_stats[actor] = {"last_task": None, "last_ts": None, "count_today": 0}
            if role_stats[actor]["last_ts"] is None or ts > role_stats[actor]["last_ts"]:
                role_stats[actor]["last_task"] = action
                role_stats[actor]["last_ts"] = ts
            if ts.startswith(today_start):
                role_stats[actor]["count_today"] += 1

        # Build response — include all prompts.yaml roles plus known base agents
        known_roles = [
            "AnalystAgent", "DeveloperAgent", "PlannerAgent",
            "MonitorAgent", "UniversalAgent", "SWEAgent",
        ]
        result = []
        for role in known_roles:
            stats = role_stats.get(role, {})
            last_ts = stats.get("last_ts")
            # Active = had activity in last 5 minutes
            status = "idle"
            if last_ts:
                try:
                    from datetime import datetime, timezone
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                    age_secs = (datetime.now(timezone.utc) - last_dt).total_seconds()
                    if age_secs < 300:
                        status = "active"
                except Exception:
                    pass
            result.append({
                "role": role,
                "status": status,
                "last_task": stats.get("last_task"),
                "task_count_today": stats.get("count_today", 0),
            })
        return result
    except Exception as e:
        logger.error("agents/status error: %s", e)
        # Return static fallback — OrgChart page handles this gracefully
        return [
            {"role": r, "status": "idle", "last_task": None, "task_count_today": 0}
            for r in ["AnalystAgent", "DeveloperAgent", "PlannerAgent",
                      "MonitorAgent", "UniversalAgent", "SWEAgent"]
        ]


@app.get("/agents/active")
async def get_active_agents():
    """
    Returns currently active (in-progress) tasks from the queue manager.
    Used by the Live Agents panel on the Dashboard.
    """
    try:
        qm = _get_task_queue()
        all_tasks = qm.get_all_tasks()   # returns list of dicts
        active = [
            {
                "task_id":    t["task_id"],
                "task_type":  t["task_type"],
                "status":     t["status"],
                "started_at": t.get("started_at"),
                "source":     t.get("source", ""),
            }
            for t in all_tasks
            if t["status"] in ("in_progress", "pending")
        ]
        return {"agents": active, "count": len(active)}
    except Exception as exc:
        logger.error("get_active_agents failed: %s", exc)
        return {"agents": [], "count": 0}


# ==============================================================================
# HIL (Hardware-in-the-Loop) Testing Endpoints
# ==============================================================================

@app.get("/hil/status")
async def hil_status():
    """Return HIL runner connection status and last session info."""
    try:
        from src.integrations.hil_runner import _hil_runner
        if _hil_runner is None:
            return {
                "connected": False,
                "transport": "none",
                "session_id": None,
                "tests_run": 0,
                "message": "No HIL runner initialised. POST /hil/connect to start.",
            }
        return _hil_runner.status()
    except Exception as e:
        return {"connected": False, "error": str(e)}


@app.post("/hil/connect")
async def hil_connect(request: Request):
    """
    Connect to hardware transport.

    Body (JSON):
      transport : "mock" | "serial" | "jlink" | "can" | "openocd"  (default: mock)
      config    : dict — transport-specific config (port, baud_rate, device, speed, ...)
    """
    try:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        transport = body.get("transport", "mock")
        config    = body.get("config", {})
    except Exception:
        transport = "mock"
        config    = {}

    try:
        from src.integrations.hil_runner import get_hil_runner
        runner    = get_hil_runner(transport=transport, config=config)
        connected = runner.connect()
        return {
            "transport":  transport,
            "connected":  connected,
            "session_id": runner.session_id,
            "message": "Connected" if connected else f"Could not connect to {transport} hardware — operating in degraded mode",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hil/run-suite")
async def hil_run_suite(request: Request):
    """
    Run a list of HIL test cases against the connected hardware.

    Body (JSON):
      tests     : list[dict]  — list of HILTestCase dicts
                  Each: {id, name, requirement_id, description, procedure, expected_result,
                          transport?, timeout_seconds?}
      transport : str         — transport to use (default: mock)
      config    : dict        — transport config (optional)
    """
    try:
        body      = await request.json()
        tests_raw = body.get("tests", [])
        transport = body.get("transport", "mock")
        config    = body.get("config", {})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    if not tests_raw:
        raise HTTPException(status_code=400, detail="'tests' list is required and must not be empty")

    try:
        from src.integrations.hil_runner import get_hil_runner, HILTestCase, HILTransport
        runner = get_hil_runner(transport=transport, config=config)
        if not runner._connected:
            runner.connect()

        test_cases = []
        for item in tests_raw:
            transport_str = item.get("transport", transport)
            try:
                t_enum = HILTransport(transport_str.lower())
            except ValueError:
                t_enum = HILTransport.MOCK
            test_cases.append(HILTestCase(
                id=item.get("id", "TC-UNKNOWN"),
                name=item.get("name", "Unnamed test"),
                requirement_id=item.get("requirement_id", "REQ-UNKNOWN"),
                description=item.get("description", ""),
                procedure=item.get("procedure", []),
                expected_result=item.get("expected_result", ""),
                transport=t_enum,
                timeout_seconds=item.get("timeout_seconds", 30),
            ))

        results = runner.run_suite(test_cases)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/hil/report/{session_id}")
async def hil_report(session_id: str, standard: str = "IEC62304"):
    """
    Generate a regulatory evidence report for a HIL test session.

    Path:  session_id — HIL session ID (from /hil/connect or /hil/run-suite)
    Query: standard   — IEC62304 | DO178C | EN50128 | ISO26262 | IEC62443 (default: IEC62304)
    """
    try:
        from src.integrations.hil_runner import _hil_runner
        if _hil_runner is None or _hil_runner.session_id != session_id:
            raise HTTPException(
                status_code=404,
                detail=f"No active HIL session with id '{session_id}'. Run /hil/run-suite first.",
            )
        report = _hil_runner.generate_report(standard=standard)
        return report
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Compliance Flags Endpoints
# ==============================================================================

@app.get("/compliance/domains")
async def compliance_domains():
    """List all supported compliance domains and their risk levels."""
    try:
        from src.core.compliance_flags import COMPLIANCE_FLAGS
        result = []
        for domain, entry in COMPLIANCE_FLAGS.items():
            result.append({
                "domain":           domain,
                "standard":         entry.get("standard", ""),
                "description":      entry.get("description", ""),
                "authority":        entry.get("authority", ""),
                "risk_levels":      entry.get("risk_levels", []),
                "hil_required_for": entry.get("hil_required_for", []),
            })
        return {"domains": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compliance/flags/{domain}")
async def compliance_flags_endpoint(domain: str, risk_level: str = "HIGH"):
    """
    Return required compliance flags for a domain at a given risk level.

    Path:  domain     — medtech | automotive | railways | avionics | iot_ics
    Query: risk_level — domain-specific level (e.g. CLASS_C, ASIL_D, SIL_4, DAL_A, SL_3)
    """
    try:
        from src.core.compliance_flags import (
            get_required_flags,
            get_hil_required_tests,
            COMPLIANCE_FLAGS,
            list_domains,
        )
        if domain.lower() not in COMPLIANCE_FLAGS:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown domain '{domain}'. Valid domains: {list_domains()}",
            )
        flags     = get_required_flags(domain, risk_level)
        hil_tests = get_hil_required_tests(domain, risk_level)
        entry     = COMPLIANCE_FLAGS[domain.lower()]
        return {
            "domain":                domain,
            "risk_level":            risk_level.upper(),
            "standard":              entry.get("standard", ""),
            "description":           entry.get("description", ""),
            "authority":             entry.get("authority", ""),
            "flags":                 flags,
            "hil_required_flag_ids": hil_tests,
            "total_flags":           len(flags),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compliance/checklist/{domain}")
async def compliance_checklist_endpoint(domain: str, risk_level: str = "HIGH"):
    """
    Generate a full compliance checklist for a domain and risk level.

    Path:  domain     — medtech | automotive | railways | avionics | iot_ics
    Query: risk_level — domain-specific level (e.g. CLASS_C, ASIL_D, SIL_4, DAL_A, SL_3)

    Returns all compliance flags, required tasks, and evidence artifacts.
    Each item has a null status field ready for audit population.
    """
    try:
        from src.core.compliance_flags import generate_compliance_checklist, COMPLIANCE_FLAGS, list_domains
        if domain.lower() not in COMPLIANCE_FLAGS:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown domain '{domain}'. Valid domains: {list_domains()}",
            )
        checklist = generate_compliance_checklist(domain, risk_level)
        return checklist
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compliance/gap-assessment")
async def compliance_gap_assessment(request: Request):
    """
    Assess compliance gaps given a list of completed task types.

    Body (JSON):
      domain          : str       — medtech | automotive | railways | avionics | iot_ics
      risk_level      : str       — domain-specific risk level
      completed_tasks : list[str] — task type strings already completed

    Returns missing tasks, HIL gaps, and overall compliance percentage.
    """
    try:
        body            = await request.json()
        domain          = body.get("domain", "")
        risk_level      = body.get("risk_level", "")
        completed_tasks = body.get("completed_tasks", [])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    if not domain or not risk_level:
        raise HTTPException(status_code=400, detail="'domain' and 'risk_level' are required")

    try:
        from src.core.compliance_flags import assess_compliance_gap, COMPLIANCE_FLAGS, list_domains
        if domain.lower() not in COMPLIANCE_FLAGS:
            raise HTTPException(status_code=404, detail=f"Unknown domain. Valid: {list_domains()}")
        result = assess_compliance_gap(domain, risk_level, completed_tasks)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Repo Map — codebase symbol graph for agent context and UI display
# ---------------------------------------------------------------------------

@app.get("/repo/map")
async def get_repo_map(max_files: int = 50):
    """Return a Markdown repo map of the active project for debugging/UI display."""
    try:
        from src.core.repo_map import generate_repo_map
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return {"map": generate_repo_map(root, max_files=max_files)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ============================================================
# Organization endpoints — org.yaml CRUD
# ============================================================

def _get_org_yaml_path() -> str:
    """Path to org.yaml in SAGE_SOLUTIONS_DIR root."""
    import os as _os
    return _os.path.join(_get_solutions_dir(), "org.yaml")


def _read_org_yaml() -> dict:
    import yaml as _yaml
    path = _get_org_yaml_path()
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return _yaml.safe_load(f) or {}


def _write_org_yaml(data: dict) -> None:
    import yaml as _yaml
    path = _get_org_yaml_path()
    with open(path, "w", encoding="utf-8") as f:
        _yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _load_org_context() -> str:
    """Load mission/vision/core_values from org.yaml for LLM injection."""
    try:
        data = _read_org_yaml()
        org = data.get("org", {}) if isinstance(data, dict) else {}
        if not org.get("mission"):
            return ""
        parts = [f"Mission: {org['mission']}"]
        if org.get("vision"):
            parts.append(f"Vision: {org['vision']}")
        if org.get("core_values"):
            vals = "\n  - ".join(org["core_values"])
            parts.append(f"Core values:\n  - {vals}")
        return "\n".join(parts)
    except Exception:
        return ""


def _parse_generated_files(raw: str) -> tuple:
    """Parse LLM output — expects JSON with project/prompts/tasks.yaml keys."""
    import json as _json
    import re as _re
    import yaml as _yaml
    text = raw.strip()
    fence_match = _re.search(r"```(?:\w+)?\n([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        files = _json.loads(text)
        if not isinstance(files, dict):
            files = {"project.yaml": text, "prompts.yaml": "roles: {}", "tasks.yaml": "task_types: []"}
    except Exception:
        files = {"project.yaml": text, "prompts.yaml": "roles: {}", "tasks.yaml": "task_types: []"}
    summary = {"name": "", "description": "", "task_types": [], "compliance_standards": [], "integrations": []}
    try:
        proj = _yaml.safe_load(files.get("project.yaml", "")) or {}
        summary["name"] = proj.get("name", "")
        summary["description"] = proj.get("description", "")
        summary["compliance_standards"] = proj.get("compliance_standards", [])
        summary["integrations"] = proj.get("integrations", [])
        tasks_raw = _yaml.safe_load(files.get("tasks.yaml", "")) or {}
        for tt in tasks_raw.get("task_types", []):
            if isinstance(tt, dict):
                summary["task_types"].append({
                    "name": tt.get("name", ""),
                    "description": tt.get("description", ""),
                })
    except Exception:
        pass
    return files, summary


class OrgUpdateRequest(BaseModel):
    name: Optional[str] = None
    mission: Optional[str] = None
    vision: Optional[str] = None
    core_values: Optional[List[str]] = None


@app.get("/org")
async def org_get():
    """Return org.yaml content enriched with cross_team_routes from all solutions."""
    from src.core.org_loader import org_loader as _ol
    data = _read_org_yaml()
    data["routes"] = _ol.get_all_routes()
    return data


@app.put("/org")
async def org_update(req: OrgUpdateRequest):
    """Save mission/vision/core_values to org.yaml. Merges — does not overwrite unset fields."""
    import yaml as _yaml

    org_path = _get_org_yaml_path()

    with _ORG_YAML_LOCK:
        # Load existing or start fresh
        existing: dict = {}
        if os.path.exists(org_path):
            try:
                with open(org_path, encoding="utf-8") as f:
                    existing = _yaml.safe_load(f) or {}
            except Exception:
                existing = {}

        # Merge only supplied fields
        if not isinstance(existing.get("org"), dict):
            existing["org"] = {}
        org_section = existing["org"]

        if req.name is not None:
            org_section["name"] = req.name
        if req.mission is not None:
            org_section["mission"] = req.mission
        if req.vision is not None:
            org_section["vision"] = req.vision
        if req.core_values is not None:
            org_section["core_values"] = req.core_values

        os.makedirs(os.path.dirname(org_path), exist_ok=True)
        with open(org_path, "w", encoding="utf-8") as f:
            _yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)

    reload_org_loader()

    _get_audit_logger().log_event(
        actor="human_via_settings",
        action_type="ORG_SAVED",
        input_context=f"name={req.name}, mission={req.mission}",
        output_content=str(org_section),
        metadata={"source": "PUT /org"},
    )

    return {"status": "saved", "org": org_section}


@app.post("/org/reload")
async def org_reload():
    """Re-read org.yaml and refresh the OrgLoader singleton."""
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "reloaded"}


@app.post("/org/channels")
async def org_channels_create(request: Request):
    """Create a knowledge channel. Body: {name, producers, consumers}"""
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="channel name is required")
    data = _read_org_yaml()
    data.setdefault("org", {}).setdefault("knowledge_channels", {})[name] = {
        "producers": body.get("producers", []),
        "consumers": body.get("consumers", []),
    }
    _write_org_yaml(data)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "created", "channel": name}


@app.delete("/org/channels/{name}")
async def org_channels_delete(name: str):
    """Delete a knowledge channel from org.yaml."""
    data = _read_org_yaml()
    channels = data.get("org", {}).get("knowledge_channels", {})
    if name not in channels:
        raise HTTPException(status_code=404, detail=f"channel '{name}' not found")
    del channels[name]
    _write_org_yaml(data)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "deleted", "channel": name}


@app.post("/org/solutions")
async def org_solutions_add(request: Request):
    """Add parent: to a solution's project.yaml. Body: {solution, parent}"""
    import yaml as _yaml, os as _os
    body = await request.json()
    solution = body.get("solution", "").strip()
    parent = body.get("parent", "").strip()
    if not solution or not parent:
        raise HTTPException(status_code=400, detail="solution and parent are required")
    sols_dir = _get_solutions_dir()
    proj_path = _os.path.join(sols_dir, solution, "project.yaml")
    if not _os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{solution}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    proj["parent"] = parent
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "added", "solution": solution, "parent": parent}


@app.delete("/org/solutions/{name}")
async def org_solutions_remove(name: str):
    """Remove parent: from a solution's project.yaml."""
    import yaml as _yaml, os as _os
    sols_dir = _get_solutions_dir()
    proj_path = _os.path.join(sols_dir, name, "project.yaml")
    if not _os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{name}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    proj.pop("parent", None)
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "removed", "solution": name}


@app.post("/org/routes")
async def org_routes_add(request: Request):
    """Add cross_team_route to a solution's project.yaml. Body: {solution, target}"""
    import yaml as _yaml, os as _os
    body = await request.json()
    solution = body.get("solution", "").strip()
    target = body.get("target", "").strip()
    if not solution or not target:
        raise HTTPException(status_code=400, detail="solution and target are required")
    sols_dir = _get_solutions_dir()
    proj_path = _os.path.join(sols_dir, solution, "project.yaml")
    if not _os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{solution}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    routes = proj.get("cross_team_routes", [])
    if not any(r.get("target") == target for r in routes):
        routes.append({"target": target})
    proj["cross_team_routes"] = routes
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "added", "solution": solution, "target": target}


@app.delete("/org/routes")
async def org_routes_delete(request: Request):
    """Remove cross_team_route. Body: {solution, target}"""
    import yaml as _yaml, os as _os
    body = await request.json()
    solution = body.get("solution", "").strip()
    target = body.get("target", "").strip()
    if not solution or not target:
        raise HTTPException(status_code=400, detail="solution and target are required")
    sols_dir = _get_solutions_dir()
    proj_path = _os.path.join(sols_dir, solution, "project.yaml")
    if not _os.path.exists(proj_path):
        raise HTTPException(status_code=404, detail=f"solution '{solution}' not found")
    with open(proj_path, "r", encoding="utf-8") as f:
        proj = _yaml.safe_load(f) or {}
    proj["cross_team_routes"] = [
        r for r in proj.get("cross_team_routes", []) if r.get("target") != target
    ]
    with open(proj_path, "w", encoding="utf-8") as f:
        _yaml.dump(proj, f, default_flow_style=False, allow_unicode=True)
    from src.core.org_loader import reload_org_loader
    reload_org_loader()
    return {"status": "removed", "solution": solution, "target": target}


# ---------------------------------------------------------------------------
# Solution branding (direct write — framework control operation, no approval)
# ---------------------------------------------------------------------------

class BrandingRequest(BaseModel):
    display_name: Optional[str] = None
    icon_name:    Optional[str] = None
    accent:       Optional[str] = None
    sidebar_bg:   Optional[str] = None
    sidebar_text: Optional[str] = None
    badge_bg:     Optional[str] = None
    badge_text:   Optional[str] = None


@app.patch("/config/project/theme")
async def patch_project_theme(req: BrandingRequest):
    """Directly update the active solution's theme block and optionally its display name.
    This is a framework control operation (like /config/switch) — executes immediately.
    """
    import yaml as _yaml
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    path = os.path.join(_SOLUTIONS_DIR, project_config.project_name, "project.yaml")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="project.yaml not found")

    with open(path, "r", encoding="utf-8") as fh:
        data = _yaml.safe_load(fh) or {}

    # Update display name if provided
    if req.display_name is not None:
        data["name"] = req.display_name

    # Build / update theme block
    theme = data.get("theme") or {}
    if req.icon_name    is not None: theme["icon_name"]    = req.icon_name
    if req.accent       is not None: theme["accent"]       = req.accent
    if req.sidebar_bg   is not None: theme["sidebar_bg"]   = req.sidebar_bg
    if req.sidebar_text is not None: theme["sidebar_text"] = req.sidebar_text
    if req.badge_bg     is not None: theme["badge_bg"]     = req.badge_bg
    if req.badge_text   is not None: theme["badge_text"]   = req.badge_text
    data["theme"] = theme

    with open(path, "w", encoding="utf-8") as fh:
        _yaml.dump(data, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)

    # Reload project config so the change is reflected immediately
    try:
        from src.core.project_loader import load_project
        load_project(project_config.project_name)
    except Exception:
        pass  # not fatal — next reload will pick it up

    return {"status": "updated", "solution": project_config.project_name}


# ---------------------------------------------------------------------------
# Dev users (dev-mode identity roster)
# ---------------------------------------------------------------------------

@app.get("/config/dev-users")
async def get_dev_users():
    """Return dev-mode user roster from config/dev_users.yaml.
    Returns empty list if file does not exist — graceful degradation.
    """
    import yaml as _yaml
    path = os.environ.get(
        "SAGE_DEV_USERS_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "dev_users.yaml")
    )
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return {"users": []}
    with open(path, "r", encoding="utf-8") as f:
        data = _yaml.safe_load(f) or {}
    return {"users": data.get("users", [])}


# ---------------------------------------------------------------------------
# OpenShell Sandbox — availability and version info
# ---------------------------------------------------------------------------

@app.get("/sandbox/status")
async def get_sandbox_status():
    """Returns OpenShell sandbox availability and version info."""
    try:
        from src.integrations.openshell_runner import get_openshell_runner
        return get_openshell_runner().status()
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Chat — contextual LLM conversation per user session (P5-ChatPanel)
# ---------------------------------------------------------------------------

@app.post("/chat")
async def chat(req: ChatRequest):
    """Non-streaming contextual chat. Routes through LLM classifier, returns action or answer."""
    from src.core.project_loader import project_config
    from src.core.chat_router import route as chat_route
    from src.memory.audit_logger import audit_logger
    import json as _json

    solution = req.solution or (project_config.project_name if project_config else "sage")
    session_id = req.session_id or str(uuid.uuid4())

    domain = ""
    try:
        domain = project_config.domain or ""
    except Exception:
        pass

    # Build rolling history for context
    history = audit_logger.get_chat_history(req.user_id, session_id, solution, limit=10)
    history_text = ""
    for msg in history:
        prefix = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{prefix}: {msg['content']}\n"
    if history_text:
        history_text += "\n"

    # Save user message
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="user", content=req.message, page_context=req.page_context,
        message_type="user",
    )

    # Route through LLM classifier
    result = chat_route(
        message=req.message, solution=solution, domain=domain,
        page_context=req.page_context or "", history_text=history_text,
    )

    response_type = result.get("type", "answer")

    if response_type == "action":
        action_name = result.get("action", "")
        params = result.get("params", {})
        confirmation_prompt = result.get("confirmation_prompt", "")

        # query_knowledge executes server-side immediately (read-only)
        if action_name == "query_knowledge":
            try:
                from src.memory.vector_store import vector_memory
                hits = vector_memory.search(params.get("query", req.message), k=3)
                knowledge_text = "\n".join(h.get("content", "") for h in hits) if hits else "No results found."
                reply = f"From the knowledge base:\n\n{knowledge_text}"
            except Exception as exc:
                reply = f"Knowledge search unavailable: {exc}"
            message_id = audit_logger.save_chat_message(
                user_id=req.user_id, session_id=session_id, solution=solution,
                role="assistant", content=reply, page_context=req.page_context,
                message_type="answer",
            )
            return {"response_type": "answer", "reply": reply, "session_id": session_id, "message_id": message_id}

        # All other actions: return as action_proposed
        message_id = audit_logger.save_chat_message(
            user_id=req.user_id, session_id=session_id, solution=solution,
            role="assistant", content=confirmation_prompt, page_context=req.page_context,
            message_type="action_proposed",
            metadata={"action": action_name, "params": params},
        )
        return {
            "response_type": "action",
            "action": action_name,
            "params": params,
            "confirmation_prompt": confirmation_prompt,
            "session_id": session_id,
            "message_id": message_id,
        }

    # Plain answer
    reply = result.get("reply", "")
    message_id = audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="assistant", content=reply, page_context=req.page_context,
        message_type="answer",
    )
    return {"response_type": "answer", "reply": reply, "session_id": session_id, "message_id": message_id}


@app.post("/chat/execute")
async def chat_execute(req: ChatExecuteRequest):
    """Execute a chat-proposed action after human confirmation."""
    from src.core.project_loader import project_config
    from src.memory.audit_logger import audit_logger

    solution = req.solution or (project_config.project_name if project_config else "sage")
    session_id = req.session_id or str(uuid.uuid4())
    action = req.action
    params = req.params

    SUPPORTED_ACTIONS = {
        "approve_proposal", "reject_proposal", "undo_proposal",
        "submit_task", "propose_yaml_edit",
    }
    if action not in SUPPORTED_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported action: {action}")

    # Log confirmation
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="user", content=f"[Confirmed: {action}]", page_context=None,
        message_type="action_confirmed",
        metadata={"action": action, "params": params},
    )

    result_msg = ""
    result_data = {}

    try:
        if action == "approve_proposal":
            trace_id = params.get("trace_id", "")
            store = _get_proposal_store()
            proposal = store.get(trace_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
            store.approve(trace_id)
            from src.core.proposal_executor import execute_approved_proposal
            import asyncio
            asyncio.ensure_future(execute_approved_proposal(proposal))
            result_msg = f"Proposal {trace_id} approved."
            result_data = {"trace_id": trace_id}

        elif action == "reject_proposal":
            trace_id = params.get("trace_id", "")
            reason = params.get("reason", "Rejected via chat.")
            store = _get_proposal_store()
            proposal = store.get(trace_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
            store.reject(trace_id, reason)
            result_msg = f"Proposal {trace_id} rejected."
            result_data = {"trace_id": trace_id}

        elif action == "undo_proposal":
            trace_id = params.get("trace_id", "")
            store = _get_proposal_store()
            proposal = store.get(trace_id)
            if proposal is None:
                raise HTTPException(status_code=404, detail=f"Proposal '{trace_id}' not found.")
            if proposal.action_type == "code_diff":
                from src.core.proposal_executor import _revert_code_diff
                import asyncio
                asyncio.ensure_future(_revert_code_diff(proposal))
                result_msg = f"Undo triggered for proposal {trace_id}."
                result_data = {"trace_id": trace_id}
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Undo is only supported for code_diff proposals (got '{proposal.action_type}')."
                )

        elif action == "submit_task":
            from src.core.queue_manager import task_queue
            task_type = params.get("task_type", "")
            payload = params.get("payload", {})
            task_id = task_queue.submit(task_type=task_type, payload=payload, source="chat")
            result_msg = f"Task {task_id} ({task_type}) queued."
            result_data = {"task_id": task_id}

        elif action == "propose_yaml_edit":
            file_name = params.get("file", "prompts")
            change_desc = params.get("change_description", "")
            store = _get_proposal_store()
            from src.core.proposal_store import RiskClass
            p = store.create(
                action_type="yaml_edit",
                risk_class=RiskClass.STATEFUL,
                payload={"file": file_name, "change_description": change_desc},
                description=f"YAML edit via chat: {change_desc[:80]}",
                reversible=True,
            )
            result_msg = f"YAML edit proposal created (trace_id: {p.trace_id}). Review it in Approvals."
            result_data = {"trace_id": p.trace_id}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("chat/execute error for action %s: %s", action, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    # Write execution result to chat history
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="assistant", content=result_msg, page_context=None,
        message_type="action_executed",
        metadata={"action": action, **result_data},
    )

    # Write to compliance audit log
    _get_audit_logger().log_event(
        actor="human_via_chat",
        action_type=f"CHAT_EXECUTE_{action.upper()}",
        input_context=f"session={session_id} user={req.user_id}",
        output_content=result_msg,
        metadata={"action": action, "params": params, "session_id": session_id, **result_data},
    )

    return {"status": "success", "message": result_msg, "result": result_data}


@app.post("/chat/cancel")
async def chat_cancel(req: ChatExecuteRequest):
    """Log a user-cancelled action proposal to the audit trail."""
    from src.core.project_loader import project_config
    from src.memory.audit_logger import audit_logger

    solution = req.solution or (project_config.project_name if project_config else "sage")
    session_id = req.session_id or str(uuid.uuid4())
    audit_logger.save_chat_message(
        user_id=req.user_id, session_id=session_id, solution=solution,
        role="user", content=f"[Cancelled: {req.action}]", page_context=None,
        message_type="action_cancelled",
        metadata={"action": req.action, "params": req.params},
    )
    _get_audit_logger().log_event(
        actor="human_via_chat",
        action_type=f"CHAT_CANCEL_{req.action.upper()}",
        input_context=f"session={session_id} user={req.user_id}",
        output_content="Action cancelled by user",
        metadata={"action": req.action, "params": req.params, "session_id": session_id},
    )
    return {"status": "logged"}


@app.delete("/chat/history")
async def clear_chat_history(user_id: str, solution: str = ""):
    """Clear chat history for a user+solution."""
    from src.core.project_loader import project_config
    from src.memory.audit_logger import audit_logger

    sol = solution or (project_config.project_name if project_config else "sage")
    count = audit_logger.clear_chat_history(user_id, sol)
    return {"cleared": count, "user_id": user_id, "solution": sol}


# ---------------------------------------------------------------------------
# Chat Conversation Persistence (CRUD)
# ---------------------------------------------------------------------------


def _get_chat_store():
    from src.stores.chat_store import ChatStore
    from src.memory.audit_logger import _resolve_db_path
    import os

    db_path = os.path.join(os.path.dirname(_resolve_db_path()), "chat_conversations.db")
    return ChatStore(db_path)


class ConversationCreate(BaseModel):
    user_id: str
    solution: str = ""
    role_id: str = ""
    role_name: str = ""
    messages: list = []


class ConversationUpdate(BaseModel):
    title: str | None = None
    messages: list | None = None


@app.get("/conversations")
async def list_conversations(user_id: str, solution: str = ""):
    return _get_chat_store().list(user_id, solution)


@app.post("/conversations")
async def create_conversation(req: ConversationCreate):
    return _get_chat_store().create(
        req.user_id, req.solution, req.role_id, req.role_name, req.messages
    )


@app.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = _get_chat_store().get(conv_id)
    if conv is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@app.put("/conversations/{conv_id}")
async def update_conversation(conv_id: str, req: ConversationUpdate):
    result = _get_chat_store().update(conv_id, title=req.title, messages=req.messages)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@app.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if _get_chat_store().delete(conv_id):
        return {"deleted": True}
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Conversation not found")


# ---------------------------------------------------------------------------
# Goals / OKR Persistence (CRUD)
# ---------------------------------------------------------------------------


def _get_goals_store():
    from src.stores.goals_store import GoalsStore
    from src.memory.audit_logger import _resolve_db_path
    import os

    db_path = os.path.join(os.path.dirname(_resolve_db_path()), "goals.db")
    return GoalsStore(db_path)


class GoalCreate(BaseModel):
    user_id: str
    solution: str = ""
    title: str
    quarter: str
    status: str = "on_track"
    owner: str = ""
    key_results: list = []


class GoalUpdate(BaseModel):
    title: str | None = None
    quarter: str | None = None
    status: str | None = None
    owner: str | None = None
    key_results: list | None = None


@app.get("/goals")
async def list_goals(user_id: str, solution: str = "", quarter: str = ""):
    return _get_goals_store().list(
        user_id, solution, quarter=quarter or None
    )


@app.post("/goals")
async def create_goal(req: GoalCreate):
    return _get_goals_store().create(
        req.user_id, req.solution, req.title,
        req.quarter, req.status, req.owner, req.key_results,
    )


@app.get("/goals/{goal_id}")
async def get_goal(goal_id: str):
    goal = _get_goals_store().get(goal_id)
    if goal is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@app.put("/goals/{goal_id}")
async def update_goal(goal_id: str, req: GoalUpdate):
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    result = _get_goals_store().update(goal_id, **kwargs)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Goal not found")
    return result


@app.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str):
    if _get_goals_store().delete(goal_id):
        return {"deleted": True}
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Goal not found")


# ---------------------------------------------------------------------------
# Connector Framework
# ---------------------------------------------------------------------------


@app.get("/connectors")
async def list_connectors():
    """List available connector types."""
    from src.connectors import connector_registry
    return {"connectors": connector_registry.get_info()}


class ConnectorConfigRequest(BaseModel):
    config: dict


@app.post("/connectors/{connector_type}/configure")
async def configure_connector(connector_type: str, req: ConnectorConfigRequest):
    """Create and configure a connector instance."""
    from src.connectors import connector_registry
    try:
        c = connector_registry.create(connector_type)
        ok = c.connect(req.config)
        return {"type": connector_type, "connected": ok}
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown connector type: {connector_type}")


@app.post("/connectors/{connector_type}/sync")
async def sync_connector(connector_type: str, req: ConnectorConfigRequest):
    """Configure and sync a connector."""
    from src.connectors import connector_registry
    try:
        c = connector_registry.create(connector_type)
        if not c.connect(req.config):
            return {"error": "Connection failed", "type": connector_type}
        result = c.sync()
        return {"type": connector_type, **result}
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown connector type: {connector_type}")
