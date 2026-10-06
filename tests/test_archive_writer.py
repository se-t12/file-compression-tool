"""
Tests for fct.archive_writer.create_archive()
Owner: Adarsh Prakash

Covers:
  - Compress plain files  → archive contains them, success=True
  - Compress a folder with nested subfolders → structure preserved
  - Empty input list      → raises ValueError
  - Output already exists, policy="skip" → no overwrite, success=False
  - Output already exists, policy="overwrite" → file replaced
  - Output already exists, policy="rename" → new path chosen automatically
  - Missing / nonexistent input path → recorded in errors, not a crash
  - Unknown overwrite_policy → raises ValueError
"""
import zipfile
from pathlib import Path

import pytest

from fct.archive_writer import create_archive


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _names_in_zip(zip_path: Path) -> set:
    """Return the set of member names stored inside a ZIP file."""
    with zipfile.ZipFile(zip_path) as zf:
        return set(zf.namelist())


# ---------------------------------------------------------------------------
# Plain-file compression  (FCT-F-002)
# ---------------------------------------------------------------------------

def test_plain_files_are_compressed(tmp_path):
    """Two plain text files end up inside the archive, result is success."""
    file_a = tmp_path / "alpha.txt"
    file_b = tmp_path / "beta.txt"
    file_a.write_text("hello")
    file_b.write_text("world")

    out = tmp_path / "out.zip"
    result = create_archive([file_a, file_b], out, overwrite_policy="overwrite")

    assert result.success is True
    assert result.entries_written == 2
    assert result.output_path == out
    assert result.errors == []

    names = _names_in_zip(out)
    assert "alpha.txt" in names
    assert "beta.txt" in names


def test_single_file_archive(tmp_path):
    """A single file also works correctly."""
    f = tmp_path / "solo.txt"
    f.write_text("only me")
    out = tmp_path / "solo.zip"

    result = create_archive([f], out, overwrite_policy="overwrite")

    assert result.success is True
    assert result.entries_written == 1
    assert "solo.txt" in _names_in_zip(out)


# ---------------------------------------------------------------------------
# Folder / nested-subfolder compression  (FCT-F-003)
# ---------------------------------------------------------------------------

def test_folder_structure_is_preserved(tmp_path):
    """Nested folder tree → relative paths are kept inside the archive."""
    src = tmp_path / "project"
    (src / "subdir").mkdir(parents=True)
    (src / "root_file.txt").write_text("root")
    (src / "subdir" / "deep_file.txt").write_text("deep")

    out = tmp_path / "project.zip"
    result = create_archive([src], out, overwrite_policy="overwrite")

    assert result.success is True
    assert result.entries_written == 2

    names = _names_in_zip(out)
    # arcname is relative to the *parent* of src, so paths start with "project/"
    assert any("root_file.txt" in n for n in names)
    assert any("deep_file.txt" in n for n in names)
    # Structure must be preserved (subdir must appear somewhere in a name)
    assert any("subdir" in n for n in names)


def test_multi_level_nesting(tmp_path):
    """Three levels deep still works."""
    src = tmp_path / "a"
    (src / "b" / "c").mkdir(parents=True)
    (src / "b" / "c" / "leaf.txt").write_text("leaf")

    out = tmp_path / "deep.zip"
    result = create_archive([src], out, overwrite_policy="overwrite")

    assert result.success is True
    names = _names_in_zip(out)
    assert any("leaf.txt" in n for n in names)
    assert any("b" in n and "c" in n for n in names)


# ---------------------------------------------------------------------------
# Empty input  (per design notes)
# ---------------------------------------------------------------------------

def test_empty_input_raises_value_error(tmp_path):
    """An empty input list raises ValueError before touching the filesystem."""
    out = tmp_path / "nothing.zip"
    with pytest.raises(ValueError, match="empty"):
        create_archive([], out)


# ---------------------------------------------------------------------------
# Overwrite policies  (FCT-SR-005)
# ---------------------------------------------------------------------------

def test_skip_policy_leaves_existing_file_untouched(tmp_path):
    """policy='skip' → original archive unchanged, result.success=False."""
    existing = tmp_path / "archive.zip"
    with zipfile.ZipFile(existing, "w") as zf:
        zf.writestr("original.txt", "original content")

    new_file = tmp_path / "new_file.txt"
    new_file.write_text("new content")

    result = create_archive([new_file], existing, overwrite_policy="skip")

    assert result.success is False
    assert result.entries_written == 0
    assert len(result.errors) == 1

    # Original archive must still contain only the original member
    assert _names_in_zip(existing) == {"original.txt"}


def test_overwrite_policy_replaces_existing_file(tmp_path):
    """policy='overwrite' → old archive is replaced by the new one."""
    existing = tmp_path / "archive.zip"
    with zipfile.ZipFile(existing, "w") as zf:
        zf.writestr("old.txt", "old")

    new_file = tmp_path / "fresh.txt"
    new_file.write_text("fresh")

    result = create_archive([new_file], existing, overwrite_policy="overwrite")

    assert result.success is True
    names = _names_in_zip(existing)
    assert "fresh.txt" in names
    assert "old.txt" not in names


def test_rename_policy_picks_new_path(tmp_path):
    """policy='rename' → a new path is chosen; original archive is untouched."""
    existing = tmp_path / "archive.zip"
    with zipfile.ZipFile(existing, "w") as zf:
        zf.writestr("original.txt", "original")

    new_file = tmp_path / "extra.txt"
    new_file.write_text("extra content")

    result = create_archive([new_file], existing, overwrite_policy="rename")

    assert result.success is True
    # The output path must differ from the original
    assert result.output_path != existing
    # The original must still be intact
    assert _names_in_zip(existing) == {"original.txt"}
    # The new archive must contain the new file
    assert "extra.txt" in _names_in_zip(result.output_path)


# ---------------------------------------------------------------------------
# Missing / unreadable inputs  (FCT-F-004)
# ---------------------------------------------------------------------------

def test_nonexistent_path_recorded_in_errors(tmp_path):
    """A path that doesn't exist gets recorded in errors; function doesn't crash."""
    ghost = tmp_path / "ghost.txt"  # intentionally not created

    out = tmp_path / "partial.zip"
    result = create_archive([ghost], out, overwrite_policy="overwrite")

    assert result.success is False
    assert result.entries_written == 0
    assert len(result.errors) == 1
    assert "ghost.txt" in result.errors[0]


def test_mixed_valid_and_invalid_paths(tmp_path):
    """Valid files are still added even when some paths are missing."""
    good = tmp_path / "good.txt"
    good.write_text("I exist")
    bad = tmp_path / "bad.txt"  # intentionally not created

    out = tmp_path / "mixed.zip"
    result = create_archive([good, bad], out, overwrite_policy="overwrite")

    assert result.entries_written == 1
    assert len(result.errors) == 1
    assert "good.txt" in _names_in_zip(out)


# ---------------------------------------------------------------------------
# Unknown overwrite_policy
# ---------------------------------------------------------------------------

def test_unknown_policy_raises_value_error(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("x")
    out = tmp_path / "out.zip"
    with pytest.raises(ValueError, match="overwrite_policy"):
        create_archive([f], out, overwrite_policy="explode")
