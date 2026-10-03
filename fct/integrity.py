"""
Integrity Module
Owner: Abhijna Marathe
Maps to SAD component "Integrity Module". Implements: FCT-F-012, FCT-NF-004, FCT-SR-003

TODO (Abhijna): implement compute_sha256() and verify_entry() below.

Design notes:
- compute_sha256() should read the file in chunks (e.g. 64KB at a time),
  not load the whole file into memory -- important for large files
  (FCT-NF-002).
- ZIP entries already carry a CRC-32 checksum (zipfile.ZipInfo.CRC) that
  zipfile verifies automatically on extraction/testzip() -- you can lean on
  that for a cheap first check, and use SHA-256 for the stronger
  round-trip guarantee the SRS asks for (FCT-NF-004).
- verify_entry() is meant to be called by the Extraction Module right after
  a file is written, to confirm the extracted file's hash matches what was
  recorded when the archive was created.

Suggested test cases (tests/test_integrity.py):
- Hash of a known small file matches Python's hashlib computed the "obvious" way
- Two different files produce different hashes
- verify_entry() returns True for a matching file, False for a tampered one
"""
import hashlib
from pathlib import Path


def compute_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Return the hex-encoded SHA-256 digest of the file at `path`."""
    raise NotImplementedError("TODO (Abhijna): implement streamed SHA-256 hashing, FCT-NF-004")


def verify_entry(path: Path, expected_sha256: str) -> bool:
    """Return True if the file at `path` matches `expected_sha256`."""
    raise NotImplementedError("TODO (Abhijna): implement integrity verification, FCT-F-012 / FCT-SR-003")
