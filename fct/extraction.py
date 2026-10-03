"""
Extraction Module
Owner: Abhijna Marathe
Maps to SAD component "Extraction Module". Implements: FCT-F-007, FCT-F-011, FCT-SR-005

TODO (Abhijna): implement extract_archive() below.

Design notes (see SAD section 4.2 Sequence Diagram 2):
- For each entry in the archive (use archive_parser.list_entries() or
  zipfile directly): call security.resolve_safe_path(entry.name, destination)
  BEFORE writing anything. If it raises PathTraversalError, record the entry
  in `failed` and skip it -- do not let the exception kill the whole
  extraction.
- Apply `overwrite_policy` when the target file already exists on disk:
  "overwrite" -> write over it, "skip" -> leave existing file, add to
  `skipped`, "rename" -> write to a new name like "file (1).txt".
- After writing, call integrity.verify_entry(...) (Abhijna is also doing
  the Integrity Module, so this wires together naturally) and only count
  the file as `extracted` if it passes.
- Call resource_manager.cleanup_temp() at the end, even on failure (consider
  try/finally).

Suggested test cases (tests/test_extraction.py):
- Normal extraction of a valid archive -> all files in `extracted`
- Archive containing a zip-slip entry -> that entry ends up in `failed`,
  nothing is written outside the destination
- Duplicate filename at destination with policy="skip" -> file left alone,
  reported in `skipped`
"""
from pathlib import Path

from .models import ExtractionResult


def extract_archive(
    archive_path: Path,
    destination: Path,
    overwrite_policy: str = "skip",
) -> ExtractionResult:
    """Extract all entries from `archive_path` into `destination`."""
    raise NotImplementedError("TODO (Abhijna): implement extraction, FCT-F-007/011")
