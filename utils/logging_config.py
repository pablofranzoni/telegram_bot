"""Central logging configuration for the application."""

import logging

from utils.config import Config


def _resolve_log_level() -> int:
    """Resolve the effective log level from environment-driven settings."""
    configured_level = (Config.LOG_LEVEL or "").upper()
    if configured_level:
        return getattr(logging, configured_level, logging.INFO)
    return logging.DEBUG if Config.DEBUG_MODE else logging.INFO


def configure_logging() -> None:
    """Configure root logging once for the whole process."""
    root_logger = logging.getLogger()

    if root_logger.handlers:
        root_logger.setLevel(_resolve_log_level())
    else:
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=_resolve_log_level(),
        )

    logging.getLogger("httpx").setLevel(logging.WARNING)
