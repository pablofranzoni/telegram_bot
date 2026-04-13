"""PDF document generation for commercial receipts."""

import asyncio
from io import BytesIO

from fpdf import FPDF
from telegram import Bot

from shared.dtos import EmailAttachmentDTO
from shared.number_utils import to_decimal
from shared.record_utils import get_record_value
from utils.config import Config
from utils.database import obtener_comprobante_pedido


def build_receipt_pdf(invoice_id: int) -> tuple[bytes | None, str | None, str | None]:
    """Build a simple commercial receipt PDF for a paid order."""
    invoice_info, items = obtener_comprobante_pedido(invoice_id)
    if not invoice_info or not items:
        return None, None, "No se encontraron datos suficientes para generar el comprobante."

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, Config.BUSINESS_NAME, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    if Config.BUSINESS_EMAIL:
        pdf.cell(0, 6, f"Email: {Config.BUSINESS_EMAIL}", new_x="LMARGIN", new_y="NEXT")

    invoice_label = str(get_record_value(invoice_info, 'id', invoice_id)).zfill(10)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, f"Comprobante Pedido #{invoice_label}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, f"Fecha: {get_record_value(invoice_info, 'fecha', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Cliente: {get_record_value(invoice_info, 'name', '')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Email: {get_record_value(invoice_info, 'email', '')}", new_x="LMARGIN", new_y="NEXT")
    if get_record_value(invoice_info, 'company'):
        pdf.cell(0, 6, f"Empresa: {get_record_value(invoice_info, 'company')}", new_x="LMARGIN", new_y="NEXT")
    if get_record_value(invoice_info, 'address'):
        pdf.multi_cell(0, 6, f"Direccion: {get_record_value(invoice_info, 'address')}")
    payment_status = str(get_record_value(invoice_info, 'payment_estado', get_record_value(invoice_info, 'estado', '')))
    payment_status = payment_status[:1].upper() + payment_status[1:] if payment_status else ''
    pdf.cell(0, 6, f"Estado pago: {payment_status}", new_x="LMARGIN", new_y="NEXT")
    if get_record_value(invoice_info, 'mp_payment_id'):
        pdf.cell(0, 6, f"Pago ID: {get_record_value(invoice_info, 'mp_payment_id')}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(80, 8, "Producto", border=1)
    pdf.cell(20, 8, "Cant.", border=1)
    pdf.cell(40, 8, "Unitario", border=1)
    pdf.cell(40, 8, "Subtotal", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", size=10)
    for item in items:
        pdf.cell(80, 8, str(get_record_value(item, 'nombre', ''))[:40], border=1)
        pdf.cell(20, 8, str(get_record_value(item, 'cantidad', 0)), border=1)
        pdf.cell(40, 8, f"$ {to_decimal(get_record_value(item, 'precio_unitario', 0), default=0):.2f}", border=1)
        pdf.cell(40, 8, f"$ {to_decimal(get_record_value(item, 'subtotal', 0), default=0):.2f}", border=1, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    total = to_decimal(get_record_value(invoice_info, 'total', 0), default=0)
    pdf.cell(0, 8, f"Total: $ {total:.2f}", new_x="LMARGIN", new_y="NEXT")

    output = pdf.output()
    pdf_bytes = bytes(output) if isinstance(output, (bytes, bytearray)) else str(output).encode('latin-1')
    file_name = f"comprobante_pedido_{invoice_label}.pdf"
    return pdf_bytes, file_name, None


def build_receipt_pdf_attachment(invoice_id: int) -> tuple[EmailAttachmentDTO | None, str | None, str | None]:
    """Return the receipt PDF wrapped as an email attachment."""
    pdf_bytes, file_name, error_message = build_receipt_pdf(invoice_id)
    if not pdf_bytes or not file_name:
        return None, None, error_message

    return (
        EmailAttachmentDTO(
            filename=file_name,
            content_bytes=pdf_bytes,
            mime_type='application/pdf',
        ),
        file_name,
        None,
    )


async def _send_pdf_via_telegram_async(chat_id: str | int, attachment: EmailAttachmentDTO, caption: str) -> None:
    """Send a PDF attachment to a Telegram chat."""
    if not Config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN no configurado para enviar comprobantes por Telegram.")

    async with Bot(token=Config.BOT_TOKEN) as bot:
        telegram_file = BytesIO(attachment.content_bytes)
        telegram_file.name = attachment.filename
        await bot.send_document(chat_id=int(chat_id), document=telegram_file, caption=caption)


def send_receipt_pdf_via_telegram(chat_id: str | int, attachment: EmailAttachmentDTO, caption: str) -> tuple[bool, str | None]:
    """Send a receipt PDF to Telegram from synchronous application code."""
    try:
        asyncio.run(_send_pdf_via_telegram_async(chat_id, attachment, caption))
        return True, None
    except Exception as exc:
        return False, str(exc)