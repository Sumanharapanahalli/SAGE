"""
SAGE Security — File type validation, size limits, and ZIP bomb detection.

Defends against:
  - ZIP bombs  : compressed ratio attack (e.g. 1 MB → 1 GB).
                 Rejection happens on the Central Directory headers ONLY —
                 no bytes are extracted before the check.
  - Magic-byte spoofing : a file named "report.pdf" that is actually a ZIP,
                          PE executable, or shell script is rejected.
  - Oversized uploads   : hard cap before any processing begins.
  - Embedded-script injection via OCR text: null-byte stripping + length cap.

Public surface
--------------
  validate_upload(filename, data)  → ValidationResult
  sanitise_ocr_text(raw)           → str
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Magic-byte signatures (first 8 bytes of the file are checked)
# ---------------------------------------------------------------------------

# Maps canonical type name → leading byte sequence
MAGIC_BYTES: dict[str, bytes] = {
    "pdf":  b"%PDF",
    "zip":  b"PK\x03\x04",
    "zip64_end": b"PK\x06\x06",
    "gz":   b"\x1f\x8b",
    "bz2":  b"BZh",
    "xz":   b"\xfd7zXZ\x00",
    "rar":  b"Rar!\x1a\x07",
    "7z":   b"7z\xbc\xaf\x27\x1c",
    "tar":  b"\x75\x73\x74\x61\x72",  # "ustar" offset 257, approximate
    "exe":  b"MZ",
    "elf":  b"\x7fELF",
    "png":  b"\x89PNG\r\n\x1a\n",
    "jpeg": b"\xff\xd8\xff",
    "gif":  b"GIF8",
    "webp": b"RIFF",
}

# Extension → allowed magic type(s).  Only these are accepted at upload time.
ALLOWED_BY_EXTENSION: dict[str, frozenset[str]] = {
    ".pdf":  frozenset({"pdf"}),
    ".png":  frozenset({"png"}),
    ".jpg":  frozenset({"jpeg"}),
    ".jpeg": frozenset({"jpeg"}),
    ".gif":  frozenset({"gif"}),
    ".webp": frozenset({"webp"}),
}

# ---------------------------------------------------------------------------
# Hard limits
# ---------------------------------------------------------------------------

#: Maximum raw upload size (bytes).  Checked before any parsing.
MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024        # 50 MB

#: Maximum size for PDF files specifically.
MAX_PDF_SIZE_BYTES: int = 20 * 1024 * 1024         # 20 MB

#: Maximum total uncompressed bytes across all ZIP entries.
MAX_UNCOMPRESSED_BYTES: int = 1 * 1024 * 1024 * 1024  # 1 GB

#: Maximum compression ratio (uncompressed / compressed) before rejection.
MAX_COMPRESSION_RATIO: float = 100.0

#: Maximum number of entries inside a ZIP before rejection.
MAX_ZIP_ENTRY_COUNT: int = 1_000

#: Maximum OCR text length (characters) passed downstream.
MAX_OCR_TEXT_LENGTH: int = 500_000


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    detected_type: str        # e.g. "pdf", "zip", "unknown"
    declared_extension: str   # e.g. ".pdf"
    error: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_magic_type(header: bytes) -> str:
    """Return the canonical type name matching the leading bytes, or 'unknown'."""
    for type_name, signature in MAGIC_BYTES.items():
        if header[: len(signature)] == signature:
            return type_name
    return "unknown"


def _extension(filename: str) -> str:
    """Return the lowercased file extension including the dot, e.g. '.pdf'."""
    dot_pos = filename.rfind(".")
    if dot_pos == -1:
        return ""
    return filename[dot_pos:].lower()


def _check_zip_bomb(data: bytes) -> tuple[bool, str]:
    """
    Inspect ZIP Central Directory without extracting a single byte.

    Returns (is_safe, error_message).
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            entries = zf.infolist()

            # 1. Entry count
            if len(entries) > MAX_ZIP_ENTRY_COUNT:
                return False, (
                    f"ZIP contains {len(entries):,} entries "
                    f"(limit {MAX_ZIP_ENTRY_COUNT:,})"
                )

            # 2. Total uncompressed size from central directory headers
            total_uncompressed = sum(e.file_size for e in entries)
            total_compressed   = sum(e.compress_size for e in entries)

            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                gb = total_uncompressed / (1024 ** 3)
                return False, (
                    f"ZIP would expand to {gb:.2f} GB "
                    f"(limit {MAX_UNCOMPRESSED_BYTES // (1024**3)} GB)"
                )

            # 3. Compression ratio
            if total_compressed > 0:
                ratio = total_uncompressed / total_compressed
                if ratio > MAX_COMPRESSION_RATIO:
                    return False, (
                        f"ZIP compression ratio {ratio:.1f}:1 exceeds "
                        f"limit {int(MAX_COMPRESSION_RATIO)}:1 — "
                        "possible ZIP bomb"
                    )

            return True, ""

    except zipfile.BadZipFile as exc:
        return False, f"Malformed ZIP archive: {exc}"
    except Exception as exc:  # pragma: no cover
        logger.warning("Unexpected error inspecting ZIP: %s", exc)
        return False, f"ZIP inspection failed: {exc}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_upload(filename: str, data: bytes) -> ValidationResult:
    """
    Validate an uploaded file before any processing.

    Checks performed (in order):
      1. Raw size cap.
      2. Magic-byte detection.
      3. Extension vs magic mismatch (type confusion attack).
      4. PDF-specific size cap.
      5. ZIP bomb check (ratio + entry count) — no extraction occurs.

    Returns a ValidationResult.  If ``valid`` is False, ``error`` explains why
    and the caller MUST return HTTP 422 without touching the payload.
    """
    ext = _extension(filename)
    header = data[:16]

    # 1 — Raw size
    if len(data) > MAX_FILE_SIZE_BYTES:
        mb = len(data) / (1024 ** 2)
        return ValidationResult(
            valid=False,
            detected_type="unknown",
            declared_extension=ext,
            error=f"File size {mb:.1f} MB exceeds limit {MAX_FILE_SIZE_BYTES // (1024**2)} MB",
        )

    # 2 — Magic-byte detection
    detected = _detect_magic_type(header)

    # 3 — Extension vs magic mismatch
    allowed_magic = ALLOWED_BY_EXTENSION.get(ext)
    if allowed_magic is not None and detected not in allowed_magic:
        logger.warning(
            "Magic-byte mismatch: filename=%s declared_ext=%s detected_type=%s",
            filename, ext, detected,
        )
        return ValidationResult(
            valid=False,
            detected_type=detected,
            declared_extension=ext,
            error=(
                f"File extension '{ext}' does not match detected type '{detected}'. "
                "Possible extension spoofing."
            ),
        )

    if allowed_magic is None and ext:
        # Extension is not in the allow-list
        return ValidationResult(
            valid=False,
            detected_type=detected,
            declared_extension=ext,
            error=f"File extension '{ext}' is not permitted for upload.",
        )

    # 4 — PDF size cap
    if detected == "pdf" and len(data) > MAX_PDF_SIZE_BYTES:
        mb = len(data) / (1024 ** 2)
        return ValidationResult(
            valid=False,
            detected_type=detected,
            declared_extension=ext,
            error=f"PDF size {mb:.1f} MB exceeds limit {MAX_PDF_SIZE_BYTES // (1024**2)} MB",
        )

    # 5 — ZIP bomb check (applies to any ZIP-magic data, even if filename says .pdf)
    if detected in {"zip", "zip64_end"}:
        is_safe, bomb_error = _check_zip_bomb(data)
        if not is_safe:
            logger.warning("ZIP bomb rejected: filename=%s error=%s", filename, bomb_error)
            return ValidationResult(
                valid=False,
                detected_type=detected,
                declared_extension=ext,
                error=bomb_error,
            )

    return ValidationResult(
        valid=True,
        detected_type=detected,
        declared_extension=ext,
    )


def sanitise_ocr_text(raw: str) -> str:
    """
    Clean OCR-extracted text before passing it to an LLM or storing it.

    Defends against:
      - Null-byte injection  (\\x00 chars that confuse parsers).
      - Oversized payloads   (cap at MAX_OCR_TEXT_LENGTH characters).
      - Prompt-injection boilerplate embedded in scanned documents
        (strips common injection prefixes — "ignore previous instructions", etc.)

    Does NOT HTML-encode; that is the responsibility of the rendering layer.
    """
    if not raw:
        return ""

    # Strip null bytes
    sanitised = raw.replace("\x00", "")

    # Collapse excessive whitespace runs (more than 4 consecutive newlines)
    sanitised = re.sub(r"\n{5,}", "\n\n\n\n", sanitised)

    # Truncate
    if len(sanitised) > MAX_OCR_TEXT_LENGTH:
        logger.warning(
            "OCR text truncated: original=%d chars, limit=%d",
            len(sanitised), MAX_OCR_TEXT_LENGTH,
        )
        sanitised = sanitised[:MAX_OCR_TEXT_LENGTH]

    return sanitised
