"""
Tests for Issue #26 — Clear Error Messages (FCT-F-026)
Owner: Adarsh

Covers three required scenarios:
1. Missing input file  — compression error names the missing file.
2. Bad / corrupt ZIP   — extract/list error names the archive file.
3. Existing output file — compression error names the output file and
                          tells the user how to fix it.

All checks assert that the human-readable message contains **both** an
action description ("what failed") and the relevant file path ("which file").
"""
import zipfile
from pathlib import Path

import pytest

from fct import archive_writer, archive_parser, extraction, cli, orchestrator


# ---------------------------------------------------------------------------
# Scenario 1 — Missing input file
# ---------------------------------------------------------------------------

class TestMissingInput:
    """compress: a non-existent source path produces a clear error."""

    def test_error_names_the_missing_file(self, tmp_path):
        missing = tmp_path / "ghost.txt"
        output = tmp_path / "out.zip"

        result = archive_writer.create_archive([missing], output)

        assert not result.success
        assert len(result.errors) == 1
        # Must mention the filename
        assert str(missing) in result.errors[0] or missing.name in result.errors[0]

    def test_error_describes_what_failed(self, tmp_path):
        missing = tmp_path / "ghost.txt"
        output = tmp_path / "out.zip"

        result = archive_writer.create_archive([missing], output)

        # Message must say *what* went wrong (path not found / input)
        msg = result.errors[0].lower()
        assert "not found" in msg or "input" in msg

    def test_cli_compress_missing_input_exits_nonzero(self, tmp_path, capsys):
        """End-to-end: CLI exits with code 1 and prints the filename."""
        missing = tmp_path / "no_such_file.txt"
        output = tmp_path / "out.zip"

        exit_code = cli.main([
            "compress", str(missing), "-o", str(output),
        ])

        assert exit_code == 1
        out = capsys.readouterr().out
        assert missing.name in out or str(missing) in out


# ---------------------------------------------------------------------------
# Scenario 2 — Bad / corrupt ZIP
# ---------------------------------------------------------------------------

class TestBadZip:
    """extract and list: a corrupt archive produces a clear error naming the file."""

    @pytest.fixture()
    def corrupt_zip(self, tmp_path) -> Path:
        p = tmp_path / "corrupt.zip"
        p.write_bytes(b"this is not a zip file")
        return p

    # archive_parser.validate_archive ----------------------------------------

    def test_validate_names_the_archive(self, corrupt_zip):
        result = archive_parser.validate_archive(corrupt_zip)

        assert not result.ok
        assert corrupt_zip.name in result.reason or str(corrupt_zip) in result.reason

    def test_validate_describes_what_failed(self, corrupt_zip):
        result = archive_parser.validate_archive(corrupt_zip)

        reason_lower = result.reason.lower()
        # Must convey it is not a valid archive
        assert "not a valid" in reason_lower or "invalid" in reason_lower or "not found" in reason_lower

    # archive_parser — missing archive file ------------------------------------

    def test_validate_missing_archive_names_path(self, tmp_path):
        missing = tmp_path / "missing.zip"
        result = archive_parser.validate_archive(missing)

        assert not result.ok
        assert missing.name in result.reason or str(missing) in result.reason

    def test_validate_missing_archive_describes_what_failed(self, tmp_path):
        missing = tmp_path / "missing.zip"
        result = archive_parser.validate_archive(missing)

        assert "not found" in result.reason.lower() or "invalid" in result.reason.lower()

    # extraction.extract_archive (BadZipFile path) ----------------------------

    def test_extraction_bad_zip_names_archive(self, corrupt_zip, tmp_path):
        dest = tmp_path / "out"
        result = extraction.extract_archive(corrupt_zip, dest)

        assert not result.success
        assert len(result.failed) == 1
        assert corrupt_zip.name in result.failed[0] or str(corrupt_zip) in result.failed[0]

    def test_extraction_bad_zip_describes_what_failed(self, corrupt_zip, tmp_path):
        dest = tmp_path / "out"
        result = extraction.extract_archive(corrupt_zip, dest)

        msg_lower = result.failed[0].lower()
        assert "not a valid" in msg_lower or "invalid" in msg_lower

    # CLI list ----------------------------------------------------------------

    def test_cli_list_bad_zip_exits_nonzero(self, corrupt_zip, capsys):
        exit_code = cli.main(["list", str(corrupt_zip)])

        assert exit_code == 1
        out = capsys.readouterr().out
        assert corrupt_zip.name in out or str(corrupt_zip) in out

    def test_cli_extract_bad_zip_exits_nonzero(self, corrupt_zip, tmp_path, capsys):
        dest = tmp_path / "dest"
        exit_code = cli.main([
            "extract", str(corrupt_zip), "-d", str(dest),
        ])

        assert exit_code == 1
        out = capsys.readouterr().out
        assert corrupt_zip.name in out or str(corrupt_zip) in out


# ---------------------------------------------------------------------------
# Scenario 3 — Existing output file
# ---------------------------------------------------------------------------

class TestExistingOutput:
    """compress with policy='skip': error names the output file and hints at resolution."""

    @pytest.fixture()
    def existing_zip(self, tmp_path) -> Path:
        p = tmp_path / "already_there.zip"
        p.write_bytes(b"placeholder")
        return p

    def test_error_names_the_output_file(self, tmp_path, existing_zip):
        src = tmp_path / "src.txt"
        src.write_text("hello")

        result = archive_writer.create_archive([src], existing_zip, overwrite_policy="skip")

        assert not result.success
        assert existing_zip.name in result.errors[0] or str(existing_zip) in result.errors[0]

    def test_error_mentions_already_exists(self, tmp_path, existing_zip):
        src = tmp_path / "src.txt"
        src.write_text("hello")

        result = archive_writer.create_archive([src], existing_zip, overwrite_policy="skip")

        assert "already exists" in result.errors[0].lower()

    def test_error_hints_at_on_duplicate(self, tmp_path, existing_zip):
        """The message should guide the user on how to resolve the conflict."""
        src = tmp_path / "src.txt"
        src.write_text("hello")

        result = archive_writer.create_archive([src], existing_zip, overwrite_policy="skip")

        assert "--on-duplicate" in result.errors[0]

    def test_cli_compress_existing_output_exits_nonzero(self, tmp_path, existing_zip, capsys):
        src = tmp_path / "src.txt"
        src.write_text("hello")

        exit_code = cli.main([
            "compress", str(src), "-o", str(existing_zip),
        ])

        assert exit_code == 1
        out = capsys.readouterr().out
        assert existing_zip.name in out or str(existing_zip) in out
