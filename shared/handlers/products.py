"""Handlers relacionados con la navegación por categorías y selección de productos."""

from collections.abc import MutableMapping
import logging
from typing import cast

from telegram import Message, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from shared.dtos import CategoryDTO, ProductDTO
from utils.constants import EstadoConversacion
from utils.logging_config import configure_logging
from shared.services.catalog_service import get_product_by_id, list_categories, list_products_by_category_page

configure_logging()

logger = logging.getLogger(__name__)

PRODUCTS_PAGE_SIZE = 10


def _get_user_data(context: ContextTypes.DEFAULT_TYPE) -> MutableMapping[str, object]:
    """Return a mutable user_data mapping even when typing marks it optional."""
    return cast(MutableMapping[str, object], context.user_data)


def _get_accessible_message(update: Update) -> Message | None:
    """Return a reply-capable message when available."""
    if isinstance(update.message, Message):
        return update.message
    callback_query = update.callback_query
    if callback_query and isinstance(callback_query.message, Message):
        return callback_query.message
    return None


def _clear_product_navigation_state(user_data: MutableMapping[str, object]) -> None:
    """Remove transient product selection and pagination data from the session."""
    for key in (
        'productos_actuales',
        'opciones_productos',
        'producto_actual',
        'pagina_productos',
        'hay_mas_productos',
    ):
        user_data.pop(key, None)


async def obtener_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra las categorías de productos disponibles para selección."""
    user_data = _get_user_data(context)
    # Obtener el mensaje de donde sea que venga
    if update.callback_query:
        mensaje = _get_accessible_message(update)
        await update.callback_query.answer()
    else:
        mensaje = _get_accessible_message(update)

    if not mensaje:
        return ConversationHandler.END

    categorias = list_categories()

    if not categorias:
        await mensaje.reply_text("No hay productos disponibles en este momento.")
        return ConversationHandler.END

    # Asignar una letra a cada categoría (A, B, C, ...)
    letras = [chr(65 + i) for i in range(len(categorias))]  # 65 es el código ASCII de 'A'

    # Guardar las categorías en context.user_data para usarlas después
    #categorias trae una tupla de (nombre, descripcion)
    user_data['categorias'] = categorias
    user_data['letras'] = letras

    # Crear el mensaje con las opciones
    opciones_texto = "Selecciona una categoría escribiendo la letra correspondiente:\n\n"
    for letra, categoria in zip(letras, categorias):
        opciones_texto += f"*{letra}) {categoria.name.capitalize()}*\n"
        opciones_texto += f"_{categoria.description}_\n"
        opciones_texto += "─" * 35 + "\n"

    opciones_texto += "\nEjemplo: Escribe 'A' para ver los productos de la primera categoría"

    await mensaje.reply_text(opciones_texto, parse_mode='Markdown')

    return EstadoConversacion.ESPERANDO_CATEGORIA.value


async def seleccionar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la selección de categoría por letra."""
    mensaje = _get_accessible_message(update)
    if not mensaje or not mensaje.text:
        return ConversationHandler.END
    user_data = _get_user_data(context)
    texto = mensaje.text.strip().upper()

    # Opción para cancelar
    if texto == "0":
        await mensaje.reply_text("Operación cancelada.")
        # Limpiar datos
        user_data.clear()
        return ConversationHandler.END

    # Verificar si hay categorías guardadas
    if 'categorias' not in user_data or 'letras' not in user_data:
        await mensaje.reply_text("Por favor, primero usa /ver_productos para ver las categorías disponibles.")
        return ConversationHandler.END

    categorias = cast(list[CategoryDTO], user_data['categorias'])
    letras = cast(list[str], user_data['letras'])

    # Verificar si el texto es una letra válida
    if texto in letras:
        indice = letras.index(texto)
        categoria = categorias[indice]

        # Guardar solo el nombre de la categoría seleccionada
        user_data['categoria_seleccionada'] = categoria.name
        user_data['pagina_productos'] = 1

        # Limpiar datos de categorías (ya no los necesitamos)
        del user_data['categorias']
        del user_data['letras']

        # Mostrar productos de la categoría
        await mostrar_productos_categoria_texto(update, context)

        # Siguiente estado: seleccionar producto
        return EstadoConversacion.ESPERANDO_PRODUCTO.value
    else:
        # Mostrar mensaje de error con las opciones disponibles
        opciones = ", ".join(letras)
        await mensaje.reply_text(
            f"❌ Opción no válida. Por favor, escribe una de estas letras: {opciones}\n"
            "O escribe 0 para cancelar"
        )
        # Permanecer en el mismo estado
        return EstadoConversacion.ESPERANDO_CATEGORIA.value


