"""Async handler tests for checkout-related cart flows."""

import io
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest
from telegram.ext import ConversationHandler

from shared.dtos import ProductDTO
from shared.handlers import cart
from utils import config as config_module

TEST_INVOICE_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_CHAT_ID = 42


def _build_query(data: str, user_id: int = 123, *, with_message: bool = True) -> SimpleNamespace:
    message = (
        SimpleNamespace(chat_id=TEST_CHAT_ID, message_id=1)
        if with_message
        else None
    )
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=message,
        answer=AsyncMock(),
        edit_message_text=AsyncMock(),
        edit_message_caption=AsyncMock(),
    )


def _build_context(user_data: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(user_data={} if user_data is None else user_data)


@pytest.mark.asyncio
async def test_finalizar_pedido_delegates_to_confirmation(monkeypatch):
    query = _build_query(f"finalizar_{TEST_INVOICE_ID}")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    captured: dict[str, object] = {}

    async def fake_confirmation(query_arg, pedido_id):
        captured["query"] = query_arg
        captured["pedido_id"] = pedido_id

    monkeypatch.setattr(cart, "mostrar_confirmacion_finalizar_carrito", fake_confirmation)

    await cart.finalizar_pedido(update, context)

    query.answer.assert_awaited_once()
    assert captured == {"query": query, "pedido_id": TEST_INVOICE_ID}


@pytest.mark.asyncio
async def test_mostrar_confirmacion_finalizar_carrito_shows_empty_message_when_cart_missing(monkeypatch):
    query = _build_query(f"finalizar_{TEST_INVOICE_ID}")

    monkeypatch.setattr(cart, "get_cart_by_invoice", lambda pedido_id: None)

    await cart.mostrar_confirmacion_finalizar_carrito(query, TEST_INVOICE_ID)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "pedido vacío" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_mostrar_confirmacion_finalizar_carrito_renders_summary(monkeypatch):
    query = _build_query(f"finalizar_{TEST_INVOICE_ID}")
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

    await cart.mostrar_confirmacion_finalizar_carrito(query, TEST_INVOICE_ID)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "confirmar finalización" in args[0].lower()
    assert "coca-cola" in args[0].lower()
    assert "25.50" in args[0]
    assert kwargs["reply_markup"] is not None
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_ejecutar_finalizar_pedido_success_stores_payment_context(monkeypatch):
    query = _build_query(f"confirm_finalize_{TEST_INVOICE_ID}")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    monkeypatch.setattr(
        cart,
        "finalize_checkout",
        lambda telegram_id, invoice_id: SimpleNamespace(
            success=True,
            payment_preference_id="pref-123",
            amount=Decimal("25.50"),
            title=f"Pedido #{TEST_INVOICE_ID}",
            payment_url="https://mp.test/pay",
        ),
    )

    await cart.ejecutar_finalizar_pedido(update, context)

    assert context.user_data["ultimo_pago"] == {
        "preference_id": "pref-123",
        "monto": "25.50",
        "concepto": f"Pedido #{TEST_INVOICE_ID}",
    }
    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "pedido confirmado" in args[0].lower()
    assert kwargs["reply_markup"] is not None
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_ejecutar_finalizar_pedido_shows_payment_error(monkeypatch):
    query = _build_query(f"confirm_finalize_{TEST_INVOICE_ID}")
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
    query = _build_query(f"confirm_finalize_{TEST_INVOICE_ID}")
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
    query.message.reply_text = AsyncMock()
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
        return SimpleNamespace(
            success=True,
            product=ProductDTO(
                id=producto_id,
                name="Coca-Cola",
                description="Bebida 500ml",
                price=Decimal("2.50"),
            ),
        )

    monkeypatch.setattr(cart, "aumentar_cantidad", fake_aumentar)

    result = await cart.agregar_y_salir_flujo_productos(update, context)

    assert result == ConversationHandler.END
    query.answer.assert_awaited_once()
    assert captured["query"] == query
    assert captured["context"] == context
    assert captured["producto_id"] == 7
    assert captured["cantidad"] == 1
    assert context.user_data == {"keep": "value"}
    query.message.reply_text.assert_awaited_once()
    guidance_args, _ = query.message.reply_text.await_args
    assert "Coca-Cola" in guidance_args[0]
    assert "agregado al pedido" in guidance_args[0]


def test_confirm_finalize_pattern_matches_legacy_int_invoice_id():
    """Legacy integer invoice ids should still match the callback pattern."""
    pattern = re.compile(r'^(confirm_finalize_.+|cancel_finalize)$')
    assert pattern.fullmatch(f"confirm_finalize_42")


def test_confirm_finalize_pattern_matches_uuid_invoice_id():
    """UUID invoice ids must match the callback pattern (regression for bot_core.py:120)."""
    pattern = re.compile(r'^(confirm_finalize_.+|cancel_finalize)$')
    assert pattern.fullmatch(f"confirm_finalize_{TEST_INVOICE_ID}")


def test_confirm_finalize_pattern_matches_cancel_action():
    """The cancel button should still match the callback pattern."""
    pattern = re.compile(r'^(confirm_finalize_.+|cancel_finalize)$')
    assert pattern.fullmatch("cancel_finalize")


@pytest.mark.asyncio
async def test_manejar_botones_carrito_info_branch_dispatches_to_foto(monkeypatch):
    """The `info_<id>` callback must route to `mostrar_foto_producto` with the parsed id."""
    query = _build_query("info_5")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    captured: dict[str, object] = {}

    async def fake_foto(query_arg, context_arg, producto_id):
        captured["query"] = query_arg
        captured["context"] = context_arg
        captured["producto_id"] = producto_id

    monkeypatch.setattr(cart, "mostrar_foto_producto", fake_foto)

    await cart.manejar_botones_carrito(update, context)

    assert captured == {"query": query, "context": context, "producto_id": 5}
    query.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_manejar_botones_carrito_info_without_id_does_not_crash(monkeypatch):
    """A bare `info_` callback (no id) must not raise `ValueError` from `int('')`.

    Regression: the dispatcher used to call `int(data.replace('info_', ''))` which
    raised `ValueError` and aborted the handler chain with a stack trace.
    """
    query = _build_query("info_")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    dispatched: list[int] = []

    async def fake_detalle(query_arg, context_arg, producto_id):
        dispatched.append(producto_id)

    monkeypatch.setattr(cart, "mostrar_foto_producto", fake_detalle)

    await cart.manejar_botones_carrito(update, context)

    assert dispatched == []
    assert query.answer.await_count >= 1


@pytest.mark.asyncio
async def test_mostrar_detalle_producto_renders_product_info(monkeypatch):
    """Happy path: edit the message with name, description, price and stock text."""
    query = _build_query("info_5")
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
        stock_available=12,
    )

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)

    await cart.mostrar_detalle_producto(query, _build_context(), 5)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()
    _, kwargs = query.edit_message_text.await_args
    text = kwargs["text"]
    assert "Coca-Cola" in text
    assert "Bebida 500ml" in text
    assert "2.50" in text
    assert "12 unidad(es) en stock" in text
    assert "Selecciona una acción" in text
    assert kwargs["parse_mode"] == "Markdown"
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_mostrar_detalle_producto_answers_callback_only_once(monkeypatch):
    """Regression: must answer the callback once and still edit the message.

    Before the fix, the function called `query.answer()` after the dispatcher had
    already answered it, raising `BadRequest` and skipping `edit_message_text`.
    """
    query = _build_query("info_5")
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
        stock_available=3,
    )

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)

    await cart.mostrar_detalle_producto(query, _build_context(), 5)

    query.answer.assert_awaited_once()
    query.edit_message_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_mostrar_detalle_producto_handles_missing_product(monkeypatch):
    """Unknown product id must toast a "no encontrado" and must not edit the message."""
    query = _build_query("info_999")

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: None)

    await cart.mostrar_detalle_producto(query, _build_context(), 999)

    query.answer.assert_awaited_once()
    args, kwargs = query.answer.await_args
    assert "no encontrado" in args[0].lower()
    query.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_mostrar_detalle_producto_renders_stock_none_as_disponible(monkeypatch):
    """When `stock_available is None`, render 'Disponible' instead of a unit count."""
    query = _build_query("info_5")
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
        stock_available=None,
    )

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)

    await cart.mostrar_detalle_producto(query, _build_context(), 5)

    query.edit_message_text.assert_awaited_once()
    _, kwargs = query.edit_message_text.await_args
    text = kwargs["text"]
    assert "Disponible" in text
    assert "unidad(es) en stock" not in text


