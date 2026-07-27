"""Tests for src.core.security.file_validator — upload validation & OCR sanitising.

Security-critical, previously untested (SAGE self-improvement loop, issue #23).
"""

import io
import zipfile

from src.core.security.file_validator import (
    MAX_FILE_SIZE_BYTES,
    MAX_OCR_TEXT_LENGTH,
    _check_zip_bomb,
    _detect_magic_type,
    _extension,
    sanitise_ocr_text,
    validate_upload,
)


# --- helpers ---------------------------------------------------------------


def test_detect_magic_type_known_and_unknown():
    assert _detect_magic_type(b"%PDF-1.7") == "pdf"
    assert _detect_magic_type(b"PK\x03\x04rest") == "zip"
    assert _detect_magic_type(b"\x89PNG\r\n\x1a\n") == "png"
    assert _detect_magic_type(b"nope") == "unknown"


def test_extension_lowercased_with_dot():
    assert _extension("Report.PDF") == ".pdf"
    assert _extension("archive.tar.gz") == ".gz"
    assert _extension("noext") == ""


# --- validate_upload -------------------------------------------------------


def test_valid_pdf_passes():
    r = validate_upload("doc.pdf", b"%PDF-1.5\n%rest of pdf")
    assert r.valid and r.detected_type == "pdf"


def test_valid_png_passes():
    r = validate_upload("img.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    assert r.valid and r.detected_type == "png"


def test_extension_magic_mismatch_is_rejected():
    # A ZIP masquerading as a PDF (extension spoofing).
    r = validate_upload("evil.pdf", b"PK\x03\x04" + b"\x00" * 20)
    assert not r.valid
    assert "does not match" in r.error


def test_disallowed_extension_is_rejected():
    r = validate_upload("payload.exe", b"MZ" + b"\x00" * 20)
    assert not r.valid
    assert "not permitted" in r.error


def test_oversized_file_is_rejected_before_parsing():
    big = b"%PDF" + b"\x00" * (MAX_FILE_SIZE_BYTES + 1)
    r = validate_upload("huge.pdf", big)
    assert not r.valid
    assert "exceeds limit" in r.error


# --- zip bomb --------------------------------------------------------------


def _make_zip(payload: bytes, name: str = "a.bin") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, payload)
    return buf.getvalue()


def test_check_zip_bomb_rejects_high_ratio():
    # 4 MB of zeros compresses to a few KB → ratio well over the 100:1 cap.
    bomb = _make_zip(b"\x00" * (4 * 1024 * 1024))
    is_safe, err = _check_zip_bomb(bomb)
    assert not is_safe
    assert "ratio" in err.lower() or "bomb" in err.lower()


def test_check_zip_bomb_accepts_normal_archive():
    normal = _make_zip(b"hello world, not a bomb")
    is_safe, err = _check_zip_bomb(normal)
    assert is_safe and err == ""


def test_check_zip_bomb_rejects_malformed():
    is_safe, err = _check_zip_bomb(b"PK\x03\x04 not really a zip")
    assert not is_safe


# --- sanitise_ocr_text -----------------------------------------------------


def test_sanitise_strips_null_bytes():
    assert "\x00" not in sanitise_ocr_text("a\x00b\x00c")
    assert sanitise_ocr_text("a\x00b") == "ab"


def test_sanitise_empty_returns_empty():
    assert sanitise_ocr_text("") == ""


def test_sanitise_truncates_to_cap():
    out = sanitise_ocr_text("x" * (MAX_OCR_TEXT_LENGTH + 100))
    assert len(out) == MAX_OCR_TEXT_LENGTH


def test_sanitise_collapses_excessive_newlines():
    out = sanitise_ocr_text("a" + "\n" * 10 + "b")
    assert "\n" * 5 not in out
