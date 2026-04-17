"""PyInstaller runtime hook — wires sys.path so the bundled framework
resolves without depending on ``SAGE_ROOT`` env var.

At runtime, PyInstaller extracts data files to ``sys._MEIPASS``. We add
that directory to ``sys.path`` so ``from src.core...`` works from inside
the single-file executable.
"""
import os
import sys

_meipass = getattr(sys, "_MEIPASS", None)
if _meipass and _meipass not in sys.path:
    sys.path.insert(0, _meipass)

# Signal to ``app.py`` that the bundled framework is already on sys.path
# — its SAGE_ROOT fallback branch should not try to infer a repo layout
# (which doesn't exist inside the bundle).
if _meipass:
    os.environ.setdefault("SAGE_ROOT", _meipass)