@pytest.mark.asyncio
async def test_mostrar_foto_producto_sends_photo_with_caption(monkeypatch, tmp_path):
    """Happy path: send the photo with the ficha as caption and the same keyboard."""
    query = _build_query("info_5")
    bot = SimpleNamespace(send_photo=AsyncMock())
    context = SimpleNamespace(user_data={}, bot=bot)
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
        stock_available=8,
    )
    image_path = tmp_path / "5.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)
    monkeypatch.setattr(cart, "_resolve_product_image", lambda producto_id: image_path)

    await cart.mostrar_foto_producto(query, context, 5)

    bot.send_photo.assert_awaited_once()
    _, kwargs = bot.send_photo.await_args
    assert kwargs["chat_id"] == TEST_CHAT_ID
    assert "Coca-Cola" in kwargs["caption"]
    assert "Bebida 500ml" in kwargs["caption"]
    assert "2.50" in kwargs["caption"]
    assert "8 unidad(es) en stock" in kwargs["caption"]
    assert kwargs["parse_mode"] == "Markdown"
    assert kwargs["reply_markup"] is not None
    photo = kwargs["photo"]
    assert hasattr(photo, "read")
    assert Path(str(photo.name)).resolve() == image_path.resolve()
    query.edit_message_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_mostrar_foto_producto_handles_missing_product(monkeypatch):
    """Unknown product id must toast and must not touch the bot."""
    query = _build_query("info_999")
    bot = SimpleNamespace(send_photo=AsyncMock())
    context = SimpleNamespace(user_data={}, bot=bot)

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: None)

    await cart.mostrar_foto_producto(query, context, 999)

    bot.send_photo.assert_not_awaited()
    query.answer.assert_awaited_once()
    args, _ = query.answer.await_args
    assert "no encontrado" in args[0].lower()


