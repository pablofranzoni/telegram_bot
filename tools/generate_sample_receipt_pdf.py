"""Generate a sample receipt PDF for manual inspection."""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.services import document_service


def _sample_receipt_data(invoice_id: int) -> tuple[dict[str, object], list[dict[str, object]]]:
    return (
        {
            "id": invoice_id,
            "fecha": "2026-04-08 12:00:00",
            "estado": "completado",
            "payment_estado": "aprobado",
            "total": Decimal("31.40"),
            "name": "Ana Perez",
            "email": "ana@example.com",
            "company": "Acme SRL",
            "address": "Calle Falsa 123, CABA",
            "mp_payment_id": "mp-demo-123",
        },
        [
            {
                "nombre": "Coca-Cola",
                "cantidad": 2,
                "precio_unitario": Decimal("2.70"),
                "subtotal": Decimal("5.40"),
            },
            {
                "nombre": "Hamburguesa Doble",
                "cantidad": 1,
                "precio_unitario": Decimal("18.00"),
                "subtotal": Decimal("18.00"),
            },
            {
                "nombre": "Papas Fritas",
                "cantidad": 1,
                "precio_unitario": Decimal("8.00"),
                "subtotal": Decimal("8.00"),
            },
        ],
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--invoice-id", type=int, default=42, help="Invoice id used in the sample PDF.")
    parser.add_argument(
        "--output-dir",
        default=str(Path("uploads") / "receipts"),
        help="Directory where the generated PDF will be written.",
    )
    parser.add_argument("--open", action="store_true", help="Open the generated PDF after writing it.")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    original_loader = document_service.obtener_comprobante_pedido
    document_service.obtener_comprobante_pedido = _sample_receipt_data
    try:
        pdf_bytes, file_name, error_message = document_service.build_receipt_pdf(args.invoice_id)
    finally:
        document_service.obtener_comprobante_pedido = original_loader

    if error_message or not pdf_bytes or not file_name:
        parser.error(error_message or "No se pudo generar el PDF de ejemplo.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / file_name
    output_path.write_bytes(pdf_bytes)

    print(f"PDF generado en: {output_path}")

    if args.open and hasattr(os, "startfile"):
        os.startfile(output_path)  # type: ignore[attr-defined]

    return 0


if __name__ == "__main__":
    raise SystemExit(main())