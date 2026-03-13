"""
Reflect solution — test configuration.
"""
import os
import pytest

# Ensure the solution is loaded for all tests
os.environ.setdefault("SAGE_PROJECT", "reflect")