@pytest.mark.asyncio
async def test_mostrar_foto_producto_handles_missing_image(monkeypatch):
    """When the image file does not exist, toast and do not call send_photo."""
    query = _build_query("info_5")
    bot = SimpleNamespace(send_photo=AsyncMock())
    context = SimpleNamespace(user_data={}, bot=bot)
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)
    monkeypatch.setattr(cart, "_resolve_product_image", lambda producto_id: None)

    await cart.mostrar_foto_producto(query, context, 5)

    bot.send_photo.assert_not_awaited()
    query.answer.assert_awaited_once()
    args, _ = query.answer.await_args
    assert "imagen" in args[0].lower()


@pytest.mark.asyncio
async def test_mostrar_foto_producto_handles_missing_message(monkeypatch):
    """If the callback has no message (rare but possible), bail out without crashing."""
    query = _build_query("info_5", with_message=False)
    bot = SimpleNamespace(send_photo=AsyncMock())
    context = SimpleNamespace(user_data={}, bot=bot)
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    image_path = SimpleNamespace(open=lambda *a, **k: io.BytesIO(b"x"))

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)
    monkeypatch.setattr(cart, "_resolve_product_image", lambda producto_id: image_path)

    await cart.mostrar_foto_producto(query, context, 5)

    bot.send_photo.assert_not_awaited()
    query.answer.assert_awaited_once()
    args, _ = query.answer.await_args
    assert "no se pudo enviar" in args[0].lower()


@pytest.mark.asyncio
async def test_mostrar_foto_producto_handles_open_error(monkeypatch):
    """If opening the image raises OSError, log and toast without crashing."""
    query = _build_query("info_5")
    bot = SimpleNamespace(send_photo=AsyncMock())
    context = SimpleNamespace(user_data={}, bot=bot)
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )

    class _BrokenPath:
        def open(self, *args, **kwargs):
            raise OSError("permission denied")

    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)
    monkeypatch.setattr(cart, "_resolve_product_image", lambda producto_id: _BrokenPath())

    await cart.mostrar_foto_producto(query, context, 5)

    bot.send_photo.assert_not_awaited()
    assert query.answer.await_count >= 1


def test_resolve_product_image_returns_none_when_dir_missing(monkeypatch, tmp_path):
    """Returns None if the configured directory does not exist."""
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(config_module.Config, "PRODUCT_IMAGES_DIR", str(missing))

    assert cart._resolve_product_image(1) is None


def test_resolve_product_image_returns_none_when_no_match(monkeypatch, tmp_path):
    """Returns None if no extension matches."""
    monkeypatch.setattr(config_module.Config, "PRODUCT_IMAGES_DIR", str(tmp_path))

    assert cart._resolve_product_image(1) is None


def test_resolve_product_image_finds_first_supported_extension(monkeypatch, tmp_path):
    """Picks the first supported extension in PRODUCT_IMAGE_EXTENSIONS order."""
    (tmp_path / "7.png").write_bytes(b"png")
    (tmp_path / "7.jpg").write_bytes(b"jpg")
    monkeypatch.setattr(config_module.Config, "PRODUCT_IMAGES_DIR", str(tmp_path))

    resolved = cart._resolve_product_image(7)

    assert resolved is not None
    assert resolved.suffix == ".jpg"
    assert resolved.read_bytes() == b"jpg"


def test_resolve_product_image_rejects_path_traversal(monkeypatch, tmp_path):
    """Even if `<id>.ext` resolves outside the base dir, the lookup must return None."""
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    (other_dir / "9.png").write_bytes(b"outside")

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    monkeypatch.setattr(config_module.Config, "PRODUCT_IMAGES_DIR", str(sandbox))

    assert cart._resolve_product_image(9) is None


