"""
SAGE[ai] - Unit tests for Serial Port MCP Server (mcp_servers/serial_port_server.py)

All serial hardware is mocked. Tests verify tool behavior, error handling,
persistent connection management, and graceful degradation.
"""

from unittest.mock import MagicMock, patch, call

import pytest


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: fresh module state for each test (reset _persistent_connections)
# ---------------------------------------------------------------------------

def _reset_connections():
    """Clear the module-level persistent connections store."""
    import mcp_servers.serial_port_server as srv
    srv._persistent_connections.clear()


# ---------------------------------------------------------------------------
# list_serial_ports
# ---------------------------------------------------------------------------


def test_list_serial_ports_returns_ports(mock_serial_port):
    """list_serial_ports() with 2 mocked ports must return count=2 with device/description/hwid."""
    import mcp_servers.serial_port_server as srv
    with patch.object(srv, "SERIAL_AVAILABLE", True):
        result = srv.list_serial_ports()
    assert result.get("count") == 2, f"Expected count=2, got {result.get('count')}"
    assert "ports" in result, "Result must contain 'ports' key."
    ports = result["ports"]
    assert len(ports) == 2
    for port in ports:
        assert "device" in port
        assert "description" in port
        assert "hwid" in port


def test_list_serial_ports_no_serial_installed():
    """When SERIAL_AVAILABLE=False, list_serial_ports() must return an error dict."""
    import mcp_servers.serial_port_server as srv
    with patch.object(srv, "SERIAL_AVAILABLE", False):
        result = srv.list_serial_ports()
    assert "error" in result, "Expected 'error' key when pyserial not available."


def test_list_serial_ports_empty():
    """When comports() returns empty list, count must be 0."""
    import mcp_servers.serial_port_server as srv
    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.tools.list_ports.comports", return_value=[]):
        result = srv.list_serial_ports()
    assert result.get("count") == 0
    assert result.get("ports") == []


# ---------------------------------------------------------------------------
# send_serial_command
# ---------------------------------------------------------------------------


def test_send_command_sends_and_reads(mock_serial_port):
    """send_serial_command() must send the command and return response in result."""
    import mcp_servers.serial_port_server as srv
    mock_serial_port["serial_instance"].read_until.return_value = b"OK: command processed\n"

    with patch.object(srv, "SERIAL_AVAILABLE", True):
        result = srv.send_serial_command(
            port="COM3", baud_rate=115200, command="STATUS", timeout=1.0
        )
    assert "response" in result, f"Expected 'response' in result: {result}"
    assert "error" not in result, f"Unexpected error: {result.get('error')}"


def test_send_command_serial_exception(mock_serial_port):
    """When Serial raises SerialException, send_serial_command() must return error dict."""
    import serial
    import mcp_servers.serial_port_server as srv
    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", side_effect=serial.SerialException("Port not found")):
        result = srv.send_serial_command(port="COM99", baud_rate=115200, command="TEST")
    assert "error" in result, "Expected 'error' key on SerialException."


def test_send_command_includes_port_in_result(mock_serial_port):
    """send_serial_command() result must include the port that was used."""
    import mcp_servers.serial_port_server as srv
    with patch.object(srv, "SERIAL_AVAILABLE", True):
        result = srv.send_serial_command(port="COM3", baud_rate=115200, command="PING")
    assert result.get("port") == "COM3", f"Expected port='COM3' in result, got '{result.get('port')}'."


# ---------------------------------------------------------------------------
# read_serial_output
# ---------------------------------------------------------------------------


def test_read_serial_output_captures_output():
    """read_serial_output() must return non-empty output when serial has data."""
    import mcp_servers.serial_port_server as srv

    mock_ser = MagicMock()
    mock_ser.__enter__ = MagicMock(return_value=mock_ser)
    mock_ser.__exit__ = MagicMock(return_value=False)
    # Return data on first call, then 0 waiting
    mock_ser.in_waiting = 20
    mock_ser.read.return_value = b"boot complete\nready\n"

    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", return_value=mock_ser), \
         patch("time.time", side_effect=[0.0, 0.0, 4.0]):  # start, loop, deadline
        result = srv.read_serial_output(port="COM3", baud_rate=115200, duration_seconds=3.0)

    assert "output" in result, "Expected 'output' in result."


