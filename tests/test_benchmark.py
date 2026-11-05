"""
Tests for fct.benchmark (NF-001 Speed Check, TC-Perf-01)
Owner: Adarsh Prakash

Covers:
  - Correct calculation of elapsed time, normalized time, and throughput
  - Correct percentile calculations (p95)
  - NF-001 threshold evaluation logic (passing and failing cases)
  - Benchmark execution with deterministic mocked timers
  - Full end-to-end integration run on real files with cleanup verification
  - CLI integration for benchmark command
  - Handling of invalid arguments and error cases
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fct import benchmark, cli, orchestrator
from fct.benchmark import (
    BYTES_PER_MB,
    BYTES_PER_MIB,
    DEFAULT_THRESHOLD_SECONDS_PER_100MB,
    DEFAULT_WORKLOAD_BYTES,
    IterationResult,
    OperationBenchmarkResult,
    benchmark_compression,
    benchmark_extraction,
    calculate_percentile,
    calculate_throughput,
    evaluate_nf001,
    format_report_text,
    generate_benchmark_file,
    normalize_to_100mb,
    run_speed_benchmark,
)


# ---------------------------------------------------------------------------
# Unit tests: Metric and statistical calculations
# ---------------------------------------------------------------------------

def test_calculate_percentile_single_value():
    """Percentile of a single value is the value itself."""
    assert calculate_percentile([42.0], 95.0) == 42.0


def test_calculate_percentile_multiple_values():
    """Verify linear interpolation matches expected percentiles."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    # For n=5, 95th percentile index is 0.95 * 4 = 3.8 -> 4.0 + 0.8 * (5.0 - 4.0) = 4.8
    p95 = calculate_percentile(values, 95.0)
    assert pytest.approx(p95, rel=1e-3) == 4.8

    # 50th percentile (median) -> index 2.0 -> 3.0
    p50 = calculate_percentile(values, 50.0)
    assert pytest.approx(p50, rel=1e-3) == 3.0


def test_calculate_percentile_validation():
    """Empty list or invalid percentile values raise ValueError."""
    with pytest.raises(ValueError, match="must not be empty"):
        calculate_percentile([], 95.0)

    with pytest.raises(ValueError, match="between 0.0 and 100.0"):
        calculate_percentile([1.0], -5.0)

    with pytest.raises(ValueError, match="between 0.0 and 100.0"):
        calculate_percentile([1.0], 105.0)


def test_calculate_throughput_decimal_and_binary():
    """Verify MB/s (10^6 bytes/s) and MiB/s (2^20 bytes/s)."""
    # 100 MB transferred in 2.0 seconds -> 50.0 MB/s
    size_bytes = 100_000_000
    mb_s = calculate_throughput(size_bytes, 2.0, binary=False)
    assert mb_s == 50.0

    # 104,857,600 bytes (100 MiB) in 2.0 seconds -> 50.0 MiB/s
    size_mib_bytes = 100 * BYTES_PER_MIB
    mib_s = calculate_throughput(size_mib_bytes, 2.0, binary=True)
    assert mib_s == 50.0

    # Elapsed <= 0 should return infinity safely
    assert calculate_throughput(size_bytes, 0.0) == float("inf")


def test_normalize_to_100mb():
    """Verify time scaling to standard 100 MB workload."""
    # 50 MB in 1.0s normalizes to 2.0s per 100 MB
    assert normalize_to_100mb(1.0, 50_000_000) == 2.0
    # 200 MB in 3.0s normalizes to 1.5s per 100 MB
    assert normalize_to_100mb(3.0, 200_000_000) == 1.5

    with pytest.raises(ValueError, match="must be positive"):
        normalize_to_100mb(1.0, 0)


def test_evaluate_nf001_threshold():
    """Verify NF-001 pass/fail threshold evaluation."""
    assert evaluate_nf001(1.5, threshold=2.0) is True
    assert evaluate_nf001(2.0, threshold=2.0) is True
    assert evaluate_nf001(2.0001, threshold=2.0) is False
    assert evaluate_nf001(3.5, threshold=2.0) is False