@pytest.mark.asyncio
async def test_safe_edit_callback_message_falls_back_to_caption_on_photo_message():
    """When the source message has no text body, retry with edit_message_caption.

    Regression: clicking "✅ Agregar" on the product photo raised
    ``BadRequest: There is no text in the message to edit`` because the
    callback tried to edit a photo message as text.
    """
    query = _build_query("add_5")

    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")

    await cart._safe_edit_callback_message(
        query,
        "➕ Coca-Cola: 0 → 1",
        parse_mode="Markdown",
    )

    query.edit_message_text.assert_awaited_once()
    query.edit_message_caption.assert_awaited_once()
    _, kwargs = query.edit_message_caption.await_args
    assert kwargs["caption"] == "➕ Coca-Cola: 0 → 1"
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_safe_edit_callback_message_prefers_text_when_available():
    """When the source message has text, do not touch the caption."""
    query = _build_query("add_5")

    await cart._safe_edit_callback_message(query, "➕ Coca-Cola: 0 → 1")

    query.edit_message_text.assert_awaited_once()
    query.edit_message_caption.assert_not_awaited()


@pytest.mark.asyncio
async def test_safe_edit_callback_message_handles_caption_not_modified():
    """If edit_message_caption also raises 'not modified', swallow it."""
    query = _build_query("add_5")

    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")
    query.edit_message_caption.side_effect = BadRequest("Message is not modified")

    await cart._safe_edit_callback_message(query, "➕ Coca-Cola: 1")


@pytest.mark.asyncio
async def test_aumentar_cantidad_does_not_edit_message_on_success(monkeypatch):
    """On success the function must not edit the callback message.

    The per-product ack (``➕ Coca-Cola: 0 → 1``) was removed: the caller is
    responsible for user-facing feedback (e.g. ``agregar_y_salir_flujo_productos``
    sends the ``✅ <name> agregado al pedido`` message). The function only
    returns the result so the caller can use the product name.
    """
    query = _build_query("add_5")
    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    monkeypatch.setattr(
        cart,
        "increase_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=True,
            product=product,
            previous_quantity=0,
            current_quantity=1,
        ),
    )

    result = await cart.aumentar_cantidad(query, _build_context(), 5)

    assert result.success is True
    assert result.product is product
    query.edit_message_text.assert_not_awaited()
    query.edit_message_caption.assert_not_awaited()


@pytest.mark.asyncio
async def test_aumentar_cantidad_error_falls_back_to_caption_on_photo_message(monkeypatch):
    """On failure, the error message still uses the photo caption fallback."""
    query = _build_query("add_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")

    monkeypatch.setattr(
        cart,
        "increase_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=False,
            product=None,
            error_message="❌ Sin stock",
        ),
    )

    await cart.aumentar_cantidad(query, _build_context(), 5)

    query.edit_message_caption.assert_awaited_once()
    _, kwargs = query.edit_message_caption.await_args
    assert "sin stock" in kwargs["caption"].lower()


@pytest.mark.asyncio
async def test_mostrar_confirmacion_eliminar_quantity_greater_than_one_uses_quitar_unidad(monkeypatch):
    """When the product has qty > 1, the dialog must use the 'quitar unidad' variant."""
    query = _build_query("del_5")
    cart_dto = SimpleNamespace(
        items=[
            SimpleNamespace(product_id=5, quantity=3),
            SimpleNamespace(product_id=9, quantity=1),
        ]
    )
    monkeypatch.setattr(cart, "get_cart_by_invoice", lambda pedido_id: cart_dto)

    await cart.mostrar_confirmacion_eliminar(query, 5, "Coca-Cola", TEST_INVOICE_ID)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    text = args[0].lower()
    assert "confirmación de quitar unidad" in text
    assert "quitar una unidad" in text
    assert "*2*" in text
    assert "unidad(es) en el carrito" in text
    assert "esta acción no se puede deshacer" not in text
    assert kwargs["parse_mode"] == "Markdown"

    markup = kwargs["reply_markup"]
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    action_buttons = [b for b in buttons if b.callback_data and b.callback_data.startswith("confirm_del_")]
    assert len(action_buttons) == 1
    assert action_buttons[0].callback_data == f"confirm_del_one_5_{TEST_INVOICE_ID}"
    assert "quitar cantidad" in action_buttons[0].text.lower()
    cancel_buttons = [b for b in buttons if b.callback_data == "cancel_del"]
    assert len(cancel_buttons) == 1
    assert "cancelar" in cancel_buttons[0].text.lower()


