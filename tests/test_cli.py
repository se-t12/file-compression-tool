"""
CLI tests. These monkeypatch the orchestrator functions so they pass
regardless of whether archive_writer/extraction/archive_parser are
implemented yet -- they only check that the CLI parses arguments correctly
and calls the right orchestrator function with the right values.
"""
from pathlib import Path

from fct import cli, orchestrator


def test_compress_command_dispatch(monkeypatch):
    captured = {}

    def fake_compress_command(input_paths, output_path, overwrite_policy):
        captured["input_paths"] = input_paths
        captured["output_path"] = output_path
        captured["overwrite_policy"] = overwrite_policy
        return 0

    monkeypatch.setattr(orchestrator, "compress_command", fake_compress_command)

    exit_code = cli.main(["compress", "a.txt", "b.txt", "-o", "out.zip"])

    assert exit_code == 0
    assert captured["input_paths"] == [Path("a.txt"), Path("b.txt")]
    assert captured["output_path"] == Path("out.zip")
    assert captured["overwrite_policy"] == "skip"  # default


def test_extract_command_dispatch(monkeypatch):
    captured = {}

    def fake_extract_command(archive_path, destination, overwrite_policy):
        captured["archive_path"] = archive_path
        captured["destination"] = destination
        captured["overwrite_policy"] = overwrite_policy
        return 0

    monkeypatch.setattr(orchestrator, "extract_command", fake_extract_command)

    exit_code = cli.main(["extract", "out.zip", "-d", "dest/", "--on-duplicate", "rename"])

    assert exit_code == 0
    assert captured["archive_path"] == Path("out.zip")
    assert captured["destination"] == Path("dest/")
    assert captured["overwrite_policy"] == "rename"


def test_list_command_dispatch(monkeypatch):
    captured = {}

    def fake_list_command(archive_path):
        captured["archive_path"] = archive_path
        return 0

    monkeypatch.setattr(orchestrator, "list_command", fake_list_command)

    exit_code = cli.main(["list", "out.zip"])

    assert exit_code == 0
    assert captured["archive_path"] == Path("out.zip")


def test_no_command_prints_help_and_fails():
    # argparse itself exits with SystemExit(2) when a required subcommand is missing.
    import pytest
    with pytest.raises(SystemExit):
        cli.main([])


def test_not_implemented_module_gives_friendly_message(monkeypatch, capsys):
    def raise_not_implemented(*args, **kwargs):
        raise NotImplementedError("TODO (Adarsh): implement ZIP creation")

    monkeypatch.setattr(orchestrator, "compress_command", raise_not_implemented)

    exit_code = cli.main(["compress", "a.txt", "-o", "out.zip"])

    assert exit_code == 2
    out = capsys.readouterr().out
    assert "Not implemented yet" in out