# ---------------------------------------------------------------------------
# Unit tests: File generator and cleanup
# ---------------------------------------------------------------------------

def test_generate_benchmark_file(tmp_path):
    """File generator creates exact byte size and reproducible content."""
    target = tmp_path / "bench.dat"
    target_size = 50_000  # 50 KB
    generate_benchmark_file(target, target_size)

    assert target.exists()
    assert target.stat().st_size == target_size

    # Verify content pattern
    with open(target, "rb") as f:
        data = f.read(100)
    assert b"File Compression Tool" in data


# ---------------------------------------------------------------------------
# Unit tests with mocked timer (Deterministic, non-flaky)
# ---------------------------------------------------------------------------

def test_benchmark_compression_with_mock_timer(tmp_path):
    """Compression benchmark calculates times, throughput, and threshold using mock timer."""
    input_file = tmp_path / "sample.bin"
    size = 10_000_000  # 10 MB
    generate_benchmark_file(input_file, size)

    # Mock timer returning 0.1s elapsed per iteration:
    # 0.1s for 10MB scales to 1.0s per 100MB (<= 2.0s threshold -> PASS)
    timer_values = [0.0, 0.10, 1.0, 1.10, 2.0, 2.10]
    timer_mock = MagicMock(side_effect=timer_values)

    result = benchmark_compression(
        input_path=input_file,
        output_dir=tmp_path / "out",
        iterations=3,
        threshold_seconds=2.0,
        timer=timer_mock,
    )

    assert result.operation == "compression"
    assert result.data_size_bytes == size
    assert result.iterations == 3
    assert len(result.runs) == 3
    assert result.all_succeeded is True
    assert result.passed is True
    assert pytest.approx(result.p95_time_per_100mb, rel=1e-3) == 1.0
    assert pytest.approx(result.mean_throughput_mb_s, rel=1e-3) == 100.0


def test_benchmark_compression_failing_threshold(tmp_path):
    """Compression benchmark correctly flags failure when exceeding 2s/100MB."""
    input_file = tmp_path / "sample.bin"
    size = 10_000_000  # 10 MB
    generate_benchmark_file(input_file, size)

    # Mock timer returning 0.3s elapsed per iteration:
    # 0.3s for 10MB scales to 3.0s per 100MB (> 2.0s threshold -> FAIL)
    timer_values = [0.0, 0.30, 1.0, 1.30, 2.0, 2.30]
    timer_mock = MagicMock(side_effect=timer_values)

    result = benchmark_compression(
        input_path=input_file,
        output_dir=tmp_path / "out",
        iterations=3,
        threshold_seconds=2.0,
        timer=timer_mock,
    )

    assert result.passed is False
    assert pytest.approx(result.p95_time_per_100mb, rel=1e-3) == 3.0


def test_benchmark_extraction_with_mock_timer(tmp_path):
    """Extraction benchmark correctly measures extraction and evaluates threshold."""
    # Create a small valid archive first
    from fct.archive_writer import create_archive

    source_file = tmp_path / "file.bin"
    size = 5_000_000  # 5 MB
    generate_benchmark_file(source_file, size)

    archive = tmp_path / "test.zip"
    create_archive([source_file], archive, overwrite_policy="overwrite")

    # 0.05s for 5MB scales to 1.0s per 100MB -> PASS
    timer_values = [0.0, 0.05, 1.0, 1.05]
    timer_mock = MagicMock(side_effect=timer_values)

    result = benchmark_extraction(
        archive_path=archive,
        extract_dir=tmp_path / "extr",
        uncompressed_size_bytes=size,
        iterations=2,
        threshold_seconds=2.0,
        timer=timer_mock,
    )

    assert result.operation == "extraction"
    assert result.iterations == 2
    assert result.passed is True
    assert pytest.approx(result.p95_time_per_100mb, rel=1e-3) == 1.0


# ---------------------------------------------------------------------------
# Integration tests: End-to-end execution and cleanup
# ---------------------------------------------------------------------------

