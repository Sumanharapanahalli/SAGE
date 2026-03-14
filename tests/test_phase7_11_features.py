"""
SAGE Framework — Phases 7–11 Feature Tests
==========================================
Tests for:
  Phase 7 — Knowledge base CRUD
  Phase 8 — Slack two-way approval
  Phase 9 — Evaluation & benchmarking
  Phase 10 — Multi-tenant isolation
  Phase 11 — Temporal durable workflows
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def _client():
    from src.interface.api import app
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Phase 7 — Knowledge Base CRUD
# ===========================================================================

class TestKnowledgeCRUD:

    def _fresh_vm(self):
        from src.memory.vector_store import VectorMemory
        vm = VectorMemory.__new__(VectorMemory)
        vm._embedding_function = None
        vm._vector_store = None
        vm._llamaindex_index = None
        vm._fallback_memory = []
        vm._ready = False
        vm._mode = "minimal"
        return vm

    def test_add_entry_returns_id(self):
        """add_entry() must return a non-empty string ID."""
        vm = self._fresh_vm()
        entry_id = vm.add_entry("Domain knowledge about firmware updates")
        assert isinstance(entry_id, str)
        assert len(entry_id) > 0

    def test_add_entry_stored_in_fallback(self):
        """add_entry() must append to the fallback memory list."""
        vm = self._fresh_vm()
        vm.add_entry("Test knowledge entry")
        assert len(vm._fallback_memory) == 1
        assert "Test knowledge entry" in vm._fallback_memory

    def test_list_entries_returns_list(self):
        """list_entries() must return a list of dicts."""
        vm = self._fresh_vm()
        vm.add_entry("Entry one")
        vm.add_entry("Entry two")
        entries = vm.list_entries(limit=10)
        assert isinstance(entries, list)
        assert len(entries) == 2

    def test_list_entries_respects_limit(self):
        """list_entries() must not return more than `limit` entries."""
        vm = self._fresh_vm()
        for i in range(10):
            vm.add_entry(f"Entry {i}")
        entries = vm.list_entries(limit=3)
        assert len(entries) <= 3

    def test_list_entries_has_id_and_text(self):
        """Each entry dict must have 'id' and 'text' keys."""
        vm = self._fresh_vm()
        vm.add_entry("Check for id and text")
        entries = vm.list_entries()
        assert "id" in entries[0]
        assert "text" in entries[0]

    def test_delete_entry_fallback_mode(self):
        """delete_entry() in fallback mode removes by positional index."""
        vm = self._fresh_vm()
        vm.add_entry("Keep this")
        vm.add_entry("Delete this")
        deleted = vm.delete_entry("1")   # index 1
        assert deleted is True
        assert len(vm._fallback_memory) == 1
        assert "Keep this" in vm._fallback_memory

    def test_delete_entry_unknown_id_returns_false(self):
        """delete_entry() with non-existent ID must return False."""
        vm = self._fresh_vm()
        result = vm.delete_entry("nonexistent_id_xyz")
        assert result is False

    def test_bulk_import_adds_entries(self):
        """bulk_import() must add all valid entries and return count."""
        vm = self._fresh_vm()
        entries = [
            {"text": "Entry A", "metadata": {"source": "manual"}},
            {"text": "Entry B"},
            {"text": ""},   # should be skipped (empty text)
        ]
        count = vm.bulk_import(entries)
        assert count == 2
        assert len(vm._fallback_memory) == 2

    # API tests

    def test_knowledge_add_returns_200(self):
        # knowledge_add now returns a STATEFUL proposal (HITL gate)
        resp = _client().post("/knowledge/add", json={"text": "Some domain knowledge"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_approval"
        assert "trace_id" in data

    def test_knowledge_add_missing_text_returns_400(self):
        resp = _client().post("/knowledge/add", json={})
        assert resp.status_code == 400

    def test_knowledge_list_returns_200(self):
        from src.memory import vector_store as vs_module
        mock_vm = MagicMock()
        mock_vm.list_entries.return_value = [{"id": "1", "text": "foo", "metadata": {}}]
        with patch.object(vs_module, "vector_memory", mock_vm):
            resp = _client().get("/knowledge/entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert len(data["entries"]) == 1

    def test_knowledge_delete_returns_200(self):
        # knowledge_delete now returns a DESTRUCTIVE proposal (HITL gate)
        from src.memory import vector_store as vs_module
        mock_vm = MagicMock()
        mock_vm.list_entries.return_value = [{"id": "entry_123", "text": "Some knowledge", "metadata": {}}]
        with patch.object(vs_module, "vector_memory", mock_vm):
            resp = _client().delete("/knowledge/entry/entry_123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_approval"
        assert "trace_id" in data

    def test_knowledge_delete_unknown_returns_404(self):
        from src.memory import vector_store as vs_module
        mock_vm = MagicMock()
        mock_vm.list_entries.return_value = []
        with patch.object(vs_module, "vector_memory", mock_vm):
            resp = _client().delete("/knowledge/entry/bad_id")
        assert resp.status_code == 404

    def test_knowledge_import_returns_200(self):
        # knowledge_import now returns a STATEFUL proposal (HITL gate)
        resp = _client().post("/knowledge/import", json={
            "entries": [
                {"text": "A"}, {"text": "B"}, {"text": "C"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending_approval"
        assert data["count"] == 3

    def test_knowledge_import_empty_returns_400(self):
        resp = _client().post("/knowledge/import", json={"entries": []})
        assert resp.status_code == 400

    def test_knowledge_search_returns_200(self):
        from src.memory import vector_store as vs_module
        mock_vm = MagicMock()
        mock_vm.search.return_value = ["result one", "result two"]
        with patch.object(vs_module, "vector_memory", mock_vm):
            resp = _client().post("/knowledge/search", json={"query": "firmware error"})
        assert resp.status_code == 200
        assert resp.json()["count"] == 2

    def test_knowledge_search_missing_query_returns_400(self):
        resp = _client().post("/knowledge/search", json={})
        assert resp.status_code == 400


# ===========================================================================
# Phase 8 — Slack Two-Way Approval
# ===========================================================================

class TestSlackApprover:

    def test_send_proposal_skips_when_no_token(self):
        """send_proposal() must return status=skipped when SLACK_BOT_TOKEN unset."""
        from src.integrations import slack_approver as sa
        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "SLACK_BOT_TOKEN"}
            with patch.dict(os.environ, env, clear=True):
                import importlib
                importlib.reload(sa)
                result = sa.send_proposal({
                    "trace_id": "t1",
                    "summary":  "Propose upgrade",
                    "action_type": "UPGRADE",
                    "actor": "analyst",
                })
        assert result["status"] == "skipped"

    def test_verify_signature_no_secret_returns_true(self):
        """verify_slack_signature() must return True when no secret configured."""
        from src.integrations.slack_approver import verify_slack_signature
        with patch.dict(os.environ, {}, clear=False):
            env = {k: v for k, v in os.environ.items() if k != "SLACK_SIGNING_SECRET"}
            with patch.dict(os.environ, env, clear=True):
                result = verify_slack_signature(b"body", "12345", "v0=abc")
        assert result is True

    def test_verify_signature_stale_timestamp_returns_false(self):
        """verify_slack_signature() must reject timestamps older than 5 minutes."""
        import time
        from src.integrations.slack_approver import verify_slack_signature
        old_ts = str(int(time.time()) - 400)
        with patch.dict(os.environ, {"SLACK_SIGNING_SECRET": "test_secret"}):
            result = verify_slack_signature(b"body", old_ts, "v0=anything")
        assert result is False

    def test_parse_action_payload_approved(self):
        """parse_action_payload() must extract trace_id and approved decision."""
        from src.integrations.slack_approver import parse_action_payload
        payload = {
            "actions": [{
                "action_id": "approve",
                "value": json.dumps({"trace_id": "tr_001", "decision": "approved"}),
            }],
            "user": {"username": "alice"},
            "action_ts": "1234567890.123456",
        }
        result = parse_action_payload(json.dumps(payload))
        assert result["trace_id"] == "tr_001"
        assert result["decision"] == "approved"
        assert result["user"] == "alice"

    def test_parse_action_payload_rejected(self):
        """parse_action_payload() must extract rejected decision."""
        from src.integrations.slack_approver import parse_action_payload
        payload = {
            "actions": [{
                "value": json.dumps({"trace_id": "tr_002", "decision": "rejected"}),
            }],
            "user": {"username": "bob"},
        }
        result = parse_action_payload(json.dumps(payload))
        assert result["decision"] == "rejected"

    def test_slack_send_proposal_missing_fields_returns_400(self):
        resp = _client().post("/slack/send-proposal", json={"trace_id": "t1"})
        assert resp.status_code == 400

    def test_slack_webhook_invalid_signature_returns_401(self):
        """POST /webhook/slack with bad signature must return 401."""
        import time
        with patch.dict(os.environ, {"SLACK_SIGNING_SECRET": "secret"}):
            resp = _client().post(
                "/webhook/slack",
                content=b"payload=%7B%7D",
                headers={
                    "X-Slack-Request-Timestamp": str(int(time.time())),
                    "X-Slack-Signature": "v0=badsig",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        assert resp.status_code == 401


# ===========================================================================
# Phase 9 — Evaluation & Benchmarking
# ===========================================================================

class TestEvalRunner:

    def _fresh_runner(self, tmpdir=None):
        from src.core.eval_runner import EvalRunner
        db = os.path.join(tmpdir, "eval.db") if tmpdir else ":memory:"
        runner = EvalRunner(db_path=db)
        return runner

    def test_list_suites_empty_when_no_dir(self):
        """list_suites() must return [] when no evals/ dir exists."""
        import src.core.eval_runner as er_module
        runner = self._fresh_runner()
        with patch("src.core.eval_runner._get_evals_dir", return_value="/nonexistent"):
            suites = runner.list_suites()
        assert suites == []

    def test_list_suites_finds_yaml_files(self):
        """list_suites() must find .yaml files in the evals/ directory."""
        import src.core.eval_runner as er_module
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "analyst_eval.yaml"), "w").close()
            open(os.path.join(tmpdir, "monitor_eval.yaml"), "w").close()
            open(os.path.join(tmpdir, "_skip.yaml"), "w").close()
            with patch("src.core.eval_runner._get_evals_dir", return_value=tmpdir):
                runner = self._fresh_runner(tmpdir)
                suites = runner.list_suites()
        assert "analyst_eval" in suites
        assert "monitor_eval" in suites
        assert "_skip" not in suites

    def test_score_case_full_keywords_gets_70(self):
        """Case where all keywords found must get at least 70 pts."""
        from src.core.eval_runner import _score_case
        case = {"expected_keywords": ["null", "pointer"]}
        result = _score_case("NullPointerException: null pointer dereferenced", case)
        assert result["score"] >= 70
        assert result["passed"] is True

    def test_score_case_no_keywords_gets_zero_keyword_score(self):
        """Case where no keywords found must get 0 keyword score."""
        from src.core.eval_runner import _score_case
        case = {"expected_keywords": ["missing", "word"]}
        result = _score_case("Unrelated response without expected terms", case)
        assert result["details"]["keyword_score"] == 0

    def test_score_case_length_compliance_adds_30(self):
        """Response within max_response_length gets full length score."""
        from src.core.eval_runner import _score_case
        case = {"max_response_length": 500}
        result = _score_case("Short response", case)
        assert result["details"]["length_score"] == 30

    def test_run_returns_error_when_no_suites(self):
        """run() must return an error dict when no eval suites found."""
        runner = self._fresh_runner()
        with patch("src.core.eval_runner._get_evals_dir", return_value="/nonexistent"):
            result = runner.run()
        assert "error" in result

    def test_run_executes_cases(self):
        """run() with a valid suite must return per-case results."""
        suite_yaml = """
