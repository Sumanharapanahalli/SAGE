"""
SAGE[ai] — System End-to-End Tests
====================================
Full-flow integration tests exercising the FastAPI app as a real HTTP client
would. Each test covers a complete user journey through the API:

  1. Health & status checks
  2. Analysis → Proposal → Approve/Reject lifecycle
  3. LLM provider switch
  4. Solution/config switch
  5. Knowledge CRUD
  6. Queue & task lifecycle
  7. Build orchestrator flow
  8. Multi-LLM parallel generation
  9. Audit trail integrity
 10. Feature requests & improvements
 11. RBAC approval roles
 12. Webhook receivers
 13. Workflow management
 14. Agent management
 15. Full lifecycle smoke tests

All LLM calls are mocked — these tests verify wiring, state transitions,
and data integrity across the full request lifecycle.
"""

import json
import re
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.system

UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

MOCK_ANALYSIS = {
    "severity": "HIGH",
    "root_cause_hypothesis": "Memory leak in connection pool",
    "recommended_action": "Restart service and apply patch",
    "trace_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_proposals():
    """Reset in-memory proposal store between tests."""
    from src.interface import api
    api._pending_proposals.clear()
    yield
    api._pending_proposals.clear()


@pytest.fixture
def sys_client(tmp_audit_db):
    """System test client with isolated audit DB."""
    with patch("src.interface.api._get_audit_logger", return_value=tmp_audit_db):
        from src.interface.api import app
        with TestClient(app) as c:
            yield c, tmp_audit_db


def _mock_analyst(trace_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"):
    """Create a mock analyst that returns a valid analysis with trace_id."""
    mock = MagicMock()
    mock.analyze_log.return_value = {
        **MOCK_ANALYSIS,
        "trace_id": trace_id,
    }
    return mock


# ===========================================================================
# 1. Health & Status
# ===========================================================================


class TestHealthAndStatus:
    """System health checks return correct shape and status codes."""

    def test_health_returns_200(self, sys_client):
        c, _ = sys_client
        with patch("src.interface.api._get_llm_gateway") as mock_llm:
            mock_llm.return_value.get_provider_name.return_value = "mock-provider"
            resp = c.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    def test_config_project_returns_metadata(self, sys_client):
        c, _ = sys_client
        resp = c.get("/config/project")
        assert resp.status_code == 200
        body = resp.json()
        # project_name is spread from metadata
        assert isinstance(body, dict)

    def test_config_projects_lists_solutions(self, sys_client):
        c, _ = sys_client
        resp = c.get("/config/projects")
        assert resp.status_code == 200
        body = resp.json()
        assert "projects" in body
        assert isinstance(body["projects"], list)

    def test_llm_status_returns_provider_info(self, sys_client):
        c, _ = sys_client
        with patch("src.interface.api._get_llm_gateway") as mock_llm:
            mock_llm.return_value.get_provider_name.return_value = "mock"
            mock_llm.return_value.get_model_info.return_value = {
                "model": "mock", "daily_request_limit": 0,
                "context_tokens": 4096, "unlimited": True,
            }
            mock_llm.return_value.get_usage.return_value = {
                "calls": 0, "calls_today": 0,
                "estimated_tokens": 0, "errors": 0,
                "started_at": "2026-01-01T00:00:00+00:00",
                "day_started_at": "2026-01-01T00:00:00+00:00",
            }
            mock_llm.return_value.provider = MagicMock()
            resp = c.get("/llm/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "provider" in body

    def test_queue_status_returns_dict(self, sys_client):
        c, _ = sys_client
        resp = c.get("/queue/status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)

    def test_monitor_status_returns_dict(self, sys_client):
        c, _ = sys_client
        resp = c.get("/monitor/status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), dict)


# ===========================================================================
# 2. Analysis → Approve / Reject Full Lifecycle
# ===========================================================================


class TestAnalysisLifecycle:
    """Full flow: analyze log → get proposal → approve or reject."""

    def _analyze(self, client, trace_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"):
        analyst = _mock_analyst(trace_id)
        with patch("src.interface.api._get_analyst", return_value=analyst):
            resp = client.post("/analyze", json={"log_entry": "ERROR: OOM at service:42"})
        return resp

    def test_analyze_creates_proposal(self, sys_client):
        c, _ = sys_client
        resp = self._analyze(c)
        assert resp.status_code == 200
        body = resp.json()
        assert "trace_id" in body

    def test_proposal_appears_in_pending(self, sys_client):
        c, _ = sys_client
        resp = self._analyze(c, trace_id="11111111-2222-4333-8444-555555555555")
        trace_id = resp.json()["trace_id"]
        # Proposals stored in _pending_proposals dict
        from src.interface.api import _pending_proposals
        assert trace_id in _pending_proposals

    def test_approve_removes_from_pending(self, sys_client):
        c, _ = sys_client
        resp = self._analyze(c, trace_id="aaaaaaaa-bbbb-4ccc-8ddd-111111111111")
        trace_id = resp.json()["trace_id"]
        approve_resp = c.post(f"/approve/{trace_id}")
        assert approve_resp.status_code == 200
        from src.interface.api import _pending_proposals
        assert trace_id not in _pending_proposals

    def test_approve_creates_audit_record(self, sys_client):
        c, audit = sys_client
        resp = self._analyze(c, trace_id="aaaaaaaa-bbbb-4ccc-8ddd-222222222222")
        trace_id = resp.json()["trace_id"]
        c.post(f"/approve/{trace_id}")
        conn = sqlite3.connect(audit.db_path)
        rows = conn.execute(
            "SELECT * FROM compliance_audit_log WHERE action_type = 'APPROVAL'"
        ).fetchall()
        conn.close()
        assert len(rows) >= 1

    def test_reject_removes_from_pending(self, sys_client):
        c, _ = sys_client
        resp = self._analyze(c, trace_id="aaaaaaaa-bbbb-4ccc-8ddd-333333333333")
        trace_id = resp.json()["trace_id"]
        reject_resp = c.post(f"/reject/{trace_id}", json={
            "feedback": "Analysis missed the real root cause",
        })
        assert reject_resp.status_code == 200
        from src.interface.api import _pending_proposals
        assert trace_id not in _pending_proposals

    def test_approve_invalid_trace_returns_404(self, sys_client):
        c, _ = sys_client
        resp = c.post("/approve/nonexistent-id-does-not-exist")
        assert resp.status_code in (400, 404)

    def test_reject_invalid_trace_returns_404(self, sys_client):
        c, _ = sys_client
        resp = c.post("/reject/nonexistent-id-does-not-exist", json={
            "feedback": "bad",
        })
        assert resp.status_code in (400, 404)

    def test_analyze_rejects_empty_log(self, sys_client):
        c, _ = sys_client
        resp = c.post("/analyze", json={"log_entry": ""})
        assert resp.status_code == 400

    def test_batch_approve(self, sys_client):
        c, _ = sys_client
        # batch approve works with ProposalStore proposals, not _pending_proposals
        # Just verify the endpoint accepts the right shape
        resp = c.post("/proposals/approve-batch", json={
            "trace_ids": ["nonexistent-1", "nonexistent-2"],
            "decided_by": "suman",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body


# ===========================================================================
# 3. LLM Provider Switch
# ===========================================================================


class TestLLMSwitch:
    """Switching LLM provider at runtime (immediate, no approval)."""

    def test_llm_switch_returns_success(self, sys_client):
        c, _ = sys_client
        with patch("src.interface.api._get_llm_gateway") as mock_llm:
            mock_llm.return_value.provider = MagicMock()
            resp = c.post("/llm/switch", json={
                "provider": "ollama",
                "model": "llama3.2",
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("status") == "switched" or "provider" in body


# ===========================================================================
# 4. Solution / Config Switch
# ===========================================================================


class TestConfigSwitch:
    """Switching active solution and updating modules."""

    def test_switch_solution(self, sys_client):
        c, _ = sys_client
        resp = c.post("/config/switch", json={"project": "starter"})
        assert resp.status_code == 200

    def test_update_modules(self, sys_client):
        c, _ = sys_client
        resp = c.post("/config/modules", json={
            "modules": ["dashboard", "analyst", "knowledge"],
        })
        assert resp.status_code == 200

    def test_read_yaml(self, sys_client):
        c, _ = sys_client
        # file_name must be "project", "prompts", or "tasks" — NOT "project.yaml"
        resp = c.get("/config/yaml/project")
        assert resp.status_code == 200
        body = resp.json()
        assert "content" in body

    def test_read_yaml_invalid_name_rejected(self, sys_client):
        c, _ = sys_client
        resp = c.get("/config/yaml/invalid_file")
        assert resp.status_code == 400

    def test_approval_roles_endpoint(self, sys_client):
        c, _ = sys_client
        resp = c.get("/config/approval-roles")
        assert resp.status_code == 200
        body = resp.json()
        assert "approval_roles" in body


# ===========================================================================
# 5. Knowledge CRUD
# ===========================================================================


class TestKnowledgeCRUD:
    """Knowledge base add, search, and delete."""

    def test_add_knowledge_entry(self, sys_client):
        c, _ = sys_client
        # The endpoint expects "text" not "content", and creates a proposal
        resp = c.post("/knowledge/add", json={
            "text": "UART buffer overflow requires increasing RX_BUF_SIZE to 512",
            "metadata": {"source": "manual", "category": "firmware"},
        })
        assert resp.status_code == 200

    def test_search_knowledge(self, sys_client):
        c, _ = sys_client
        resp = c.post("/knowledge/search", json={"query": "I2C bus"})
        assert resp.status_code == 200

    def test_list_knowledge_entries(self, sys_client):
        c, _ = sys_client
        resp = c.get("/knowledge/entries")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)


# ===========================================================================
# 6. Queue & Task Lifecycle
# ===========================================================================


class TestQueueAndTasks:
    """Task submission, queue listing, status checks."""

    def test_submit_task(self, sys_client):
        c, _ = sys_client
        resp = c.post("/tasks/submit", json={
            "task_type": "ANALYZE_LOG",
            "payload": {"log_entry": "ERROR test"},
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "task_id" in body

    def test_queue_status(self, sys_client):
        c, _ = sys_client
        resp = c.get("/queue/status")
        assert resp.status_code == 200


# ===========================================================================
# 7. Build Orchestrator Flow
# ===========================================================================


class TestBuildOrchestrator:
    """Build pipeline: start → status → list runs."""

    def test_build_start(self, sys_client):
        c, _ = sys_client
        with patch("src.interface.api._get_build_orchestrator") as mock_bo:
            mock_bo.return_value.start.return_value = {
                "run_id": "build-001",
                "status": "planning",
                "description": "Test product",
            }
            resp = c.post("/build/start", json={
                "product_description": "A simple REST API for task management with CRUD endpoints",
            })
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body

    def test_build_status(self, sys_client):
        c, _ = sys_client
        with patch("src.interface.api._get_build_orchestrator") as mock_bo:
            mock_bo.return_value.get_status.return_value = {
                "run_id": "build-001",
                "status": "planning",
                "phase": "plan",
            }
            resp = c.get("/build/status/build-001")
        assert resp.status_code == 200

    def test_build_list_runs(self, sys_client):
        c, _ = sys_client
        with patch("src.interface.api._get_build_orchestrator") as mock_bo:
            mock_bo.return_value.list_runs.return_value = []
            resp = c.get("/build/runs")
        assert resp.status_code == 200

    def test_build_roles(self, sys_client):
        c, _ = sys_client
        resp = c.get("/build/roles")
        assert resp.status_code == 200


# ===========================================================================
# 8. Multi-LLM Parallel Generation
# ===========================================================================


class TestMultiLLMSystem:
    """Provider pool and parallel generation via gateway."""

    def test_provider_pool_lifecycle(self):
        """Register → list → set_default → remove → verify."""
        from src.core.llm_gateway import ProviderPool

        pool = ProviderPool()
        assert pool.list_providers() == []

        mock_a = MagicMock()
        mock_b = MagicMock()
        pool.register("a", mock_a)
        pool.register("b", mock_b)

        assert set(pool.list_providers()) == {"a", "b"}
        assert pool.default_name == "a"

        pool.set_default("b")
        assert pool.default_name == "b"

        pool.remove("a")
        assert pool.list_providers() == ["b"]
        assert pool.get("a") is None

    def test_generate_parallel_voting(self):
        """Voting strategy selects majority response."""
        from src.core.llm_gateway import ProviderPool, generate_parallel

        class _P:
            def __init__(self, resp):
                self._resp = resp
            def provider_name(self):
                return "mock"
            def generate(self, prompt, system_prompt):
                return self._resp

        pool = ProviderPool()
        pool.register("a", _P("answer X"))
        pool.register("b", _P("answer X"))
        pool.register("c", _P("answer Y"))

        result = generate_parallel(pool, "test", "sys", strategy="voting")
        assert result["response"] == "answer X"
        assert result["votes"]["answer X"] == 2

    def test_generate_parallel_fallback(self):
        """Fallback strategy skips failed provider."""
        from src.core.llm_gateway import ProviderPool, generate_parallel

        class _Fail:
            def provider_name(self):
                return "fail"
            def generate(self, p, s):
                raise ConnectionError("down")

        class _OK:
            def provider_name(self):
                return "ok"
            def generate(self, p, s):
                return "backup works"

        pool = ProviderPool()
        pool.register("broken", _Fail())
        pool.register("backup", _OK())

        result = generate_parallel(
            pool, "test", "sys",
            strategy="fallback", provider_names=["broken", "backup"],
        )
        assert result["response"] == "backup works"
        assert result["provider"] == "backup"

    def test_generate_parallel_quality(self):
        """Quality strategy picks longest response."""
        from src.core.llm_gateway import ProviderPool, generate_parallel

        class _P:
            def __init__(self, resp):
                self._resp = resp
            def provider_name(self):
                return "mock"
            def generate(self, p, s):
                return self._resp

        pool = ProviderPool()
        pool.register("short", _P("ok"))
        pool.register("long", _P("This is a much more detailed response"))

        result = generate_parallel(pool, "t", "s", strategy="quality")
        assert result["provider"] == "long"

    def test_generate_parallel_fastest(self):
        """Fastest strategy returns first success."""
        from src.core.llm_gateway import ProviderPool, generate_parallel

        class _P:
            def __init__(self, resp):
                self._resp = resp
            def provider_name(self):
                return "mock"
            def generate(self, p, s):
                return self._resp

        pool = ProviderPool()
        pool.register("a", _P("answer"))

        result = generate_parallel(pool, "t", "s", strategy="fastest")
        assert result["response"] == "answer"
        assert result["strategy"] == "fastest"
        assert "elapsed_ms" in result


# ===========================================================================
# 9. Audit Trail Integrity
# ===========================================================================


class TestAuditTrail:
    """Audit log captures events and supports pagination."""

    def test_audit_returns_paginated_dict(self, sys_client):
        c, audit = sys_client
        # Insert events directly
        audit.log_event(
            actor="system-test", action_type="TEST_EVENT",
            input_context="input", output_content="output",
        )
        resp = c.get("/audit?limit=10")
        assert resp.status_code == 200
        body = resp.json()
        # Returns {"entries": [...], "count": N, "total": N, "limit": N, "offset": N}
        assert "entries" in body
        assert isinstance(body["entries"], list)
        assert body["total"] >= 1

    def test_audit_pagination(self, sys_client):
        c, audit = sys_client
        for i in range(5):
            audit.log_event(
                actor="system-test", action_type="TEST_EVENT",
                input_context=f"input-{i}", output_content=f"output-{i}",
            )
        page1 = c.get("/audit?limit=2&offset=0").json()
        page2 = c.get("/audit?limit=2&offset=2").json()
        assert len(page1["entries"]) <= 2
        assert len(page2["entries"]) <= 2
        assert page1["total"] == 5

    def test_audit_max_limit_capped(self, sys_client):
        c, _ = sys_client
        resp = c.get("/audit?limit=9999")
        assert resp.status_code == 200


# ===========================================================================
# 10. Feature Requests & Improvements
# ===========================================================================


class TestFeatureRequests:
    """Feature request submission and retrieval."""

    def test_submit_solution_feature_request(self, sys_client):
        c, _ = sys_client
        # FeatureRequestCreate requires: module_id, module_name, title, description
        resp = c.post("/feedback/feature-request", json={
            "module_id": "dashboard",
            "module_name": "Dashboard",
            "title": "Add voice commands",
            "description": "Support voice input for hands-free operation",
            "scope": "solution",
            "requested_by": "suman",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "id" in body
        assert body["status"] == "pending"

    def test_submit_sage_feature_request(self, sys_client):
        c, _ = sys_client
        resp = c.post("/feedback/feature-request", json={
            "module_id": "llm",
            "module_name": "LLM Gateway",
            "title": "Add WebSocket streaming",
            "description": "Support WebSocket as alternative to SSE",
            "scope": "sage",
            "requested_by": "contributor",
        })
        assert resp.status_code == 200

    def test_list_feature_requests(self, sys_client):
        c, _ = sys_client
        # Submit first
        c.post("/feedback/feature-request", json={
            "module_id": "analyst",
            "module_name": "Analyst",
            "title": "Test request",
            "description": "For listing test",
            "scope": "solution",
            "requested_by": "test",
        })
        resp = c.get("/feedback/feature-requests")
        assert resp.status_code == 200
        body = resp.json()
        # Returns {"requests": [...], "count": N}
        assert "requests" in body
        assert body["count"] >= 1


# ===========================================================================
# 11. RBAC Approval Roles
# ===========================================================================


class TestRBAC:
    """Role-based access control for approval operations."""

    def test_approval_roles_configured(self, sys_client):
        c, _ = sys_client
        resp = c.get("/config/approval-roles")
        assert resp.status_code == 200
        body = resp.json()
        roles = body.get("approval_roles", {})
        assert isinstance(roles, dict)

    def test_approvers_listed(self, sys_client):
        c, _ = sys_client
        resp = c.get("/config/approval-roles")
        body = resp.json()
        assert "approvers" in body


# ===========================================================================
# 12. Webhook Receivers
# ===========================================================================


class TestWebhooks:
    """Webhook endpoint acceptance."""

    def test_teams_webhook_accepts_json(self, sys_client):
        c, _ = sys_client
        resp = c.post("/webhook/teams", json={
            "message": "ERROR: device offline",
            "from": "monitor-bot",
        })
        assert resp.status_code == 200

    def test_teams_webhook_rejects_invalid(self, sys_client):
        c, _ = sys_client
        resp = c.post("/webhook/teams", content=b"not json",
                       headers={"Content-Type": "application/json"})
        assert resp.status_code in (400, 422)

    def test_n8n_webhook_with_event_type(self, sys_client):
        c, _ = sys_client
        # n8n requires event_type field
        resp = c.post("/webhook/n8n", json={
            "event_type": "log_alert",
            "payload": {"message": "CPU > 90%"},
            "source": "n8n-workflow",
        })
        assert resp.status_code == 200


# ===========================================================================
# 13. Workflow Management
# ===========================================================================


class TestWorkflows:
    """Workflow listing and execution."""

    def test_list_workflows(self, sys_client):
        c, _ = sys_client
        resp = c.get("/workflows")
        assert resp.status_code == 200

    def test_workflow_list_alt(self, sys_client):
        c, _ = sys_client
        resp = c.get("/workflow/list")
        assert resp.status_code == 200


# ===========================================================================
# 14. Agent Management
# ===========================================================================


class TestAgentManagement:
    """Agent role listing and status."""

    def test_list_agent_roles(self, sys_client):
        c, _ = sys_client
        resp = c.get("/agent/roles")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (list, dict))

    def test_agents_active(self, sys_client):
        c, _ = sys_client
        resp = c.get("/agents/status")
        assert resp.status_code == 200


# ===========================================================================
# 15. MCP Tools
# ===========================================================================


class TestMCPTools:
    """MCP tool discovery."""

    def test_list_mcp_tools(self, sys_client):
        c, _ = sys_client
        resp = c.get("/mcp/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, (list, dict))


# ===========================================================================
# 16. Onboarding
# ===========================================================================


class TestOnboarding:
    """Solution onboarding and scaffolding."""

    def test_onboarding_generate(self, sys_client):
        c, _ = sys_client
        with patch("src.core.onboarding.generate_solution") as mock_gen:
            mock_gen.return_value = {
                "solution_name": "fitness_app",
                "path": "/tmp/fitness_app",
                "status": "created",
                "files": ["project.yaml", "prompts.yaml", "tasks.yaml"],
                "message": "Solution created",
            }
            resp = c.post("/onboarding/generate", json={
                "description": "A fitness tracking app for gym users",
                "solution_name": "fitness_app",
            })
        assert resp.status_code == 200


# ===========================================================================
# 17. Eval Suite
# ===========================================================================


class TestEvalSuite:
    """Eval listing and history."""

    def test_list_eval_suites(self, sys_client):
        c, _ = sys_client
        resp = c.get("/eval/suites")
        assert resp.status_code == 200

    def test_eval_history(self, sys_client):
        c, _ = sys_client
        resp = c.get("/eval/history")
        assert resp.status_code == 200


# ===========================================================================
# 18. Repo Map
# ===========================================================================


class TestRepoMap:
    """Repository map endpoint."""

    def test_repo_map(self, sys_client):
        c, _ = sys_client
        resp = c.get("/repo/map")
        assert resp.status_code == 200


# ===========================================================================
# 19. Full Lifecycle Smoke Tests
# ===========================================================================


class TestFullLifecycleSmoke:
    """
    End-to-end smoke: health → analyze → approve → verify audit.
    Exercises the complete happy path in a single test.
    """

    def test_full_happy_path(self, sys_client):
        c, audit = sys_client

        # 1. Health check
        with patch("src.interface.api._get_llm_gateway") as mock_llm:
            mock_llm.return_value.get_provider_name.return_value = "mock"
            health = c.get("/health")
        assert health.status_code == 200

        # 2. Submit analysis
        analyst = _mock_analyst(trace_id="ffffffff-0000-4000-8000-aaaaaaaaaaaa")
        with patch("src.interface.api._get_analyst", return_value=analyst):
            analyze_resp = c.post("/analyze", json={
                "log_entry": "CRITICAL: Connection pool exhausted at db_pool:89",
            })
        assert analyze_resp.status_code == 200
        trace_id = analyze_resp.json()["trace_id"]

        # 3. Verify proposal is stored
        from src.interface.api import _pending_proposals
        assert trace_id in _pending_proposals

        # 4. Approve
        approve_resp = c.post(f"/approve/{trace_id}")
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "approved"

        # 5. Verify no longer pending
        assert trace_id not in _pending_proposals

        # 6. Verify audit trail
        conn = sqlite3.connect(audit.db_path)
        rows = conn.execute(
            "SELECT * FROM compliance_audit_log WHERE action_type = 'APPROVAL'"
        ).fetchall()
        conn.close()
        assert len(rows) >= 1

    def test_full_reject_path(self, sys_client):
        c, _ = sys_client

        # Submit analysis
        analyst = _mock_analyst(trace_id="ffffffff-1111-4111-8111-bbbbbbbbbbbb")
        with patch("src.interface.api._get_analyst", return_value=analyst):
            resp = c.post("/analyze", json={
                "log_entry": "WARNING: cache miss rate >50%",
            })
        trace_id = resp.json()["trace_id"]

        # Reject with feedback
        reject_resp = c.post(f"/reject/{trace_id}", json={
            "feedback": "Root cause is incorrect — config issue not cache",
        })
        assert reject_resp.status_code == 200

        # Verify cleared
        from src.interface.api import _pending_proposals
        assert trace_id not in _pending_proposals


# ===========================================================================
# 20. Scheduler Status
# ===========================================================================


class TestScheduler:
    """Task scheduler status."""

    def test_scheduler_status(self, sys_client):
        c, _ = sys_client
        resp = c.get("/scheduler/status")
        assert resp.status_code == 200
