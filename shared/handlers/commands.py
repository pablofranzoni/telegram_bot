import random
import string
import re
import os
import logging

from telegram import (
    ReplyKeyboardRemove,
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup,
)
from telegram.ext import ContextTypes
from telegram.ext import ConversationHandler

from utils.constants import EstadoConversacion

from utils.database import (
    buscar_ultimo_pago_usuario,
    guardar_pago,
    obtener_cliente,
    guardar_cliente,
    obtener_categorias_db,
    obtener_productos_por_categoria,
    obtener_producto_por_id,
    crear_pedido,
    agregar_producto,
    obtener_pedido_actual,
    obtener_detalle_pedido,
    quitar_producto_del_pedido,
    actualizar_cantidad_producto,
    verificar_stock_disponible,
    obtener_cantidad_producto,
    finalizar_pedido_db,
    vaciar_pedido_db
)
from utils.mpago import MercadoPagoSimple

MP_ACCESS_TOKEN = os.getenv('MP_ACCESS_TOKEN')

def es_email_valido(email):
    """Valida formato de email"""
    if not email or len(email) > 100:
        return False
    
    # Patrón básico de email
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(patron, email) is not None


async def cmd_inicio_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - verifica si tiene email"""
    usuario = update.effective_user
    telegram_id = usuario.id
    
    # Buscar si ya tiene email
    datos_cliente = obtener_cliente(telegram_id)
    
    if datos_cliente and datos_cliente['email']:
        # Ya tiene email, mostrar menú principal
        await mostrar_menu_principal(update, context, usuario.first_name)
        return ConversationHandler.END
    else:
        # No tiene email, solicitarlo
        await update.message.reply_text(
            f"¡Hola {usuario.first_name}! 👋\n\n"
            "Para poder procesar tus pedidos, necesito tu email.\n"
            "Por favor, ingrésalo:",
            reply_markup=ReplyKeyboardRemove()  # Quitar teclado temporalmente
        )
        return EstadoConversacion.ESPERANDO_EMAIL.value
    

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - verifica si tiene email"""
    usuario = update.effective_user
    telegram_id = usuario.id
    
    # Buscar si ya tiene email
    datos_cliente = obtener_cliente(telegram_id)
    
    if datos_cliente and datos_cliente['email']:
        # Ya tiene email, mostrar menú principal
        await mostrar_menu_principal(update, context, usuario.first_name)
    else:
        # No tiene email, solicitarlo
        await update.message.reply_text(
            f"¡Hola {usuario.first_name}! 👋\n\n"
            "Para poder procesar tus pedidos, necesito tu email.\n"
            "Por favor, ingrésalo:",
            reply_markup=ReplyKeyboardRemove()  # Quitar teclado temporalmente
        )
        return EstadoConversacion.ESPERANDO_EMAIL.value


async def ver_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra mensaje de ayuda"""
    mensaje = (
        "📋 *Ayuda - Comandos disponibles:*\n\n"
        "• /start - Iniciar conversación y verificar email\n"
        "• /ver_productos - Ver categorías y productos disponibles\n"
        "• /carrito - Ver tu pedido actual\n"
        "• /checkout - Finalizar compra\n"
        "• /mis_pedidos - Ver historial de pedidos\n"
        "• /estado - Ver estado del último pago\n"
        "\nSi necesitas asistencia adicional, no dudes en contactarnos."
    )
    return mensaje
    
def generar_codigo_verificacion():
    """Genera un código de 6 dígitos"""
     # Por ahora solo imprimimos en consola
    codigo = ''.join(random.choices(string.digits, k=6))
    print(f"📧 CÓDIGO ENVIADO: {codigo}")
    print("⚠️ EN PRODUCCIÓN: Implementar envío real de email")
    return codigo


async def recibir_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el email y envía código de verificación"""
    email = update.message.text.strip()
    
    if not es_email_valido(email):
        await update.message.reply_text("❌ Email inválido. Intenta nuevamente:")
        return EstadoConversacion.ESPERANDO_EMAIL.value
    
    # Generar código de verificación
    codigo = generar_codigo_verificacion()
    
    # Guardar email y código temporalmente
    context.user_data['email_temp'] = email
    context.user_data['codigo_verificacion'] = codigo
    
    # Aquí enviarías el código por email (simulado)
    print(f"📧 Código enviado a {email}: {codigo}")  # En producción, enviar email real
    
    await update.message.reply_text(
        f"📧 Hemos enviado un código de verificación a **{email}**\n\n"
        f"Por favor, ingresa el código de 6 dígitos que recibiste:",
        parse_mode='Markdown'
    )
    
    return EstadoConversacion.ESPERANDO_CODIGO.value


