import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Add SAGE framework root to sys.path
# tests/ -> medtech/ -> solutions/ -> SystemAutonomousAgent/
# ---------------------------------------------------------------------------
SAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if SAGE_ROOT not in sys.path:
    sys.path.insert(0, SAGE_ROOT)


# ---------------------------------------------------------------------------
# Sample log entries
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_log_entries():
    return [
        "ERROR [uart_driver.c:142] UART1 RX buffer overflow: received 512 bytes, buffer capacity 256",
        "CRITICAL [watchdog.c:88] Watchdog timeout expired — system halted. Last task: SENSOR_POLL",
        "ERROR [flash_controller.c:310] Flash write failed at address 0x08040000: HAL_ERROR status 0x02",
        "WARNING [i2c_bus.c:205] I2C1 bus stuck LOW — attempting recovery sequence (attempt 3/3)",
        "ERROR [rtos_hooks.c:57] Stack overflow detected in task 'CommsHandler' (stack high watermark: 48 bytes)",
    ]


# ---------------------------------------------------------------------------
# Audit logger — isolated SQLite per test
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_audit_db(tmp_path):
    from src.memory.audit_logger import AuditLogger
    db_file = str(tmp_path / "test_audit.db")
    return AuditLogger(db_path=db_file)


# ---------------------------------------------------------------------------
# Vector memory — in-memory fallback only
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_vector_memory():
    with patch("src.memory.vector_store._HAS_CHROMADB", False), \
         patch("src.memory.vector_store.Chroma", None):
        from src.memory.vector_store import VectorMemory
        import logging
        vm = VectorMemory.__new__(VectorMemory)
        vm.logger = logging.getLogger("VectorMemory.test")
        vm._fallback_memory = []
        vm._vector_store = None
        vm._ready = False
        return vm


# ---------------------------------------------------------------------------
# Mock LLM gateway
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_gateway():
    fixed_response = json.dumps({
        "severity": "HIGH",
        "root_cause_hypothesis": "test hypothesis",
        "recommended_action": "test action",
    })
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=fixed_response) as mock_gen:
        yield mock_gen


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    from fastapi.testclient import TestClient
    from src.interface.api import app
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Mock GitLab HTTP responses
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gitlab_responses():
    return {
        "mr": {
            "id": 1001, "iid": 7, "title": "Fix UART buffer overflow",
            "description": "Increases UART1 RX buffer from 256 to 512 bytes.",
            "source_branch": "sage-ai/7-fix-uart", "target_branch": "main",
            "author": {"name": "Jane Dev"},
            "web_url": "https://gitlab.example.com/project/-/merge_requests/7",
            "pipeline": {"id": 555, "status": "passed",
                         "web_url": "https://gitlab.example.com/project/-/pipelines/555"},
            "labels": ["sage-ai"],
        },
        "mr_diffs": [{"old_path": "src/uart_driver.c", "new_path": "src/uart_driver.c",
                      "diff": "@@ -10,7 +10,7 @@\n-#define UART_BUF_SIZE 256\n+#define UART_BUF_SIZE 512\n"}],
        "issue": {"id": 2001, "iid": 45, "title": "UART RX buffer too small",
                  "description": "Device crashes when receiving bursts of >256 bytes on UART1.",
                  "labels": ["bug", "sage-ai"]},
        "project": {"id": 123, "name": "FirmwareProject", "default_branch": "main",
                    "web_url": "https://gitlab.example.com/project"},
        "mr_created": {"id": 3001, "iid": 8, "title": "Fix: UART RX buffer too small",
                       "web_url": "https://gitlab.example.com/project/-/merge_requests/8",
                       "source_branch": "sage-ai/45-uart-rx-buffer-too-small", "target_branch": "main"},
        "pipeline": {"id": 555, "status": "passed", "created_at": "2024-01-15T10:00:00Z",
                     "finished_at": "2024-01-15T10:05:00Z", "duration": 300,
                     "web_url": "https://gitlab.example.com/project/-/pipelines/555"},
        "jobs": [{"name": "build", "stage": "build", "status": "success", "duration": 120, "web_url": ""},
                 {"name": "test", "stage": "test", "status": "success", "duration": 180, "web_url": ""}],
        "note": {"id": 9001, "body": "SAGE[ai] review comment"},
        "projects_list": [{"id": 123, "name": "FirmwareProject", "default_branch": "main"}],
    }


# ---------------------------------------------------------------------------
# Teams mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_teams_requests():
    mock_token_result = {"access_token": "mock-graph-token-xyz", "expires_in": 3600, "token_type": "Bearer"}
    mock_msal_app = MagicMock()
    mock_msal_app.acquire_token_for_client.return_value = mock_token_result
    mock_webhook_response = MagicMock()
    mock_webhook_response.status_code = 200
    mock_webhook_response.raise_for_status = MagicMock()
    mock_graph_response = MagicMock()
    mock_graph_response.status_code = 200
    mock_graph_response.raise_for_status = MagicMock()
    mock_graph_response.json.return_value = {"value": [
        {"id": "msg-001", "createdDateTime": "2024-01-15T10:00:00Z",
         "from": {"user": {"displayName": "Alice Engineer"}},
         "body": {"contentType": "text", "content": "ERROR timeout on device COM3"},
         "importance": "normal", "subject": ""},
    ]}
    with patch("msal.ConfidentialClientApplication", return_value=mock_msal_app) as mock_msal_cls, \
         patch("requests.post", return_value=mock_webhook_response) as mock_post, \
         patch("requests.get", return_value=mock_graph_response) as mock_get:
        yield {"msal_cls": mock_msal_cls, "msal_app": mock_msal_app,
               "post": mock_post, "get": mock_get}
