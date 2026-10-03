"""
Archive Parser / Archive Inspector
Owner: Abhirup Roy
Maps to SAD component "Archive Parser". Implements: FCT-F-009, FCT-F-010, FCT-SR-002

TODO (Abhirup): implement validate_archive() and list_entries() below.

Design notes:
- Use Python's zipfile module. zipfile.ZipFile(path).testzip() returns the
  name of the first bad file, or None if the archive is OK -- useful for
  validate_archive().
- Wrap file open/parse errors (zipfile.BadZipFile, OSError) and convert them
  into a ValidationResult(ok=False, reason=...) rather than letting them
  propagate as raw exceptions -- see FCT-NF-003 (clear error messages).
- list_entries() should NOT extract anything, just read metadata
  (zipfile.ZipFile.infolist() gives you name, file_size, compress_size, is_dir()).

Suggested test cases (tests/test_archive_parser.py):
- A valid archive -> validate_archive returns ok=True, list_entries returns
  the right EntryInfo list
- A corrupted/truncated zip file -> validate_archive returns ok=False with a
  reason, does not raise
- An empty archive -> list_entries returns []
"""
from pathlib import Path
from typing import List

from .models import EntryInfo, ValidationResult


def validate_archive(archive_path: Path) -> ValidationResult:
    """Check that `archive_path` is a structurally valid ZIP archive."""
    raise NotImplementedError("TODO (Abhirup): implement archive validation, FCT-F-009 / FCT-SR-002")


def list_entries(archive_path: Path) -> List[EntryInfo]:
    """Return metadata for every entry in the archive, without extracting."""
    raise NotImplementedError("TODO (Abhirup): implement entry listing, FCT-F-010")
