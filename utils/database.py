import logging
from typing import Any
from database.db import DatabaseError
from database.db_manager import get_db
from utils.logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


def _execute_db(db, query, params=(), fetchone=False, fetchall=False, param_types=None):
    """Compat wrapper for db.execute across adapters with/without param_types."""
    try:
        return db.execute(
            query,
            params,
            fetchone=fetchone,
            fetchall=fetchall,
            param_types=param_types,
        )
    except TypeError:
        # SQLite/MySQL adapters in this project do not accept param_types.
        return db.execute(query, params, fetchone=fetchone, fetchall=fetchall)

# ====================== FUNCIONES DE PRODUCTOS ======================
def obtener_categorias_db():
    try:
        db = get_db()
        categories: list[Any] | None = db.execute('''
                    SELECT categories.nombre, categories.descripcion FROM categories 
                    INNER JOIN products ON categories.id = products.category_id 
                            WHERE products.disponible = ?
                            GROUP BY categories.nombre, categories.descripcion 
                            ORDER BY categories.nombre
                ''', (1,), fetchall=True, param_types=['boolean'])
        if categories is not None:
            return [(row['nombre'], row['descripcion']) for row in categories]
        return []
        
    except DatabaseError as e:
        logger.error("Error al obtener categorias: %s", e)
        return []  # Retorna lista vacía en caso de error


def obtener_productos_por_categoria(categoria):
    """Obtiene productos de una categoría específica"""
    logger.debug("Obteniendo productos por categoria", extra={"categoria": categoria})
    try:
        db = get_db()
        productos_x_cat: list[Any] | None = db.execute('''
                SELECT products.id, products.nombre, products.descripcion, products.precio 
                FROM products 
                INNER JOIN categories ON products.category_id = categories.id
                WHERE categories.nombre = ? AND products.disponible = ?
                ORDER BY nombre
            ''', (categoria,1,), fetchall=True, param_types=['text', 'boolean'])
        if productos_x_cat is not None:
            productos = [ (row['id'], row['nombre'], row['descripcion'], row['precio']) \
                         for row in productos_x_cat ]
            return productos
        return []
    
    except DatabaseError as e:
        logger.error("Error al obtener productos por categoria %s: %s", categoria, e)
        return []  # Retorna lista vacía en caso de error


def obtener_productos_por_categoria_paginados(categoria, limite, offset=0):
    """Obtiene una página de productos de una categoría específica."""
    logger.debug(
        "Obteniendo productos por categoria paginados",
        extra={"categoria": categoria, "limite": limite, "offset": offset},
    )
    try:
        db = get_db()
        productos_x_cat: list[Any] | None = db.execute('''
                SELECT products.id, products.nombre, products.descripcion, products.precio 
                FROM products 
                INNER JOIN categories ON products.category_id = categories.id
                WHERE categories.nombre = ? AND products.disponible = ?
                ORDER BY products.nombre
                LIMIT ? OFFSET ?
            ''', (categoria, 1, limite, offset), fetchall=True, param_types=['text', 'boolean', 'integer', 'integer'])
        if productos_x_cat is not None:
            productos = [
                (row['id'], row['nombre'], row['descripcion'], row['precio'])
                for row in productos_x_cat
            ]
            return productos
        return []

    except DatabaseError as e:
        logger.error(
            "Error al obtener productos paginados por categoria %s: %s",
            categoria,
            e,
        )
        return []


def obtener_producto_por_id(product_id):
    """Obtiene información de un producto específico"""
    try:
        db = get_db()
        producto = db.execute('''
                SELECT id, nombre, descripcion, precio 
                FROM products
                WHERE id = ?
            ''', (product_id,), fetchone=True, param_types=['integer'])
        return producto
    
    except DatabaseError as e:
        logger.error("Error al obtener producto por ID %s: %s", product_id, e)
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
            ''', (f"{nombre} {apellido}", telefono, direccion, username, email, telegram_id), 
            param_types=['text', 'text', 'text', 'text', 'text', 'text'])
        else:   
            db.execute('''
                INSERT INTO customers (customer_id, name, phone, address, username, email)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (telegram_id, f"{nombre} {apellido}", telefono, direccion, username, email), 
                param_types=['text', 'text', 'text', 'text', 'text', 'text'])
        
    except DatabaseError as e:
        logger.error("Error al registrar cliente %s: %s", telegram_id, e)


