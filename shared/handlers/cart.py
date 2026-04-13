"""Handlers relacionados con el carrito y el pago."""
from collections.abc import MutableMapping
import logging
import traceback
import json
import html
from decimal import Decimal
from typing import cast

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from shared.handlers.products import obtener_categorias
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
from utils.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

DEVELOPER_CHAT_ID = 7225069015


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

    if data.startswith('rem_'):
        producto_id = int(data.replace('rem_', ''))
        await disminuir_cantidad(query, context, producto_id)

    elif data.startswith('add_'):
        producto_id = int(data.replace('add_', ''))
        await aumentar_cantidad(query, context, producto_id)

    elif data.startswith('del_'):
        producto_id = int(data.replace('del_', ''))
        await eliminar_producto(query, context, producto_id)

    elif data.startswith('info_'):
        producto_id = int(data.replace('info_', ''))
        await mostrar_detalle_producto(query, context, producto_id)

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
    producto_id = int(query.data.replace('add_', ''))
    await aumentar_cantidad(query, context, producto_id)

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

    return ConversationHandler.END


async def disminuir_cantidad(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, producto_id: int, cantidad: int = 1):
    """Disminuye la cantidad de un producto en el carrito."""
    usuario_id = query.from_user.id
    result = decrease_product_quantity(usuario_id, producto_id, cantidad)

    if result.success and result.product:
        await query.answer(
            f"➖ {result.product.name}: {result.previous_quantity} → {result.current_quantity}"
        )
        return

    await query.answer(result.error_message or "❌ Error al actualizar cantidad")


async def mostrar_detalle_producto(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, producto_id: int):
    """Muestra la ficha del producto con las acciones principales."""
    producto = get_product_by_id(producto_id)

    if not producto:
        await query.answer("❌ Producto no encontrado")
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

    await query.answer()
    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


async def aumentar_cantidad(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE, producto_id: int, cantidad: int = 1):
    """Aumenta la cantidad de un producto en el carrito."""
    usuario_id = query.from_user.id
    result = increase_product_quantity(usuario_id, producto_id, cantidad)

    if result.success and result.product:
        await query.edit_message_text(
            f"➕ {result.product.name}: {result.previous_quantity} → {result.current_quantity}"
        )
        return

    await query.edit_message_text(result.error_message or "❌ Error al actualizar cantidad")


async def agregar_producto_al_pedido(query: CallbackQuery, producto_id: int, cantidad: int = 1):
    """Agrega un nuevo producto al pedido."""
    # Siempre responde el callback para que Telegram deje de mostrar el "relojito"
    await query.answer()

    usuario_id = query.from_user.id
    result = add_product_to_cart(usuario_id, producto_id, cantidad)

    if result.success and result.product:
        await query.edit_message_text(text=f"➕ {result.product.name}: {result.current_quantity}")
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
    """Muestra diálogo de confirmación antes de eliminar."""
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Sí, eliminar",
                callback_data=f'confirm_del_{producto_id}_{pedido_id}',
            ),
            InlineKeyboardButton(
                "❌ No, cancelar",
                callback_data='cancel_del',
            ),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"⚠️ *Confirmar eliminación*\n\n"
        f"¿Estás seguro de eliminar **{producto_nombre}** del carrito?\n\n"
        f"Esta acción no se puede deshacer.",
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


async def mostrar_confirmacion_finalizar_carrito(query: CallbackQuery, pedido_id: int):
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
    pedido_id: int,
    usuario_id: int,
):
    """Ejecuta la eliminación del producto."""
    try:
        eliminado = remove_product_from_cart(pedido_id, producto_id)

        if eliminado.success:
            await query.answer(f"✅ {producto_nombre} eliminado")
            pedido_actual = get_current_cart(usuario_id)

            if not pedido_actual:
                await query.edit_message_text(
                    "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
                    parse_mode='Markdown',
                )
            else:
                #await actualizar_vista_pedido(query, context, usuario_id)
                await query.answer("❌ Se actualizó el pedido.")
        else:
            await query.answer(eliminado.error_message or "❌ Error al eliminar el producto")

    except Exception as e:
        logger.exception(
            "Error eliminando producto del carrito",
            extra={"usuario_id": usuario_id, "pedido_id": pedido_id, "producto_id": producto_id},
        )
        await query.answer("❌ Error interno al eliminar")


