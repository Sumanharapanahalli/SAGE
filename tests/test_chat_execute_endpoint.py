# tests/test_chat_execute_endpoint.py
from fastapi.testclient import TestClient


def test_execute_unknown_action_returns_400():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/chat/execute", json={
        "action": "nonexistent_action", "params": {},
        "user_id": "u1", "session_id": "s1", "solution": "test"
    })
    assert resp.status_code == 400


def test_execute_approve_unknown_trace_returns_404():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/chat/execute", json={
        "action": "approve_proposal",
        "params": {"trace_id": "does-not-exist"},
        "user_id": "u1", "session_id": "s1", "solution": "test"
    })
    assert resp.status_code == 404


def test_execute_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/chat/execute" in routes


def test_chat_response_has_response_type():
    """Enhanced /chat always returns response_type field."""
    from src.interface.api import app
    from unittest.mock import patch
    client = TestClient(app)
    mock_result = {"type": "answer", "reply": "Hello"}
    with patch("src.core.chat_router.route", return_value=mock_result):
        resp = client.post("/chat", json={"message": "hi", "user_id": "u1"})
    assert resp.status_code == 200
    assert "response_type" in resp.json()


def test_chat_query_knowledge_returns_answer_type():
    """query_knowledge action is resolved inline — returns response_type 'answer'."""
    from src.interface.api import app
    from unittest.mock import patch
    client = TestClient(app)
    mock_result = {"type": "action", "action": "query_knowledge",
                   "params": {"query": "what is SAGE?"}, "confirmation_prompt": ""}
    with patch("src.core.chat_router.route", return_value=mock_result):
        with patch("src.memory.vector_store.vector_memory.search", return_value=[{"content": "SAGE is a framework."}]):
            resp = client.post("/chat", json={"message": "what is SAGE?", "user_id": "u1"})
    data = resp.json()
    assert data.get("response_type") == "answer"


def test_execute_writes_message_type_to_chat_store():
    """chat/execute writes action_confirmed and action_executed message_type entries."""
    from src.interface.api import app
    from unittest.mock import patch, MagicMock
    client = TestClient(app)

    # Mock audit_logger.save_chat_message to capture calls
    saved_types = []
    original_save = None

    def capture_save(*args, **kwargs):
        mt = kwargs.get("message_type")
        if mt:
            saved_types.append(mt)
        return "test-msg-id"

    mock_proposal = MagicMock()
    mock_proposal.action_type = "yaml_edit"
    mock_store = MagicMock()
    mock_store.get.return_value = mock_proposal

    with patch("src.memory.audit_logger.audit_logger.save_chat_message", side_effect=capture_save):
        with patch("src.core.proposal_store.ProposalStore.get", return_value=mock_proposal):
            with patch("src.core.proposal_store.ProposalStore.approve"):
                with patch("src.core.proposal_executor.execute_approved_proposal"):
                    with patch("asyncio.ensure_future"):
                        # Use an action that won't 404 — patch the store getter
                        with patch("src.interface.api._get_proposal_store", return_value=mock_store):
                            with patch("src.memory.audit_logger.audit_logger.log_event"):
                                resp = client.post("/chat/execute", json={
                                    "action": "approve_proposal",
                                    "params": {"trace_id": "test-trace"},
                                    "user_id": "u1", "session_id": "s1", "solution": "test"
                                })
    assert resp.status_code == 200
    assert "action_confirmed" in saved_types
    assert "action_executed" in saved_types
