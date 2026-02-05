import sqlite3
from database.db import get_db

# ====================== FUNCIONES DE PRODUCTOS ======================
def get_categorias():
    try:
        db = get_db()
        categories = db.execute("""
                    SELECT categories.descripcion FROM categories 
                    INNER JOIN products ON categories.id = products.category_id 
                            WHERE products.disponible = 1 
                            GROUP BY categories.descripcion 
                            ORDER BY categories.descripcion
                """, fetchall=True)
        return [row[0] for row in categories]
        
    except sqlite3.Error as e:
        print(f"Error al obtener categorías: {e}")
        return []  # Retorna lista vacía en caso de error

def get_productos_por_categoria(categoria):
    """Obtiene productos de una categoría específica"""
    try:
        db = get_db()
        productos_x_cat = db.execute('''
                SELECT products.id, products.nombre, products.descripcion, products.precio 
                FROM products 
                INNER JOIN categories ON products.category_id = categories.id
                WHERE categories.descripcion = ? AND products.disponible = 1
                ORDER BY nombre
            ''', (categoria,), fetchall=True)
        productos = [ (row[0], row[1], row[2], row[3]) for row in productos_x_cat ]
        return productos
    
    except sqlite3.Error as e:
        print(f"Error al obtener productos por categoría: {e}")
        return []  # Retorna lista vacía en caso de error


def get_producto_por_id(product_id):
    """Obtiene información de un producto específico"""
    try:
        db = get_db()
        producto = db.execute('''
                SELECT id, nombre, descripcion, precio 
                FROM products
                WHERE id = ?
            ''', (product_id,), fetchone=True)
        return producto
    
    except sqlite3.Error as e:
        print(f"Error al obtener producto por ID: {e}")
        return None

# ====================== FUNCIONES DE CLIENTES ======================
def registrar_cliente(telegram_id, nombre, apellido, username, telefono=None, direccion=None):
    """Registra o actualiza un cliente"""
    try:
        db = get_db()
        #db.execute('''
        #    INSERT OR REPLACE INTO clientes (telegram_id, nombre, apellido, username, telefono, direccion)
        #    VALUES (?, ?, ?, ?, ?, ?)
        #    ''', (telegram_id, nombre, apellido, username, telefono, direccion))
        
        #insertar en table customers si no existe
        db.execute('''
            INSERT OR REPLACE INTO customers (customer_id, name, phone, address, username)
            VALUES (?, ?, ?, ?, ?)
            ''', (telegram_id, f"{nombre} {apellido}", None, None, username))
        
    except sqlite3.Error as e:
        print(f"Error al registrar cliente: {e}")


def get_cliente(telegram_id):
    """Obtiene información de un cliente"""
    try:
        db = get_db()
        cliente = db.execute('SELECT * FROM customers WHERE customer_id = ?', 
                             (telegram_id,), fetchone=True)
        return cliente
    
    except sqlite3.Error as e:
        print(f"Error al obtener cliente: {e}")
        return None


# ====================== FUNCIONES DE PEDIDOS ======================
def crear_pedido(customer_id):
    """Crea un nuevo pedido y devuelve su ID"""
    try:
        db = get_db()

        #obtener el id del customer dado su customer_id que es el id de telegram
        customer = db.execute('SELECT id FROM customers WHERE customer_id = ?', (customer_id,), fetchone=True)
        if not customer:
            print(f"Cliente con ID {customer_id} no encontrado")
            return None
        customer_id = customer[0]

        db.execute('INSERT INTO invoices (customer_id) VALUES (?)', (customer_id,))
        invoice = db.execute('SELECT last_insert_rowid()', fetchone=True)
        invoice_id = invoice[0] if invoice else None
        return invoice_id
    
    except sqlite3.Error as e:
        print(f"Error al crear Invoice: {e}")
        return None


