import os
import tempfile
import pytest


def test_scan_produces_markdown(tmp_path):
    """Scan a temp directory with a Python file and get markdown back."""
    py_file = tmp_path / "example.py"
    py_file.write_text("class Foo:\n    def bar(self):\n        pass\n\ndef baz():\n    pass\n")
    from src.core.repo_map import generate_repo_map
    result = generate_repo_map(str(tmp_path))
    assert "example.py" in result
    assert "Foo" in result
    assert "baz" in result


def test_scan_excludes_venv(tmp_path):
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "something.py").write_text("def secret(): pass\n")
    real_file = tmp_path / "main.py"
    real_file.write_text("def real(): pass\n")
    from src.core.repo_map import generate_repo_map
    result = generate_repo_map(str(tmp_path))
    assert "real" in result
    assert "secret" not in result


def test_scan_respects_max_files(tmp_path):
    for i in range(20):
        (tmp_path / f"file{i}.py").write_text(f"def func{i}(): pass\n")
    from src.core.repo_map import generate_repo_map
    result = generate_repo_map(str(tmp_path), max_files=5)
    # At most 5 file entries in the result
    file_count = result.count("`.py`") + result.count(".py`:")
    assert file_count <= 5
