from fastapi.testclient import TestClient


def test_undo_unknown_trace_returns_404():
    from src.interface.api import app
    client = TestClient(app)
    resp = client.post("/proposals/nonexistent-trace/undo")
    assert resp.status_code == 404


def test_undo_pending_proposal_returns_409():
    """Can't undo a proposal that hasn't been approved yet."""
    from src.interface.api import app
    from src.core.proposal_store import RiskClass
    client = TestClient(app)

    from src.interface.api import _get_proposal_store
    store = _get_proposal_store()
    # Use store.create() — the real API (no store.add())
    p = store.create(
        action_type="analysis",
        risk_class=RiskClass.EPHEMERAL,
        payload={},
        description="test pending proposal",
        reversible=True,
    )
    resp = client.post(f"/proposals/{p.trace_id}/undo")
    assert resp.status_code == 409


def test_undo_endpoint_exists():
    from src.interface.api import app
    routes = [r.path for r in app.routes]
    assert "/proposals/{trace_id}/undo" in routes
