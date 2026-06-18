"""Logging setup: detailed rotating file log + quiet lifecycle console.

The file captures everything at DEBUG with a `run·contact` context column; the
console stays quiet by default (only `gifty.request` lifecycle lines + errors)
unless `settings.debug` is set, which mirrors the full file detail to stderr.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings

# Logger that carries the four lifecycle shapes shown on the quiet console.
REQUEST_LOGGER = "gifty.request"

FILE_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(runctx)s | %(message)s"
CONSOLE_FORMAT = "%(levelname)s | %(message)s"

# Chatty libraries pinned to WARNING everywhere (file + console). httpcore/httpx
# emit a DEBUG line per request phase, which floods the file log otherwise.
NOISY_LIBS = (
    "httpx",
    "httpcore",
    "anthropic",
    "google",
    "google_genai",
    "google.genai",
    "urllib3",
)


class RunContextFilter(logging.Filter):
    """Guarantee every record has a `runctx` attribute for the file format."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "runctx"):
            record.runctx = "-"
        return True


class LifecycleFilter(logging.Filter):
    """Console gate: pass lifecycle (`gifty.request`) records and errors only."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name == REQUEST_LOGGER or record.levelno >= logging.ERROR


def setup_logging() -> None:
    """Configure root logging; idempotent so repeated lifespans stay clean."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    Path(settings.log_path).parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.log_path, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT))
    file_handler.addFilter(RunContextFilter())
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    if settings.debug:
        console.setLevel(logging.DEBUG)
        console.addFilter(RunContextFilter())
    else:
        console.setLevel(logging.INFO)
        console.addFilter(LifecycleFilter())
    root.addHandler(console)

    for lib in NOISY_LIBS:
        logging.getLogger(lib).setLevel(logging.WARNING)


def request_logger() -> logging.Logger:
    """Logger for lifecycle lines (`received → processing → completed/failed`)."""
    return logging.getLogger(REQUEST_LOGGER)
