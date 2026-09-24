"""Factory helpers para obtener loggers separados de bot y API.

Cada módulo debe pedir su logger a través de estas funciones para que los
mensajes terminen en el archivo correspondiente (`bot.log` o `api.log`).
"""

import contextvars
import logging
from typing import Any

from telegram import Update

# Contexto thread/async-safe para ids de trazabilidad
_bot_telegram_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "bot_telegram_user_id", default=None
)
_api_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "api_request_id", default=None
)


def get_bot_logger(name: str) -> logging.Logger:
    """Devuelve un logger bajo el namespace `bot.*`."""
    return logging.getLogger(f"bot.{name}")


def get_api_logger(name: str) -> logging.Logger:
    """Devuelve un logger bajo el namespace `api.*`."""
    return logging.getLogger(f"api.{name}")


def set_bot_telegram_user_id(telegram_user_id: int | None) -> None:
    """Establece el telegram_user_id actual en el contexto de ejecución."""
    _bot_telegram_user_id.set(telegram_user_id)


def get_bot_telegram_user_id() -> int | None:
    """Obtiene el telegram_user_id del contexto actual, si existe."""
    return _bot_telegram_user_id.get()


def set_api_request_id(request_id: str | None) -> None:
    """Establece el request_id actual en el contexto de ejecución."""
    _api_request_id.set(request_id)


def get_api_request_id() -> str | None:
    """Obtiene el request_id del contexto actual, si existe."""
    return _api_request_id.get()


def _extract_user_info(update: Update | None) -> dict[str, Any]:
    """Extrae información segura de `update.effective_user` y `effective_chat`."""
    user = getattr(update, "effective_user", None) if update else None
    chat = getattr(update, "effective_chat", None) if update else None
    return {
        "telegram_user_id": getattr(user, "id", None) if user else None,
        "telegram_username": getattr(user, "username", None) if user else None,
        "telegram_chat_id": getattr(chat, "id", None) if chat else None,
        "request_id": None,
    }


def log_bot_event(
    logger: logging.Logger,
    update: Update | None,
    action: str,
    level: int = logging.INFO,
    **kwargs: Any,
) -> None:
    """Registra un evento de actividad del bot con contexto de usuario.

    Args:
        logger: Logger de bot obtenido con `get_bot_logger(__name__)`.
        update: Objeto `Update` de python-telegram-bot.
        action: Descripción corta de la acción (p. ej. "Comando /start recibido").
        level: Nivel de log (default INFO).
        **kwargs: Campos adicionales para el dict `extra`.
    """
    extra = _extract_user_info(update)
    extra.update(kwargs)
    if extra.get("telegram_user_id"):
        set_bot_telegram_user_id(extra["telegram_user_id"])
    logger.log(level, action, extra=extra)
