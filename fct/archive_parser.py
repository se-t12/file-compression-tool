"""
Archive Parser / Archive Inspector

Owner: Abhirup Roy
Maps to SAD component "Archive Parser". Implements: FCT-F-009, FCT-F-010, FCT-SR-002
"""

import zipfile
from pathlib import Path
from typing import List

from .models import EntryInfo, ValidationResult


def validate_archive(archive_path: Path) -> ValidationResult:
    """Check that `archive_path` is a structurally valid ZIP archive."""
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            bad_file = archive.testzip()

            if bad_file is not None:
                return ValidationResult(
                    ok=False,
                    reason=f"Corrupted file in archive: {bad_file}",
                )

            entries = list_entries(archive_path)

            return ValidationResult(
                ok=True,
                reason="Archive is valid",
                entries=entries,
            )

    except (zipfile.BadZipFile, OSError) as exc:
        return ValidationResult(
            ok=False,
            reason=f"Invalid archive: {exc}",
        )


def list_entries(archive_path: Path) -> List[EntryInfo]:
    """Return metadata for every entry in the archive, without extracting."""
    with zipfile.ZipFile(archive_path, "r") as archive:
        return [
            EntryInfo(
                name=info.filename,
                size=info.file_size,
                compressed_size=info.compress_size,
                is_dir=info.is_dir(),
            )
            for info in archive.infolist()
        ]