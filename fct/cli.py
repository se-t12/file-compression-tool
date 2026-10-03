"""
CLI Interface
Owner: Aakash Agarwal
Maps to SAD component "CLI Interface" (UI/CLI Module). Implements: FCT-F-005, FCT-F-015, FCT-NF-003

Usage:
    python -m fct.cli compress file1.txt folder/ -o out.zip
    python -m fct.cli extract out.zip -d dest/
    python -m fct.cli list out.zip
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import orchestrator
from .logging_setup import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fct",
        description="File Compression Tool -- a basic ZIP-compatible archive utility.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compress_parser = subparsers.add_parser("compress", help="Compress files/folders into a ZIP archive")
    compress_parser.add_argument("inputs", nargs="+", type=Path, help="Files or folders to compress")
    compress_parser.add_argument("-o", "--output", required=True, type=Path, help="Output .zip path")
    compress_parser.add_argument(
        "--on-duplicate", choices=["overwrite", "skip", "rename"], default="skip",
        help="What to do if the output file already exists (default: skip)",
    )

    extract_parser = subparsers.add_parser("extract", help="Extract a ZIP archive")
    extract_parser.add_argument("archive", type=Path, help="Archive to extract")
    extract_parser.add_argument("-d", "--destination", required=True, type=Path, help="Destination folder")
    extract_parser.add_argument(
        "--on-duplicate", choices=["overwrite", "skip", "rename"], default="skip",
        help="What to do if an extracted file already exists (default: skip)",
    )

    list_parser = subparsers.add_parser("list", help="List the contents of a ZIP archive without extracting")
    list_parser.add_argument("archive", type=Path, help="Archive to inspect")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "compress":
            return orchestrator.compress_command(args.inputs, args.output, args.on_duplicate)
        if args.command == "extract":
            return orchestrator.extract_command(args.archive, args.destination, args.on_duplicate)
        if args.command == "list":
            return orchestrator.list_command(args.archive)
    except NotImplementedError as exc:
        # Friendly message while modules are still being implemented during Sprint 1.
        print(f"Not implemented yet: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001 -- top-level CLI boundary, FCT-NF-003
        print(f"Error: {exc}")
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
