"""REST API blueprint for invoice consultation (read-only).

Invoices are created exclusively through the Telegram bot flow and cannot be
created or modified via this API.
"""

import math

from flask import Blueprint, jsonify, request

from shared.services import invoice_service

invoices_bp = Blueprint("invoices", __name__)

_VALID_ESTADOS = {"pendiente", "pagado", "cancelado"}


def _invoice_to_dict(dto) -> dict:
    return {
        "id": dto.id,
        "fecha": dto.fecha,
        "estado": dto.estado,
        "total": float(dto.total),
        "customer": {
            "id": dto.customer_db_id,
            "nombre": dto.customer_name,
            "telegram_id": dto.telegram_id,
        },
    }


def _item_to_dict(dto) -> dict:
    return {
        "id": dto.id,
        "product_id": dto.product_id,
        "product_name": dto.product_name,
        "product_description": dto.product_description,
        "cantidad": dto.cantidad,
        "precio_unitario": float(dto.precio_unitario),
        "subtotal": float(dto.subtotal),
    }


# --------------------------------------------------------------------------- #
#  GET /api/invoices
# --------------------------------------------------------------------------- #
@invoices_bp.route("/invoices", methods=["GET"])
def list_invoices():
    """Returns a paginated list of invoices.

    Query params:
        page        (int, default 1)
        per_page    (int, default 10)
        estado      (str, optional) – filter by status: pendiente | pagado | cancelado
        customer_id (int, optional) – filter by internal customer DB id
    """
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = max(int(request.args.get("per_page", 10)), 1)
    except (ValueError, TypeError):
        return jsonify({"error": "Los parámetros page y per_page deben ser enteros positivos"}), 400

    estado = request.args.get("estado")
    if estado is not None:
        estado = estado.strip().lower()
        if estado not in _VALID_ESTADOS:
            return jsonify({"error": f"estado inválido. Valores permitidos: {', '.join(sorted(_VALID_ESTADOS))}"}), 400

    customer_id: int | None = None
    raw_customer_id = request.args.get("customer_id")
    if raw_customer_id is not None:
        try:
            customer_id = int(raw_customer_id)
        except (ValueError, TypeError):
            return jsonify({"error": "customer_id debe ser un entero"}), 400

    invoices, total = invoice_service.list_invoices(
        page=page,
        per_page=per_page,
        estado=estado,
        customer_id=customer_id,
    )
    total_pages = math.ceil(total / per_page) if total else 0

    return jsonify({
        "invoices": [_invoice_to_dict(inv) for inv in invoices],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }), 200


# --------------------------------------------------------------------------- #
#  GET /api/invoices/<id>
# --------------------------------------------------------------------------- #
@invoices_bp.route("/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice(invoice_id: int):
    """Returns a single invoice by id, including its line items."""
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        return jsonify({"error": "Invoice no encontrada"}), 404

    items = invoice_service.get_invoice_items(invoice_id)
    body = _invoice_to_dict(invoice)
    body["items"] = [_item_to_dict(it) for it in items]
    return jsonify(body), 200


# --------------------------------------------------------------------------- #
#  GET /api/invoices/<id>/items
# --------------------------------------------------------------------------- #
@invoices_bp.route("/invoices/<int:invoice_id>/items", methods=["GET"])
def get_invoice_items(invoice_id: int):
    """Returns only the line items of an invoice."""
    invoice = invoice_service.get_invoice(invoice_id)
    if invoice is None:
        return jsonify({"error": "Invoice no encontrada"}), 404

    items = invoice_service.get_invoice_items(invoice_id)
    return jsonify({
        "invoice_id": invoice_id,
        "items": [_item_to_dict(it) for it in items],
    }), 200


# --------------------------------------------------------------------------- #
#  GET /api/invoices/by-customer/<telegram_id>
# --------------------------------------------------------------------------- #
@invoices_bp.route("/invoices/by-customer/<telegram_id>", methods=["GET"])
def list_invoices_by_customer(telegram_id: str):
    """Returns paginated invoices belonging to a customer identified by their Telegram id.

    Query params:
        page     (int, default 1)
        per_page (int, default 10)
        estado   (str, optional) – pendiente | pagado | cancelado
    """
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = max(int(request.args.get("per_page", 10)), 1)
    except (ValueError, TypeError):
        return jsonify({"error": "Los parámetros page y per_page deben ser enteros positivos"}), 400

    estado = request.args.get("estado")
    if estado is not None:
        estado = estado.strip().lower()
        if estado not in _VALID_ESTADOS:
            return jsonify({"error": f"estado inválido. Valores permitidos: {', '.join(sorted(_VALID_ESTADOS))}"}), 400

    result = invoice_service.list_invoices_by_customer(
        telegram_id=telegram_id,
        page=page,
        per_page=per_page,
        estado=estado,
    )
    if result is None:
        return jsonify({"error": "Cliente no encontrado"}), 404

    invoices, total = result
    total_pages = math.ceil(total / per_page) if total else 0
    return jsonify({
        "telegram_id": telegram_id,
        "invoices": [_invoice_to_dict(inv) for inv in invoices],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }), 200
