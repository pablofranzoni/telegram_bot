CREATE TABLE IF NOT EXISTS inventory_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    tipo_movimiento VARCHAR(20) NOT NULL CHECK (tipo_movimiento IN ('compra', 'venta', 'devolucion_compra', 'devolucion_venta', 'ajuste', 'reserva', 'cancelacion_reserva')),
    cantidad INTEGER NOT NULL, -- Positivo para compras, negativo para ventas
    stock_previo INTEGER NOT NULL, -- Para auditoría
    stock_posterior INTEGER NOT NULL, -- Para auditoría
    costo_unitario DECIMAL(10,2), -- Para calcular ganancias
    precio_venta_unitario DECIMAL(10,2), -- Para calcular ganancias
    referencia VARCHAR(100), -- Número de factura, orden de compra, etc.
    usuario_id INTEGER REFERENCES customers(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_movements_product_date ON inventory_movements (product_id, created_at);

CREATE OR REPLACE FUNCTION update_inventory_from_movement()
RETURNS TRIGGER AS $$
BEGIN
    -- Actualizar el stock_actual, updated_at y ultima_compra en caso de compra
    UPDATE product_inventory
    SET stock_actual = stock_actual + NEW.cantidad,
        updated_at = CURRENT_TIMESTAMP,
        ultima_compra = CASE
            WHEN NEW.tipo_movimiento = 'compra' THEN CURRENT_DATE
            ELSE ultima_compra
        END
    WHERE product_id = NEW.product_id;

    -- Verificar que no quede negativo (seguridad extra)
    IF (SELECT stock_actual FROM product_inventory WHERE product_id = NEW.product_id) < 0 THEN
        RAISE EXCEPTION 'Stock negativo para producto %', NEW.product_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_inventory
AFTER INSERT ON inventory_movements
FOR EACH ROW
EXECUTE FUNCTION update_inventory_from_movement();