def obtener_cliente(telegram_id):
    """Obtiene información de un cliente"""
    try:
        db = get_db()
        cliente = db.execute('SELECT * FROM customers WHERE customer_id = ?', 
                             (telegram_id,), fetchone=True, param_types=['text'])
        return cliente
    
    except DatabaseError as e:
        logger.error("Error al obtener cliente %s: %s", telegram_id, e)
        return None


# ====================== FUNCIONES DE PEDIDOS ======================
def crear_pedido(customer_id):
    """Crea un nuevo pedido y devuelve su ID"""
    try:
        db = get_db()

        #obtener el id del customer dado su customer_id que es el id de telegram
        customer = db.execute('SELECT id FROM customers WHERE customer_id = ?', 
                              (customer_id,), fetchone=True, param_types=['text'])
        if not customer:
            logger.warning("Cliente no encontrado al crear pedido", extra={"customer_id": customer_id})
            return None
        customer_id = customer['id']

        invoice_id = db.execute('INSERT INTO invoices (customer_id) VALUES (?)', 
                                (customer_id,), param_types=['integer'])
        return invoice_id
    
    except DatabaseError as e:
        logger.error("Error al crear invoice para customer_id %s: %s", customer_id, e)
        return None


def vaciar_pedido_db(invoice_id):
    try:
        db = get_db()
        # Eliminar todos los items del pedido
        db.execute('DELETE FROM invoice_items WHERE invoice_id = ?', (invoice_id,), 
                   param_types=['integer'])
        # Actualizar total del pedido a 0
        db.execute('UPDATE invoices SET total = 0 WHERE id = ?', (invoice_id,), 
                   param_types=['integer'])

        return True
    
    except DatabaseError as e:
        logger.error("Error al vaciar pedido %s: %s", invoice_id, e)
        return False


def agregar_producto(invoice_id, producto_id, cantidad):
    """Agrega un producto a un pedido"""
    try:
        db = get_db()
        
        # Obtener precio del producto
        product = db.execute('SELECT precio FROM products WHERE id = ?', 
                              (producto_id,), fetchone=True, param_types=['integer'])
        if not product:
            return False
        
        precio_unitario = product['precio']
        
        # Verificar si el producto ya está en el pedido
        item_existente = db.execute('''
            SELECT id, cantidad FROM invoice_items 
            WHERE invoice_id = ? AND product_id = ?
        ''', (invoice_id, producto_id), fetchone=True, param_types=['integer', 'integer'])
        
        if item_existente:
            # Actualizar cantidad si ya existe
            nueva_cantidad = item_existente['cantidad'] + cantidad
            db.execute('''
                UPDATE invoice_items 
                SET cantidad = ?, precio_unitario = ?
                WHERE id = ?
            ''', (nueva_cantidad, precio_unitario, item_existente['id']), 
            param_types=['integer', 'float', 'integer'])
        else:
            # Insertar nuevo item
            db.execute('''
                INSERT INTO invoice_items (invoice_id, product_id, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
            ''', (invoice_id, producto_id, cantidad, precio_unitario), 
            param_types=['integer', 'integer', 'integer', 'float'])

        # Actualizar total del pedido
        db.execute('''
            UPDATE invoices 
            SET total = (
                SELECT SUM(cantidad * precio_unitario) 
                FROM invoice_items 
                WHERE invoice_id = ?
            )
            WHERE id = ?
        ''', (invoice_id, invoice_id), param_types=['integer', 'integer'])
        
        return True
    
    except DatabaseError as e:
        logger.error(
            "Error al agregar producto al invoice",
            extra={"invoice_id": invoice_id, "producto_id": producto_id, "cantidad": cantidad, "error": str(e)},
        )
        return False


