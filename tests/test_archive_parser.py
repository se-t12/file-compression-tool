"""
Tests for the Archive Parser / Archive Inspector.

Owner: Abhirup Roy
Tests FCT-F-009, FCT-F-010 and FCT-SR-002.
"""

import zipfile
from pathlib import Path

from fct.archive_parser import validate_archive, list_entries


def test_valid_archive(tmp_path: Path):
    archive_path = tmp_path / "test.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("hello.txt", "Hello world")
        archive.writestr("folder/data.txt", "Some data")

    result = validate_archive(archive_path)

    assert result.ok is True
    assert result.reason == "Archive is valid"
    assert len(result.entries) == 2


def test_list_entries_returns_correct_metadata(tmp_path: Path):
    archive_path = tmp_path / "test.zip"

    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("hello.txt", "Hello world")
        archive.writestr("folder/data.txt", "Some data")

    entries = list_entries(archive_path)

    assert len(entries) == 2

    names = {entry.name for entry in entries}

    assert "hello.txt" in names
    assert "folder/data.txt" in names

    hello_entry = next(
        entry for entry in entries if entry.name == "hello.txt"
    )

    assert hello_entry.size == len("Hello world".encode())
    assert hello_entry.is_dir is False


def test_corrupted_archive(tmp_path: Path):
    archive_path = tmp_path / "corrupted.zip"

    archive_path.write_bytes(b"This is not a valid ZIP file")

    result = validate_archive(archive_path)

    assert result.ok is False
    assert result.reason != ""


def test_empty_archive(tmp_path: Path):
    archive_path = tmp_path / "empty.zip"

    with zipfile.ZipFile(archive_path, "w"):
        pass

    entries = list_entries(archive_path)

    assert entries == []

    result = validate_archive(archive_path)

    assert result.ok is True
    assert result.entries == []