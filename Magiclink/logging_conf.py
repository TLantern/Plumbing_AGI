from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # pass through extra fields
        for key, value in record.__dict__.items():
            if key in {"levelname", "name", "msg", "args", "exc_info", "exc_text", "stack_info", "lineno", "pathname", "filename", "funcName", "created", "msecs", "relativeCreated", "thread", "threadName", "processName", "process", "message", "asctime"}:
                continue
            payload[key] = value
        return json.dumps(payload, separators=(",", ":"))


def configure_json_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    # Clear existing handlers to avoid duplicate logs
    for h in list(root.handlers):
        root.removeHandler(h)

    root.addHandler(handler)

    # uvicorn access logger optional
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn").handlers = [handler] 