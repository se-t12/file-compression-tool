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
python -m fct.cli benchmark --size-mb 100 --iterations 5
```

## Performance Benchmark (FCT-NF-001 / TC-Perf-01)

The tool provides an automated benchmark to verify compliance with non-functional requirement **FCT-NF-001** (95th-percentile elapsed time $\le$ 2.0 seconds per 100 MB):

```bash
# Run standard 100 MB benchmark (5 iterations)
python -m fct.benchmark --size-mb 100 --iterations 5

# Or run via CLI:
python -m fct.cli benchmark --size-mb 100 --iterations 5

# Output raw metrics in JSON format
python -m fct.benchmark --size-mb 100 --iterations 5 --json
```

- **Operations Measured**: Benchmarks compression (`create_archive`) and extraction (`extract_archive`) independently, excluding fixture generation, directory scanning, and cleanup time.
- **Input Size & Units**: Default size is 100 MB where 1 MB = 1,000,000 bytes (decimal SI standard). Throughput is reported in both decimal MB/s ($10^6$ B/s) and binary MiB/s ($2^{20}$ B/s).
- **Threshold Evaluation**: Computes the 95th-percentile elapsed time normalized to 100 MB across all iterations. The benchmark passes if both operations achieve $\le 2.0$ seconds per 100 MB ($\ge 50$ MB/s throughput at p95).
- **Measurement Conditions & Hardware**: Measures wall-clock time using `time.perf_counter()`. Measurements run in an isolated temporary directory and clean up automatically. Performance may vary depending on disk I/O, OS file caching, and CPU load.


## Running Tests

```bash
pytest -v
```

Placeholder tests for not-yet-implemented modules are marked `@pytest.mark.skip` so the suite stays green -- replace the placeholder in your owned `tests/test_*.py` file with real tests as you implement your module.

## CI/CD

Every push triggers `.github/workflows/ci.yml`, which installs dependencies and runs `pytest -v`. Check the **Actions** tab on GitHub after pushing -- a red X means something broke; fix it before building further on top.

## Requirements Traceability

See `Software Requirements Specification.pdf` and `Software Architecture and Design Specification.pdf` in this repo for the full SRS/SAD. Each module's docstring references the specific requirement IDs (e.g. `FCT-SR-001`) it implements.
