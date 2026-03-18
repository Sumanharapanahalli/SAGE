"""
SAGE HIL Runner — Hardware-in-the-Loop Test Integration
========================================================
Supports multiple hardware transports:
  - serial/UART  (pyserial — already in ecosystem)
  - J-Link/SWD   (pylink-square or OpenOCD subprocess)
  - CAN bus      (python-can)
  - JTAG via OpenOCD subprocess
  - Mock mode    (no hardware — for CI environments)

All test results are written to the SAGE audit log for regulatory evidence.
Graceful degradation: if hardware not connected, returns BLOCKED results.

Usage:
  from src.integrations.hil_runner import get_hil_runner, HILTestCase, HILTransport
  runner = get_hil_runner(transport="mock")
  runner.connect()
  result = runner.run_test(HILTestCase(...))
  report = runner.generate_report(standard="IEC62304")
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger("HILRunner")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HILTransport(str, Enum):
    SERIAL  = "serial"
    JLINK   = "jlink"
    CAN     = "can"
    OPENOCD = "openocd"
    MOCK    = "mock"


class TestVerdict(str, Enum):
    PASS    = "PASS"
    FAIL    = "FAIL"
    ERROR   = "ERROR"
    SKIP    = "SKIP"
    BLOCKED = "BLOCKED"  # hardware not available


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HILTestCase:
    id: str
    name: str
    requirement_id: str        # links to requirement (e.g. REQ-001, IEC62304-5.5.1)
    description: str
    procedure: list            # ordered steps — list[str]
    expected_result: str
    transport: HILTransport = HILTransport.MOCK
    timeout_seconds: int = 30


@dataclass
class HILTestResult:
    test_id: str
    test_name: str
    requirement_id: str
    verdict: TestVerdict
    actual_result: str
    duration_seconds: float
    timestamp: str
    evidence: dict = field(default_factory=dict)  # raw data captured from hardware
    deviation_notes: str = ""


# ---------------------------------------------------------------------------
# HIL Runner
# ---------------------------------------------------------------------------

class HILRunner:
    """
    Hardware-in-the-Loop test runner with regulatory evidence capture.
    Instantiate once per test session; all results accumulate for report generation.

    Design principles:
    - All hardware interactions degrade gracefully (BLOCKED, never crash)
    - Every result is written to the SAGE audit log for regulatory evidence
    - Supports serial, J-Link, CAN bus, OpenOCD, and mock transport
    """

    def __init__(self, transport: HILTransport = HILTransport.MOCK, config: dict = None):
        self.transport = transport
        self.config = config or {}
        self.results: list = []          # list[HILTestResult]
        self.session_id = f"hil_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self._serial_conn = None
        self._can_bus = None
        self._connected = False
        logger.info(
            "HILRunner initialized: transport=%s session=%s",
            transport.value, self.session_id,
        )

    # -----------------------------------------------------------------------
    # Transport connection
    # -----------------------------------------------------------------------

    def connect(self) -> bool:
        """Establish hardware connection. Returns True if connected."""
        if self.transport == HILTransport.MOCK:
            logger.info("HIL mock mode — no hardware required")
            self._connected = True
            return True
        if self.transport == HILTransport.SERIAL:
            self._connected = self._connect_serial()
            return self._connected
        if self.transport == HILTransport.JLINK:
            self._connected = self._connect_jlink()
            return self._connected
        if self.transport == HILTransport.CAN:
            self._connected = self._connect_can()
            return self._connected
        if self.transport == HILTransport.OPENOCD:
            self._connected = self._connect_openocd()
            return self._connected
        logger.warning("Unknown transport: %s", self.transport)
        return False

    def disconnect(self):
        """Close all open hardware connections."""
        if self._serial_conn:
            try:
                self._serial_conn.close()
            except Exception:
                pass
            self._serial_conn = None
        if self._can_bus:
            try:
                self._can_bus.shutdown()
            except Exception:
                pass
            self._can_bus = None
        self._connected = False

    def _connect_serial(self) -> bool:
        try:
            import serial  # pyserial
            port     = self.config.get("port", "/dev/ttyUSB0")
            baud     = self.config.get("baud_rate", 115200)
            timeout  = self.config.get("timeout", 2)
            self._serial_conn = serial.Serial(port, baud, timeout=timeout)
            logger.info("Serial connected: %s @ %d baud", port, baud)
            return True
        except ImportError:
            logger.warning("pyserial not installed — serial transport unavailable")
            return False
        except Exception as e:
            logger.warning("Serial connect failed (non-fatal): %s", e)
            return False

    def _connect_jlink(self) -> bool:
        try:
            device    = self.config.get("device", "")
            serial_no = self.config.get("serial_number", "")
            speed     = self.config.get("speed", 4000)
            cmd = [
                "JLinkExe",
                "-device", device,
                "-if", "SWD",
                "-speed", str(speed),
                "-autoconnect", "1",
                "-NoGui", "1",
            ]
            if serial_no:
                cmd += ["-SelectEmuBySN", str(serial_no)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            connected = result.returncode == 0
            if connected:
                logger.info("J-Link connected: device=%s", device)
            else:
                logger.warning("J-Link connect failed: %s", result.stderr[:200])
            return connected
        except FileNotFoundError:
            logger.warning("JLinkExe not found — J-Link transport unavailable")
            return False
        except Exception as e:
            logger.warning("J-Link connect failed (non-fatal): %s", e)
            return False

    def _connect_can(self) -> bool:
        try:
            import can  # python-can
            interface      = self.config.get("interface", "socketcan")
            channel        = self.config.get("channel", "can0")
            bitrate        = self.config.get("bitrate", 500000)
            self._can_bus  = can.interface.Bus(
                channel=channel, bustype=interface, bitrate=bitrate
            )
            logger.info("CAN connected: %s / %s @ %d bps", interface, channel, bitrate)
            return True
        except ImportError:
            logger.warning("python-can not installed — CAN transport unavailable")
            return False
        except Exception as e:
            logger.warning("CAN connect failed (non-fatal): %s", e)
            return False

    def _connect_openocd(self) -> bool:
        try:
            cfg_file = self.config.get("openocd_config", "board/stm32f4discovery.cfg")
            result   = subprocess.run(
                ["openocd", "-f", cfg_file, "-c", "init; exit"],
                capture_output=True, text=True, timeout=15,
            )
            ok = "Info : Listening" in result.stderr or result.returncode == 0
            if ok:
                logger.info("OpenOCD connected: cfg=%s", cfg_file)
            else:
                logger.warning("OpenOCD connect failed: %s", result.stderr[:200])
            return ok
        except FileNotFoundError:
            logger.warning("openocd not found — OpenOCD transport unavailable")
            return False
        except Exception as e:
            logger.warning("OpenOCD connect failed (non-fatal): %s", e)
            return False

    # -----------------------------------------------------------------------
    # Firmware flashing
    # -----------------------------------------------------------------------

    def flash_firmware(self, firmware_path: str) -> dict:
        """
        Flash a firmware binary to the connected device.
        Returns {"success": bool, "output": str, "error": str}.
        """
        if not os.path.isfile(firmware_path):
            return {"success": False, "output": "", "error": f"Firmware not found: {firmware_path}"}

        if self.transport == HILTransport.MOCK:
            logger.info("MOCK: flash_firmware(%s)", firmware_path)
            return {"success": True, "output": f"[MOCK] Flashed {firmware_path}", "error": ""}

        if self.transport == HILTransport.JLINK:
            return self._flash_jlink(firmware_path)

        if self.transport == HILTransport.OPENOCD:
            return self._flash_openocd(firmware_path)

        if self.transport == HILTransport.SERIAL:
            # Serial bootloader flash (e.g. stm32flash)
            return self._flash_serial(firmware_path)

        return {"success": False, "output": "", "error": f"Flash not supported for transport: {self.transport}"}

    def _flash_jlink(self, firmware_path: str) -> dict:
        try:
            device    = self.config.get("device", "")
            speed     = self.config.get("speed", 4000)
            addr      = self.config.get("flash_address", "0x08000000")
            jlink_cmd = (
                f"h\n"
                f"loadbin {firmware_path},{addr}\n"
                f"r\n"
                f"g\n"
                f"exit\n"
            )
            script_path = "/tmp/sage_jlink_flash.jlink"
            with open(script_path, "w") as f:
                f.write(jlink_cmd)
            cmd = [
                "JLinkExe",
                "-device", device,
                "-if", "SWD",
                "-speed", str(speed),
                "-autoconnect", "1",
                "-NoGui", "1",
                "-CommandFile", script_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            ok = result.returncode == 0 or "Flash download: Program OK" in result.stdout
            return {
                "success": ok,
                "output": result.stdout[-1000:],
                "error": result.stderr[-500:] if not ok else "",
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _flash_openocd(self, firmware_path: str) -> dict:
        try:
            cfg_file = self.config.get("openocd_config", "board/stm32f4discovery.cfg")
            cmd = [
                "openocd",
                "-f", cfg_file,
                "-c", f"program {firmware_path} verify reset exit",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            ok = "Verified OK" in result.stderr or result.returncode == 0
            return {
                "success": ok,
                "output": result.stderr[-1000:],
                "error": result.stderr[-500:] if not ok else "",
            }
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def _flash_serial(self, firmware_path: str) -> dict:
        try:
            port  = self.config.get("port", "/dev/ttyUSB0")
            baud  = self.config.get("baud_rate", 115200)
            # stm32flash is common for UART bootloader
            cmd   = ["stm32flash", "-w", firmware_path, "-v", "-b", str(baud), port]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            ok = result.returncode == 0
            return {
                "success": ok,
                "output": result.stdout[-1000:],
                "error": result.stderr[-500:] if not ok else "",
            }
        except FileNotFoundError:
            return {"success": False, "output": "", "error": "stm32flash not installed"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    # -----------------------------------------------------------------------
    # Test execution
    # -----------------------------------------------------------------------

    def run_test(self, test: HILTestCase) -> HILTestResult:
        """Execute a single HIL test case. Always returns a result (BLOCKED if no HW)."""
        start = time.time()
        ts    = datetime.now(timezone.utc).isoformat()

        if self.transport == HILTransport.MOCK:
            verdict  = TestVerdict.PASS
            actual   = f"[MOCK] {test.expected_result}"
            evidence = {"mock": True, "procedure_steps": len(test.procedure)}
        elif not self._connected:
            verdict  = TestVerdict.BLOCKED
            actual   = "Hardware transport not connected"
            evidence = {}
        else:
            verdict, actual, evidence = self._execute_on_hardware(test)

        duration = time.time() - start
        result   = HILTestResult(
            test_id=test.id,
            test_name=test.name,
            requirement_id=test.requirement_id,
            verdict=verdict,
            actual_result=actual,
            duration_seconds=round(duration, 3),
            timestamp=ts,
            evidence=evidence,
        )
        self.results.append(result)
        logger.info("HIL test %s: %s (%s)", test.id, verdict.value, test.name)
        self._write_audit(result)
        return result

    def _execute_on_hardware(self, test: HILTestCase) -> tuple:
        """Execute test on real hardware. Returns (verdict, actual_result, evidence)."""
        evidence = {}
        try:
            if self.transport == HILTransport.SERIAL and self._serial_conn:
                cmd      = f"RUN_TEST {test.id}\n".encode()
                self._serial_conn.write(cmd)
                time.sleep(0.5)
                response = self._serial_conn.read(512).decode(errors="replace")
                evidence["raw_response"] = response
                evidence["command_sent"] = f"RUN_TEST {test.id}"
                upper = response.upper()
                if "PASS" in upper:
                    return TestVerdict.PASS, response.strip(), evidence
                elif "FAIL" in upper:
                    return TestVerdict.FAIL, response.strip(), evidence
                else:
                    return TestVerdict.ERROR, f"Unexpected response: {response[:200]}", evidence

            elif self.transport == HILTransport.CAN and self._can_bus:
                import can
                # Send test trigger frame (CAN ID 0x7FF = broadcast test command)
                test_id_bytes = test.id.encode()[:8]
                msg = can.Message(arbitration_id=0x7FF, data=test_id_bytes, is_extended_id=False)
                self._can_bus.send(msg)
                # Wait for response frame (CAN ID 0x7FE = test result)
                deadline = time.time() + test.timeout_seconds
                while time.time() < deadline:
                    rx = self._can_bus.recv(timeout=1.0)
                    if rx and rx.arbitration_id == 0x7FE:
                        resp = bytes(rx.data).decode(errors="replace")
                        evidence["can_frame"] = {
                            "arb_id": hex(rx.arbitration_id),
                            "data": list(rx.data),
                        }
                        if "PASS" in resp.upper():
                            return TestVerdict.PASS, resp.strip(), evidence
                        else:
                            return TestVerdict.FAIL, resp.strip(), evidence
                return TestVerdict.ERROR, "CAN response timeout", evidence

            else:
                return TestVerdict.BLOCKED, f"Transport {self.transport} not active", evidence

        except Exception as e:
            logger.error("HIL hardware execution error for %s: %s", test.id, e)
            return TestVerdict.ERROR, str(e), evidence

    def _write_audit(self, result: HILTestResult):
        """Write test result to SAGE audit log for regulatory evidence."""
        try:
            from src.memory.audit_logger import audit_logger
            audit_logger.log_event(
                actor="HILRunner",
                action_type="HIL_TEST_RESULT",
                input_context=f"{result.test_id}: {result.test_name}",
                output_content=result.verdict.value,
                metadata={
                    "session_id": self.session_id,
                    "test_id": result.test_id,
                    "requirement_id": result.requirement_id,
                    "verdict": result.verdict.value,
                    "duration_seconds": result.duration_seconds,
                    "timestamp": result.timestamp,
                    "evidence": result.evidence,
                },
            )
        except Exception as e:
            logger.debug("Audit log for HIL test failed (non-fatal): %s", e)

    def run_suite(self, tests: list) -> dict:
        """Run a list of HILTestCase objects. Returns a structured summary."""
        results  = [self.run_test(t) for t in tests]
        passed   = sum(1 for r in results if r.verdict == TestVerdict.PASS)
        failed   = sum(1 for r in results if r.verdict == TestVerdict.FAIL)
        errors   = sum(1 for r in results if r.verdict == TestVerdict.ERROR)
        skipped  = sum(1 for r in results if r.verdict == TestVerdict.SKIP)
        blocked  = sum(1 for r in results if r.verdict == TestVerdict.BLOCKED)
        total    = len(results)
        return {
            "session_id":  self.session_id,
            "transport":   self.transport.value,
            "total":       total,
            "passed":      passed,
            "failed":      failed,
            "errors":      errors,
            "skipped":     skipped,
            "blocked":     blocked,
            "pass_rate":   round(passed / total * 100, 1) if total else 0.0,
            "results":     [vars(r) for r in results],
        }

    def generate_report(self, standard: str = "IEC62304") -> dict:
        """
        Generate a regulatory evidence report from all accumulated results.
        Supports IEC 62304, DO-178C, EN 50128, ISO 26262, IEC 62443.
        """
        passed  = sum(1 for r in self.results if r.verdict == TestVerdict.PASS)
        failed  = sum(1 for r in self.results if r.verdict == TestVerdict.FAIL)
        blocked = sum(1 for r in self.results if r.verdict == TestVerdict.BLOCKED)
        total   = len(self.results)

        # Standard-specific metadata
        standard_meta = {
            "IEC62304": {
                "full_name": "IEC 62304:2015+A1 — Medical Device Software",
                "evidence_sections": ["§5.5 Unit Testing", "§5.6 Integration Testing", "§5.7 System Testing"],
                "pass_criteria": "All safety-class tests must PASS with zero FAILs",
            },
            "DO178C": {
                "full_name": "DO-178C — Software Considerations in Airborne Systems",
                "evidence_sections": ["§6.4 Reviews and Analyses", "§6.4.3 Hardware/Software Integration Testing"],
                "pass_criteria": "All DAL-A/B tests must PASS; coverage objectives met",
            },
            "EN50128": {
                "full_name": "EN 50128:2011+A2 — Railway Applications Software",
                "evidence_sections": ["§6.2 Software Test Specification", "§6.3 Software Integration Test"],
                "pass_criteria": "SIL-3/4 requires formal verification in addition to testing",
            },
            "ISO26262": {
                "full_name": "ISO 26262:2018 — Road Vehicles Functional Safety",
                "evidence_sections": ["Part 6 §9 Software Unit Testing", "Part 6 §10 Software Integration Testing"],
                "pass_criteria": "ASIL C/D: MC/DC coverage; all tests PASS",
            },
            "IEC62443": {
                "full_name": "IEC 62443-3-3 — Industrial Cybersecurity",
                "evidence_sections": ["§SR 3.1 Communication Integrity", "§SR 3.3 Security Functionality Verification"],
                "pass_criteria": "All security-level requirements verified",
            },
        }.get(standard, {
            "full_name": standard,
            "evidence_sections": [],
            "pass_criteria": "All tests must PASS",
        })

        return {
            "report_type":       f"HIL Test Evidence — {standard}",
            "standard":          standard,
            "standard_full_name": standard_meta.get("full_name", standard),
            "generated_at":      datetime.now(timezone.utc).isoformat(),
            "session_id":        self.session_id,
            "transport":         self.transport.value,
            "evidence_sections": standard_meta.get("evidence_sections", []),
            "pass_criteria":     standard_meta.get("pass_criteria", ""),
            "summary": {
                "total_tests":   total,
                "passed":        passed,
                "failed":        failed,
                "blocked":       blocked,
                "pass_rate":     round(passed / total * 100, 1) if total else 0.0,
                "overall_status": "PASS" if (total > 0 and failed == 0 and blocked == 0) else "FAIL",
            },
            "traceability": [
                {
                    "requirement_id":    r.requirement_id,
                    "test_id":           r.test_id,
                    "test_name":         r.test_name,
                    "verdict":           r.verdict.value,
                    "timestamp":         r.timestamp,
                    "duration_seconds":  r.duration_seconds,
                    "evidence_captured": bool(r.evidence),
                }
                for r in self.results
            ],
            "deviations": [
                {"test_id": r.test_id, "notes": r.deviation_notes}
                for r in self.results if r.deviation_notes
            ],
            "failed_tests": [
                {
                    "test_id":       r.test_id,
                    "test_name":     r.test_name,
                    "requirement_id": r.requirement_id,
                    "actual_result": r.actual_result,
                    "verdict":       r.verdict.value,
                }
                for r in self.results
                if r.verdict in (TestVerdict.FAIL, TestVerdict.ERROR, TestVerdict.BLOCKED)
            ],
        }

    def status(self) -> dict:
        """Return current runner status for API health checks."""
        return {
            "session_id":    self.session_id,
            "transport":     self.transport.value,
            "connected":     self._connected,
            "tests_run":     len(self.results),
            "passed":        sum(1 for r in self.results if r.verdict == TestVerdict.PASS),
            "failed":        sum(1 for r in self.results if r.verdict == TestVerdict.FAIL),
            "blocked":       sum(1 for r in self.results if r.verdict == TestVerdict.BLOCKED),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_hil_runner: Optional[HILRunner] = None


def get_hil_runner(transport: str = "mock", config: dict = None) -> HILRunner:
    """Return (or create) the global HIL runner for the requested transport."""
    global _hil_runner
    transport_enum = HILTransport(transport.lower())
    if _hil_runner is None or _hil_runner.transport != transport_enum:
        _hil_runner = HILRunner(transport_enum, config or {})
    return _hil_runner
