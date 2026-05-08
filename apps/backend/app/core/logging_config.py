"""Centralized logging configuration (single place to tune format/levels)."""
from __future__ import annotations
import logging
import os

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=_DEFAULT_FORMAT)
    else:
        root.setLevel(level)
    # Ensure app loggers follow root
    logging.getLogger("onetouch").setLevel(level)
    logging.getLogger("uvicorn").setLevel(level)
    logging.getLogger("uvicorn.error").setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
