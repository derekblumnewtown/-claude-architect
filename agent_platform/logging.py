"""
agent_platform/logging.py
Structured JSON logging for all agent runs.
Every tool call, hook fire, and escalation gets logged here.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        if record.exc_info:
            log_data["exception"] = self.formatException(
                record.exc_info
            )
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    """
    Get a structured JSON logger.
    Usage: logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    **kwargs: Any,
) -> None:
    """
    Log a structured event with arbitrary key-value pairs.
    Usage: log_event(logger, "tool_called", tool="get_customer", input_id="123")
    """
    record = logging.LogRecord(
        name=logger.name,
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=event,
        args=(),
        exc_info=None,
    )
    record.extra = {"event": event, **kwargs}
    logger.handle(record)