def obtener_pedido_actual_o_crear_nuevo(customer_id):
    pedido_id = obtener_pedido_actual(customer_id)

    if not pedido_id:
        pedido_id = crear_pedido(customer_id)
    return pedido_id


def obtener_pedido_actual(customer_id) -> dict | None:
    """Obtiene el pedido pendiente del cliente"""
    try:
        db = get_db()

        #obtener el id del customer dado su customer_id que es el id de telegram
        customer = db.execute('SELECT id FROM customers WHERE customer_id = ?', 
                              (customer_id,), fetchone=True, param_types=['text'])
        if not customer:
            logger.warning("Cliente no encontrado al obtener pedido actual", extra={"customer_id": customer_id})
            return None
        
        customer_id = customer['id']
        logger.debug("Obteniendo pedido actual", extra={"customer_id": customer_id})
        pedido = db.execute('''
            SELECT p.id FROM invoices p
            LEFT JOIN invoice_items pi ON p.id = pi.invoice_id
            WHERE p.customer_id = ? AND p.estado = 'pendiente'
            GROUP BY p.id
            ORDER BY p.fecha DESC
            LIMIT 1
        ''', (customer_id,), fetchone=True, param_types=['text'])
        logger.debug("Pedido actual obtenido", extra={"customer_id": customer_id, "pedido_encontrado": bool(pedido)})
        return pedido['id'] if pedido else None
    
    except DatabaseError as e:
        logger.error("Error al obtener pedido actual para customer_id %s: %s", customer_id, e)
        return None

