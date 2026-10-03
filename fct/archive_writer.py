"""
Archive Writer (Compression Module)
Owner: Adarsh Prakash
Maps to SAD component "Archive Writer". Implements: FCT-F-002, FCT-F-003, FCT-F-004

TODO (Adarsh): implement create_archive() below.

Design notes (see SAD section 4.3):
- Use zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as a context manager.
- For each input path: if it's a file, add it directly; if it's a folder,
  os.walk() it and add every file, using the path *relative to the input
  folder's parent* as the archive name, so directory structure is preserved
  (FCT-F-003).
- Use ZipFile.write(file_path, arcname=...) rather than reading the whole
  file into memory yourself -- zipfile streams internally.
- `overwrite_policy` ("overwrite" | "skip" | "rename") governs what happens
  if output_path already exists -- don't silently clobber it otherwise
  (FCT-SR-005).
- Catch FileNotFoundError / PermissionError for missing or unreadable
  inputs and record them in ArchiveResult.errors rather than crashing.

Suggested test cases (tests/test_archive_writer.py):
- Compress a couple of plain files -> archive contains them, success=True
- Compress a folder with nested subfolders -> structure preserved in the archive
- Empty input list -> raise ValueError (or return success=False, your call --
  just document it)
- Output path already exists, policy="skip" -> no file written, reported in result
"""
from pathlib import Path
from typing import List

from .models import ArchiveResult


def create_archive(
    input_paths: List[Path],
    output_path: Path,
    overwrite_policy: str = "skip",
) -> ArchiveResult:
    """Create a ZIP archive at `output_path` containing all `input_paths`."""
    raise NotImplementedError("TODO (Adarsh): implement ZIP creation, FCT-F-002/003/004")
