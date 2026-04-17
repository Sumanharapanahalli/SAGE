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
