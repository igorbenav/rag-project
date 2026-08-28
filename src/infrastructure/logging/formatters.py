"""Log formatters, selected by the LOG_FORMAT setting."""

import json
import logging
from typing import Any, Dict

# Attributes LogRecord always carries; anything else was passed as `extra`.
_STANDARD_FIELDS = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


class TextFormatter(logging.Formatter):
    """Human-readable single line: timestamp, level, logger, message."""

    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s [%(levelname)8s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


class JSONFormatter(logging.Formatter):
    """One JSON object per line, for log collectors that parse rather than grep."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = {key: value for key, value in record.__dict__.items() if key not in _STANDARD_FIELDS}
        if extras:
            payload["context"] = extras

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_formatter(format_name: str) -> logging.Formatter:
    """Return the formatter named by LOG_FORMAT, defaulting to text."""
    return JSONFormatter() if format_name.lower() == "json" else TextFormatter()