async def ejecutar_finalizar_pedido(update, context):
    """Ejecuta la finalización del pedido."""
    query = update.callback_query
    if not query or not isinstance(query.data, str):
        return
    user_data = _get_user_data(context)
    await query.answer()

    telegram_id = query.from_user.id

    if 'confirm_finalize_' in query.data:
        invoice_id = int(query.data.replace('confirm_finalize_', ''))

        try:
            resultado = finalize_checkout(
                telegram_id=telegram_id,
                invoice_id=invoice_id,
            )

            if resultado.success:
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
                    "Te contactaremos para la entrega apenas confirmemos el pago.\n\n"
                    "¡Gracias por tu compra! 🎉",
                    reply_markup=keyboard,
                    parse_mode='Markdown',
                )
            else:
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

    pedido_actual = get_current_cart(usuario_id)

    if not pedido_actual:
        await query.edit_message_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
            parse_mode='Markdown',
        )
        return

    pedido_id = pedido_actual.invoice_id
    total = pedido_actual.total
    num_items = pedido_actual.item_count
    items = pedido_actual.items

    mensaje = "🛒 *Carrito Actualizado*\n\n"

    #items es asi: [{'id': 28, 'total': Decimal('4.5'), 'items': 1}, ...]
    for item in items:
        mensaje += f"• **{item.name}**\n"
        mensaje += f"  Cantidad: `{item.quantity}` × ${item.unit_price:.2f} = **${item.subtotal:.2f}**\n\n"

    mensaje += f"**Total: ${total:.2f}**\n"
    mensaje += f"**Items: {num_items} productos**\n\n"
    mensaje += (
        " ¿Qué deseas hacer? Modifica tu pedido o finalízalo cuando estés listo.\n\n"
        "Puedes eliminar productos, agregar más o proceder al pago.\n\n"
        "/quitar para eliminar productos, /ver_productos para agregar más, o \n\n"
        "/finalizar para completar tu compra"
    )

    keyboard = []

    #items es asi: [{'id': 28, 'total': Decimal('4.5'), 'items': 1}, ...]
    for item in items:
        nombre_corto = item.name[:10] + "..." if len(item.name) > 10 else item.name
        keyboard.append([
            InlineKeyboardButton(f"❌  Quitar {nombre_corto}", callback_data=f'del_{item.product_id}')
        ])

    keyboard.append([
        InlineKeyboardButton("✅ Finalizar pedido", callback_data=f'finalizar_{pedido_id}')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown',
    )


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

    if data.startswith('confirm_del_'):
        partes = data.replace('confirm_del_', '').split('_')
        if len(partes) >= 2:
            producto_id = int(partes[0])
            pedido_id = int(partes[1])
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

    mensaje = "🛒 *Tu Pedido Actual*\n\n"

    for idx, item in enumerate(items_detalle, 1):
        mensaje += f"**{idx}. {item['nombre']}**\n"
        if item['descripcion']:
            mensaje += f"   _{item['descripcion']}_\n"
        mensaje += f"   📦 Cantidad: `{item['cantidad']}` "
        mensaje += f"× ${item['precio']:.2f} "
        mensaje += f"= **${item['subtotal']:.2f}**\n\n"

    impuestos = Decimal(0.00)  # Aquí podrías calcular impuestos si es necesario
    total_final = total + impuestos
    mensaje += f"• **TOTAL: ${total_final:.2f}**\n\n"

    keyboard = []

    for idx, item in enumerate(items_detalle, 1):
        producto_id = item['id']
        nombre_corto = item['nombre'][:15] + "..." if len(item['nombre']) > 15 else item['nombre']

        keyboard.append([
            InlineKeyboardButton(f"❌ Eliminar {nombre_corto}", callback_data=f'del_{producto_id}')
        ])

    keyboard.append([
        InlineKeyboardButton("🗑️ Vaciar todo", callback_data='vaciar_todo'),
    ])

    keyboard.append([
        InlineKeyboardButton("✅ Finalizar pedido", callback_data=f'finalizar_{cart.invoice_id}')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

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

    pedido_id = int(query.data.replace('finalizar_', ''))
    await mostrar_confirmacion_finalizar_carrito(query, pedido_id)


async def mensajes_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del teclado principal."""
    if not update.message or not update.message.text:
        return
    texto = update.message.text
    logger.debug("Mensaje de texto recibido en menu principal", extra={"texto": texto})

    if texto.lower() in ['ver productos', 'productos', 'menú', 'menu', '🛍️ ver productos']:
        await obtener_categorias(update, context)

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
            "• *🛒 Mi Pedido*: Revisa tu pedido actual\n"
            "• *📋 Mis Pedidos*: Historial de compras\n\n"
            "Para agregar productos, selecciona una categoría y luego el producto. Puedes modificar tu pedido antes de finalizarlo.\n\n",
            parse_mode='Markdown',
        )
    else:
        await update.message.reply_text(
            "❌ Opción no reconocida. Por favor, elige una opción del menú principal."
        )
