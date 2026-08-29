-- Corrige la FK de inventory_movements.usuario_id para que apunte a customers(id)
-- en lugar de users(id), alineándose con el schema de PostgreSQL.

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

CREATE TABLE inventory_movements_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    tipo_movimiento TEXT NOT NULL CHECK(tipo_movimiento IN ('compra', 'venta', 'devolucion_compra', 'devolucion_venta', 'ajuste', 'reserva', 'cancelacion_reserva')),
    cantidad INTEGER NOT NULL,
    stock_previo INTEGER NOT NULL,
    stock_posterior INTEGER NOT NULL,
    costo_unitario REAL,
    precio_venta_unitario REAL,
    referencia TEXT,
    usuario_id INTEGER REFERENCES customers(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO inventory_movements_new (
    id, product_id, tipo_movimiento, cantidad, stock_previo, stock_posterior,
    costo_unitario, precio_venta_unitario, referencia, usuario_id, created_at
)
SELECT
    id, product_id, tipo_movimiento, cantidad, stock_previo, stock_posterior,
    costo_unitario, precio_venta_unitario, referencia, usuario_id, created_at
FROM inventory_movements;

DROP TABLE inventory_movements;

ALTER TABLE inventory_movements_new RENAME TO inventory_movements;

UPDATE sqlite_sequence SET name = 'inventory_movements' WHERE name = 'inventory_movements_new';

CREATE INDEX IF NOT EXISTS idx_movements_product_date ON inventory_movements(product_id, created_at);

-- The trigger that updates product_inventory was dropped with the old table,
-- so it must be recreated on the new table.
CREATE TRIGGER IF NOT EXISTS trg_update_inventory
AFTER INSERT ON inventory_movements
BEGIN
    UPDATE product_inventory
    SET stock_actual = stock_actual + NEW.cantidad,
        updated_at = CURRENT_TIMESTAMP,
        ultima_compra = CASE
            WHEN NEW.tipo_movimiento = 'compra' THEN DATE('now')
            ELSE ultima_compra
        END
    WHERE product_id = NEW.product_id;

    SELECT CASE
        WHEN (SELECT stock_actual FROM product_inventory WHERE product_id = NEW.product_id) < 0
        THEN RAISE(ABORT, 'Stock negativo para producto')
    END;
END;

COMMIT;

PRAGMA foreign_keys = ON;
