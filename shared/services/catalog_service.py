"""Read-only catalog service used by handlers and future API endpoints."""

from shared.dtos import CategoryDTO, ProductDTO
from shared.number_utils import to_decimal
from shared.record_utils import get_record_value
from utils.database import (
    obtener_categorias_db,
    obtener_producto_por_id,
    obtener_productos_por_categoria,
    obtener_productos_por_categoria_paginados,
    verificar_stock_disponible,
)


def list_categories() -> list[CategoryDTO]:
    """Return all available categories in a normalized form."""
    categories = obtener_categorias_db()
    return [CategoryDTO(name=name, description=description) for name, description in categories]


def list_products_by_category(category_name: str | None) -> list[ProductDTO]:
    """Return the products available in a category."""
    if not category_name:
        return []

    products = obtener_productos_por_categoria(category_name)
    return [
        ProductDTO(
            id=product_id,
            name=name,
            description=description,
            price=to_decimal(price),
        )
        for product_id, name, description, price in products
    ]


def list_products_by_category_page(
    category_name: str | None,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[ProductDTO], bool]:
    """Return one page of products and whether another page exists."""
    if not category_name:
        return [], False

    normalized_page = max(page, 1)
    normalized_page_size = max(page_size, 1)
    offset = (normalized_page - 1) * normalized_page_size
    products = obtener_productos_por_categoria_paginados(
        category_name,
        normalized_page_size + 1,
        offset,
    )
    has_next_page = len(products) > normalized_page_size
    visible_products = products[:normalized_page_size]
    return (
        [
            ProductDTO(
                id=product_id,
                name=name,
                description=description,
                price=to_decimal(price),
            )
            for product_id, name, description, price in visible_products
        ],
        has_next_page,
    )


def get_product_by_id(product_id: int) -> ProductDTO | None:
    """Return one product in normalized form."""
    product = obtener_producto_por_id(product_id)
    if not product:
        return None

    return ProductDTO(
        id=int(get_record_value(product, "id", fallback_index=0)),
        name=str(get_record_value(product, "nombre", fallback_index=1) or ""),
        description=str(get_record_value(product, "descripcion", fallback_index=2) or ""),
        price=to_decimal(get_record_value(product, "precio", fallback_index=3)),
        stock_available=verificar_stock_disponible(product_id),
    )