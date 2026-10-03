"""
Path / Security Validator
Owner: Abhirup Roy
Maps to SAD component "Path/Security Validator" (security module).
Implements: FCT-SR-001 (path traversal protection)

TODO (Abhirup): implement resolve_safe_path() below.

Design notes (see SAD section 3.9 / 4.2 Sequence Diagram 2):
- Every entry name read from a ZIP archive must be resolved against the
  destination directory.
- If the resolved absolute path is NOT inside the destination directory,
  raise PathTraversalError -- do not write the file.
- Watch out for entries like "../../etc/passwd", absolute paths, and
  Windows drive-letter tricks (e.g. "C:\\Windows\\System32\\...").
- pathlib.Path.resolve() + checking the destination is a parent of the
  resolved path is the standard approach.

Suggested test cases (tests/test_security.py):
- A normal relative entry name -> returns the safe resolved path
- An entry with "../" that would escape the destination -> raises PathTraversalError
- An absolute path entry -> raises PathTraversalError
- A nested-but-safe entry ("subdir/file.txt") -> returns the safe resolved path
"""
from pathlib import Path

from .models import PathTraversalError


def resolve_safe_path(entry_name: str, destination: Path) -> Path:
    """
    Resolve `entry_name` (a path as stored inside the ZIP archive) against
    `destination`, and return the safe absolute path to extract it to.

    Raises:
        PathTraversalError: if the resolved path would fall outside `destination`.
    """
    raise NotImplementedError("TODO (Abhirup): implement path traversal protection, FCT-SR-001")
