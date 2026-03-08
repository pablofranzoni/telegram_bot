import sqlite3
from typing import Any
from database.db_manager import get_db

# ====================== FUNCIONES DE PRODUCTOS ======================
def obtener_categorias_db():
    try:
        db = get_db()
        categories: list[Any] | None = db.execute("""
                    SELECT categories.descripcion FROM categories 
                    INNER JOIN products ON categories.id = products.category_id 
                            WHERE products.disponible = 1 
                            GROUP BY categories.descripcion 
                            ORDER BY categories.descripcion
                """, fetchall=True)
        if categories is not None:
            return [row['descripcion'] for row in categories]
        return []
        
    except sqlite3.Error as e:
        print(f"Error al obtener categorías: {e}")
        return []  # Retorna lista vacía en caso de error


def obtener_productos_por_categoria(categoria):
    """Obtiene productos de una categoría específica"""
    try:
        db = get_db()
        productos_x_cat: list[Any] | None = db.execute('''
                SELECT products.id, products.nombre, products.descripcion, products.precio 
                FROM products 
                INNER JOIN categories ON products.category_id = categories.id
                WHERE categories.descripcion = ? AND products.disponible = 1
                ORDER BY nombre
            ''', (categoria,), fetchall=True)
        if productos_x_cat is not None:
            productos = [ (row['id'], row['nombre'], row['descripcion'], row['precio']) \
                         for row in productos_x_cat ]
            return productos
        return []
    
    except sqlite3.Error as e:
        print(f"Error al obtener productos por categoría: {e}")
        return []  # Retorna lista vacía en caso de error


def obtener_producto_por_id(product_id):
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
def guardar_cliente(telegram_id, nombre, apellido, username, email, telefono=None, direccion=None):
    """Registra o actualiza un cliente"""
    try:
        db = get_db()
        
        #insertar en table customers si no existe
        #si el cliente ya existe, actualizar su información (excepto el customer_id que es el telegram_id)
        if db.execute('SELECT id FROM customers WHERE customer_id = ?', (telegram_id,), fetchone=True):
            db.execute('''
            UPDATE customers 
            SET name = ?, phone = ?, address = ?, username = ?, email = ?
            WHERE customer_id = ?
            ''', (f"{nombre} {apellido}", telefono, direccion, username, email, telegram_id))
        else:   
            db.execute('''
                INSERT OR IGNORE INTO customers (customer_id, name, phone, address, username, email)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (telegram_id, f"{nombre} {apellido}", telefono, direccion, username, email))
        
    except sqlite3.Error as e:
        print(f"Error al registrar cliente: {e}")


def obtener_cliente(telegram_id):
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
        customer_id = customer['id']

        invoice_id = db.execute('INSERT INTO invoices (customer_id) VALUES (?)', (customer_id,))
        return invoice_id
    
    except sqlite3.Error as e:
        print(f"Error al crear Invoice: {e}")
        return None


def vaciar_pedido_db(invoice_id):
    try:
        db = get_db()
        # Eliminar todos los items del pedido
        db.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (invoice_id,))
        # Actualizar total del pedido a 0
        db.execute('UPDATE invoices SET total = 0 WHERE id = ?', (invoice_id,))

        return True
    
    except sqlite3.Error as e:
        print(f"Error al eliminar todos los productos del pedido: {e}") 
        return False


def agregar_producto(invoice_id, producto_id, cantidad):
    """Agrega un producto a un pedido"""
    try:
        db = get_db()
        
        # Obtener precio del producto
        product = db.execute('SELECT precio FROM products WHERE id = ?', 
                              (producto_id,), fetchone=True)
        if not product:
            return False
        
        precio_unitario = product['precio']
        
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
        customer_id = customer['id']

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


def quitar_producto_del_pedido(invoice_id, producto_id):
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
        return quitar_producto_del_pedido(invoice_id, producto_id)
    
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
    
    return True  # Por ahora, sin límite


def obtener_cantidad_producto(invoice_id, producto_id):
    """Obtiene la cantidad actual de un producto en un invoice"""
    try:
        db = get_db()
        resultado = db.execute('''
            SELECT cantidad FROM invoice_items 
            WHERE invoice_id = ? AND product_id = ?
        ''', (invoice_id, producto_id), fetchone=True)
        return resultado['cantidad'] if resultado else None
    
    except sqlite3.Error as e:
        print(f"Error al obtener cantidad de producto: {e}")
        return None


def finalizar_pedido_db(invoice_id):
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


#======================= FUNCIONES DE PAGOS ======================

def guardar_pago(telegram_id, mp_payment_id, invoice_id, monto, concepto, estado='pendiente'):
    """Guarda el pago en base de datos"""
    try:
        db = get_db()
        pago_id = db.execute('''
            INSERT INTO payments (telegram_id, mp_payment_id, invoice_id, monto, concepto, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (telegram_id, mp_payment_id, invoice_id, monto, concepto, estado))
        print(f"💾 Pago guardado en BD: {mp_payment_id} - {concepto} - ${monto}")
        
        return pago_id
    except sqlite3.Error as e:
        print(f"Error al guardar pago en BD: {e}")
        return None


def actualizar_pago(payment_id, invoice_id, estado, monto, fecha_aprobacion=None):
    """Actualiza el estado del pago en nuestra BD"""
    try:
        db = get_db()
        db.execute('''
            UPDATE payments 
            SET estado = ?, fecha_aprobacion = ?, mp_payment_id = ?
            WHERE invoice_id = ? AND monto = ?
        ''', (estado, fecha_aprobacion, payment_id, invoice_id, monto))
    
        print(f"💾 Pago {payment_id} actualizado a {estado}")

    except sqlite3.Error as e:
        print(f"Error al actualizar pago: {e}")


def buscar_ultimo_pago_usuario(customer_id):
    """Busca el último pago realizado por un cliente"""
    try:
        db = get_db()
        payment = db.execute('''
            SELECT monto, concepto, estado, fecha_creacion, fecha_aprobacion, mp_payment_id FROM payments 
            WHERE telegram_id = ? 
            ORDER BY fecha_creacion DESC 
            LIMIT 1
        ''', (customer_id,), fetchone=True)
        return payment
    
    except sqlite3.Error as e:
        print(f"Error al buscar último pago: {e}")
        return None
    
    
    
    