async def mostrar_productos_categoria_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra productos de una categoría usando letras."""
    user_data = _get_user_data(context)
    message = _get_accessible_message(update)
    if not message:
        return
    categoria = user_data.get('categoria_seleccionada')
    if not isinstance(categoria, str):
        return
    pagina_actual_raw = user_data.get('pagina_productos', 1)
    pagina_actual = pagina_actual_raw if isinstance(pagina_actual_raw, int) and pagina_actual_raw > 0 else 1
    productos, hay_mas_productos = list_products_by_category_page(
        categoria,
        page=pagina_actual,
        page_size=PRODUCTS_PAGE_SIZE,
    )

    if not productos:
        _clear_product_navigation_state(user_data)
        await message.reply_text(f"No hay productos en la categoría {categoria}")
        # Volver a categorías
        await obtener_categorias(update, context)
        return

    # Asignar letras a productos
    opciones = [chr(65 + i) for i in range(len(productos))]

    # Guardar para el siguiente estado
    user_data['productos_actuales'] = productos
    user_data['opciones_productos'] = opciones
    user_data['pagina_productos'] = pagina_actual
    user_data['hay_mas_productos'] = hay_mas_productos

    # Crear mensaje
    mensaje = f"*{categoria.capitalize()}* 🍽️\n"
    mensaje += f"_Página {pagina_actual}_\n\n"

    for letra, producto in zip(opciones, productos):
        mensaje += f"*{letra}) {producto.name}*\n"
        mensaje += f"   _{producto.description}_\n"
        mensaje += f"   💰 ${producto.price:.2f}\n"
        mensaje += "─" * 20 + "\n"

    mensaje += "\nEjemplo: Escribe 'A' para ver el detalle del primer producto"
    if pagina_actual > 1:
        mensaje += "\nEscribe 'P' para ver la página anterior"
    if hay_mas_productos:
        mensaje += "\nEscribe 'N' para ver la página siguiente"
    mensaje += "\nO escribe 0 para volver a las categorías"

    await message.reply_text(mensaje, parse_mode='Markdown')


async def mostrar_detalle_producto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    producto,
):
    """Muestra la ficha del producto seleccionado con acciones."""
    stock_disponible = producto.stock_available
    disponibilidad = (
        f"{stock_disponible} unidad(es) en stock"
        if isinstance(stock_disponible, int)
        else "Disponible"
        if stock_disponible is None
        else "Sin stock"
    )

    mensaje = f"*{producto.name}*\n\n"
    mensaje += f"_{producto.description}_\n\n"
    mensaje += f"*Precio:* ${producto.price:.2f}\n"
    mensaje += f"*Disponibilidad:* {disponibilidad}\n\n"
    mensaje += "Selecciona una acción:"

    keyboard = [
        [InlineKeyboardButton("✅ Agregar", callback_data=f"add_{producto.id}")],
        [InlineKeyboardButton("💬 +Info", callback_data=f"info_{producto.id}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            mensaje,
            reply_markup=reply_markup,
            parse_mode='Markdown',
        )
    else:
        message = _get_accessible_message(update)
        if not message:
            return
        await message.reply_text(
            mensaje,
            reply_markup=reply_markup,
            parse_mode='Markdown',
        )


async def mostrar_productos_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra productos de una categoría recibida por callback ('cat_<categoria>')."""
    user_data = _get_user_data(context)
    if update.callback_query:
        data: str | None = update.callback_query.data
        if data and data.startswith('cat_'):
            categoria = data.replace('cat_', '', 1)
            user_data['categoria_seleccionada'] = categoria
            user_data['pagina_productos'] = 1
            await mostrar_productos_categoria_texto(update, context)
            return

    # Fallback: mostrar categorías si no se entiende el callback
    await obtener_categorias(update, context)


