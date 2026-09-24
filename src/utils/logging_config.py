"""Central logging configuration for the application.

Provides two independent log streams:

- ``bot``  -> logs/bot.log  (Telegram bot activity)
- ``api``  -> logs/api.log  (Flask REST API activity)

Both propagate to the root logger so messages also appear on the console.
"""

import logging
import logging.handlers
import os

from utils.config import Config
from utils.logger_factory import get_api_request_id, get_bot_telegram_user_id


LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | "
    "req=%(request_id)s | tg=%(telegram_user_id)s | %(message)s"
)


class _ContextualFormatter(logging.Formatter):
    """Formatter that guarantees contextual fields exist on every record."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id") or record.request_id is None:
            record.request_id = "-"
        if not hasattr(record, "telegram_user_id") or record.telegram_user_id is None:
            record.telegram_user_id = "-"
        return super().format(record)


class _RequestContextFilter(logging.Filter):
    """Injects the Flask request_id when available."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = getattr(record, "request_id", None)
        if request_id is None:
            try:
                from flask import g, has_request_context

                if has_request_context() and hasattr(g, "request_id"):
                    request_id = g.request_id
            except Exception:
                pass
        if request_id is None:
            request_id = get_api_request_id()
        record.request_id = request_id if request_id is not None else "-"
        return True


class _BotContextFilter(logging.Filter):
    """Injects the current telegram_user_id when available."""

    def filter(self, record: logging.LogRecord) -> bool:
        telegram_user_id = getattr(record, "telegram_user_id", None)
        if telegram_user_id is None:
            telegram_user_id = get_bot_telegram_user_id()
        record.telegram_user_id = telegram_user_id if telegram_user_id is not None else "-"
        return True


def _resolve_log_level() -> int:
    """Resolve the effective root log level from environment-driven settings."""
    configured_level = (Config.LOG_LEVEL or "").upper()
    if configured_level:
        return getattr(logging, configured_level, logging.INFO)
    return logging.DEBUG if Config.DEBUG_MODE else logging.INFO


def _level_from_name(name: str, default: int) -> int:
    """Convert a level name to its logging int value."""
    return getattr(logging, name.upper(), default)


def configure_logging() -> None:
    """Configure root, bot and api logging once for the whole process."""
    root_logger = logging.getLogger()
    root_level = _resolve_log_level()
    root_logger.setLevel(root_level)

    formatter = _ContextualFormatter(LOG_FORMAT)

    # Console handler attached to root so all propagated messages are visible
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Dedicated bot logger -> logs/bot.log
    bot_logger = logging.getLogger("bot")
    bot_logger.setLevel(_level_from_name(Config.BOT_LOG_LEVEL, logging.DEBUG))
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in bot_logger.handlers):
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        bot_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(Config.LOG_DIR, "bot.log"),
            maxBytes=Config.LOG_MAX_BYTES,
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        bot_file_handler.setFormatter(formatter)
        bot_file_handler.addFilter(_BotContextFilter())
        bot_logger.addHandler(bot_file_handler)

    # Dedicated api logger -> logs/api.log
    api_logger = logging.getLogger("api")
    api_logger.setLevel(_level_from_name(Config.API_LOG_LEVEL, logging.INFO))
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in api_logger.handlers):
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        api_file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(Config.LOG_DIR, "api.log"),
            maxBytes=Config.LOG_MAX_BYTES,
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        api_file_handler.setFormatter(formatter)
        api_file_handler.addFilter(_RequestContextFilter())
        api_logger.addHandler(api_file_handler)

    # Keep httpx quiet
    logging.getLogger("httpx").setLevel(logging.WARNING)
