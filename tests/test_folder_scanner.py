import os
import tempfile
import pytest
from src.core.folder_scanner import FolderScanner


def _make_tree(base: str, files: dict) -> None:
    """Create a directory tree from a {rel_path: content} dict."""
    for rel_path, content in files.items():
        abs_path = os.path.join(base, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)


def test_scan_nonexistent_path_raises():
    scanner = FolderScanner()
    with pytest.raises(FileNotFoundError):
        scanner.scan("/nonexistent/path/xyz")


def test_scan_reads_readme_first():
    with tempfile.TemporaryDirectory() as tmp:
        _make_tree(tmp, {
            "README.md": "# My Project\nThis is the readme.",
            "src/main.py": "def main(): pass",
        })
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        # README should appear before main.py
        assert result.index("README.md") < result.index("main.py")
        assert "This is the readme." in result
        assert "def main" in result


def test_scan_skips_git_and_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        _make_tree(tmp, {
            ".git/config": "secret git config",
            "node_modules/pkg/index.js": "module.exports = {}",
            "__pycache__/app.cpython-311.pyc": "bytecode",
            "src/app.py": "print('hello')",
        })
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        assert ".git/config" not in result
        assert "node_modules" not in result
        assert "__pycache__" not in result
        assert "print('hello')" in result


def test_scan_respects_token_budget():
    with tempfile.TemporaryDirectory() as tmp:
        # Create files totalling well over 1000 chars
        for i in range(20):
            _make_tree(tmp, {f"src/file_{i}.py": "x = " + "a" * 200})
        scanner = FolderScanner()
        result = scanner.scan(tmp, max_tokens=50)  # ~200 chars
        # Result should be truncated
        assert len(result) <= 230  # budget is max_tokens*4=200 chars, header ~24 chars max


def test_scan_includes_file_headers():
    with tempfile.TemporaryDirectory() as tmp:
        _make_tree(tmp, {"src/utils.py": "def helper(): pass"})
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        assert "utils.py" in result
        assert "def helper" in result


def test_scan_empty_folder_returns_empty_string():
    with tempfile.TemporaryDirectory() as tmp:
        scanner = FolderScanner()
        result = scanner.scan(tmp)
        assert result == ""