def eliminar_todos_productos_de_pedido(invoice_id):
    try:
        db = get_db()
        # Eliminar todos los items del pedido
        db.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (invoice_id,))
        # Actualizar total del pedido a 0
        db.execute('UPDATE invoices SET total = 0 WHERE id = ?', (invoice_id,))
    except sqlite3.Error as e:
        print(f"Error al eliminar todos los productos del pedido: {e}") 


def agregar_producto_a_pedido(invoice_id, producto_id, cantidad):
    """Agrega un producto a un pedido"""
    try:
        db = get_db()
        
        # Obtener precio del producto
        product = db.execute('SELECT precio FROM products WHERE id = ?', 
                              (producto_id,), fetchone=True)
        if not product:
            return False
        
        precio_unitario = product[0]
        
        # Verificar si el producto ya está en el pedido
        item_existente = db.execute('''
            SELECT id, cantidad FROM invoice_items 
            WHERE invoice_id = ? AND product_id = ?
        ''', (invoice_id, producto_id), fetchone=True)
        
        if item_existente:
            # Actualizar cantidad si ya existe
            nueva_cantidad = item_existente[1] + cantidad
            db.execute('''
                UPDATE invoice_items 
                SET cantidad = ?, precio_unitario = ?
                WHERE id = ?
            ''', (nueva_cantidad, precio_unitario, item_existente[0]))
        else:
            # Insertar nuevo item
            db.execute('''
                INSERT INTO invoice_items (invoice_id, product_id, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
            ''', (invoice_id, producto_id, cantidad, precio_unitario))
        
        # Actualizar total del pedido
        db.execute('''
            UPDATE invoices 
            SET total = (
                SELECT SUM(cantidad * precio_unitario) 
                FROM invoice_items 
                WHERE invoice_id = ?
            )
            WHERE id = ?
        ''', (invoice_id, invoice_id))
        
        return True
    
    except sqlite3.Error as e:
        print(f"Error al agregar producto a invoice: {e}")
        return False


def obtener_pedido_actual(customer_id):
    """Obtiene el pedido pendiente del cliente"""
    try:
        db = get_db()

        #obtener el id del customer dado su customer_id que es el id de telegram
        customer = db.execute('SELECT id FROM customers WHERE customer_id = ?', (customer_id,), fetchone=True)
        if not customer:
            print(f"Cliente con ID {customer_id} no encontrado")
            return None
        customer_id = customer[0]

        pedido = db.execute('''
            SELECT p.id, p.total, COUNT(pi.id) as items
            FROM invoices p
            LEFT JOIN invoice_items pi ON p.id = pi.invoice_id
            WHERE p.customer_id = ? AND p.estado = 'pendiente'
            GROUP BY p.id
            ORDER BY p.fecha DESC
            LIMIT 1
        ''', (customer_id,), fetchone=True)
        return pedido
    
    except sqlite3.Error as e:
        print(f"Error al obtener pedido actual: {e}")
        return None


def obtener_detalle_pedido(invoice_id):
    """Obtiene el detalle completo de un invoice"""
    try:
        db = get_db()
            # Información del pedido
        info_pedido = db.execute('''
            SELECT p.id, p.fecha, p.estado, p.total, c.name
            FROM invoices p
            JOIN customers c ON p.customer_id = c.id
            WHERE p.id = ?
        ''', (invoice_id,), fetchone=True)
        # Items del pedido
        items = db.execute('''
            SELECT pr.id, pr.nombre, pi.cantidad, pi.precio_unitario, 
                   (pi.cantidad * pi.precio_unitario) as subtotal
            FROM invoice_items pi
            JOIN products pr ON pi.product_id = pr.id
            WHERE pi.invoice_id = ?
            ORDER BY pr.nombre
        ''', (invoice_id,), fetchall=True)
        return info_pedido, items
    
    except sqlite3.Error as e:
        print(f"Error al obtener detalle de invoice: {e}")
        return None, []


