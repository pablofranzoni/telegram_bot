"""REST API blueprint for customer consultation (read-only).

Customers are created through the Telegram bot flow or via the admin
endpoints; this blueprint only exposes paginated reads.
"""

import math

from flask import Blueprint, jsonify, request

from shared.decorators import api_token_required
from shared.services import customer_service

customers_bp = Blueprint("customers", __name__)


def _customer_to_dict(dto) -> dict:
    return {
        "id": dto.id,
        "name": dto.name,
        "telegram_id": dto.telegram_id,
        "email": dto.email,
    }


# --------------------------------------------------------------------------- #
#  GET /api/customers
# --------------------------------------------------------------------------- #
@customers_bp.route("/customers", methods=["GET"])
@api_token_required
def list_customers():
    """Returns a paginated list of customers.

    Query params:
        page     (int, default 1)
        per_page (int, default 10)

    Requires a valid JWT token in the Authorization header.
    """
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = max(int(request.args.get("per_page", 10)), 1)
    except (ValueError, TypeError):
        return jsonify({"error": "Los parámetros page y per_page deben ser enteros positivos"}), 400

    customers, total = customer_service.list_customers(page=page, per_page=per_page)
    total_pages = math.ceil(total / per_page) if total else 0

    return jsonify({
        "customers": [_customer_to_dict(c) for c in customers],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }), 200
