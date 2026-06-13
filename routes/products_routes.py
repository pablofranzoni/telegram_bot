"""REST API blueprint for product management (CRUD)."""

import math

from flask import Blueprint, jsonify, request

from shared.services import product_service

products_bp = Blueprint("products", __name__)

_REQUIRED_CREATE_FIELDS = {"nombre", "descripcion", "precio", "category_id"}


def _product_to_dict(dto) -> dict:
    return {
        "id": dto.id,
        "nombre": dto.name,
        "descripcion": dto.description,
        "precio": float(dto.price),
        "stock_available": dto.stock_available,
    }


# --------------------------------------------------------------------------- #
#  GET /api/products
# --------------------------------------------------------------------------- #
@products_bp.route("/products", methods=["GET"])
def list_products():
    """Returns a paginated list of all products."""
    try:
        page = max(int(request.args.get("page", 1)), 1)
        per_page = max(int(request.args.get("per_page", 10)), 1)
    except (ValueError, TypeError):
        return jsonify({"error": "Los parámetros page y per_page deben ser enteros positivos"}), 400

    products, total = product_service.list_products(page=page, per_page=per_page)
    total_pages = math.ceil(total / per_page) if total else 0

    return jsonify({
        "products": [_product_to_dict(p) for p in products],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }), 200


# --------------------------------------------------------------------------- #
#  GET /api/products/<id>
# --------------------------------------------------------------------------- #
@products_bp.route("/products/<int:product_id>", methods=["GET"])
def get_product(product_id: int):
    """Returns a single product by id."""
    product = product_service.get_product(product_id)
    if product is None:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(_product_to_dict(product)), 200


# --------------------------------------------------------------------------- #
#  POST /api/products
# --------------------------------------------------------------------------- #
@products_bp.route("/products", methods=["POST"])
def create_product():
    """Creates a new product.

    Expected JSON body:
        nombre      (str, required)
        descripcion (str, required)
        precio      (number, required)
        category_id (int, required)
        stock_inicial (int, optional, default 0)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere un cuerpo JSON"}), 400

    missing = _REQUIRED_CREATE_FIELDS - data.keys()
    if missing:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(sorted(missing))}"}), 400

    try:
        precio = float(data["precio"])
        if precio < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "precio debe ser un número positivo"}), 400

    try:
        category_id = int(data["category_id"])
    except (ValueError, TypeError):
        return jsonify({"error": "category_id debe ser un entero"}), 400

    stock_inicial = 0
    if "stock_inicial" in data:
        try:
            stock_inicial = int(data["stock_inicial"])
            if stock_inicial < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "stock_inicial debe ser un entero no negativo"}), 400

    nombre = str(data["nombre"]).strip()
    descripcion = str(data["descripcion"]).strip()

    if not nombre:
        return jsonify({"error": "nombre no puede estar vacío"}), 400

    product = product_service.create_product(
        nombre=nombre,
        descripcion=descripcion,
        precio=precio,
        category_id=category_id,
        stock_inicial=stock_inicial,
    )
    if product is None:
        return jsonify({"error": "Error al crear el producto"}), 500

    return jsonify(_product_to_dict(product)), 201


# --------------------------------------------------------------------------- #
#  PUT /api/products/<id>
# --------------------------------------------------------------------------- #
@products_bp.route("/products/<int:product_id>", methods=["PUT"])
def update_product(product_id: int):
    """Partially updates a product.

    Accepted JSON fields (all optional):
        nombre, descripcion, precio, disponible, category_id
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere un cuerpo JSON"}), 400

    allowed_fields = {"nombre", "descripcion", "precio", "disponible", "category_id"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        return jsonify({"error": "No se proporcionaron campos válidos para actualizar"}), 400

    if "precio" in update_data:
        try:
            precio = float(update_data["precio"])
            if precio < 0:
                raise ValueError
            update_data["precio"] = precio
        except (ValueError, TypeError):
            return jsonify({"error": "precio debe ser un número positivo"}), 400

    if "category_id" in update_data:
        try:
            update_data["category_id"] = int(update_data["category_id"])
        except (ValueError, TypeError):
            return jsonify({"error": "category_id debe ser un entero"}), 400

    if "disponible" in update_data:
        if not isinstance(update_data["disponible"], bool):
            return jsonify({"error": "disponible debe ser true o false"}), 400

    updated = product_service.update_product(product_id, update_data)
    if updated is None:
        return jsonify({"error": "Producto no encontrado"}), 404

    return jsonify(_product_to_dict(updated)), 200


# --------------------------------------------------------------------------- #
#  DELETE /api/products/<id>
# --------------------------------------------------------------------------- #
@products_bp.route("/products/<int:product_id>", methods=["DELETE"])
def deactivate_product(product_id: int):
    """Soft-deletes a product (sets disponible=False)."""
    success = product_service.deactivate_product(product_id)
    if not success:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"message": "Producto desactivado correctamente"}), 200
