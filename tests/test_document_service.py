"""Unit tests for document_service."""

import re
import zlib
from decimal import Decimal

from shared.services import document_service


_PDF_STREAM_PATTERN = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_PDF_TEXT_PATTERN = re.compile(r"\((.*?)\)\s*Tj")
_PDF_TEXT_ARRAY_PATTERN = re.compile(r"\[(.*?)\]\s*TJ", re.DOTALL)
_PDF_TEXT_FRAGMENT_PATTERN = re.compile(r"\((.*?)\)")
_PDF_OCTAL_ESCAPE_PATTERN = re.compile(r"\\([0-7]{1,3})")


def _decode_pdf_text_fragment(fragment: str) -> str:
    def replace_octal(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 8))

    fragment = _PDF_OCTAL_ESCAPE_PATTERN.sub(replace_octal, fragment)
    fragment = fragment.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return fragment


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    fragments: list[str] = []

    for match in _PDF_STREAM_PATTERN.finditer(pdf_bytes):
        stream = match.group(1)
        payloads = [stream]

        try:
            payloads.append(zlib.decompress(stream))
        except zlib.error:
            pass

        for payload in payloads:
            decoded = payload.decode("latin-1", errors="ignore")
            fragments.extend(_PDF_TEXT_PATTERN.findall(decoded))
            for text_array in _PDF_TEXT_ARRAY_PATTERN.findall(decoded):
                fragments.extend(_PDF_TEXT_FRAGMENT_PATTERN.findall(text_array))

    normalized_text = " ".join(_decode_pdf_text_fragment(fragment) for fragment in fragments)
    return " ".join(normalized_text.split())


def test_build_receipt_pdf_generates_pdf_bytes(monkeypatch):
    monkeypatch.setattr(
        document_service,
        "obtener_comprobante_pedido",
        lambda invoice_id: (
            {
                "id": invoice_id,
                "fecha": "2026-04-08 12:00:00",
                "estado": "completado",
                "payment_estado": "aprobado",
                "total": Decimal("25.50"),
                "name": "Ana Perez",
                "email": "ana@example.com",
                "mp_payment_id": "mp-123",
            },
            [
                {
                    "nombre": "Coca-Cola",
                    "cantidad": 1,
                    "precio_unitario": Decimal("2.50"),
                    "subtotal": Decimal("2.50"),
                },
                {
                    "nombre": "Hamburguesa Doble",
                    "cantidad": 1,
                    "precio_unitario": Decimal("23.00"),
                    "subtotal": Decimal("23.00"),
                },
            ],
        ),
    )

    pdf_bytes, file_name, error_message = document_service.build_receipt_pdf(42)

    assert error_message is None
    assert file_name == "comprobante_pedido_0000000042.pdf"
    assert pdf_bytes is not None
    assert pdf_bytes.startswith(b"%PDF")


def test_build_receipt_pdf_contains_expected_content(monkeypatch):
    monkeypatch.setattr(
        document_service,
        "obtener_comprobante_pedido",
        lambda invoice_id: (
            {
                "id": invoice_id,
                "fecha": "2026-04-08 12:00:00",
                "estado": "completado",
                "payment_estado": "aprobado",
                "total": Decimal("25.50"),
                "name": "Ana Perez",
                "email": "ana@example.com",
                "company": "Acme SRL",
                "address": "Calle Falsa 123",
                "mp_payment_id": "mp-123",
            },
            [
                {
                    "nombre": "Coca-Cola",
                    "cantidad": 1,
                    "precio_unitario": Decimal("2.50"),
                    "subtotal": Decimal("2.50"),
                },
                {
                    "nombre": "Hamburguesa Doble",
                    "cantidad": 1,
                    "precio_unitario": Decimal("23.00"),
                    "subtotal": Decimal("23.00"),
                },
            ],
        ),
    )

    pdf_bytes, _, error_message = document_service.build_receipt_pdf(42)

    assert error_message is None
    assert pdf_bytes is not None

    pdf_text = _extract_pdf_text(pdf_bytes)

    assert "Comprobante Pedido #0000000042" in pdf_text
    assert "Fecha: 2026-04-08 12:00:00" in pdf_text
    assert "Cliente: Ana Perez" in pdf_text
    assert "Email: ana@example.com" in pdf_text
    assert "Empresa: Acme SRL" in pdf_text
    assert "Direccion: Calle Falsa 123" in pdf_text
    assert "Estado pago: Aprobado" in pdf_text
    assert "Pago ID: mp-123" in pdf_text
    assert "Coca-Cola" in pdf_text
    assert "Hamburguesa Doble" in pdf_text
    assert "Total: $ 25.50" in pdf_text


def test_build_receipt_pdf_attachment_wraps_pdf(monkeypatch):
    monkeypatch.setattr(
        document_service,
        "build_receipt_pdf",
        lambda invoice_id: (b"%PDF-demo", "comprobante.pdf", None),
    )

    attachment, file_name, error_message = document_service.build_receipt_pdf_attachment(42)

    assert error_message is None
    assert file_name == "comprobante.pdf"
    assert attachment is not None
    assert attachment.filename == "comprobante.pdf"
    assert attachment.mime_type == "application/pdf"
    assert attachment.content_bytes == b"%PDF-demo"