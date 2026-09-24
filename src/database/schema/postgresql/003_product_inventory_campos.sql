-- Agrega columnas de stock disponible, ultima compra y ubicacion al product_inventory
ALTER TABLE product_inventory
    ADD COLUMN IF NOT EXISTS stock_disponible INTEGER GENERATED ALWAYS AS (stock_actual - stock_reservado) STORED;

ALTER TABLE product_inventory
    ADD COLUMN IF NOT EXISTS ultima_compra DATE;

ALTER TABLE product_inventory
    ADD COLUMN IF NOT EXISTS ubicacion_almacen VARCHAR(50);
