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

from dotenv import load_dotenv   
load_dotenv()                    


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

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Get a structured JSON logger.

    Reads LOG_LEVEL from .env to set the threshold:
        DEBUG   = 10 — show everything
        INFO    = 20 — show INFO and above
        WARNING = 30 — show WARNING and ERROR only
        ERROR   = 40 — show ERROR only

    Usage: logger = get_logger(__name__)
    """
    # Read log level from environment
    # Defaults to INFO if LOG_LEVEL not set in .env
    import os
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Convert string "WARNING" to logging.WARNING (30)
    # getattr looks up the attribute by name on the logging module
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    # Set level every time — not just on first creation
    # This ensures .env changes take effect immediately
    logger.setLevel(log_level)
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.DEBUG,
    **kwargs: Any,
) -> None:
    """
    Log a structured event with arbitrary key-value pairs.

    Default level is DEBUG — only shows when LOG_LEVEL=DEBUG.
    Pass a higher level to always show regardless of LOG_LEVEL.

    How it works:
        logger.handle() compares record.level vs logger.level
        If record.level >= logger.level → show it
        If record.level <  logger.level → drop it silently
        Python does this check automatically inside logger.handle()

    Usage:
        # Only shows in DEBUG mode — routine events
        log_event(logger, "tool_called", tool="get_customer")

        # Always shows in WARNING mode and above
        log_event(logger, "escalation_triggered",
                  level=logging.WARNING,
                  customer_id="123")

        # Always shows — something broke
        log_event(logger, "api_failed",
                  level=logging.ERROR,
                  error="timeout")
    """
    record = logging.LogRecord(
        name=logger.name,
        level=level,
        pathname="",
        lineno=0,
        msg=event,
        args=(),
        exc_info=None,
    )
    record.extra = {"event": event, **kwargs}

    # Only print the log if its level is high enough — this check is NOT built into logger.handle()
    # The level is set when we call get_logger() and read from .env, so changing LOG_LEVEL in .env will change # what gets printed without needing to restart the program.
    if logger.isEnabledFor(level):
        logger.handle(record)