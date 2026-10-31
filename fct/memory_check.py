"""
Memory Benchmark Module for NF-002
Owner: Adarsh Prakash
Maps to requirement: FCT-NF-002 (TC-Perf-02)
SAD Section: 3.1, 4.4

Requirement FCT-NF-002:
    "The application shall use no more than 512 MB peak working memory
    for a 1 GB sequential test workload under reference conditions."

This module measures peak process working set memory (RSS) and Python heap
allocations during sequential compression and extraction operations.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .archive_writer import create_archive
from .extraction import extract_archive
from .models import ArchiveResult, ExtractionResult
from .resource_manager import MemoryTracker, cleanup_temp

# Default constants
BYTES_PER_MB = 1_000_000  # Decimal megabyte (SI)
BYTES_PER_MIB = 1_048_576  # Binary mebibyte (IEC)
DEFAULT_WORKLOAD_BYTES = 1_000_000_000  # 1 GB (1,000 MB)
DEFAULT_THRESHOLD_BYTES = 512 * BYTES_PER_MB  # 512 MB limit (FCT-NF-002)


@dataclass
class OperationMemoryResult:
    """Memory measurement result for a single operation."""
    operation: str
    workload_bytes: int
    elapsed_seconds: float
    initial_process_bytes: int
    peak_process_bytes: int
    peak_python_bytes: int
    threshold_bytes: int
    passed: bool
    success: bool
    error_message: Optional[str] = None

    @property
    def peak_process_mb(self) -> float:
        return self.peak_process_bytes / BYTES_PER_MB

    @property
    def peak_process_mib(self) -> float:
        return self.peak_process_bytes / BYTES_PER_MIB

    @property
    def peak_python_mb(self) -> float:
        return self.peak_python_bytes / BYTES_PER_MB

    @property
    def threshold_mb(self) -> float:
        return self.threshold_bytes / BYTES_PER_MB


@dataclass
class MemorySuiteReport:
    """Overall benchmark report covering compression and extraction."""
    workload_bytes: int
    threshold_bytes: int
    is_full_1gb_workload: bool
    compression: OperationMemoryResult
    extraction: OperationMemoryResult
    all_passed: bool
    workload_note: str = ""


def evaluate_nf002(peak_memory_bytes: int, threshold_bytes: int = DEFAULT_THRESHOLD_BYTES) -> bool:
    """Evaluate whether peak memory satisfies FCT-NF-002 (<= 512 MB)."""
    return peak_memory_bytes <= threshold_bytes


def generate_workload_file(target_path: Path, size_bytes: int) -> Path:
    """Generate a reproducible, representative sequential workload file of exact size.

    Streams data in 64 KB chunks to ensure that file generation itself
    does not consume large working memory.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # 1 KB representative pattern
    line = b"FCT-NF-002 memory benchmark payload: sequential streaming data verification.\n"
    block = (line * (1024 // len(line) + 1))[:1024]
    chunk_size = 64 * 1024  # 64 KB streaming buffer
    chunk = block * (chunk_size // 1024)

    written = 0
    with open(target_path, "wb") as f:
        while written < size_bytes:
            to_write = min(len(chunk), size_bytes - written)
            f.write(chunk[:to_write])
            written += to_write

    return target_path


def benchmark_compression_memory(
    input_path: Path,
    output_dir: Path,
    threshold_bytes: int = DEFAULT_THRESHOLD_BYTES,
) -> OperationMemoryResult:
    """Benchmark peak memory of compression on input_path.

    Measures only the core create_archive call, excluding preparation and cleanup.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    size_bytes = input_path.stat().st_size
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "bench_mem.zip"
    if zip_path.exists():
        zip_path.unlink()

    with MemoryTracker() as tracker:
        res: ArchiveResult = create_archive([input_path], zip_path, overwrite_policy="overwrite")

    error_msg = "; ".join(res.errors) if (not res.success or res.errors) else None
    passed = res.success and evaluate_nf002(tracker.peak_process_bytes, threshold_bytes)

    return OperationMemoryResult(
        operation="compression",
        workload_bytes=size_bytes,
        elapsed_seconds=tracker.elapsed_seconds,
        initial_process_bytes=tracker.initial_process_bytes,
        peak_process_bytes=tracker.peak_process_bytes,
        peak_python_bytes=tracker.peak_python_bytes,
        threshold_bytes=threshold_bytes,
        passed=passed,
        success=res.success,
        error_message=error_msg,
    )


def benchmark_extraction_memory(
    archive_path: Path,
    extract_dir: Path,
    uncompressed_size_bytes: int,
    threshold_bytes: int = DEFAULT_THRESHOLD_BYTES,
) -> OperationMemoryResult:
    """Benchmark peak memory of extraction on archive_path.

    Measures only the core extract_archive call, excluding preparation and cleanup.
    """
    archive_path = Path(archive_path)
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with MemoryTracker() as tracker:
        res: ExtractionResult = extract_archive(archive_path, extract_dir, overwrite_policy="overwrite")

    error_msg = "; ".join(res.failed) if (not res.success or res.failed) else None
    passed = res.success and evaluate_nf002(tracker.peak_process_bytes, threshold_bytes)

    return OperationMemoryResult(
        operation="extraction",
        workload_bytes=uncompressed_size_bytes,
        elapsed_seconds=tracker.elapsed_seconds,
        initial_process_bytes=tracker.initial_process_bytes,
        peak_process_bytes=tracker.peak_process_bytes,
        peak_python_bytes=tracker.peak_python_bytes,
        threshold_bytes=threshold_bytes,
        passed=passed,
        success=res.success,
        error_message=error_msg,
    )


def run_memory_benchmark(
    workload_bytes: int = DEFAULT_WORKLOAD_BYTES,
    threshold_bytes: int = DEFAULT_THRESHOLD_BYTES,
    work_dir: Optional[Path] = None,
) -> MemorySuiteReport:
    """Run full NF-002 memory benchmark for compression and extraction.

    Streams a sequential workload file of exact workload_bytes, measures
    peak process working set and Python heap during compression and extraction,
    and cleans up all temporary artifacts safely.
    """
    if workload_bytes <= 0:
        raise ValueError("workload_bytes must be positive")
    if threshold_bytes <= 0:
        raise ValueError("threshold_bytes must be positive")

    use_temp = work_dir is None
    temp_obj = tempfile.TemporaryDirectory() if use_temp else None
    base_dir = Path(temp_obj.name if temp_obj else work_dir)

    is_full_1gb = workload_bytes >= DEFAULT_WORKLOAD_BYTES
    note = (
        "Full 1 GB (>= 1,000,000,000 bytes) workload tested."
        if is_full_1gb
        else f"Partial workload tested ({workload_bytes:,} bytes). Full 1 GB requirement not directly exercised."
    )

    try:
        input_file = base_dir / "workload.bin"
        output_dir = base_dir / "archives"
        output_dir.mkdir(parents=True, exist_ok=True)
        extract_dir = base_dir / "extracts"
        extract_dir.mkdir(parents=True, exist_ok=True)

        # 1. Generate workload
        generate_workload_file(input_file, workload_bytes)

        # 2. Benchmark compression memory
        comp_res = benchmark_compression_memory(
            input_path=input_file,
            output_dir=output_dir,
            threshold_bytes=threshold_bytes,
        )

        # 3. Create reference archive for extraction test
        ref_archive = base_dir / "ref_archive.zip"
        create_archive([input_file], ref_archive, overwrite_policy="overwrite")

        # 4. Benchmark extraction memory
        extr_res = benchmark_extraction_memory(
            archive_path=ref_archive,
            extract_dir=extract_dir,
            uncompressed_size_bytes=workload_bytes,
            threshold_bytes=threshold_bytes,
        )

        all_passed = comp_res.passed and extr_res.passed

        return MemorySuiteReport(
            workload_bytes=workload_bytes,
            threshold_bytes=threshold_bytes,
            is_full_1gb_workload=is_full_1gb,
            compression=comp_res,
            extraction=extr_res,
            all_passed=all_passed,
            workload_note=note,
        )
    finally:
        if temp_obj:
            temp_obj.cleanup()
        else:
            # Clean up manually if custom work_dir was used
            cleanup_temp([base_dir / "workload.bin", base_dir / "ref_archive.zip"])


def format_report_text(report: MemorySuiteReport) -> str:
    """Format memory suite report into readable text."""
    size_mb = report.workload_bytes / BYTES_PER_MB
    size_mib = report.workload_bytes / BYTES_PER_MIB
    thresh_mb = report.threshold_bytes / BYTES_PER_MB

    lines = [
        "=" * 70,
        "  FCT-NF-002 MEMORY BENCHMARK REPORT (TC-Perf-02)",
        "=" * 70,
        f"Workload Size       : {report.workload_bytes:,} bytes ({size_mb:.2f} MB / {size_mib:.2f} MiB)",
        f"1 GB Target Status  : {'YES - Full 1 GB tested' if report.is_full_1gb_workload else 'PARTIAL - Sub-1GB workload'}",
        f"NF-002 Threshold    : <= {thresh_mb:.1f} MB peak memory",
        f"Note                : {report.workload_note}",
        "-" * 70,
    ]

    for op in (report.compression, report.extraction):
        name = op.operation.upper()
        status = "PASSED" if op.passed else "FAILED"
        lines.append(f"\n[{name}] -- Status: {status}")
        lines.append(f"  Elapsed Time      : {op.elapsed_seconds:.2f} s")
        lines.append(
            f"  Peak Process (RSS): {op.peak_process_mb:.2f} MB ({op.peak_process_mib:.2f} MiB) "
            f"[{op.peak_process_bytes:,} bytes]"
        )
        lines.append(
            f"  Peak Python Heap  : {op.peak_python_mb:.2f} MB [{op.peak_python_bytes:,} bytes]"
        )
        lines.append(
            f"  Threshold Check   : {op.peak_process_mb:.2f} MB <= {op.threshold_mb:.1f} MB -> "
            f"{'PASS' if op.passed else 'FAIL'}"
        )

    lines.append("\n" + "=" * 70)
    verdict = "PASSED (Satisfies FCT-NF-002)" if report.all_passed else "FAILED (Exceeds 512 MB threshold)"
    lines.append(f"OVERALL MEMORY VERDICT: {verdict}")
    lines.append("=" * 70)
    return "\n".join(lines)


def build_memory_parser() -> argparse.ArgumentParser:
    """Build CLI parser for standalone memory benchmark execution."""
    parser = argparse.ArgumentParser(
        prog="python -m fct.memory_check",
        description="Run FCT-NF-002 memory benchmark (512 MB limit for 1 GB workload).",
    )
    parser.add_argument(
        "--size-mb",
        type=float,
        default=1000.0,
        help="Workload size in decimal megabytes (default: 1000.0 MB / 1 GB)",
    )
    parser.add_argument(
        "--threshold-mb",
        type=float,
        default=512.0,
        help="Memory threshold in MB (default: 512.0 MB)",
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
    """CLI entrypoint for standalone memory check."""
    parser = build_memory_parser()
    args = parser.parse_args(argv)

    size_bytes = int(args.size_mb * BYTES_PER_MB)
    threshold_bytes = int(args.threshold_mb * BYTES_PER_MB)

    try:
        report = run_memory_benchmark(
            workload_bytes=size_bytes,
            threshold_bytes=threshold_bytes,
            work_dir=args.work_dir,
        )
    except Exception as exc:
        print(f"Memory benchmark error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        data = asdict(report)
        print(json.dumps(data, indent=2))
    else:
        print(format_report_text(report))

    return 0 if report.all_passed else 2


if __name__ == "__main__":
    sys.exit(main())
