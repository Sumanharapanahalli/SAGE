"""
hil_robot_library.py
Robot Framework keyword library for OpenOCD/GDB HIL integration.

Import in Robot Framework:
    Library    hil_robot_library.py
"""

import socket
import time
from typing import Optional


OPENOCD_TIMEOUT = 5.0
PROMPT = b"\x1a"


class hil_robot_library:
    """Robot Framework library — OpenOCD telnet keyword implementation."""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def __init__(self) -> None:
        self._sock: Optional[socket.socket] = None

    # ── Connection ────────────────────────────────────────────────────────────

    def open_openocd_connection(self, host: str = "127.0.0.1",
                                port: int = 4444) -> None:
        """Open a telnet connection to the OpenOCD command interface."""
        self._sock = socket.create_connection((host, int(port)),
                                               timeout=OPENOCD_TIMEOUT)
        self._drain()

    def close_openocd_connection(self) -> None:
        """Close the OpenOCD telnet connection."""
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    # ── Low-level I/O ─────────────────────────────────────────────────────────

    def _send(self, cmd: str) -> str:
        if self._sock is None:
            raise RuntimeError("OpenOCD not connected — call Open OpenOCD Connection first")
        self._sock.sendall((cmd + "\n").encode())
        return self._recv_until(PROMPT)

    def _recv_until(self, sentinel: bytes, max_bytes: int = 4096) -> str:
        assert self._sock is not None
        buf = b""
        while sentinel not in buf:
            chunk = self._sock.recv(256)
            if not chunk:
                break
            buf += chunk
            if len(buf) > max_bytes:
                break
        return buf.decode(errors="replace").strip()

    def _drain(self) -> None:
        if self._sock is None:
            return
        self._sock.settimeout(0.5)
        try:
            while True:
                data = self._sock.recv(256)
                if not data:
                    break
        except OSError:
            pass
        finally:
            self._sock.settimeout(OPENOCD_TIMEOUT)

    # ── OpenOCD keywords ──────────────────────────────────────────────────────

    def openocd_command(self, cmd: str) -> str:
        """Execute an arbitrary OpenOCD Tcl command and return the response."""
        resp = self._send(cmd)
        return resp

    def openocd_read_word(self, addr: str) -> str:
        """Read a 32-bit word from the given hex address and return as hex string."""
        resp = self._send(f"mdw {addr}")
        # Parse: "0x40011000: 00000001 \n..."
        parts = resp.split(":")
        if len(parts) >= 2:
            return parts[-1].strip().split()[0]
        return "00000000"

    def openocd_write_word(self, addr: str, value: str) -> None:
        """Write a 32-bit word to the given hex address."""
        self._send(f"mww {addr} {value}")

    def encode_stimulus_to_adc(self,
                                velocity_mps: str,
                                acceleration_mps2: str,
                                yaw_rate_radps: str,
                                steering_angle_rad: str,
                                throttle_pct: str,
                                brake_pressure_kpa: str,
                                data_valid: str = "True") -> list:
        """
        Encode 6 physical vehicle-state values to 12-bit ADC words.
        Returns a list of integers (hex-formatted as strings for Robot).
        """
        def clamp(v: int) -> int:
            return max(0, min(0x0FFF, v))

        v   = float(velocity_mps)
        a   = float(acceleration_mps2)
        y   = float(yaw_rate_radps)
        s   = float(steering_angle_rad)
        t   = float(throttle_pct)
        b   = float(brake_pressure_kpa)
        valid = str(data_valid).strip().lower() in ("true", "1", "yes")

        words = [
            clamp(int(v  / 0.08789)),
            clamp(int(a  / 0.03831 + 2048)),
            clamp(int(y  / 0.001533 + 2048)),
            clamp(int(s  / 0.003834 + 2048)),
            clamp(int(t  / 0.02442)),
            clamp(int(b  / 0.09775)) | (0x8000 if valid else 0),
        ]
        return [f"0x{w:04X}" for w in words]
