"""
Owner: Abhijna Marathe
Tests for fct.extraction.extract_archive().
Covers: normal extraction, zip-slip rejection, overwrite/skip/rename policies.

NOTE: Since security.resolve_safe_path() is Abhirup's module and may still be
a stub, we mock it here so our tests are self-contained. When Abhirup pushes
his implementation, integration tests in test_cli.py will cover the real wiring.
"""
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch

from fct.extraction import extract_archive
from fct.models import ExtractionResult, PathTraversalError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_zip(zip_path: Path, files: dict[str, bytes]) -> Path:
    """Create a ZIP at `zip_path` with the given {name: content} entries."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return zip_path


def _mock_resolve_safe(entry_name: str, destination: Path) -> Path:
    """A working stand-in for security.resolve_safe_path() that blocks '../'."""
    target = (destination / entry_name).resolve()
    dest_resolved = destination.resolve()
    if not str(target).startswith(str(dest_resolved)):
        raise PathTraversalError(f"Blocked: {entry_name}")
    return target


# ---------------------------------------------------------------------------
# Normal extraction
# ---------------------------------------------------------------------------

@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_valid_archive(mock_sec, tmp_path):
    """Normal extraction of a valid archive -> all files in `extracted`."""
    archive = _make_zip(tmp_path / "test.zip", {
        "hello.txt": b"hello world",
        "subdir/data.bin": b"\x00\x01\x02\x03",
    })
    dest = tmp_path / "out"

    result = extract_archive(archive, dest)

    assert result.success is True
    assert sorted(result.extracted) == ["hello.txt", "subdir/data.bin"]
    assert result.skipped == []
    assert result.failed == []
    assert (dest / "hello.txt").read_bytes() == b"hello world"
    assert (dest / "subdir" / "data.bin").read_bytes() == b"\x00\x01\x02\x03"


@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_preserves_directory_structure(mock_sec, tmp_path):
    """Nested directories are recreated correctly."""
    archive = _make_zip(tmp_path / "nested.zip", {
        "a/b/c/deep.txt": b"deep file",
    })
    dest = tmp_path / "out"

    result = extract_archive(archive, dest)

    assert result.success is True
    assert (dest / "a" / "b" / "c" / "deep.txt").read_bytes() == b"deep file"


@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_empty_archive(mock_sec, tmp_path):
    """Extracting an empty archive succeeds with nothing extracted."""
    archive = _make_zip(tmp_path / "empty.zip", {})
    dest = tmp_path / "out"

    result = extract_archive(archive, dest)

    assert result.success is True
    assert result.extracted == []


# ---------------------------------------------------------------------------
# Zip-slip / path traversal
# ---------------------------------------------------------------------------

@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_zipslip_blocked(mock_sec, tmp_path):
    """Archive with a '../' entry -> that entry lands in `failed`, nothing written outside dest."""
    archive = _make_zip(tmp_path / "evil.zip", {
        "good.txt": b"safe",
        "../../etc/passwd": b"malicious",
    })
    dest = tmp_path / "out"

    result = extract_archive(archive, dest)

    assert "../../etc/passwd" in result.failed
    assert "good.txt" in result.extracted
    # The malicious file must NOT exist outside dest
    assert not (tmp_path / "etc" / "passwd").exists()


# ---------------------------------------------------------------------------
# Overwrite policies (FCT-F-011 / FCT-SR-005)
# ---------------------------------------------------------------------------

@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_policy_skip(mock_sec, tmp_path):
    """policy='skip' -> existing file left alone, reported in `skipped`."""
    archive = _make_zip(tmp_path / "dup.zip", {"file.txt": b"new content"})
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "file.txt").write_bytes(b"old content")

    result = extract_archive(archive, dest, overwrite_policy="skip")

    assert "file.txt" in result.skipped
    assert (dest / "file.txt").read_bytes() == b"old content"


@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_policy_overwrite(mock_sec, tmp_path):
    """policy='overwrite' -> existing file replaced."""
    archive = _make_zip(tmp_path / "dup.zip", {"file.txt": b"new content"})
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "file.txt").write_bytes(b"old content")

    result = extract_archive(archive, dest, overwrite_policy="overwrite")

    assert "file.txt" in result.extracted
    assert (dest / "file.txt").read_bytes() == b"new content"


@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_policy_rename(mock_sec, tmp_path):
    """policy='rename' -> new file gets a (1) suffix, original untouched."""
    archive = _make_zip(tmp_path / "dup.zip", {"file.txt": b"new content"})
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "file.txt").write_bytes(b"old content")

    result = extract_archive(archive, dest, overwrite_policy="rename")

    assert "file.txt" in result.extracted
    assert (dest / "file.txt").read_bytes() == b"old content"
    assert (dest / "file (1).txt").read_bytes() == b"new content"


# ---------------------------------------------------------------------------
# Bad archive
# ---------------------------------------------------------------------------

def test_extract_invalid_zip(tmp_path):
    """Corrupted/non-zip file -> ExtractionResult with success=False."""
    bad_file = tmp_path / "not_a_zip.zip"
    bad_file.write_bytes(b"this is not a zip file at all")
    dest = tmp_path / "out"

    result = extract_archive(bad_file, dest)

    assert result.success is False


# ---------------------------------------------------------------------------
# Integrity failure tests (CRC & SHA-256)
# ---------------------------------------------------------------------------

@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_integrity_failure_corrupted_crc(mock_sec, tmp_path):
    """Archive with corrupted payload -> CRC check fails, file placed in failed, cleaned up."""
    zip_path = tmp_path / "crc_corrupt.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("good.txt", b"good payload")
        zf.writestr("corrupted.txt", b"corrupted payload data")

    # Corrupt the raw payload byte of corrupted.txt
    raw = bytearray(zip_path.read_bytes())
    idx = raw.find(b"corrupted payload")
    assert idx != -1
    raw[idx] = ord("X")
    zip_path.write_bytes(raw)

    dest = tmp_path / "out"
    result = extract_archive(zip_path, dest)

    assert result.success is False
    assert "good.txt" in result.extracted
    assert "corrupted.txt" in result.failed
    assert not (dest / "corrupted.txt").exists()


@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_integrity_failure_sha256_mismatch(mock_sec, tmp_path):
    """When expected_hashes does not match, entry lands in failed and is cleaned up."""
    archive = _make_zip(tmp_path / "test.zip", {"data.txt": b"original content"})
    dest = tmp_path / "out"

    # Provide an incorrect hash
    bad_hashes = {"data.txt": "0" * 64}
    result = extract_archive(archive, dest, expected_hashes=bad_hashes)

    assert result.success is False
    assert "data.txt" in result.failed
    assert "data.txt" not in result.extracted
    assert not (dest / "data.txt").exists()


@patch("fct.extraction.resolve_safe_path", side_effect=_mock_resolve_safe)
def test_extract_integrity_sha256_matching(mock_sec, tmp_path):
    """When expected_hashes matches actual SHA-256, extraction succeeds."""
    import hashlib
    archive = _make_zip(tmp_path / "test.zip", {"data.txt": b"original content"})
    dest = tmp_path / "out"

    good_hash = hashlib.sha256(b"original content").hexdigest()
    result = extract_archive(archive, dest, expected_hashes={"data.txt": good_hash})

    assert result.success is True
    assert "data.txt" in result.extracted
    assert (dest / "data.txt").read_bytes() == b"original content"

