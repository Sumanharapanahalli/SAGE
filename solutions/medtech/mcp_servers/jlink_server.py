"""
SAGE[ai] - J-Link Debugger MCP Server
========================================
FastMCP server exposing J-Link JTAG/SWD debugger tools via pylink-square.
Allows the LLM to inspect memory, flash firmware, and read RTT debug output.
"""

import logging
import time
import os
import binascii

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

# --- Optional heavy import (graceful degradation) ---
try:
    import pylink
    PYLINK_AVAILABLE = True
except ImportError:
    logger.warning("pylink-square not installed. J-Link tools will return errors. Install: pip install pylink-square")
    PYLINK_AVAILABLE = False

from fastmcp import FastMCP

mcp = FastMCP("SAGE J-Link Debugger Server")

# --- Module-level J-Link instance ---
_jlink_instance = None


def _get_jlink() -> "pylink.JLink":
    """Returns the module-level JLink instance, raising if not connected."""
    global _jlink_instance
    if _jlink_instance is None:
        raise RuntimeError("J-Link not connected. Call connect_jlink() first.")
    return _jlink_instance


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def connect_jlink(device: str, interface: str = "SWD", speed: int = 4000) -> dict:
    """
    Connects to a target MCU via J-Link debugger.

    Args:
        device:    Target device name (e.g. 'STM32F407VG', 'nRF52840_xxAA')
        interface: Debug interface — 'SWD' (default) or 'JTAG'
        speed:     Communication speed in kHz (default 4000)

    Returns:
        dict with connection info or 'error'.
    """
    global _jlink_instance

    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed. Run: pip install pylink-square"}

    try:
        jlink = pylink.JLink()
        jlink.open()

        # Set interface
        if interface.upper() == "JTAG":
            jlink.set_tif(pylink.enums.JLinkInterfaces.JTAG)
        else:
            jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)

        jlink.set_speed(speed)
        jlink.connect(device, verbose=False)

        _jlink_instance = jlink

        hw_info = {
            "serial_number": str(jlink.serial_number),
            "hardware_version": str(jlink.hardware_version),
            "firmware_version": str(jlink.firmware_version),
            "product_name": str(jlink.product_name),
        }

        logger.info("J-Link connected to %s via %s @ %d kHz", device, interface, speed)
        return {
            "status": "connected",
            "device": device,
            "interface": interface,
            "speed_khz": speed,
            "jlink_info": hw_info,
        }

    except Exception as e:
        logger.error("Failed to connect J-Link to %s: %s", device, e)
        return {"error": str(e), "device": device}


@mcp.tool()
def disconnect_jlink() -> dict:
    """
    Disconnects from the target and closes the J-Link connection.

    Returns:
        dict with 'status' or 'error'.
    """
    global _jlink_instance

    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    if _jlink_instance is None:
        return {"status": "not_connected", "message": "No active J-Link connection."}

    try:
        _jlink_instance.close()
        _jlink_instance = None
        logger.info("J-Link disconnected.")
        return {"status": "disconnected"}
    except Exception as e:
        logger.error("Error disconnecting J-Link: %s", e)
        _jlink_instance = None
        return {"error": str(e)}


@mcp.tool()
def read_memory(address: int, num_bytes: int) -> dict:
    """
    Reads bytes from target MCU memory.

    Args:
        address:   Memory address (e.g. 0x20000000 for SRAM start)
        num_bytes: Number of bytes to read (max 65536)

    Returns:
        dict with 'hex_data' string and 'address'.
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    if num_bytes > 65536:
        return {"error": "num_bytes exceeds maximum of 65536."}

    try:
        jlink = _get_jlink()
        data = jlink.memory_read(address, num_bytes)
        hex_str = binascii.hexlify(bytes(data)).decode("ascii")
        logger.info("Read %d bytes from 0x%08X", num_bytes, address)
        return {
            "address": f"0x{address:08X}",
            "num_bytes": num_bytes,
            "hex_data": hex_str,
            "preview": hex_str[:64] + ("..." if len(hex_str) > 64 else ""),
        }
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("Memory read failed at 0x%08X: %s", address, e)
        return {"error": str(e), "address": f"0x{address:08X}"}


@mcp.tool()
def write_memory(address: int, data_hex: str) -> dict:
    """
    Writes bytes to target MCU memory.

    Args:
        address:  Memory address to write to
        data_hex: Hex string of bytes to write (e.g. 'DEADBEEF')

    Returns:
        dict with 'status' or 'error'.
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    try:
        data_bytes = binascii.unhexlify(data_hex.replace(" ", ""))
    except Exception as e:
        return {"error": f"Invalid hex data: {e}"}

    try:
        jlink = _get_jlink()
        jlink.memory_write(address, list(data_bytes))
        logger.info("Wrote %d bytes to 0x%08X", len(data_bytes), address)
        return {
            "status": "written",
            "address": f"0x{address:08X}",
            "bytes_written": len(data_bytes),
        }
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("Memory write failed at 0x%08X: %s", address, e)
        return {"error": str(e), "address": f"0x{address:08X}"}


