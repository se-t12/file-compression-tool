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
import os
import zipfile
from pathlib import Path
from typing import List

from .models import ArchiveResult


def create_archive(
    input_paths: List[Path],
    output_path: Path,
    overwrite_policy: str = "skip",
) -> ArchiveResult:
    """Create a ZIP archive at ``output_path`` containing all ``input_paths``.

    Parameters
    ----------
    input_paths:
        Files and/or directories to compress. Directories are walked
        recursively; the archive preserves the structure relative to each
        directory's *parent* (FCT-F-003).
    output_path:
        Destination ``.zip`` path.
    overwrite_policy:
        ``"overwrite"`` – replace an existing file silently.
        ``"skip"``      – leave the existing file untouched and return
                          ``success=False`` (FCT-SR-005, default).
        ``"rename"``    – append ``_1``, ``_2``, … to the stem until a
                          free name is found, then write there.

    Returns
    -------
    ArchiveResult
        ``success=True`` when at least one entry was written without a
        fatal error.  Per-file I/O errors are recorded in ``.errors``
        instead of propagating (FCT-F-004).

    Raises
    ------
    ValueError
        When ``input_paths`` is empty or ``overwrite_policy`` is unknown.
    """
    if not input_paths:
        raise ValueError("input_paths must not be empty")

    valid_policies = {"overwrite", "skip", "rename"}
    if overwrite_policy not in valid_policies:
        raise ValueError(
            f"overwrite_policy must be one of {valid_policies}, got {overwrite_policy!r}"
        )

    output_path = Path(output_path)

    # ------------------------------------------------------------------ #
    # Overwrite-policy gate (FCT-SR-005)                                   #
    # ------------------------------------------------------------------ #
    if output_path.exists():
        if overwrite_policy == "skip":
            return ArchiveResult(
                success=False,
                entries_written=0,
                output_path=output_path,
                errors=[f"Output already exists and policy is 'skip': {output_path}"],
            )
        elif overwrite_policy == "rename":
            stem = output_path.stem
            suffix = output_path.suffix
            parent = output_path.parent
            counter = 1
            while output_path.exists():
                output_path = parent / f"{stem}_{counter}{suffix}"
                counter += 1
        # "overwrite" → fall through and let ZipFile clobber it

    errors: List[str] = []
    entries_written = 0

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for input_path in input_paths:
            input_path = Path(input_path)

            if input_path.is_file():
                # Single file: archive name is just the file's own name.
                try:
                    zf.write(input_path, arcname=input_path.name)
                    entries_written += 1
                except FileNotFoundError:
                    errors.append(f"File not found: {input_path}")
                except PermissionError:
                    errors.append(f"Permission denied: {input_path}")

            elif input_path.is_dir():
                # Directory: walk and preserve structure relative to the
                # directory's *parent* (FCT-F-003).
                parent = input_path.parent
                for dirpath, _dirnames, filenames in os.walk(input_path):
                    for filename in filenames:
                        file_abs = Path(dirpath) / filename
                        arcname = str(file_abs.relative_to(parent))
                        try:
                            zf.write(file_abs, arcname=arcname)
                            entries_written += 1
                        except FileNotFoundError:
                            errors.append(f"File not found: {file_abs}")
                        except PermissionError:
                            errors.append(f"Permission denied: {file_abs}")

            else:
                errors.append(f"Path not found or not accessible: {input_path}")

    return ArchiveResult(
        success=entries_written > 0,
        entries_written=entries_written,
        output_path=output_path,
        errors=errors,
    )
