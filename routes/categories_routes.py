"""REST API blueprint for category management (CRUD)."""

from flask import Blueprint, jsonify, request

from shared.services import category_service

categories_bp = Blueprint("categories", __name__)

_REQUIRED_CREATE_FIELDS = {"codigo", "nombre", "descripcion"}

  
def _category_to_dict(dto) -> dict:
    return {
        "id": dto.id,
        "codigo": dto.codigo,
        "nombre": dto.name,
        "descripcion": dto.description,
        "parent_id": dto.parent_id,
    }


# --------------------------------------------------------------------------- #
#  GET /api/categories
# --------------------------------------------------------------------------- #
@categories_bp.route("/categories", methods=["GET"])
def list_categories():
    """Returns the list of all categories."""
    categories = category_service.list_categories()
    return jsonify({"categories": [_category_to_dict(c) for c in categories]}), 200


# --------------------------------------------------------------------------- #
#  GET /api/categories/<id>
# --------------------------------------------------------------------------- #
@categories_bp.route("/categories/<int:category_id>", methods=["GET"])
def get_category(category_id: int):
    """Returns a single category by id."""
    category = category_service.get_category(category_id)
    if category is None:
        return jsonify({"error": "Categoría no encontrada"}), 404
    return jsonify(_category_to_dict(category)), 200


# --------------------------------------------------------------------------- #
#  POST /api/categories
# --------------------------------------------------------------------------- #
@categories_bp.route("/categories", methods=["POST"])
def create_category():
    """Creates a new category.

    Expected JSON body:
        codigo      (str, required) – short unique code e.g. 'PIZ'
        nombre      (str, required) – unique display name
        descripcion (str, required)
        parent_id   (int, optional)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere un cuerpo JSON"}), 400

    missing = _REQUIRED_CREATE_FIELDS - data.keys()
    if missing:
        return jsonify({"error": f"Campos requeridos faltantes: {', '.join(sorted(missing))}"}), 400

    codigo = str(data["codigo"]).strip().upper()
    nombre = str(data["nombre"]).strip()
    descripcion = str(data["descripcion"]).strip()

    if not codigo:
        return jsonify({"error": "codigo no puede estar vacío"}), 400
    if len(codigo) > 10:
        return jsonify({"error": "codigo no puede superar los 10 caracteres"}), 400
    if not nombre:
        return jsonify({"error": "nombre no puede estar vacío"}), 400

    parent_id = None
    if "parent_id" in data and data["parent_id"] is not None:
        try:
            parent_id = int(data["parent_id"])
        except (ValueError, TypeError):
            return jsonify({"error": "parent_id debe ser un entero"}), 400

    category = category_service.create_category(
        codigo=codigo,
        nombre=nombre,
        descripcion=descripcion,
        parent_id=parent_id,
    )
    if category is None:
        return jsonify({"error": "Error al crear la categoría"}), 500

    return jsonify(_category_to_dict(category)), 201


# --------------------------------------------------------------------------- #
#  PUT /api/categories/<id>
# --------------------------------------------------------------------------- #
@categories_bp.route("/categories/<int:category_id>", methods=["PUT"])
def update_category(category_id: int):
    """Partially updates a category.

    Accepted JSON fields (all optional):
        codigo, nombre, descripcion, parent_id
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Se requiere un cuerpo JSON"}), 400

    allowed_fields = {"codigo", "nombre", "descripcion", "parent_id"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        return jsonify({"error": "No se proporcionaron campos válidos para actualizar"}), 400

    if "codigo" in update_data:
        codigo = str(update_data["codigo"]).strip().upper()
        if not codigo:
            return jsonify({"error": "codigo no puede estar vacío"}), 400
        if len(codigo) > 10:
            return jsonify({"error": "codigo no puede superar los 10 caracteres"}), 400
        update_data["codigo"] = codigo

    if "nombre" in update_data:
        nombre = str(update_data["nombre"]).strip()
        if not nombre:
            return jsonify({"error": "nombre no puede estar vacío"}), 400
        update_data["nombre"] = nombre

    if "parent_id" in update_data and update_data["parent_id"] is not None:
        try:
            update_data["parent_id"] = int(update_data["parent_id"])
        except (ValueError, TypeError):
            return jsonify({"error": "parent_id debe ser un entero"}), 400

    updated = category_service.update_category(category_id, update_data)
    if updated is None:
        return jsonify({"error": "Categoría no encontrada"}), 404

    return jsonify(_category_to_dict(updated)), 200


# --------------------------------------------------------------------------- #
#  DELETE /api/categories/<id>
# --------------------------------------------------------------------------- #
@categories_bp.route("/categories/<int:category_id>", methods=["DELETE"])
def delete_category(category_id: int):
    """Deletes a category by id."""
    success = category_service.delete_category(category_id)
    if not success:
        return jsonify({"error": "Categoría no encontrada"}), 404
    return jsonify({"message": "Categoría eliminada correctamente"}), 200
