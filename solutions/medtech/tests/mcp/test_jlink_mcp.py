"""
SAGE[ai] - Unit tests for J-Link MCP Server (mcp_servers/jlink_server.py)

Marked as @pytest.mark.hardware — skipped if pylink is not installed.
All actual pylink calls are mocked so no physical device is needed.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.hardware]

# Skip entire module if pylink is not importable
pylink = pytest.importorskip("pylink", reason="pylink-square not installed; skipping J-Link tests.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_jlink_state():
    """Reset the module-level J-Link instance to None."""
    import mcp_servers.jlink_server as srv
    srv._jlink_instance = None


# ---------------------------------------------------------------------------
# connect_jlink
# ---------------------------------------------------------------------------


def test_connect_jlink_opens_connection(mock_jlink):
    """connect_jlink() must return a success dict with 'status': 'connected'."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        result = srv.connect_jlink(device="nRF52840_xxAA", interface="SWD", speed=4000)
    _reset_jlink_state()
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result.get("status") == "connected", f"Expected 'connected', got: {result}"


def test_connect_jlink_device_name_stored(mock_jlink):
    """After connect_jlink(device='nRF52840'), module state must have an active JLink instance."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv.connect_jlink(device="nRF52840", interface="SWD", speed=4000)
    assert srv._jlink_instance is not None, "_jlink_instance must be set after connect."
    _reset_jlink_state()


def test_disconnect_clears_state(mock_jlink):
    """After disconnect_jlink(), _jlink_instance must be None."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv.connect_jlink(device="STM32F407VG")
        assert srv._jlink_instance is not None
        result = srv.disconnect_jlink()
    assert srv._jlink_instance is None, "_jlink_instance must be None after disconnect."
    assert result.get("status") == "disconnected", f"Expected 'disconnected': {result}"


def test_disconnect_when_not_connected():
    """disconnect_jlink() when not connected must return a graceful status dict (not an exception)."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        result = srv.disconnect_jlink()
    # Should NOT raise exception, should return a dict
    assert isinstance(result, dict), "disconnect_jlink() must return a dict."
    assert "status" in result or "error" in result, f"Result must have 'status' or 'error': {result}"


def test_read_memory_returns_hex(mock_jlink):
    """read_memory() must return a dict with 'hex_data' as a hex string."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    mock_jlink["instance"].memory_read.return_value = [0xDE, 0xAD, 0xBE, 0xEF]

    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.read_memory(address=0x20000000, num_bytes=4)

    _reset_jlink_state()
    assert "hex_data" in result, f"Expected 'hex_data' in result: {result}"
    assert isinstance(result["hex_data"], str), "hex_data must be a string."
    assert all(c in "0123456789abcdefABCDEF" for c in result["hex_data"]), (
        f"hex_data must be a valid hex string: {result['hex_data']!r}"
    )


def test_read_memory_correct_length(mock_jlink):
    """Requesting 4 bytes must produce a hex string of 8 hex characters (2 chars per byte)."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    mock_jlink["instance"].memory_read.return_value = [0xDE, 0xAD, 0xBE, 0xEF]

    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.read_memory(address=0x20000000, num_bytes=4)

    _reset_jlink_state()
    hex_str = result.get("hex_data", "")
    assert len(hex_str) == 8, f"Expected 8 hex chars for 4 bytes, got {len(hex_str)}: '{hex_str}'"


def test_write_memory_calls_jlink(mock_jlink):
    """write_memory() must call jlink.memory_write() with correct address."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.write_memory(address=0x20000000, data_hex="DEADBEEF")

    _reset_jlink_state()
    assert mock_jlink["instance"].memory_write.called, "jlink.memory_write() must be called."
    call_args = mock_jlink["instance"].memory_write.call_args
    assert call_args[0][0] == 0x20000000, f"Expected address 0x20000000, got {call_args[0][0]}"
    assert "error" not in result, f"Unexpected error: {result.get('error')}"


def test_read_registers_returns_dict(mock_jlink):
    """read_registers() must return a dict with 'registers' mapping register names to values."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    mock_jlink["instance"].register_list.return_value = ["R0", "R1", "PC", "SP"]
    mock_jlink["instance"].register_read.return_value = 0xDEADBEEF

    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.read_registers()

    _reset_jlink_state()
    assert "registers" in result, f"Expected 'registers' in result: {result}"
    regs = result["registers"]
    assert isinstance(regs, dict), "registers must be a dict."
    for name in ["R0", "R1", "PC", "SP"]:
        assert name in regs, f"Register '{name}' must be in result."


def test_flash_firmware_validates_file_exists():
    """flash_firmware() with a non-existent file path must return error about file not found."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        result = srv.flash_firmware(bin_path="/nonexistent/path/firmware.bin")
    assert "error" in result, "Expected 'error' for non-existent file."
    assert "not found" in result["error"].lower() or "file" in result["error"].lower(), (
        f"Error must mention file not found: {result['error']}"
    )


def test_reset_target_with_halt(mock_jlink):
    """reset_target(halt=True) must call jlink.reset() with halt=True."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.reset_target(halt=True)

    _reset_jlink_state()
    mock_jlink["instance"].reset.assert_called_once_with(halt=True)
    assert "error" not in result, f"Unexpected error: {result.get('error')}"


def test_get_jlink_info_returns_hardware_info(mock_jlink):
    """get_jlink_info() must return a dict with serial_number and firmware_version."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.get_jlink_info()

    _reset_jlink_state()
    assert "serial_number" in result, f"Expected 'serial_number': {result}"
    assert "firmware_version" in result, f"Expected 'firmware_version': {result}"
    assert "error" not in result, f"Unexpected error: {result.get('error')}"


def test_read_rtt_returns_string(mock_jlink):
    """read_rtt_output() must return a dict with 'output' as a string."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv

    # Mock RTT read to return some chars
    mock_jlink["instance"].rtt_read.return_value = [ord(c) for c in "RTT: boot complete\n"]

    with patch.object(srv, "PYLINK_AVAILABLE", True), \
         patch("time.sleep"), \
         patch("time.time", side_effect=[0.0, 0.0, 5.0]):
        srv._jlink_instance = mock_jlink["instance"]
        result = srv.read_rtt_output(duration_seconds=0.1)

    _reset_jlink_state()
    assert "output" in result, f"Expected 'output' in result: {result}"
    assert isinstance(result["output"], str), "output must be a string."


def test_connect_when_already_connected(mock_jlink):
    """Calling connect_jlink() twice must handle the second call gracefully."""
    _reset_jlink_state()
    import mcp_servers.jlink_server as srv
    with patch.object(srv, "PYLINK_AVAILABLE", True):
        result1 = srv.connect_jlink(device="nRF52840")
        # Second call — should not crash
        try:
            result2 = srv.connect_jlink(device="nRF52840")
        except Exception as exc:
            pytest.fail(f"Second connect_jlink() raised an exception: {exc}")
    _reset_jlink_state()
    assert isinstance(result2, dict), "Second connect_jlink() must return a dict."
