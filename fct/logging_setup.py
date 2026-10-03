"""
Logging Module
Owner: Aakash Agarwal
Maps to SAD component "Logging Module". Implements: FCT-SR-004.

Records operation metadata only (operation type, path, result) -- NEVER
file contents or archive payloads. See SAD section 4.4.
"""
import logging
from pathlib import Path
from typing import Optional


def configure_logging(log_path: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the root 'fct' logger."""
    logger = logging.getLogger("fct")
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_path is not None:
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_operation(logger: logging.Logger, operation: str, path: Path, result: str) -> None:
    """
    Log a single operation's metadata.

    IMPORTANT: `path` and `result` must never contain file contents -- only
    paths, counts, and status strings (e.g. "success", "rejected: path
    traversal"). This is what FCT-SR-004 requires.
    """
    logger.info("operation=%s path=%s result=%s", operation, path, result)
