"""Application logging.

One console handler, an optional rotating file handler, and a formatter chosen
by LOG_FORMAT. Configured once, on first use.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Optional

from ..config.settings import get_settings
from .formatters import get_formatter

__all__ = ["get_logger", "configure_logging"]

_configured = False
_lock = Lock()


def _build_handlers() -> list[logging.Handler]:
    settings = get_settings()
    formatter = get_formatter(settings.LOG_FORMAT)
    handlers: list[logging.Handler] = []

    if settings.LOG_CONSOLE_ENABLED:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        handlers.append(console)

    if settings.LOG_FILE_ENABLED:
        path = Path(settings.LOG_FILE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(path, maxBytes=settings.LOG_FILE_MAX_SIZE, backupCount=settings.LOG_FILE_BACKUP_COUNT)
        rotating.setFormatter(formatter)
        handlers.append(rotating)

    return handlers or [logging.NullHandler()]


def configure_logging() -> None:
    """Install handlers on the root logger. Safe to call more than once."""
    global _configured

    with _lock:
        if _configured:
            return

        settings = get_settings()
        root = logging.getLogger()
        root.handlers.clear()
        for handler in _build_handlers():
            root.addHandler(handler)
        root.setLevel(settings.LOG_LEVEL_INT)

        # These log every request and every connection at INFO; useful when
        # chasing something specific, noise the rest of the time.
        for noisy in ("httpx", "httpcore", "asyncio", "watchfiles"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger.

    Pass `__name__`. The previous implementation guessed the caller's module by
    walking the stack, which returned "unknown" whenever it was called at
    module scope — which is most of the time.
    """
    configure_logging()
    return logging.getLogger(name or "app")
