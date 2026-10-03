"""
Command Orchestrator
Owner: Aakash Agarwal
Maps to SAD component "Command Orchestrator" -- sequences calls between
modules for each CLI command. See SAD sections 4.1 and 4.2 (sequence diagrams).

This module deliberately contains no business logic of its own: it just
calls the right functions in the right order and turns their results into
plain-text summaries for the CLI to print. Once everyone's stubs are filled
in, these functions should work end-to-end without changes here.
"""
import logging
from pathlib import Path
from typing import List

from . import archive_parser, archive_writer, extraction, resource_manager
from .models import ArchiveValidationError

logger = logging.getLogger("fct.orchestrator")


def compress_command(input_paths: List[Path], output_path: Path, overwrite_policy: str) -> int:
    """Run the compress flow (SAD Sequence Diagram 1). Returns a process exit code."""
    result = archive_writer.create_archive(input_paths, output_path, overwrite_policy)
    logger.info("operation=compress path=%s result=%s", output_path, "success" if result.success else "failed")

    if result.success:
        print(f"Created '{result.output_path}' with {result.entries_written} entries.")
        return 0

    print(f"Compression failed for '{output_path}':")
    for err in result.errors:
        print(f"  - {err}")
    return 1


def extract_command(archive_path: Path, destination: Path, overwrite_policy: str) -> int:
    """Run the extract flow (SAD Sequence Diagram 2). Returns a process exit code."""
    validation = archive_parser.validate_archive(archive_path)
    if not validation.ok:
        print(f"Extract failed: '{archive_path}' is not a valid archive ({validation.reason}).")
        logger.info("operation=extract path=%s result=rejected: %s", archive_path, validation.reason)
        return 1

    result = extraction.extract_archive(archive_path, destination, overwrite_policy)
    logger.info("operation=extract path=%s result=%s", archive_path, "success" if result.success else "failed")

    print(f"Extracted {len(result.extracted)} file(s) to '{destination}'.")
    if result.skipped:
        print(f"Skipped {len(result.skipped)} file(s) (already exist): {', '.join(result.skipped)}")
    if result.failed:
        print(f"Failed {len(result.failed)} file(s): {', '.join(result.failed)}")
        return 1
    return 0


def list_command(archive_path: Path) -> int:
    """Run the list flow. Validates first, then prints entry metadata."""
    validation = archive_parser.validate_archive(archive_path)
    if not validation.ok:
        print(f"List failed: '{archive_path}' is not a valid archive ({validation.reason}).")
        return 1

    entries = archive_parser.list_entries(archive_path)
    for entry in entries:
        kind = "DIR " if entry.is_dir else "FILE"
        print(f"{kind}  {entry.size:>10} bytes  {entry.name}")
    return 0