#agregar informacion de retorno
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
        ''', (invoice_id,), fetchone=True, param_types=['integer'])
        # Items del pedido
        items: list | None = db.execute('''
            SELECT pr.id, pr.nombre, pi.cantidad, pi.precio_unitario, 
                   (pi.cantidad * pi.precio_unitario) as subtotal
            FROM invoice_items pi
            JOIN products pr ON pi.product_id = pr.id
            WHERE pi.invoice_id = ?
            ORDER BY pr.nombre
        ''', (invoice_id,), fetchall=True, param_types=['integer'])
       
        return info_pedido, items
    
    except DatabaseError as e:
        logger.error("Error al obtener detalle de invoice %s: %s", invoice_id, e)
        return None, []


def obtener_comprobante_pedido(invoice_id):
    """Obtiene los datos necesarios para generar un comprobante PDF."""
    try:
        db = get_db()
        info_pedido = db.execute('''
            SELECT i.id, i.fecha, i.estado, i.total,
                   c.name, c.email, c.address, c.company, c.customer_id,
                   p.mp_payment_id, p.estado AS payment_estado,
                   p.fecha_aprobacion, p.concepto, p.monto
            FROM invoices i
            JOIN customers c ON i.customer_id = c.id
            LEFT JOIN payments p ON p.invoice_id = i.id
            WHERE i.id = ?
            ORDER BY p.fecha_creacion DESC
            LIMIT 1
        ''', (invoice_id,), fetchone=True, param_types=['integer'])

        items: list | None = db.execute('''
            SELECT pr.id, pr.nombre, pr.descripcion, pi.cantidad,
                   pi.precio_unitario, (pi.cantidad * pi.precio_unitario) as subtotal
            FROM invoice_items pi
            JOIN products pr ON pi.product_id = pr.id
            WHERE pi.invoice_id = ?
            ORDER BY pr.nombre
        ''', (invoice_id,), fetchall=True, param_types=['integer'])

        return info_pedido, items or []

    except DatabaseError as e:
        logger.error("Error al obtener datos de comprobante para invoice %s: %s", invoice_id, e)
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
            ''', (invoice_id, producto_id), param_types=['integer', 'integer'])
        logger.info("Producto eliminado del pedido", extra={"invoice_id": invoice_id, "producto_id": producto_id})
        # 2. Actualizar total del invoice
        db.execute('''
            UPDATE invoices 
            SET total = COALESCE((
                SELECT SUM(cantidad * precio_unitario)
                FROM invoice_items 
                WHERE invoice_id = ?
            ), 0)
            WHERE id = ?
            ''', (invoice_id, invoice_id), param_types=['integer', 'integer'])
        logger.debug("Total de pedido actualizado tras eliminar producto", extra={"invoice_id": invoice_id, "producto_id": producto_id})
        
        # 3. Verificar si el invoice quedó vacío
        #count = db.execute('SELECT COUNT(*) as cant_items FROM invoice_items WHERE invoice_id = ?', 
        #                   (invoice_id,),fetchone=True, param_types=['integer'])
        
        #si el count es 0, eliminar el invoice para evitar pedidos vacíos
        #if count is not None:
        db.execute('DELETE FROM invoices WHERE id = ? AND (SELECT COUNT(*) FROM invoice_items WHERE invoice_id = ?) = 0',
                       (invoice_id, invoice_id), param_types=['integer', 'integer'])
            
        #if count['cant_items'] == 0:
            # Eliminar invoice vacío
        #    db.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,), 
        #               param_types=['integer'])
        #    print(f"Pedido {invoice_id} eliminado por estar vacío")

        return True
    
    except DatabaseError as e:
        logger.error("Error en BD al eliminar producto %s del invoice %s: %s", producto_id, invoice_id, e)
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
        ''', (nueva_cantidad, invoice_id, producto_id), 
        param_types=['integer', 'integer', 'integer'])
        
        # 2. Actualizar precio unitario (por si cambió)
        db.execute('''
            UPDATE invoice_items 
            SET precio_unitario = (
                SELECT precio FROM products WHERE id = ?
            )
            WHERE invoice_id = ? AND product_id = ?
        ''', (producto_id, invoice_id, producto_id), param_types=['integer', 'integer', 'integer'])
        
        # 3. Actualizar total del invoice
        db.execute('''
            UPDATE invoices 
            SET total = (
                SELECT SUM(cantidad * precio_unitario)
                FROM invoice_items 
                WHERE invoice_id = ?
            )
            WHERE id = ?
        ''', (invoice_id, invoice_id), param_types=['integer', 'integer'])
        
        return True
    except DatabaseError as e:
        logger.error(
            "Error actualizando cantidad de producto",
            extra={"invoice_id": invoice_id, "producto_id": producto_id, "nueva_cantidad": nueva_cantidad, "error": str(e)},
        )
        return False
    

def verificar_stock_disponible(producto_id):
    """
    Verifica el stock disponible de un producto.
    Retorna None si no hay control de stock.
    """
    try:
        db = get_db()
        resultado = db.execute(
            '''
                SELECT stock_actual, stock_reservado
                FROM product_inventory
                WHERE product_id = ?
            ''',
            (producto_id,),
            fetchone=True,
            param_types=['integer'],
        )
        if not resultado:
            return None

        stock_actual = resultado['stock_actual'] or 0
        stock_reservado = resultado['stock_reservado'] or 0
        return max(int(stock_actual) - int(stock_reservado), 0)

    except DatabaseError as e:
        logger.error("Error al verificar stock disponible para producto %s: %s", producto_id, e)
        return None


def obtener_cantidad_producto(invoice_id, producto_id):
    """Obtiene la cantidad actual de un producto en un invoice"""
    try:
        db = get_db()
        resultado = db.execute('''
            SELECT cantidad FROM invoice_items 
            WHERE invoice_id = ? AND product_id = ?
        ''', (invoice_id, producto_id), fetchone=True, param_types=['integer', 'integer'])
        return resultado['cantidad'] if resultado else None
    
    except DatabaseError as e:
        logger.error("Error al obtener cantidad de producto %s en invoice %s: %s", producto_id, invoice_id, e)
        return None


def finalizar_pedido_db(invoice_id):
    """Marca un invoice como completado"""
    try:
        db = get_db()
        db.execute('''
            UPDATE invoices 
            SET estado = 'completado' 
            WHERE id = ?
        ''', (invoice_id,), param_types=['integer'])
        
    except DatabaseError as e:
        logger.error("Error al finalizar invoice %s: %s", invoice_id, e)


#======================= FUNCIONES DE PAGOS ======================

def guardar_pago(telegram_id, mp_payment_id, invoice_id, monto, concepto, estado='pendiente'):
    """Guarda el pago en base de datos"""
    try:
        db = get_db()
        pago_id = db.execute('''
            INSERT INTO payments (telegram_id, mp_payment_id, invoice_id, monto, concepto, estado)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (telegram_id, mp_payment_id, invoice_id, monto, concepto, estado), 
            param_types=['integer', 'string', 'integer', 'float', 'string', 'string'])
        logger.info(
            "Pago guardado en BD",
            extra={"telegram_id": telegram_id, "invoice_id": invoice_id, "mp_payment_id": mp_payment_id, "estado": estado},
        )
        
        return pago_id
    except DatabaseError as e:
        logger.error("Error al guardar pago %s para invoice %s: %s", mp_payment_id, invoice_id, e)
        return None


