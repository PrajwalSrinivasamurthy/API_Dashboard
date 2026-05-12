"""File + console logging: dev (verbose) and separate audit stream for IT."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import get_settings

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_DEV_LOG_MAX_BYTES = 10 * 1024 * 1024
_DEV_LOG_BACKUPS = 5
_AUDIT_LOG_MAX_BYTES = 10 * 1024 * 1024
_AUDIT_LOG_BACKUPS = 10
_TIMING_LOG_MAX_BYTES = 10 * 1024 * 1024
_TIMING_LOG_BACKUPS = 10

_configured = False


def _build_rotating_handler(path: Path, *, max_bytes: int, backups: int) -> RotatingFileHandler:
    return RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backups,
        encoding="utf-8",
    )


def _parse_level(name: str) -> int:
    mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return mapping.get((name or "INFO").strip().upper(), logging.INFO)


def configure_logging() -> None:
    """Configure app and audit logging once."""
    global _configured
    if _configured:
        return
    _configured = True
    settings = get_settings()
    if not settings.log_to_files:
        _console_only()
        return

    log_root = Path(settings.log_dir)
    if not log_root.is_absolute():
        log_root = _BACKEND_DIR / log_root
    log_root.mkdir(parents=True, exist_ok=True)

    dev_path = log_root / settings.dev_log_filename
    audit_path = log_root / settings.audit_log_filename
    timing_path = log_root / settings.timing_log_filename

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    dev_handler = _build_rotating_handler(
        dev_path,
        max_bytes=_DEV_LOG_MAX_BYTES,
        backups=_DEV_LOG_BACKUPS,
    )
    dev_handler.setLevel(_parse_level(settings.log_level))
    dev_handler.setFormatter(fmt)

    audit_handler = _build_rotating_handler(
        audit_path,
        max_bytes=_AUDIT_LOG_MAX_BYTES,
        backups=_AUDIT_LOG_BACKUPS,
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(logging.Formatter("%(message)s"))

    timing_handler = _build_rotating_handler(
        timing_path,
        max_bytes=_TIMING_LOG_MAX_BYTES,
        backups=_TIMING_LOG_BACKUPS,
    )
    timing_handler.setLevel(logging.INFO)
    timing_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(_parse_level(settings.log_level))
    console.setFormatter(fmt)

    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.setLevel(_parse_level(settings.log_level))
    app_logger.addHandler(dev_handler)
    app_logger.addHandler(console)
    app_logger.propagate = False

    audit_logger = logging.getLogger("app.audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.INFO)
    audit_logger.addHandler(audit_handler)
    audit_logger.propagate = False

    timing_logger = logging.getLogger("app.timing")
    timing_logger.handlers.clear()
    timing_logger.setLevel(logging.INFO)
    timing_logger.addHandler(timing_handler)
    timing_logger.propagate = False

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _console_only() -> None:
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(console)
    app_logger.propagate = False
    audit_logger = logging.getLogger("app.audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.INFO)
    audit_logger.addHandler(console)
    audit_logger.propagate = False
    timing_logger = logging.getLogger("app.timing")
    timing_logger.handlers.clear()
    timing_logger.setLevel(logging.INFO)
    timing_logger.addHandler(console)
    timing_logger.propagate = False
