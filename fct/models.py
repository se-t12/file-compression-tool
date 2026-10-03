"""
Shared data models and exceptions used across all File Compression Tool modules.

These types are the "contract" between modules, matching the interfaces
defined in the Software Architecture and Design Specification (SAD), section 4.3.
Please don't change a field name/type without pinging the group first --
other people's modules depend on these shapes.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PathTraversalError(Exception):
    """Raised when an archive entry would resolve outside the destination
    directory (the "zip-slip" attack). Maps to FCT-SR-001."""


class ArchiveValidationError(Exception):
    """Raised when an archive is malformed, corrupted, or otherwise fails
    structural validation. Maps to FCT-F-009 / FCT-SR-002."""


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class ArchiveResult:
    """Returned by archive_writer.create_archive(). Maps to FCT-F-002..005."""
    success: bool
    entries_written: int
    output_path: Path
    errors: List[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Returned by extraction.extract_archive(). Maps to FCT-F-007, FCT-F-011."""
    success: bool
    extracted: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)


@dataclass
class EntryInfo:
    """One entry inside a ZIP archive, as reported by archive_parser.list_entries().
    Maps to FCT-F-010."""
    name: str
    size: int
    compressed_size: int
    is_dir: bool


@dataclass
class ValidationResult:
    """Returned by archive_parser.validate_archive(). Maps to FCT-F-009, FCT-SR-002."""
    ok: bool
    reason: str = ""
    entries: List[EntryInfo] = field(default_factory=list)