async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la selección de producto por letra."""
    mensaje = _get_accessible_message(update)
    texto: str | None = mensaje.text.strip().upper() if mensaje and mensaje.text else None
    #texto = mensaje.text.strip().upper()

    if not mensaje or texto is None:
        return ConversationHandler.END
    user_data = _get_user_data(context)

    cliente_id: int | None = mensaje.from_user.id if mensaje and mensaje.from_user and mensaje.from_user.id else None
    logger.debug("Seleccion de producto iniciada", extra={"cliente_id": cliente_id, "texto": texto})

    pagina_actual_raw = user_data.get('pagina_productos', 1)
    pagina_actual = pagina_actual_raw if isinstance(pagina_actual_raw, int) and pagina_actual_raw > 0 else 1
    hay_mas_productos = bool(user_data.get('hay_mas_productos', False))

    # Opción para volver a categorías
    if texto == "0":
        await mensaje.reply_text("Volviendo a categorías...")
        _clear_product_navigation_state(user_data)

        # Volver a mostrar categorías
        await obtener_categorias(update, context)
        return EstadoConversacion.ESPERANDO_CATEGORIA.value

    if texto == "P":
        if pagina_actual == 1:
            await mensaje.reply_text("Ya estás en la primera página.")
            return EstadoConversacion.ESPERANDO_PRODUCTO.value
        user_data['pagina_productos'] = pagina_actual - 1
        await mostrar_productos_categoria_texto(update, context)
        return EstadoConversacion.ESPERANDO_PRODUCTO.value

    if texto == "N":
        if not hay_mas_productos:
            await mensaje.reply_text("No hay más productos para mostrar.")
            return EstadoConversacion.ESPERANDO_PRODUCTO.value
        user_data['pagina_productos'] = pagina_actual + 1
        await mostrar_productos_categoria_texto(update, context)
        return EstadoConversacion.ESPERANDO_PRODUCTO.value

    # Verificar si hay productos guardados
    if 'productos_actuales' not in user_data or 'opciones_productos' not in user_data:
        await mensaje.reply_text("Error en la sesión. Por favor, empieza de nuevo con /ver_productos")
        return ConversationHandler.END

    productos = cast(list[ProductDTO], user_data['productos_actuales'])
    opciones = cast(list[str], user_data['opciones_productos'])

    # Verificar si la letra es válida
    if texto in opciones:
        indice = opciones.index(texto)
        producto = productos[indice]
        user_data['producto_actual'] = producto
        logger.info(
            "Producto seleccionado",
            extra={"cliente_id": cliente_id, "producto_id": producto.id, "producto_nombre": producto.name},
        )

        await mostrar_detalle_producto(update, context, producto)
        return EstadoConversacion.ESPERANDO_PRODUCTO.value

    else:
        # Letra no válida
        opciones_texto = ", ".join(opciones)
        navegacion = []
        if pagina_actual > 1:
            navegacion.append("P")
        if hay_mas_productos:
            navegacion.append("N")
        if navegacion:
            opciones_texto = f"{opciones_texto}, {', '.join(navegacion)}"
        await mensaje.reply_text(
            f"❌ Opción no válida. Letras disponibles: {opciones_texto}\n"
            f"O escribe 0 para volver a categorías"
        )
        return EstadoConversacion.ESPERANDO_PRODUCTO.value


async def cancelar_opcion_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación de selección de productos."""
    message = _get_accessible_message(update)
    if not message:
        return ConversationHandler.END
    user_data = _get_user_data(context)
    await message.reply_text(
        "Operación cancelada. Puedes volver a empezar con /ver_productos"
    )
    # Limpiar todos los datos
    user_data.clear()
    return ConversationHandler.END
