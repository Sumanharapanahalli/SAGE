"""
SAGE MCP Server — Hardware Tools
=================================
Exposes open-source hardware design and test tools as MCP tools for agents.

Supported tools (all open source, graceful degradation if not installed):
  - openocd_flash      : Flash firmware via OpenOCD
  - openocd_debug      : Start GDB debug session via OpenOCD
  - kicad_drc          : Run KiCad Design Rule Check on a .kicad_pcb file
  - ngspice_simulate   : Run ngspice circuit simulation
  - serial_monitor     : Read N bytes from serial port
  - can_send           : Send a CAN frame
  - can_monitor        : Capture N CAN frames
  - pytest_embedded    : Run pytest-embedded test suite against connected hardware
  - jlink_flash        : Flash firmware via J-Link
  - jlink_rtt_read     : Read J-Link RTT output

Usage:
  python solutions/starter/mcp_servers/hardware_tools.py
  (or mount in solutions/<name>/mcp_servers/ and register in project.yaml)

Returns {"available": false, "reason": "..."} if required tool is not installed.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
import time

logger = logging.getLogger("hardware_tools_mcp")

try:
    from fastmcp import FastMCP
    mcp = FastMCP("hardware-tools")
except ImportError:
    # Graceful degradation: FastMCP not installed
    logger.warning("fastmcp not installed — MCP server cannot start")
    mcp = None


def _tool_available(name: str) -> bool:
    """Check if a CLI tool is on PATH."""
    import shutil
    return shutil.which(name) is not None


def _run(cmd: list, timeout: int = 60, cwd: str = None) -> dict:
    """Run a subprocess and return structured result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return {
            "returncode": result.returncode,
            "stdout":     result.stdout[-3000:],
            "stderr":     result.stderr[-1500:],
            "success":    result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Command timed out", "success": False}
    except FileNotFoundError as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e), "success": False}
    except Exception as e:
        return {"returncode": -1, "stdout": "", "stderr": str(e), "success": False}


# ---------------------------------------------------------------------------
# OpenOCD tools
# ---------------------------------------------------------------------------

