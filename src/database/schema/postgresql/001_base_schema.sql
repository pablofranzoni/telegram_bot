-- Tabla categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) NOT NULL UNIQUE,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES categories(id)
);

-- Tabla upload_logs
CREATE TABLE IF NOT EXISTS upload_logs (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('processing', 'completed', 'failed', 'partial')),
    processed_rows INTEGER DEFAULT 0,
    total_rows INTEGER DEFAULT 0,
    error_message TEXT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_date TIMESTAMP,
    user_id INTEGER,
    checksum VARCHAR(64),
    metadata TEXT
);

-- Tabla csv_processing_errors
CREATE TABLE IF NOT EXISTS csv_processing_errors (
    id SERIAL PRIMARY KEY,
    upload_id INTEGER NOT NULL REFERENCES upload_logs(id),
    row_number INTEGER NOT NULL,
    raw_data TEXT,
    column_name VARCHAR(100),
    error_type VARCHAR(50) NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP
);

-- Tabla customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(30),
    address TEXT,
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50),
    postal_code VARCHAR(20),
    company VARCHAR(200),
    username VARCHAR(100),
    password_hash VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin INTEGER DEFAULT 0,
    email_verified BOOLEAN DEFAULT FALSE,
    email_verification_code VARCHAR(10),
    email_verification_expires TIMESTAMP,
    password_reset_token VARCHAR(64),
    password_reset_expires TIMESTAMP,
    created_by INTEGER REFERENCES customers(id),
    notes TEXT,
    last_purchase_date TIMESTAMP,
    total_purchases NUMERIC DEFAULT 0
);

-- Tabla products
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
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

-- Extension UUID v7
CREATE EXTENSION IF NOT EXISTS pg_uuidv7;

-- Tabla invoices
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v7(),
    folio SERIAL UNIQUE,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'pendiente',
    total NUMERIC DEFAULT 0.0
);

-- Tabla invoice_items
CREATE TABLE IF NOT EXISTS invoice_items (
    id SERIAL PRIMARY KEY,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    cantidad INTEGER NOT NULL,
    precio_unitario NUMERIC NOT NULL,
    subtotal NUMERIC GENERATED ALWAYS AS (cantidad * precio_unitario) STORED
);

-- Tabla payments
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    mp_payment_id VARCHAR(50) UNIQUE,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    monto NUMERIC NOT NULL,
    concepto VARCHAR(255),
    estado VARCHAR(20) DEFAULT 'pendiente',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_aprobacion TIMESTAMP
);

-- Tabla sent_documents
CREATE TABLE IF NOT EXISTS sent_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
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

-- Tabla schema_migrations (control de migraciones)
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers (city);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
CREATE INDEX IF NOT EXISTS idx_products_category_available_name ON products (category_id, disponible, nombre);
CREATE INDEX IF NOT EXISTS idx_logs_date ON upload_logs (upload_date);
CREATE INDEX IF NOT EXISTS idx_logs_status ON upload_logs (status);
CREATE INDEX IF NOT EXISTS idx_customers_username ON customers(username);
CREATE INDEX IF NOT EXISTS idx_customers_is_admin ON customers(is_admin);
CREATE INDEX IF NOT EXISTS idx_customers_email_verified ON customers(email_verified);
CREATE INDEX IF NOT EXISTS idx_customers_password_reset_token ON customers(password_reset_token);
CREATE INDEX IF NOT EXISTS idx_customers_email_verification_code ON customers(email_verification_code);