@mcp.tool()
def read_registers() -> dict:
    """
    Reads all CPU core registers from the target MCU.

    Returns:
        dict with 'registers' mapping register name to value (hex string).
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    try:
        jlink = _get_jlink()
        regs = {}
        reg_names = jlink.register_list()
        for name in reg_names:
            try:
                val = jlink.register_read(name)
                regs[name] = f"0x{val:08X}"
            except Exception:
                regs[name] = "N/A"

        logger.info("Read %d registers from target", len(regs))
        return {"registers": regs, "count": len(regs)}
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("Register read failed: %s", e)
        return {"error": str(e)}


@mcp.tool()
def flash_firmware(bin_path: str) -> dict:
    """
    Flashes a binary firmware file to the target MCU.

    Args:
        bin_path: Absolute path to the .bin firmware file

    Returns:
        dict with 'status', 'bytes_flashed', or 'error'.
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    if not os.path.isfile(bin_path):
        return {"error": f"File not found: {bin_path}"}

    file_size = os.path.getsize(bin_path)

    try:
        jlink = _get_jlink()
        logger.info("Flashing firmware: %s (%d bytes)", bin_path, file_size)

        jlink.flash_file(bin_path, 0x08000000)  # STM32 flash base; adjust per device config

        logger.info("Flash complete: %s", bin_path)
        return {
            "status": "flashed",
            "bin_path": bin_path,
            "bytes_flashed": file_size,
        }
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("Flash failed for %s: %s", bin_path, e)
        return {"error": str(e), "bin_path": bin_path}


@mcp.tool()
def reset_target(halt: bool = True) -> dict:
    """
    Resets the target MCU, optionally halting after reset.

    Args:
        halt: If True (default), halt CPU after reset for debugging.

    Returns:
        dict with 'status' or 'error'.
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    try:
        jlink = _get_jlink()
        if halt:
            jlink.reset(halt=True)
            logger.info("Target reset and halted.")
            return {"status": "reset_and_halted"}
        else:
            jlink.reset(halt=False)
            logger.info("Target reset (running).")
            return {"status": "reset_running"}
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("Reset failed: %s", e)
        return {"error": str(e)}


@mcp.tool()
def get_jlink_info() -> dict:
    """
    Returns information about the connected J-Link hardware.

    Returns:
        dict with serial number, firmware version, hardware version, product name.
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    try:
        jlink = _get_jlink()
        return {
            "serial_number": str(jlink.serial_number),
            "firmware_version": str(jlink.firmware_version),
            "hardware_version": str(jlink.hardware_version),
            "product_name": str(jlink.product_name),
            "connected": jlink.connected(),
            "target_connected": jlink.target_connected(),
        }
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("Failed to get J-Link info: %s", e)
        return {"error": str(e)}


@mcp.tool()
def read_rtt_output(duration_seconds: float = 2.0) -> dict:
    """
    Reads RTT (Real-Time Transfer) debug output from the target MCU.

    Args:
        duration_seconds: How long to collect RTT data (default 2.0 seconds)

    Returns:
        dict with 'output' text and 'lines' list.
    """
    if not PYLINK_AVAILABLE:
        return {"error": "pylink-square not installed."}

    try:
        jlink = _get_jlink()

        # Start RTT
        jlink.rtt_start(None)
        time.sleep(0.1)  # Let RTT initialize

        collected = []
        deadline = time.time() + duration_seconds

        while time.time() < deadline:
            try:
                chunk = jlink.rtt_read(0, 1024)
                if chunk:
                    text = "".join(chr(c) for c in chunk)
                    collected.append(text)
            except Exception:
                pass
            time.sleep(0.05)

        jlink.rtt_stop()

        full_output = "".join(collected)
        lines = [l.strip() for l in full_output.splitlines() if l.strip()]

        logger.info("RTT: captured %d bytes, %d lines in %.1fs", len(full_output), len(lines), duration_seconds)
        return {
            "output": full_output,
            "lines": lines,
            "byte_count": len(full_output),
            "duration_seconds": duration_seconds,
        }
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.error("RTT read failed: %s", e)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Standalone test helper
# ---------------------------------------------------------------------------

def test_connection():
    """Quick standalone test — checks if J-Link library is importable."""
    print("=== J-Link Server Standalone Test ===")
    if not PYLINK_AVAILABLE:
        print("ERROR: pylink-square not installed. Run: pip install pylink-square")
    else:
        print("pylink-square is available.")
        try:
            j = pylink.JLink()
            j.open()
            print(f"J-Link detected: {j.product_name} (SN: {j.serial_number})")
            j.close()
        except Exception as e:
            print(f"No J-Link detected or connection failed: {e}")
    print("=====================================")


if __name__ == "__main__":
    mcp.run()