if mcp:
    @mcp.tool()
    def openocd_flash(
        firmware_path: str,
        config_file: str = "board/stm32f4discovery.cfg",
        verify: bool = True,
    ) -> dict:
        """
        Flash firmware to a connected device via OpenOCD.

        Args:
            firmware_path: Absolute path to the .bin or .elf firmware file.
            config_file:   OpenOCD board/interface config file path.
            verify:        Verify flash contents after programming.

        Returns structured result with success status and OpenOCD output.
        """
        if not _tool_available("openocd"):
            return {"available": False, "reason": "openocd not found on PATH. Install: https://openocd.org/"}

        if not os.path.isfile(firmware_path):
            return {"available": True, "success": False, "error": f"Firmware file not found: {firmware_path}"}

        verify_cmd = "verify" if verify else ""
        cmd = [
            "openocd",
            "-f", config_file,
            "-c", f"program {firmware_path} {verify_cmd} reset exit",
        ]
        result = _run(cmd, timeout=120)
        ok = "Verified OK" in result["stderr"] or result["success"]
        return {
            "available": True,
            "success":   ok,
            "firmware":  firmware_path,
            "config":    config_file,
            "output":    result["stderr"][-1500:],
            "returncode": result["returncode"],
        }


    @mcp.tool()
    def openocd_debug(
        config_file: str = "board/stm32f4discovery.cfg",
        gdb_port: int = 3333,
    ) -> dict:
        """
        Start an OpenOCD GDB server for remote debugging.

        Args:
            config_file: OpenOCD board/interface config file path.
            gdb_port:    TCP port for GDB remote target (default 3333).

        Returns connection info for attaching GDB.
        """
        if not _tool_available("openocd"):
            return {"available": False, "reason": "openocd not found on PATH"}

        # Start OpenOCD as a background process (non-blocking)
        try:
            proc = subprocess.Popen(
                ["openocd", "-f", config_file, "-c", f"gdb_port {gdb_port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(2)
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace")
                return {"available": True, "success": False, "error": stderr[:500]}
            return {
                "available": True,
                "success":   True,
                "pid":       proc.pid,
                "gdb_target": f"target remote localhost:{gdb_port}",
                "instruction": f"Attach GDB with: arm-none-eabi-gdb -ex 'target remote localhost:{gdb_port}'",
            }
        except Exception as e:
            return {"available": True, "success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# KiCad tools
# ---------------------------------------------------------------------------

    @mcp.tool()
    def kicad_drc(
        pcb_file: str,
        output_format: str = "json",
    ) -> dict:
        """
        Run KiCad Design Rule Check (DRC) on a .kicad_pcb file.

        Args:
            pcb_file:      Absolute path to the .kicad_pcb file.
            output_format: Output format — "json" or "text" (default: "json").

        Returns DRC violations and severity counts.
        """
        if not _tool_available("kicad-cli"):
            return {
                "available": False,
                "reason":    "kicad-cli not found. Install KiCad 7+ from https://www.kicad.org/",
            }

        if not os.path.isfile(pcb_file):
            return {"available": True, "success": False, "error": f"PCB file not found: {pcb_file}"}

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name

        try:
            cmd = [
                "kicad-cli", "pcb", "drc",
                "--output", out_path,
                "--format", "json",
                pcb_file,
            ]
            result = _run(cmd, timeout=60)

            violations = []
            if os.path.isfile(out_path):
                with open(out_path, "r") as f:
                    try:
                        drc_data = json.load(f)
                        violations = drc_data.get("violations", [])
                    except json.JSONDecodeError:
                        violations = []

            return {
                "available":       True,
                "success":         result["success"],
                "pcb_file":        pcb_file,
                "violation_count": len(violations),
                "violations":      violations[:50],  # cap for response size
                "stdout":          result["stdout"][:500],
                "stderr":          result["stderr"][:500],
            }
        finally:
            try:
                os.unlink(out_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# ngspice simulation
# ---------------------------------------------------------------------------

    @mcp.tool()
    def ngspice_simulate(
        netlist_file: str,
        output_variables: list = None,
    ) -> dict:
        """
        Run an ngspice circuit simulation from a SPICE netlist file.

        Args:
            netlist_file:      Absolute path to a .cir or .sp SPICE netlist.
            output_variables:  List of variable names to extract from output (optional).

        Returns simulation status and any extracted output values.
        """
        if not _tool_available("ngspice"):
            return {
                "available": False,
                "reason":    "ngspice not found. Install: sudo apt install ngspice / brew install ngspice",
            }

        if not os.path.isfile(netlist_file):
            return {"available": True, "success": False, "error": f"Netlist not found: {netlist_file}"}

        result = _run(["ngspice", "-b", netlist_file], timeout=120)
        output = (result["stdout"] + result["stderr"])[:3000]

        extracted = {}
        if output_variables:
            for var in output_variables:
                for line in output.split("\n"):
                    if var.lower() in line.lower() and "=" in line:
                        extracted[var] = line.strip()
                        break

        return {
            "available":         True,
            "success":           result["success"],
            "netlist":           netlist_file,
            "output":            output,
            "extracted_values":  extracted,
            "returncode":        result["returncode"],
        }


# ---------------------------------------------------------------------------
# Serial monitor
# ---------------------------------------------------------------------------

    @mcp.tool()
    def serial_monitor(
        port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        read_bytes: int = 1024,
        timeout_seconds: float = 2.0,
    ) -> dict:
        """
        Read bytes from a serial port (UART monitor).

        Args:
            port:            Serial port device path (e.g. /dev/ttyUSB0, COM3).
            baud_rate:       Baud rate (default 115200).
            read_bytes:      Number of bytes to read (default 1024).
            timeout_seconds: Read timeout in seconds (default 2.0).

        Returns raw output decoded as UTF-8 (errors replaced).
        """
        try:
            import serial
        except ImportError:
            return {"available": False, "reason": "pyserial not installed: pip install pyserial"}

        try:
            with serial.Serial(port, baud_rate, timeout=timeout_seconds) as ser:
                data = ser.read(read_bytes)
                text = data.decode("utf-8", errors="replace")
            return {
                "available":  True,
                "success":    True,
                "port":       port,
                "baud_rate":  baud_rate,
                "bytes_read": len(data),
                "output":     text,
            }
        except Exception as e:
            return {"available": True, "success": False, "error": str(e), "port": port}


# ---------------------------------------------------------------------------
# CAN bus tools
# ---------------------------------------------------------------------------

    @mcp.tool()
    def can_send(
        channel: str = "can0",
        arbitration_id: int = 0x123,
        data: list = None,
        interface: str = "socketcan",
        is_extended_id: bool = False,
    ) -> dict:
        """
        Send a single CAN frame.

        Args:
            channel:         CAN interface name (e.g. can0, vcan0).
            arbitration_id:  CAN arbitration ID (decimal or hex int).
            data:            List of up to 8 bytes (integers 0-255).
            interface:       python-can bustype (default: socketcan).
            is_extended_id:  True for 29-bit extended frame.

        Returns send status and echoed frame data.
        """
        try:
            import can
        except ImportError:
            return {"available": False, "reason": "python-can not installed: pip install python-can"}

        data = data or [0x00]
        try:
            bus = can.interface.Bus(channel=channel, bustype=interface)
            msg = can.Message(
                arbitration_id=arbitration_id,
                data=bytes(data),
                is_extended_id=is_extended_id,
            )
            bus.send(msg)
            bus.shutdown()
            return {
                "available":      True,
                "success":        True,
                "channel":        channel,
                "arbitration_id": hex(arbitration_id),
                "data_sent":      data,
                "dlc":            len(data),
            }
        except Exception as e:
            return {"available": True, "success": False, "error": str(e)}


    @mcp.tool()
    def can_monitor(
        channel: str = "can0",
        interface: str = "socketcan",
        frame_count: int = 10,
        timeout_seconds: float = 5.0,
    ) -> dict:
        """
        Capture CAN frames from the bus.

        Args:
            channel:         CAN interface name (e.g. can0, vcan0).
            interface:       python-can bustype (default: socketcan).
            frame_count:     Number of frames to capture (default 10).
            timeout_seconds: Total capture timeout in seconds (default 5.0).

        Returns list of captured frames with arbitration ID, DLC, and data.
        """
        try:
            import can
        except ImportError:
            return {"available": False, "reason": "python-can not installed: pip install python-can"}

        try:
            bus    = can.interface.Bus(channel=channel, bustype=interface)
            frames = []
            start  = time.time()

            while len(frames) < frame_count and (time.time() - start) < timeout_seconds:
                msg = bus.recv(timeout=1.0)
                if msg:
                    frames.append({
                        "timestamp":      msg.timestamp,
                        "arbitration_id": hex(msg.arbitration_id),
                        "dlc":            msg.dlc,
                        "data":           list(msg.data),
                        "is_extended_id": msg.is_extended_id,
                        "is_error_frame": msg.is_error_frame,
                    })

            bus.shutdown()
            return {
                "available":     True,
                "success":       True,
                "channel":       channel,
                "frames_captured": len(frames),
                "frames":        frames,
                "capture_duration_seconds": round(time.time() - start, 3),
            }
        except Exception as e:
            return {"available": True, "success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# pytest-embedded
# ---------------------------------------------------------------------------

    @mcp.tool()
    def pytest_embedded(
        test_path: str = "tests/",
        target: str = "esp32",
        port: str = "/dev/ttyUSB0",
        extra_args: list = None,
    ) -> dict:
        """
        Run pytest-embedded test suite against connected hardware.

        Args:
            test_path:   Path to test directory or file.
            target:      Target chip (esp32, esp32s2, esp32c3, stm32, nrf52, ...).
            port:        Serial port the device is connected to.
            extra_args:  Additional pytest arguments.

        Returns pytest exit code and output.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                return {"available": False, "reason": "pytest not installed"}
        except Exception:
            return {"available": False, "reason": "pytest not found"}

        cmd = [
            sys.executable, "-m", "pytest",
            test_path,
            f"--target={target}",
            f"--port={port}",
            "-v",
        ] + (extra_args or [])

        result = _run(cmd, timeout=300)
        output = (result["stdout"] + result["stderr"])[:4000]

        # Parse pytest summary
        passed = failed = errors = 0
        for line in output.split("\n"):
            if "passed" in line:
                try:
                    passed = int(line.split("passed")[0].strip().split()[-1])
                except Exception:
                    pass
            if "failed" in line:
                try:
                    failed = int(line.split("failed")[0].strip().split()[-1])
                except Exception:
                    pass
            if "error" in line.lower():
                try:
                    errors = int(line.split("error")[0].strip().split()[-1])
                except Exception:
                    pass

        return {
            "available":  True,
            "success":    result["success"],
            "target":     target,
            "port":       port,
            "test_path":  test_path,
            "passed":     passed,
            "failed":     failed,
            "errors":     errors,
            "output":     output,
            "returncode": result["returncode"],
        }


# ---------------------------------------------------------------------------
# J-Link tools
# ---------------------------------------------------------------------------

    @mcp.tool()
    def jlink_flash(
        firmware_path: str,
        device: str = "STM32F407VG",
        flash_address: str = "0x08000000",
        interface: str = "SWD",
        speed: int = 4000,
    ) -> dict:
        """
        Flash firmware to a connected device via J-Link.

        Args:
            firmware_path:  Absolute path to .bin or .hex firmware file.
            device:         SEGGER device name (e.g. STM32F407VG, nRF52840_xxAA).
            flash_address:  Flash start address in hex (default 0x08000000).
            interface:      Debug interface — SWD or JTAG (default SWD).
            speed:          Interface speed in kHz (default 4000).

        Returns flash result with J-Link output.
        """
        if not _tool_available("JLinkExe"):
            return {
                "available": False,
                "reason":    "JLinkExe not found. Install SEGGER J-Link tools from https://www.segger.com/",
            }

        if not os.path.isfile(firmware_path):
            return {"available": True, "success": False, "error": f"Firmware not found: {firmware_path}"}

        script = (
            f"h\n"
            f"loadbin {firmware_path},{flash_address}\n"
            f"r\n"
            f"g\n"
            f"exit\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jlink", delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            cmd = [
                "JLinkExe",
                "-device", device,
                "-if", interface,
                "-speed", str(speed),
                "-autoconnect", "1",
                "-NoGui", "1",
                "-CommandFile", script_path,
            ]
            result = _run(cmd, timeout=60)
            ok = result["success"] or "Flash download: Program OK" in result["stdout"]
            return {
                "available":    True,
                "success":      ok,
                "device":       device,
                "firmware":     firmware_path,
                "flash_address": flash_address,
                "output":       result["stdout"][-1500:],
                "returncode":   result["returncode"],
            }
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass


    @mcp.tool()
    def jlink_rtt_read(
        device: str = "STM32F407VG",
        interface: str = "SWD",
        speed: int = 4000,
        read_timeout_ms: int = 2000,
        channel: int = 0,
    ) -> dict:
        """
        Read Real-Time Transfer (RTT) output from a connected device via J-Link.

        Args:
            device:          SEGGER device name.
            interface:       Debug interface — SWD or JTAG.
            speed:           Interface speed in kHz.
            read_timeout_ms: How long to collect RTT data (milliseconds).
            channel:         RTT channel index (default 0 = Terminal).

        Returns RTT output text captured from the device.
        """
        if not _tool_available("JLinkExe"):
            return {
                "available": False,
                "reason":    "JLinkExe not found. Install SEGGER J-Link tools from https://www.segger.com/",
            }

        timeout_s = read_timeout_ms / 1000
        script = (
            f"connect\n"
            f"r\n"
            f"g\n"
            f"rttstart\n"
            f"sleep {read_timeout_ms}\n"
            f"rttread {channel}\n"
            f"rttstop\n"
            f"exit\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jlink", delete=False) as f:
            f.write(script)
            script_path = f.name

        try:
            cmd = [
                "JLinkExe",
                "-device", device,
                "-if", interface,
                "-speed", str(speed),
                "-autoconnect", "1",
                "-NoGui", "1",
                "-CommandFile", script_path,
            ]
            result = _run(cmd, timeout=int(timeout_s) + 15)
            output = result["stdout"] + result["stderr"]

            # Extract RTT output between RTT markers if present
            rtt_text = output
            if "RTT>" in output:
                lines = [l for l in output.split("\n") if "RTT>" not in l and l.strip()]
                rtt_text = "\n".join(lines)

            return {
                "available":   True,
                "success":     result["success"],
                "device":      device,
                "channel":     channel,
                "rtt_output":  rtt_text[-2000:],
                "returncode":  result["returncode"],
            }
        finally:
            try:
                os.unlink(script_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if mcp is None:
        print("ERROR: fastmcp not installed. Run: pip install fastmcp")
        sys.exit(1)
    logger.info("Starting SAGE Hardware Tools MCP server")
    mcp.run()
