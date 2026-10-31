# file-compression-tool

File Compression Tool (Basic ZIP implementation)

## Project Overview

This project is a standalone command-line software application that reads files and directories from local storage, compresses their contents into a ZIP archive, and extracts ZIP archives to a user-selected destination. It will be implemented in Python 3 using standard libraries such as `zipfile`, `hashlib`, and `argparse`.

## Team Members

- Adarsh Prakash (PES2UG24CS027)
- Aakash Agarwal (PES2UG24CS009)
- Abhijna Marathe (PES2UG24CS020)
- Abhirup Roy (PES2UG24CS025)

## Project Structure

```
fct/
  models.py           Shared data types (ArchiveResult, ExtractionResult, EntryInfo, ValidationResult)
  cli.py               CLI Interface (argparse) -- Aakash
  orchestrator.py       Command Orchestrator -- Aakash
  archive_writer.py     Compression -- Adarsh            [TODO: create_archive()]
  extraction.py         Extraction -- Abhijna             [TODO: extract_archive()]
  integrity.py          CRC/SHA-256 checks -- Abhijna     [TODO: compute_sha256(), verify_entry()]
  archive_parser.py     Listing/validation -- Abhirup     [TODO: validate_archive(), list_entries()]
  security.py           Path traversal protection -- Abhirup [TODO: resolve_safe_path()]
  resource_manager.py   Temp file cleanup -- Aakash
  logging_setup.py      Logging (metadata only) -- Aakash
tests/
  one test file per module above, mirroring the same names
.github/workflows/ci.yml   Runs pytest on every push
```

Each stub module (`archive_writer.py`, `extraction.py`, `integrity.py`, `archive_parser.py`, `security.py`) has a docstring with design notes and suggested test cases -- read that before you start.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
```

## Usage

```bash
python -m fct.cli compress file1.txt folder/ -o out.zip
python -m fct.cli extract out.zip -d dest/
python -m fct.cli list out.zip
python -m fct.cli memory-check --size-mb 1000 --threshold-mb 512
```

## Memory Benchmark (FCT-NF-002 / TC-Perf-02)

The tool provides an automated memory benchmark to verify compliance with non-functional requirement **FCT-NF-002** (peak working memory $\le$ 512 MB for a 1 GB workload):

```bash
# Run standard 1 GB (1,000 MB) memory benchmark
python -m fct.memory_check --size-mb 1000 --threshold-mb 512

# Or run via CLI:
python -m fct.cli memory-check --size-mb 1000 --threshold-mb 512

# Output raw metrics in JSON format
python -m fct.memory_check --size-mb 1000 --threshold-mb 512 --json
```

- **Operations Measured**: Streams a sequential test workload file of known size and measures peak process working set (RSS) and Python heap allocations during compression (`create_archive`) and extraction (`extract_archive`), excluding fixture setup and cleanup time.
- **Workload & Units**: Standard workload is 1 GB (1,000,000,000 bytes decimal / 953.67 MiB). Units are reported in decimal MB ($10^6$ bytes) and binary MiB ($2^{20}$ bytes).
- **Threshold Evaluation**: Checks that peak process working set remains $\le 512\text{ MB}$ ($512,000,000\text{ bytes}$) for both compression and extraction.
- **Actual Measured Results (1 GB Workload)**:
  - Compression: **30.30 MB** peak working set (elapsed ~8.45 s) $\rightarrow$ PASS
  - Extraction: **50.22 MB** peak working set (elapsed ~5.79 s) $\rightarrow$ PASS
- **Measurement Method**: Uses native OS APIs (`GetProcessMemoryInfo` on Windows, `/proc/self/statm` and `getrusage` on Unix) combined with high-frequency background sampling and Python `tracemalloc`.


## Running Tests

```bash
pytest -v
```

Placeholder tests for not-yet-implemented modules are marked `@pytest.mark.skip` so the suite stays green -- replace the placeholder in your owned `tests/test_*.py` file with real tests as you implement your module.

## CI/CD

Every push triggers `.github/workflows/ci.yml`, which installs dependencies and runs `pytest -v`. Check the **Actions** tab on GitHub after pushing -- a red X means something broke; fix it before building further on top.

## Requirements Traceability

See `Software Requirements Specification.pdf` and `Software Architecture and Design Specification.pdf` in this repo for the full SRS/SAD. Each module's docstring references the specific requirement IDs (e.g. `FCT-SR-001`) it implements.
