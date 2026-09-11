-- Seed estático para taller/venta de repuestos automotrices.
-- Compatibles con el schema SQLite actual (categories, products, product_inventory, customers).
-- Los IDs de categorías y productos son fijos para facilitar pruebas.

PRAGMA foreign_keys = OFF;

-- ============================================================
-- Categorías
-- ============================================================
DELETE FROM categories;
INSERT INTO categories (id, codigo, nombre, descripcion, parent_id) VALUES
(1, 'FREN', 'Frenos', 'Discos, pastillas, zapatas, líquido de frenos y componentes del sistema de frenado.', NULL),
(2, 'SUSP', 'Suspensión', 'Amortiguadores, resortes, bujes, rotulas y piezas de suspensión.', NULL),
(3, 'MOTOR', 'Motor', 'Bujías, correas, sensores, juntas y repuestos para motor.', NULL),
(4, 'TRAN', 'Transmisión', 'Embragues, clutch, aceites de transmisión y componentes de caja.', NULL),
(5, 'ELEC', 'Electricidad', 'Baterías, alternadores, arranques, fusibles y faros.', NULL),
(6, 'FILT', 'Filtración', 'Filtros de aceite, aire, combustible y habitáculo.', NULL),
(7, 'CARRO', 'Carrocería', 'Parachoques, espejos, guardabarros, manijas y accesorios de carrocería.', NULL),
(8, 'ACEITE', 'Aceites y lubricantes', 'Aceites de motor, refrigerantes, grasas y aditivos.', NULL),
(9, 'NEUM', 'Neumáticos', 'Neumáticos para autos, camionetas y utilitarios.', NULL),
(10, 'ACCES', 'Accesorios', 'Limpia-parabrisas, alfombras, fundas, antenas y otros accesorios.', NULL);

-- ============================================================
-- Productos
-- ============================================================
DELETE FROM products;
INSERT INTO products (id, nombre, descripcion, precio, disponible, category_id) VALUES
-- Frenos
(1, 'Disco de freno delantero', 'Disco ventilado 280mm para sedan y hatchback.', 45.00, 1, 1),
(2, 'Pastillas de freno delanteras', 'Juego de pastillas semimetálicas de alto rendimiento.', 32.50, 1, 1),
(3, 'Líquido de frenos DOT 4', 'Envase de 500ml. Compatible con todos los sistemas hidráulicos DOT 4.', 12.00, 1, 1),
-- Suspensión
(4, 'Amortiguador delantero', 'Amortiguador a gas para suspensión delantera.', 68.00, 1, 2),
(5, 'Resorte helicoidal', 'Resorte de suspensión trasera reforzado.', 55.00, 1, 2),
(6, 'Buje de barra estabilizadora', 'Kit de bujes de poliuretano.', 18.00, 1, 2),
-- Motor
(7, 'Bujía de encendido', 'Bujía de iridio larga duración.', 9.50, 1, 3),
(8, 'Correa distribución', 'Correa dentada de alto kilometraje.', 85.00, 1, 3),
(9, 'Sensor de oxígeno O2', 'Sensor lambda universal 4 cables.', 42.00, 1, 3),
-- Transmisión
(10, 'Kit de embrague', 'Disco, plato y collarín para transmisión manual.', 165.00, 1, 4),
(11, 'Aceite de caja manual 75W90', 'Envase 1 litro, sintético.', 22.00, 1, 4),
-- Electricidad
(12, 'Batería 12V 60Ah', 'Batería de arranque con garantía de 12 meses.', 120.00, 1, 5),
(13, 'Alternador remanufacturado', 'Alternador 90A compatible con múltiples modelos.', 145.00, 1, 5),
(14, 'Farol halógeno H4', 'Bombilla halógena H4 60/55W.', 8.00, 1, 5),
-- Filtración
(15, 'Filtro de aceite', 'Filtro de aceite convencional.', 7.50, 1, 6),
(16, 'Filtro de aire', 'Filtro de aire de reemplazo.', 14.00, 1, 6),
(17, 'Filtro de habitáculo', 'Filtro antipolen y antiolor.', 11.00, 1, 6),
-- Carrocería
(18, 'Espejo retrovisor lateral', 'Espejo manual lado derecho.', 35.00, 1, 7),
(19, 'Manija de puerta exterior', 'Manija cromada lado izquierdo.', 22.00, 1, 7),
-- Aceites y lubricantes
(20, 'Aceite de motor 5W30', 'Aceite semisintético 1 litro.', 18.50, 1, 8),
(21, 'Aceite de motor 10W40', 'Aceite mineral 4 litros.', 48.00, 1, 8),
(22, 'Refrigerante concentrado', 'Envase 1 litro, protección anticorrosión.', 15.00, 1, 8),
-- Neumáticos
(23, 'Neumático 185/60 R14', 'Neumático de turismo, alto rendimiento.', 75.00, 1, 9),
(24, 'Neumático 205/55 R16', 'Neumático de turismo, buen agarre en mojado.', 105.00, 1, 9),
-- Accesorios
(25, 'Escobilla limpia-parabrisas 18"', 'Escobilla plana universal.', 14.00, 1, 10),
(26, 'Alfombra de goma', 'Juego de alfombras universales.', 25.00, 1, 10);