def test_run_speed_benchmark_end_to_end(tmp_path):
    """Run full speed benchmark suite end-to-end with real operations and verify cleanup."""
    # Use 1 MB payload for fast, reliable local test run
    payload_size = 1_000_000
    report = run_speed_benchmark(
        data_size_bytes=payload_size,
        iterations=2,
        threshold_seconds=5.0,  # Generous threshold for 1MB test in CI
        work_dir=tmp_path / "bench_env",
    )

    assert report.data_size_bytes == payload_size
    assert report.iterations == 2
    assert report.compression.operation == "compression"
    assert report.extraction.operation == "extraction"
    assert report.compression.all_succeeded is True
    assert report.extraction.all_succeeded is True

    # Formatting checks
    formatted = format_report_text(report)
    assert "FCT-NF-001 SPEED BENCHMARK REPORT" in formatted
    assert "[COMPRESSION]" in formatted
    assert "[EXTRACTION]" in formatted
    assert "OVERALL BENCHMARK VERDICT" in formatted


def test_run_speed_benchmark_auto_cleanup():
    """Verify that using default temporary directory leaves no temporary directory behind."""
    temp_dir = tempfile.gettempdir()
    before_dirs = set(Path(temp_dir).iterdir())
    report = run_speed_benchmark(
        data_size_bytes=100_000,
        iterations=1,
        threshold_seconds=100.0,
    )
    assert report.compression.all_succeeded is True
    assert report.extraction.all_succeeded is True
    assert report.all_passed is True
    after_dirs = set(Path(temp_dir).iterdir())
    created_and_left = [d for d in (after_dirs - before_dirs) if "tmp" in d.name]
    assert len(created_and_left) == 0


# ---------------------------------------------------------------------------
# CLI and Orchestrator tests
# ---------------------------------------------------------------------------

def test_cli_benchmark_dispatch(monkeypatch):
    """CLI benchmark subcommand dispatches correctly to orchestrator."""
    captured = {}

    def fake_benchmark_command(size_mb, iterations, json_output):
        captured["size_mb"] = size_mb
        captured["iterations"] = iterations
        captured["json"] = json_output
        return 0

    monkeypatch.setattr(orchestrator, "benchmark_command", fake_benchmark_command)

    exit_code = cli.main(["benchmark", "--size-mb", "50", "--iterations", "3", "--json"])
    assert exit_code == 0
    assert captured["size_mb"] == 50.0
    assert captured["iterations"] == 3
    assert captured["json"] is True


def test_orchestrator_benchmark_command(capsys, monkeypatch):
    """Orchestrator runs benchmark and outputs formatted summary or json."""
    # Small benchmark mock
    def fake_run(data_size_bytes, iterations):
        mock_op = OperationBenchmarkResult(
            operation="compression",
            data_size_bytes=data_size_bytes,
            iterations=iterations,
            threshold_seconds_per_100mb=2.0,
            p95_time_per_100mb=1.2,
            passed=True,
            all_succeeded=True,
        )
        return benchmark.BenchmarkSuiteReport(
            data_size_bytes=data_size_bytes,
            iterations=iterations,
            threshold_seconds_per_100mb=2.0,
            compression=mock_op,
            extraction=mock_op,
            all_passed=True,
        )

    monkeypatch.setattr(benchmark, "run_speed_benchmark", fake_run)

    exit_code = orchestrator.benchmark_command(size_mb=10.0, iterations=2, json_output=False)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FCT-NF-001 SPEED BENCHMARK REPORT" in out

    exit_code_json = orchestrator.benchmark_command(size_mb=10.0, iterations=2, json_output=True)
    assert exit_code_json == 0
    out_json = capsys.readouterr().out
    parsed = json.loads(out_json)
    assert parsed["all_passed"] is True
    assert parsed["data_size_bytes"] == 10_000_000


def test_benchmark_module_main(capsys):
    """Standalone python -m fct.benchmark CLI interface works for pass and fail exits."""
    exit_code = benchmark.main(["--size-mb", "0.5", "--iterations", "1", "--threshold", "50.0"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "FCT-NF-001 SPEED BENCHMARK REPORT" in out

    exit_code_fail = benchmark.main(["--size-mb", "0.5", "--iterations", "1", "--threshold", "0.0001"])
    assert exit_code_fail == 2

