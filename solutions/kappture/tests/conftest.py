import sys
import os

# Add SAGE framework root (3 levels up: tests/ -> kappture/ -> solutions/ -> root)
SAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if SAGE_ROOT not in sys.path:
    sys.path.insert(0, SAGE_ROOT)
