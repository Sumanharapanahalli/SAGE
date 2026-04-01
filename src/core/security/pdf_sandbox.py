"""
SAGE Security — Sandboxed PDF text extraction.

Runs PDF parsing in an isolated child process with:
  - Wall-clock timeout  (default 30 s)
  - RSS memory cap      (default 256 MB, Linux only via resource module)
  - No network access   (the child inherits no sockets and makes no calls)

If the child exceeds its limits or crashes, the parent receives a structured
error dict and the document is rejected — the host process is never affected.

Usage
-----
    from src.core.security.pdf_sandbox import extract_pdf_text_safe

    result = extract_pdf_text_safe(pdf_bytes)
    if result["ok"]:
        text = result["text"]
    else:
        raise ValueError(result["error"])

Dependencies
------------
    pip install pypdf          # pure-Python PDF parser (no native libs needed)
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import queue
import sys
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

#: Maximum RSS memory the child process may consume (bytes).  Linux only.
_MAX_RSS_BYTES: int = 256 * 1024 * 1024   # 256 MB

#: Wall-clock seconds before the child is killed.
_TIMEOUT_SECONDS: int = 30

#: Maximum pages extracted per document (defence against very large PDFs).
_MAX_PAGES: int = 500


# ---------------------------------------------------------------------------
# Child-process worker
# ---------------------------------------------------------------------------

def _pdf_worker(pdf_bytes: bytes, result_queue: "multiprocessing.Queue[dict[str, Any]]") -> None:
    """
    Runs inside an isolated child process.
    Applies an RSS memory cap on Linux, then extracts text with pypdf.
    Sends a single dict to result_queue and exits.
    """
    # Apply RSS cap on Linux
    if sys.platform.startswith("linux"):
        try:
            import resource
            resource.setrlimit(
                resource.RLIMIT_AS,
                (_MAX_RSS_BYTES, _MAX_RSS_BYTES),
            )
        except Exception as exc:  # pragma: no cover
            # Non-fatal: log and continue without the cap
            logger.warning("Could not set RSS limit in PDF worker: %s", exc)

    try:
        import io
        from pypdf import PdfReader  # type: ignore[import]

        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages_to_read = min(len(reader.pages), _MAX_PAGES)
        parts: list[str] = []
        for i in range(pages_to_read):
            text = reader.pages[i].extract_text() or ""
            parts.append(text)

        result_queue.put({
            "ok": True,
            "text": "\n".join(parts),
            "page_count": len(reader.pages),
            "pages_read": pages_to_read,
        })
    except MemoryError:
        result_queue.put({"ok": False, "error": "PDF extraction exceeded memory limit"})
    except Exception as exc:
        result_queue.put({"ok": False, "error": f"PDF parse error: {exc}"})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_pdf_text_safe(pdf_bytes: bytes) -> dict[str, Any]:
    """
    Extract text from a PDF in a sandboxed child process.

    Returns a dict:
      - ``{"ok": True, "text": str, "page_count": int, "pages_read": int}``
        on success.
      - ``{"ok": False, "error": str}`` on any failure (timeout, crash, OOM,
        parse error).

    The caller receives the result regardless of what happens inside the child.
    """
    ctx = multiprocessing.get_context("spawn")   # spawn > fork for isolation
    result_queue: "multiprocessing.Queue[dict[str, Any]]" = ctx.Queue(maxsize=1)

    proc = ctx.Process(
        target=_pdf_worker,
        args=(pdf_bytes, result_queue),
        daemon=True,
    )
    proc.start()
    proc.join(timeout=_TIMEOUT_SECONDS)

    if proc.is_alive():
        proc.kill()
        proc.join()
        logger.warning("PDF worker timed out after %d s — document rejected", _TIMEOUT_SECONDS)
        return {"ok": False, "error": f"PDF extraction timed out ({_TIMEOUT_SECONDS} s)"}

    if proc.exitcode != 0:
        logger.warning("PDF worker exited with code %d", proc.exitcode)
        return {"ok": False, "error": f"PDF worker crashed (exit code {proc.exitcode})"}

    try:
        result: dict[str, Any] = result_queue.get_nowait()
    except Exception:
        return {"ok": False, "error": "PDF worker produced no result"}

    return result
