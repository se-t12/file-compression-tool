"""
Resource Manager
Owner: Aakash Agarwal
Maps to SAD component "Resource Manager". Implements: FCT-F-014 (cleanup).

Small enough to just implement directly rather than stub out.
"""
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger("fct.resource_manager")


def cleanup_temp(paths: Iterable[Path]) -> None:
    """
    Remove temporary files created during a compress/extract operation.

    Never raises -- a cleanup failure shouldn't crash an otherwise-successful
    operation. Failures are logged (path + reason only, no file contents,
    per FCT-SR-004).
    """
    for path in paths:
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
        except OSError as exc:
            logger.warning("cleanup failed for %s: %s", path, exc)
