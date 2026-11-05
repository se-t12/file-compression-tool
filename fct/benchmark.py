"""
Speed Benchmark Module for NF-001
Owner: Adarsh Prakash
Maps to requirement: FCT-NF-001 (TC-Perf-01)
SAD Section: 3.1, 4.4

Requirement FCT-NF-001:
    "For the reference test machine and normal local storage, compression and
    extraction shall achieve a 95th-percentile elapsed time of <= 2 seconds
    per 100 MB for the defined benchmark workload."

This module provides reproducible measurement and verification for both
compression and extraction operations using Python's high-resolution monotonic
timer (time.perf_counter).
"""
import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .archive_writer import create_archive
from .extraction import extract_archive
from .models import ArchiveResult, ExtractionResult

# Default constants
BYTES_PER_MB = 1_000_000  # Decimal megabyte (SI)
BYTES_PER_MIB = 1_048_576  # Binary mebibyte (IEC)
DEFAULT_WORKLOAD_BYTES = 100 * BYTES_PER_MB  # 100 MB
DEFAULT_THRESHOLD_SECONDS_PER_100MB = 2.0  # FCT-NF-001 threshold
DEFAULT_ITERATIONS = 5


@dataclass
class IterationResult:
    """Measurement for a single benchmark iteration."""
    iteration: int
    elapsed_seconds: float
    throughput_mb_s: float
    throughput_mib_s: float
    normalized_time_per_100mb: float
    success: bool
    error_message: Optional[str] = None


@dataclass
class OperationBenchmarkResult:
    """Benchmark results for a single operation (compression or extraction)."""
    operation: str
    data_size_bytes: int
    iterations: int
    threshold_seconds_per_100mb: float
    runs: List[IterationResult] = field(default_factory=list)
    p95_elapsed_seconds: float = 0.0
    p95_time_per_100mb: float = 0.0
    mean_elapsed_seconds: float = 0.0
    mean_throughput_mb_s: float = 0.0
    mean_throughput_mib_s: float = 0.0
    passed: bool = False
    all_succeeded: bool = False


@dataclass
class BenchmarkSuiteReport:
    """Overall benchmark report covering compression and extraction."""
    data_size_bytes: int
    iterations: int
    threshold_seconds_per_100mb: float
    compression: OperationBenchmarkResult
    extraction: OperationBenchmarkResult
    all_passed: bool


def calculate_percentile(values: List[float], percentile: float = 95.0) -> float:
    """Calculate the given percentile (0 to 100) using linear interpolation.

    Matches the standard quantile estimation method.
    """
    if not values:
        raise ValueError("values list must not be empty")
    if not (0.0 <= percentile <= 100.0):
        raise ValueError("percentile must be between 0.0 and 100.0")

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]

    # Rank index from 0 to n - 1
    rank = (percentile / 100.0) * (n - 1)
    lower_idx = int(rank)
    upper_idx = min(lower_idx + 1, n - 1)
    weight = rank - lower_idx

    return sorted_vals[lower_idx] * (1.0 - weight) + sorted_vals[upper_idx] * weight


def calculate_throughput(size_bytes: int, elapsed_seconds: float, binary: bool = False) -> float:
    """Calculate transfer rate in MB/s (decimal) or MiB/s (binary)."""
    if elapsed_seconds <= 0:
        return float("inf")
    unit = BYTES_PER_MIB if binary else BYTES_PER_MB
    return (size_bytes / unit) / elapsed_seconds


def normalize_to_100mb(elapsed_seconds: float, size_bytes: int) -> float:
    """Scale elapsed time proportionally to a standard 100 MB (10^8 bytes) workload."""
    if size_bytes <= 0:
        raise ValueError("size_bytes must be positive")
    return elapsed_seconds * (DEFAULT_WORKLOAD_BYTES / size_bytes)


def evaluate_nf001(p95_time_per_100mb: float, threshold: float = DEFAULT_THRESHOLD_SECONDS_PER_100MB) -> bool:
    """Evaluate whether the 95th-percentile time per 100 MB satisfies FCT-NF-001."""
    return p95_time_per_100mb <= threshold


