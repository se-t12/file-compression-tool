"""
Owner: Abhijna Marathe
Tests for fct.integrity (compute_sha256, verify_entry).
"""
import hashlib
import pytest
from pathlib import Path

from fct.integrity import compute_sha256, verify_entry


# ---- compute_sha256 tests ----

def test_sha256_known_content(tmp_path):
    """Hash of a known small file matches Python's hashlib computed the obvious way."""
    f = tmp_path / "hello.txt"
    content = b"hello world\n"
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert compute_sha256(f) == expected


def test_sha256_empty_file(tmp_path):
    """Empty file produces the well-known SHA-256 of empty bytes."""
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")

    expected = hashlib.sha256(b"").hexdigest()
    assert compute_sha256(f) == expected


def test_sha256_binary_file(tmp_path):
    """Binary content (non-UTF-8 bytes) is hashed correctly."""
    f = tmp_path / "binary.bin"
    content = bytes(range(256)) * 100  # 25.6 KB of binary data
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert compute_sha256(f) == expected


def test_sha256_two_different_files(tmp_path):
    """Two different files produce different hashes."""
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_bytes(b"file one")
    f2.write_bytes(b"file two")

    assert compute_sha256(f1) != compute_sha256(f2)


def test_sha256_large_file_chunked(tmp_path):
    """Large file (>1 chunk) produces the correct hash, proving chunked reading works."""
    f = tmp_path / "large.bin"
    # 256 KB -- larger than the default 64 KB chunk size
    content = b"A" * (256 * 1024)
    f.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert compute_sha256(f) == expected


def test_sha256_custom_chunk_size(tmp_path):
    """Result is the same regardless of chunk size."""
    f = tmp_path / "data.txt"
    content = b"the quick brown fox jumps over the lazy dog"
    f.write_bytes(content)

    assert compute_sha256(f, chunk_size=8) == compute_sha256(f, chunk_size=65536)


# ---- verify_entry tests ----

def test_verify_entry_matching(tmp_path):
    """verify_entry returns True for a file whose hash matches."""
    f = tmp_path / "match.txt"
    content = b"correct content"
    f.write_bytes(content)

    sha = hashlib.sha256(content).hexdigest()
    assert verify_entry(f, sha) is True


def test_verify_entry_tampered(tmp_path):
    """verify_entry returns False for a tampered file."""
    f = tmp_path / "tampered.txt"
    f.write_bytes(b"original content")

    # Provide the hash of different content
    wrong_sha = hashlib.sha256(b"different content").hexdigest()
    assert verify_entry(f, wrong_sha) is False


def test_verify_entry_wrong_hash_format(tmp_path):
    """verify_entry returns False if the expected hash is garbage."""
    f = tmp_path / "file.txt"
    f.write_bytes(b"some data")

    assert verify_entry(f, "not_a_real_hash") is False
