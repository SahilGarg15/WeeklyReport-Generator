"""
src/logger.py
─────────────
Rotating file + console logger shared across all modules.
Logs are written to logs/report_log.txt (tracks execution time,
LLM token usage, errors — as required by the spec).
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """Return a named logger wired to console + rotating file."""
    from src.config import cfg  # deferred to avoid circular import

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, cfg.get("log_level", "INFO").upper(), logging.INFO)
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    ch.setLevel(level)
    logger.addHandler(ch)

    # Rotating file  →  logs/report_log.txt
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    fh = RotatingFileHandler(
        log_dir / "report_log.txt",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(fh)

    return logger
