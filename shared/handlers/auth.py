"""Handlers relacionados con el registro / autenticación y el menú principal."""

from collections.abc import MutableMapping

from telegram import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from utils.constants import EstadoConversacion
from shared.services.auth_service import (
    generate_verification_code,
    get_customer_with_email,
    is_valid_email,
    register_verified_customer,
)
from shared.services.email_service import send_verification_email


def _require_message(update: Update) -> Message | None:
    """Return the message when present."""
    return update.message


def _get_user_data(context: ContextTypes.DEFAULT_TYPE) -> MutableMapping[str, object]:
    """Return a mutable user_data mapping even when typing marks it optional."""
    user_data = context.user_data
    if user_data is None:
        raise RuntimeError("context.user_data no esta disponible")
    return user_data


def es_email_valido(email: str) -> bool:
    """Mantiene compatibilidad pública para validar email."""
    return is_valid_email(email)


def generar_codigo_verificacion() -> str:
    """Genera un código de 6 dígitos para verificar el email."""
    return generate_verification_code()


async def cmd_inicio_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /inicio_cliente: verifica si el usuario ya tiene email."""
    usuario = update.effective_user
    message = _require_message(update)
    if not usuario or not message:
        return ConversationHandler.END
    telegram_id = usuario.id

    # Buscar si ya tiene email
    datos_cliente = get_customer_with_email(telegram_id)

    if datos_cliente and datos_cliente.get('email'):
        # Ya tiene email, mostrar menú principal
        await mostrar_menu_principal(update, context, usuario.first_name)
        return ConversationHandler.END
    else:
        # No tiene email, solicitarlo
        await message.reply_text(
            f"¡Hola {usuario.first_name}! 👋\n\n"
            "Para poder procesar tus pedidos, necesito tu email.\n"
            "Por favor, ingrésalo:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return EstadoConversacion.ESPERANDO_EMAIL.value


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - verifica si tiene email y muestra el menú principal."""
    usuario = update.effective_user
    message = _require_message(update)
    if not usuario or not message:
        return ConversationHandler.END
    telegram_id = usuario.id

    # Buscar si ya tiene email
    datos_cliente = get_customer_with_email(telegram_id)

    if datos_cliente and datos_cliente.get('email'):
        # Ya tiene email, mostrar menú principal
        await mostrar_menu_principal(update, context, usuario.first_name)
    else:
        # No tiene email, solicitarlo
        await message.reply_text(
            f"¡Hola {usuario.first_name}! 👋\n\n"
            "Para poder procesar tus pedidos, necesito tu email.\n"
            "Por favor, ingrésalo:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return EstadoConversacion.ESPERANDO_EMAIL.value


async def ver_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra mensaje de ayuda."""
    mensaje = (
        "📋 *Ayuda - Comandos disponibles:*\n\n"
        "• /start - Iniciar conversación y verificar email\n"
        "• /ver_productos - Ver categorías y productos disponibles\n"
        "• /carrito - Ver tu pedido actual\n"
        "• /checkout - Finalizar compra\n"
        "• /mis_pedidos - Ver historial de pedidos\n"
        "• /estado - Ver estado del último pago\n"
        "\nSi necesitas asistencia adicional, no dudes en contactarnos."
    )
    return mensaje


async def recibir_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el email y envía código de verificación."""
    message = _require_message(update)
    if not message or not message.text:
        return ConversationHandler.END
    user_data = _get_user_data(context)
    email = message.text.strip()

    if not es_email_valido(email):
        await message.reply_text("❌ Email inválido. Intenta nuevamente:")
        return EstadoConversacion.ESPERANDO_EMAIL.value

    # Generar código de verificación
    codigo = generar_codigo_verificacion()

    send_result = send_verification_email(
        recipient_email=email,
        verification_code=codigo,
        recipient_name=getattr(update, "effective_user", None).first_name if getattr(update, "effective_user", None) else None,
    )

    if not send_result.success:
        await message.reply_text(
            send_result.error_message or "❌ No se pudo enviar el código de verificación. Intenta nuevamente."
        )
        return EstadoConversacion.ESPERANDO_EMAIL.value

    # Guardar email y código temporalmente
    user_data['email_temp'] = email
    user_data['codigo_verificacion'] = codigo

    await message.reply_text(
        f"📧 Hemos enviado un código de verificación a **{email}**\n\n"
        f"Por favor, ingresa el código de 6 dígitos que recibiste:",
        parse_mode='Markdown'
    )

    return EstadoConversacion.ESPERANDO_CODIGO.value


async def verificar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica el código ingresado."""
    message = _require_message(update)
    usuario = update.effective_user
    if not message or not message.text or not usuario:
        return ConversationHandler.END
    user_data = _get_user_data(context)
    codigo_ingresado = message.text.strip()
    codigo_correcto = user_data.get('codigo_verificacion')

    if codigo_ingresado == codigo_correcto:
        # Código correcto, guardar email
        usuario_id = usuario.id
        email = str(user_data.get('email_temp') or '')

        register_verified_customer(
            usuario_id,
            usuario.first_name,
            usuario.last_name,
            usuario.username,
            email=email,
        )

        user_data.clear()

        await message.reply_text(
            "✅ **¡Email verificado correctamente!**",
            parse_mode='Markdown',
            reply_markup=reply_markup_principal(),
        )

        return ConversationHandler.END
    else:
        await message.reply_text(
            "❌ Código incorrecto. Intenta nuevamente:\n"
            "(o escribe /cancelar para abortar)"
        )
        return EstadoConversacion.ESPERANDO_CODIGO.value


async def cancelar_ingreso_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la operación de ingreso de email."""
    message = _require_message(update)
    if not message:
        return ConversationHandler.END
    await message.reply_text(
        "Operación cancelada. Usa /start cuando quieras intentar nuevamente.",
        reply_markup=reply_markup_principal(),
    )
    return ConversationHandler.END


def reply_markup_principal():
    """Teclado principal."""
    keyboard = [
        ['🛍️ Ver Productos', '🛒 Mi Pedido'],
        ['📋 Mis Pedidos', 'ℹ️ Ayuda'],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def mostrar_menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE, nombre: str | None = None):
    """Muestra el menú principal al usuario."""
    message = _require_message(update)
    if not message:
        return
    mensaje = f"¡Bienvenido{ ' ' + nombre if nombre else ''}!\n"
    mensaje += "¿Qué deseas hacer hoy?"

    await message.reply_text(
        mensaje,
        reply_markup=reply_markup_principal(),
    )


async def reiniciar_desde_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback para reiniciar la conversación cuando llega /start durante un flujo."""
    message = _require_message(update)
    if not message:
        return ConversationHandler.END
    await message.reply_text("Reiniciando la conversación...")
    # Terminamos la conversación actual y comenzamos una nueva
    return await start(update, context)