def test_read_serial_output_returns_lines():
    """read_serial_output() must split output into lines correctly."""
    import mcp_servers.serial_port_server as srv

    mock_ser = MagicMock()
    mock_ser.__enter__ = MagicMock(return_value=mock_ser)
    mock_ser.__exit__ = MagicMock(return_value=False)
    mock_ser.in_waiting = 30
    mock_ser.read.return_value = b"line1\nline2\nline3\n"

    call_count = {"n": 0}
    def time_side_effect():
        call_count["n"] += 1
        return 0.0 if call_count["n"] <= 2 else 5.0

    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", return_value=mock_ser), \
         patch("time.time", side_effect=time_side_effect):
        result = srv.read_serial_output(port="COM3", baud_rate=115200, duration_seconds=3.0)

    lines = result.get("lines", [])
    assert len(lines) == 3, f"Expected 3 lines, got {len(lines)}: {lines}"


# ---------------------------------------------------------------------------
# open_persistent_connection
# ---------------------------------------------------------------------------


def test_open_persistent_connection_returns_id():
    """open_persistent_connection() must return connection_id as an 8-char string."""
    _reset_connections()
    import mcp_servers.serial_port_server as srv

    mock_ser = MagicMock()
    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", return_value=mock_ser):
        result = srv.open_persistent_connection(port="COM3", baud_rate=115200)
    _reset_connections()

    assert "connection_id" in result, f"Expected 'connection_id' in result: {result}"
    conn_id = result["connection_id"]
    assert len(conn_id) == 8, f"Expected 8-char connection_id, got '{conn_id}' (len={len(conn_id)})."


def test_open_persistent_connection_stores_connection():
    """After open_persistent_connection(), the connection_id must be in _persistent_connections."""
    _reset_connections()
    import mcp_servers.serial_port_server as srv

    mock_ser = MagicMock()
    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", return_value=mock_ser):
        result = srv.open_persistent_connection(port="COM3", baud_rate=115200)
    conn_id = result.get("connection_id")
    assert conn_id in srv._persistent_connections, (
        f"Connection {conn_id} must be stored in _persistent_connections."
    )
    _reset_connections()


# ---------------------------------------------------------------------------
# close_connection
# ---------------------------------------------------------------------------


def test_close_connection_removes_from_store():
    """After close_connection(), the connection_id must no longer be in _persistent_connections."""
    _reset_connections()
    import mcp_servers.serial_port_server as srv

    mock_ser = MagicMock()
    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", return_value=mock_ser):
        open_result = srv.open_persistent_connection(port="COM3", baud_rate=115200)
    conn_id = open_result.get("connection_id")
    assert conn_id in srv._persistent_connections

    close_result = srv.close_connection(conn_id)
    assert close_result.get("status") == "closed", f"Expected status='closed': {close_result}"
    assert conn_id not in srv._persistent_connections, (
        f"Connection {conn_id} must be removed from _persistent_connections after close."
    )


def test_close_connection_invalid_id():
    """Calling close_connection() with unknown ID must return error dict with known_ids list."""
    _reset_connections()
    import mcp_servers.serial_port_server as srv

    result = srv.close_connection("nonexist")
    assert "error" in result, "Expected 'error' key for unknown connection ID."
    assert "known_ids" in result, "Error dict must include 'known_ids' list."


def test_multiple_persistent_connections():
    """Opening 2 connections must create 2 unique IDs in _persistent_connections."""
    _reset_connections()
    import mcp_servers.serial_port_server as srv

    mock_ser = MagicMock()
    with patch.object(srv, "SERIAL_AVAILABLE", True), \
         patch("serial.Serial", return_value=mock_ser):
        r1 = srv.open_persistent_connection(port="COM3", baud_rate=115200)
        r2 = srv.open_persistent_connection(port="COM4", baud_rate=9600)

    id1 = r1.get("connection_id")
    id2 = r2.get("connection_id")
    assert id1 != id2, f"Two connections must have different IDs, both got: '{id1}'"
    assert len(srv._persistent_connections) == 2
    _reset_connections()
