"""
CLI integration tests (Sprint 2, issue #29).

Unlike tests/test_cli.py (which mocks the orchestrator), these tests run the REAL
command line end to end: CLI -> orchestrator -> archive writer / parser /
extraction / security, using real files in a temporary folder. Nothing is mocked.

Each test lists the SRS requirement(s) it covers.
"""
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from fct import cli

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cli(capsys, *args):
    """Run the CLI in-process and return (exit_code, printed_output)."""
    capsys.readouterr()  # discard anything printed earlier
    code = cli.main([str(a) for a in args])
    return code, capsys.readouterr().out


def read_tree(root: Path) -> dict:
    """Map relative file path (with / separators) -> file bytes, for every file under root."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def sample_dir(tmp_path):
    """A small folder with text, a nested file and a binary file."""
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("alpha\n")
    (src / "sub" / "b.txt").write_text("beta\n")
    (src / "blob.bin").write_bytes(bytes(range(256)) * 20)  # 5120 bytes, all byte values
    return src


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------

def test_round_trip_folder_preserves_structure_and_bytes(capsys, tmp_path, sample_dir):
    """FCT-F-002, F-003, F-007, F-013, NF-004: compress then extract gives identical files."""
    archive = tmp_path / "out.zip"
    dest = tmp_path / "dest"

    code, out = run_cli(capsys, "compress", sample_dir, "-o", archive)
    assert code == 0
    assert archive.exists()
    assert "3 entries" in out

    code, out = run_cli(capsys, "extract", archive, "-d", dest)
    assert code == 0
    assert "Extracted 3 file(s)" in out

    original = read_tree(sample_dir)
    extracted = read_tree(dest / "src")
    assert extracted == original  # same names (structure) and same bytes
    for name, data in original.items():
        assert sha256(extracted[name]) == sha256(data)
        assert len(extracted[name]) == len(data)


def test_list_shows_every_entry_without_extracting(capsys, tmp_path, sample_dir):
    """FCT-F-010: list prints each entry with its size and creates no files."""
    archive = tmp_path / "out.zip"
    run_cli(capsys, "compress", sample_dir, "-o", archive)
    before = sorted(p.name for p in tmp_path.iterdir())

    code, out = run_cli(capsys, "list", archive)

    assert code == 0
    for name in ("src/a.txt", "src/sub/b.txt", "src/blob.bin"):
        assert name in out
    assert "5120 bytes" in out
    assert sorted(p.name for p in tmp_path.iterdir()) == before  # nothing extracted


def test_compress_multiple_inputs_file_and_folder(capsys, tmp_path, sample_dir):
    """FCT-F-001, F-002: a single file and a folder can be compressed together."""
    archive = tmp_path / "two.zip"

    code, out = run_cli(capsys, "compress", sample_dir / "a.txt", sample_dir / "sub", "-o", archive)

    assert code == 0
    assert sorted(zipfile.ZipFile(archive).namelist()) == ["a.txt", "sub/b.txt"]


# ---------------------------------------------------------------------------
# Duplicate-file policies (compress side and extract side)
# ---------------------------------------------------------------------------

def test_compress_existing_output_default_is_non_destructive(capsys, tmp_path, sample_dir):
    """FCT-SR-005: by default an existing output archive is NOT overwritten."""
    archive = tmp_path / "out.zip"
    run_cli(capsys, "compress", sample_dir, "-o", archive)
    original_bytes = archive.read_bytes()

    code, out = run_cli(capsys, "compress", sample_dir / "a.txt", "-o", archive)

    assert code == 1
    assert "already exists" in out
    assert "--on-duplicate" in out  # tells the user how to proceed
    assert archive.read_bytes() == original_bytes


def test_compress_overwrite_policy_replaces_existing_output(capsys, tmp_path, sample_dir):
    """FCT-F-011/SR-005: --on-duplicate overwrite replaces the old archive."""
    archive = tmp_path / "out.zip"
    run_cli(capsys, "compress", sample_dir, "-o", archive)

    code, _ = run_cli(capsys, "compress", sample_dir / "a.txt", "-o", archive, "--on-duplicate", "overwrite")

    assert code == 0
    assert zipfile.ZipFile(archive).namelist() == ["a.txt"]


def test_compress_rename_policy_keeps_original(capsys, tmp_path, sample_dir):
    """FCT-F-011/SR-005: --on-duplicate rename saves next to the existing archive."""
    archive = tmp_path / "out.zip"
    run_cli(capsys, "compress", sample_dir, "-o", archive)
    original_bytes = archive.read_bytes()

    code, _ = run_cli(capsys, "compress", sample_dir / "a.txt", "-o", archive, "--on-duplicate", "rename")

    assert code == 0
    assert archive.read_bytes() == original_bytes
    renamed = tmp_path / "out_1.zip"
    assert renamed.exists()
    assert zipfile.ZipFile(renamed).namelist() == ["a.txt"]


def _extract_twice_setup(capsys, tmp_path, sample_dir):
    archive = tmp_path / "out.zip"
    dest = tmp_path / "dest"
    run_cli(capsys, "compress", sample_dir, "-o", archive)
    run_cli(capsys, "extract", archive, "-d", dest)
    (dest / "src" / "a.txt").write_text("LOCAL EDIT\n")  # make the existing file differ
    return archive, dest


def test_extract_skip_policy_leaves_existing_files(capsys, tmp_path, sample_dir):
    """FCT-F-011, SR-005: default policy keeps existing files and reports them as skipped."""
    archive, dest = _extract_twice_setup(capsys, tmp_path, sample_dir)

    code, out = run_cli(capsys, "extract", archive, "-d", dest)

    assert code == 0
    assert "Skipped 3 file(s)" in out
    assert (dest / "src" / "a.txt").read_text() == "LOCAL EDIT\n"


def test_extract_overwrite_policy_replaces_existing_files(capsys, tmp_path, sample_dir):
    """FCT-F-011: --on-duplicate overwrite restores the archived content."""
    archive, dest = _extract_twice_setup(capsys, tmp_path, sample_dir)

    code, _ = run_cli(capsys, "extract", archive, "-d", dest, "--on-duplicate", "overwrite")

    assert code == 0
    assert (dest / "src" / "a.txt").read_text() == "alpha\n"


def test_extract_rename_policy_keeps_both_versions(capsys, tmp_path, sample_dir):
    """FCT-F-011: --on-duplicate rename keeps the local file and adds a renamed copy."""
    archive, dest = _extract_twice_setup(capsys, tmp_path, sample_dir)

    code, _ = run_cli(capsys, "extract", archive, "-d", dest, "--on-duplicate", "rename")

    assert code == 0
    assert (dest / "src" / "a.txt").read_text() == "LOCAL EDIT\n"
    assert (dest / "src" / "a (1).txt").read_text() == "alpha\n"


# ---------------------------------------------------------------------------
# Security: path traversal (zip-slip) through the whole pipeline
# ---------------------------------------------------------------------------

# An absolute-path entry would land at the root of the current drive if the security
# check ever failed. The test removes this file before and after, so a failed run
# never leaves junk behind and never makes the next run fail by accident.
ABSOLUTE_PROBE = Path("/fct_abs_probe_evil.txt")


def test_extract_blocks_path_traversal_end_to_end(capsys, tmp_path):
    """FCT-F-008, FCT-SR-001: unsafe entries are refused, safe entries still extract."""
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../escape.txt", "should never be written")
        zf.writestr(ABSOLUTE_PROBE.as_posix(), "should never be written")
        zf.writestr("ok.txt", "fine")
    dest = tmp_path / "out"

    ABSOLUTE_PROBE.unlink(missing_ok=True)  # clean slate
    try:
        code, out = run_cli(capsys, "extract", evil, "-d", dest)

        assert code == 1  # a blocked entry makes the command report failure
        assert "Failed 2 file(s)" in out
        assert (dest / "ok.txt").read_text() == "fine"  # the harmless entry still extracted
        assert not (tmp_path / "escape.txt").exists()  # nothing escaped above the destination
        assert not ABSOLUTE_PROBE.exists()  # nothing written at an absolute path
        assert sorted(read_tree(dest)) == ["ok.txt"]
    finally:
        ABSOLUTE_PROBE.unlink(missing_ok=True)  # never leave a stray file behind


# ---------------------------------------------------------------------------
# Error handling: clear messages and non-zero exit codes
# ---------------------------------------------------------------------------

def test_compress_missing_input_fails_with_clear_message(capsys, tmp_path):
    """FCT-NF-003: the error names the operation and the missing path."""
    code, out = run_cli(capsys, "compress", tmp_path / "does_not_exist.txt", "-o", tmp_path / "out.zip")

    assert code == 1
    assert "Compression failed" in out
    assert "does_not_exist.txt" in out


@pytest.mark.parametrize("command", ["extract", "list"])
@pytest.mark.parametrize("kind", ["not_a_zip", "truncated"])
def test_bad_archive_is_rejected(capsys, tmp_path, sample_dir, command, kind):
    """FCT-F-009, FCT-SR-002, FCT-NF-003: corrupt archives are rejected, nothing is extracted."""
    good = tmp_path / "good.zip"
    run_cli(capsys, "compress", sample_dir, "-o", good)
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"this is plain text, not a zip" if kind == "not_a_zip" else good.read_bytes()[:100])
    dest = tmp_path / "dest"

    args = [command, bad] + (["-d", dest] if command == "extract" else [])
    code, out = run_cli(capsys, *args)

    assert code == 1
    assert "failed" in out.lower()
    assert "bad.zip" in out  # names the offending file
    assert not dest.exists() or not read_tree(dest)


@pytest.mark.parametrize("command", ["extract", "list"])
def test_missing_archive_is_rejected(capsys, tmp_path, command):
    """FCT-NF-003: a missing archive gives a clear error, not a crash."""
    args = [command, tmp_path / "missing.zip"] + (["-d", tmp_path / "dest"] if command == "extract" else [])

    code, out = run_cli(capsys, *args)

    assert code == 1
    assert "missing.zip" in out


@pytest.mark.xfail(reason="Known issue: a failed compress still leaves an empty .zip behind")
def test_failed_compress_leaves_no_output_file(capsys, tmp_path):
    """FCT-F-014: a failed compression should not leave an empty archive behind."""
    archive = tmp_path / "out.zip"

    code, _ = run_cli(capsys, "compress", tmp_path / "does_not_exist.txt", "-o", archive)

    assert code == 1
    assert not archive.exists()


# ---------------------------------------------------------------------------
# Real process: the command as a user would actually run it
# ---------------------------------------------------------------------------

def _run_process(*args):
    return subprocess.run(
        [sys.executable, "-m", "fct.cli", *[str(a) for a in args]],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def test_real_process_round_trip(tmp_path, sample_dir):
    """FCT-F-002, F-007, F-015: python -m fct.cli works as a separate process, exit code 0."""
    archive = tmp_path / "out.zip"
    dest = tmp_path / "dest"

    result = _run_process("compress", sample_dir, "-o", archive)
    assert result.returncode == 0
    assert "Created" in result.stdout

    result = _run_process("extract", archive, "-d", dest)
    assert result.returncode == 0
    assert "Extracted 3 file(s)" in result.stdout
    assert read_tree(dest / "src") == read_tree(sample_dir)


def test_real_process_help_and_unknown_command():
    """The CLI lists its commands, and an unknown command exits with an error."""
    result = _run_process("--help")
    assert result.returncode == 0
    for command in ("compress", "extract", "list"):
        assert command in result.stdout

    result = _run_process("explode")
    assert result.returncode != 0
