"""
Extraction Module
Owner: Abhijna Marathe
Maps to SAD component "Extraction Module". Implements: FCT-F-007, FCT-F-011, FCT-SR-005

Design notes (see SAD section 4.2 Sequence Diagram 2):
- For each entry in the archive: call security.resolve_safe_path(entry.name,
  destination) BEFORE writing anything. If it raises PathTraversalError,
  record the entry in `failed` and skip it.
- Apply `overwrite_policy` when the target file already exists on disk:
  "overwrite" -> write over it, "skip" -> leave existing file, add to
  `skipped`, "rename" -> write to a new name like "file (1).txt".
- After writing, call integrity.verify_entry() and only count the file as
  `extracted` if the CRC from zipfile doesn't flag an error.
- Call resource_manager.cleanup_temp() at the end, even on failure
  (try/finally).
"""
import logging
import zipfile
from pathlib import Path

from .models import ExtractionResult, PathTraversalError
from . import integrity
from . import resource_manager
from .security import resolve_safe_path

logger = logging.getLogger("fct.extraction")

# Buffer size for streaming extraction (FCT-NF-002: stay under 512 MB)
_EXTRACT_BUF = 1 << 22  # 4 MB


def _find_rename(target: Path) -> Path:
    """Return a non-colliding path like 'file (1).txt', 'file (2).txt', etc."""
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def extract_archive(
    archive_path: Path,
    destination: Path,
    overwrite_policy: str = "skip",
    expected_hashes: dict[str, str] | None = None,
) -> ExtractionResult:
    """Extract all entries from `archive_path` into `destination`.

    Args:
        archive_path: Path to the ZIP file to extract.
        destination: Directory to extract files into.
        overwrite_policy: One of "overwrite", "skip", or "rename".
        expected_hashes: Optional mapping of entry name to expected SHA-256 hex digest.

    Returns:
        ExtractionResult with lists of extracted, skipped, and failed entries.
    """
    extracted: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    temp_files: list[Path] = []

    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            # Quick CRC integrity check on the whole archive first
            bad = zf.testzip()
            if bad is not None:
                logger.warning("CRC check failed for entry: %s", bad)

            for info in zf.infolist():
                entry_name = info.filename

                # Skip directory entries — they get created implicitly
                if info.is_dir():
                    continue

                # --- Security: path-traversal check (FCT-SR-001) ---
                try:
                    target = resolve_safe_path(entry_name, destination)
                except PathTraversalError:
                    logger.warning("Path traversal blocked: %s", entry_name)
                    failed.append(entry_name)
                    continue

                # --- Overwrite policy (FCT-F-011 / FCT-SR-005) ---
                if target.exists():
                    if overwrite_policy == "skip":
                        skipped.append(entry_name)
                        continue
                    elif overwrite_policy == "rename":
                        target = _find_rename(target)
                    # "overwrite" falls through and writes over the file

                # --- Extract the entry via buffered streaming ---
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with zf.open(info) as src, open(target, "wb") as dst:
                        while True:
                            chunk = src.read(_EXTRACT_BUF)
                            if not chunk:
                                break
                            dst.write(chunk)
                except Exception as exc:
                    logger.error("Failed to extract %s: %s", entry_name, exc)
                    failed.append(entry_name)
                    # Track partial file for cleanup
                    if target.exists():
                        temp_files.append(target)
                    continue

                # --- Integrity verification: SHA-256 (FCT-NF-004) ---
                if expected_hashes and entry_name in expected_hashes:
                    if not integrity.verify_entry(target, expected_hashes[entry_name]):
                        logger.error("Integrity check failed for %s", entry_name)
                        failed.append(entry_name)
                        if target.exists():
                            temp_files.append(target)
                        continue

                extracted.append(entry_name)

    except zipfile.BadZipFile as exc:
        logger.error("Invalid ZIP archive %s: %s", archive_path, exc)
        return ExtractionResult(
            success=False,
            extracted=extracted,
            skipped=skipped,
            failed=[str(exc)],
        )
    finally:
        # FCT-F-014: always clean up temp resources
        resource_manager.cleanup_temp(temp_files)

    success = len(failed) == 0
    return ExtractionResult(
        success=success,
        extracted=extracted,
        skipped=skipped,
        failed=failed,
    )
