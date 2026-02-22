import logging
import json
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        # Merge any extra fields passed via extra={...}
        for key, val in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
                "taskName",
            }:
                log_data[key] = val
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_request(
    logger: logging.Logger,
    gene: str,
    cache_status: str,
    uniprot_status: int | None,
    elapsed_ms: float,
    error: str | None = None,
) -> None:
    """Log a structured API request record."""
    extra = {
        "gene": gene,
        "cache": cache_status,
        "uniprot_status": uniprot_status,
        "time_ms": round(elapsed_ms, 1),
    }
    if error:
        extra["error"] = error
        logger.warning("Request completed with error", extra=extra)
    else:
        logger.info(
            f"gene={gene} cache={cache_status} uniprot_status={uniprot_status} time={round(elapsed_ms)}ms",
            extra=extra,
        )