async def verificar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica el código ingresado"""
    codigo_ingresado = update.message.text.strip()
    codigo_correcto = context.user_data.get('codigo_verificacion')
    
    if codigo_ingresado == codigo_correcto:
        # Código correcto, guardar email
        usuario_id = update.effective_user.id
        email = context.user_data.get('email_temp')
        
        #guardar_email(usuario_id, email)
        guardar_cliente(usuario_id, update.effective_user.first_name, update.effective_user.last_name, update.effective_user.username, email=email)
    
        context.user_data.clear()
        
        await update.message.reply_text(
            "✅ **¡Email verificado correctamente!**",
            parse_mode='Markdown',
            reply_markup=reply_markup_principal()
        )
        
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Código incorrecto. Intenta nuevamente:\n"
            "(o escribe /cancelar para abortar)"
        )
        return EstadoConversacion.ESPERANDO_CODIGO.value


async def cancelar_ingreso_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la operación"""
    await update.message.reply_text(
        "Operación cancelada. Usa /start cuando quieras intentar nuevamente.",
        reply_markup=reply_markup_principal()
    )
    return ConversationHandler.END


def reply_markup_principal():
    """Teclado principal"""
    keyboard = [
        ['🛍️ Ver Productos', '🛒 Mi Pedido'],
        ['📋 Mis Pedidos', 'ℹ️ Ayuda']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def mostrar_menu_principal(update: Update, context: ContextTypes.DEFAULT_TYPE, nombre=None):
    """Muestra el menú principal"""
    mensaje = f"¡Bienvenido{ ' ' + nombre if nombre else ''}!\n"
    mensaje += "¿Qué deseas hacer hoy?"
    
    await update.message.reply_text(
        mensaje,
        reply_markup=reply_markup_principal()
    )


async def reiniciar_desde_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Este fallback se llama cuando /start se envía DURANTE una conversación"""
    await update.message.reply_text("Reiniciando la conversación...")
    # Terminamos la conversación actual y comenzamos una nueva
    return await start(update, context)  # Inicia el estado NOMBRE


async def obtener_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Obtener el mensaje de donde sea que venga
    if update.callback_query:
        mensaje = update.callback_query.message
        await update.callback_query.answer()
    else:
        mensaje = update.message

    """Muestra las categorías de productos disponibles para selección por letra"""
    categorias = obtener_categorias_db()
    
    if not categorias:
        await mensaje.reply_text("No hay productos disponibles en este momento.")
        return ConversationHandler.END
    
    # Asignar una letra a cada categoría (A, B, C, ...)
    letras = [chr(65 + i) for i in range(len(categorias))]  # 65 es el código ASCII de 'A'
    
    # Guardar las categorías en context.user_data para usarlas después
    context.user_data['categorias'] = categorias
    context.user_data['letras'] = letras
    
    # Crear el mensaje con las opciones
    opciones_texto = "Selecciona una categoría escribiendo la letra correspondiente:\n\n"
    for letra, categoria in zip(letras, categorias):
        opciones_texto += f"*{letra}) {categoria.capitalize()}*\n"
    
    opciones_texto += "\nEjemplo: Escribe 'A' para ver los productos de la primera categoría"
    
    await mensaje.reply_text(opciones_texto, parse_mode='Markdown')

    return EstadoConversacion.ESPERANDO_CATEGORIA.value


async def seleccionar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la selección de categoría por letra"""
    mensaje = update.message
    texto = mensaje.text.strip().upper()
    
    # Opción para cancelar
    if texto == "0":
        await mensaje.reply_text("Operación cancelada.")
        # Limpiar datos
        context.user_data.clear()
        return ConversationHandler.END
    
    # Verificar si hay categorías guardadas
    if 'categorias' not in context.user_data or 'letras' not in context.user_data:
        await mensaje.reply_text("Por favor, primero usa /ver_productos para ver las categorías disponibles.")
        return ConversationHandler.END
    
    categorias = context.user_data['categorias']
    letras = context.user_data['letras']
    
    # Verificar si el texto es una letra válida
    if texto in letras:
        indice = letras.index(texto)
        categoria_seleccionada = categorias[indice]
        
        # Guardar la categoría seleccionada
        context.user_data['categoria_seleccionada'] = categoria_seleccionada
        
        # Limpiar datos de categorías (ya no los necesitamos)
        del context.user_data['categorias']
        del context.user_data['letras']
        
        # Mostrar productos de la categoría
        await mostrar_productos_categoria_texto(update, context)
        
        # Siguiente estado: seleccionar producto
        return EstadoConversacion.ESPERANDO_PRODUCTO.value
        
    else:
        # Mostrar mensaje de error con las opciones disponibles
        opciones = ", ".join(letras)
        await mensaje.reply_text(
            f"❌ Opción no válida. Por favor, escribe una de estas letras: {opciones}\n"
            "O escribe 0 para cancelar"
        )
        # Permanecer en el mismo estado
        return EstadoConversacion.ESPERANDO_CATEGORIA.value


async def mostrar_productos_categoria_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra productos de una categoría usando letras"""
    
    categoria = context.user_data['categoria_seleccionada']
    productos = obtener_productos_por_categoria(categoria)
    
    if not productos:
        await update.message.reply_text(f"No hay productos en la categoría {categoria}")
        # Volver a categorías
        await obtener_categorias(update, context)
        return
    
    # Asignar letras a productos
    opciones = [chr(65 + i) for i in range(len(productos))]
    
    # Guardar para el siguiente estado
    context.user_data['productos_actuales'] = productos
    context.user_data['opciones_productos'] = opciones
    
    # Crear mensaje
    mensaje = f"*{categoria.capitalize()}* 🍽️\n\n"
    
    for letra, producto in zip(opciones, productos):
        producto_id, nombre, descripcion, precio = producto
        mensaje += f"*{letra}) {nombre}*\n"
        mensaje += f"   _{descripcion}_\n"
        mensaje += f"   💰 ${precio:.2f}\n"
        mensaje += "─" * 30 + "\n"
    
    mensaje += "\nEjemplo: Escribe 'A' para agregar el primer producto al carrito"
    mensaje += "\nO escribe 0 para volver a las categorías"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')


async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa la selección de producto por letra"""
    mensaje = update.message
    texto = mensaje.text.strip().upper()

    cliente_id = mensaje.from_user.id
    #imprimir datos para debug
    print(f"Cliente ID: {cliente_id}")
    
    # Opción para volver a categorías
    if texto == "0":
        await mensaje.reply_text("Volviendo a categorías...")
        # Limpiar datos de productos
        if 'productos_actuales' in context.user_data:
            del context.user_data['productos_actuales']
        if 'opciones_productos' in context.user_data:
            del context.user_data['opciones_productos']
        
        # Volver a mostrar categorías
        await obtener_categorias(update, context)
        return EstadoConversacion.ESPERANDO_CATEGORIA.value
    
    # Verificar si hay productos guardados
    if 'productos_actuales' not in context.user_data or 'opciones_productos' not in context.user_data:
        await mensaje.reply_text("Error en la sesión. Por favor, empieza de nuevo con /ver_productos")
        return ConversationHandler.END
    
    productos = context.user_data['productos_actuales']
    opciones = context.user_data['opciones_productos']
    categoria = context.user_data['categoria_seleccionada']
    
    # Verificar si la letra es válida
    if texto in opciones:
        indice = opciones.index(texto)
        producto = productos[indice]
        producto_id, nombre, descripcion, precio = producto
        print(f"Producto seleccionado: ID={producto_id}, Nombre={nombre}, Precio={precio}")
        
        # Verificar si el cliente tiene un pedido activo
        # el cliente_id es el usuario de telegram, no el id del cliente en la DB, 
        # por eso se busca el pedido actual con ese cliente_id
        pedido_actual = obtener_pedido_actual(cliente_id)

        if not pedido_actual:
            pedido_id = crear_pedido(cliente_id)
        else:
            pedido_id = pedido_actual[0]
        
        stock_disponible = verificar_stock_disponible(producto_id)
        
        if stock_disponible is None or stock_disponible == 0:
            await mensaje.reply_text(f"❌ No hay stock disponible para *{nombre}*")
            return EstadoConversacion.ESPERANDO_PRODUCTO.value
        
        exito = agregar_producto(pedido_id, producto_id, 1)
        if exito: 
            await mensaje.reply_text(
                f"✅ *{nombre}* agregado al pedido!\n\n"
                f"Precio: ${precio:.2f}\n\n",
                parse_mode='Markdown'
            )

            #volver a mostrar los productos de la categoria actual
            await mostrar_productos_categoria_texto(update, context) 
        
        # Permanecer en el mismo estado para seguir seleccionando
        return EstadoConversacion.ESPERANDO_PRODUCTO.value
        
    else:
        # Letra no válida
        opciones_texto = ", ".join(opciones)
        await mensaje.reply_text(
            f"❌ Opción no válida. Letras disponibles: {opciones_texto}\n"
            f"O escribe 0 para volver a categorías"
        )
        return EstadoConversacion.ESPERANDO_PRODUCTO.value


async def cancelar_opcion_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación actual"""
    await update.message.reply_text(
        "Operación cancelada. Puedes volver a empezar con /ver_productos"
    )
    # Limpiar todos los datos
    context.user_data.clear()
    return ConversationHandler.END


async def manejar_botones_carrito(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los botones del carrito"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('rem_'):
        producto_id = int(data.replace('rem_', ''))
        await disminuir_cantidad(query, context, producto_id)
        
    elif data.startswith('add_'):
        producto_id = int(data.replace('add_', ''))
        await aumentar_cantidad(query, context, producto_id)
        
    elif data.startswith('del_'):
        producto_id = int(data.replace('del_', ''))
        await eliminar_producto(query, context, producto_id)

    elif data.startswith('info_'):
        producto_id = int(data.replace('info_', ''))
        await mostrar_info_producto(query, context, producto_id)
        
    elif data == 'vaciar_todo':
        await vaciar_pedido(query, context)
        
    elif data == 'ver_productos':
        await obtener_categorias(update, context)
        
    elif data.startswith('finalizar_'):
        await finalizar_pedido(update, context)
        
    elif data == 'volver_carrito':
        await ver_pedido(update, context)


async def disminuir_cantidad(query, context, producto_id, cantidad=1):
    """Disminuye la cantidad de un producto en el carrito"""
    usuario_id = query.from_user.id
    
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
        producto_info = obtener_producto_por_id(producto_id)
        producto_nombre = producto_info[1] if producto_info else "Producto"
        
        await query.answer(f"➖ {producto_nombre}: {cantidad_actual} → {nueva_cantidad}")
        
        # Actualizar vista del carrito
        await actualizar_vista_pedido(query, context, usuario_id) #x disminuir cantidad
    else:
        await query.answer("❌ Error al actualizar cantidad")


async def mostrar_info_producto(query, context, producto_id):
    """Muestra información detallada del producto"""
    producto = obtener_producto_por_id(producto_id)
    
    if not producto:
        await query.answer("❌ Producto no encontrado")
        return
    
    producto_id, nombre, descripcion, precio = producto
    mensaje = f"*{nombre}*\n\n"
    mensaje += f"_{descripcion}_\n\n"
    mensaje += f"*Precio:* ${precio:.2f}\n\n"
    mensaje += "¿Quieres agregarlo al pedido?"
    
    keyboard = [
        #[InlineKeyboardButton("➖ 1", callback_data=f'rem_{producto_id}'),
         InlineKeyboardButton("✅ Sí, agregar", callback_data=f'add_{producto_id}'),
        #[InlineKeyboardButton("📋 Ver todos", callback_data='volver_categorias')]
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
        await agregar_producto_al_pedido(query, context, producto_id, cantidad)
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
        producto_info = obtener_producto_por_id(producto_id)
        producto_nombre = producto_info[1] if producto_info else "Producto"
        
        await query.answer(f"➕ {producto_nombre}: {cantidad_actual} → {nueva_cantidad}")
        
        # Actualizar vista del pedido
        await actualizar_vista_pedido(query, context, usuario_id) #x aumentar cantidad
    else:
        await query.answer("❌ Error al actualizar cantidad")


async def agregar_producto_al_pedido(query, context, producto_id, cantidad=1):
    """Agrega un nuevo producto al pedido"""
    usuario_id = query.from_user.id
    
    # Obtener información del producto
    producto_info = obtener_producto_por_id(producto_id)
    
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
    exito = agregar_producto(pedido_id, producto_id, cantidad)
    
    if exito:
        await actualizar_vista_pedido(query, context, usuario_id) #x agregar producto nuevo
    else:
        await query.answer("❌ Error al agregar producto")


async def vaciar_pedido(query, context):
    """Elimina todos los productos del pedido actual."""
    usuario_id = query.from_user.id
    
    # Obtener pedido actual
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        await query.answer("❌ No tienes productos en el pedido")
        return
    
    pedido_id = pedido_actual[0]
    
    # Eliminar todos los productos del pedido
    try:
        eliminado = vaciar_pedido_db(pedido_id)
        
        if eliminado:
            await query.answer("🗑️ Pedido vaciado")
            await query.edit_message_text(
                "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
                parse_mode='Markdown'
            )
        else:
            await query.answer("❌ Error al vaciar el pedido")
            
    except Exception as e:
        print(f"Error al vaciar pedido: {e}")
        await query.answer("❌ Error interno al vaciar el pedido")


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
    producto_info = obtener_producto_por_id(producto_id)
    
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


async def mostrar_confirmacion_finalizar_carrito(query, pedido_id):
    """Muestra diálogo de confirmación antes de finalizar el pedido"""
    
    #mostrar contenido del carrito antes de confirmar
    detalle_pedido = obtener_detalle_pedido(pedido_id)
    mensaje = f"⚠️ *Confirmar finalización del pedido*\n\n"
    mensaje += f"Una vez finalizado, no podrás hacer más cambios.\n\n"
    total = 0
    for item in detalle_pedido:
        producto_id, nombre, descripcion, precio, cantidad = item
        subtotal = precio * cantidad
        total += subtotal
        mensaje += f"*{nombre}* x {cantidad}\n"
        mensaje += f"   _{descripcion}_\n"
        mensaje += f"   💰 ${precio:.2f} c/u | Subtotal: ${subtotal:.2f}\n"
        mensaje += "─" * 30 + "\n"
    mensaje += f"\n*Total: ${total:.2f}*"

    # Crear teclado de confirmación
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Sí, finalizar", 
                callback_data=f'confirm_finalize_{pedido_id}'
            ),
            InlineKeyboardButton(
                "❌ No, cancelar", 
                callback_data='cancel_finalize'
            )
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Editar mensaje para mostrar confirmación
    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def ejecutar_eliminacion(query, context, producto_id, producto_nombre, pedido_id, usuario_id):
    """Ejecuta la eliminación del producto"""
    
    try:
        # Eliminar de la base de datos
        eliminado = quitar_producto_del_pedido(pedido_id, producto_id)
        
        if eliminado:
            # Notificar éxito
            await query.answer(f"✅ {producto_nombre} eliminado")
            
            # Verificar si el carrito quedó vacío
            nuevo_pedido = obtener_pedido_actual(usuario_id)
            
            if not nuevo_pedido:
                # Carrito vacío
                await query.edit_message_text(
                    "🛒 *Pedido vacío*\n\n"
                    f"**{producto_nombre}** fue eliminado y tu pedido ahora está vacío.\n\n"
                    "¡Agrega productos para continuar!",
                    parse_mode='Markdown'
                )
            else:
                # Actualizar vista del carrito
                await actualizar_vista_pedido(query, context, usuario_id) #x eliminar producto
                
        else:
            await query.answer("❌ Error al eliminar el producto")
            
    except Exception as e:
        print(f"Error en eliminación: {e}")
        await query.answer("❌ Error interno al eliminar")


async def ejecutar_finalizar_pedido(update, context):
    """Ejecuta la finalización del pedido"""
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id  
    
    if 'confirm_finalize_' in query.data:
        # El usuario confirmó
        invoice_id = int(query.data.replace('confirm_finalize_', ''))
        
        #obtener datos del cliente
        customer = obtener_cliente(telegram_id)
        email = customer['email'] if customer else None

        #el titulo del pago es el invoice_id con relleno de ceros a la izquierda para que siempre tenga 10 dígitos, por ejemplo: 0000000123
        title = f"Pedido #{str(invoice_id).zfill(10)}"
        invoice = obtener_pedido_actual(telegram_id)
        print(f"Datos del pedido para invoice_id {invoice_id}")
        amount = invoice['total']
        invoice_id = invoice['id']

        # Ejecutar la acción final
        try:
            # Descomenta esta línea cuando estés listo
            finalizar_pedido_db(invoice_id)

            ### extracto traido desde cmd_pagar para integrar aqui:
            mp = MercadoPagoSimple()
    
            # Crear pago en MercadoPago
            resultado = mp.crear_pago(
                titulo=title,
                monto=amount,
                telegram_id=telegram_id,
                invoice_id=invoice_id,
                email_cliente=email
            )
            
            if resultado['success']:
                # Guardar en BD (sin mp_payment_id aún, se actualizará con webhook)
                guardar_pago(
                    telegram_id=telegram_id,
                    mp_payment_id=None,
                    invoice_id=invoice_id,
                    monto=amount,
                    concepto=title
                )
                
                # Guardar preference_id en context para referencia
                context.user_data['ultimo_pago'] = {
                    'preference_id': resultado['preference_id'],
                    'monto': amount,
                    'concepto': title
                }
                
                # Enviar link de pago al usuario
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Pagar con MercadoPago", url=resultado['init_point'])]
                ])
                
                #await update.message.reply_text(
                #    f"🧾 **Detalle del pago:**\n\n"
                #    f"💰 Monto: **${amount:.2f}**\n"
                #    f"📝 Concepto: {title}\n\n"
                #    f"Hacé clic en el botón para pagar:",
                #    reply_markup=keyboard,
                #    parse_mode='Markdown'
                #)
            else:
                await update.message.reply_text(
                    "❌ Error al generar el pago. Intenta más tarde."
                )
            ###
            
            await query.edit_message_text(
                "✅ *¡Pedido confirmado!*\n\n"
                "Tu pedido ha sido registrado correctamente.\n"
                "Por favor, procede al pago para completar tu compra.\n\n"
                "Te contactaremos para la entrega apenas confirmemos el pago.\n\n"
                "¡Gracias por tu compra! 🎉",
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

        except Exception as e:
            print(f"Error al finalizar pedido: {e}")
            await query.edit_message_text(
                "❌ *Error al procesar el pedido*\n\n"
                "Hubo un problema al finalizar tu pedido.\n"
                "Por favor, intenta nuevamente.",
                parse_mode='Markdown'
            )
    
    elif query.data == 'cancel_finalize':
        # El usuario canceló
        await query.edit_message_text(
            "❌ *Acción cancelada*\n\n"
            "No se ha finalizado el pedido.\n"
            "Puedes continuar modificándolo.",
            parse_mode='Markdown'
        )


async def actualizar_vista_pedido(query, context, usuario_id):
    """Actualiza la vista del carrito después de cambios"""
    
    # Obtener pedido actualizado
    pedido_actual = obtener_pedido_actual(usuario_id)
    
    if not pedido_actual:
        # Esto no debería pasar si acabamos de eliminar, pero por si acaso
        await query.edit_message_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
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
    mensaje += f" ¿Qué deseas hacer? Modifica tu pedido o finalízalo cuando estés listo.\n\n"
    mensaje += "Puedes eliminar productos, agregar más o proceder al pago.\n\n"
    mensaje += "/quitar para eliminar productos, /ver_productos para agregar más, o \n\n"
    mensaje += "/finalizar para completar tu compra"
    
    # Crear teclado actualizado
    keyboard = []
    
    # Botones por producto
    for producto_id, nombre, cantidad, _, _ in items:
        nombre_corto = nombre[:10] + "..." if len(nombre) > 10 else nombre
        #keyboard.append([
        #    InlineKeyboardButton(f"➖ {nombre_corto}", callback_data=f'rem_{producto_id}'),
        #   InlineKeyboardButton(f"➕ {nombre_corto}", callback_data=f'add_{producto_id}')
        #])
        keyboard.append([
            InlineKeyboardButton(f"❌  Quitar {nombre_corto}", callback_data=f'del_{producto_id}')
        ])
    
    # Botones generales
    keyboard.append([
        #InlineKeyboardButton("🛍️ Agregar más", callback_data='ver_productos'),
        InlineKeyboardButton("✅ Finalizar pedido", callback_data=f'finalizar_{pedido_id}')
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        mensaje,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def manejar_confirmacion_finalizar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la confirmación de finalización del pedido"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('confirm_finalize_'):
        await ejecutar_finalizar_pedido(update, context)


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
            producto_info = obtener_producto_por_id(producto_id)
            
            if producto_info:
                await ejecutar_eliminacion(
                    query, context, producto_id, 
                    producto_info[1], pedido_id, usuario_id
                )
    
    elif data == 'cancel_del':
        # Cancelar eliminación - volver al carrito
        await query.answer("❌ Eliminación cancelada")
        await ver_pedido(update, context)


async def ver_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Versión con botones inline por producto"""
    
    # Determinar origen del mensaje
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
    else:
        return
    
    print("Mostrando pedido actual del cliente...")
    cliente_id = update.effective_user.id
    pedido_actual = obtener_pedido_actual(cliente_id)
    
    if not pedido_actual:
        await message.reply_text(
                "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!",
                parse_mode='Markdown'
        )
        return
    
    pedido_id = pedido_actual[0]
    detalle_pedido = obtener_detalle_pedido(pedido_id)
    
    if not detalle_pedido or not detalle_pedido[1]:
        await message.reply_text(
            "🛒 *Pedido vacío*\n\n¡Agrega productos para continuar!", 
                parse_mode='Markdown')
        return
    
    items = detalle_pedido[1]
    
    # Procesar todos los items primero
    items_detalle = []
    total = 0.0
    
    for producto_id, nombre_producto, cantidad, precio_unit, subtotal in items:
        producto_info = obtener_producto_por_id(producto_id)
        
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
    mensaje = "🛒 *Tu Pedido Actual*\n\n"
    #mensaje += "═" * 35 + "\n\n"
    
    # Listar productos en el mensaje
    for idx, item in enumerate(items_detalle, 1):
        mensaje += f"**{idx}. {item['nombre']}**\n"
        
        if item['descripcion']:
            mensaje += f"   _{item['descripcion']}_\n"
        
        mensaje += f"   📦 Cantidad: `{item['cantidad']}` "
        mensaje += f"× ${item['precio']:.2f} "
        mensaje += f"= **${item['subtotal']:.2f}**\n\n"
    
    # Resumen total
    mensaje += "═ " * 15 + "\n\n"
    #mensaje += "📊 **RESUMEN DE COMPRA**\n\n"
    #mensaje += f"• Productos: **{len(items_detalle)}**\n"
    #mensaje += f"• Items totales: **{sum(item['cantidad'] for item in items_detalle)}**\n"
    #mensaje += f"• Subtotal: **${total:.2f}**\n"
    
    #impuestos = total * 0.21
    #mensaje += f"• Impuestos (21%): **${impuestos:.2f}**\n"
    impuestos = 0.0
    total_final = total + impuestos
    mensaje += f"• **TOTAL: ${total_final:.2f}**\n\n"
    
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
        #InlineKeyboardButton("🛍️ Agregar más", callback_data='ver_productos')
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


async def finalizar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finaliza el pedido actual"""
    query = update.callback_query
    await query.answer()
    
    pedido_id = int(query.data.replace('finalizar_', ''))
    
    await mostrar_confirmacion_finalizar_carrito(query, pedido_id)


async def mensajes_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto del teclado principal"""
    texto = update.message.text
   
    #si texto se parece a Productos hacer obtener_categorias
    if texto.lower() in ['ver productos', 'productos', 'menú', 'menu', '🛍️ ver productos']:
        await obtener_categorias(update, context)

    #lo mismo con pedido
    elif texto.lower() in ['mi pedido', 'pedido', 'carrito', '🛒 mi pedido']:
        # Simulamos que es un callback query
        #query_data = type('obj', (object,), {'data': 'ver_pedido', 'from_user': user})()
        await ver_pedido(update, context)
    
    elif texto.lower() in ['mis pedidos', 'historial', 'historial de pedidos', '📋 mis pedidos']:
        await update.message.reply_text(
            "📊 *Historial de Pedidos*\n\n"
            "Pronto podrás ver todos tus pedidos anteriores.",
            parse_mode='Markdown'
        )
    
    elif texto.lower() in ['contacto', 'soporte', 'ayuda', 'ℹ️ ayuda']:
        await update.message.reply_text(
            "*Ayuda del Bot de Pedidos*\n\n"
            "• *🛍️ Ver Productos*: Explora nuestro menú\n"
            "• *🛒 Mi Pedido*: Revisa tu pedido actual\n"
            "• *📋 Mis Pedidos*: Historial de compras\n\n"
            "Para agregar productos, selecciona una categoría y luego el producto. Puedes modificar tu pedido antes de finalizarlo.\n\n",
            parse_mode='Markdown'
        )
    
    else:
        await update.message.reply_text(
            "❌ Opción no reconocida. Por favor, elige una opción del menú principal."
        )


async def cmd_estado_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando /estado - Verifica el estado del último pago
    """
    usuario_id = update.effective_user.id
    
    pago = buscar_ultimo_pago_usuario(usuario_id)
    
    if not pago:
        await update.message.reply_text("❌ No tenés pagos registrados.")
        return
    
    monto, concepto, estado, fecha_creacion, fecha_aprobacion, mp_payment_id = pago
    
    mp = MercadoPagoSimple()
    # Si hay mp_payment_id, consultar estado actual en MP (opcional)
    estado_mp = ""
    if mp_payment_id:
        resultado = mp.obtener_pago(mp_payment_id)
        if resultado['success']:
            estado_mp = f"\n📊 Estado MP: {resultado['pago']['status']}"
    
    # Emojis según estado
    emoji = {
        'pendiente': '⏳',
        'aprobado': '✅',
        'rechazado': '❌'
    }.get(estado, '❓')
    
    fecha_aprob = f"\n✅ Aprobado: {fecha_aprobacion}" if fecha_aprobacion else ""
    
    mensaje = (
        f"{emoji} **Estado de tu pago:**\n\n"
        f"💰 Monto: **${monto}**\n"
        f"📝 Concepto: {concepto}\n"
        f"📅 Solicitado: {fecha_creacion}\n"
        f"📌 Estado: **{estado.upper()}**{fecha_aprob}{estado_mp}"
    )
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')