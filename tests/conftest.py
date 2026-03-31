"""
SAGE[ai] - Shared pytest fixtures for the complete test suite.

Provides reusable fixtures for:
  - Isolated audit logger instances (SQLite in tmp_path)
  - In-memory vector memory (no ChromaDB required)
  - Mocked LLM gateway
  - Mocked external service HTTP responses
  - FastAPI TestClient
  - Mocked serial/JLink/Metabase/Spira/Teams dependencies
  - Sample embedded device log strings
"""

import json
import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Sample log entries used across multiple test files
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_log_entries():
    """Returns 5 realistic embedded device log strings."""
    return [
        "ERROR [uart_driver.c:142] UART1 RX buffer overflow: received 512 bytes, buffer capacity 256",
        "CRITICAL [watchdog.c:88] Watchdog timeout expired — system halted. Last task: SENSOR_POLL",
        "ERROR [flash_controller.c:310] Flash write failed at address 0x08040000: HAL_ERROR status 0x02",
        "WARNING [i2c_bus.c:205] I2C1 bus stuck LOW — attempting recovery sequence (attempt 3/3)",
        "ERROR [rtos_hooks.c:57] Stack overflow detected in task 'CommsHandler' (stack high watermark: 48 bytes)",
    ]


# ---------------------------------------------------------------------------
# Audit logger fixture — fresh isolated SQLite DB per test
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_audit_db(tmp_path):
    """
    Creates a fresh AuditLogger pointed at a temporary SQLite file.
    Each test gets its own isolated DB — no shared state.
    """
    from src.memory.audit_logger import AuditLogger
    db_file = str(tmp_path / "test_audit.db")
    logger = AuditLogger(db_path=db_file)
    return logger


# ---------------------------------------------------------------------------
# Vector memory fixture — in-memory fallback only
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_vector_memory():
    """
    Creates a VectorMemory instance with ChromaDB disabled.
    Uses only the in-memory keyword-search fallback — no ChromaDB needed.
    """
    with patch.dict("sys.modules", {"chromadb": None}):
        # Patch _HAS_CHROMADB and Chroma to force fallback path
        with patch("src.memory.vector_store._HAS_CHROMADB", False), \
             patch("src.memory.vector_store.Chroma", None):
            from src.memory.vector_store import VectorMemory
            vm = VectorMemory.__new__(VectorMemory)
            import logging
            import threading
            vm.logger = logging.getLogger("VectorMemory.test")
            vm._fallback_memory = []
            vm._fallback_lock = threading.Lock()
            vm.vector_store = None
            vm._ready = False
            return vm


# ---------------------------------------------------------------------------
# Mock LLM gateway fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm_gateway():
    """
    Patches llm_gateway.generate() to return a fixed valid JSON analysis string.
    Suitable for testing agents that call the LLM gateway.
    """
    fixed_response = json.dumps({
        "severity": "HIGH",
        "root_cause_hypothesis": "test hypothesis",
        "recommended_action": "test action",
    })
    with patch("src.core.llm_gateway.LLMGateway.generate", return_value=fixed_response) as mock_gen:
        yield mock_gen


