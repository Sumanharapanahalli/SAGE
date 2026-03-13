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
    Switch the active solution at runtime.
    Reloads project config, prompts, and task definitions for the given solution.
    The web UI calls this when the user selects a different solution from the dropdown.
    """
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    import os as _os
    proj_dir = _os.path.join(_SOLUTIONS_DIR, req.project)
    if not _os.path.isdir(proj_dir):
        raise HTTPException(status_code=404, detail=f"Solution '{req.project}' not found in {_SOLUTIONS_DIR}")
    try:
        project_config.reload(req.project)
        pc = _get_project_config()
        logger.info("Switched active project to: %s", req.project)
        return {
            "switched": True,
            "project": req.project,
            **pc.metadata,
            "task_types": pc.get_task_types(),
        }
    except Exception as e:
        logger.error("Failed to switch project to %s: %s", req.project, e)
        raise HTTPException(status_code=500, detail=f"Failed to switch project: {e}")



@app.post("/config/modules")
async def set_modules(req: SetModulesRequest):
    """
    Override the active modules list for the current solution at runtime.
    Changes are in-memory only — reload the solution to reset to YAML defaults.
    """
    from src.core.project_loader import project_config
    project_config.set_active_modules(req.modules)
    return {"active_modules": req.modules}


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
    Overwrite a solution YAML config file (project | prompts | tasks).
    Validates that the content is parseable YAML before writing.
    Reloads the project config after a successful write.
    """
    import yaml as _yaml
    allowed = {"project", "prompts", "tasks"}
    if file_name not in allowed:
        raise HTTPException(status_code=400, detail=f"file_name must be one of: {sorted(allowed)}")
    # Validate YAML before touching the file
    try:
        _yaml.safe_load(req.content)
    except _yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {e}")
    from src.core.project_loader import project_config, _SOLUTIONS_DIR
    path = os.path.join(_SOLUTIONS_DIR, project_config.project_name, f"{file_name}.yaml")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"{file_name}.yaml not found for solution '{project_config.project_name}'")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(req.content)
    # Reload so the running process picks up the changes
    project_config.reload(project_config.project_name)
    logger.info("YAML file saved and config reloaded: %s/%s.yaml", project_config.project_name, file_name)
    return {"saved": True, "file": file_name, "solution": project_config.project_name}


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


@app.post("/approve/{trace_id}")
async def approve(trace_id: str):
    """
    Approves a pending AI proposal, executing the recommended action.

    Args:
        trace_id: The trace ID from a previous /analyze response.
    """
    if trace_id not in _pending_proposals:
        raise HTTPException(status_code=404, detail=f"Trace ID '{trace_id}' not found or already processed.")

    proposal_entry = _pending_proposals[trace_id]
    proposal_entry["status"] = "approved"

    # Audit the approval
    try:
        audit = _get_audit_logger()
        audit.log_event(
            actor="Human_Engineer",
            action_type="APPROVAL",
            input_context=f"trace_id={trace_id}",
            output_content=json.dumps(proposal_entry["proposal"]),
            metadata={"trace_id": trace_id, "approved_via": "api"},
        )
    except Exception as e:
        logger.error("Audit log failed on approve: %s", e)

    del _pending_proposals[trace_id]
    logger.info("Proposal approved via API: trace_id=%s", trace_id)

    return {
        "status": "approved",
        "trace_id": trace_id,
        "message": "Proposal approved and logged. Action may now be executed.",
    }


@app.post("/reject/{trace_id}")
async def reject(trace_id: str, request: RejectRequest):
    """
    Rejects a pending AI proposal with human feedback (enables learning).

    Args:
        trace_id: The trace ID from a previous /analyze response.

    Request body: {"feedback": "The real root cause is..."}
    """
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
    logger.info("Proposal rejected with feedback via API: trace_id=%s", trace_id)

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
    Switch LLM provider at runtime (gemini, local, or claude).
    Reinitialises the LLMGateway with the new provider.
    """
    from src.core.llm_gateway import LLMGateway, GeminiCLIProvider, LocalLlamaProvider, ClaudeCodeCLIProvider, ClaudeAPIProvider
    import yaml

    if req.provider not in ("gemini", "local", "claude-code", "claude"):
        raise HTTPException(status_code=400, detail="provider must be 'gemini', 'local', 'claude-code', or 'claude'")

    try:
        with open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "config.yaml"
        )) as f:
            cfg = yaml.safe_load(f) or {}
        llm_cfg = cfg.get("llm", {})

        if req.provider == "gemini" and req.model:
            llm_cfg["gemini_model"] = req.model
        elif req.provider == "local" and req.model:
            llm_cfg["model_path"] = req.model
        elif req.provider == "claude-code":
            if req.model:
                llm_cfg["claude_model"] = req.model
            if req.claude_path:
                llm_cfg["claude_path"] = req.claude_path
        elif req.provider == "claude":
            if req.model:
                llm_cfg["claude_model"] = req.model
            if req.api_key:
                os.environ["ANTHROPIC_API_KEY"] = req.api_key

        gw = LLMGateway()
        if req.provider == "gemini":
            gw.provider = GeminiCLIProvider(llm_cfg)
        elif req.provider == "local":
            gw.provider = LocalLlamaProvider(llm_cfg)
        elif req.provider == "claude-code":
            gw.provider = ClaudeCodeCLIProvider(llm_cfg)
        else:
            gw.provider = ClaudeAPIProvider(llm_cfg)

        logger.info("LLM provider switched to: %s", gw.get_provider_name())
        gw.reset_usage()

        return {
            "switched": True,
            "provider": req.provider,
            "provider_name": gw.get_provider_name(),
            "model": req.model,
        }
    except Exception as e:
        logger.error("LLM switch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
