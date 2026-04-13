"""Handlers relacionados con pagos y estado de pago."""

from telegram import Update
from telegram.ext import ContextTypes

from utils.mpago import MercadoPagoSimple
from utils.database import buscar_ultimo_pago_usuario


async def cmd_estado_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /estado - Verifica el estado del último pago."""
    usuario_id = update.effective_user.id

    pago = buscar_ultimo_pago_usuario(usuario_id)

    if not pago:
        await update.message.reply_text("❌ No tenés pagos registrados.")
        return

    monto, concepto, estado, fecha_creacion, fecha_aprobacion, mp_payment_id = pago

    mp = MercadoPagoSimple()
    estado_mp = ""
    if mp_payment_id:
        resultado = mp.obtener_pago(mp_payment_id)
        if resultado['success']:
            estado_mp = f"\n📊 Estado MP: {resultado['pago']['status']}"

    emoji = {
        'pendiente': '⏳',
        'aprobado': '✅',
        'rechazado': '❌'
    }.get(estado, '❓')

    fecha_aprob = f"\n✅ Aprobado: {fecha_aprobacion}" if fecha_aprobacion else ""

    mensaje = (
        f"{emoji} **Estado de tu pago:**\n\n"
        f"💰 Monto: **${monto}**\n"
        f"📝 Concepto: {concepto}\n"
        f"📅 Solicitado: {fecha_creacion}\n"
        f"📌 Estado: **{estado.upper()}**{fecha_aprob}{estado_mp}"
    )

    await update.message.reply_text(mensaje, parse_mode='Markdown')
