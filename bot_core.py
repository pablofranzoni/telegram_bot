import os
import asyncio
import logging

from telegram.ext import (
    CallbackQueryHandler, 
    MessageHandler, 
    filters,
    Application, 
    CommandHandler, 
    ConversationHandler
)

from utils.config import Config
from utils.logging_config import configure_logging
from database.db_manager import db_manager, DatabaseType
from utils.constants import EstadoConversacion
from shared.handlers.commands import (
    reiniciar_desde_fallback,
    start,
    recibir_email,
    cancelar_ingreso_email,
    ver_ayuda,
    verificar_codigo,
    cmd_inicio_cliente,
    cancelar_opcion_producto,
    seleccionar_categoria,
    seleccionar_producto,
    agregar_y_salir_flujo_productos,
    mensajes_texto,
    obtener_categorias,
    ver_pedido,
    finalizar_pedido,
    manejar_botones_carrito,
    manejar_confirmacion_eliminar,
    manejar_confirmacion_finalizar_pedido,
    cmd_estado_pago,
    error_handler
)

configure_logging()

logger = logging.getLogger(__name__)

def init_database():
    """Inicializar según configuración"""
    db_type = Config.DB_TYPE
    
    if db_type == DatabaseType.SQLITE:
        # ✅ CORRECTO: db_path como keyword argument
        db_manager.init_db(
            DatabaseType.SQLITE,
            db_path=Config.SQLITE_PATH
        )
        logger.info(f"📁 SQLite: {Config.SQLITE_PATH}")
        
    elif db_type == DatabaseType.POSTGRESQL:
        # ✅ CORRECTO: db_url como keyword argument
        db_manager.init_db(
            DatabaseType.POSTGRESQL,
            db_url=Config.DATABASE_URL
        )
        logger.info("🐘 PostgreSQL conectado")
        
    elif db_type == DatabaseType.MYSQL:
        # ✅ CORRECTO: parámetros MySQL
        db_manager.init_db(
            DatabaseType.MYSQL,
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            port=Config.MYSQL_PORT
        )
        logger.info("🐬 MySQL conectado")


# ==================== CREACIÓN DE LA APP TELEGRAM ====================
def create_and_initialize_app(bot_token, bot_mode, initialize_app=True):
    """Crea e inicializa una Application de python-telegram-bot"""
    
    logger.info("🔄 Creando e inicializando Application...")
    
    if bot_mode == "POLLING":
        raise ValueError("Modo POLLING no permitido: este proyecto funciona solo con WEBHOOK")

    # 1. Crear la aplicación
    app = Application.builder().token(bot_token).build()
    logger.info("✅ Application creada")
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler("mi_pedido", ver_pedido))

    products_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("ver_productos", obtener_categorias),
            MessageHandler(filters.Regex('^🛍️ Ver Productos$'), obtener_categorias)
        ],
        states={
            EstadoConversacion.ESPERANDO_CATEGORIA.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, seleccionar_categoria)
            ],
            EstadoConversacion.ESPERANDO_PRODUCTO.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, seleccionar_producto),
                CallbackQueryHandler(agregar_y_salir_flujo_productos, pattern='^add_'),
                CallbackQueryHandler(manejar_botones_carrito, pattern='^(info_|prod_)')
            ],
        },
        fallbacks=[
            CommandHandler("cancelar_productos", cancelar_opcion_producto),
            CommandHandler("mi_pedido", ver_pedido),
            CommandHandler('ayuda', ver_ayuda),
        ],
        allow_reentry=True,
        name="flujo_compra"
    )
    app.add_handler(products_conv_handler)  
    
    app.add_handler(CallbackQueryHandler(manejar_confirmacion_eliminar, pattern='^(confirm_del_|cancel_del)'))
    app.add_handler(CallbackQueryHandler(manejar_confirmacion_finalizar_pedido, pattern=r'^(confirm_finalize_\d+|cancel_finalize)$'))
    app.add_handler(CallbackQueryHandler(finalizar_pedido, pattern='^finalizar_'))
    app.add_handler(CallbackQueryHandler(manejar_botones_carrito))

    # Crear ConversationHandler para el email
    email_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('inicio_cliente', cmd_inicio_cliente)],
            states={
            EstadoConversacion.ESPERANDO_EMAIL.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_email)
            ],
            EstadoConversacion.ESPERANDO_CODIGO.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_codigo)
            ],
        },
        fallbacks=[
            CommandHandler('cancelar', cancelar_ingreso_email),
            CommandHandler('ayuda', ver_ayuda),
            CommandHandler('start', reiniciar_desde_fallback),
        ],
        allow_reentry=True,
        name="flujo_registro_email"
    )
    app.add_handler(email_conv_handler)  # Agregar el ConversationHandler a la aplicación
    app.add_handler(CommandHandler("estado", cmd_estado_pago))

    # Manejador de mensajes de texto (teclado principal)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensajes_texto))
    
    #app.add_error_handler(error_handler)

    if not initialize_app:
        logger.info("Application creada sin initialize(); lifecycle externo")
        return app

    # Creamos un event loop para inicializar
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(app.initialize())
        logger.info("✅ Application inicializada correctamente")
        return app
    except Exception as e:
        logger.error(f"❌ Error inicializando Application: {e}")
        raise
    finally:
        loop.close()
        