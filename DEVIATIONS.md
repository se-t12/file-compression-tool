# Deviations from the Submitted Documents

**Project:** File Compression Tool (Basic ZIP Implementation)
**Compared against:** SRS v1.0, SAD v1.0, Test Plan v1.0
**Code reviewed:** `main` branch, 23 Oct 2026 (end of Sprint 1)

This file lists where the implementation differs from what the SRS, SAD and Test Plan describe, and what we plan to do about each item. Status values: **Open** = a requirement is not fully met yet and is planned for Sprint 2; **Accepted** = a deliberate difference we intend to keep.

## 1. SRS: requirements not fully met yet

| Requirement | Documented | Implemented | Status |
|---|---|---|---|
| FCT-F-005 | Visible progress or status while a multi-file compression runs | Only a final summary is printed after compression finishes. No live progress. | Open, Sprint 2 |
| FCT-F-001 (acceptance criterion) | Selected inputs are displayed before compression starts | The CLI accepts the inputs but does not echo them before compressing | Open, Sprint 2 |
| FCT-F-003 | Relative directory structure of selected folders is preserved | Files and nested folders are preserved. Empty folders are not stored (only files are archived, and directory entries are skipped on extraction). | Accepted |
| FCT-NF-001 | Speed (2 s per 100 MB) target met | Files are streamed, but speed target has not been measured on this branch | Open, Sprint 2 |
| FCT-NF-002 | Memory (512 MB) target met | Automated benchmark in `fct/memory_check.py` and memory monitoring in `fct/resource_manager.py`. Measured peak working set is ~30.3 MB (compression) and ~50.2 MB (extraction) on full 1 GB workload, meeting the <= 512 MB threshold. | Closed, Sprint 2 |

| FCT-NF-004 | SHA-256 and size preserved over a compress-extract round trip | No automated round-trip test exists yet | Open, Sprint 2 |
| FCT-NF-005 | Path handling verified on each supported OS | Automated tests currently run on Linux (CI, Python 3.11) only | Open, Sprint 2 |

## 2. SAD: design differences

| Area | SAD says | Implemented | Status |
|---|---|---|---|
| Component structure | Separate Input Selector (Path Module), Compression Module, File I/O Module | Folded into one module, `archive_writer.py`. Input checks and relative-path handling are done there. | Accepted |
| Sequence Diagram 1 (compress) | Archive Writer calls the Integrity Module to hash each entry (SHA-256) | Not done. Compression does not compute hashes. | Open, Sprint 2 |
| Integrity verification | Extraction verifies entries with CRC and SHA-256 | `integrity.py` (SHA-256) is implemented and tested, but the CLI never passes expected hashes, so in normal use only the ZIP CRC-32 check runs (via `zipfile`) | Open, Sprint 2 |
| Archive Parser and Security Validator | Parser calls the Security Validator to validate structure | The parser validates structure itself using `zipfile`. The Security Validator is used only by extraction, for path checks. | Accepted |
| Error handling in the module APIs | `create_archive` raises FileNotFoundError / PermissionError. `extract_archive` raises PathTraversalError / BadZipFile. | Per-file problems are recorded in the result (`errors` / `failed`) instead of raising, so one bad file does not stop the whole run. Only invalid arguments raise `ValueError`. | Accepted |
| Function signatures | `extract_archive(archive_path, destination, overwrite_policy)` | Extra optional parameter `expected_hashes`. `ValidationResult` also has an extra `entries` field. Existing calls still work. | Accepted |
| Rename policy | "rename" (format not specified) | Compression names the output `name_1.zip`. Extraction names files `name (1).txt`. Two styles. | Accepted |
| Logging | Operational metadata only, optional log file | Metadata only (no file contents), printed to the console. The optional log file is not enabled. | Accepted |
| Python version | "Python 3.x" | Needs Python 3.10 or newer (a type annotation in `extraction.py` uses the `X \| None` syntax). CI runs 3.11. | Accepted |

## 3. Test Plan: differences

| Area | Test Plan says | Current state | Status |
|---|---|---|---|
| Test case IDs | Cases named like TC-Comp-01, mapped to requirement IDs | pytest tests have descriptive names and are not yet tagged with TC IDs. The RTM mapping is not written. | Open, Sprint 2 |
| Integration tests | CLI to Orchestrator to core modules | The existing CLI tests mock the orchestrator. Tests that run the real CLI end to end are not written yet. | Open, Sprint 2 |
| Performance (memory runs TC-Perf-02) | Memory runs against FCT-NF-002 (<= 512 MB for 1 GB) | Automated memory benchmark executed and verified on full 1 GB workload (30.3 MB comp / 50.2 MB extr peak working set) | Closed, Sprint 2 |
| Timing and usability checks | Timing runs against FCT-NF-001, manual CLI checklists | Open, Sprint 2 |

| Schedule | Milestone dates left as "to be scheduled" | Sprint 1: 19 to 23 Oct. Sprint 2: 26 to 30 Oct. | Closed |
| Test Plan PDF in repo | Part of the deliverables | Not committed yet | Open, Sprint 1 |

Automated tests currently cover each module (`tests/`), including path-traversal and malformed-archive cases, and run through GitHub Actions on every push.

## 4. Process differences

- The core modules (compression, extraction, integrity, archive parsing, path-traversal protection) were implemented and merged before the Sprint 1 window and before the GitHub Project board existed. The board was created on 23 Oct and records that work afterwards, with links to the pull requests that delivered it.
- Individual contributions are visible in the pull requests and commit history.

## 5. Cleanup items (no behaviour change)

- `archive_writer.py` still has an outdated line in its header comment saying the function is a TODO.
- `orchestrator.py` has unused imports (`resource_manager`, `ArchiveValidationError`).