def actualizar_pago(payment_id, invoice_id, estado, monto, fecha_aprobacion=None):
    """Actualiza el estado del pago en nuestra BD"""
    try:
        db = get_db()
        updated_rows = db.execute('''
            UPDATE payments 
            SET estado = ?, fecha_aprobacion = ?, mp_payment_id = ?
            WHERE invoice_id = ? AND monto = ?
        ''', (estado, fecha_aprobacion, payment_id, invoice_id, monto), 
            param_types=['string', 'datetime', 'string', 'integer', 'float'])

        if isinstance(updated_rows, int) and updated_rows == 0:
            logger.warning(
                "Pago no actualizado: 0 filas afectadas",
                extra={
                    "payment_id": payment_id,
                    "invoice_id": invoice_id,
                    "estado": estado,
                    "monto": monto,
                    "fecha_aprobacion": fecha_aprobacion,
                },
            )
        else:
            logger.info(
                "Pago actualizado en BD",
                extra={
                    "payment_id": payment_id,
                    "invoice_id": invoice_id,
                    "estado": estado,
                    "updated_rows": updated_rows,
                },
            )

        return updated_rows

    except DatabaseError as e:
        logger.error("Error al actualizar pago %s de invoice %s: %s", payment_id, invoice_id, e)
        return 0


def buscar_ultimo_pago_usuario(customer_id):
    """Busca el último pago realizado por un cliente"""
    try:
        db = get_db()
        payment = db.execute('''
            SELECT monto, concepto, estado, fecha_creacion, fecha_aprobacion, mp_payment_id FROM payments 
            WHERE telegram_id = ? 
            ORDER BY fecha_creacion DESC 
            LIMIT 1
        ''', (customer_id,), fetchone=True, param_types=['integer'])
        return payment
    
    except DatabaseError as e:
        logger.error("Error al buscar ultimo pago del cliente %s: %s", customer_id, e)
        return None


def documento_ya_enviado(invoice_id, document_type, delivery_channel, recipient_target):
    """Indica si ya se registró el envío exitoso de un documento."""
    try:
        db = get_db()
        normalized_channel = str(delivery_channel or '').strip().lower()
        normalized_target = str(recipient_target or '').strip()
        if normalized_channel == 'email':
            normalized_target = normalized_target.lower()

        resultado = db.execute('''
            SELECT 1 FROM sent_documents
            WHERE invoice_id = ?
              AND document_type = ?
              AND delivery_channel = ?
              AND recipient_target = ?
              AND status = 'sent'
            LIMIT 1
        ''', (invoice_id, document_type, normalized_channel, normalized_target), fetchone=True,
            param_types=['integer', 'string', 'string', 'string'])
        
        encontrado = resultado is not None
        logger.info(
            "Consulta de documento ya enviado",
            extra={
                "invoice_id": invoice_id,
                "document_type": document_type,
                "delivery_channel": normalized_channel,
                "recipient_target": normalized_target,
                "encontrado": encontrado,
            },
        )
        return encontrado

    except (DatabaseError, RuntimeError) as e:
        logger.error(
            "Error al consultar documentos enviados",
            extra={"invoice_id": invoice_id, "document_type": document_type, "delivery_channel": delivery_channel, "recipient_target": recipient_target, "error": str(e)},
        )
        return False


