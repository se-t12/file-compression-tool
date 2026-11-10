"""
Automated Round-Trip Correctness Test Suite
Requirement: FCT-NF-004 (TC-Corr-01)
Also covers: FCT-F-002, FCT-F-003, FCT-F-007, FCT-F-013, FCT-SR-003
Owner: Abhijna Marathe

Verifies that compressing a folder containing text, empty, and binary files,
and subsequently extracting it, preserves exact directory structure, file
sizes, and SHA-256 digests for every file.
"""
from pathlib import Path
import os
import pytest

from fct import archive_writer, extraction, integrity, cli


def collect_file_metadata(root: Path) -> dict[str, dict]:
    """Scan directory tree and return mapping of relative posix paths to metadata.
    
    Returns:
        dict: {
            "rel/path.txt": {
                "size": int,
                "sha256": str,
                "bytes": bytes,
            }
        }
    """
    metadata = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel_path = path.relative_to(root).as_posix()
            data = path.read_bytes()
            metadata[rel_path] = {
                "size": len(data),
                "sha256": integrity.compute_sha256(path),
                "bytes": data,
            }
    return metadata


@pytest.fixture
def complex_sample_folder(tmp_path: Path) -> Path:
    """Creates a realistic, complex test folder with text and binary files."""
    src = tmp_path / "dataset"
    src.mkdir(parents=True)

    # 1. Plain ASCII text file
    (src / "readme.txt").write_text("Hello, this is a plain text file for testing.\nLine 2.\n")

    # 2. UTF-8 multi-byte unicode text file
    (src / "unicode_utf8.txt").write_text(
        "Unicode test: 🚀 Antigravity compression — \u0928\u092e\u0938\u094d\u0924\u0947 \u2014 \u4e16\u754c\n",
        encoding="utf-8",
    )

    # 3. Empty file (edge case)
    (src / "empty.txt").write_bytes(b"")

    # 4. Binary file with all 256 byte values repeated
    all_bytes = bytes(range(256)) * 8  # 2048 bytes
    (src / "all_bytes.bin").write_bytes(all_bytes)

    # 5. Larger binary file (>100KB, tests chunked streaming)
    # Repeated deterministic pseudo-binary sequence
    large_pattern = b"\x00\xff\x7f\x80\xaa\x55\x12\x34\xde\xad\xbe\xef" * 10000  # 120 KB
    (src / "stream_chunked.bin").write_bytes(large_pattern)

    # 6. Nested folder structure with documents and binary blobs
    nested_dir = src / "nested" / "sub1" / "sub2"
    nested_dir.mkdir(parents=True)
    (nested_dir / "deep_doc.md").write_text("# Deep Document\nNested markdown content.\n")
    (nested_dir / "payload.dat").write_bytes(os.urandom(8192))

    # 7. Sibling directory with mixed files
    assets_dir = src / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "config.json").write_text('{"archive": "zip", "tested": true, "code": 200}\n')
    (assets_dir / "sample.ico").write_bytes(b"\x00\x00\x01\x00\x01\x00" + b"\xcc" * 256)

    return src


def test_round_trip_mixed_folder_sizes_and_sha256(tmp_path: Path, complex_sample_folder: Path):
    """TC-Corr-01: Compress complex folder with text and binary files, extract, and
    verify every file's size and SHA-256 digest match original exactly.
    """
    archive_path = tmp_path / "test_roundtrip.zip"
    dest_path = tmp_path / "extracted_out"

    # Step 1: Collect ground-truth metadata before compression
    original_meta = collect_file_metadata(complex_sample_folder)
    assert len(original_meta) >= 7

    # Step 2: Compress using archive_writer
    compress_res = archive_writer.create_archive(
        input_paths=[complex_sample_folder],
        output_path=archive_path,
        overwrite_policy="skip",
    )
    assert compress_res.success is True
    assert compress_res.entries_written == len(original_meta)
    assert archive_path.exists()

    # Step 3: Extract using extraction module
    extract_res = extraction.extract_archive(
        archive_path=archive_path,
        destination=dest_path,
        overwrite_policy="skip",
    )
    assert extract_res.success is True
    assert len(extract_res.failed) == 0
    assert len(extract_res.extracted) == len(original_meta)

    # Note: archive_writer preserves relative to input folder's parent (FCT-F-003),
    # so entries are stored under 'dataset/...'
    extracted_dataset_root = dest_path / "dataset"
    assert extracted_dataset_root.is_dir()

    extracted_meta = collect_file_metadata(extracted_dataset_root)

    # Step 4: Strict comparison of file list, sizes, and SHA-256
    assert set(extracted_meta.keys()) == set(original_meta.keys()), (
        f"Mismatch in relative paths:\n"
        f"Missing: {set(original_meta.keys()) - set(extracted_meta.keys())}\n"
        f"Extra: {set(extracted_meta.keys()) - set(original_meta.keys())}"
    )

    for rel_path, orig_info in original_meta.items():
        extr_info = extracted_meta[rel_path]

        # Exact file size match
        assert extr_info["size"] == orig_info["size"], (
            f"Size mismatch for '{rel_path}': expected {orig_info['size']} bytes, "
            f"got {extr_info['size']} bytes"
        )

        # Exact SHA-256 hash match
        assert extr_info["sha256"] == orig_info["sha256"], (
            f"SHA-256 mismatch for '{rel_path}': expected {orig_info['sha256']}, "
            f"got {extr_info['sha256']}"
        )

        # Exact byte contents match (FCT-F-013)
        assert extr_info["bytes"] == orig_info["bytes"], (
            f"Byte contents mismatch for '{rel_path}'"
        )


