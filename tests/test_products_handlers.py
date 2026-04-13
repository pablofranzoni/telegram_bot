"""Async handler tests for shared.handlers.products."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ConversationHandler

from shared.dtos import CategoryDTO, ProductDTO
from shared.handlers import products
from utils.constants import EstadoConversacion


def _build_message(text: str | None = None, user_id: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        reply_text=AsyncMock(),
        from_user=SimpleNamespace(id=user_id),
    )


def _build_context(user_data: dict[str, object] | None = None) -> SimpleNamespace:
    return SimpleNamespace(user_data={} if user_data is None else user_data)


@pytest.mark.asyncio
async def test_obtener_categorias_saves_options_and_returns_state(monkeypatch):
    message = _build_message()
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context()

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    monkeypatch.setattr(
        products,
        "list_categories",
        lambda: [
            CategoryDTO(name="bebidas", description="Frias"),
            CategoryDTO(name="hamburguesas", description="A la plancha"),
        ],
    )

    result = await products.obtener_categorias(update, context)

    assert result == EstadoConversacion.ESPERANDO_CATEGORIA.value
    assert context.user_data["letras"] == ["A", "B"]
    categorias = context.user_data["categorias"]
    assert isinstance(categorias, list)
    assert categorias[0].name == "bebidas"
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.await_args
    assert "selecciona una categoría" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_obtener_categorias_returns_end_when_empty(monkeypatch):
    message = _build_message()
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context()

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    monkeypatch.setattr(products, "list_categories", lambda: [])

    result = await products.obtener_categorias(update, context)

    assert result == ConversationHandler.END
    message.reply_text.assert_awaited_once_with("No hay productos disponibles en este momento.")


@pytest.mark.asyncio
async def test_seleccionar_categoria_rejects_invalid_option():
    message = _build_message("Z")
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context(
        {
            "categorias": [CategoryDTO(name="bebidas", description="Frias")],
            "letras": ["A"],
        }
    )

    products._get_accessible_message = lambda update_arg: message

    result = await products.seleccionar_categoria(update, context)

    assert result == EstadoConversacion.ESPERANDO_CATEGORIA.value
    message.reply_text.assert_awaited_once()
    args, _ = message.reply_text.await_args
    assert "opción no válida" in args[0].lower()


@pytest.mark.asyncio
async def test_seleccionar_categoria_stores_selection_and_shows_products(monkeypatch):
    message = _build_message("A")
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context(
        {
            "categorias": [CategoryDTO(name="bebidas", description="Frias")],
            "letras": ["A"],
        }
    )

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    shown = {"called": False}

    async def fake_show(update_arg, context_arg):
        shown["called"] = True

    monkeypatch.setattr(products, "mostrar_productos_categoria_texto", fake_show)

    result = await products.seleccionar_categoria(update, context)

    assert result == EstadoConversacion.ESPERANDO_PRODUCTO.value
    assert context.user_data == {"categoria_seleccionada": "bebidas", "pagina_productos": 1}
    assert shown["called"] is True


@pytest.mark.asyncio
async def test_mostrar_productos_categoria_texto_saves_products_and_options(monkeypatch):
    message = _build_message()
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context({"categoria_seleccionada": "bebidas", "pagina_productos": 1})

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    monkeypatch.setattr(
        products,
        "list_products_by_category_page",
        lambda category, page, page_size: (
            [
                ProductDTO(id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50")),
                ProductDTO(id=6, name="Sprite", description="Bebida lima-limon", price=Decimal("2.80")),
            ],
            True,
        ),
    )

    await products.mostrar_productos_categoria_texto(update, context)

    assert context.user_data["opciones_productos"] == ["A", "B"]
    assert context.user_data["hay_mas_productos"] is True
    productos_actuales = context.user_data["productos_actuales"]
    assert isinstance(productos_actuales, list)
    assert productos_actuales[0].name == "Coca-Cola"
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.await_args
    assert "bebidas" in args[0].lower()
    assert "escribe 'n'" in args[0].lower()
    assert kwargs["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_seleccionar_producto_with_zero_returns_to_categories(monkeypatch):
    message = _build_message("0")
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context(
        {
            "productos_actuales": [ProductDTO(id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50"))],
            "opciones_productos": ["A"],
            "pagina_productos": 1,
            "hay_mas_productos": False,
        }
    )

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    called = {"count": 0}

    async def fake_obtener_categorias(update_arg, context_arg):
        called["count"] += 1

    monkeypatch.setattr(products, "obtener_categorias", fake_obtener_categorias)

    result = await products.seleccionar_producto(update, context)

    assert result == EstadoConversacion.ESPERANDO_CATEGORIA.value
    assert context.user_data == {}
    assert called["count"] == 1
    message.reply_text.assert_awaited_once_with("Volviendo a categorías...")


@pytest.mark.asyncio
async def test_seleccionar_producto_with_n_loads_next_page(monkeypatch):
    message = _build_message("N")
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context(
        {
            "categoria_seleccionada": "bebidas",
            "productos_actuales": [ProductDTO(id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50"))],
            "opciones_productos": ["A"],
            "pagina_productos": 1,
            "hay_mas_productos": True,
        }
    )

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    shown = {"count": 0}

    async def fake_show(update_arg, context_arg):
        shown["count"] += 1

    monkeypatch.setattr(products, "mostrar_productos_categoria_texto", fake_show)

    result = await products.seleccionar_producto(update, context)

    assert result == EstadoConversacion.ESPERANDO_PRODUCTO.value
    assert context.user_data["pagina_productos"] == 2
    assert shown["count"] == 1


@pytest.mark.asyncio
async def test_seleccionar_producto_with_p_on_first_page_rejects(monkeypatch):
    message = _build_message("P")
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context(
        {
            "productos_actuales": [ProductDTO(id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50"))],
            "opciones_productos": ["A"],
            "pagina_productos": 1,
            "hay_mas_productos": False,
        }
    )

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)

    result = await products.seleccionar_producto(update, context)

    assert result == EstadoConversacion.ESPERANDO_PRODUCTO.value
    message.reply_text.assert_awaited_once_with("Ya estás en la primera página.")


@pytest.mark.asyncio
async def test_seleccionar_producto_stores_current_product_and_shows_detail(monkeypatch):
    message = _build_message("A")
    product = ProductDTO(id=5, name="Coca-Cola", description="Bebida 500ml", price=Decimal("2.50"))
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context(
        {
            "productos_actuales": [product],
            "opciones_productos": ["A"],
        }
    )

    monkeypatch.setattr(products, "_get_accessible_message", lambda update_arg: message)
    shown: dict[str, object] = {}

    async def fake_show(update_arg, context_arg, producto):
        shown["producto"] = producto

    monkeypatch.setattr(products, "mostrar_detalle_producto", fake_show)

    result = await products.seleccionar_producto(update, context)

    assert result == EstadoConversacion.ESPERANDO_PRODUCTO.value
    assert context.user_data["producto_actual"] == product
    assert shown["producto"] == product


@pytest.mark.asyncio
async def test_cancelar_opcion_producto_clears_session():
    message = _build_message()
    update = SimpleNamespace(message=message, callback_query=None)
    context = _build_context({"categoria_seleccionada": "bebidas", "producto_actual": object()})

    products._get_accessible_message = lambda update_arg: message

    result = await products.cancelar_opcion_producto(update, context)

    assert result == ConversationHandler.END
    assert context.user_data == {}
    message.reply_text.assert_awaited_once()
    args, _ = message.reply_text.await_args
    assert "operación cancelada" in args[0].lower()