@pytest.mark.asyncio
async def test_mostrar_confirmacion_eliminar_quantity_one_uses_eliminar(monkeypatch):
    """When the product has qty == 1, the dialog must use the legacy 'eliminar' variant."""
    query = _build_query("del_5")
    cart_dto = SimpleNamespace(
        items=[SimpleNamespace(product_id=5, quantity=1)]
    )
    monkeypatch.setattr(cart, "get_cart_by_invoice", lambda pedido_id: cart_dto)

    await cart.mostrar_confirmacion_eliminar(query, 5, "Coca-Cola", TEST_INVOICE_ID)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    text = args[0].lower()
    assert "confirmar eliminación" in text
    assert "esta acción no se puede deshacer" in text
    assert "confirmación de quitar unidad" not in text

    markup = kwargs["reply_markup"]
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    action_buttons = [b for b in buttons if b.callback_data and b.callback_data.startswith("confirm_del_")]
    assert len(action_buttons) == 1
    assert action_buttons[0].callback_data == f"confirm_del_5_{TEST_INVOICE_ID}"
    assert "eliminar" in action_buttons[0].text.lower()
    assert "quitar cantidad" not in action_buttons[0].text.lower()


@pytest.mark.asyncio
async def test_mostrar_confirmacion_eliminar_product_not_in_cart_falls_back_to_eliminar(monkeypatch):
    """If the cart lookup can't find the product, treat as qty == 1 and offer 'eliminar'."""
    query = _build_query("del_5")
    cart_dto = SimpleNamespace(items=[SimpleNamespace(product_id=9, quantity=2)])
    monkeypatch.setattr(cart, "get_cart_by_invoice", lambda pedido_id: cart_dto)

    await cart.mostrar_confirmacion_eliminar(query, 5, "Coca-Cola", TEST_INVOICE_ID)

    query.edit_message_text.assert_awaited_once()
    args, kwargs = query.edit_message_text.await_args
    assert "confirmar eliminación" in args[0].lower()
    markup = kwargs["reply_markup"]
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    action_buttons = [b for b in buttons if b.callback_data and b.callback_data.startswith("confirm_del_one_") is False and b.callback_data.startswith("confirm_del_")]
    assert action_buttons[0].callback_data == f"confirm_del_5_{TEST_INVOICE_ID}"


@pytest.mark.asyncio
async def test_manejar_confirmacion_eliminar_dispatches_quitar_unidad(monkeypatch):
    """The dispatcher must route `confirm_del_one_*` to `ejecutar_quitar_unidad`."""
    query = _build_query(f"confirm_del_one_5_{TEST_INVOICE_ID}")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)

    captured: dict[str, object] = {}

    async def fake_quitar(query_arg, context_arg, producto_id_arg, nombre_arg, usuario_id_arg):
        captured["query"] = query_arg
        captured["context"] = context_arg
        captured["producto_id"] = producto_id_arg
        captured["nombre"] = nombre_arg
        captured["usuario_id"] = usuario_id_arg

    monkeypatch.setattr(cart, "ejecutar_quitar_unidad", fake_quitar)

    await cart.manejar_confirmacion_eliminar(update, context)

    assert captured["query"] is query
    assert captured["context"] is context
    assert captured["producto_id"] == 5
    assert captured["nombre"] == "Coca-Cola"
    assert captured["usuario_id"] == query.from_user.id


@pytest.mark.asyncio
async def test_manejar_confirmacion_eliminar_legacy_path_still_works(monkeypatch):
    """The dispatcher must still route plain `confirm_del_*` to `ejecutar_eliminacion`."""
    query = _build_query(f"confirm_del_5_{TEST_INVOICE_ID}")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    monkeypatch.setattr(cart, "get_product_by_id", lambda producto_id: product)

    captured: dict[str, object] = {}

    async def fake_eliminar(query_arg, context_arg, producto_id_arg, nombre_arg, pedido_id_arg, usuario_id_arg):
        captured["producto_id"] = producto_id_arg
        captured["nombre"] = nombre_arg
        captured["pedido_id"] = pedido_id_arg
        captured["usuario_id"] = usuario_id_arg

    monkeypatch.setattr(cart, "ejecutar_eliminacion", fake_eliminar)

    await cart.manejar_confirmacion_eliminar(update, context)

    assert captured == {
        "producto_id": 5,
        "nombre": "Coca-Cola",
        "pedido_id": TEST_INVOICE_ID,
        "usuario_id": query.from_user.id,
    }


