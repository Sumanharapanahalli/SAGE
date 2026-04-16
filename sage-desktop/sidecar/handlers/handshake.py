"""Handshake handler — called by the Rust side immediately after sidecar spawn.

Probes key SAGE imports so the UI can render a graceful-degradation banner
if something is missing (spec §6.5). Probe failures are *warnings*, not fatal.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Optional

SIDECAR_VERSION = "0.1.0"

# Populated by __main__.py at startup from CLI args.
_SOLUTION_PATH: Optional[Path] = None
_SOLUTION_NAME: str = ""

# Modules the sidecar expects to import from the SAGE repo. Keeping this
# list short and load-bearing — any failure here surfaces as a UI warning
# but does not block startup (spec §6.5 graceful degradation).
_PROBE_IMPORTS = [
    "src.core.proposal_store",
    "src.memory.audit_logger",
    "src.core.project_loader",
    "src.core.llm_gateway",
]


def _sage_version() -> str:
    """Best-effort read of the SAGE package version."""
    try:
        from src import __version__  # type: ignore
        return str(__version__)
    except Exception:  # noqa: BLE001
        return "unknown"


def handshake(params: dict) -> dict:
    warnings: list[str] = []
    for mod in _PROBE_IMPORTS:
        try:
            importlib.import_module(mod)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{mod}: {e}")
    return {
        "sidecar_version": SIDECAR_VERSION,
        "sage_version": _sage_version(),
        "solution_name": _SOLUTION_NAME,
        "solution_path": str(_SOLUTION_PATH) if _SOLUTION_PATH else "",
        "warnings": warnings,
    }
