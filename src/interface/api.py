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
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


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
# Multi-Tenant Middleware (Phase 10)
# ---------------------------------------------------------------------------

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest


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


class FeatureRequestCreate(BaseModel):
    module_id: str
    module_name: str
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
async def shutdown():
    """
    Gracefully stop the SAGE backend and the Vite frontend dev server.
    Called by the web UI Stop button.
    """
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
                })
            except Exception:
                projects.append({"id": name, "name": name, "domain": "general",
                                  "version": "1.0.0", "description": "", "active_modules": []})
    active = _get_project_config().metadata.get("project", "")
    return {"projects": projects, "active": active}


class SwitchProjectRequest(BaseModel):
    project: str


class SetModulesRequest(BaseModel):
    modules: list[str]


@app.post("/config/switch")
async def switch_project(req: SwitchProjectRequest):
    """
    Propose switching the active solution at runtime.
    Returns an EPHEMERAL proposal — actual switch on POST /approve/{trace_id}.
    """
    from src.core.project_loader import _SOLUTIONS_DIR
    from src.core.proposal_store import RiskClass
    import os as _os
    proj_dir = _os.path.join(_SOLUTIONS_DIR, req.project)
    if not _os.path.isdir(proj_dir):
        raise HTTPException(status_code=404, detail=f"Solution '{req.project}' not found in {_SOLUTIONS_DIR}")
    current_project = _get_project_config().project_name
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "config_switch",
        risk_class    = RiskClass.EPHEMERAL,
        payload       = {"project": req.project, "previous_project": current_project},
        description   = f"Switch active solution: {current_project} → {req.project}",
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("config_switch"),
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
        "message":     "POST /approve/{trace_id} to switch.",
    }



@app.post("/config/modules")
async def set_modules(req: SetModulesRequest):
    """
    Propose updating the active modules list for the current solution.
    Returns an EPHEMERAL proposal — actual change on POST /approve/{trace_id}.
    """
    from src.core.proposal_store import RiskClass
    current_modules = _get_project_config().metadata.get("active_modules", [])
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "config_modules",
        risk_class    = RiskClass.EPHEMERAL,
        payload       = {"modules": req.modules, "previous_modules": current_modules},
        description   = f"Update active modules: {current_modules} → {req.modules}",
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("config_modules"),
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
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
        logger.error("list_queue_tasks error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


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
    scope_context = (
        "This is a SAGE FRAMEWORK improvement — implement in src/ and web/src/. "
        "Output concrete file-level implementation steps."
        if scope == 'sage' else
        "This is a SOLUTION feature — implement in the active solution's codebase."
    )
    planner_task = (
        f"{scope_context}\n"
        f"Title: {req['title']}\n"
        f"Description: {req['description']}\n"
        f"Priority: {req['priority']}"
    )

    try:
        planner = _get_planner()
        from src.agents.planner import PlannerAgent
        task_types = PlannerAgent.FRAMEWORK_TASK_TYPES if scope == "sage" else None
        steps = planner.create_plan(planner_task, override_task_types=task_types)
    except Exception as e:
        logger.error("Planner failed for feature request %s: %s", req_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    if not steps:
        raise HTTPException(status_code=422, detail="LLM could not produce an executable plan. Try rephrasing the description.")

    # Store as a ProposalStore entry (HITL — nothing executes until approved)
    from src.core.proposal_store import RiskClass
    store = _get_proposal_store()
    required_role = _get_required_role("implementation_plan_sage") if scope == "sage" else None
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
        required_role=required_role,
    )

    now = datetime.now(timezone.utc).isoformat()
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
        "status": "in_planning",
        "trace_id": proposal.trace_id,
        "step_count": len(steps),
        "plan": steps,
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


class LLMSwitchRequest(BaseModel):
    provider: str   # "gemini" | "local" | "claude-code" | "claude"
    model: Optional[str] = None   # gemini model name, GGUF path, or claude model name
    api_key: Optional[str] = None  # Anthropic API key (claude only, stored in env)
    claude_path: Optional[str] = None  # Custom path to claude.exe (claude-code only)
    save_as_default: bool = False  # If True, persist selection to config.yaml


@app.post("/llm/switch")
async def llm_switch(req: LLMSwitchRequest):
    """
    Propose switching the LLM provider at runtime.
    Returns an EPHEMERAL proposal (5-min expiry) — actual switch on POST /approve/{trace_id}.
    """
    from src.core.proposal_store import RiskClass
    allowed = ("gemini", "local", "claude-code", "claude", "ollama", "generic-cli")
    if req.provider not in allowed:
        raise HTTPException(status_code=400, detail=f"provider must be one of: {allowed}")
    current_provider = _get_llm_gateway().get_provider_name()
    store = _get_proposal_store()
    proposal = store.create(
        action_type   = "llm_switch",
        risk_class    = RiskClass.EPHEMERAL,
        payload       = {
            "provider":        req.provider,
            "model":           req.model,
            "api_key":         req.api_key,
            "claude_path":     req.claude_path,
            "save_as_default": req.save_as_default,
        },
        description   = f"Switch LLM provider: {current_provider} → {req.provider}" + (f" ({req.model})" if req.model else "") + (" [save as default]" if req.save_as_default else ""),
        reversible    = True,
        proposed_by   = "user",
        required_role = _get_required_role("llm_switch"),
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
        "expires_at":  proposal.expires_at,
        "message":     "POST /approve/{trace_id} to apply. Expires in 5 minutes.",
    }


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
        "integrations": [str]            — optional list (default: ["gitlab"])
    }

    Returns: { solution_name, path, status, files, message }
    status = "created" | "exists"
    """
    body = await request.json()
    description   = body.get("description", "").strip()
    solution_name = body.get("solution_name", "").strip()
    compliance    = body.get("compliance_standards", [])
    integrations  = body.get("integrations", ["gitlab"])

    if not description:
        raise HTTPException(status_code=400, detail="description is required")
    if not solution_name:
        raise HTTPException(status_code=400, detail="solution_name is required")

    try:
        from src.core.onboarding import generate_solution
        result = generate_solution(
            description=description,
            solution_name=solution_name,
            compliance_standards=compliance,
            integrations=integrations,
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


@app.post("/knowledge/add")
async def knowledge_add(request: Request):
    """
    Propose adding a knowledge entry to the vector store.
    Returns STATEFUL proposal — actual add on POST /approve/{trace_id}.
    Body: { "text": str, "metadata": dict (optional) }
    """
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    metadata = body.get("metadata", {})
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
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    from src.memory.vector_store import vector_memory
    results = vector_memory.search(query, k=k)
    return {"results": results, "count": len(results), "query": query}


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
