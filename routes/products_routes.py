"""REST API blueprint for product management (CRUD)."""

import math

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from shared.decorators import admin_required, api_token_required
from shared.services import inventory_service, product_service
from shared.services.inventory_service import InventoryError
from shared.services.user_service import UserService

products_bp = Blueprint("products", __name__)

_REQUIRED_CREATE_FIELDS = {"nombre", "descripcion", "precio", "category_id"}


def _product_to_dict(dto) -> dict:
    return {
        "id": dto.id,
        "nombre": dto.name,
        "descripcion": dto.description,
        "precio": float(dto.price),
        "stock_available": dto.stock_available,
        "ultima_compra": dto.last_purchase_date,
        "ubicacion_almacen": dto.warehouse_location,
    }


# --------------------------------------------------------------------------- #
#  GET /api/products
# --------------------------------------------------------------------------- #
@products_bp.route("/products", methods=["GET"])
@api_token_required
def list_products():
    """Returns a paginated list of all products.
    
    Requires a valid JWT token in the Authorization header.
    """
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
@api_token_required
def get_product(product_id: int):
    """Returns a single product by id.
    
    Requires a valid JWT token in the Authorization header.
    """
    product = product_service.get_product(product_id)
    if product is None:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(_product_to_dict(product)), 200


# --------------------------------------------------------------------------- #
#  POST /api/products
# --------------------------------------------------------------------------- #
@products_bp.route("/products", methods=["POST"])
@api_token_required
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
@api_token_required
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
@api_token_required
def deactivate_product(product_id: int):
    """Soft-deletes a product (sets disponible=False)."""
    success = product_service.deactivate_product(product_id)
    if not success:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify({"message": "Producto desactivado correctamente"}), 200


# --------------------------------------------------------------------------- #
#  GET /api/products/<id>/stock
# --------------------------------------------------------------------------- #
@products_bp.route("/products/<int:product_id>/stock", methods=["GET"])
@api_token_required
def get_product_stock(product_id: int):
    """Returns the inventory state of a single product.

    Requires a valid JWT token in the Authorization header.
    """
    inventory = inventory_service.get_inventory(product_id)
    if inventory is None:
        return jsonify({"error": "Producto no encontrado"}), 404

    return jsonify({
        "product_id": inventory.product_id,
        "stock_actual": inventory.stock_actual,
        "stock_reservado": inventory.stock_reservado,
        "stock_disponible": inventory.stock_disponible,
        "stock_minimo": inventory.stock_minimo,
        "ultima_compra": inventory.ultima_compra,
        "ubicacion_almacen": inventory.ubicacion_almacen,
    }), 200


# --------------------------------------------------------------------------- #
#  POST /api/products/<id>/stock
# --------------------------------------------------------------------------- #
@products_bp.route("/products/<int:product_id>/stock", methods=["POST"])
@api_token_required
@admin_required
def add_product_stock(product_id: int):
    """Adds stock to an existing product (admin only).

    Expected JSON body:
        cantidad        (int, required)    - Positive amount to add.
        tipo            (str, optional)    - "compra" or "ajuste" (default "compra").
        costo_unitario  (number, optional) - Unit cost for purchase movements.
        referencia      (str, optional)    - Reference number (purchase order, etc.).
    """
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Se requiere un cuerpo JSON"}), 400

    if "cantidad" not in data:
        return jsonify({"error": "cantidad es requerida"}), 400

    try:
        cantidad = int(data["cantidad"])
        if cantidad <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "cantidad debe ser un entero positivo"}), 400

    movement_type = str(data.get("tipo", "compra")).strip().lower()
    if movement_type not in {"compra", "ajuste"}:
        return jsonify({"error": "tipo debe ser 'compra' o 'ajuste'"}), 400

    costo_unitario = data.get("costo_unitario")
    if costo_unitario is not None:
        try:
            costo_unitario = float(costo_unitario)
            if costo_unitario < 0:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify({"error": "costo_unitario debe ser un número no negativo"}), 400

    referencia = data.get("referencia")
    if referencia is not None:
        referencia = str(referencia).strip() or None

    username = get_jwt_identity()
    user = UserService.get_user_by_username(username)
    usuario_id = user["id"] if user else None

    try:
        result = inventory_service.add_stock(
            product_id=product_id,
            cantidad=cantidad,
            movement_type=movement_type,
            costo_unitario=costo_unitario,
            referencia=referencia,
            usuario_id=usuario_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except InventoryError as e:
        return jsonify({"error": str(e)}), 500

    if result is None:
        return jsonify({"error": "Producto no encontrado"}), 404

    return jsonify({
        "movement_id": result["movement_id"],
        "product_id": result["product_id"],
        "stock_actual": result["stock_actual"],
        "stock_disponible": result["stock_disponible"],
    }), 201
