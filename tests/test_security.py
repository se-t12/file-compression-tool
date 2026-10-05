"""
Tests for the Path / Security Validator.

Owner: Abhirup Roy
Tests FCT-SR-001 path traversal protection.
"""

import pytest
from pathlib import Path

from fct.security import resolve_safe_path
from fct.models import PathTraversalError


def test_normal_entry_returns_safe_path(tmp_path: Path):
    destination = tmp_path / "extracted"
    destination.mkdir()

    result = resolve_safe_path("file.txt", destination)

    assert result == destination.resolve() / "file.txt"


def test_nested_entry_returns_safe_path(tmp_path: Path):
    destination = tmp_path / "extracted"
    destination.mkdir()

    result = resolve_safe_path("subdir/file.txt", destination)

    assert result == destination.resolve() / "subdir/file.txt"


def test_parent_traversal_is_rejected(tmp_path: Path):
    destination = tmp_path / "extracted"
    destination.mkdir()

    with pytest.raises(PathTraversalError):
        resolve_safe_path("../etc/passwd", destination)


def test_deep_parent_traversal_is_rejected(tmp_path: Path):
    destination = tmp_path / "extracted"
    destination.mkdir()

    with pytest.raises(PathTraversalError):
        resolve_safe_path("../../etc/passwd", destination)


def test_absolute_path_is_rejected(tmp_path: Path):
    destination = tmp_path / "extracted"
    destination.mkdir()

    with pytest.raises(PathTraversalError):
        resolve_safe_path("/etc/passwd", destination)