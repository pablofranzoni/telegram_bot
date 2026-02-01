import sqlite3


# ====================== CONFIGURACIÓN DE LA BASE DE DATOS ======================
def init_database():
    """Inicializa todas las tablas necesarias"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    
    # Tabla de productos disponibles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio REAL NOT NULL,
            categoria TEXT,
            disponible BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de usuarios/clientes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            telegram_id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            telefono TEXT,
            direccion TEXT,
            saldo REAL DEFAULT 0.0
        )
    ''')
    
    # Tabla principal de pedidos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado TEXT DEFAULT 'pendiente',
            total REAL DEFAULT 0.0,
            FOREIGN KEY (cliente_id) REFERENCES clientes (telegram_id)
        )
    ''')
    
    # Tabla de items del pedido (relación muchos-a-muchos)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedido_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            subtotal REAL GENERATED ALWAYS AS (cantidad * precio_unitario) VIRTUAL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos (id),
            FOREIGN KEY (producto_id) REFERENCES productos (id)
        )
    ''')
    
    # Insertar productos de ejemplo si la tabla está vacía
    cursor.execute('SELECT COUNT(*) FROM productos')
    if cursor.fetchone()[0] == 0:
        productos_ejemplo = [
            ('Pizza Margarita', 'Queso mozzarella y tomate', 12.99, 'pizzas'),
            ('Pizza Pepperoni', 'Extra pepperoni', 14.99, 'pizzas'),
            ('Hamburguesa Clásica', 'Carne, lechuga, tomate', 9.99, 'hamburguesas'),
            ('Hamburguesa BBQ', 'Salsa barbacoa', 11.99, 'hamburguesas'),
            ('Coca-Cola', '500ml', 2.50, 'bebidas'),
            ('Agua Mineral', '1L', 1.50, 'bebidas'),
            ('Ensalada César', 'Pollo y aderezo especial', 8.99, 'ensaladas')
        ]
        cursor.executemany('INSERT INTO productos (nombre, descripcion, precio, categoria) VALUES (?, ?, ?, ?)', productos_ejemplo)
    
    conn.commit()
    conn.close()
    print("✅ Base de datos inicializada correctamente")

if __name__ == "__main__":
    init_database()