def registrar_documento_enviado(invoice_id, document_type, delivery_channel, recipient_target, file_name, payment_id=None, status='sent', error_message=None):
    """Registra o actualiza un envío documental."""
    try:
        db = get_db()
        normalized_channel = str(delivery_channel or '').strip().lower()
        normalized_target = str(recipient_target or '').strip()
        if normalized_channel == 'email':
            normalized_target = normalized_target.lower()

        existing = db.execute(
            '''
                SELECT id
                FROM sent_documents
                WHERE document_type = ?
                  AND invoice_id = ?
                  AND delivery_channel = ?
                  AND recipient_target = ?
                LIMIT 1
            ''', (document_type, invoice_id, normalized_channel, normalized_target), fetchone=True, param_types=['string', 'integer', 'string', 'string'])

        if existing:
            existing_id = existing.get('id') if isinstance(existing, dict) else existing[0]
            db.execute(
                '''
                    UPDATE sent_documents
                    SET file_name = ?,
                        payment_id = ?,
                        sent_at = CURRENT_TIMESTAMP,
                        status = ?,
                        error_message = ?
                    WHERE id = ?
                ''', (file_name, payment_id, status, error_message, existing_id), fetchone=False,
                param_types=['string', 'string', 'string', 'string', 'integer'])

        else:
            db.execute(
                '''
                    INSERT INTO sent_documents (
                        document_type, invoice_id, delivery_channel, recipient_target, file_name, payment_id, status, error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (document_type, invoice_id, normalized_channel, normalized_target, file_name, payment_id, status, error_message), fetchone=False,
                param_types=['string', 'integer', 'string', 'string', 'string', 'string', 'string', 'string'])

        logger.info(
            "Documento enviado registrado/actualizado",
            extra={
                "invoice_id": invoice_id,
                "document_type": document_type,
                "delivery_channel": normalized_channel,
                "status": status,
                "recipient_target": normalized_target,
                "payment_id": payment_id,
            },
        )

        return True

    except (DatabaseError, RuntimeError) as e:
        logger.error(
            "Error al registrar documento enviado",
            extra={"invoice_id": invoice_id, "document_type": document_type, "delivery_channel": delivery_channel, "recipient_target": recipient_target, "status": status, "error": str(e)},
        )
        return False


def pago_ya_procesado(mp_payment_id: str) -> bool:
    """
    Verifica si un pago de Mercado Pago ya fue procesado (estado != 'pendiente').
    
    Esto evita que se procese el mismo pago múltiples veces si llegan dos webhooks:
    1. topic='payment' (procesar_notificacion_pago)
    2. topic='merchant_order' (procesar_merchant_order -> procesar_pago)
    
    Args:
        mp_payment_id: ID del pago en Mercado Pago
        
    Returns:
        True si el pago ya existe con estado aprobado/rechazado/etc (no pendiente)
        False si no existe la controla o si está en pendiente
    """
    try:
        db = get_db()
        result = db.execute(
            '''SELECT estado FROM payments WHERE mp_payment_id = ?''',
            (mp_payment_id,), param_types=['string'], fetchone=True
        )
        
        if result:
            estado = result.get('estado') if isinstance(result, dict) else result[0]
            ya_procesado = estado != 'pendiente'
            logger.info(
                "Verificación de pago ya procesado",
                extra={
                    "mp_payment_id": mp_payment_id,
                    "estado": estado,
                    "ya_procesado": ya_procesado,
                },
            )
            return ya_procesado
        else:
            logger.info(
                "Pago no encontrado en BD",
                extra={"mp_payment_id": mp_payment_id},
            )
            return False
            
    except DatabaseError as e:
        logger.error(
            "Error verificando si pago ya fue procesado",
            extra={"mp_payment_id": mp_payment_id, "error": str(e)},
        )
        return False

    
    
    
    

