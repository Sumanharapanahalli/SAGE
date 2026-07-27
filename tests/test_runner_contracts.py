"""Contract tests for the domain execution runners (src/integrations/*_runner.py).

Several runners (openml, opensim, opendesign, opendoc, openbrowser, openstrategy,
…) had no test referencing them (SAGE self-improvement loop, issue #23). Rather
than assert domain behaviour speculatively, these lock the BaseRunner contract:
every runner module must import cleanly and expose a CONCRETE BaseRunner subclass
that implements the abstract interface. This catches import regressions and any
runner that silently fails to implement execute()/verify()/get_workflow().
"""

import importlib
import inspect

import pytest

from src.integrations.base_runner import BaseRunner

RUNNER_MODULES = [
    "openml",
    "opensim",
    "openstrategy",
    "opendesign",
    "opendoc",
    "openbrowser",
    "openeda",
    "openfw",
    "openterminal",
]


def _runner_class(module_name):
    mod = importlib.import_module(f"src.integrations.{module_name}_runner")
    concrete = [
        c
        for _, c in inspect.getmembers(mod, inspect.isclass)
        if issubclass(c, BaseRunner)
        and c is not BaseRunner
        and c.__module__ == mod.__name__
    ]
    return mod, concrete


@pytest.mark.parametrize("module_name", RUNNER_MODULES)
def test_runner_exposes_one_concrete_baserunner_subclass(module_name):
    _mod, concrete = _runner_class(module_name)
    assert len(concrete) == 1, (
        f"{module_name}_runner should expose exactly one BaseRunner subclass, "
        f"found {[c.__name__ for c in concrete]}"
    )
    cls = concrete[0]
    assert not inspect.isabstract(cls), (
        f"{cls.__name__} is abstract — it must implement execute/verify/get_workflow"
    )


@pytest.mark.parametrize("module_name", RUNNER_MODULES)
def test_runner_implements_the_abstract_interface(module_name):
    _mod, concrete = _runner_class(module_name)
    cls = concrete[0]
    for method in ("execute", "verify", "get_workflow"):
        assert callable(getattr(cls, method, None)), (
            f"{cls.__name__} is missing BaseRunner method {method}()"
        )