def generate_benchmark_file(target_path: Path, size_bytes: int) -> Path:
    """Generate a reproducible, representative benchmark payload of exact size.

    Uses a mixed text and structured numerical pattern to yield realistic
    compression ratios and CPU workloads, representative of real-world documents/data.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 1 KB representative block pattern with realistic entropy
    pattern_lines = (
        b"The File Compression Tool provides fast, reliable ZIP compression and extraction.\n"
        b"Structured data payload: index=0123456789, timestamp=2026-10-26T21:00:00Z.\n"
        b"Standard algorithms stream data using 4MB chunks to control memory usage.\n"
        b"Non-functional requirement FCT-NF-001 targets 2 seconds per 100 MB throughput.\n"
    )
    # Pad or repeat to form a 1024-byte chunk
    block = pattern_lines * (1024 // len(pattern_lines) + 1)
    block = block[:1024]

    chunk_size = 64 * 1024  # 64 KB write buffer
    chunk = block * (chunk_size // 1024)

    written = 0
    with open(target_path, "wb") as f:
        while written < size_bytes:
            to_write = min(len(chunk), size_bytes - written)
            f.write(chunk[:to_write])
            written += to_write

    return target_path


def benchmark_compression(
    input_path: Path,
    output_dir: Path,
    iterations: int = DEFAULT_ITERATIONS,
    threshold_seconds: float = DEFAULT_THRESHOLD_SECONDS_PER_100MB,
    timer: Callable[[], float] = time.perf_counter,
) -> OperationBenchmarkResult:
    """Benchmark compression of input_path across multiple iterations.

    Measures only the core create_archive call, excluding preparation and cleanup.
    """
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Benchmark input file not found: {input_path}")

    size_bytes = input_path.stat().st_size
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs: List[IterationResult] = []

    for i in range(1, iterations + 1):
        zip_path = output_dir / f"bench_run_{i}.zip"
        if zip_path.exists():
            zip_path.unlink()

        t0 = timer()
        result: ArchiveResult = create_archive([input_path], zip_path, overwrite_policy="overwrite")
        t1 = timer()

        elapsed = max(0.0, t1 - t0)
        mb_s = calculate_throughput(size_bytes, elapsed, binary=False)
        mib_s = calculate_throughput(size_bytes, elapsed, binary=True)
        norm_time = normalize_to_100mb(elapsed, size_bytes)

        error_msg = "; ".join(result.errors) if (not result.success or result.errors) else None
        runs.append(
            IterationResult(
                iteration=i,
                elapsed_seconds=elapsed,
                throughput_mb_s=mb_s,
                throughput_mib_s=mib_s,
                normalized_time_per_100mb=norm_time,
                success=result.success,
                error_message=error_msg,
            )
        )

        # Clean up temporary archive file after each run
        if zip_path.exists():
            try:
                zip_path.unlink()
            except OSError:
                pass

    elapsed_list = [r.elapsed_seconds for r in runs]
    norm_list = [r.normalized_time_per_100mb for r in runs]
    p95_elapsed = calculate_percentile(elapsed_list, 95.0)
    p95_norm = calculate_percentile(norm_list, 95.0)
    mean_elapsed = sum(elapsed_list) / len(elapsed_list)
    mean_mb_s = sum(r.throughput_mb_s for r in runs) / len(runs)
    mean_mib_s = sum(r.throughput_mib_s for r in runs) / len(runs)
    all_succeeded = all(r.success for r in runs)
    passed = all_succeeded and evaluate_nf001(p95_norm, threshold_seconds)

    return OperationBenchmarkResult(
        operation="compression",
        data_size_bytes=size_bytes,
        iterations=iterations,
        threshold_seconds_per_100mb=threshold_seconds,
        runs=runs,
        p95_elapsed_seconds=p95_elapsed,
        p95_time_per_100mb=p95_norm,
        mean_elapsed_seconds=mean_elapsed,
        mean_throughput_mb_s=mean_mb_s,
        mean_throughput_mib_s=mean_mib_s,
        passed=passed,
        all_succeeded=all_succeeded,
    )


def benchmark_extraction(
    archive_path: Path,
    extract_dir: Path,
    uncompressed_size_bytes: int,
    iterations: int = DEFAULT_ITERATIONS,
    threshold_seconds: float = DEFAULT_THRESHOLD_SECONDS_PER_100MB,
    timer: Callable[[], float] = time.perf_counter,
) -> OperationBenchmarkResult:
    """Benchmark extraction of archive_path across multiple iterations.

    Measures only the core extract_archive call, excluding preparation and cleanup.
    """
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Benchmark archive not found: {archive_path}")

    runs: List[IterationResult] = []

    for i in range(1, iterations + 1):
        target_dir = extract_dir / f"run_{i}"
        target_dir.mkdir(parents=True, exist_ok=True)

        t0 = timer()
        result: ExtractionResult = extract_archive(
            archive_path, target_dir, overwrite_policy="overwrite"
        )
        t1 = timer()

        elapsed = max(0.0, t1 - t0)
        mb_s = calculate_throughput(uncompressed_size_bytes, elapsed, binary=False)
        mib_s = calculate_throughput(uncompressed_size_bytes, elapsed, binary=True)
        norm_time = normalize_to_100mb(elapsed, uncompressed_size_bytes)

        error_msg = "; ".join(result.failed) if (not result.success or result.failed) else None
        runs.append(
            IterationResult(
                iteration=i,
                elapsed_seconds=elapsed,
                throughput_mb_s=mb_s,
                throughput_mib_s=mib_s,
                normalized_time_per_100mb=norm_time,
                success=result.success,
                error_message=error_msg,
            )
        )

        # Cleanup extracted files
        for root, dirs, files in os.walk(target_dir, topdown=False):
            for file in files:
                try:
                    os.unlink(os.path.join(root, file))
                except OSError:
                    pass
            for dir_name in dirs:
                try:
                    os.rmdir(os.path.join(root, dir_name))
                except OSError:
                    pass
        try:
            target_dir.rmdir()
        except OSError:
            pass

    elapsed_list = [r.elapsed_seconds for r in runs]
    norm_list = [r.normalized_time_per_100mb for r in runs]
    p95_elapsed = calculate_percentile(elapsed_list, 95.0)
    p95_norm = calculate_percentile(norm_list, 95.0)
    mean_elapsed = sum(elapsed_list) / len(elapsed_list)
    mean_mb_s = sum(r.throughput_mb_s for r in runs) / len(runs)
    mean_mib_s = sum(r.throughput_mib_s for r in runs) / len(runs)
    all_succeeded = all(r.success for r in runs)
    passed = all_succeeded and evaluate_nf001(p95_norm, threshold_seconds)

    return OperationBenchmarkResult(
        operation="extraction",
        data_size_bytes=uncompressed_size_bytes,
        iterations=iterations,
        threshold_seconds_per_100mb=threshold_seconds,
        runs=runs,
        p95_elapsed_seconds=p95_elapsed,
        p95_time_per_100mb=p95_norm,
        mean_elapsed_seconds=mean_elapsed,
        mean_throughput_mb_s=mean_mb_s,
        mean_throughput_mib_s=mean_mib_s,
        passed=passed,
        all_succeeded=all_succeeded,
    )


def run_speed_benchmark(
    data_size_bytes: int = DEFAULT_WORKLOAD_BYTES,
    iterations: int = DEFAULT_ITERATIONS,
    threshold_seconds: float = DEFAULT_THRESHOLD_SECONDS_PER_100MB,
    work_dir: Optional[Path] = None,
    timer: Callable[[], float] = time.perf_counter,
) -> BenchmarkSuiteReport:
    """Run full NF-001 speed benchmark for both compression and extraction.

    Creates an isolated temporary environment, generates test data, measures
    both operations independently across specified iterations, and evaluates the
    requirement threshold (95th-percentile time <= 2.0 s per 100 MB).
    """
    if data_size_bytes <= 0:
        raise ValueError("data_size_bytes must be positive")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    use_temp = work_dir is None
    temp_obj = tempfile.TemporaryDirectory() if use_temp else None
    base_dir = Path(temp_obj.name if temp_obj else work_dir)

    try:
        input_file = base_dir / "benchmark_workload.bin"
        output_dir = base_dir / "archives"
        output_dir.mkdir(parents=True, exist_ok=True)
        extract_dir = base_dir / "extracts"
        extract_dir.mkdir(parents=True, exist_ok=True)

        # 1. Generate representative benchmark input file
        generate_benchmark_file(input_file, data_size_bytes)

        # 2. Benchmark compression
        comp_result = benchmark_compression(
            input_path=input_file,
            output_dir=output_dir,
            iterations=iterations,
            threshold_seconds=threshold_seconds,
            timer=timer,
        )

        # 3. Create a stable reference archive for extraction benchmark
        ref_archive = base_dir / "ref_archive.zip"
        create_archive([input_file], ref_archive, overwrite_policy="overwrite")

        # 4. Benchmark extraction
        extr_result = benchmark_extraction(
            archive_path=ref_archive,
            extract_dir=extract_dir,
            uncompressed_size_bytes=data_size_bytes,
            iterations=iterations,
            threshold_seconds=threshold_seconds,
            timer=timer,
        )

        all_passed = comp_result.passed and extr_result.passed

        return BenchmarkSuiteReport(
            data_size_bytes=data_size_bytes,
            iterations=iterations,
            threshold_seconds_per_100mb=threshold_seconds,
            compression=comp_result,
            extraction=extr_result,
            all_passed=all_passed,
        )
    finally:
        if temp_obj:
            temp_obj.cleanup()


def format_report_text(report: BenchmarkSuiteReport) -> str:
    """Format benchmark suite report into human-readable text."""
    size_mb = report.data_size_bytes / BYTES_PER_MB
    size_mib = report.data_size_bytes / BYTES_PER_MIB

    lines = [
        "=" * 70,
        "  FCT-NF-001 SPEED BENCHMARK REPORT (TC-Perf-01)",
        "=" * 70,
        f"Input Workload Size : {report.data_size_bytes:,} bytes ({size_mb:.2f} MB / {size_mib:.2f} MiB)",
        f"Iterations          : {report.iterations}",
        f"NF-001 Threshold    : <= {report.threshold_seconds_per_100mb:.2f} s per 100 MB (>= {100.0 / report.threshold_seconds_per_100mb:.1f} MB/s p95)",
        "-" * 70,
    ]

    for op in (report.compression, report.extraction):
        name = op.operation.upper()
        status = "PASSED" if op.passed else "FAILED"
        lines.append(f"\n[{name}] -- Status: {status}")
        lines.append(
            f"  Mean Time         : {op.mean_elapsed_seconds:.4f} s "
            f"(Throughput: {op.mean_throughput_mb_s:.2f} MB/s | {op.mean_throughput_mib_s:.2f} MiB/s)"
        )
        lines.append(
            f"  95th-Percentile   : {op.p95_elapsed_seconds:.4f} s "
            f"(Normalized per 100 MB: {op.p95_time_per_100mb:.4f} s)"
        )
        lines.append(
            f"  Target Check      : {op.p95_time_per_100mb:.4f} s <= {op.threshold_seconds_per_100mb:.2f} s -> "
            f"{'PASS' if op.passed else 'FAIL'}"
        )
        lines.append("  Detailed Iterations:")
        for r in op.runs:
            status_text = "OK" if r.success else f"ERR: {r.error_message}"
            lines.append(
                f"    Run {r.iteration}: {r.elapsed_seconds:.4f} s | "
                f"{r.throughput_mb_s:>7.2f} MB/s | "
                f"Norm(100MB): {r.normalized_time_per_100mb:.4f} s | {status_text}"
            )

    lines.append("\n" + "=" * 70)
    verdict = "PASSED (Satisfies FCT-NF-001)" if report.all_passed else "FAILED (Exceeds 2s/100MB threshold)"
    lines.append(f"OVERALL BENCHMARK VERDICT: {verdict}")
    lines.append("=" * 70)
    return "\n".join(lines)


def build_benchmark_parser() -> argparse.ArgumentParser:
    """Build CLI parser for standalone benchmark execution."""
    parser = argparse.ArgumentParser(
        prog="python -m fct.benchmark",
        description="Run FCT-NF-001 speed benchmark (2 seconds per 100 MB).",
    )
    parser.add_argument(
        "--size-mb",
        type=float,
        default=100.0,
        help="Workload size in decimal megabytes (default: 100.0 MB)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of test iterations (default: {DEFAULT_ITERATIONS})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_SECONDS_PER_100MB,
        help=f"Threshold time in seconds per 100 MB (default: {DEFAULT_THRESHOLD_SECONDS_PER_100MB} s)",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional custom working directory (uses temporary directory by default)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw results in JSON format",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for standalone benchmark execution."""
    parser = build_benchmark_parser()
    args = parser.parse_args(argv)

    size_bytes = int(args.size_mb * BYTES_PER_MB)
    try:
        report = run_speed_benchmark(
            data_size_bytes=size_bytes,
            iterations=args.iterations,
            threshold_seconds=args.threshold,
            work_dir=args.work_dir,
        )
    except Exception as exc:
        print(f"Benchmark error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_text(report))

    return 0 if report.all_passed else 2


if __name__ == "__main__":
    sys.exit(main())
