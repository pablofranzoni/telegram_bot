from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from utils.database import (
    registrar_cliente,
    get_categorias,
    get_productos_por_categoria,
    get_producto_por_id,
    crear_pedido,
    agregar_producto_a_pedido,
    obtener_pedido_actual,
    obtener_detalle_pedido,
    eliminar_producto_de_db,
    actualizar_cantidad_producto,
    verificar_stock_disponible,
    obtener_cantidad_producto,
    finalizar_pedido,
    eliminar_todos_productos_de_pedido
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Inicializa el bot y registra al cliente"""
    user = update.effective_user
    registrar_cliente(user.id, user.first_name, user.last_name, user.username)
    
    # Teclado principal
    keyboard = [
        ['🛍️ Ver Productos', '🛒 Mi Carrito'],
        ['📋 Mis Pedidos', 'ℹ️ Ayuda']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f'¡Bienvenido {user.first_name}! 🍕\n\n'
        '¿Qué te apetece hoy?',
        reply_markup=reply_markup
    )


async def ver_productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Obtener el mensaje de donde sea que venga
    if update.callback_query:
        mensaje = update.callback_query.message
        await update.callback_query.answer()
    else:
        mensaje = update.message

    """Muestra las categorías de productos disponibles"""
    categorias = get_categorias()
    
    if not categorias:
        await mensaje.reply_text("No hay productos disponibles en este momento.")
        return
    
    # Crear botones inline para cada categoría
    keyboard = []
    for categoria in categorias:
        keyboard.append([InlineKeyboardButton(f"📂 {categoria.capitalize()}", callback_data=f'cat_{categoria}')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await mensaje.reply_text(
        "Selecciona una categoría:",
        reply_markup=reply_markup
    )


async def mostrar_productos_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra productos de una categoría específica"""
    query = update.callback_query
    await query.answer()
    
    categoria = query.data.replace('cat_', '')
    productos = get_productos_por_categoria(categoria)
    
    if not productos:
        await query.edit_message_text(f"No hay productos en la categoría {categoria}")
        return
    
    # Crear mensaje con productos
    mensaje = f"*{categoria.capitalize()}* 🍽️\n\n"
    keyboard = []
    
    for producto in productos:
        producto_id, nombre, descripcion, precio = producto
        mensaje += f"*{nombre}*\n"
        mensaje += f"_{descripcion}_\n"
        mensaje += f"💰 ${precio:.2f}\n"
        
        # Botones para agregar al carrito
        keyboard.append([
            InlineKeyboardButton(f"➖", callback_data=f'rem_{producto_id}'),
            InlineKeyboardButton(f"🛒 {nombre[:10]}...", callback_data=f'info_{producto_id}'),
            InlineKeyboardButton(f"➕", callback_data=f'add_{producto_id}')
        ])
        mensaje += "─" * 20 + "\n"
    
    # Botón para ver carrito
    keyboard.append([InlineKeyboardButton("🛒 Ver mi carrito", callback_data='ver_carrito')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def manejar_seleccion_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de productos (agregar/quitar)"""
    query = update.callback_query
    await query.answer()
    
    cliente_id = query.from_user.id
    data = query.data
    
    # Verificar si el cliente tiene un pedido activo
    pedido_actual = obtener_pedido_actual(cliente_id)
    
    if data.startswith('add_'):
        producto_id = int(data.replace('add_', ''))
        
        if not pedido_actual:
            pedido_id = crear_pedido(cliente_id)
        else:
            pedido_id = pedido_actual[0]
        
        if agregar_producto_a_pedido(pedido_id, producto_id, 1):
            await query.answer("✅ Producto agregado al carrito")
            #await query.edit_message_text(
            #    text=f"✅ Producto agregado al carrito\n\n{query.message.text}",
            #    reply_markup=query.message.reply_markup
            #)
        else:
            await query.answer("❌ Error al agregar producto")
    
    elif data.startswith('rem_'):
        producto_id = int(data.replace('rem_', ''))
        
        if pedido_actual:
            await disminuir_cantidad(query, context, producto_id)
        else:
            await query.answer("No tienes productos en el carrito")
    
    elif data.startswith('info_'):
        producto_id = int(data.replace('info_', ''))
        producto = get_producto_por_id(producto_id)
        
        if producto:
            producto_id, nombre, descripcion, precio = producto
            mensaje = f"*{nombre}*\n\n"
            mensaje += f"_{descripcion}_\n\n"
            mensaje += f"*Precio:* ${precio:.2f}\n\n"
            mensaje += "¿Quieres agregarlo al carrito?"
            
            keyboard = [
                [InlineKeyboardButton("➖ 1", callback_data=f'rem_{producto_id}'),
                InlineKeyboardButton("➕ 1", callback_data=f'add_{producto_id}')],
                [InlineKeyboardButton("📋 Ver todos", callback_data='volver_categorias')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                mensaje,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )


async def manejar_botones_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los botones del carrito"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('rem_'):
        producto_id = int(data.replace('rem_', ''))
        # Lógica para disminuir cantidad
        await disminuir_cantidad(query, context, producto_id)
        
    elif data.startswith('add_'):
        producto_id = int(data.replace('add_', ''))
        # Lógica para aumentar cantidad
        await aumentar_cantidad(query, context, producto_id)
        
    elif data.startswith('del_'):
        producto_id = int(data.replace('del_', ''))
        # Lógica para eliminar producto
        await eliminar_producto(query, context, producto_id)

    elif data.startswith('info_'): ##ACA
        producto_id = int(data.replace('info_', ''))
        # Lógica para mostrar info del producto
        await mostrar_info_producto(query, context, producto_id)
        
    elif data == 'vaciar_todo':
        # Vaciar todo el carrito
        await vaciar_carrito(query, context)
        
    elif data == 'ver_productos':
        # Volver a ver productos
        await ver_productos(update, context)
        
    elif data.startswith('finalizar_'):
        #pedido_id = int(data.replace('finalizar_', ''))
        # Finalizar pedido
        #await finalizar_pedido_handler(query, context, pedido_id)
        await finalizar_pedido_handler(update, context)
        
    elif data == 'volver_carrito':
        # Volver al carrito
        await ver_carrito(update, context)


async def disminuir_cantidad(query, context, producto_id, cantidad=1):
    """Disminuye la cantidad de un producto en el carrito"""
    usuario_id = query.from_user.id
    
    # Obtener pedido actual
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        await query.answer("❌ No tienes productos en el carrito")
        return
    
    pedido_id = pedido_actual[0]
    
    # Verificar si el producto ya está en el carrito
    cantidad_actual = obtener_cantidad_producto(pedido_id, producto_id)
    
    if cantidad_actual is None or cantidad_actual <= 0:
        await query.answer("❌ No tienes este producto en el carrito")
        return
    
    nueva_cantidad = max(cantidad_actual - cantidad, 0)
    
    # Actualizar cantidad
    exito = actualizar_cantidad_producto(pedido_id, producto_id, nueva_cantidad)
    
    if exito:
        # Obtener nombre para el mensaje
        producto_info = get_producto_por_id(producto_id)
        producto_nombre = producto_info[1] if producto_info else "Producto"
        
        await query.answer(f"➖ {producto_nombre}: {cantidad_actual} → {nueva_cantidad}")
        
        # Actualizar vista del carrito
        await actualizar_vista_carrito(query, context, usuario_id)
    else:
        await query.answer("❌ Error al actualizar cantidad")


async def mostrar_info_producto(query, context, producto_id):
    """Muestra información detallada del producto"""
    producto = get_producto_por_id(producto_id)
    
    if not producto:
        await query.answer("❌ Producto no encontrado")
        return
    
    producto_id, nombre, descripcion, precio = producto
    mensaje = f"*{nombre}*\n\n"
    mensaje += f"_{descripcion}_\n\n"
    mensaje += f"*Precio:* ${precio:.2f}\n\n"
    mensaje += "¿Quieres agregarlo al carrito?"
    
    keyboard = [
        [InlineKeyboardButton("➖ 1", callback_data=f'rem_{producto_id}'),
         InlineKeyboardButton("➕ 1", callback_data=f'add_{producto_id}')],
        [InlineKeyboardButton("📋 Ver todos", callback_data='volver_categorias')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def aumentar_cantidad(query, context, producto_id, cantidad=1):
    """
    Aumenta la cantidad de un producto en el carrito.
    
    Args:
        query: CallbackQuery de Telegram
        context: Contexto del bot
        producto_id: ID del producto
        cantidad: Cantidad a aumentar (default: 1)
    """
    
    usuario_id = query.from_user.id
    
    # Obtener pedido actual
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        await query.answer("❌ No tienes productos en el carrito")
        return
    
    pedido_id = pedido_actual[0]
    
    # Verificar si el producto ya está en el carrito
    cantidad_actual = obtener_cantidad_producto(pedido_id, producto_id)
    
    if cantidad_actual is None:
        # Producto no está en el carrito, agregarlo
        await agregar_producto_al_carrito(query, context, producto_id, cantidad)
        return
    
    # Calcular nueva cantidad
    nueva_cantidad = cantidad_actual + cantidad
    
    # Verificar límite de stock (si tienes control de inventario)
    stock_disponible = verificar_stock_disponible(producto_id)
    
    if stock_disponible is not None and nueva_cantidad > stock_disponible:
        await query.answer(f"❌ Stock máximo: {stock_disponible} unidades")
        return
    
    # Actualizar cantidad
    exito = actualizar_cantidad_producto(pedido_id, producto_id, nueva_cantidad)
    
    if exito:
        # Obtener nombre para el mensaje
        producto_info = get_producto_por_id(producto_id)
        producto_nombre = producto_info[1] if producto_info else "Producto"
        
        await query.answer(f"➕ {producto_nombre}: {cantidad_actual} → {nueva_cantidad}")
        
        # Actualizar vista del carrito
        await actualizar_vista_carrito(query, context, usuario_id)
    else:
        await query.answer("❌ Error al actualizar cantidad")


async def agregar_producto_al_carrito(query, context, producto_id, cantidad=1):
    """Agrega un nuevo producto al carrito"""
    usuario_id = query.from_user.id
    
    # Obtener información del producto
    producto_info = get_producto_por_id(producto_id)
    
    if not producto_info:
        await query.answer("❌ Producto no encontrado")
        return
    
    # Obtener o crear pedido
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if pedido_actual:
        pedido_id = pedido_actual[0]
    else:
        # Crear nuevo pedido
        pedido_id = crear_pedido(usuario_id)
    
    # Agregar producto al pedido
    exito = agregar_producto_a_pedido(pedido_id, producto_id, cantidad)
    
    if exito:
        await query.answer(f"✅ {producto_info[1]} agregado al carrito")
        await actualizar_vista_carrito(query, context, usuario_id)
    else:
        await query.answer("❌ Error al agregar producto")


async def vaciar_carrito(query, context):
    """Elimina todos los productos del carrito actual."""
    usuario_id = query.from_user.id
    
    # Obtener pedido actual
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        await query.answer("❌ No tienes productos en el carrito")
        return
    
    pedido_id = pedido_actual[0]
    
    # Eliminar todos los productos del pedido
    try:
        eliminado = eliminar_todos_productos_de_pedido(pedido_id)
        
        if eliminado:
            await query.answer("🗑️ Carrito vaciado")
            await query.edit_message_text(
                "🛒 *Carrito vacío*\n\n¡Agrega productos para continuar!",
                parse_mode='Markdown'
            )
        else:
            await query.answer("❌ Error al vaciar el carrito")
            
    except Exception as e:
        print(f"Error al vaciar carrito: {e}")
        await query.answer("❌ Error interno al vaciar el carrito")


async def eliminar_producto(query, context, producto_id, con_confirmacion=True):
    """
    Elimina un producto del carrito.
    
    Args:
        query: CallbackQuery de Telegram
        context: Contexto del bot
        producto_id: ID del producto a eliminar
        con_confirmacion: Si mostrar diálogo de confirmación (default: True)
    """
    
    usuario_id = query.from_user.id
    
    # Obtener pedido actual del usuario
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        await query.answer("❌ No tienes productos en el carrito")
        return
    
    pedido_id = pedido_actual[0]
    
    # Obtener información del producto
    producto_info = get_producto_por_id(producto_id)
    
    if not producto_info:
        await query.answer("❌ Producto no encontrado")
        return
    
    producto_nombre = producto_info[1]  # Asumiendo que [1] es el nombre
    
    if con_confirmacion:
        # Mostrar diálogo de confirmación
        await mostrar_confirmacion_eliminar(query, producto_id, producto_nombre, pedido_id)
    else:
        # Eliminar directamente
        await ejecutar_eliminacion(query, context, producto_id, producto_nombre, pedido_id, usuario_id)


async def mostrar_confirmacion_eliminar(query, producto_id, producto_nombre, pedido_id):
    """Muestra diálogo de confirmación antes de eliminar"""
    
    # Crear teclado de confirmación
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Sí, eliminar", 
                callback_data=f'confirm_del_{producto_id}_{pedido_id}'
            ),
            InlineKeyboardButton(
                "❌ No, cancelar", 
                callback_data='cancel_del'
            )
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Editar mensaje para mostrar confirmación
    await query.edit_message_text(
        f"⚠️ *Confirmar eliminación*\n\n"
        f"¿Estás seguro de eliminar **{producto_nombre}** del carrito?\n\n"
        f"Esta acción no se puede deshacer.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def ejecutar_eliminacion(query, context, producto_id, producto_nombre, pedido_id, usuario_id):
    """Ejecuta la eliminación del producto"""
    
    try:
        # Eliminar de la base de datos
        eliminado = eliminar_producto_de_db(pedido_id, producto_id)
        
        if eliminado:
            # Notificar éxito
            await query.answer(f"✅ {producto_nombre} eliminado")
            
            # Verificar si el carrito quedó vacío
            nuevo_pedido = obtener_pedido_actual(usuario_id)
            
            if not nuevo_pedido:
                # Carrito vacío
                await query.edit_message_text(
                    "🛒 *Carrito vacío*\n\n"
                    f"**{producto_nombre}** fue eliminado y tu carrito ahora está vacío.\n\n"
                    "¡Agrega productos para continuar!",
                    parse_mode='Markdown'
                )
            else:
                # Actualizar vista del carrito
                await actualizar_vista_carrito(query, context, usuario_id)
                
        else:
            await query.answer("❌ Error al eliminar el producto")
            
    except Exception as e:
        print(f"Error en eliminación: {e}")
        await query.answer("❌ Error interno al eliminar")


async def actualizar_vista_carrito(query, context, usuario_id):
    """Actualiza la vista del carrito después de cambios"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    # Obtener pedido actualizado
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        # Esto no debería pasar si acabamos de eliminar, pero por si acaso
        await query.edit_message_text(
            "🛒 *Carrito vacío*\n\n¡Agrega productos!",
            parse_mode='Markdown'
        )
        return
    
    pedido_id, total, num_items = pedido_actual
    info_pedido, items = obtener_detalle_pedido(pedido_id)
    
    # Construir mensaje actualizado
    mensaje = "🛒 *Carrito Actualizado*\n\n"
    
    for producto_id, nombre, cantidad, precio_unitario, subtotal in items:
        mensaje += f"• **{nombre}**\n"
        mensaje += f"  Cantidad: `{cantidad}` × ${precio_unitario:.2f} = **${subtotal:.2f}**\n\n"
    
    mensaje += f"**Total: ${total:.2f}**\n"
    mensaje += f"**Items: {len(items)} productos**\n\n"
    
    # Crear teclado actualizado
    keyboard = []
    
    # Botones por producto
    for producto_id, nombre, cantidad, _, _ in items:
        nombre_corto = nombre[:10] + "..." if len(nombre) > 10 else nombre
        keyboard.append([
            InlineKeyboardButton(f"➖ {nombre_corto}", callback_data=f'rem_{producto_id}'),
            InlineKeyboardButton(f"➕ {nombre_corto}", callback_data=f'add_{producto_id}')
        ])
        keyboard.append([
            InlineKeyboardButton(f"🗑️ Eliminar {nombre_corto}", callback_data=f'del_{producto_id}')
        ])
    
    # Botones generales
    keyboard.append([
        InlineKeyboardButton("🛍️ Agregar más", callback_data='ver_productos'),
        InlineKeyboardButton("✅ Finalizar", callback_data=f'finalizar_{pedido_id}')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def manejar_confirmacion_eliminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la confirmación de eliminación"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('confirm_del_'):
        # Formato: confirm_del_123_456 (producto_id_pedido_id)
        partes = data.replace('confirm_del_', '').split('_')
        print("Partes confirmación eliminación:", partes)
        if len(partes) >= 2:
            producto_id = int(partes[0])
            pedido_id = int(partes[1])
            usuario_id = query.from_user.id
            
            # Obtener nombre del producto
            producto_info = get_producto_por_id(producto_id)
            
            if producto_info:
                await ejecutar_eliminacion(
                    query, context, producto_id, 
                    producto_info[1], pedido_id, usuario_id
                )
    
    elif data == 'cancel_del':
        # Cancelar eliminación - volver al carrito
        await query.answer("❌ Eliminación cancelada")
        await ver_carrito(update, context)


async def ver_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Versión con botones inline por producto"""
    
    # Determinar origen del mensaje
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return
    
    cliente_id = update.effective_user.id
    pedido_actual = obtener_pedido_actual(cliente_id)
    
    if not pedido_actual:
        await message.reply_text("🛒 Tu carrito está vacío.")
        return
    
    pedido_id = pedido_actual[0]
    detalle_pedido = obtener_detalle_pedido(pedido_id)
    
    if not detalle_pedido or not detalle_pedido[1]:
        await message.reply_text("🛒 Tu carrito está vacío.")
        return
    
    items = detalle_pedido[1]
    
    # Procesar todos los items primero
    items_detalle = []
    total = 0.0
    
    for producto_id, nombre_producto, cantidad, precio_unit, subtotal in items:
        producto_info = get_producto_por_id(producto_id)
        
        items_detalle.append({
            'id': producto_id,
            'nombre': nombre_producto,
            'cantidad': cantidad,
            'precio': precio_unit,
            'subtotal': subtotal,
            'descripcion': producto_info[2] if producto_info else ''
        })
        
        total += subtotal
    
    # Construir el mensaje DESPUÉS del bucle
    mensaje = "🛒 *Tu Carrito Actual*\n\n"
    mensaje += "═" * 35 + "\n\n"
    
    # Listar productos en el mensaje
    for idx, item in enumerate(items_detalle, 1):
        mensaje += f"**{idx}. {item['nombre']}**\n"
        
        if item['descripcion']:
            mensaje += f"   _{item['descripcion']}_\n"
        
        mensaje += f"   📦 Cantidad: `{item['cantidad']}` "
        mensaje += f"× ${item['precio']:.2f} "
        mensaje += f"= **${item['subtotal']:.2f}**\n\n"
    
    # Resumen total
    mensaje += "═" * 35 + "\n\n"
    mensaje += "📊 **RESUMEN DE COMPRA**\n\n"
    mensaje += f"• Productos: **{len(items_detalle)}**\n"
    mensaje += f"• Items totales: **{sum(item['cantidad'] for item in items_detalle)}**\n"
    mensaje += f"• Subtotal: **${total:.2f}**\n"
    
    impuestos = total * 0.21
    mensaje += f"• Impuestos (21%): **${impuestos:.2f}**\n"
    
    total_final = total + impuestos
    mensaje += f"• **TOTAL: ${total_final:.2f}**\n\n"
    
    # Crear teclado inline con botones POR PRODUCTO
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    
    keyboard = []
    
    # Botones para cada producto
    for idx, item in enumerate(items_detalle, 1):
        producto_id = item['id']
        nombre_corto = item['nombre'][:15] + "..." if len(item['nombre']) > 15 else item['nombre']
        
        # Fila con botones para este producto
        #keyboard.append([
        #    InlineKeyboardButton(f"➖ {nombre_corto}", callback_data=f'rem_{producto_id}'),
        #    InlineKeyboardButton(f"➕ {nombre_corto}", callback_data=f'add_{producto_id}')
        #])
        
        # Fila para eliminar
        keyboard.append([
            InlineKeyboardButton(f"❌ Eliminar {nombre_corto}", callback_data=f'del_{producto_id}')
        ])
        
        # Separador visual
        #if idx < len(items_detalle):
        #    keyboard.append([InlineKeyboardButton("─" * 20, callback_data='none')])
    
    # Botones generales del carrito
    keyboard.append([
        InlineKeyboardButton("🗑️ Vaciar todo", callback_data='vaciar_todo'),
        InlineKeyboardButton("🛍️ Agregar más", callback_data='ver_productos')
    ])
    
    keyboard.append([
        InlineKeyboardButton("✅ Finalizar pedido", callback_data=f'finalizar_{pedido_id}')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Enviar mensaje
    await message.reply_text(
        mensaje,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def finalizar_pedido_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finaliza el pedido actual"""
    query = update.callback_query
    await query.answer()
    
    pedido_id = int(query.data.replace('finalizar_', ''))
    finalizar_pedido(pedido_id)
    
    await query.edit_message_text(
        "✅ *¡Pedido confirmado!*\n\n"
        "Tu pedido ha sido registrado correctamente.\n"
        "Te contactaremos pronto para la entrega.\n\n"
        "¡Gracias por tu compra! 🎉",
        parse_mode='Markdown'
    )


async def mensajes_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del teclado principal"""
    texto = update.message.text
    user = update.effective_user
    
    if texto == '🛍️ Ver Productos':
        await ver_productos(update, context)
    
    elif texto == '🛒 Mi Carrito':
        # Simulamos que es un callback query
        query_data = type('obj', (object,), {'data': 'ver_carrito', 'from_user': user})()
        #update.callback_query = query_data
        await ver_carrito(update, context)
    
    elif texto == '📋 Mis Pedidos':
        await update.message.reply_text(
            "📊 *Historial de Pedidos*\n\n"
            "Función en desarrollo... Pronto podrás ver todos tus pedidos anteriores.",
            parse_mode='Markdown'
        )
    
    elif texto == 'ℹ️ Ayuda':
        await update.message.reply_text(
            "*Ayuda del Bot de Pedidos*\n\n"
            "• *🛍️ Ver Productos*: Explora nuestro menú\n"
            "• *🛒 Mi Carrito*: Revisa tu pedido actual\n"
            "• *📋 Mis Pedidos*: Historial de compras\n\n"
            "Para agregar productos, selecciona una categoría y usa los botones ➕/➖",
            parse_mode='Markdown'
        )
