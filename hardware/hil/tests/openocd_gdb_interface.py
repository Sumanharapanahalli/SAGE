"""
openocd_gdb_interface.py — Low-level OpenOCD/GDB helpers for HIL automation
===========================================================================
Provides:
  - BreakpointSession: set/clear breakpoints, read registers, dump stack
  - MemoryMap: symbolic access to HIL result block fields
  - FaultRelayController: drive the fault-relay MCU over a second serial port

Used by both hil_harness.py (pytest) and the Robot Framework keyword library.
"""

from __future__ import annotations

import socket
import struct
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Optional

# ---------------------------------------------------------------------------
# OpenOCD TCL socket client
# ---------------------------------------------------------------------------
_OPENOCD_TCL_HOST = "127.0.0.1"
_OPENOCD_TCL_PORT = 6666
_TCL_TERMINATOR   = b"\x1a"   # Ctrl-Z terminates each TCL command


class OpenOCDTCL:
    """Send raw TCL commands to OpenOCD and receive the response."""

    def __init__(
        self,
        host: str = _OPENOCD_TCL_HOST,
        port: int = _OPENOCD_TCL_PORT,
    ) -> None:
        self._host   = host
        self._port   = port
        self._sock: Optional[socket.socket] = None

    def connect(self) -> None:
        self._sock = socket.create_connection((self._host, self._port), timeout=5.0)

    def disconnect(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def send(self, command: str) -> str:
        if self._sock is None:
            raise RuntimeError("Not connected to OpenOCD TCL port")
        payload = command.encode("ascii") + _TCL_TERMINATOR
        self._sock.sendall(payload)
        return self._receive()

    def _receive(self) -> str:
        buf = b""
        assert self._sock is not None
        while True:
            chunk = self._sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            if _TCL_TERMINATOR in buf:
                buf = buf.replace(_TCL_TERMINATOR, b"")
                break
        return buf.decode("ascii", errors="replace").strip()

    # ---- Convenience wrappers ------------------------------------------------

    def halt(self) -> str:
        return self.send("halt")

    def resume(self) -> str:
        return self.send("resume")

    def reset_halt(self) -> str:
        return self.send("reset halt")

    def read_word(self, address: int) -> int:
        resp = self.send(f"mdw 0x{address:08x}")
        # Response: "0x20000000: cafebef0 \n"
        parts = resp.split(":")
        if len(parts) < 2:
            raise ValueError(f"Unexpected mdw response: {resp!r}")
        return int(parts[1].strip(), 16)

    def read_memory_raw(self, address: int, length_bytes: int) -> bytes:
        """Read `length_bytes` bytes via mdb command, return as bytes object."""
        words = (length_bytes + 3) // 4
        data = bytearray()
        for i in range(words):
            word = self.read_word(address + i * 4)
            data += struct.pack("<I", word)
        return bytes(data[:length_bytes])

    def write_word(self, address: int, value: int) -> None:
        self.send(f"mww 0x{address:08x} 0x{value:08x}")

    def set_breakpoint(self, address: int) -> None:
        self.send(f"bp 0x{address:08x} 2 hw")

    def clear_breakpoint(self, address: int) -> None:
        self.send(f"rbp 0x{address:08x}")

    def read_register(self, reg_name: str) -> int:
        resp = self.send(f"reg {reg_name}")
        m_val = resp.split(":")
        if len(m_val) >= 2:
            return int(m_val[-1].strip(), 0)
        raise ValueError(f"Cannot parse register response: {resp!r}")


# ---------------------------------------------------------------------------
# MemoryMap — symbolic access to HIL result block
# ---------------------------------------------------------------------------
@dataclass
class HILMemoryMap:
    BASE: int = 0x20000000

    @property
    def MAGIC(self)             -> int: return self.BASE + 0x00
    @property
    def SUITE_PASS_MASK(self)   -> int: return self.BASE + 0x04
    @property
    def SUITE_FAIL_MASK(self)   -> int: return self.BASE + 0x08
    @property
    def TOTAL_ASSERTIONS(self)  -> int: return self.BASE + 0x0C
    @property
    def FAILED_ASSERTIONS(self) -> int: return self.BASE + 0x10


HIL_MAP = HILMemoryMap()


def read_hil_result(tcl: OpenOCDTCL) -> dict:
    """Read the HIL result block and return as a dict."""
    return {
        "magic":             tcl.read_word(HIL_MAP.MAGIC),
        "suite_pass_mask":   tcl.read_word(HIL_MAP.SUITE_PASS_MASK),
        "suite_fail_mask":   tcl.read_word(HIL_MAP.SUITE_FAIL_MASK),
        "total_assertions":  tcl.read_word(HIL_MAP.TOTAL_ASSERTIONS),
        "failed_assertions": tcl.read_word(HIL_MAP.FAILED_ASSERTIONS),
    }


# ---------------------------------------------------------------------------
# Context manager: connect → run → disconnect
# ---------------------------------------------------------------------------
@contextmanager
def openocd_session(
    host: str = _OPENOCD_TCL_HOST,
    port: int = _OPENOCD_TCL_PORT,
) -> Generator[OpenOCDTCL, None, None]:
    tcl = OpenOCDTCL(host=host, port=port)
    tcl.connect()
    try:
        yield tcl
    finally:
        tcl.disconnect()


# ---------------------------------------------------------------------------
# FaultRelayController — drives the STM32G0 fault-relay MCU
# Relay MCU listens on a second UART; one-byte command protocol:
#   0x01-0x11  inject fault (matches HIL_FaultType_t enum)
#   0x00       clear all faults
#   0xF0       measure actuator (relay ADC) → returns 8 bytes (rise_ms, fall_ms)
#   0xF1       play fall profile  → returns 4 bytes (latency_ms)
#   0xF2       pulse IMU DRDY (GPIO) → no data return
# ---------------------------------------------------------------------------
import serial as _serial   # noqa: E402 — deferred import for Robot compat


class FaultRelayController:
    def __init__(self, port: str, baudrate: int = 115200) -> None:
        self._port     = port
        self._baudrate = baudrate
        self._ser: Optional[_serial.Serial] = None

    def open(self) -> None:
        self._ser = _serial.Serial(
            self._port,
            baudrate=self._baudrate,
            timeout=2.0,
        )
        time.sleep(0.1)   # relay MCU boot settle

    def close(self) -> None:
        if self._ser is not None and self._ser.is_open:
            self._ser.close()

    def _send(self, cmd: int, read_bytes: int = 0) -> bytes:
        if self._ser is None:
            raise RuntimeError("FaultRelay not open")
        self._ser.write(bytes([cmd]))
        if read_bytes > 0:
            return self._ser.read(read_bytes)
        return b""

    def inject(self, fault_type: int) -> None:
        if not 0x01 <= fault_type <= 0x11:
            raise ValueError(f"Invalid fault type: 0x{fault_type:02X}")
        self._send(fault_type)

    def clear(self) -> None:
        self._send(0x00)

    def measure_actuator(self) -> tuple[int, int]:
        raw = self._send(0xF0, read_bytes=8)
        if len(raw) < 8:
            raise RuntimeError("Short read from relay actuator measure")
        rise_ms, fall_ms = struct.unpack("<II", raw)
        return rise_ms, fall_ms

    def play_fall_profile(self) -> int:
        raw = self._send(0xF1, read_bytes=4)
        if len(raw) < 4:
            raise RuntimeError("Short read from relay fall profile")
        (latency_ms,) = struct.unpack("<I", raw)
        return latency_ms

    def pulse_imu_drdy(self) -> None:
        self._send(0xF2)


# ---------------------------------------------------------------------------
# Standalone CLI: read & print result block from a running OpenOCD instance
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    with openocd_session() as tcl:
        tcl.halt()
        result = read_hil_result(tcl)
        print("HIL Result Block:")
        for k, v in result.items():
            print(f"  {k:25s} = 0x{v:08X}  ({v})")
        passed = (result["magic"] == 0xCAFEBEEF and
                  result["failed_assertions"] == 0)
        print(f"\nOverall: {'PASS' if passed else 'FAIL'}")
