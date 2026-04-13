from abc import ABC, abstractmethod
import os
from typing import Any

from flask.cli import load_dotenv


# ─────────────────────────────────────────────
# Adaptadores de row
# ─────────────────────────────────────────────

class RowAdapter(ABC):
    """Interfaz común para distintos tipos de row de BD."""

    @abstractmethod
    def fields(self) -> list[str]: ...

    @abstractmethod
    def values(self) -> list[str]: ...


class SQLiteRowAdapter(RowAdapter):
    """Adapta sqlite3.Row (soporta _fields y keys())."""

    def __init__(self, row):
        self._row = row

    def fields(self) -> list[str]:
        return list(self._row.keys())

    def values(self) -> list[str]:
        return [str(self._row[k]) for k in self._row.keys()]


class PsycopgRowAdapter(RowAdapter):
    """
    Adapta rows de psycopg2.
    - RealDictRow  → usa .keys()
    - tuple + description → requiere headers externos
    """

    def __init__(self, row, headers: list[str] | None = None):
        self._row = row
        self._headers = headers

    def fields(self) -> list[str]:
        if self._headers:
            return self._headers
        if hasattr(self._row, "keys"):          # RealDictRow
            return list(self._row.keys())
        raise ValueError(
            "Row es una tupla simple: pasá `headers` desde cursor.description"
        )

    def values(self) -> list[str]:
        if hasattr(self._row, "keys"):          # RealDictRow / dict
            return [str(self._row[k]) for k in self._row.keys()]
        return [str(v) for v in self._row]      # tuple


class NamedTupleRowAdapter(RowAdapter):
    """Adapta namedtuples genéricos."""

    def __init__(self, row):
        self._row = row

    def fields(self) -> list[str]:
        return list(self._row._fields)

    def values(self) -> list[str]:
        return [str(v) for v in self._row]


# ─────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────

class RowAdapterFactory:
    @staticmethod
    def create(row, headers: list[str] | None = None) -> RowAdapter:
        # namedtuple (incluye sqlite3.Row en versiones antiguas)
        if hasattr(row, "_fields"):
            return NamedTupleRowAdapter(row)

        # sqlite3.Row moderno (tiene keys() pero no _fields)
        if hasattr(row, "keys") and hasattr(row, "description"):
            return SQLiteRowAdapter(row)

        # dict-like (psycopg2 RealDictRow, asyncpg Record, etc.)
        if hasattr(row, "keys"):
            return PsycopgRowAdapter(row, headers)

        # tuple plana (psycopg2 cursor estándar)
        if isinstance(row, tuple):
            return PsycopgRowAdapter(row, headers)

        raise TypeError(f"Tipo de row no soportado: {type(row)}")


# ─────────────────────────────────────────────
# Clase principal
# ─────────────────────────────────────────────

class TelegramTable:
    def __init__(self, rows: list[Any], headers: list[str] | None = None, use_pre: bool = True):
        """
        rows:    lista de rows de sqlite3, psycopg2 o namedtuples
        headers: requerido solo para tuplas planas de psycopg2
        use_pre: envolver salida en <pre> (por defecto True)
        """
        self.use_pre = use_pre

        if not rows:
            self.text = "<pre>Sin resultados</pre>" if use_pre else "Sin resultados"
            return

        adapted = [RowAdapterFactory.create(r, headers) for r in rows]
        self.headers  = adapted[0].fields()
        self.rows     = [a.values() for a in adapted]
        self.col_widths = self._calc_widths()
        self.text     = self._build()

    # ── helpers internos ──────────────────────

    def _calc_widths(self) -> list[int]:
        return [
            max(len(h), max(len(row[i]) for row in self.rows))
            for i, h in enumerate(self.headers)
        ]

    def _fmt_row(self, cells: list[str], center: bool = False) -> str:
        if center:
            parts = [f" {str(c).center(w + 1)}" for c, w in zip(cells, self.col_widths)]
        else:
            parts = [f" {str(c).ljust(w + 1)}" for c, w in zip(cells, self.col_widths)]
        return "│" + "│".join(parts) + "│"

    def _separator(self, left: str, mid: str, right: str) -> str:
        return left + mid.join("─" * (w + 2) for w in self.col_widths) + right

    def _build(self) -> str:
        lines = [
            self._separator("┌", "┬", "┐"),
            self._fmt_row(self.headers, center=True),
            self._separator("├", "┼", "┤"),
            *[self._fmt_row(row) for row in self.rows],
            self._separator("└", "┴", "┘"),
        ]
        body = "\n".join(lines)
        return f"<pre>{body}</pre>" if self.use_pre else body

    def __str__(self) -> str:
        return self.text
    

"""Ejemplo de uso:"""
if __name__ == "__main__":
    """ import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (nombre TEXT, edad INT, ciudad TEXT)")
    conn.executemany("INSERT INTO t VALUES (?,?,?)", [
        ("Juan", 25, "Madrid"), ("María", 30, "Lima")
    ])

    rows = conn.execute("SELECT * FROM t").fetchall()
    print(TelegramTable(rows)) """

    #Utilizando RealDictCursor de psycopg2
    import psycopg2
    import psycopg2.extras

    load_dotenv()
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))  # Heroku
    cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nombre, precio FROM products")

    print(TelegramTable(cur.fetchall()))

    #Utilizando tuplas planas de psycopg2
    """ cur = conn.cursor()
    cur.execute("SELECT nombre, edad, ciudad FROM usuarios")

    # headers obligatorio porque las tuplas no tienen nombres
    headers = [desc[0] for desc in cur.description]
    print(TelegramTable(cur.fetchall(), headers=headers)) """