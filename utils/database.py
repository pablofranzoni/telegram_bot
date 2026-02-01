import sqlite3
from database.db import get_db

# ====================== FUNCIONES DE PRODUCTOS ======================
def get_categorias():
    try:
        db = get_db()
        categorias = db.execute("""
                    SELECT categorias.descripcion FROM categorias 
                    INNER JOIN productos ON categorias.id = productos.categoria_id 
                            WHERE productos.disponible = 1 
                            GROUP BY categorias.descripcion 
                            ORDER BY categorias.descripcion
                """, fetchall=True)
        return [row[0] for row in categorias]
        
    except sqlite3.Error as e:
        print(f"Error al obtener categorías: {e}")
        return []  # Retorna lista vacía en caso de error

def get_productos_por_categoria(categoria):
    """Obtiene productos de una categoría específica"""
    try:
         with sqlite3.connect('pedidos_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT productos.id, productos.nombre, productos.descripcion, productos.precio 
                FROM productos 
                INNER JOIN categorias ON productos.categoria_id = categorias.id
                WHERE categorias.descripcion = ? AND productos.disponible = 1
                ORDER BY nombre
            ''', (categoria,))
            productos = cursor.fetchall()
         return productos
    except sqlite3.Error as e:
        print(f"Error al obtener productos por categoría: {e}")
        return []  # Retorna lista vacía en caso de error


def get_producto_por_id(producto_id):
    """Obtiene información de un producto específico"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre, descripcion, precio FROM productos WHERE id = ?', (producto_id,))
    producto = cursor.fetchone()
    conn.close()
    return producto

# ====================== FUNCIONES DE CLIENTES ======================
def registrar_cliente(telegram_id, nombre, apellido, username, telefono=None, direccion=None):
    """Registra o actualiza un cliente"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO clientes (telegram_id, nombre, apellido, username, telefono, direccion)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (telegram_id, nombre, apellido, username, telefono, direccion))
    conn.commit()
    conn.close()

def get_cliente(telegram_id):
    """Obtiene información de un cliente"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes WHERE telegram_id = ?', (telegram_id,))
    cliente = cursor.fetchone()
    conn.close()
    return cliente

# ====================== FUNCIONES DE PEDIDOS ======================
def crear_pedido(cliente_id):
    """Crea un nuevo pedido y devuelve su ID"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pedidos (cliente_id) VALUES (?)', (cliente_id,))
    pedido_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return pedido_id

def agregar_producto_a_pedido(pedido_id, producto_id, cantidad):
    """Agrega un producto a un pedido"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    
    # Obtener precio del producto
    cursor.execute('SELECT precio FROM productos WHERE id = ?', (producto_id,))
    resultado = cursor.fetchone()
    if not resultado:
        conn.close()
        return False
    
    precio_unitario = resultado[0]
    
    # Verificar si el producto ya está en el pedido
    cursor.execute('''
        SELECT id, cantidad FROM pedido_items 
        WHERE pedido_id = ? AND producto_id = ?
    ''', (pedido_id, producto_id))
    
    item_existente = cursor.fetchone()
    
    if item_existente:
        # Actualizar cantidad si ya existe
        nueva_cantidad = item_existente[1] + cantidad
        cursor.execute('''
            UPDATE pedido_items 
            SET cantidad = ?, precio_unitario = ?
            WHERE id = ?
        ''', (nueva_cantidad, precio_unitario, item_existente[0]))
    else:
        # Insertar nuevo item
        cursor.execute('''
            INSERT INTO pedido_items (pedido_id, producto_id, cantidad, precio_unitario)
            VALUES (?, ?, ?, ?)
        ''', (pedido_id, producto_id, cantidad, precio_unitario))
    
    # Actualizar total del pedido
    cursor.execute('''
        UPDATE pedidos 
        SET total = (
            SELECT SUM(cantidad * precio_unitario) 
            FROM pedido_items 
            WHERE pedido_id = ?
        )
        WHERE id = ?
    ''', (pedido_id, pedido_id))
    
    conn.commit()
    conn.close()
    return True

def obtener_pedido_actual(cliente_id):
    """Obtiene el pedido pendiente del cliente"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.total, COUNT(pi.id) as items
        FROM pedidos p
        LEFT JOIN pedido_items pi ON p.id = pi.pedido_id
        WHERE p.cliente_id = ? AND p.estado = 'pendiente'
        GROUP BY p.id
        ORDER BY p.fecha DESC
        LIMIT 1
    ''', (cliente_id,))
    pedido = cursor.fetchone()
    conn.close()
    return pedido

