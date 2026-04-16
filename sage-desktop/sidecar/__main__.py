"""sage-desktop sidecar entry point.

Spawned by the Rust Tauri app. Delegates to ``app.run()`` so the event
loop is importable from tests.

CLI:
    python -m sidecar --solution-name NAME --solution-path PATH
    python sidecar/__main__.py --solution-name NAME --solution-path PATH
"""
import os
import sys

# Ensure sibling modules (app.py, rpc.py, etc.) are importable whether
# launched as `python -m sidecar` (package mode) or `python __main__.py`.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from app import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
