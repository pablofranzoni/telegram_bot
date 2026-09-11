-- Migración: convierte las claves foráneas de invoices de INTEGER a TEXT UUID.
--
-- Es idempotente: si las tablas ya usan TEXT, simplemente copia los datos
-- tal cual. Si aún usan INTEGER (estado legacy), genera UUID v4 para cada
-- invoice existente y actualiza las tablas hijas.
--
-- Nota: los invoices creados después de esta migración usan UUID v7
-- generados en Python; los invoices legacy migrados aquí reciben UUID v4.

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- Tabla temporal de mapeo old_id (INTEGER) -> new_id (TEXT UUID).
CREATE TABLE IF NOT EXISTS __invoice_id_map (
    old_id INTEGER PRIMARY KEY,
    new_id TEXT NOT NULL
);

DELETE FROM __invoice_id_map;

-- Poblar el mapeo solo para invoices cuyo id sea INTEGER (legacy).
INSERT INTO __invoice_id_map (old_id, new_id)
SELECT id,
       lower(hex(randomblob(4))) || '-' ||
       lower(hex(randomblob(2))) || '-4' ||
       substr(lower(hex(randomblob(2))), 2, 3) || '-' ||
       substr('89ab', abs(random()) % 4 + 1, 1) ||
       substr(lower(hex(randomblob(2))), 2, 3) || '-' ||
       lower(hex(randomblob(6)))
FROM invoices
WHERE typeof(id) = 'integer';

-- Tablas nuevas con invoice_id como TEXT.
CREATE TABLE IF NOT EXISTS invoices_new (
    id TEXT PRIMARY KEY,
    folio INTEGER UNIQUE,
    customer_id INTEGER NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado TEXT DEFAULT 'pendiente',
    total REAL DEFAULT 0.0,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS invoice_items_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    product_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    precio_unitario REAL NOT NULL,
    subtotal REAL GENERATED ALWAYS AS (cantidad * precio_unitario) VIRTUAL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS payments_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    mp_payment_id TEXT UNIQUE,
    invoice_id TEXT,
    monto NUMERIC NOT NULL,
    concepto TEXT,
    estado TEXT DEFAULT 'pendiente',
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_aprobacion TIMESTAMP,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id)
);

CREATE TABLE IF NOT EXISTS sent_documents_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_type TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    delivery_channel TEXT NOT NULL,
    recipient_target TEXT NOT NULL,
    file_name TEXT NOT NULL,
    payment_id TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'sent',
    error_message TEXT,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id),
    UNIQUE(document_type, invoice_id, delivery_channel, recipient_target)
);

-- Limpiar tablas nuevas por si la migración se ejecutó parcialmente.
DELETE FROM invoices_new;
DELETE FROM invoice_items_new;
DELETE FROM payments_new;
DELETE FROM sent_documents_new;

-- Migrar invoices. COALESCE maneja tanto legacy (mapeo) como estado ya TEXT.
INSERT INTO invoices_new (id, folio, customer_id, fecha, estado, total)
SELECT COALESCE(m.new_id, CAST(i.id AS TEXT)),
       i.folio, i.customer_id, i.fecha, i.estado, i.total
FROM invoices i
LEFT JOIN __invoice_id_map m ON i.id = m.old_id;

-- Migrar items.
INSERT INTO invoice_items_new (id, invoice_id, product_id, cantidad, precio_unitario)
SELECT ii.id,
       COALESCE(m.new_id, CAST(ii.invoice_id AS TEXT)),
       ii.product_id, ii.cantidad, ii.precio_unitario
FROM invoice_items ii
LEFT JOIN __invoice_id_map m ON ii.invoice_id = m.old_id;

-- Migrar pagos.
INSERT INTO payments_new (id, telegram_id, mp_payment_id, invoice_id, monto, concepto, estado, fecha_creacion, fecha_aprobacion)
SELECT p.id, p.telegram_id, p.mp_payment_id,
       COALESCE(m.new_id, CAST(p.invoice_id AS TEXT)),
       p.monto, p.concepto, p.estado, p.fecha_creacion, p.fecha_aprobacion
FROM payments p
LEFT JOIN __invoice_id_map m ON p.invoice_id = m.old_id;

-- Migrar documentos enviados.
INSERT INTO sent_documents_new (id, document_type, invoice_id, delivery_channel, recipient_target, file_name, payment_id, sent_at, status, error_message)
SELECT s.id, s.document_type,
       COALESCE(m.new_id, CAST(s.invoice_id AS TEXT)),
       s.delivery_channel, s.recipient_target, s.file_name, s.payment_id,
       s.sent_at, s.status, s.error_message
FROM sent_documents s
LEFT JOIN __invoice_id_map m ON s.invoice_id = m.old_id;

-- Eliminar tablas viejas.
DROP TABLE IF EXISTS invoice_items;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS sent_documents;
DROP TABLE IF EXISTS invoices;

-- Renombrar tablas nuevas.
ALTER TABLE invoices_new RENAME TO invoices;
ALTER TABLE invoice_items_new RENAME TO invoice_items;
ALTER TABLE payments_new RENAME TO payments;
ALTER TABLE sent_documents_new RENAME TO sent_documents;

-- Recrear índices que dependen de estas tablas.
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoices_folio ON invoices (folio);

-- Limpiar tabla de mapeo.
DROP TABLE __invoice_id_map;

COMMIT;

PRAGMA foreign_keys = ON;
