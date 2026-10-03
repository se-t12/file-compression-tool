from pathlib import Path

from fct.models import ArchiveResult, EntryInfo, ExtractionResult, ValidationResult


def test_archive_result_defaults():
    result = ArchiveResult(success=True, entries_written=3, output_path=Path("out.zip"))
    assert result.errors == []


def test_extraction_result_defaults():
    result = ExtractionResult(success=True)
    assert result.extracted == []
    assert result.skipped == []
    assert result.failed == []


def test_entry_info_fields():
    entry = EntryInfo(name="a.txt", size=10, compressed_size=8, is_dir=False)
    assert entry.name == "a.txt"
    assert entry.is_dir is False


def test_validation_result_defaults():
    result = ValidationResult(ok=True)
    assert result.reason == ""
    assert result.entries == []