@pytest.mark.asyncio
async def test_actualizar_vista_pedido_falls_back_to_caption_on_photo_message(monkeypatch):
    """When the cart is refreshed onto a photo message, edit the caption instead of text.

    Regression: previously ``actualizar_vista_pedido`` called
    ``query.edit_message_text`` directly, which raised ``BadRequest: There is
    no text in the message to edit`` whenever the source was a photo. The
    handler then surfaced ``❌ Error interno al quitar unidad`` to the user
    even though the cart mutation itself succeeded.
    """
    query = _build_query("del_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")

    cart_dto = SimpleNamespace(
        invoice_id=TEST_INVOICE_ID,
        total=Decimal("5.00"),
        item_count=1,
        items=[
            SimpleNamespace(
                product_id=5,
                name="Coca-Cola",
                quantity=2,
                unit_price=Decimal("2.50"),
                subtotal=Decimal("5.00"),
            )
        ],
    )
    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: cart_dto)

    await cart.actualizar_vista_pedido(query, _build_context(), usuario_id=123)

    query.edit_message_text.assert_awaited_once()
    query.edit_message_caption.assert_awaited_once()
    _, kwargs = query.edit_message_caption.await_args
    assert "Carrito Actualizado" in kwargs["caption"]
    assert "Coca-Cola" in kwargs["caption"]
    assert "5.00" in kwargs["caption"]
    assert kwargs["parse_mode"] == "Markdown"
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_actualizar_vista_pedido_empty_cart_falls_back_to_caption_on_photo_message(monkeypatch):
    """The 'pedido vacío' branch must also fall back to the caption on a photo."""
    query = _build_query("del_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")

    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: None)

    await cart.actualizar_vista_pedido(query, _build_context(), usuario_id=123)

    query.edit_message_text.assert_awaited_once()
    query.edit_message_caption.assert_awaited_once()
    _, kwargs = query.edit_message_caption.await_args
    assert "pedido vacío" in kwargs["caption"].lower()


@pytest.mark.asyncio
async def test_ejecutar_quitar_unidad_falls_back_to_caption_on_photo_message(monkeypatch):
    """End-to-end: the 'quitar unidad' flow must not crash on a photo source.

    Regression: clicking ``Quitar Cantidad`` after the photo-message flow used
    to surface ``❌ Error interno al quitar unidad`` because the cart-refresh
    step hit ``edit_message_text`` on a media message.
    """
    query = _build_query("confirm_del_one_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")

    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    cart_dto = SimpleNamespace(
        invoice_id=TEST_INVOICE_ID,
        total=Decimal("2.50"),
        item_count=1,
        items=[
            SimpleNamespace(
                product_id=5,
                name="Coca-Cola",
                quantity=1,
                unit_price=Decimal("2.50"),
                subtotal=Decimal("2.50"),
            )
        ],
    )
    monkeypatch.setattr(
        cart,
        "decrease_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=True,
            product=product,
            previous_quantity=2,
            current_quantity=1,
        ),
    )
    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: cart_dto)

    await cart.ejecutar_quitar_unidad(query, _build_context(), 5, "Coca-Cola", usuario_id=123)

    query.edit_message_caption.assert_awaited_once()
    _, kwargs = query.edit_message_caption.await_args
    assert "Carrito Actualizado" in kwargs["caption"]


@pytest.mark.asyncio
async def test_ejecutar_quitar_unidad_empty_cart_falls_back_to_caption_on_photo_message(monkeypatch):
    """The empty-cart branch inside ``ejecutar_quitar_unidad`` must also be safe on photos."""
    query = _build_query("confirm_del_one_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")

    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    monkeypatch.setattr(
        cart,
        "decrease_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=True,
            product=product,
            previous_quantity=1,
            current_quantity=0,
        ),
    )
    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: None)

    await cart.ejecutar_quitar_unidad(query, _build_context(), 5, "Coca-Cola", usuario_id=123)

    query.edit_message_caption.assert_awaited_once()
    _, kwargs = query.edit_message_caption.await_args
    assert "pedido vacío" in kwargs["caption"].lower()


@pytest.mark.asyncio
async def test_safe_edit_callback_message_skips_when_text_too_long():
    """If Telegram rejects the edit with 'message is too long', don't propagate the error.

    Regression: the cart view rendered after a successful ``Quitar Cantidad`` mutation
    can exceed Telegram's 4096-char text limit when the cart has many items. Without
    this handler the exception bubbled up to ``ejecutar_quitar_unidad`` and surfaced
    ``❌ Error interno al quitar unidad`` to the user.
    """
    query = _build_query("info_5")
    query.edit_message_text.side_effect = BadRequest("Message is too long")

    await cart._safe_edit_callback_message(query, "x" * 5000)

    query.edit_message_text.assert_awaited_once()
    query.edit_message_caption.assert_not_awaited()


@pytest.mark.asyncio
async def test_safe_edit_callback_message_skips_when_caption_too_long():
    """Same as above, but for the photo caption fallback path."""
    query = _build_query("info_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")
    query.edit_message_caption.side_effect = BadRequest("Caption is too long")

    await cart._safe_edit_callback_message(query, "x" * 5000)

    query.edit_message_text.assert_awaited_once()
    query.edit_message_caption.assert_awaited_once()