# ---------------------------------------------------------------------------
# Mock GitLab HTTP responses
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_gitlab_responses():
    """
    Returns a dict of mock HTTP response data for common GitLab API endpoints.
    Use as the return_value of a patched requests.get / requests.post.
    """
    return {
        "mr": {
            "id": 1001,
            "iid": 7,
            "title": "Fix UART buffer overflow",
            "description": "Increases UART1 RX buffer from 256 to 512 bytes.",
            "source_branch": "sage-ai/7-fix-uart",
            "target_branch": "main",
            "author": {"name": "Jane Dev"},
            "web_url": "https://gitlab.example.com/project/-/merge_requests/7",
            "pipeline": {
                "id": 555,
                "status": "passed",
                "web_url": "https://gitlab.example.com/project/-/pipelines/555",
            },
            "labels": ["sage-ai"],
        },
        "mr_diffs": [
            {
                "old_path": "src/uart_driver.c",
                "new_path": "src/uart_driver.c",
                "diff": "@@ -10,7 +10,7 @@\n-#define UART_BUF_SIZE 256\n+#define UART_BUF_SIZE 512\n",
            }
        ],
        "issue": {
            "id": 2001,
            "iid": 45,
            "title": "UART RX buffer too small",
            "description": "Device crashes when receiving bursts of >256 bytes on UART1.",
            "labels": ["bug", "sage-ai"],
        },
        "project": {
            "id": 123,
            "name": "FirmwareProject",
            "default_branch": "main",
            "web_url": "https://gitlab.example.com/project",
        },
        "mr_created": {
            "id": 3001,
            "iid": 8,
            "title": "Fix: UART RX buffer too small",
            "web_url": "https://gitlab.example.com/project/-/merge_requests/8",
            "source_branch": "sage-ai/45-uart-rx-buffer-too-small",
            "target_branch": "main",
        },
        "pipeline": {
            "id": 555,
            "status": "passed",
            "created_at": "2024-01-15T10:00:00Z",
            "finished_at": "2024-01-15T10:05:00Z",
            "duration": 300,
            "web_url": "https://gitlab.example.com/project/-/pipelines/555",
        },
        "jobs": [
            {"name": "build", "stage": "build", "status": "success", "duration": 120, "web_url": ""},
            {"name": "test", "stage": "test", "status": "success", "duration": 180, "web_url": ""},
        ],
        "note": {
            "id": 9001,
            "body": "SAGE[ai] review comment",
        },
        "projects_list": [
            {"id": 123, "name": "FirmwareProject", "default_branch": "main"},
        ],
    }


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """
    Returns a FastAPI TestClient wrapping the SAGE[ai] API app.
    Agents are NOT mocked here — individual tests should patch as needed.
    """
    from fastapi.testclient import TestClient
    from src.interface.api import app
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Serial port mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_serial_port():
    """
    Mocks serial.Serial and serial.tools.list_ports.comports.
    Returns a dict of the mock objects for assertions.
    """
    mock_port_info = MagicMock()
    mock_port_info.device = "COM3"
    mock_port_info.description = "USB Serial Device"
    mock_port_info.hwid = "USB VID:PID=1234:5678"

    mock_port_info2 = MagicMock()
    mock_port_info2.device = "COM4"
    mock_port_info2.description = "J-Link CDC UART Port"
    mock_port_info2.hwid = "USB VID:PID=1366:1015"

    mock_ser_instance = MagicMock()
    mock_ser_instance.__enter__ = MagicMock(return_value=mock_ser_instance)
    mock_ser_instance.__exit__ = MagicMock(return_value=False)
    mock_ser_instance.read_until.return_value = b"OK\n"
    mock_ser_instance.read.return_value = b"OK"
    mock_ser_instance.in_waiting = 3

    with patch("serial.tools.list_ports.comports", return_value=[mock_port_info, mock_port_info2]) as mock_comports, \
         patch("serial.Serial", return_value=mock_ser_instance) as mock_serial_cls:
        yield {
            "comports": mock_comports,
            "Serial": mock_serial_cls,
            "serial_instance": mock_ser_instance,
            "port_infos": [mock_port_info, mock_port_info2],
        }


# ---------------------------------------------------------------------------
# J-Link mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_jlink():
    """
    Mocks pylink.JLink for hardware-free J-Link tests.
    Returns a dict with the mock JLink class and instance.
    """
    mock_jlink_instance = MagicMock()
    mock_jlink_instance.serial_number = 123456789
    mock_jlink_instance.hardware_version = "V10.10"
    mock_jlink_instance.firmware_version = "J-Link V10.10 compiled Mar  1 2024"
    mock_jlink_instance.product_name = "J-Link PLUS"
    mock_jlink_instance.connected.return_value = True
    mock_jlink_instance.target_connected.return_value = True
    mock_jlink_instance.memory_read.return_value = [0xDE, 0xAD, 0xBE, 0xEF]
    mock_jlink_instance.register_list.return_value = ["R0", "R1", "PC", "SP"]
    mock_jlink_instance.register_read.return_value = 0x12345678
    mock_jlink_instance.rtt_read.return_value = [ord(c) for c in "RTT output line\n"]

    with patch("pylink.JLink", return_value=mock_jlink_instance) as mock_jlink_cls:
        yield {
            "JLink": mock_jlink_cls,
            "instance": mock_jlink_instance,
        }


