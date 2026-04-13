"""Async handler tests for checkout-related cart flows."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ConversationHandler

from shared.handlers import cart


def _build_query(data: str, user_id: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
    )


def _build_context(user_data: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(user_data={} if user_data is None else user_data)


@pytest.mark.asyncio
async def test_finalizar_pedido_delegates_to_confirmation(monkeypatch):
    query = _build_query("finalizar_42")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    captured: dict[str, object] = {}

    async def fake_confirmation(query_arg, pedido_id):
        captured["query"] = query_arg
        captured["pedido_id"] = pedido_id

    monkeypatch.setattr(cart, "mostrar_confirmacion_finalizar_carrito", fake_confirmation)

    await cart.finalizar_pedido(update, context)

    query.answer.assert_awaited_once()
    assert captured == {"query": query, "pedido_id": 42}


@pytest.mark.asyncio
async def test_mostrar_confirmacion_finalizar_carrito_shows_empty_message_when_cart_missing(monkeypatch):
    query = _build_query("finalizar_42")

    monkeypatch.setattr(cart, "get_cart_by_invoice", lambda pedido_id: None)

    await cart.mostrar_confirmacion_finalizar_carrito(query, 42)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "pedido vacío" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_mostrar_confirmacion_finalizar_carrito_renders_summary(monkeypatch):
    query = _build_query("finalizar_42")
    cart_dto = SimpleNamespace(
        is_empty=False,
        total=Decimal("25.50"),
        items=[
            SimpleNamespace(
                name="Coca-Cola",
                quantity=2,
                description="Bebida 500ml",
                unit_price=Decimal("2.50"),
                subtotal=Decimal("5.00"),
            )
        ],
    )

    monkeypatch.setattr(cart, "get_cart_by_invoice", lambda pedido_id: cart_dto)

    await cart.mostrar_confirmacion_finalizar_carrito(query, 42)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "confirmar finalización" in args[0].lower()
    assert "coca-cola" in args[0].lower()
    assert "25.50" in args[0]
    assert kwargs["reply_markup"] is not None
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_ejecutar_finalizar_pedido_success_stores_payment_context(monkeypatch):
    query = _build_query("confirm_finalize_42")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    monkeypatch.setattr(
        cart,
        "finalize_checkout",
        lambda telegram_id, invoice_id: SimpleNamespace(
            success=True,
            payment_preference_id="pref-123",
            amount=Decimal("25.50"),
            title="Pedido #0000000042",
            payment_url="https://mp.test/pay",
        ),
    )

    await cart.ejecutar_finalizar_pedido(update, context)

    assert context.user_data["ultimo_pago"] == {
        "preference_id": "pref-123",
        "monto": "25.50",
        "concepto": "Pedido #0000000042",
    }
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "pedido confirmado" in args[0].lower()
    assert kwargs["reply_markup"] is not None
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_ejecutar_finalizar_pedido_shows_payment_error(monkeypatch):
    query = _build_query("confirm_finalize_42")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    monkeypatch.setattr(
        cart,
        "finalize_checkout",
        lambda telegram_id, invoice_id: SimpleNamespace(
            success=False,
            error_message="MercadoPago no disponible",
        ),
    )

    await cart.ejecutar_finalizar_pedido(update, context)

    assert context.user_data == {}
    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "no se pudo generar el pago" in args[0].lower()
    assert "mercadopago no disponible" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_ejecutar_finalizar_pedido_handles_cancel_action():
    query = _build_query("cancel_finalize")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    await cart.ejecutar_finalizar_pedido(update, context)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "acción cancelada" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_manejar_confirmacion_finalizar_pedido_delegates_on_confirm(monkeypatch):
    query = _build_query("confirm_finalize_42")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    called = {"count": 0}

    async def fake_execute(update_arg, context_arg):
        called["count"] += 1

    monkeypatch.setattr(cart, "ejecutar_finalizar_pedido", fake_execute)

    await cart.manejar_confirmacion_finalizar_pedido(update, context)

    query.answer.assert_awaited_once()
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_agregar_y_salir_flujo_productos_adds_and_ends(monkeypatch):
    query = _build_query("add_7")
    update = SimpleNamespace(callback_query=query)
    context = _build_context(
        {
            "categoria_seleccionada": "bebidas",
            "productos_actuales": [object()],
            "opciones_productos": ["A"],
            "producto_actual": object(),
            "pagina_productos": 1,
            "hay_mas_productos": False,
            "keep": "value",
        }
    )

    captured: dict[str, object] = {}

    async def fake_aumentar(query_arg, context_arg, producto_id, cantidad=1):
        captured["query"] = query_arg
        captured["context"] = context_arg
        captured["producto_id"] = producto_id
        captured["cantidad"] = cantidad

    monkeypatch.setattr(cart, "aumentar_cantidad", fake_aumentar)

    result = await cart.agregar_y_salir_flujo_productos(update, context)

    assert result == ConversationHandler.END
    query.answer.assert_awaited_once()
    assert captured["query"] == query
    assert captured["context"] == context
    assert captured["producto_id"] == 7
    assert captured["cantidad"] == 1
    assert context.user_data == {"keep": "value"}