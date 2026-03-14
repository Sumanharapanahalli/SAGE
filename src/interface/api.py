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
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
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
        action_type = "config_switch",
        risk_class  = RiskClass.EPHEMERAL,
        payload     = {"project": req.project, "previous_project": current_project},
        description = f"Switch active solution: {current_project} → {req.project}",
        reversible  = True,
        proposed_by = "user",
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
        action_type = "config_modules",
        risk_class  = RiskClass.EPHEMERAL,
        payload     = {"modules": req.modules, "previous_modules": current_modules},
        description = f"Update active modules: {current_modules} → {req.modules}",
        reversible  = True,
        proposed_by = "user",
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
        action_type = "yaml_edit",
        risk_class  = RiskClass.STATEFUL,
        payload     = {
            "file":     file_name,
            "content":  req.content,
            "solution": project_config.project_name,
            "previous_content": current,
        },
        description = f"Edit {file_name}.yaml ({diff_summary})",
        reversible  = True,
        proposed_by = "user",
    )
    return {
        "status":      "pending_approval",
        "trace_id":    proposal.trace_id,
        "description": proposal.description,
        "diff_summary": diff_summary,
        "message":     "Review the change and POST /approve/{trace_id} to apply.",
    }


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


@app.post("/approve/{trace_id}")
async def approve(trace_id: str, body: ApproveProposalRequest = ApproveProposalRequest()):
    """
    Approve a pending proposal.

    For analysis proposals: records approval in audit log.
    For action proposals (yaml_edit, llm_switch, etc.): executes the action.

    Args:
        trace_id: The trace ID from a previous proposal response.
    """
    from src.core.proposal_executor import execute_approved_proposal

    # --- Check ProposalStore first (HITL action proposals) ---
    store = _get_proposal_store()
    proposal = store.get(trace_id)
    if proposal and proposal.status == "pending":
        approved = store.approve(trace_id, decided_by=body.decided_by, feedback=body.feedback)
        # Execute the action
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
async def reject(trace_id: str, request: RejectRequest):
    """
    Reject a pending proposal with human feedback.

    For analysis proposals: stores feedback in vector memory for learning.
    For action proposals: marks rejected, no action taken.

    Request body: {"feedback": "The real root cause is..."}
    """
    # --- Check ProposalStore first (HITL action proposals) ---
    store = _get_proposal_store()
    proposal = store.get(trace_id)
    if proposal and proposal.status == "pending":
        store.reject(trace_id, decided_by="human", feedback=request.feedback)
        try:
            _get_audit_logger().log_event(
                actor="human",
                action_type="PROPOSAL_REJECTED",
                input_context=f"trace_id={trace_id} action={proposal.action_type}",
                output_content=request.feedback,
                metadata={"trace_id": trace_id, "risk_class": proposal.risk_class.value},
            )
        except Exception as e:
            logger.error("Audit log failed on reject: %s", e)
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
        "This is a SOLUTION feature request — it should be implemented in the active solution's codebase."
        if scope == 'solution' else
        "This is a SAGE FRAMEWORK improvement request — it should be implemented in the SAGE framework itself (src/, web/src/)."
    )
    planner_task = (
        f"{scope_context}\n"
        f"Feature request for the '{req['module_name']}' module.\n"
        f"Title: {req['title']}\n"
        f"Description: {req['description']}\n"
        f"Priority: {req['priority']}"
    )

    try:
        planner = _get_planner()
        result = planner.plan_and_execute(planner_task)
    except Exception as e:
        logger.error("Planner failed for feature request %s: %s", req_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    # Update status
    now = datetime.now(timezone.utc).isoformat()
    try:
        db_path = _get_db_path()
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE feature_requests SET status='in_planning', plan_trace_id=?, updated_at=? WHERE id=?",
            (result.get("trace_id"), now, req_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("DB update failed after planning: %s", e)

    return {"request_id": req_id, "status": "in_planning", "plan": result}


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
            "project": project_config.project_name or os.environ.get("SAGE_PROJECT", ""),
        },
    }


class LLMSwitchRequest(BaseModel):
    provider: str   # "gemini" | "local" | "claude-code" | "claude"
    model: Optional[str] = None   # gemini model name, GGUF path, or claude model name
    api_key: Optional[str] = None  # Anthropic API key (claude only, stored in env)
    claude_path: Optional[str] = None  # Custom path to claude.exe (claude-code only)


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
        action_type = "llm_switch",
        risk_class  = RiskClass.EPHEMERAL,
        payload     = {
            "provider":    req.provider,
            "model":       req.model,
            "api_key":     req.api_key,
            "claude_path": req.claude_path,
        },
        description = f"Switch LLM provider: {current_provider} → {req.provider}" + (f" ({req.model})" if req.model else ""),
        reversible  = True,
        proposed_by = "user",
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
        action_type = "knowledge_add",
        risk_class  = RiskClass.STATEFUL,
        payload     = {"text": text, "metadata": metadata},
        description = f"Add knowledge entry: \"{preview}\"",
        reversible  = True,
        proposed_by = "user",
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
        action_type = "knowledge_delete",
        risk_class  = RiskClass.DESTRUCTIVE,
        payload     = {"entry_id": entry_id, "preview": preview},
        description = f"DELETE knowledge entry {entry_id}: \"{preview}\"",
        reversible  = False,
        proposed_by = "user",
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
        action_type = "knowledge_import",
        risk_class  = RiskClass.STATEFUL,
        payload     = {"entries": entries},
        description = f"Bulk import {len(entries)} knowledge entries (sample: \"{sample}\")",
        reversible  = True,
        proposed_by = "user",
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