name: Test Suite
cases:
  - id: case_1
    role: analyst
    input: "Check this log error"
    expected_keywords: ["error"]
"""
        from src.core import llm_gateway as gw_module
        mock_gw = MagicMock()
        mock_gw.generate.return_value = "This is an error in the system logs"

        with tempfile.TemporaryDirectory() as tmpdir:
            suite_path = os.path.join(tmpdir, "test_suite.yaml")
            with open(suite_path, "w") as f:
                f.write(suite_yaml)
            runner = self._fresh_runner(tmpdir)
            with patch("src.core.eval_runner._get_evals_dir", return_value=tmpdir), \
                 patch.object(gw_module, "llm_gateway", mock_gw):
                result = runner.run(suite="test_suite")

        assert result["total_cases"] == 1
        assert "run_id" in result

    def test_get_history_returns_list(self):
        """get_history() must return a list (empty when no runs yet)."""
        runner = self._fresh_runner()
        history = runner.get_history()
        assert isinstance(history, list)

    # API tests

    def test_eval_suites_returns_200(self):
        from src.core import eval_runner as er_module
        mock_runner = MagicMock()
        mock_runner.list_suites.return_value = ["analyst_eval", "monitor_eval"]
        with patch.object(er_module, "eval_runner", mock_runner):
            resp = _client().get("/eval/suites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    def test_eval_run_returns_200(self):
        from src.core import eval_runner as er_module
        mock_runner = MagicMock()
        mock_runner.run.return_value = {
            "run_id": "r1", "suite": "test_suite",
            "total_cases": 3, "passed_cases": 2,
            "failed_cases": 1, "mean_score": 75.0, "results": [],
        }
        with patch.object(er_module, "eval_runner", mock_runner):
            resp = _client().post("/eval/run", json={"suite": "test_suite"})
        assert resp.status_code == 200
        assert resp.json()["mean_score"] == 75.0

    def test_eval_history_returns_200(self):
        from src.core import eval_runner as er_module
        mock_runner = MagicMock()
        mock_runner.get_history.return_value = []
        with patch.object(er_module, "eval_runner", mock_runner):
            resp = _client().get("/eval/history")
        assert resp.status_code == 200
        assert "history" in resp.json()


# ===========================================================================
# Phase 10 — Multi-Tenant Isolation
# ===========================================================================

class TestMultiTenant:

    def test_get_current_tenant_fallback_to_solution(self):
        """get_current_tenant() must return active solution name when no header."""
        from src.core.tenant import get_current_tenant, _current_tenant
        _current_tenant.set("")  # reset
        tenant = get_current_tenant()
        assert isinstance(tenant, str)
        assert len(tenant) > 0

    def test_set_tenant_overrides_context(self):
        """set_tenant() must change the returned value."""
        from src.core.tenant import set_tenant, get_current_tenant
        set_tenant("team_alpha")
        assert get_current_tenant() == "team_alpha"
        # cleanup
        set_tenant("")

    def test_tenant_scoped_collection(self):
        """tenant_scoped_collection() must prefix the collection with tenant name."""
        from src.core.tenant import tenant_scoped_collection, set_tenant
        set_tenant("robotics")
        collection = tenant_scoped_collection()
        assert collection.startswith("robotics")
        set_tenant("")

    def test_tenant_context_endpoint_no_header(self):
        """GET /tenant/context without header returns default tenant."""
        resp = _client().get("/tenant/context")
        assert resp.status_code == 200
        data = resp.json()
        assert "tenant_id" in data
        assert "collection" in data
        assert data["header_set"] is False

    def test_tenant_context_endpoint_with_header(self):
        """GET /tenant/context with X-SAGE-Tenant header returns that tenant."""
        resp = _client().get(
            "/tenant/context",
            headers={"X-SAGE-Tenant": "team_beta"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] == "team_beta"
        assert data["header_set"] is True

    def test_tenant_middleware_sets_context(self):
        """Requests with X-SAGE-Tenant must be reflected in /tenant/context."""
        resp = _client().get(
            "/tenant/context",
            headers={"X-SAGE-Tenant": "fintech"},
        )
        assert resp.json()["tenant_id"] == "fintech"


# ===========================================================================
# Phase 11 — Temporal Durable Workflows
# ===========================================================================

class TestTemporalRunner:

    def _fresh_runner(self):
        from src.integrations.temporal_runner import TemporalRunner
        return TemporalRunner()

    def test_start_falls_back_when_no_temporal(self):
        """start() must fall back gracefully when temporalio is not installed."""
        runner = self._fresh_runner()
        with patch("src.integrations.temporal_runner._HAS_TEMPORAL", False):
            result = runner.start("some_workflow", {"task": "test"})
        # Should not raise; returns fallback result
        assert "workflow_id" in result
        assert result.get("fallback") is True

    def test_start_stores_run_metadata(self):
        """start() must store run metadata in _runs regardless of fallback."""
        runner = self._fresh_runner()
        with patch("src.integrations.temporal_runner._HAS_TEMPORAL", False):
            result = runner.start("test_wf", {})
        assert result["workflow_id"] in runner._runs

    def test_get_status_known_run(self):
        """get_status() must return correct dict for a known workflow_id."""
        runner = self._fresh_runner()
        with patch("src.integrations.temporal_runner._HAS_TEMPORAL", False):
            start = runner.start("wf", {"x": 1})
        status = runner.get_status(start["workflow_id"])
        assert status["workflow_id"] == start["workflow_id"]
        assert "status" in status

    def test_get_status_unknown_run_returns_error(self):
        """get_status() for unknown workflow_id must return error dict."""
        runner = self._fresh_runner()
        result = runner.get_status("nonexistent_workflow_id")
        assert "error" in result

    def test_list_runs_returns_list(self):
        """list_runs() must return a list."""
        runner = self._fresh_runner()
        assert isinstance(runner.list_runs(), list)

    # API tests

    def test_temporal_start_returns_200(self):
        import src.integrations.temporal_runner as tr_module
        mock_runner = MagicMock()
        mock_runner.start.return_value = {
            "workflow_id": "wf-1",
            "workflow_name": "deploy_wf",
            "status": "fallback",
            "fallback": True,
        }
        with patch.object(tr_module, "temporal_runner", mock_runner):
            resp = _client().post("/temporal/workflow/start", json={
                "workflow_name": "deploy_wf",
                "args": {"version": "1.2.3"},
            })
        assert resp.status_code == 200

    def test_temporal_start_missing_name_returns_400(self):
        resp = _client().post("/temporal/workflow/start", json={"args": {}})
        assert resp.status_code == 400

    def test_temporal_status_known_returns_200(self):
        import src.integrations.temporal_runner as tr_module
        mock_runner = MagicMock()
        mock_runner.get_status.return_value = {
            "workflow_id": "wf-1",
            "workflow_name": "deploy_wf",
            "status": "running",
            "fallback": False,
        }
        with patch.object(tr_module, "temporal_runner", mock_runner):
            resp = _client().get("/temporal/workflow/status/wf-1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_temporal_status_unknown_returns_404(self):
        import src.integrations.temporal_runner as tr_module
        mock_runner = MagicMock()
        mock_runner.get_status.return_value = {"error": "not found", "workflow_id": "x"}
        with patch.object(tr_module, "temporal_runner", mock_runner):
            resp = _client().get("/temporal/workflow/status/x")
        assert resp.status_code == 404

    def test_temporal_list_returns_200(self):
        import src.integrations.temporal_runner as tr_module
        mock_runner = MagicMock()
        mock_runner.list_runs.return_value = []
        with patch.object(tr_module, "temporal_runner", mock_runner):
            resp = _client().get("/temporal/workflow/list")
        assert resp.status_code == 200
        assert "runs" in resp.json()
