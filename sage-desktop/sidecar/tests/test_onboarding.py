"""Tests for the sidecar onboarding handler."""
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.onboarding as onb  # noqa: E402
from rpc import RpcError  # noqa: E402


def test_generate_requires_description(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", lambda **kw: {})
    with pytest.raises(RpcError) as e:
        onb.generate({"solution_name": "x"})
    assert e.value.code == -32602


def test_generate_requires_solution_name(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", lambda **kw: {})
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "yoga app"})
    assert e.value.code == -32602


def test_generate_happy_path(monkeypatch):
    monkeypatch.setattr(
        onb,
        "_generate_fn",
        lambda **kw: {
            "solution_name": "yoga",
            "status": "created",
            "path": "/abs/yoga",
            "files": {"project.yaml": "a: 1"},
            "suggested_routes": [],
            "message": "ok",
        },
    )
    out = onb.generate(
        {
            "description": "yoga app thirty chars long enough",
            "solution_name": "yoga",
        }
    )
    assert out["status"] == "created"
    assert out["files"]["project.yaml"] == "a: 1"


def test_generate_wraps_llm_failure_as_sidecar_error(monkeypatch):
    def boom(**_kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(onb, "_generate_fn", boom)
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "x" * 40, "solution_name": "y"})
    assert e.value.code == -32000


def test_generate_wraps_validation_error_as_invalid_params(monkeypatch):
    def boom(**_kw):
        raise ValueError("bad yaml")

    monkeypatch.setattr(onb, "_generate_fn", boom)
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "x" * 40, "solution_name": "y"})
    assert e.value.code == -32602


def test_generate_missing_generate_fn_returns_sidecar_error(monkeypatch):
    monkeypatch.setattr(onb, "_generate_fn", None)
    with pytest.raises(RpcError) as e:
        onb.generate({"description": "x" * 40, "solution_name": "y"})
    assert e.value.code == -32000


def test_generate_rejects_non_dict_params():
    with pytest.raises(RpcError) as e:
        onb.generate([])
    assert e.value.code == -32602
