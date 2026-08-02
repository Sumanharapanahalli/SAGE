"""Pytest config for the sidecar test suite.

Adds the sidecar package and the SAGE repo root to sys.path so that
`from rpc import ...` and `from src.core.proposal_store import ...` both work.
"""

from __future__ import annotations

import sys
from pathlib import Path

SIDECAR_ROOT = Path(__file__).resolve().parent.parent
SAGE_ROOT = SIDECAR_ROOT.parent.parent

sys.path.insert(0, str(SIDECAR_ROOT))
sys.path.insert(0, str(SAGE_ROOT))


import os

import pytest

# Env vars ``app._bootstrap_env`` exports for real (not via monkeypatch) every
# time a test drives ``app.run()``. Nothing restores them, so they leak into
# every subsequent test in the session.
_LEAKY_ENV = ("SAGE_PROJECT", "SAGE_SOLUTIONS_DIR", "SAGE_SOLUTION_PATH")


@pytest.fixture(autouse=True)
def _isolate_sage_env(monkeypatch):
    """Clear the solution-resolution env vars before each test.

    Without this, a registration test that boots the sidecar leaves
    ``SAGE_SOLUTIONS_DIR`` pointing at its tmp dir, and any later test whose
    handler honours that var resolves against the wrong tree — passing alone
    and failing in a full run, or vice versa. Tests that want the override set
    it themselves.
    """
    for name in _LEAKY_ENV:
        monkeypatch.delenv(name, raising=False)
    yield
    # monkeypatch restores what it deleted; explicitly drop anything a test (or
    # _bootstrap_env) SET during the run, so it cannot leak forward either.
    for name in _LEAKY_ENV:
        os.environ.pop(name, None)
