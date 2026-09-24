-- Agrega columnas de stock disponible, ultima compra y ubicacion al product_inventory
ALTER TABLE product_inventory
    ADD COLUMN stock_disponible INTEGER GENERATED ALWAYS AS (stock_actual - stock_reservado) STORED;

ALTER TABLE product_inventory
    ADD COLUMN ultima_compra DATE;

ALTER TABLE product_inventory
    ADD COLUMN ubicacion_almacen TEXT;
