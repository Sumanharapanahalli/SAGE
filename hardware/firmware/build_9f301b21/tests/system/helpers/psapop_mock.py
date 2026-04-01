"""psapop_mock.py — In-process HTTP mock for PSAPoP (Public Safety Answering Point
of Presence) emergency dispatch API.

Runs a FastAPI server in a background thread.  Tests configure the expected
behaviour (accept / reject) and assert call counts and timing.

IEC 62304 traceability: STS-SYS-003 (emergency dispatch integration)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


@dataclass
class DispatchCall:
    """Records a single PSAPoP dispatch invocation."""
    received_at: float
    payload: Dict[str, Any]
    response_code: int


class PSAPoPMock:
    """Thread-local FastAPI server that records PSAPoP dispatch calls.

    Usage::

        mock = PSAPoPMock(port=8765)
        mock.start()         # blocks until server ready
        # ... run test ...
        mock.assert_called_once_within(t0=fall_time, window_start_s=55, window_end_s=65)
        mock.stop()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self._host = host
        self._port = port
        self._calls: List[DispatchCall] = []
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._app = self._build_app()

    # ── App factory ───────────────────────────────────────────────────────────

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="PSAPoP Mock", docs_url=None)
        mock = self  # closure reference

        @app.post("/v1/dispatch/emergency")
        async def dispatch(request: Request) -> JSONResponse:
            body = await request.json()
            call = DispatchCall(
                received_at=time.monotonic(),
                payload=body,
                response_code=202,
            )
            with mock._lock:
                mock._calls.append(call)
            log.info(
                "PSAPoPMock: dispatch received — device=%s lat=%s lon=%s",
                body.get("device_id"), body.get("latitude"), body.get("longitude"),
            )
            return JSONResponse(status_code=202, content={
                "incident_id": f"INC-{len(mock._calls):06d}",
                "status": "accepted",
                "eta_minutes": 8,
            })

        @app.get("/health")
        async def health() -> JSONResponse:
            return JSONResponse({"status": "ok"})

        return app

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, startup_timeout: float = 5.0) -> None:
        """Start the mock server in a daemon thread."""
        config = uvicorn.Config(
            self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)

        def _run() -> None:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _serve() -> None:
                self._ready.set()
                await self._server.serve()  # type: ignore[union-attr]

            loop.run_until_complete(_serve())

        self._thread = threading.Thread(target=_run, daemon=True,
                                        name="psapop-mock")
        self._thread.start()
        if not self._ready.wait(timeout=startup_timeout):
            raise RuntimeError("PSAPoPMock did not start within timeout")
        # Brief pause for socket to bind
        time.sleep(0.3)
        log.info("PSAPoPMock: listening on %s:%d", self._host, self._port)

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=5.0)
        log.info("PSAPoPMock: stopped")

    def __enter__(self) -> "PSAPoPMock":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # ── Test assertion helpers ────────────────────────────────────────────────

    def reset(self) -> None:
        """Clear call history before a new scenario."""
        with self._lock:
            self._calls.clear()

    def call_count(self) -> int:
        with self._lock:
            return len(self._calls)

    def calls(self) -> List[DispatchCall]:
        with self._lock:
            return list(self._calls)

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def assert_called_exactly_once(
        self,
        t0_monotonic: float,
        window_start_s: float,
        window_end_s: float,
    ) -> DispatchCall:
        """Assert PSAPoP was called exactly once within [t0 + window_start_s,
        t0 + window_end_s].

        Args:
            t0_monotonic: monotonic timestamp of fall injection.
            window_start_s: earliest acceptable dispatch time (seconds after t0).
            window_end_s: latest acceptable dispatch time (seconds after t0).

        Returns:
            The single DispatchCall that matched.

        Raises:
            AssertionError: if call count != 1 or call fell outside window.
        """
        count = self.call_count()
        assert count == 1, (
            f"PSAPoP dispatch called {count} times; expected exactly 1"
        )
        call = self.calls()[0]
        elapsed_s = call.received_at - t0_monotonic
        assert window_start_s <= elapsed_s <= window_end_s, (
            f"PSAPoP dispatch at T+{elapsed_s:.1f}s is outside expected window "
            f"[T+{window_start_s}s, T+{window_end_s}s]"
        )
        return call

    def assert_not_called(self) -> None:
        count = self.call_count()
        assert count == 0, (
            f"PSAPoP dispatch was unexpectedly called {count} time(s)"
        )