def eliminar_producto_de_db(invoice_id, producto_id):
    """
    Elimina un producto de la base de datos.
    Retorna True si fue exitoso, False si hubo error.
    """
    try:
        db = get_db()
        # 1. Eliminar el item
        db.execute('''
            DELETE FROM invoice_items 
            WHERE invoice_id = ? AND product_id = ?
            ''', (invoice_id, producto_id))
        # 2. Actualizar total del invoice
        db.execute('''
            UPDATE invoices 
            SET total = COALESCE((
                SELECT SUM(cantidad * precio_unitario)
                FROM invoice_items 
                WHERE invoice_id = ?
            ), 0)
            WHERE id = ?
            ''', (invoice_id, invoice_id))
        
        # 3. Verificar si el invoice quedó vacío
        count = db.execute('SELECT COUNT(*) FROM invoice_items WHERE invoice_id = ?', 
                           (invoice_id,),fetchone=True)
        if count[0] == 0:
            # Eliminar invoice vacío
            db.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
        
        return True
    
    except sqlite3.Error as e:
        print(f"Error en BD al eliminar producto: {e}")
        return False


def actualizar_cantidad_producto(invoice_id, producto_id, nueva_cantidad):
    """
    Actualiza la cantidad de un producto en la base de datos.
    Retorna True si fue exitoso.
    """
    if nueva_cantidad <= 0:
        return eliminar_producto_de_db(invoice_id, producto_id)
    
    try:
        db = get_db()
        
        # 1. Actualizar cantidad
        db.execute('''
            UPDATE invoice_items 
            SET cantidad = ? 
            WHERE invoice_id = ? AND product_id = ?
        ''', (nueva_cantidad, invoice_id, producto_id))
        
        # 2. Actualizar precio unitario (por si cambió)
        db.execute('''
            UPDATE invoice_items 
            SET precio_unitario = (
                SELECT precio FROM products WHERE id = ?
            )
            WHERE invoice_id = ? AND product_id = ?
        ''', (producto_id, invoice_id, producto_id))
        
        # 3. Actualizar total del invoice
        db.execute('''
            UPDATE invoices 
            SET total = (
                SELECT SUM(cantidad * precio_unitario)
                FROM invoice_items 
                WHERE invoice_id = ?
            )
            WHERE id = ?
        ''', (invoice_id, invoice_id))
        
        return True
    except sqlite3.Error as e:
        print(f"Error actualizando cantidad: {e}")
        return False
    

def verificar_stock_disponible(producto_id):
    """
    Verifica el stock disponible de un producto.
    Retorna None si no hay control de stock.
    """
    # Si tienes tabla de inventario, implementa aquí
    # Ejemplo:
    # conn = sqlite3.connect('pedidos_bot.db')
    # cursor = conn.cursor()
    # cursor.execute('SELECT stock FROM inventario WHERE producto_id = ?', (producto_id,))
    # resultado = cursor.fetchone()
    # conn.close()
    # return resultado[0] if resultado else None
    
    return None  # Por ahora, sin límite


def obtener_cantidad_producto(invoice_id, producto_id):
    """Obtiene la cantidad actual de un producto en un invoice"""
    try:
        db = get_db()
        resultado = db.execute('''
            SELECT cantidad FROM invoice_items 
            WHERE invoice_id = ? AND product_id = ?
        ''', (invoice_id, producto_id), fetchone=True)
        return resultado[0] if resultado else None
    
    except sqlite3.Error as e:
        print(f"Error al obtener cantidad de producto: {e}")
        return None


def finalizar_pedido(invoice_id):
    """Marca un invoice como completado"""
    try:
        db = get_db()
        db.execute('''
            UPDATE invoices 
            SET estado = 'completado' 
            WHERE id = ?
        ''', (invoice_id,))
        
    except sqlite3.Error as e:
        print(f"Error al finalizar invoice: {e}") 