# ---------------------------------------------------------------------------
# Metabase session mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_metabase_session():
    """
    Mocks requests.post (Metabase auth) and requests.get (dashboard/card queries).
    """
    mock_auth_response = MagicMock()
    mock_auth_response.status_code = 200
    mock_auth_response.raise_for_status = MagicMock()
    mock_auth_response.json.return_value = {"id": "mock-session-token-abc123"}

    mock_data_response = MagicMock()
    mock_data_response.status_code = 200
    mock_data_response.raise_for_status = MagicMock()
    mock_data_response.json.return_value = [
        {"error_code": "E001", "message": "Sensor timeout", "timestamp": "2024-01-15T10:00:00Z"},
        {"error_code": "E002", "message": "Flash write error", "timestamp": "2024-01-15T09:30:00Z"},
    ]

    with patch("requests.post", return_value=mock_auth_response) as mock_post, \
         patch("requests.get", return_value=mock_data_response) as mock_get:
        yield {
            "post": mock_post,
            "get": mock_get,
            "auth_response": mock_auth_response,
            "data_response": mock_data_response,
        }


# ---------------------------------------------------------------------------
# Spira requests mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_spira_requests():
    """
    Mocks requests.get and requests.post for Spira API calls.
    """
    mock_get_response = MagicMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status = MagicMock()
    mock_get_response.json.return_value = [
        {
            "IncidentId": 101,
            "Name": "UART buffer overflow",
            "Description": "Buffer overflow detected at 0x20001000",
            "IncidentStatusId": 1,
            "IncidentStatusName": "New",
            "IncidentTypeId": 1,
            "IncidentTypeName": "Bug",
            "PriorityId": 2,
            "PriorityName": "High",
            "SeverityId": 2,
            "SeverityName": "High",
            "OpenerName": "Jane Dev",
            "CreationDate": "2024-01-15T08:00:00",
        }
    ]

    mock_post_response = MagicMock()
    mock_post_response.status_code = 201
    mock_post_response.raise_for_status = MagicMock()
    mock_post_response.json.return_value = {
        "IncidentId": 999,
        "Name": "New test incident",
        "Description": "Created by SAGE[ai]",
        "IncidentStatusId": 1,
        "IncidentStatusName": "New",
        "IncidentTypeId": 1,
        "IncidentTypeName": "Bug",
        "PriorityId": 2,
        "PriorityName": "High",
        "SeverityId": 2,
        "SeverityName": "High",
        "OpenerName": "AI Agent",
        "CreationDate": "2024-01-15T10:00:00",
    }

    with patch("requests.get", return_value=mock_get_response) as mock_get, \
         patch("requests.post", return_value=mock_post_response) as mock_post:
        yield {
            "get": mock_get,
            "post": mock_post,
            "get_response": mock_get_response,
            "post_response": mock_post_response,
        }


# ---------------------------------------------------------------------------
# Teams requests mock fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_teams_requests():
    """
    Mocks requests.post (Teams webhook) and requests.get (Graph API).
    Also mocks msal.ConfidentialClientApplication.
    """
    mock_token_result = {
        "access_token": "mock-graph-token-xyz",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    mock_msal_app = MagicMock()
    mock_msal_app.acquire_token_for_client.return_value = mock_token_result

    mock_webhook_response = MagicMock()
    mock_webhook_response.status_code = 200
    mock_webhook_response.raise_for_status = MagicMock()

    mock_graph_response = MagicMock()
    mock_graph_response.status_code = 200
    mock_graph_response.raise_for_status = MagicMock()
    mock_graph_response.json.return_value = {
        "value": [
            {
                "id": "msg-001",
                "createdDateTime": "2024-01-15T10:00:00Z",
                "from": {"user": {"displayName": "Alice Engineer"}},
                "body": {"contentType": "text", "content": "ERROR timeout on device COM3"},
                "importance": "normal",
                "subject": "",
            },
            {
                "id": "msg-002",
                "createdDateTime": "2024-01-15T10:01:00Z",
                "from": {"user": {"displayName": "Bob Dev"}},
                "body": {"contentType": "text", "content": "Firmware update completed successfully"},
                "importance": "normal",
                "subject": "",
            },
            {
                "id": "msg-003",
                "createdDateTime": "2024-01-15T10:02:00Z",
                "from": {"user": {"displayName": "System Monitor"}},
                "body": {"contentType": "text", "content": "CRITICAL sensor fault detected on line 4"},
                "importance": "urgent",
                "subject": "",
            },
        ]
    }

    with patch("msal.ConfidentialClientApplication", return_value=mock_msal_app) as mock_msal_cls, \
         patch("requests.post", return_value=mock_webhook_response) as mock_post, \
         patch("requests.get", return_value=mock_graph_response) as mock_get:
        yield {
            "msal_cls": mock_msal_cls,
            "msal_app": mock_msal_app,
            "post": mock_post,
            "get": mock_get,
            "webhook_response": mock_webhook_response,
            "graph_response": mock_graph_response,
        }
