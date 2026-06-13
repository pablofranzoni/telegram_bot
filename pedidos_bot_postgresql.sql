BEGIN;

-- Tabla categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) NOT NULL UNIQUE,        -- Códigos como 'PIZ', 'HAM' (máx 3-4 chars)
    nombre VARCHAR(100) NOT NULL UNIQUE,        -- Identificador visible/usado por el bot (pizzas, bebidas)
    descripcion VARCHAR(100) NOT NULL,          -- Descripciones cortas (Pizzas, Hamburguesas)
    parent_id INTEGER REFERENCES categories(id)
);

-- Tabla upload_logs
CREATE TABLE IF NOT EXISTS upload_logs (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,              -- Nombres de archivo
    original_filename VARCHAR(255) NOT NULL,     -- Nombres de archivo originales
    file_size INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('processing', 'completed', 'failed', 'partial')),
    processed_rows INTEGER DEFAULT 0,
    total_rows INTEGER DEFAULT 0,
    error_message TEXT,                           -- TEXT porque puede ser largo
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_date TIMESTAMP,
    user_id INTEGER,
    checksum VARCHAR(64),                         -- MD5, SHA hashes
    metadata TEXT                                  -- JSON u otros datos largos
);

-- Tabla csv_processing_errors
CREATE TABLE IF NOT EXISTS csv_processing_errors (
    id SERIAL PRIMARY KEY,
    upload_id INTEGER NOT NULL REFERENCES upload_logs(id),
    row_number INTEGER NOT NULL,
    raw_data TEXT,                                 -- TEXT porque puede ser CSV largo
    column_name VARCHAR(100),                      -- Nombres de columna
    error_type VARCHAR(50) NOT NULL,               -- Tipos de error
    error_message TEXT NOT NULL,                   -- Mensajes pueden ser largos
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP
);

-- Tabla customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL UNIQUE,      -- IDs de cliente (ej: '7225069015')
    name VARCHAR(200) NOT NULL,                    -- Nombre completo
    email VARCHAR(255),                             -- Email tiene límite estándar
    phone VARCHAR(30),                              -- Teléfono con códigos
    address TEXT,                                   -- Dirección puede ser larga
    city VARCHAR(100),                              -- Ciudad
    state VARCHAR(50),                              -- Estado/Provincia
    country VARCHAR(50),                            -- País
    postal_code VARCHAR(20),                        -- Código postal
    company VARCHAR(200),                            -- Nombre de empresa
    username VARCHAR(100),                           -- Nombre de usuario
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,                                      -- Notas pueden ser largas
    last_purchase_date TIMESTAMP,
    total_purchases NUMERIC DEFAULT 0
);

-- Tabla products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,                   -- Nombre de producto
    descripcion TEXT,                                -- Descripción puede ser larga
    precio NUMERIC NOT NULL,
    disponible BOOLEAN DEFAULT TRUE,
    category_id INTEGER REFERENCES categories(id)
);

-- Tabla product_inventory
CREATE TABLE IF NOT EXISTS product_inventory (
    product_id INTEGER PRIMARY KEY REFERENCES products(id),
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK (stock_actual >= 0),
    stock_reservado INTEGER NOT NULL DEFAULT 0 CHECK (stock_reservado >= 0),
    stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT product_inventory_stock_reservado_lte_actual
        CHECK (stock_reservado <= stock_actual)
);

-- 0. ASEGURAR QUE LA EXTENSIÓN ESTÉ ACTIVA
CREATE EXTENSION IF NOT EXISTS pg_uuidv7;

-- Tabla invoices (Modificada a UUID v7)
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(), -- Generación automática con tu extensión
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'pendiente',
    total NUMERIC DEFAULT 0.0
);

-- Tabla invoice_items
CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE, -- Tipo cambiado a UUID
    product_id INTEGER NOT NULL REFERENCES products(id),
    cantidad INTEGER NOT NULL,
    precio_unitario NUMERIC NOT NULL,
    subtotal NUMERIC GENERATED ALWAYS AS (cantidad * precio_unitario) STORED
);

-- Tabla payments
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    mp_payment_id VARCHAR(50) UNIQUE, -- IDs de MercadoPago
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE, -- Tipo cambiado a UUID
    monto NUMERIC NOT NULL,
    concepto VARCHAR(255), -- Concepto del pago
    estado VARCHAR(20) DEFAULT 'pendiente',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_aprobacion TIMESTAMP
);

-- Tabla sent_documents
CREATE TABLE IF NOT EXISTS sent_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE, -- Tipo cambiado a UUID
    delivery_channel VARCHAR(20) NOT NULL,
    recipient_target VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    payment_id VARCHAR(50),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    error_message TEXT,
    CONSTRAINT sent_documents_unique_delivery
        UNIQUE (document_type, invoice_id, delivery_channel, recipient_target)
);

-- Insertar datos en categories
INSERT INTO categories (id, codigo, nombre, descripcion, parent_id) VALUES 
(1, 'PIZ', 'pizzas', 'Pizzas', NULL),
(2, 'HAM', 'hamburguesas', 'Hamburguesas', NULL),
(3, 'BEB', 'bebidas', 'Bebidas', NULL),
(4, 'ENS', 'ensaladas', 'Ensaladas', NULL),
(5, 'EMP', 'empanadas', 'Empanadas', NULL);

SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories));

-- Insertar datos en customers
INSERT INTO customers (id, customer_id, name, email, phone, address, city, state, country, postal_code, company, username, created_at, updated_at, is_active, notes, last_purchase_date, total_purchases) VALUES 
(1, '7225069015', 'Pablo Franzoni', 'pablo.franzoni@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pablo_franzoni', '2026-02-05 00:04:36', '2026-02-05 00:04:36', TRUE, NULL, NULL, 0.0);

SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers));

-- Insertar datos en products
INSERT INTO products (id, nombre, descripcion, precio, disponible, category_id) VALUES 
(1, 'Pizza Margarita', 'Queso mozzarella y tomate', 12.99, TRUE, 1),
(2, 'Pizza Pepperoni', 'Extra pepperoni', 14.99, TRUE, 1),
(3, 'Hamburguesa Clásica', 'Carne, lechuga, tomate', 9.99, TRUE, 2),
(4, 'Hamburguesa BBQ', 'Salsa barbacoa', 11.99, TRUE, 2),
(5, 'Coca-Cola', '500ml', 2.5, TRUE, 3),
(6, 'Agua Mineral', '1L', 1.5, TRUE, 3),
(7, 'Ensalada César', 'Pollo y aderezo especial', 8.99, TRUE, 4),
(8, 'Ensalada Mixta', 'Ensalada de Lechuga, Tomate y Cebolla', 5.6, TRUE, 4),
(9, 'Cerveza Lata 330 Quilmes', 'Cerveza Lata 330ml Quilmes', 3.5, TRUE, 3),
(10, 'Pizza Muzzarella', 'Queso mozzarella, tomates y aceitunas', 10.99, TRUE, 1),
(11, 'Hamburguesa Doble', 'Doble Carne, lechuga, tomate y huevo', 12.99, TRUE, 2);

SELECT setval('products_id_seq', (SELECT MAX(id) FROM products));

-- Insertar datos en invoices
INSERT INTO invoices (id, customer_id, fecha, estado, total) VALUES 
(9, 1, '2026-02-05 22:02:18', 'completado', 25.98),
(10, 1, '2026-02-06 04:28:44', 'completado', 1.5),
(11, 1, '2026-02-06 15:40:00', 'completado', 1.5),
(12, 1, '2026-02-06 15:45:58', 'completado', 1.5),
(13, 1, '2026-02-06 15:51:19', 'completado', 1.5),
(17, 1, '2026-02-13 00:19:20', 'completado', 1.5),
(18, 1, '2026-02-19 22:39:17', 'completado', 12.99),
(19, 1, '2026-02-19 22:43:18', 'completado', 14.99),
(20, 1, '2026-02-19 23:28:06', 'completado', 1.5),
(26, 1, '2026-03-06 03:56:20', 'completado', 12.99);

SELECT setval('invoices_id_seq', (SELECT MAX(id) FROM invoices));

-- Insertar datos en invoice_items
INSERT INTO invoice_items (id, invoice_id, product_id, cantidad, precio_unitario) VALUES 
(20, 9, 1, 2, 12.99),
(21, 10, 6, 1, 1.5),
(22, 11, 6, 1, 1.5),
(23, 12, 6, 1, 1.5),
(24, 13, 6, 1, 1.5),
(38, 17, 6, 1, 1.5),
(39, 18, 1, 1, 12.99),
(40, 19, 2, 1, 14.99),
(41, 20, 6, 1, 1.5),
(57, 26, 11, 1, 12.99);

SELECT setval('invoice_items_id_seq', (SELECT MAX(id) FROM invoice_items));

-- Insertar datos en payments
INSERT INTO payments (id, telegram_id, mp_payment_id, invoice_id, monto, concepto, estado, fecha_creacion, fecha_aprobacion) VALUES 
(1, 7225069015, NULL, 17, 1.5, 'Pedido #0000000017', 'pendiente', '2026-02-19 21:48:14', NULL),
(2, 7225069015, NULL, 18, 12.99, 'Pedido #0000000018', 'pendiente', '2026-02-19 22:40:48', NULL),
(3, 7225069015, NULL, 19, 14.99, 'Pedido #0000000019', 'pendiente', '2026-02-19 22:43:23', NULL),
(4, 7225069015, '146271431813', 20, 1.5, 'Pedido #0000000020', 'aprobado', '2026-02-19 23:57:43', '2026-02-19 21:16:21.792562'),
(5, 7225069015, NULL, 26, 12.99, 'Pedido #0000000026', 'pendiente', '2026-03-08 13:19:25', NULL);

SELECT setval('payments_id_seq', (SELECT MAX(id) FROM payments));

-- Crear índices
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers (city);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
CREATE INDEX IF NOT EXISTS idx_products_category_available_name ON products (category_id, disponible, nombre);
CREATE INDEX IF NOT EXISTS idx_logs_date ON upload_logs (upload_date);
CREATE INDEX IF NOT EXISTS idx_logs_status ON upload_logs (status);

COMMIT;