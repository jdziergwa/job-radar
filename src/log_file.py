"""Persistent debug log for the LLM path (adapters, resolver, scorer).

The pipeline runs as a subprocess of the API whose output is not kept, so
failures there are otherwise invisible. Both processes append to one file.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = _PROJECT_ROOT / "logs" / "job-radar.log"

# Loggers whose DEBUG records go to the file even when the console is at INFO.
_DEBUG_LOGGERS = ("src.llm", "src.scorer")


def attach_file_log() -> Path | None:
    """Attach a rotating file handler to the root logger. Safe to call twice.

    Path comes from JOB_RADAR_LOG_FILE; set it to an empty string to disable.
    """
    raw = os.getenv("JOB_RADAR_LOG_FILE")
    if raw is not None and not raw.strip():
        return None
    path = Path(raw).expanduser() if raw else DEFAULT_LOG_PATH

    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == path.resolve():
            return path

    if not root.handlers:
        # Without any handler Python prints WARNING+ via its last-resort handler;
        # adding the file handler would silence that, so keep an explicit one.
        console = logging.StreamHandler()
        console.setLevel(logging.WARNING)
        root.addHandler(console)
    # Keep console output at its current verbosity while DEBUG flows to the file.
    console_level = root.level if root.level != logging.NOTSET else logging.WARNING
    for existing in root.handlers:
        if existing.level == logging.NOTSET:
            existing.setLevel(console_level)

    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] pid=%(process)d %(name)s: %(message)s"
    ))
    root.addHandler(handler)

    # A logger with its own level is not gated by the root level on propagation.
    for name in _DEBUG_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)
    return path
