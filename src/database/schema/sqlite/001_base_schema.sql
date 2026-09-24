-- Tabla categories
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    parent_id INTEGER,
    PRIMARY KEY(id AUTOINCREMENT)
);

-- Tabla upload_logs
CREATE TABLE IF NOT EXISTS upload_logs (
    id INTEGER,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'completed', 'failed', 'partial')),
    processed_rows INTEGER DEFAULT 0,
    total_rows INTEGER DEFAULT 0,
    error_message TEXT,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_date TIMESTAMP,
    user_id INTEGER,
    checksum TEXT,
    metadata TEXT,
    PRIMARY KEY(id AUTOINCREMENT)
);

-- Tabla csv_processing_errors
CREATE TABLE IF NOT EXISTS csv_processing_errors (
    id INTEGER,
    upload_id INTEGER NOT NULL,
    row_number INTEGER NOT NULL,
    raw_data TEXT,
    column_name TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT 0,
    resolved_at TIMESTAMP,
    PRIMARY KEY(id AUTOINCREMENT),
    FOREIGN KEY(upload_id) REFERENCES upload_logs(id)
);

-- Tabla customers
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER,
    customer_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    postal_code TEXT,
    company TEXT,
    username TEXT,
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    email_verified BOOLEAN DEFAULT 0,
    email_verification_code TEXT,
    email_verification_expires TIMESTAMP,
    password_reset_token TEXT,
    password_reset_expires TIMESTAMP,
    created_by INTEGER,
    notes TEXT,
    last_purchase_date TIMESTAMP,
    total_purchases REAL DEFAULT 0,
    PRIMARY KEY(id AUTOINCREMENT),
    FOREIGN KEY(created_by) REFERENCES customers(id)
);

-- Tabla products
CREATE TABLE IF NOT EXISTS products (
    id INTEGER,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    precio REAL NOT NULL,
    disponible BOOLEAN DEFAULT 1,
    category_id INTEGER,
    PRIMARY KEY(id AUTOINCREMENT),
    FOREIGN KEY(category_id) REFERENCES categories(id)
);

-- Tabla product_inventory
CREATE TABLE IF NOT EXISTS product_inventory (
    product_id INTEGER NOT NULL,
    stock_actual INTEGER NOT NULL DEFAULT 0 CHECK(stock_actual >= 0),
    stock_reservado INTEGER NOT NULL DEFAULT 0 CHECK(stock_reservado >= 0),
    stock_minimo INTEGER NOT NULL DEFAULT 0 CHECK(stock_minimo >= 0),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(product_id),
    FOREIGN KEY(product_id) REFERENCES products(id),
    CHECK(stock_reservado <= stock_actual)
);

-- Tabla invoices
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    folio INTEGER UNIQUE,
    customer_id INTEGER NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado TEXT DEFAULT 'pendiente',
    total REAL DEFAULT 0.0,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- Tabla invoice_items
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER,
    invoice_id TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario REAL NOT NULL,
    subtotal REAL GENERATED ALWAYS AS (cantidad * precio_unitario) VIRTUAL,
    PRIMARY KEY(id AUTOINCREMENT),
    FOREIGN KEY(invoice_id) REFERENCES invoices(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- Tabla payments
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER,
    telegram_id INTEGER NOT NULL,
    mp_payment_id TEXT UNIQUE,
    invoice_id TEXT,
    monto NUMERIC NOT NULL,
    concepto TEXT,
    estado TEXT DEFAULT 'pendiente',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_aprobacion TIMESTAMP,
    PRIMARY KEY(id AUTOINCREMENT),
    FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);

-- Tabla sent_documents
CREATE TABLE IF NOT EXISTS sent_documents (
    id INTEGER,
    document_type TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    delivery_channel TEXT NOT NULL,
    recipient_target TEXT NOT NULL,
    file_name TEXT NOT NULL,
    payment_id TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'sent',
    error_message TEXT,
    PRIMARY KEY(id AUTOINCREMENT),
    FOREIGN KEY(invoice_id) REFERENCES invoices(id),
    UNIQUE(document_type, invoice_id, delivery_channel, recipient_target)
);

-- Tabla schema_migrations (control de migraciones)
CREATE TABLE IF NOT EXISTS schema_migrations (
    id INTEGER,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(id AUTOINCREMENT)
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_customers_city ON customers (city);
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email);
CREATE INDEX IF NOT EXISTS idx_products_category_available_name ON products (category_id, disponible, nombre);
CREATE INDEX IF NOT EXISTS idx_logs_date ON upload_logs (upload_date);
CREATE INDEX IF NOT EXISTS idx_logs_status ON upload_logs (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_folio ON invoices (folio);
CREATE INDEX IF NOT EXISTS idx_customers_username ON customers(username);
CREATE INDEX IF NOT EXISTS idx_customers_is_admin ON customers(is_admin);
CREATE INDEX IF NOT EXISTS idx_customers_email_verified ON customers(email_verified);
CREATE INDEX IF NOT EXISTS idx_customers_password_reset_token ON customers(password_reset_token);
CREATE INDEX IF NOT EXISTS idx_customers_email_verification_code ON customers(email_verification_code);