-- ============================================================
-- Inventario inicial
-- ============================================================
DELETE FROM product_inventory;
INSERT INTO product_inventory (product_id, stock_actual, stock_reservado, stock_minimo, updated_at, ultima_compra, ubicacion_almacen) VALUES
(1,  24, 0, 5,  CURRENT_TIMESTAMP, '2026-08-15', 'E-A1'),
(2,  40, 0, 10, CURRENT_TIMESTAMP, '2026-08-15', 'E-A1'),
(3,  60, 0, 12, CURRENT_TIMESTAMP, '2026-08-20', 'E-A2'),
(4,  16, 0, 4,  CURRENT_TIMESTAMP, '2026-08-10', 'E-B1'),
(5,  20, 0, 5,  CURRENT_TIMESTAMP, '2026-08-10', 'E-B2'),
(6,  100, 0, 20, CURRENT_TIMESTAMP, '2026-08-18', 'E-B3'),
(7,  80, 0, 20, CURRENT_TIMESTAMP, '2026-09-01', 'E-C1'),
(8,  12, 0, 3,  CURRENT_TIMESTAMP, '2026-08-05', 'E-C2'),
(9,  8,  0, 2,  CURRENT_TIMESTAMP, '2026-08-22', 'E-C3'),
(10, 6,  0, 2,  CURRENT_TIMESTAMP, '2026-08-12', 'E-D1'),
(11, 30, 0, 6,  CURRENT_TIMESTAMP, '2026-08-25', 'E-D2'),
(12, 10, 0, 3,  CURRENT_TIMESTAMP, '2026-09-02', 'E-E1'),
(13, 4,  0, 1,  CURRENT_TIMESTAMP, '2026-07-30', 'E-E2'),
(14, 50, 0, 10, CURRENT_TIMESTAMP, '2026-08-28', 'E-E3'),
(15, 120, 0, 30, CURRENT_TIMESTAMP, '2026-09-03', 'E-F1'),
(16, 45, 0, 10, CURRENT_TIMESTAMP, '2026-09-03', 'E-F2'),
(17, 35, 0, 8,  CURRENT_TIMESTAMP, '2026-08-29', 'E-F3'),
(18, 14, 0, 4,  CURRENT_TIMESTAMP, '2026-08-14', 'E-G1'),
(19, 22, 0, 6,  CURRENT_TIMESTAMP, '2026-08-14', 'E-G2'),
(20, 48, 0, 12, CURRENT_TIMESTAMP, '2026-09-04', 'E-H1'),
(21, 36, 0, 9,  CURRENT_TIMESTAMP, '2026-09-04', 'E-H2'),
(22, 25, 0, 6,  CURRENT_TIMESTAMP, '2026-08-21', 'E-H3'),
(23, 16, 0, 4,  CURRENT_TIMESTAMP, '2026-08-16', 'E-I1'),
(24, 12, 0, 3,  CURRENT_TIMESTAMP, '2026-08-16', 'E-I2'),
(25, 70, 0, 15, CURRENT_TIMESTAMP, '2026-08-30', 'E-J1'),
(26, 40, 0, 10, CURRENT_TIMESTAMP, '2026-08-30', 'E-J2');

-- ============================================================
-- Clientes de ejemplo (simulan usuarios de Telegram)
-- ============================================================
DELETE FROM customers;
INSERT INTO customers (
    id, customer_id, name, email, phone, address, city, state, country,
    postal_code, company, username, password_hash, created_at, updated_at,
    is_active, is_admin, email_verified, total_purchases
) VALUES
(1, '111111111', 'Juan Pérez', 'juan.perez@email.com', '555-0101', 'Av. Libertador 1234', 'Buenos Aires', 'CABA', 'Argentina', 'C1001', NULL, 'juanperez', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 0, 1, 0),
(2, '222222222', 'María González', 'maria.g@email.com', '555-0102', 'Calle Mitre 567', 'Rosario', 'Santa Fe', 'Argentina', 'S2000', NULL, 'mariagonzalez', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 0, 1, 0),
(3, '333333333', 'Carlos Rodríguez', 'carlos.r@email.com', '555-0103', 'Ruta 9 Km 25', 'Córdoba', 'Córdoba', 'Argentina', 'X5000', 'Taller Carlos', 'crodriguez', NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, 0, 0, 0);

PRAGMA foreign_keys = ON;
