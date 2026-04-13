"""Async handler tests for shared.handlers.auth."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ConversationHandler

from shared.dtos import EmailSendResult
from shared.handlers import auth
from utils.constants import EstadoConversacion


def _build_message(text: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(text=text, reply_text=AsyncMock())


def _build_user(user_id: int = 123, first_name: str = "Ana") -> SimpleNamespace:
    return SimpleNamespace(id=user_id, first_name=first_name, last_name="Perez", username="anap")


def _build_context(user_data: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(user_data={} if user_data is None else user_data)


@pytest.mark.asyncio
async def test_start_with_existing_customer_shows_main_menu(monkeypatch):
    message = _build_message()
    update = SimpleNamespace(effective_user=_build_user(), message=message)
    context = _build_context()

    shown = {"called": False, "name": None}

    monkeypatch.setattr(auth, "get_customer_with_email", lambda telegram_id: {"email": "ana@example.com"})

    async def fake_menu(update_arg, context_arg, nombre=None):
        shown["called"] = True
        shown["name"] = nombre

    monkeypatch.setattr(auth, "mostrar_menu_principal", fake_menu)

    result = await auth.start(update, context)

    assert result is None
    assert shown == {"called": True, "name": "Ana"}
    message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_without_customer_email_requests_email(monkeypatch):
    message = _build_message()
    update = SimpleNamespace(effective_user=_build_user(), message=message)
    context = _build_context()

    monkeypatch.setattr(auth, "get_customer_with_email", lambda telegram_id: None)

    result = await auth.start(update, context)

    assert result == EstadoConversacion.ESPERANDO_EMAIL.value
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.await_args
    assert "necesito tu email" in args[0].lower()
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_recibir_email_rejects_invalid_email(monkeypatch):
    message = _build_message("correo-invalido")
    update = SimpleNamespace(message=message)
    context = _build_context()

    monkeypatch.setattr(auth, "es_email_valido", lambda email: False)

    result = await auth.recibir_email(update, context)

    assert result == EstadoConversacion.ESPERANDO_EMAIL.value
    assert context.user_data == {}
    message.reply_text.assert_awaited_once_with("❌ Email inválido. Intenta nuevamente:")


@pytest.mark.asyncio
async def test_recibir_email_stores_code_and_email(monkeypatch):
    message = _build_message("ana@example.com")
    update = SimpleNamespace(message=message, effective_user=_build_user())
    context = _build_context()

    monkeypatch.setattr(auth, "es_email_valido", lambda email: True)
    monkeypatch.setattr(auth, "generar_codigo_verificacion", lambda: "123456")
    monkeypatch.setattr(
        auth,
        "send_verification_email",
        lambda recipient_email, verification_code, recipient_name=None: EmailSendResult(
            success=True,
            recipients=[recipient_email],
            subject="Tu codigo de verificacion",
        ),
    )

    result = await auth.recibir_email(update, context)

    assert result == EstadoConversacion.ESPERANDO_CODIGO.value
    assert context.user_data == {
        "email_temp": "ana@example.com",
        "codigo_verificacion": "123456",
    }
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.await_args
    assert "123456" not in args[0]
    assert "ana@example.com" in args[0]
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_recibir_email_returns_error_when_email_send_fails(monkeypatch):
    message = _build_message("ana@example.com")
    update = SimpleNamespace(message=message, effective_user=_build_user())
    context = _build_context()

    monkeypatch.setattr(auth, "es_email_valido", lambda email: True)
    monkeypatch.setattr(auth, "generar_codigo_verificacion", lambda: "123456")
    monkeypatch.setattr(
        auth,
        "send_verification_email",
        lambda recipient_email, verification_code, recipient_name=None: EmailSendResult(
            success=False,
            recipients=[recipient_email],
            subject="Tu codigo de verificacion",
            error_message="❌ No se pudo enviar el email",
        ),
    )

    result = await auth.recibir_email(update, context)

    assert result == EstadoConversacion.ESPERANDO_EMAIL.value
    assert context.user_data == {}
    message.reply_text.assert_awaited_once_with("❌ No se pudo enviar el email")


@pytest.mark.asyncio
async def test_verificar_codigo_success_persists_customer_and_clears_state(monkeypatch):
    message = _build_message("123456")
    user = _build_user()
    update = SimpleNamespace(message=message, effective_user=user)
    context = _build_context({"codigo_verificacion": "123456", "email_temp": "ana@example.com"})

    captured: dict[str, object] = {}

    def fake_register(telegram_id, first_name, last_name, username, email):
        captured.update(
            {
                "telegram_id": telegram_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "email": email,
            }
        )

    monkeypatch.setattr(auth, "register_verified_customer", fake_register)

    result = await auth.verificar_codigo(update, context)

    assert result == ConversationHandler.END
    assert captured == {
        "telegram_id": 123,
        "first_name": "Ana",
        "last_name": "Perez",
        "username": "anap",
        "email": "ana@example.com",
    }
    assert context.user_data == {}
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.await_args
    assert "email verificado" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_verificar_codigo_failure_keeps_waiting(monkeypatch):
    message = _build_message("000000")
    update = SimpleNamespace(message=message, effective_user=_build_user())
    context = _build_context({"codigo_verificacion": "123456", "email_temp": "ana@example.com"})

    register = {"called": False}

    def fake_register(*args, **kwargs):
        register["called"] = True

    monkeypatch.setattr(auth, "register_verified_customer", fake_register)

    result = await auth.verificar_codigo(update, context)

    assert result == EstadoConversacion.ESPERANDO_CODIGO.value
    assert register["called"] is False
    assert context.user_data == {
        "codigo_verificacion": "123456",
        "email_temp": "ana@example.com",
    }
    message.reply_text.assert_awaited_once()
    args, _ = message.reply_text.await_args
    assert "incorrecto" in args[0].lower()