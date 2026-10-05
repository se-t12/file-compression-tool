"""
Path / Security Validator

Owner: Abhirup Roy
Maps to SAD component "Path/Security Validator" (security module).
Implements: FCT-SR-001 (path traversal protection)
"""

from pathlib import Path

from .models import PathTraversalError


def resolve_safe_path(entry_name: str, destination: Path) -> Path:
    """
    Resolve `entry_name` (a path as stored inside the ZIP archive) against
    `destination`, and return the safe absolute path to extract it to.

    Raises:
        PathTraversalError: if the resolved path would fall outside `destination`.
    """
    destination = destination.resolve()
    candidate = (destination / entry_name).resolve()

    try:
        candidate.relative_to(destination)
    except ValueError:
        raise PathTraversalError(
            f"Archive entry '{entry_name}' resolves outside destination"
        )

    return candidate