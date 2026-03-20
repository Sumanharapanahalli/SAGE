import os
import logging

logger = logging.getLogger(__name__)

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".sage", "dist", "build", ".next"}
_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".class", ".o", ".a", ".so", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".db", ".sqlite", ".lock",
}
_PRIORITY_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".c", ".cpp", ".h", ".md", ".yaml", ".yml", ".json", ".txt", ".rst"}
_MAX_FILE_BYTES = 500 * 1024  # 500KB


def _priority(rel_path: str) -> int:
    """Lower number = higher priority (read first)."""
    lower = rel_path.lower()
    name = os.path.basename(lower)
    if name.startswith("readme"):
        return 0
    parts = lower.replace("\\", "/").split("/")
    if any(p in ("docs", "doc", "documentation") for p in parts):
        return 1
    ext = os.path.splitext(lower)[1]
    if ext in _PRIORITY_EXTENSIONS:
        return 2
    return 3


class FolderScanner:
    def scan(self, folder_path: str, max_tokens: int = 24_000) -> str:
        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        candidates: list[tuple[int, str]] = []
        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in _SKIP_EXTENSIONS:
                    continue
                abs_path = os.path.join(root, fname)
                try:
                    if os.path.getsize(abs_path) > _MAX_FILE_BYTES:
                        logger.debug("Skipping %s — exceeds 500KB size limit", abs_path)
                        continue
                except OSError:
                    continue
                rel_path = os.path.relpath(abs_path, folder_path)
                candidates.append((_priority(rel_path), abs_path))

        candidates.sort(key=lambda x: (x[0], os.path.relpath(x[1], folder_path)))

        budget = max_tokens * 4  # chars
        parts: list[str] = []

        for _, abs_path in candidates:
            if budget <= 0:
                break
            rel_path = os.path.relpath(abs_path, folder_path)
            header = f"# --- {rel_path} ---\n"
            remaining = budget - len(header)
            if remaining <= 0:
                break
            try:
                with open(abs_path, encoding="utf-8", errors="replace") as f:
                    content = f.read(remaining)
            except OSError:
                continue
            if not content.strip():
                continue
            chunk = header + content + "\n"
            parts.append(chunk)
            budget -= len(chunk)

        return "".join(parts)