def obtener_detalle_pedido(pedido_id):
    """Obtiene el detalle completo de un pedido"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    
    # Información del pedido
    cursor.execute('''
        SELECT p.id, p.fecha, p.estado, p.total, c.nombre
        FROM pedidos p
        JOIN clientes c ON p.cliente_id = c.telegram_id
        WHERE p.id = ?
    ''', (pedido_id,))
    info_pedido = cursor.fetchone()
    
    # Items del pedido
    cursor.execute('''
        SELECT pr.id, pr.nombre, pi.cantidad, pi.precio_unitario, 
               (pi.cantidad * pi.precio_unitario) as subtotal
        FROM pedido_items pi
        JOIN productos pr ON pi.producto_id = pr.id
        WHERE pi.pedido_id = ?
        ORDER BY pr.nombre
    ''', (pedido_id,))
    items = cursor.fetchall()
    
    conn.close()
    return info_pedido, items

def eliminar_producto_de_db(pedido_id, producto_id):
    """
    Elimina un producto de la base de datos.
    Retorna True si fue exitoso, False si hubo error.
    """
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    
    try:
        # 1. Eliminar el item
        cursor.execute('''
            DELETE FROM pedido_items 
            WHERE pedido_id = ? AND producto_id = ?
        ''', (pedido_id, producto_id))
        
        # 2. Actualizar total del pedido
        cursor.execute('''
            UPDATE pedidos 
            SET total = COALESCE((
                SELECT SUM(cantidad * precio_unitario)
                FROM pedido_items 
                WHERE pedido_id = ?
            ), 0)
            WHERE id = ?
        ''', (pedido_id, pedido_id))
        
        # 3. Verificar si el pedido quedó vacío
        cursor.execute('SELECT COUNT(*) FROM pedido_items WHERE pedido_id = ?', (pedido_id,))
        items_restantes = cursor.fetchone()[0]
        
        if items_restantes == 0:
            # Eliminar pedido vacío
            cursor.execute('DELETE FROM pedidos WHERE id = ?', (pedido_id,))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error en BD al eliminar producto: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def actualizar_cantidad_producto(pedido_id, producto_id, nueva_cantidad):
    """
    Actualiza la cantidad de un producto en la base de datos.
    Retorna True si fue exitoso.
    """
    if nueva_cantidad <= 0:
        return eliminar_producto_de_db(pedido_id, producto_id)
    
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    
    try:
        # 1. Actualizar cantidad
        cursor.execute('''
            UPDATE pedido_items 
            SET cantidad = ? 
            WHERE pedido_id = ? AND producto_id = ?
        ''', (nueva_cantidad, pedido_id, producto_id))
        
        # 2. Actualizar precio unitario (por si cambió)
        cursor.execute('''
            UPDATE pedido_items 
            SET precio_unitario = (
                SELECT precio FROM productos WHERE id = ?
            )
            WHERE pedido_id = ? AND producto_id = ?
        ''', (producto_id, pedido_id, producto_id))
        
        # 3. Actualizar total del pedido
        cursor.execute('''
            UPDATE pedidos 
            SET total = (
                SELECT SUM(cantidad * precio_unitario)
                FROM pedido_items 
                WHERE pedido_id = ?
            )
            WHERE id = ?
        ''', (pedido_id, pedido_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"Error actualizando cantidad: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

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

def obtener_cantidad_producto(pedido_id, producto_id):
    """Obtiene la cantidad actual de un producto en un pedido"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT cantidad FROM pedido_items 
        WHERE pedido_id = ? AND producto_id = ?
    ''', (pedido_id, producto_id))
    
    resultado = cursor.fetchone()
    conn.close()
    
    return resultado[0] if resultado else None



def finalizar_pedido(pedido_id):
    """Marca un pedido como completado"""
    conn = sqlite3.connect('pedidos_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE pedidos SET estado = 'completado' WHERE id = ?", (pedido_id,))
    conn.commit()
    conn.close()