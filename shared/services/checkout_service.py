"""Business logic for finalizing an order checkout."""

from decimal import Decimal

from shared.dtos import CheckoutResultDTO
from shared.number_utils import to_decimal
from shared.record_utils import get_record_value
from shared.services.payment_service import create_payment_link
from utils.database import (
    finalizar_pedido_db,
    guardar_pago,
    obtener_cliente,
    obtener_detalle_pedido,
)


def finalize_checkout(*, telegram_id: int, invoice_id: str) -> CheckoutResultDTO:
    """Finalize an order and generate a payment link for it."""
    customer = obtener_cliente(telegram_id)
    email = get_record_value(customer, "email")

    if not email:
        return CheckoutResultDTO(
            success=False,
            invoice_id=invoice_id,
            error_message="No se encontro un email valido para completar el pago.",
        )

    invoice_info, items = obtener_detalle_pedido(invoice_id)
    if not invoice_info or not items:
        return CheckoutResultDTO(
            success=False,
            invoice_id=invoice_id,
            error_message="El pedido no existe o no tiene productos.",
        )

    amount = to_decimal(get_record_value(invoice_info, "total", Decimal("0.00")))
    title = f"Pedido #{invoice_id}"

    finalizar_pedido_db(invoice_id)

    payment_result = create_payment_link(
        title=title,
        amount=amount,
        telegram_id=telegram_id,
        invoice_id=invoice_id,
        email=email,
    )

    if not payment_result.success:
        return CheckoutResultDTO(
            success=False,
            invoice_id=invoice_id,
            amount=amount,
            title=title,
            error_message=payment_result.error_message,
        )

    guardar_pago(
        telegram_id=telegram_id,
        mp_payment_id=None,
        invoice_id=invoice_id,
        monto=float(amount),
        concepto=title,
    )

    return CheckoutResultDTO(
        success=True,
        invoice_id=invoice_id,
        amount=amount,
        title=title,
        payment_preference_id=payment_result.preference_id,
        payment_url=payment_result.init_point,
    )