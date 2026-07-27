"""Contract test for src.integrations.openswe_adapter.OpenSWEAdapter.

Wraps OpenSWERunner to the BaseRunner interface; must remain a concrete
BaseRunner. Previously untested (SAGE self-improvement loop, issue #23).
"""

import inspect

from src.integrations.base_runner import BaseRunner
from src.integrations.openswe_adapter import OpenSWEAdapter


def test_adapter_is_concrete_baserunner():
    assert issubclass(OpenSWEAdapter, BaseRunner)
    assert not inspect.isabstract(OpenSWEAdapter)


def test_adapter_implements_the_interface():
    for method in ("execute", "verify", "get_workflow"):
        assert callable(getattr(OpenSWEAdapter, method, None))