def test_round_trip_cli_execution(tmp_path: Path, complex_sample_folder: Path, capsys):
    """TC-Corr-01 via CLI: Run compress and extract end-to-end via CLI and verify SHA-256."""
    archive_path = tmp_path / "cli_roundtrip.zip"
    dest_path = tmp_path / "cli_out"

    original_meta = collect_file_metadata(complex_sample_folder)

    # Compress via CLI
    compress_code = cli.main(["compress", str(complex_sample_folder), "-o", str(archive_path)])
    out_compress = capsys.readouterr().out
    assert compress_code == 0
    assert f"with {len(original_meta)} entries" in out_compress
    assert archive_path.exists()

    # Extract via CLI
    extract_code = cli.main(["extract", str(archive_path), "-d", str(dest_path)])
    out_extract = capsys.readouterr().out
    assert extract_code == 0
    assert f"Extracted {len(original_meta)} file(s)" in out_extract

    # Verify extracted structure and SHA-256
    extracted_root = dest_path / complex_sample_folder.name
    extracted_meta = collect_file_metadata(extracted_root)

    assert set(extracted_meta.keys()) == set(original_meta.keys())
    for rel_path, orig_info in original_meta.items():
        extr_info = extracted_meta[rel_path]
        assert extr_info["size"] == orig_info["size"]
        assert extr_info["sha256"] == orig_info["sha256"]
        assert integrity.verify_entry(extracted_root / rel_path, orig_info["sha256"]) is True


def test_round_trip_binary_exactness_all_byte_values(tmp_path: Path):
    """FCT-F-013: Verify binary exactness for arbitrary bytes, null bytes, EOF markers."""
    src = tmp_path / "bin_source"
    src.mkdir()

    # Byte values including EOF markers (0x1A on Windows, 0x04 on Unix), null bytes, 0xFF
    test_bytes = bytearray(range(256))
    test_bytes.extend(b"\x00" * 100)
    test_bytes.extend(b"\x1a\x04\xff\xfe\x00\x0a\x0d" * 50)
    test_bytes.extend(os.urandom(16384))

    bin_file = src / "tricky_binary.bin"
    bin_file.write_bytes(test_bytes)
    original_sha = integrity.compute_sha256(bin_file)

    archive = tmp_path / "binary_archive.zip"
    dest = tmp_path / "binary_dest"

    archive_writer.create_archive([bin_file], archive, overwrite_policy="overwrite")
    extraction.extract_archive(archive, dest, overwrite_policy="overwrite")

    extracted_file = dest / "tricky_binary.bin"
    assert extracted_file.exists()
    assert extracted_file.stat().st_size == len(test_bytes)
    assert integrity.compute_sha256(extracted_file) == original_sha
    assert extracted_file.read_bytes() == bytes(test_bytes)


def test_round_trip_multi_inputs_files_and_directories(tmp_path: Path):
    """Compress multiple independent files and a folder together, extract and verify."""
    standalone_text = tmp_path / "single.txt"
    standalone_text.write_text("standalone text content\n")

    standalone_bin = tmp_path / "single.dat"
    standalone_bin.write_bytes(b"\xde\xad\xbe\xef" * 64)

    folder = tmp_path / "batch_folder"
    folder.mkdir()
    (folder / "item1.txt").write_text("item 1")
    (folder / "item2.bin").write_bytes(b"\x01\x02\x03\x04")

    archive = tmp_path / "multi_inputs.zip"
    dest = tmp_path / "multi_dest"

    res = archive_writer.create_archive(
        [standalone_text, standalone_bin, folder],
        archive,
        overwrite_policy="skip",
    )
    assert res.success is True
    assert res.entries_written == 4

    ext_res = extraction.extract_archive(archive, dest)
    assert ext_res.success is True
    assert len(ext_res.extracted) == 4

    # Verify each file's size and SHA-256
    assert (dest / "single.txt").read_text() == "standalone text content\n"
    assert integrity.compute_sha256(dest / "single.txt") == integrity.compute_sha256(standalone_text)

    assert (dest / "single.dat").read_bytes() == b"\xde\xad\xbe\xef" * 64
    assert integrity.compute_sha256(dest / "single.dat") == integrity.compute_sha256(standalone_bin)

    batch_root = dest / "batch_folder"
    assert (batch_root / "item1.txt").read_text() == "item 1"
    assert integrity.compute_sha256(batch_root / "item1.txt") == integrity.compute_sha256(folder / "item1.txt")

    assert (batch_root / "item2.bin").read_bytes() == b"\x01\x02\x03\x04"
    assert integrity.compute_sha256(batch_root / "item2.bin") == integrity.compute_sha256(folder / "item2.bin")


def test_round_trip_deep_nested_directories(tmp_path: Path):
    """Verify deep directory hierarchy (5 levels) preserves exact relative paths and hashes."""
    base = tmp_path / "hierarchy"
    deep = base / "a" / "b" / "c" / "d" / "e"
    deep.mkdir(parents=True)
    deep_file = deep / "level5.txt"
    deep_file.write_text("deepest level file content\n")

    archive = tmp_path / "deep.zip"
    dest = tmp_path / "deep_dest"

    archive_writer.create_archive([base], archive)
    extraction.extract_archive(archive, dest)

    extracted_deep = dest / "hierarchy" / "a" / "b" / "c" / "d" / "e" / "level5.txt"
    assert extracted_deep.exists()
    assert integrity.compute_sha256(extracted_deep) == integrity.compute_sha256(deep_file)
    assert extracted_deep.stat().st_size == deep_file.stat().st_size
