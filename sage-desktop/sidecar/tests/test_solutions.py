"""Tests for the sidecar solutions handler."""

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import handlers.solutions as solutions  # noqa: E402
from rpc import RPC_INVALID_PARAMS, RpcError  # noqa: E402


def test_list_calls_framework_helper(monkeypatch, tmp_path):
    calls = []

    def fake(root):
        calls.append(root)
        return [{"name": "x", "path": "/x", "has_sage_dir": False}]

    monkeypatch.setattr(solutions, "_list_fn", fake)
    monkeypatch.setattr(solutions, "_sage_root", tmp_path)
    assert solutions.list_solutions({}) == [
        {"name": "x", "path": "/x", "has_sage_dir": False}
    ]
    assert calls == [tmp_path]


def test_list_missing_sage_root_returns_empty(monkeypatch):
    monkeypatch.setattr(solutions, "_sage_root", None)
    assert solutions.list_solutions({}) == []


def test_list_missing_list_fn_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(solutions, "_list_fn", None)
    monkeypatch.setattr(solutions, "_sage_root", tmp_path)
    assert solutions.list_solutions({}) == []


def test_get_current_returns_wired_values(monkeypatch):
    monkeypatch.setattr(solutions, "_current_name", "meditation_app")
    monkeypatch.setattr(solutions, "_current_path", Path("/abs/meditation_app"))
    assert solutions.get_current({}) == {
        "name": "meditation_app",
        "path": str(Path("/abs/meditation_app")),
    }


def test_get_current_returns_none_when_unwired(monkeypatch):
    monkeypatch.setattr(solutions, "_current_name", "")
    monkeypatch.setattr(solutions, "_current_path", None)
    assert solutions.get_current({}) is None


def test_get_current_treats_blank_name_as_unwired(monkeypatch):
    monkeypatch.setattr(solutions, "_current_name", "")
    monkeypatch.setattr(solutions, "_current_path", Path("/something"))
    assert solutions.get_current({}) is None


# ── solutions.remove ───────────────────────────────────────────────────────


@pytest.fixture()
def solutions_dir(monkeypatch, tmp_path):
    """A solutions root with two valid solutions, wired via SAGE_SOLUTIONS_DIR."""
    root = tmp_path / "solutions"
    for name in ("alpha", "beta"):
        d = root / name
        (d / ".sage").mkdir(parents=True)
        (d / "project.yaml").write_text("name: %s\n" % name, encoding="utf-8")
        (d / "src.py").write_text("# precious source code\n", encoding="utf-8")
    monkeypatch.setenv("SAGE_SOLUTIONS_DIR", str(root))
    monkeypatch.setattr(solutions, "_sage_root", tmp_path)
    monkeypatch.setattr(solutions, "_current_name", "")
    monkeypatch.setattr(solutions, "_current_path", None)
    return root


def test_remove_archives_by_default(solutions_dir):
    result = solutions.remove({"name": "alpha"})

    assert result["mode"] == "archive"
    assert not (solutions_dir / "alpha").exists()
    archived = Path(result["archived_to"])
    # Nothing was destroyed — the whole tree moved under the dot-archive dir,
    # which list_solutions skips.
    assert archived.parent == solutions_dir / ".archive"
    assert (archived / "project.yaml").is_file()
    assert (archived / "src.py").read_text(
        encoding="utf-8"
    ) == "# precious source code\n"
    # The other solution is untouched.
    assert (solutions_dir / "beta" / "project.yaml").is_file()


def test_archived_solution_disappears_from_list(solutions_dir):
    from src.core.project_loader import list_solutions as real_list

    solutions.remove({"name": "alpha"})
    names = [s["name"] for s in real_list(solutions_dir.parent)]
    assert names == ["beta"]


def test_remove_delete_requires_matching_confirm(solutions_dir):
    with pytest.raises(RpcError) as e1:
        solutions.remove({"name": "alpha", "mode": "delete"})
    assert e1.value.code == RPC_INVALID_PARAMS

    with pytest.raises(RpcError) as e2:
        solutions.remove({"name": "alpha", "mode": "delete", "confirm": "Alpha"})
    assert e2.value.code == RPC_INVALID_PARAMS

    # Refused, not half-done.
    assert (solutions_dir / "alpha" / "project.yaml").is_file()


def test_remove_delete_with_confirm_erases_the_dir(solutions_dir):
    result = solutions.remove({"name": "alpha", "mode": "delete", "confirm": "alpha"})
    assert result["mode"] == "delete"
    assert not (solutions_dir / "alpha").exists()
    assert not (solutions_dir / ".archive").exists()
    assert (solutions_dir / "beta").is_dir()


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "..",
        ".",
        ".hidden",
        "sub/alpha",
        "sub\\alpha",
        "/etc",
        "C:\\Windows",
        "",
        "   ",
    ],
)
def test_remove_rejects_paths_outside_the_solutions_dir(solutions_dir, tmp_path, name):
    victim = tmp_path / "outside"
    victim.mkdir()
    (victim / "project.yaml").write_text("name: outside\n", encoding="utf-8")

    with pytest.raises(RpcError) as e:
        solutions.remove({"name": name, "mode": "delete", "confirm": name})
    assert e.value.code == RPC_INVALID_PARAMS
    assert victim.is_dir()


def test_remove_refuses_a_dir_that_is_not_a_solution(solutions_dir):
    junk = solutions_dir / "junk"
    junk.mkdir()
    (junk / "notes.txt").write_text("hi", encoding="utf-8")

    with pytest.raises(RpcError) as e:
        solutions.remove({"name": "junk", "mode": "delete", "confirm": "junk"})
    assert e.value.code == RPC_INVALID_PARAMS
    assert junk.is_dir()


def test_remove_refuses_the_active_solution(monkeypatch, solutions_dir):
    monkeypatch.setattr(solutions, "_current_name", "alpha")
    with pytest.raises(RpcError) as e:
        solutions.remove({"name": "alpha"})
    assert e.value.code == RPC_INVALID_PARAMS
    assert "unload" in e.value.message
    assert (solutions_dir / "alpha").is_dir()


def test_remove_rejects_unknown_mode(solutions_dir):
    with pytest.raises(RpcError) as e:
        solutions.remove({"name": "alpha", "mode": "nuke"})
    assert e.value.code == RPC_INVALID_PARAMS
    assert (solutions_dir / "alpha").is_dir()


def test_remove_rejects_non_object_params(solutions_dir):
    with pytest.raises(RpcError) as e:
        solutions.remove(["alpha"])
    assert e.value.code == RPC_INVALID_PARAMS


def test_remove_unknown_solution(solutions_dir):
    with pytest.raises(RpcError) as e:
        solutions.remove({"name": "ghost"})
    assert e.value.code == RPC_INVALID_PARAMS


def test_solutions_rpcs_are_registered():
    """An unregistered handler is dead code — the UI would get -32601."""
    import app

    d = app._build_dispatcher()
    assert "solutions.list" in d._handlers
    assert "solutions.get_current" in d._handlers
    assert "solutions.remove" in d._handlers
