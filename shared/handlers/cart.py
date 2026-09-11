"""Handlers relacionados con el carrito y el pago."""
from collections.abc import MutableMapping
import logging
import traceback
import json
import html
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError

from shared.handlers.products import buscar_productos, obtener_categorias
from shared.dtos import CartMutationResult
from utils.constants import EstadoConversacion
from utils.logger_factory import get_bot_logger, log_bot_event
from shared.services.cart_service import (
    add_product_to_cart,
    clear_cart,
    decrease_product_quantity,
    get_cart_by_invoice,
    get_current_cart,
    get_current_cart_id,
    increase_product_quantity,
    remove_product_from_cart,
)
from shared.services.catalog_service import get_product_by_id
from shared.services.checkout_service import finalize_checkout
from utils.config import Config

logger = get_bot_logger(__name__)

DEVELOPER_CHAT_ID = 7225069015

PRODUCT_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp')


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


def _parse_invoice_id(raw_invoice_id: str) -> str | int:
    """Parse callback invoice ids preserving int ids and UUID/text ids."""
    return int(raw_invoice_id) if raw_invoice_id.isdigit() else raw_invoice_id


async def _safe_edit_callback_message(
    query: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> None:
    """Edit the callback message, falling back to ``edit_message_caption`` for media.

    The handler tries to edit the message as text first. When the source is a
    media message (e.g. a product photo with a caption) Telegram rejects
    ``edit_message_text`` with ``BadRequest: There is no text in the message to
    edit``; in that case the handler retries with ``edit_message_caption`` so
    the photo is preserved and only the caption (and the keyboard) is updated.
    """
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except BadRequest as exc:
        error_text = str(exc).lower()

        # Telegram raises this when the new message equals the current one.
        if "message is not modified" in error_text:
            logger.debug("Skipping edit_message_text because message did not change")
            return

        # Source message has no text body (e.g. it's a photo with a caption).
        # Retry with edit_message_caption so the image stays and only the
        # caption/keyboard are updated.
        if "there is no text in the message to edit" in error_text:
            await _try_edit_caption(
                query, text, reply_markup=reply_markup, parse_mode=parse_mode
            )
            return

        # Message is too long for either text body or caption. The mutation
        # already succeeded; just log and leave the previous message in place
        # rather than surfacing a generic error to the user.
        if "message is too long" in error_text or "caption is too long" in error_text:
            logger.warning(
                "Skipping edit_message_text because the rendered content is too long",
                extra={"preview": text[:80]},
            )
            return

        # Some callback origins are not editable (or no longer exist); send a new message instead.
        if (
            "message can't be edited" in error_text
            or "message to edit not found" in error_text
        ) and isinstance(query.message, Message):
            await query.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return

        logger.exception("Unexpected telegram BadRequest while editing callback message")
        raise


async def _try_edit_caption(
    query: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None,
    parse_mode: str | None,
) -> None:
    """Edit a media message's caption with the same fallback rules as text edits."""
    try:
        await query.edit_message_caption(
            caption=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except BadRequest as caption_exc:
        caption_error_text = str(caption_exc).lower()
        if "message is not modified" in caption_error_text:
            logger.debug("Skipping edit_message_caption because caption did not change")
            return
        if "caption is too long" in caption_error_text or "message is too long" in caption_error_text:
            logger.warning(
                "Skipping edit_message_caption because the caption is too long",
                extra={"preview": text[:80]},
            )
            return
        logger.exception(
            "Unexpected telegram BadRequest while editing callback caption",
        )
        raise


def _escape_markdown(text: str) -> str:
    """Escape special Markdown characters to prevent parse errors."""
    if not text:
        return text
    return text.replace('_', r'\_').replace('*', r'\*').replace('`', r'\`').replace('[', r'\[').replace(']', r'\]')


async def _safe_answer_callback(query: CallbackQuery, text: str | None = None) -> None:
    """Answer callback queries without breaking flows when already answered."""
    try:
        await query.answer(text)
    except BadRequest:
        logger.debug("Skipping callback answer because it was already answered or expired")
    except TelegramError:
        logger.debug(
            "Skipping callback answer because Telegram rejected the call",
            exc_info=True,
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    error = context.error
    if error is None:
        return
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, error, error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    message = f"❌ Ocurrió un error: la acción no pudo realizarse\n"

    # Finally, send the message to developer
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )


async def manejar_botones_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones del carrito (callback queries)."""
    query = update.callback_query
    if not query or not isinstance(query.data, str):
        return

    # Siempre responde el callback para que Telegram deje de mostrar el "relojito"
    await query.answer()
    data = query.data

    log_bot_event(logger, update, "Callback de carrito recibido", extra={"callback_data": data})

    if data == 'noop':
        return

    if data.startswith('rem_'):
        producto_id = int(data.replace('rem_', ''))
        resultado = await disminuir_cantidad(query, context, producto_id)
        if resultado.success:
            await actualizar_vista_pedido(query, context, query.from_user.id)

    elif data.startswith('add_'):
        producto_id = int(data.replace('add_', ''))
        resultado = await aumentar_cantidad(query, context, producto_id)
        if resultado.success:
            await actualizar_vista_pedido(query, context, query.from_user.id)

    elif data.startswith('del_'):
        producto_id = int(data.replace('del_', ''))
        await eliminar_producto(query, context, producto_id)

    elif data.startswith('info_'):
        raw_id = data.replace('info_', '', 1)
        if raw_id.isdigit():
            await mostrar_foto_producto(query, context, int(raw_id))
        else:
            await _safe_answer_callback(query, "❌ Producto no encontrado")

    elif data == 'vaciar_todo':
        await vaciar_pedido(query, context)

    elif data == 'ver_productos':
        await obtener_categorias(update, context)

    elif data == 'volver_carrito':
        await ver_pedido(update, context)


async def agregar_y_salir_flujo_productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle add_ callbacks and finish the product conversation flow."""
    query = update.callback_query
    if not query or not isinstance(query.data, str) or not query.data.startswith('add_'):
        return ConversationHandler.END

    await query.answer()
    producto_id = int(query.data.replace('add_', '', 1))
    result = await aumentar_cantidad(query, context, producto_id)

    log_bot_event(
        logger,
        update,
        "Producto agregado al carrito desde flujo de productos",
        extra={
            "producto_id": producto_id,
            "producto_nombre": result.product.name if result and result.product else None,
            "cantidad": getattr(result, "current_quantity", None) if result else None,
        },
    )

    user_data = _get_user_data(context)
    for key in (
        'productos_actuales',
        'opciones_productos',
        'producto_actual',
        'pagina_productos',
        'hay_mas_productos',
        'categoria_seleccionada',
    ):
        user_data.pop(key, None)

    nombre_producto = result.product.name if result and result.product else "Producto"
    guidance_message = (
        f"✅ {nombre_producto} agregado al pedido.\n\n"
        "Para seguir comprando, usa /ver_productos.\n"
        "Para revisar el carrito, usa Mi Pedido o /mi_pedido."
    )
    reply_text = getattr(getattr(query, "message", None), "reply_text", None)
    if reply_text is not None:
        await reply_text(guidance_message)

    return ConversationHandler.END


async def disminuir_cantidad(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    producto_id: int,
    cantidad: int = 1,
) -> CartMutationResult:
    """Disminuye la cantidad de un producto en el carrito.

    Devuelve el :class:`CartMutationResult` para que el caller (ej. el dispatcher
    de callbacks) pueda decidir si refresca la vista del carrito.
    """
    usuario_id = query.from_user.id
    result = decrease_product_quantity(usuario_id, producto_id, cantidad)

    if result.success and result.product:
        await _safe_answer_callback(
            query,
            f"➖ {result.product.name}: {result.previous_quantity} → {result.current_quantity}",
        )
        return result

    await _safe_answer_callback(query, result.error_message or "❌ Error al actualizar cantidad")
    return result


async def mostrar_detalle_producto(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, producto_id: int):
    """Muestra la ficha del producto con las acciones principales."""
    producto = get_product_by_id(producto_id)

    if not producto:
        await _safe_answer_callback(query, "❌ Producto no encontrado")
        return

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
        [InlineKeyboardButton("✅ Agregar", callback_data=f'add_{producto.id}')],
        [InlineKeyboardButton("💬 +Info", callback_data=f'info_{producto.id}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await _safe_answer_callback(query)
    await _safe_edit_callback_message(
        query,
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


def _resolve_product_image(product_id: int) -> Path | None:
    """Return the path to the product image inside the configured directory.

    Files are looked up as ``<id>.<ext>`` for each entry in
    :data:`PRODUCT_IMAGE_EXTENSIONS`. Returns ``None`` when the directory is
    missing or no file matches. The configured directory is resolved and the
    candidate path is verified to be inside it to prevent traversal.
    """
    try:
        base = Path(Config.PRODUCT_IMAGES_DIR).expanduser().resolve()
    except OSError:
        logger.warning(
            "PRODUCT_IMAGES_DIR could not be resolved: %s",
            Config.PRODUCT_IMAGES_DIR,
        )
        return None

    if not base.is_dir():
        logger.debug(
            "Imagen de producto no encontrada: directorio inexistente",
            extra={"producto_id": product_id, "images_dir": str(base)},
        )
        return None

    for ext in PRODUCT_IMAGE_EXTENSIONS:
        candidate = (base / f"{product_id}{ext}").resolve()
        try:
            if candidate.is_file() and base in candidate.parents:
                logger.debug(
                    "Imagen de producto encontrada",
                    extra={
                        "producto_id": product_id,
                        "image_path": str(candidate),
                        "extension": ext,
                    },
                )
                return candidate
        except OSError:
            continue
        logger.debug(
            "Imagen de producto no encontrada: probando siguiente extension",
            extra={"producto_id": product_id, "candidate": str(candidate), "extension": ext},
        )

    logger.debug(
        "Imagen de producto no encontrada: ninguna extension coincide",
        extra={
            "producto_id": product_id,
            "images_dir": str(base),
            "extensions_tried": list(PRODUCT_IMAGE_EXTENSIONS),
        },
    )
    return None


async def mostrar_foto_producto(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    producto_id: int,
):
    """Send the product photo with the ficha as caption (replaces text-only detail)."""
    logger.debug(
        "mostrar_foto_producto invoked",
        extra={
            "producto_id": producto_id,
            "chat_id": getattr(query.message, "chat_id", None) if query.message else None,
            "images_dir": Config.PRODUCT_IMAGES_DIR,
        },
    )
    producto = get_product_by_id(producto_id)

    if not producto:
        logger.debug(
            "mostrar_foto_producto: producto no encontrado",
            extra={"producto_id": producto_id},
        )
        await _safe_answer_callback(query, "❌ Producto no encontrado")
        return

    chat_id = getattr(query.message, "chat_id", None) if query.message else None
    if not chat_id:
        logger.debug(
            "mostrar_foto_producto: callback sin message/chat_id",
            extra={"producto_id": producto_id},
        )
        await _safe_answer_callback(query, "❌ No se pudo enviar la imagen")
        return

    image_path = _resolve_product_image(producto_id)
    if image_path is None:
        logger.debug(
            "mostrar_foto_producto: sin imagen para el producto",
            extra={"producto_id": producto_id, "images_dir": Config.PRODUCT_IMAGES_DIR},
        )
        await _safe_answer_callback(query, "📷 Sin imagen disponible")
        return

    stock_disponible = producto.stock_available
    disponibilidad = (
        f"{stock_disponible} unidad(es) en stock"
        if isinstance(stock_disponible, int)
        else "Disponible"
        if stock_disponible is None
        else "Sin stock"
    )

    caption = (
        f"*{producto.name}*\n\n"
        f"_{producto.description}_\n\n"
        f"*Precio:* ${producto.price:.2f}\n"
        f"*Disponibilidad:* {disponibilidad}"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Agregar", callback_data=f'add_{producto.id}')],
        [InlineKeyboardButton("💬 +Info", callback_data=f'info_{producto.id}')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await _safe_answer_callback(query)
    try:
        with image_path.open('rb') as photo_file:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo_file,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='Markdown',
            )
    except (OSError, BadRequest) as exc:
        logger.exception(
            "Error enviando imagen del producto",
            extra={"producto_id": producto_id, "image_path": str(image_path)},
        )
        await _safe_answer_callback(query, "❌ No se pudo enviar la imagen")


async def aumentar_cantidad(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    producto_id: int,
    cantidad: int = 1,
) -> CartMutationResult:
    """Aumenta la cantidad de un producto en el carrito.

    On success the function returns the :class:`CartMutationResult` so the
    caller can craft its own confirmation message; it does not edit the
    callback message (the per-product ack previously rendered with the
    ``previous → current`` arrow is intentionally gone — the caller is
    responsible for user-facing feedback).

    On failure the function edits the message in place with the error so the
    user still sees what went wrong when invoked from the cart dispatcher.
    """
    usuario_id = query.from_user.id
    result = increase_product_quantity(usuario_id, producto_id, cantidad)

    if result.success and result.product:
        return result

    await _safe_edit_callback_message(
        query,
        result.error_message or "❌ Error al actualizar cantidad",
    )
    return result


async def agregar_producto_al_pedido(query: CallbackQuery, producto_id: int, cantidad: int = 1):
    """Agrega un nuevo producto al pedido."""
    # Siempre responde el callback para que Telegram deje de mostrar el "relojito"
    await query.answer()

    usuario_id = query.from_user.id
    result = add_product_to_cart(usuario_id, producto_id, cantidad)

    if result.success and result.product:
        await _safe_edit_callback_message(
            query,
            f"➕ {result.product.name}: {result.current_quantity}",
        )
        return

    await query.answer(result.error_message or "❌ Error al agregar producto")


async def vaciar_pedido(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE):
    """Elimina todos los productos del pedido actual."""
    usuario_id = query.from_user.id

    if not get_current_cart_id(usuario_id):
        await query.answer("❌ No tienes productos en el pedido")
        return

    try:
        eliminado = clear_cart(usuario_id)

        if eliminado:
            logger.info("Pedido vaciado", extra={"telegram_user_id": usuario_id})
            await query.answer("🗑️ Pedido vaciado")
            await query.edit_message_text(
                "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
                parse_mode='Markdown',
            )
        else:
            await query.answer("❌ Error al vaciar el pedido")

    except Exception as e:
        logger.exception("Error al vaciar pedido del usuario %s", usuario_id)
        await query.answer("❌ Error interno al vaciar el pedido")


async def eliminar_producto(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, producto_id: int, con_confirmacion: bool = True):
    """Elimina un producto del carrito."""
    usuario_id = query.from_user.id

    pedido_id = get_current_cart_id(usuario_id)
    if not pedido_id:
        await query.answer("❌ No tienes productos en el carrito")
        return

    producto_info = get_product_by_id(producto_id)

    if not producto_info:
        await query.answer("❌ Producto no encontrado")
        return

    producto_nombre = producto_info.name

    if con_confirmacion:
        await mostrar_confirmacion_eliminar(query, producto_id, producto_nombre, pedido_id)
    else:
        await ejecutar_eliminacion(query, context, producto_id, producto_nombre, pedido_id, usuario_id)


async def mostrar_confirmacion_eliminar(query: CallbackQuery, producto_id: int, producto_nombre: str, pedido_id: int):
    """Muestra diálogo de confirmación antes de quitar o eliminar.

    El título y la acción del botón dependen de la cantidad actual del producto
    en el carrito:

    - ``cantidad > 1`` → "Confirmación de quitar unidad" + botón "Quitar Cantidad"
      (decrementa en 1; el producto sigue en el carrito).
    - ``cantidad == 1`` → "Confirmar eliminación" + botón "Eliminar" (saca el
      producto del carrito por completo).
    """
    cart = get_cart_by_invoice(pedido_id)
    cantidad_actual = 0
    if cart is not None:
        for item in cart.items:
            if item.product_id == producto_id:
                cantidad_actual = item.quantity
                break

    if cantidad_actual > 1:
        restantes = cantidad_actual - 1
        title = "⚠️ *Confirmación de quitar unidad*"
        body = (
            f"¿Quitar una unidad de **{producto_nombre}** del carrito?\n\n"
            f"Te quedarán *{restantes}* unidad(es) en el carrito."
        )
        action_label = "➖ Quitar Cantidad"
        callback_data = f'confirm_del_one_{producto_id}_{pedido_id}'
    else:
        title = "⚠️ *Confirmar eliminación*"
        body = (
            f"¿Estás seguro de eliminar **{producto_nombre}** del carrito?\n\n"
            f"Esta acción no se puede deshacer."
        )
        action_label = "🗑️ Eliminar"
        callback_data = f'confirm_del_{producto_id}_{pedido_id}'

    keyboard = [
        [
            InlineKeyboardButton(action_label, callback_data=callback_data),
            InlineKeyboardButton("❌ Cancelar", callback_data='cancel_del'),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"{title}\n\n{body}",
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


async def mostrar_confirmacion_finalizar_carrito(query: CallbackQuery, pedido_id: str | int):
    """Muestra diálogo de confirmación antes de finalizar el pedido."""
    cart = get_cart_by_invoice(pedido_id)
    if not cart or cart.is_empty:
        await query.edit_message_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return

    mensaje = f"⚠️ *Confirmar finalización del pedido*\n\n"
    mensaje += "Una vez finalizado, no podrás hacer más cambios.\n\n"

    for item in cart.items:
        mensaje += f"*{item.name}* x {item.quantity}\n"
        mensaje += f"   _{item.description}_\n"
        mensaje += f"   💰 ${item.unit_price:.2f} c/u | Subtotal: ${item.subtotal:.2f}\n"
        mensaje += "─" * 30 + "\n"
    mensaje += f"\n*Total: ${cart.total:.2f}*"

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Sí, finalizar",
                callback_data=f'confirm_finalize_{pedido_id}',
            ),
            InlineKeyboardButton(
                "❌ No, cancelar",
                callback_data='cancel_finalize',
            ),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


async def ejecutar_eliminacion(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    producto_id: int,
    producto_nombre: str,
    pedido_id: str | int,
    usuario_id: int,
):
    """Ejecuta la eliminación del producto."""
    try:
        eliminado = remove_product_from_cart(pedido_id, producto_id)

        if eliminado.success:
            logger.info(
                "Producto eliminado del carrito",
                extra={
                    "telegram_user_id": usuario_id,
                    "pedido_id": pedido_id,
                    "producto_id": producto_id,
                    "producto_nombre": producto_nombre,
                },
            )
            await _safe_answer_callback(query, f"✅ {producto_nombre} eliminado")
            pedido_actual = get_current_cart(usuario_id)

            if not pedido_actual:
                await _safe_edit_callback_message(
                    query,
                    "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
                    parse_mode='Markdown',
                )
            else:
                await actualizar_vista_pedido(query, context, usuario_id)
        else:
            await _safe_answer_callback(
                query,
                eliminado.error_message or "❌ Error al eliminar el producto",
            )

    except Exception as e:
        logger.exception(
            "Error eliminando producto del carrito",
            extra={"usuario_id": usuario_id, "pedido_id": pedido_id, "producto_id": producto_id},
        )
        await _safe_answer_callback(query, "❌ Error interno al eliminar")


async def ejecutar_quitar_unidad(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    producto_id: int,
    producto_nombre: str,
    usuario_id: int,
):
    """Ejecuta la quita de una unidad del producto (sin eliminarlo del carrito)."""
    try:
        resultado = decrease_product_quantity(usuario_id, producto_id, 1)

        if resultado.success and resultado.product:
            restantes = resultado.current_quantity or 0
            await _safe_answer_callback(
                query,
                f"➖ {producto_nombre}: queda {restantes} unidad(es)",
            )
            pedido_actual = get_current_cart(usuario_id)
            if not pedido_actual:
                await _safe_edit_callback_message(
                    query,
                    "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
                    parse_mode='Markdown',
                )
            else:
                await actualizar_vista_pedido(query, context, usuario_id)
        else:
            await _safe_answer_callback(
                query,
                resultado.error_message or "❌ Error al quitar una unidad",
            )

    except BadRequest as exc:
        logger.exception(
            "BadRequest quitando una unidad del producto",
            extra={"usuario_id": usuario_id, "producto_id": producto_id},
        )
        await _safe_answer_callback(query, f"❌ Error al quitar unidad: {exc}")
    except Exception as exc:
        logger.exception(
            "Error quitando una unidad del producto",
            extra={
                "usuario_id": usuario_id,
                "producto_id": producto_id,
                "exception_type": type(exc).__name__,
            },
        )
        await _safe_answer_callback(query, "❌ Error interno al quitar unidad")


async def ejecutar_finalizar_pedido(update, context):
    """Ejecuta la finalización del pedido."""
    query = update.callback_query
    if not query or not isinstance(query.data, str):
        return
    user_data = _get_user_data(context)
    await query.answer()

    telegram_id = query.from_user.id

    if 'confirm_finalize_' in query.data:
        invoice_id = _parse_invoice_id(query.data.replace('confirm_finalize_', '', 1))

        try:
            resultado = finalize_checkout(
                telegram_id=telegram_id,
                invoice_id=invoice_id,
            )

            if resultado.success:
                logger.info(
                    "Pedido finalizado",
                    extra={
                        "telegram_user_id": telegram_id,
                        "invoice_id": invoice_id,
                        "monto": str(resultado.amount),
                        "preference_id": resultado.payment_preference_id,
                    },
                )
                user_data['ultimo_pago'] = {
                    'preference_id': resultado.payment_preference_id,
                    'monto': str(resultado.amount),
                    'concepto': resultado.title,
                }

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Pagar con MercadoPago", url=resultado.payment_url)]
                ])

                await query.edit_message_text(
                    "✅ *¡Pedido confirmado!*\n\n"
                    "Tu pedido ha sido registrado correctamente.\n"
                    "Por favor, procede al pago para completar tu compra.\n\n"
                    "*Te contactaremos para la entrega apenas confirmemos el pago.*\n\n"
                    "¡Gracias por tu compra! 🎉",
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                )
            else:
                logger.warning(
                    "No se pudo finalizar pedido",
                    extra={
                        "telegram_user_id": telegram_id,
                        "invoice_id": invoice_id,
                        "error": resultado.error_message,
                    },
                )
                await query.edit_message_text(
                    "❌ *No se pudo generar el pago*\n\n"
                    f"{resultado.error_message or 'Intenta nuevamente mas tarde.'}",
                    parse_mode='Markdown',
                )

        except Exception as e:
            logger.exception("Error al finalizar pedido", extra={"telegram_id": telegram_id, "invoice_id": invoice_id})
            await query.edit_message_text(
                "❌ *Error al procesar el pedido*\n\n"
                "Hubo un problema al finalizar tu pedido.\n"
                "Por favor, intenta nuevamente.",
                parse_mode='Markdown',
            )

    elif query.data == 'cancel_finalize':
        await query.edit_message_text(
            "❌ *Acción cancelada*\n\n"
            "No se ha finalizado el pedido.\n"
            "Puedes continuar modificándolo.",
            parse_mode='Markdown',
        )


async def actualizar_vista_pedido(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, usuario_id: int):
    """Actualiza la vista del carrito después de cambios."""
    user_data = _get_user_data(context)

    pedido_actual = get_current_cart(usuario_id)

    if not pedido_actual:
        await _safe_edit_callback_message(
            query,
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return

    pedido_id = pedido_actual.invoice_id
    total = pedido_actual.total
    items = pedido_actual.items

    items_detalle = []
    for item in items:
        items_detalle.append({
            'id': item.product_id,
            'nombre': item.name,
            'cantidad': item.quantity,
            'precio': item.unit_price,
            'subtotal': item.subtotal,
            'descripcion': getattr(item, 'description', ''),
        })

    letras_carrito = [chr(65 + i) for i in range(len(items_detalle))]
    user_data['carrito_letras'] = {letra: item['id'] for letra, item in zip(letras_carrito, items_detalle)}
    user_data['carrito_items'] = items_detalle

    mensaje = "🛒 *Carrito Actualizado*\n\n"

    for letra, item in zip(letras_carrito, items_detalle):
        mensaje += f"**{letra}) {_escape_markdown(item['nombre'])}**\n"
        mensaje += f"   📦 Cantidad: `{item['cantidad']}` × ${item['precio']:.2f} = **${item['subtotal']:.2f}**\n\n"

    mensaje += f"**Total: ${total:.2f}**\n\n"
    mensaje += "Usa *Modificar* para cambiar cantidades o eliminar items.\n"

    keyboard = []

    keyboard.append([
        InlineKeyboardButton("✅ Confirmar", callback_data=f'confirmar_{pedido_id}'),
        InlineKeyboardButton("✏️ Modificar", callback_data='modificar_carrito'),
    ])

    keyboard.append([
        InlineKeyboardButton("✅ Finalizar pedido", callback_data=f'finalizar_{pedido_id}')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    logger.debug("Mensaje a enviar en actualizar_vista_pedido: %r", mensaje)
    await _safe_edit_callback_message(
        query,
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


async def entrar_modo_modificacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entra al modo modificación del carrito."""
    message = _get_accessible_message(update)
    user_data = _get_user_data(context)

    if not message or not update.effective_user:
        return EstadoConversacion.MODIFICANDO_CARRITO.value

    cliente_id = update.effective_user.id
    cart = get_current_cart(cliente_id)

    if not cart or cart.is_empty:
        await message.reply_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return ConversationHandler.END

    user_data['carrito_original'] = {
        'items': [
            {
                'id': item.product_id,
                'nombre': item.name,
                'cantidad': item.quantity,
                'precio': item.unit_price,
                'subtotal': item.subtotal,
                'descripcion': item.description,
            }
            for item in cart.items
        ]
    }

    await _mostrar_vista_modificacion(message, context, cliente_id)

    return EstadoConversacion.MODIFICANDO_CARRITO.value


async def _mostrar_vista_modificacion(message: Message, context: ContextTypes.DEFAULT_TYPE, usuario_id: int):
    """Muestra el carrito en modo modificación con instrucciones."""
    user_data = _get_user_data(context)
    cart = get_current_cart(usuario_id)

    if not cart or cart.is_empty:
        await message.reply_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return

    items_detalle = [
        {
            'id': item.product_id,
            'nombre': item.name,
            'cantidad': item.quantity,
            'precio': item.unit_price,
            'subtotal': item.subtotal,
            'descripcion': item.description,
        }
        for item in cart.items
    ]

    letras_carrito = [chr(65 + i) for i in range(len(items_detalle))]
    user_data['carrito_letras'] = {letra: item['id'] for letra, item in zip(letras_carrito, items_detalle)}
    user_data['carrito_items'] = items_detalle

    mensaje = "✏️ *Modo Modificación*\n\n"
    mensaje += "Usa los siguientes comandos:\n"
    mensaje += "• *A+* → Agregar 1 unidad del item A\n"
    mensaje += "• *A-* → Quitar 1 unidad del item A\n"
    mensaje += "• A\* → Eliminar item A\n\n"

    total = Decimal('0.00')
    for letra, item in zip(letras_carrito, items_detalle):
        mensaje += f"**{letra}) {_escape_markdown(item['nombre'])}**\n"
        if item['descripcion']:
            mensaje += f"   _{_escape_markdown(item['descripcion'])}_\n"
        mensaje += f"   📦 Cantidad: `{item['cantidad']}` "
        mensaje += f"× ${item['precio']:.2f} = **${item['subtotal']:.2f}**\n\n"
        total += item['subtotal']

    mensaje += f"**Total: ${total:.2f}**\n"
        
    keyboard = [
        [
            InlineKeyboardButton("✅ Aceptar", callback_data='aceptar_modificacion'),
            InlineKeyboardButton("❌ Cancelar", callback_data='cancelar_modificacion'),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    logger.debug("Mensaje", extra={"texto": mensaje})
    logger.debug("Mensaje a enviar en modo modificacion: %r", mensaje)
    await message.reply_text(mensaje, parse_mode='Markdown', reply_markup=reply_markup)


def _log_modificacion_result(
    update: Update,
    operacion: str,
    producto_id: int,
    result: Any,
) -> None:
    """Loguea el resultado de una modificación del carrito en bot.log."""
    success = bool(getattr(result, "success", False))
    product = getattr(result, "product", None)
    error_message = getattr(result, "error_message", None)
    log_bot_event(
        logger,
        update,
        "Producto modificado en carrito",
        level=logging.INFO if success else logging.WARNING,
        extra={
            "operacion": operacion,
            "producto_id": producto_id,
            "producto_nombre": getattr(product, "name", None),
            "cantidad_anterior": getattr(result, "previous_quantity", None),
            "cantidad_actual": getattr(result, "current_quantity", None),
            "success": success,
            "error": error_message if not success else None,
        },
    )


async def procesar_modificacion_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa los comandos de modificación del carrito (A+, A-, A*)."""
    message = _get_accessible_message(update)
    user_data = _get_user_data(context)

    if not message or not update.effective_user:
        return EstadoConversacion.MODIFICANDO_CARRITO.value

    if not update.message or not update.message.text:
        return EstadoConversacion.MODIFICANDO_CARRITO.value

    texto = update.message.text.strip().upper()

    if texto in ('ACEPTAR', 'CANCELAR'):
        return await _procesar_boton_modificacion(update, context, texto)

    carrito_letras = user_data.get('carrito_letras', {})
    letras_validas = set(carrito_letras.keys())

    import re
    match = re.match(r'^([A-Z])([\+\-\*])$', texto)

    if not match:
        log_bot_event(
            logger,
            update,
            "Comando de modificacion de carrito no valido",
            level=logging.WARNING,
            extra={"texto_ingresado": texto},
        )
        await message.reply_text(
            "❌ Comando no válido. Usa *A+*, *A-* o *A** para modificar.\n"
            "O escribe *Aceptar* para confirmar o *Cancelar* para descartar.",
            parse_mode='Markdown',
        )
        return EstadoConversacion.MODIFICANDO_CARRITO.value

    letra = match.group(1)
    operacion = match.group(2)

    if letra not in letras_validas:
        log_bot_event(
            logger,
            update,
            "Letra de carrito no valida",
            level=logging.WARNING,
            extra={"letra": letra, "letras_validas": sorted(letras_validas)},
        )
        opciones = ", ".join(sorted(letras_validas))
        await message.reply_text(
            f"❌ Letra *{letra}* no válida. Opciones: {opciones}",
            parse_mode='Markdown',
        )
        return EstadoConversacion.MODIFICANDO_CARRITO.value

    producto_id = carrito_letras[letra]
    usuario_id = update.effective_user.id

    log_bot_event(
        logger,
        update,
        "Modificacion de carrito solicitada",
        extra={
            "operacion": operacion,
            "letra": letra,
            "producto_id": producto_id,
        },
    )

    if operacion == '+':
        result = increase_product_quantity(usuario_id, producto_id, 1)
        _log_modificacion_result(update, "+", producto_id, result)
        if result.success:
            await message.reply_text(f"➕ Agregado 1 unidad de *{result.product.name}*", parse_mode='Markdown')
        else:
            await message.reply_text(result.error_message or "❌ Error al agregar", parse_mode='Markdown')

    elif operacion == '-':
        result = decrease_product_quantity(usuario_id, producto_id, 1)
        _log_modificacion_result(update, "-", producto_id, result)
        if result.success:
            if result.current_quantity == 0:
                await message.reply_text(f"🗑️ *{result.product.name}* eliminado del carrito", parse_mode='Markdown')
            else:
                await message.reply_text(f"➖ Quitada 1 unidad de *{result.product.name}* ({result.current_quantity} restantes)", parse_mode='Markdown')
        else:
            await message.reply_text(result.error_message or "❌ Error al quitar", parse_mode='Markdown')

    elif operacion == '*':
        result = remove_product_from_cart(
            get_current_cart_id(usuario_id) or 0,
            producto_id
        )
        _log_modificacion_result(update, "*", producto_id, result)
        if result.success:
            await message.reply_text(f"🗑️ *{result.product.name}* eliminado del carrito", parse_mode='Markdown')
        else:
            await message.reply_text(result.error_message or "❌ Error al eliminar", parse_mode='Markdown')

    cart = get_current_cart(usuario_id)
    if not cart or cart.is_empty:
        await message.reply_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return ConversationHandler.END

    await _mostrar_vista_modificacion(message, context, usuario_id)

    return EstadoConversacion.MODIFICANDO_CARRITO.value


async def _procesar_boton_modificacion(update: Update, context: ContextTypes.DEFAULT_TYPE, accion: str):
    """Procesa los botones Aceptar/Cancelar del modo modificación."""
    message = _get_accessible_message(update)
    user_data = _get_user_data(context)

    if accion == 'CANCELAR':
        carrito_original = user_data.pop('carrito_original', None)
        user_data.pop('carrito_letras', None)
        user_data.pop('carrito_items', None)

        if carrito_original:
            usuario_id = update.effective_user.id
            pedido_id = get_current_cart_id(usuario_id)

            if pedido_id and carrito_original.get('items'):
                for item in carrito_original['items']:
                    for _ in range(item['cantidad']):
                        add_product_to_cart(usuario_id, item['id'], 1)

        await message.reply_text("❌ Cambios descartados.", parse_mode='Markdown')
        return ConversationHandler.END

    user_data.pop('carrito_original', None)
    user_data.pop('carrito_letras', None)
    user_data.pop('carrito_items', None)

    await message.reply_text("✅ Cambios aplicados.", parse_mode='Markdown')
    return ConversationHandler.END


async def manejar_boton_modificacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones Aceptar/Cancelar en el modo modificación."""
    query = update.callback_query
    if not query or not isinstance(query.data, str):
        return

    await query.answer()

    if query.data == 'aceptar_modificacion':
        return await _procesar_boton_modificacion(update, context, 'ACEPTAR')
    elif query.data == 'cancelar_modificacion':
        return await _procesar_boton_modificacion(update, context, 'CANCELAR')


async def manejar_confirmacion_finalizar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la confirmación de finalización del pedido."""
    query: CallbackQuery | None = update.callback_query
    if not query or not isinstance(query.data, str):
        return
    await query.answer()

    data = query.data

    if data.startswith('confirm_finalize_'):
        await ejecutar_finalizar_pedido(update, context)


async def manejar_confirmacion_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la confirmación de eliminación."""
    query = update.callback_query
    if not query or not isinstance(query.data, str):
        return
    await query.answer()

    data = query.data

    if data.startswith('confirm_del_one_'):
        partes = data.replace('confirm_del_one_', '', 1).split('_', 1)
        if len(partes) >= 2:
            producto_id = int(partes[0])
            usuario_id = query.from_user.id
            producto_info = get_product_by_id(producto_id)

            if producto_info:
                await ejecutar_quitar_unidad(
                    query,
                    context,
                    producto_id,
                    producto_info.name,
                    usuario_id,
                )

    elif data.startswith('confirm_del_'):
        partes = data.replace('confirm_del_', '', 1).split('_', 1)
        if len(partes) >= 2:
            producto_id = int(partes[0])
            pedido_id = _parse_invoice_id(partes[1])
            usuario_id = query.from_user.id
            producto_info = get_product_by_id(producto_id)

            if producto_info:
                await ejecutar_eliminacion(
                    query,
                    context,
                    producto_id,
                    producto_info.name,
                    pedido_id,
                    usuario_id,
                )

    elif data == 'cancel_del':
        await query.answer("❌ Eliminación cancelada")
        await ver_pedido(update, context)


async def ver_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el pedido actual del usuario."""
    message = _get_accessible_message(update)
    user_data = _get_user_data(context)

    if not message or not update.effective_user:
        return

    cliente_id = update.effective_user.id
    cart = get_current_cart(cliente_id)

    if not cart or cart.is_empty:
        await message.reply_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return

    items_detalle = []
    total = Decimal('0.00')

    for item in cart.items:
        items_detalle.append(
            {
                'id': item.product_id,
                'nombre': item.name,
                'cantidad': item.quantity,
                'precio': item.unit_price,
                'subtotal': item.subtotal,
                'descripcion': item.description,
            }
        )
        total += item.subtotal

    letras_carrito = [chr(65 + i) for i in range(len(items_detalle))]
    user_data['carrito_letras'] = {letra: item['id'] for letra, item in zip(letras_carrito, items_detalle)}
    user_data['carrito_items'] = items_detalle

    mensaje = "🛒 *Tu Pedido Actual*\n\n"

    for letra, item in zip(letras_carrito, items_detalle):
        mensaje += f"**{letra}) {_escape_markdown(item['nombre'])}**\n"
        if item['descripcion']:
            mensaje += f"   _{_escape_markdown(item['descripcion'])}_\n"
        mensaje += f"   📦 Cantidad: `{item['cantidad']}` "
        mensaje += f"× ${item['precio']:.2f} "
        mensaje += f"= **${item['subtotal']:.2f}**\n\n"

    impuestos = Decimal(0.00)
    total_final = total + impuestos
    mensaje += f"• **TOTAL: ${total_final:.2f}**\n\n"
    mensaje += "Usa *Modificar* para cambiar cantidades o eliminar items.\n"

    keyboard = []

    keyboard.append([
        InlineKeyboardButton("✅ Confirmar", callback_data=f'confirmar_{cart.invoice_id}'),
        InlineKeyboardButton("✏️ Modificar", callback_data='modificar_carrito'),
    ])

    keyboard.append([
        InlineKeyboardButton("✅ Finalizar pedido", callback_data=f'finalizar_{cart.invoice_id}')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    logger.debug("Mensaje a enviar en ver_pedido: %r", mensaje)
    await message.reply_text(
        mensaje,
        parse_mode='Markdown',
        reply_markup=reply_markup,
    )


async def finalizar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finaliza el pedido actual."""
    query = update.callback_query
    if not query or not isinstance(query.data, str):
        return
    await query.answer()

    pedido_id = _parse_invoice_id(query.data.replace('finalizar_', '', 1))
    await mostrar_confirmacion_finalizar_carrito(query, pedido_id)


async def mensajes_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del teclado principal."""
    if not update.message or not update.message.text:
        return
    texto = update.message.text
    log_bot_event(logger, update, "Mensaje de texto recibido", extra={"texto": texto})

    if texto.lower() in ['ver productos', 'productos', 'menú', 'menu', '🛍️ ver productos']:
        await obtener_categorias(update, context)

    elif texto.lower() in ['buscar', '🔎 buscar']:
        await buscar_productos(update, context)

    elif texto.lower() in ['mi pedido', 'pedido', 'carrito', '🛒 mi pedido']:
        await ver_pedido(update, context)

    elif texto.lower() in ['mis pedidos', 'historial', 'historial de pedidos', '📋 mis pedidos']:
        await update.message.reply_text(
            "📊 *Historial de Pedidos*\n\n"
            "Pronto podrás ver todos tus pedidos anteriores.",
            parse_mode='Markdown',
        )

    elif texto.lower() in ['contacto', 'soporte', 'ayuda', 'ℹ️ ayuda']:
        await update.message.reply_text(
            "*Ayuda del Bot de Pedidos*\n\n"
            "• *🛍️ Ver Productos*: Explora nuestro menú\n"
            "• *🔎 Buscar*: Encontra un producto por nombre o descripción\n"
            "• *🛒 Mi Pedido*: Revisa tu pedido actual\n"
            "• *📋 Mis Pedidos*: Historial de compras\n\n"
            "Para agregar productos, selecciona una categoría y luego el producto. Puedes modificar tu pedido antes de finalizarlo.\n\n",
            parse_mode='Markdown',
        )
    else:
        await update.message.reply_text(
            "❌ Opción no reconocida. Por favor, elige una opción del menú principal."
        )