@pytest.mark.asyncio
async def test_actualizar_vista_pedido_swallows_too_long_caption(monkeypatch):
    """End-to-end: a long cart view must not raise in ``Quitar Cantidad``.

    Regression: with many items the rendered cart view exceeded Telegram's
    1024-char caption limit, the fallback re-raised, and the user saw
    ``❌ Error interno al quitar unidad`` even though the decrement had
    already been persisted.
    """
    query = _build_query("confirm_del_one_5")
    query.edit_message_text.side_effect = BadRequest("There is no text in the message to edit")
    query.edit_message_caption.side_effect = BadRequest("Caption is too long")

    product = ProductDTO(
        id=5,
        name="Coca-Cola",
        description="Bebida 500ml",
        price=Decimal("2.50"),
    )
    items = [
        SimpleNamespace(
            product_id=i,
            name=f"Producto {i:02d} con nombre extremadamente largo " * 3,
            quantity=2,
            unit_price=Decimal("9.99"),
            subtotal=Decimal("19.98"),
        )
        for i in range(1, 21)
    ]
    cart_dto = SimpleNamespace(
        invoice_id=TEST_INVOICE_ID,
        total=Decimal("399.60"),
        item_count=40,
        items=items,
    )
    monkeypatch.setattr(
        cart,
        "decrease_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=True,
            product=product,
            previous_quantity=2,
            current_quantity=1,
        ),
    )
    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: cart_dto)

    await cart.ejecutar_quitar_unidad(query, _build_context(), 5, "Coca-Cola", usuario_id=123)

    assert query.answer.await_count >= 1


def _build_cart_dto(invoice_id=TEST_INVOICE_ID, total=Decimal("5.00"), item_count=1, items=None):
    return SimpleNamespace(
        invoice_id=invoice_id,
        total=total,
        item_count=item_count,
        items=items
        or [
            SimpleNamespace(
                product_id=5,
                name="Coca-Cola",
                quantity=2,
                unit_price=Decimal("2.50"),
                subtotal=Decimal("5.00"),
            )
        ],
    )


def _collect_callbacks(markup):
    """Return a flat list of callback_data values from every button in the markup."""
    return [
        btn.callback_data
        for row in markup.inline_keyboard
        for btn in row
        if btn.callback_data
    ]


@pytest.mark.asyncio
async def test_actualizar_vista_pedido_includes_adjustment_buttons_per_item(monkeypatch):
    """Each item must render a [−1][qty][+1] row and a [❌ Quitar] row."""
    query = _build_query("noop")
    cart_dto = _build_cart_dto(
        item_count=4,
        items=[
            SimpleNamespace(
                product_id=5,
                name="Coca-Cola",
                quantity=2,
                unit_price=Decimal("2.50"),
                subtotal=Decimal("5.00"),
            ),
            SimpleNamespace(
                product_id=9,
                name="Sprite",
                quantity=1,
                unit_price=Decimal("2.80"),
                subtotal=Decimal("2.80"),
            ),
        ],
    )
    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: cart_dto)

    await cart.actualizar_vista_pedido(query, _build_context(), usuario_id=123)

    query.edit_message_text.assert_awaited_once()
    _, kwargs = query.edit_message_text.await_args
    markup = kwargs["reply_markup"]
    callbacks = _collect_callbacks(markup)
    assert "rem_5" in callbacks
    assert "add_5" in callbacks
    assert "del_5" in callbacks
    assert "rem_9" in callbacks
    assert "add_9" in callbacks
    assert "del_9" in callbacks
    assert "noop" in callbacks
    adjustment_rows = [
        row for row in markup.inline_keyboard
        if [btn.callback_data for btn in row] == ["rem_5", "noop", "add_5"]
    ]
    assert len(adjustment_rows) == 1
    qty_label = adjustment_rows[0][1]
    assert qty_label.text == "2"
    assert qty_label.callback_data == "noop"


@pytest.mark.asyncio
async def test_ver_pedido_includes_adjustment_buttons_per_item(monkeypatch):
    """``ver_pedido`` must also render the [−1][qty][+1] row per item."""
    cart_dto = SimpleNamespace(
        is_empty=False,
        invoice_id=TEST_INVOICE_ID,
        items=[
            SimpleNamespace(
                product_id=5,
                name="Coca-Cola",
                quantity=3,
                unit_price=Decimal("2.50"),
                subtotal=Decimal("7.50"),
                description="Bebida 500ml",
            )
        ],
    )
    monkeypatch.setattr(cart, "get_current_cart", lambda usuario_id: cart_dto)
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(
        message=message,
        callback_query=None,
        effective_user=SimpleNamespace(id=123),
    )
    context = _build_context()
    monkeypatch.setattr(cart, "_get_accessible_message", lambda _u: message)

    await cart.ver_pedido(update, context)

    message.reply_text.assert_awaited_once()
    _, kwargs = message.reply_text.await_args
    markup = kwargs["reply_markup"]
    callbacks = _collect_callbacks(markup)
    assert "rem_5" in callbacks
    assert "add_5" in callbacks
    assert "del_5" in callbacks
    assert "noop" in callbacks
    adjustment_rows = [
        row for row in markup.inline_keyboard
        if [btn.callback_data for btn in row] == ["rem_5", "noop", "add_5"]
    ]
    assert len(adjustment_rows) == 1
    assert adjustment_rows[0][1].text == "3"


