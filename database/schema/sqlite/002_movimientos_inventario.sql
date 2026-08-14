-- Tabla de movimientos de inventario (auditoria y trigger de stock)
CREATE TABLE IF NOT EXISTS inventory_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id),
    tipo_movimiento TEXT NOT NULL CHECK(tipo_movimiento IN ('compra', 'venta', 'devolucion_compra', 'devolucion_venta', 'ajuste', 'reserva', 'cancelacion_reserva')),
    cantidad INTEGER NOT NULL, -- Positivo para compras, negativo para ventas
    stock_previo INTEGER NOT NULL, -- Para auditoria
    stock_posterior INTEGER NOT NULL, -- Para auditoria
    costo_unitario REAL, -- Para calcular ganancias
    precio_venta_unitario REAL, -- Para calcular ganancias
    referencia TEXT, -- Numero de factura, orden de compra, etc.
    usuario_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_movements_product_date ON inventory_movements(product_id, created_at);

CREATE TRIGGER IF NOT EXISTS trg_update_inventory
AFTER INSERT ON inventory_movements
BEGIN
    -- Actualizar stock_actual, updated_at y ultima_compra en caso de compra
    UPDATE product_inventory
    SET stock_actual = stock_actual + NEW.cantidad,
        updated_at = CURRENT_TIMESTAMP,
        ultima_compra = CASE
            WHEN NEW.tipo_movimiento = 'compra' THEN DATE('now')
            ELSE ultima_compra
        END
    WHERE product_id = NEW.product_id;

    -- Verificar que no quede negativo
    SELECT CASE
        WHEN (SELECT stock_actual FROM product_inventory WHERE product_id = NEW.product_id) < 0
        THEN RAISE(ABORT, 'Stock negativo para producto')
    END;
END;
