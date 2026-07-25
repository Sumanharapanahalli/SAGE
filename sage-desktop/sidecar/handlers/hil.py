"""HIL (Hardware-in-the-Loop) handlers — ports src.integrations.hil_runner.

    GET  /hil/status         -> status
    POST /hil/connect        -> connect
    POST /hil/run-suite      -> run_suite
    GET  /hil/report/{id}    -> report

Scope note: HILRunner.flash_firmware() exists on the runner class but has
NO endpoint anywhere in the web API (src/interface/api.py exposes only
status/connect/run-suite/report) — not ported here either, for the same
reason: mirror the existing API surface, don't introduce a new one.
Firmware flashing stays unreachable from both interfaces.

Like workflow.py/compliance.py, hil_runner is a module-level *singleton*
(get_hil_runner() / _hil_runner) — there is no store/instance to wire at
startup, so these handlers import the module directly at call time
rather than reading an injected module-level variable.

Note: hil_runner._write_audit() (called internally by run_test/run_suite)
imports src.memory.audit_logger's own global `audit_logger` singleton
directly — not the per-solution AuditLogger instance the desktop sidecar
wires into handlers.audit. That's a pre-existing framework behavior
(same for the web API), out of scope for this port.
"""

from __future__ import annotations

from rpc import RPC_INVALID_PARAMS, RPC_SIDECAR_ERROR, RpcError


def status(params: dict) -> dict:
    try:
        from src.integrations import hil_runner as hr

        if hr._hil_runner is None:
            return {
                "connected": False,
                "transport": "none",
                "session_id": None,
                "tests_run": 0,
                "message": "No HIL runner initialised. Call hil.connect to start.",
            }
        return hr._hil_runner.status()
    except Exception as e:  # noqa: BLE001
        return {"connected": False, "error": str(e)}


def connect(params: dict) -> dict:
    transport = params.get("transport") or "mock"
    config = params.get("config") or {}
    if not isinstance(config, dict):
        raise RpcError(RPC_INVALID_PARAMS, "'config' must be an object")

    try:
        from src.integrations.hil_runner import HILTransport

        HILTransport(str(transport).lower())
    except ValueError:
        raise RpcError(RPC_INVALID_PARAMS, f"unknown transport: {transport}")

    try:
        from src.integrations.hil_runner import get_hil_runner

        runner = get_hil_runner(transport=transport, config=config)
        connected = runner.connect()
        return {
            "transport": transport,
            "connected": connected,
            "session_id": runner.session_id,
            "message": (
                "Connected"
                if connected
                else f"Could not connect to {transport} hardware — operating in degraded mode"
            ),
        }
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"hil.connect failed: {e}") from e


def run_suite(params: dict) -> dict:
    tests_raw = params.get("tests")
    if not tests_raw or not isinstance(tests_raw, list):
        raise RpcError(
            RPC_INVALID_PARAMS, "'tests' list is required and must not be empty"
        )
    transport = params.get("transport") or "mock"
    config = params.get("config") or {}
    if not isinstance(config, dict):
        raise RpcError(RPC_INVALID_PARAMS, "'config' must be an object")

    try:
        from src.integrations.hil_runner import (
            get_hil_runner,
            HILTestCase,
            HILTransport,
        )

        runner = get_hil_runner(transport=transport, config=config)
        if not runner._connected:
            runner.connect()

        test_cases = []
        for item in tests_raw:
            transport_str = item.get("transport", transport)
            try:
                t_enum = HILTransport(str(transport_str).lower())
            except ValueError:
                t_enum = HILTransport.MOCK
            test_cases.append(
                HILTestCase(
                    id=item.get("id", "TC-UNKNOWN"),
                    name=item.get("name", "Unnamed test"),
                    requirement_id=item.get("requirement_id", "REQ-UNKNOWN"),
                    description=item.get("description", ""),
                    procedure=item.get("procedure", []),
                    expected_result=item.get("expected_result", ""),
                    transport=t_enum,
                    timeout_seconds=item.get("timeout_seconds", 30),
                )
            )

        return runner.run_suite(test_cases)
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"hil.run_suite failed: {e}") from e


def report(params: dict) -> dict:
    session_id = params.get("session_id")
    if not session_id:
        raise RpcError(RPC_INVALID_PARAMS, "session_id required")
    standard = params.get("standard") or "IEC62304"

    try:
        from src.integrations import hil_runner as hr

        if hr._hil_runner is None or hr._hil_runner.session_id != session_id:
            raise RpcError(
                RPC_INVALID_PARAMS,
                f"no active HIL session with id '{session_id}' — run hil.run_suite first",
                {"session_id": session_id},
            )
        return hr._hil_runner.generate_report(standard=standard)
    except RpcError:
        raise
    except Exception as e:  # noqa: BLE001
        raise RpcError(RPC_SIDECAR_ERROR, f"hil.report failed: {e}") from e
