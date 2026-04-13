"""Service wrapper around MercadoPago integration."""

from decimal import Decimal

from shared.dtos import PaymentLinkResult
from utils.mpago import MercadoPagoSimple


def create_payment_link(
    *,
    title: str,
    amount: Decimal,
    telegram_id: int,
    invoice_id: int,
    email: str | None,
    mp_client: MercadoPagoSimple | None = None,
) -> PaymentLinkResult:
    """Create a MercadoPago payment link and normalize its response."""
    client = mp_client or MercadoPagoSimple()
    result = client.crear_pago(
        titulo=title,
        monto=str(amount),
        telegram_id=telegram_id,
        invoice_id=invoice_id,
        email_cliente=email,
    )

    if result.get("success"):
        return PaymentLinkResult(
            success=True,
            preference_id=result.get("preference_id"),
            init_point=result.get("init_point"),
            external_reference=result.get("external_reference"),
        )

    error_message = result.get("error") or "No se pudo generar el pago."
    return PaymentLinkResult(success=False, error_message=str(error_message))