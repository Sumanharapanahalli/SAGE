"""
SAGE[ai] - Serial Port MCP Server
===================================
FastMCP server exposing serial port communication tools.
Allows the LLM to interact with embedded devices via COM ports.
"""

import logging
import time
import uuid
import os
from typing import Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# --- Optional heavy imports (graceful degradation) ---
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    logger.warning("pyserial not installed. Serial tools will return errors. Install: pip install pyserial")
    SERIAL_AVAILABLE = False

from fastmcp import FastMCP

mcp = FastMCP("SAGE Serial Port Server")

# --- Module-level persistent connection store ---
_persistent_connections: dict = {}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_serial_ports() -> dict:
    """
    Lists all available serial/COM ports on the system.

    Returns:
        dict with 'ports' list (each entry has 'device', 'description', 'hwid')
        or 'error' key on failure.
    """
    if not SERIAL_AVAILABLE:
        return {"error": "pyserial is not installed. Run: pip install pyserial"}

    try:
        ports = serial.tools.list_ports.comports()
        result = []
        for p in ports:
            result.append({
                "device": p.device,
                "description": p.description,
                "hwid": p.hwid,
            })
        logger.info("Found %d serial ports", len(result))
        return {"ports": result, "count": len(result)}
    except Exception as e:
        logger.error("Failed to list serial ports: %s", e)
        return {"error": str(e)}


@mcp.tool()
def send_serial_command(port: str, baud_rate: int, command: str, timeout: float = 2.0) -> dict:
    """
    Opens a serial port, sends a command string (with newline), and reads the response.

    Args:
        port:      Serial port name (e.g. 'COM3' or '/dev/ttyUSB0')
        baud_rate: Baud rate (e.g. 115200)
        command:   Command string to send (newline appended automatically)
        timeout:   Read timeout in seconds (default 2.0)

    Returns:
        dict with 'response' (decoded string) or 'error'.
    """
    if not SERIAL_AVAILABLE:
        return {"error": "pyserial is not installed. Run: pip install pyserial"}

    try:
        logger.info("Opening %s @ %d baud, sending: %r", port, baud_rate, command)
        with serial.Serial(port, baud_rate, timeout=timeout) as ser:
            # Flush any stale data
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Send command
            ser.write((command + "\n").encode("utf-8"))
            ser.flush()

            # Read response until timeout
            response_bytes = ser.read_until(expected=b"\n", size=4096)
            if not response_bytes:
                # Try reading available bytes
                time.sleep(timeout)
                response_bytes = ser.read(ser.in_waiting or 1)

            response = response_bytes.decode("utf-8", errors="replace").strip()
            logger.info("Response from %s: %r", port, response)
            return {"port": port, "command": command, "response": response}

    except serial.SerialException as e:
        logger.error("Serial error on %s: %s", port, e)
        return {"error": f"Serial error: {e}", "port": port}
    except Exception as e:
        logger.error("Unexpected error on %s: %s", port, e)
        return {"error": str(e), "port": port}


@mcp.tool()
def read_serial_output(port: str, baud_rate: int, duration_seconds: float = 3.0) -> dict:
    """
    Opens a serial port and reads all output for a specified duration.

    Args:
        port:             Serial port name
        baud_rate:        Baud rate
        duration_seconds: How long to read (default 3.0 seconds)

    Returns:
        dict with 'output' (full captured text) and 'lines' list.
    """
    if not SERIAL_AVAILABLE:
        return {"error": "pyserial is not installed. Run: pip install pyserial"}

    try:
        logger.info("Reading from %s @ %d baud for %.1fs", port, baud_rate, duration_seconds)
        collected = []
        deadline = time.time() + duration_seconds

        with serial.Serial(port, baud_rate, timeout=0.1) as ser:
            ser.reset_input_buffer()
            while time.time() < deadline:
                waiting = ser.in_waiting
                if waiting:
                    chunk = ser.read(waiting).decode("utf-8", errors="replace")
                    collected.append(chunk)
                else:
                    time.sleep(0.05)

        full_output = "".join(collected)
        lines = [l.strip() for l in full_output.splitlines() if l.strip()]
        logger.info("Captured %d bytes, %d lines from %s", len(full_output), len(lines), port)
        return {
            "port": port,
            "duration_seconds": duration_seconds,
            "output": full_output,
            "lines": lines,
            "byte_count": len(full_output),
        }

    except serial.SerialException as e:
        logger.error("Serial error reading %s: %s", port, e)
        return {"error": f"Serial error: {e}", "port": port}
    except Exception as e:
        logger.error("Unexpected error reading %s: %s", port, e)
        return {"error": str(e), "port": port}


@mcp.tool()
def open_persistent_connection(port: str, baud_rate: int) -> dict:
    """
    Opens a serial connection that persists across tool calls (stored in module state).

    Args:
        port:      Serial port name
        baud_rate: Baud rate

    Returns:
        dict with 'connection_id' to use in subsequent calls, or 'error'.
    """
    if not SERIAL_AVAILABLE:
        return {"error": "pyserial is not installed. Run: pip install pyserial"}

    try:
        conn_id = str(uuid.uuid4())[:8]
        ser = serial.Serial(port, baud_rate, timeout=1.0)
        _persistent_connections[conn_id] = {
            "serial": ser,
            "port": port,
            "baud_rate": baud_rate,
            "opened_at": time.time(),
        }
        logger.info("Persistent connection %s opened on %s @ %d baud", conn_id, port, baud_rate)
        return {
            "connection_id": conn_id,
            "port": port,
            "baud_rate": baud_rate,
            "status": "open",
        }
    except serial.SerialException as e:
        logger.error("Failed to open persistent connection to %s: %s", port, e)
        return {"error": f"Serial error: {e}", "port": port}
    except Exception as e:
        logger.error("Unexpected error opening %s: %s", port, e)
        return {"error": str(e)}


@mcp.tool()
def close_connection(connection_id: str) -> dict:
    """
    Closes a persistent serial connection previously opened with open_persistent_connection.

    Args:
        connection_id: The ID returned by open_persistent_connection

    Returns:
        dict with 'status' or 'error'.
    """
    if connection_id not in _persistent_connections:
        return {"error": f"Connection ID '{connection_id}' not found.", "known_ids": list(_persistent_connections.keys())}

    try:
        conn = _persistent_connections.pop(connection_id)
        conn["serial"].close()
        logger.info("Persistent connection %s closed (was on %s)", connection_id, conn["port"])
        return {"connection_id": connection_id, "status": "closed", "port": conn["port"]}
    except Exception as e:
        logger.error("Error closing connection %s: %s", connection_id, e)
        return {"error": str(e), "connection_id": connection_id}


# ---------------------------------------------------------------------------
# Standalone test helper
# ---------------------------------------------------------------------------

def test_connection():
    """Quick standalone test — lists available ports."""
    print("=== Serial Port Server Standalone Test ===")
    result = list_serial_ports()
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"Found {result['count']} port(s):")
        for p in result["ports"]:
            print(f"  {p['device']:12s} — {p['description']}")
    print("==========================================")


if __name__ == "__main__":
    mcp.run()
