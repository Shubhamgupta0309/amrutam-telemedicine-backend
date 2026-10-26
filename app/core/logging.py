import json
import logging
import sys
import contextvars
from datetime import datetime, timezone
from typing import Any, Dict

# Context variable for request correlation ID
correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")

SENSITIVE_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "secret_key", "authorization", "mfa_secret", "credit_card",
    "cvv", "payment_token"
}


class JSONFormatter(logging.Formatter):
    """
    Format logs as structured JSON with correlation ID and sensitive data redaction.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get(),
        }

        # Include exception info if available
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include extra attributes
        for key, val in record.__dict__.items():
            if key not in ("msg", "args", "levelname", "levelno", "pathname", "filename",
                           "module", "exc_info", "exc_text", "stack_info", "lineno",
                           "funcName", "created", "msecs", "relativeCreated", "thread",
                           "threadName", "processName", "process", "message", "name"):
                if key.lower() in SENSITIVE_KEYS:
                    log_entry[key] = "[REDACTED]"
                else:
                    log_entry[key] = val

        return json.dumps(log_entry)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with JSONFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)


logger = logging.getLogger("amrutam.backend")
