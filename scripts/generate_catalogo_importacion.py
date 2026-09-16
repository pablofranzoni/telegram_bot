"""Generate a sample catalog Excel file for category/product import.

Reads existing categories from the configured SQLite database and builds an
.xlsx file with two sheets:

- ``categories``: current categories (for reference/update import).
- ``products``: sample products referencing those categories by name.

Usage:

    python scripts/generate_catalogo_importacion.py
    python scripts/generate_catalogo_importacion.py --db-path ./data.db
    python scripts/generate_catalogo_importacion.py --output catalogo.xlsx
"""
from __future__ import annotations

import argparse
import sqlite3
import unicodedata
from pathlib import Path

from openpyxl import Workbook


DEFAULT_DB_PATH = "pedidos_bot.db"
DEFAULT_OUTPUT = "catalogo_importacion.xlsx"

SAMPLE_PRODUCTS: list[tuple[str, str, float, int]] = [
    # (product_name, planned_category_name_without_accents, price, initial_stock)
    ("Pastilla de freno delantera", "Frenos", 45000.0, 20),
    ("Disco de freno trasero", "Frenos", 62000.0, 15),
    ("Amortiguador delantero", "Suspension", 98000.0, 12),
    ("Bieleta de suspensión", "Suspension", 35000.0, 25),
    ("Filtro de aceite", "Motor", 12000.0, 50),
    ("Bujía de encendido", "Motor", 8500.0, 80),
    ("Aceite sintético 5W30", "Aceites y lubricantes", 28000.0, 40),
    ("Filtro de aire", "Filtracion", 18000.0, 30),
    ("Filtro de habitáculo", "Filtracion", 15000.0, 35),
    ("Faro delantero", "Electricidad", 75000.0, 8),
    ("Alternador", "Electricidad", 145000.0, 5),
    ("Parachoques delantero", "Carroceria", 210000.0, 3),
    ("Neumático 205/55 R16", "Neumaticos", 95000.0, 16),
    ("Kit de herramientas", "Accesorios", 42000.0, 10),
    ("Embrague completo", "Transmision", 185000.0, 4),
]


def _normalize(text: str) -> str:
    """Return lower-case, accent-free text for fuzzy comparison."""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _resolve_category_names(categories: list[dict], planned_names: set[str]) -> dict[str, str]:
    """Map planned category names to exact DB names using accent-insensitive matching."""
    exact_map: dict[str, str] = {}
    for planned in planned_names:
        normalized_planned = _normalize(planned)
        exact = None
        for category in categories:
            if _normalize(category["nombre"]) == normalized_planned:
                exact = category["nombre"]
                break
        exact_map[planned] = exact or planned
    return exact_map


def _load_categories(db_path: Path) -> list[dict]:
    """Load categories ordered by name from the SQLite database."""
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, codigo, nombre, descripcion, parent_id "
            "FROM categories ORDER BY nombre"
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _build_workbook(categories: list[dict]) -> Workbook:
    """Create the workbook with categories and sample products sheets."""
    planned_names = {planned[1] for planned in SAMPLE_PRODUCTS}
    exact_map = _resolve_category_names(categories, planned_names)

    workbook = Workbook()

    # Categories sheet
    ws_cat = workbook.active
    ws_cat.title = "categories"
    ws_cat.append(["codigo", "nombre", "descripcion", "parent_id"])
    for category in categories:
        ws_cat.append([
            category["codigo"],
            category["nombre"],
            category["descripcion"] or "",
            category["parent_id"] or "",
        ])

    # Products sheet
    ws_prod = workbook.create_sheet(title="products")
    ws_prod.append([
        "nombre",
        "descripcion",
        "precio",
        "category_name",
        "disponible",
        "stock_inicial",
    ])
    for nombre, planned_category, precio, stock in SAMPLE_PRODUCTS:
        ws_prod.append([
            nombre,
            f"Producto de repuesto - {nombre}",
            precio,
            exact_map[planned_category],
            1,
            stock,
        ])

    return workbook


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a sample import catalog Excel file."
    )
    parser.add_argument(
        "--db-path",
        default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output Excel path (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    # Resolve paths relative to the project root (one level up from scripts/)
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / args.db_path
    output_path = project_root / args.output

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    categories = _load_categories(db_path)
    workbook = _build_workbook(categories)
    workbook.save(output_path)

    print(f"Saved {output_path}")
    print(f"Categories written: {len(categories)}")
    print(f"Products written: {len(SAMPLE_PRODUCTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
