"""
Tests for fct.memory_check (NF-002 Peak Memory Check, TC-Perf-02)
Owner: Adarsh Prakash

Covers:
  - Evaluation of NF-002 threshold (<= 512 MB limit)
  - Workload file generation (streaming without large memory buffers)
  - End-to-end compression and extraction memory measurements
  - Safe cleanup of temporary benchmark files
  - Distinction between full 1 GB and sub-1GB workload reporting
  - CLI and Orchestrator dispatch
  - Error handling and invalid argument validation
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fct import cli, memory_check, orchestrator
from fct.memory_check import (
    BYTES_PER_MB,
    BYTES_PER_MIB,
    DEFAULT_THRESHOLD_BYTES,
    DEFAULT_WORKLOAD_BYTES,
    MemorySuiteReport,
    OperationMemoryResult,
    benchmark_compression_memory,
    benchmark_extraction_memory,
    evaluate_nf002,
    format_report_text,
    generate_workload_file,
    run_memory_benchmark,
)


# ---------------------------------------------------------------------------
# Unit tests: Threshold evaluation and units
# ---------------------------------------------------------------------------

def test_evaluate_nf002_threshold():
    """Verify threshold evaluation for values at, below, and above 512 MB."""
    limit_512mb = 512 * BYTES_PER_MB  # 512,000,000 bytes

    # Below 512 MB -> PASS
    assert evaluate_nf002(100 * BYTES_PER_MB, threshold_bytes=limit_512mb) is True
    assert evaluate_nf002(511 * BYTES_PER_MB, threshold_bytes=limit_512mb) is True

    # Exactly 512 MB -> PASS
    assert evaluate_nf002(limit_512mb, threshold_bytes=limit_512mb) is True

    # Above 512 MB -> FAIL
    assert evaluate_nf002(limit_512mb + 1, threshold_bytes=limit_512mb) is False
    assert evaluate_nf002(600 * BYTES_PER_MB, threshold_bytes=limit_512mb) is False


def test_operation_memory_result_unit_properties():
    """Verify conversion of bytes to MB and MiB properties."""
    res = OperationMemoryResult(
        operation="compression",
        workload_bytes=100_000_000,
        elapsed_seconds=1.5,
        initial_process_bytes=20 * BYTES_PER_MB,
        peak_process_bytes=50 * BYTES_PER_MB,
        peak_python_bytes=10 * BYTES_PER_MB,
        threshold_bytes=DEFAULT_THRESHOLD_BYTES,
        passed=True,
        success=True,
    )
    assert res.peak_process_mb == 50.0
    assert pytest.approx(res.peak_process_mib, rel=1e-3) == (50 * BYTES_PER_MB) / BYTES_PER_MIB
    assert res.peak_python_mb == 10.0
    assert res.threshold_mb == 512.0


def test_invalid_argument_validation():
    """Negative or zero workload/threshold raises ValueError."""
    with pytest.raises(ValueError, match="workload_bytes must be positive"):
        run_memory_benchmark(workload_bytes=0)

    with pytest.raises(ValueError, match="threshold_bytes must be positive"):
        run_memory_benchmark(workload_bytes=1000, threshold_bytes=-1)


# ---------------------------------------------------------------------------
# Workload generator and streaming
# ---------------------------------------------------------------------------

def test_generate_workload_file(tmp_path):
    """Generator writes exact specified bytes and preserves disk file."""
    target = tmp_path / "workload.dat"
    target_size = 500_000  # 500 KB
    generate_workload_file(target, target_size)

    assert target.exists()
    assert target.stat().st_size == target_size

    with open(target, "rb") as f:
        header = f.read(80)
    assert b"FCT-NF-002" in header


# ---------------------------------------------------------------------------
# Integration tests: End-to-end memory measurement & cleanup
# ---------------------------------------------------------------------------

def test_run_memory_benchmark_end_to_end(tmp_path):
    """Run full memory benchmark with small payload and verify results and cleanup."""
    # 1 MB workload for fast test execution
    workload_bytes = 1_000_000
    report = run_memory_benchmark(
        workload_bytes=workload_bytes,
        threshold_bytes=DEFAULT_THRESHOLD_BYTES,
        work_dir=tmp_path / "bench_env",
    )

    assert report.workload_bytes == workload_bytes
    assert report.is_full_1gb_workload is False
    assert "Partial workload" in report.workload_note
    assert report.compression.success is True
    assert report.extraction.success is True
    assert report.compression.passed is True
    assert report.extraction.passed is True
    assert report.all_passed is True

    # Memory assertions: streaming operations should use << 512 MB
    assert report.compression.peak_process_bytes < DEFAULT_THRESHOLD_BYTES
    assert report.extraction.peak_process_bytes < DEFAULT_THRESHOLD_BYTES

    # Formatted report checks
    text = format_report_text(report)
    assert "FCT-NF-002 MEMORY BENCHMARK REPORT" in text
    assert "[COMPRESSION]" in text
    assert "[EXTRACTION]" in text
    assert "OVERALL MEMORY VERDICT: PASSED" in text


def test_run_memory_benchmark_auto_cleanup():
    """Verify that using default temporary directory leaves no leftover temporary directory."""
    temp_dir = tempfile.gettempdir()
    before_dirs = set(Path(temp_dir).iterdir())
    report = run_memory_benchmark(
        workload_bytes=200_000,
        threshold_bytes=DEFAULT_THRESHOLD_BYTES,
    )
    assert report.all_passed is True
    after_dirs = set(Path(temp_dir).iterdir())
    created_and_left = [d for d in (after_dirs - before_dirs) if "tmp" in d.name]
    assert len(created_and_left) == 0


def test_full_1gb_workload_flag():
    """Verify that is_full_1gb_workload is correctly identified."""
    # Mocking execution to verify flag logic without allocating 1 GB in unit test
    def mock_comp(input_path, output_dir, threshold_bytes):
        return OperationMemoryResult(
            operation="compression",
            workload_bytes=DEFAULT_WORKLOAD_BYTES,
            elapsed_seconds=1.0,
            initial_process_bytes=1000,
            peak_process_bytes=2000,
            peak_python_bytes=500,
            threshold_bytes=threshold_bytes,
            passed=True,
            success=True,
        )

    def mock_extr(archive_path, extract_dir, uncompressed_size_bytes, threshold_bytes):
        return OperationMemoryResult(
            operation="extraction",
            workload_bytes=DEFAULT_WORKLOAD_BYTES,
            elapsed_seconds=1.0,
            initial_process_bytes=1000,
            peak_process_bytes=2000,
            peak_python_bytes=500,
            threshold_bytes=threshold_bytes,
            passed=True,
            success=True,
        )

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # Create dummy file
        dummy = tdp / "workload.bin"
        dummy.write_bytes(b"x")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(memory_check, "generate_workload_file", lambda p, s: dummy)
            mp.setattr(memory_check, "benchmark_compression_memory", mock_comp)
            mp.setattr(memory_check, "benchmark_extraction_memory", mock_extr)
            report = run_memory_benchmark(
                workload_bytes=DEFAULT_WORKLOAD_BYTES,
                threshold_bytes=DEFAULT_THRESHOLD_BYTES,
                work_dir=tdp,
            )
            assert report.is_full_1gb_workload is True
            assert "Full 1 GB" in report.workload_note


# ---------------------------------------------------------------------------
# CLI and Orchestrator tests
# ---------------------------------------------------------------------------

def test_cli_memory_check_dispatch(monkeypatch):
    """CLI memory-check subcommand dispatches correctly to orchestrator."""
    captured = {}

    def fake_memory_check_command(size_mb, threshold_mb, json_output):
        captured["size_mb"] = size_mb
        captured["threshold_mb"] = threshold_mb
        captured["json"] = json_output
        return 0

    monkeypatch.setattr(orchestrator, "memory_check_command", fake_memory_check_command)

    exit_code = cli.main(["memory-check", "--size-mb", "200", "--threshold-mb", "256", "--json"])
    assert exit_code == 0
    assert captured["size_mb"] == 200.0
    assert captured["threshold_mb"] == 256.0
    assert captured["json"] is True


def test_orchestrator_memory_check_command(capsys, monkeypatch):
    """Orchestrator runs memory check and prints formatted output or json."""
    def fake_run(workload_bytes, threshold_bytes):
        mock_op = OperationMemoryResult(
            operation="compression",
            workload_bytes=workload_bytes,
            elapsed_seconds=0.5,
            initial_process_bytes=10_000_000,
            peak_process_bytes=25_000_000,
            peak_python_bytes=5_000_000,
            threshold_bytes=threshold_bytes,
            passed=True,
            success=True,
        )
        return MemorySuiteReport(
            workload_bytes=workload_bytes,
            threshold_bytes=threshold_bytes,
            is_full_1gb_workload=False,
            compression=mock_op,
            extraction=mock_op,
            all_passed=True,
            workload_note="Test run",
        )

    monkeypatch.setattr(memory_check, "run_memory_benchmark", fake_run)

    exit_code = orchestrator.memory_check_command(size_mb=10.0, threshold_mb=512.0, json_output=False)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FCT-NF-002 MEMORY BENCHMARK REPORT" in out

    exit_code_json = orchestrator.memory_check_command(size_mb=10.0, threshold_mb=512.0, json_output=True)
    assert exit_code_json == 0
    out_json = capsys.readouterr().out
    parsed = json.loads(out_json)
    assert parsed["all_passed"] is True
    assert parsed["workload_bytes"] == 10_000_000


def test_memory_check_module_main(capsys):
    """Standalone python -m fct.memory_check works for pass and fail exits."""
    # Passing run
    exit_code = memory_check.main(["--size-mb", "0.5", "--threshold-mb", "512.0"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FCT-NF-002 MEMORY BENCHMARK REPORT" in out

    # Failing run with artificially tiny threshold
    exit_code_fail = memory_check.main(["--size-mb", "0.5", "--threshold-mb", "0.0001"])
    assert exit_code_fail == 2
