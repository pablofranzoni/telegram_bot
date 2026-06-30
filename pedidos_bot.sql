BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "categories" (
	"id"	INTEGER,
	"codigo"	TEXT NOT NULL UNIQUE,
	"nombre"	TEXT NOT NULL UNIQUE,
	"descripcion"	TEXT NOT NULL,
	"parent_id"	INTEGER,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "csv_processing_errors" (
	"id"	INTEGER,
	"upload_id"	INTEGER NOT NULL,
	"row_number"	INTEGER NOT NULL,
	"raw_data"	TEXT,
	"column_name"	TEXT,
	"error_type"	TEXT NOT NULL,
	"error_message"	TEXT NOT NULL,
	"created_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"resolved"	BOOLEAN DEFAULT 0,
	"resolved_at"	TIMESTAMP,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("upload_id") REFERENCES "upload_logs"("id")
);
CREATE TABLE IF NOT EXISTS "customers" (
	"id"	INTEGER,
	"customer_id"	TEXT NOT NULL UNIQUE,
	"name"	TEXT NOT NULL,
	"email"	TEXT,
	"phone"	TEXT,
	"address"	TEXT,
	"city"	TEXT,
	"state"	TEXT,
	"country"	TEXT,
	"postal_code"	TEXT,
	"company"	TEXT,
	"username"	TEXT,
	"password_hash"	TEXT,
	"created_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"updated_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"is_active"	BOOLEAN DEFAULT 1,
	"is_admin"	INTEGER DEFAULT 0,
	"email_verified"	BOOLEAN DEFAULT 0,
	"email_verification_code"	TEXT,
	"email_verification_expires"	TIMESTAMP,
	"password_reset_token"	TEXT,
	"password_reset_expires"	TIMESTAMP,
	"created_by"	INTEGER,
	"notes"	TEXT,
	"last_purchase_date"	TIMESTAMP,
	"total_purchases"	REAL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("created_by") REFERENCES "customers"("id")
);
CREATE TABLE IF NOT EXISTS "invoice_items" (
	"id"	INTEGER,
	"invoice_id"	INTEGER NOT NULL,
	"product_id"	INTEGER NOT NULL,
	"cantidad"	INTEGER NOT NULL,
	"precio_unitario"	REAL NOT NULL,
	"subtotal"	REAL GENERATED ALWAYS AS ("cantidad" * "precio_unitario") VIRTUAL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("invoice_id") REFERENCES "invoices"("id"),
	FOREIGN KEY("product_id") REFERENCES "products"("id")
);
CREATE TABLE IF NOT EXISTS "invoices" (
	"id"	INTEGER,
	"customer_id"	INTEGER NOT NULL,
	"fecha"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"estado"	TEXT DEFAULT 'pendiente',
	"total"	REAL DEFAULT 0.0,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("customer_id") REFERENCES "customers"("id")
);
CREATE TABLE IF NOT EXISTS "payments" (
	"id"	INTEGER,
	"telegram_id"	INTEGER NOT NULL,
	"mp_payment_id"	TEXT UNIQUE,
	"invoice_id"	INTEGER,
	"monto"	NUMERIC NOT NULL,
	"concepto"	TEXT,
	"estado"	TEXT DEFAULT 'pendiente',
	"fecha_creacion"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"fecha_aprobacion"	TIMESTAMP,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("invoice_id") REFERENCES "invoices"("id")
);
CREATE TABLE IF NOT EXISTS "sent_documents" (
	"id"	INTEGER,
	"document_type"	TEXT NOT NULL,
	"invoice_id"	INTEGER NOT NULL,
	"delivery_channel"	TEXT NOT NULL,
	"recipient_target"	TEXT NOT NULL,
	"file_name"	TEXT NOT NULL,
	"payment_id"	TEXT,
	"sent_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"status"	TEXT NOT NULL DEFAULT 'sent',
	"error_message"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("invoice_id") REFERENCES "invoices"("id"),
	UNIQUE("document_type", "invoice_id", "delivery_channel", "recipient_target")
);
CREATE TABLE IF NOT EXISTS "products" (
	"id"	INTEGER,
	"nombre"	TEXT NOT NULL,
	"descripcion"	TEXT,
	"precio"	REAL NOT NULL,
	"disponible"	BOOLEAN DEFAULT 1,
	"category_id"	INTEGER,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("category_id") REFERENCES "categories"("id")
);
CREATE TABLE IF NOT EXISTS "product_inventory" (
	"product_id"	INTEGER NOT NULL,
	"stock_actual"	INTEGER NOT NULL DEFAULT 0,
	"stock_reservado"	INTEGER NOT NULL DEFAULT 0,
	"stock_minimo"	INTEGER NOT NULL DEFAULT 0,
	"updated_at"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("product_id"),
	FOREIGN KEY("product_id") REFERENCES "products"("id"),
	CHECK("stock_actual" >= 0),
	CHECK("stock_reservado" >= 0),
	CHECK("stock_minimo" >= 0),
	CHECK("stock_reservado" <= "stock_actual")
);
CREATE TABLE IF NOT EXISTS "upload_logs" (
	"id"	INTEGER,
	"filename"	TEXT NOT NULL,
	"original_filename"	TEXT NOT NULL,
	"file_size"	INTEGER NOT NULL,
	"status"	TEXT NOT NULL CHECK("status" IN ('processing', 'completed', 'failed', 'partial')),
	"processed_rows"	INTEGER DEFAULT 0,
	"total_rows"	INTEGER DEFAULT 0,
	"error_message"	TEXT,
	"upload_date"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"completed_date"	TIMESTAMP,
	"user_id"	INTEGER,
	"checksum"	TEXT,
	"metadata"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);
INSERT INTO "categories" VALUES (1,'PIZ','pizzas','Pizzas',NULL);
INSERT INTO "categories" VALUES (2,'HAM','hamburguesas','Hamburguesas',NULL);
INSERT INTO "categories" VALUES (3,'BEB','bebidas','Bebidas',NULL);
INSERT INTO "categories" VALUES (4,'ENS','ensaladas','Ensaladas',NULL);
INSERT INTO "categories" VALUES (5,'EMP','empanadas','Empanadas',NULL);

INSERT INTO "products" VALUES (1,'Pizza Margarita','Queso mozzarella y tomate',12.99,1,1);
INSERT INTO "products" VALUES (2,'Pizza Pepperoni','Extra pepperoni',14.99,1,1);
INSERT INTO "products" VALUES (3,'Hamburguesa Clásica','Carne, lechuga, tomate',9.99,1,2);
INSERT INTO "products" VALUES (4,'Hamburguesa BBQ','Salsa barbacoa',11.99,1,2);
INSERT INTO "products" VALUES (5,'Coca-Cola','500ml',2.5,1,3);
INSERT INTO "products" VALUES (6,'Agua Mineral','1L',1.5,1,3);
INSERT INTO "products" VALUES (7,'Ensalada César','Pollo y aderezo especial',8.99,1,4);
INSERT INTO "products" VALUES (8,'Ensalada Mixta','Ensalada de Lechuga, Tomate y Cebolla',5.6,1,4);
INSERT INTO "products" VALUES (9,'Cerveza Lata 330 Quilmes','Cerveza Lata 330ml Quilmes',3.5,1,3);
INSERT INTO "products" VALUES (10,'Pizza Muzzarella','Queso mozzarella, tomates y aceitunas',10.99,1,1);
INSERT INTO "products" VALUES (11,'Hamburguesa Doble','Doble Carne, lechuga, tomate y huevo',12.99,1,2);

CREATE INDEX IF NOT EXISTS "idx_customers_city" ON "customers" (
	"city"
);
CREATE INDEX IF NOT EXISTS "idx_customers_email" ON "customers" (
	"email"
);
CREATE INDEX IF NOT EXISTS "idx_products_category_available_name" ON "products" (
	"category_id",
	"disponible",
	"nombre"
);
CREATE INDEX IF NOT EXISTS "idx_logs_date" ON "upload_logs" (
	"upload_date"
);
CREATE INDEX IF NOT EXISTS "idx_logs_status" ON "upload_logs" (
	"status"
);
COMMIT;