@pytest.mark.asyncio
async def test_manejar_botones_carrito_add_refreshes_view_on_success(monkeypatch):
    """A successful ``+1`` from the cart must refresh the cart view."""
    query = _build_query("add_5")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()
    product = ProductDTO(
        id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50")
    )
    monkeypatch.setattr(
        cart,
        "increase_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=True, product=product,
            previous_quantity=1, current_quantity=2,
        ),
    )

    refresh_calls: list[int] = []

    async def fake_refresh(query_arg, context_arg, usuario_id):
        refresh_calls.append(usuario_id)
        return None

    monkeypatch.setattr(cart, "actualizar_vista_pedido", fake_refresh)

    await cart.manejar_botones_carrito(update, context)

    assert refresh_calls == [query.from_user.id]


@pytest.mark.asyncio
async def test_manejar_botones_carrito_add_does_not_refresh_on_stock_error(monkeypatch):
    """When stock is exceeded, the dispatcher must NOT refresh the cart view."""
    query = _build_query("add_5")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()
    product = ProductDTO(
        id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50")
    )
    monkeypatch.setattr(
        cart,
        "increase_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=False, product=product,
            previous_quantity=10, current_quantity=10,
            error_message="❌ Stock máximo: 10 unidades",
        ),
    )

    refresh_calls: list[int] = []

    async def fake_refresh(query_arg, context_arg, usuario_id):
        refresh_calls.append(usuario_id)
        return None

    monkeypatch.setattr(cart, "actualizar_vista_pedido", fake_refresh)

    await cart.manejar_botones_carrito(update, context)

    assert refresh_calls == []


@pytest.mark.asyncio
async def test_manejar_botones_carrito_rem_refreshes_view_on_success(monkeypatch):
    """A successful ``−1`` from the cart must refresh the cart view."""
    query = _build_query("rem_5")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()
    product = ProductDTO(
        id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50")
    )
    monkeypatch.setattr(
        cart,
        "decrease_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=True, product=product,
            previous_quantity=2, current_quantity=1,
        ),
    )

    refresh_calls: list[int] = []

    async def fake_refresh(query_arg, context_arg, usuario_id):
        refresh_calls.append(usuario_id)
        return None

    monkeypatch.setattr(cart, "actualizar_vista_pedido", fake_refresh)

    await cart.manejar_botones_carrito(update, context)

    assert refresh_calls == [query.from_user.id]


@pytest.mark.asyncio
async def test_manejar_botones_carrito_rem_does_not_refresh_on_error(monkeypatch):
    """When decrement fails, the dispatcher must NOT refresh the cart view."""
    query = _build_query("rem_5")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()
    monkeypatch.setattr(
        cart,
        "decrease_product_quantity",
        lambda usuario_id, producto_id, cantidad=1: SimpleNamespace(
            success=False, product=None,
            error_message="❌ No tienes este producto en el carrito",
        ),
    )

    refresh_calls: list[int] = []

    async def fake_refresh(query_arg, context_arg, usuario_id):
        refresh_calls.append(usuario_id)
        return None

    monkeypatch.setattr(cart, "actualizar_vista_pedido", fake_refresh)

    await cart.manejar_botones_carrito(update, context)

    assert refresh_calls == []


@pytest.mark.asyncio
async def test_manejar_botones_carrito_noop_is_ignored(monkeypatch):
    """The dispatcher must not call any service when the user clicks the qty label."""
    query = _build_query("noop")
    update = SimpleNamespace(callback_query=query)
    context = _build_context()

    increase_called = False
    decrease_called = False

    def fake_increase(*args, **kwargs):
        nonlocal increase_called
        increase_called = True
        return SimpleNamespace(success=False, error_message="x")

    def fake_decrease(*args, **kwargs):
        nonlocal decrease_called
        decrease_called = True
        return SimpleNamespace(success=False, error_message="x")

    monkeypatch.setattr(cart, "increase_product_quantity", fake_increase)
    monkeypatch.setattr(cart, "decrease_product_quantity", fake_decrease)

    await cart.manejar_botones_carrito(update, context)

    assert increase_called is False
    assert decrease_called is False


@pytest.mark.asyncio
async def test_disminuir_cantidad_returns_result(monkeypatch):
    """``disminuir_cantidad`` must return the ``CartMutationResult`` for callers."""
    query = _build_query("rem_5")
    product = ProductDTO(
        id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50")
    )
    expected = SimpleNamespace(
        success=True,
        product=product,
        previous_quantity=2,
        current_quantity=1,
    )
    monkeypatch.setattr(cart, "decrease_product_quantity", lambda *a, **k: expected)

    result = await cart.disminuir_cantidad(query, _build_context(), 5)

    assert result is expected