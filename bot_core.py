import os
import asyncio
import logging

from telegram.ext import CallbackQueryHandler, MessageHandler, filters

from shared.handlers.commands import (
    start,
    mensajes_texto,
    manejar_seleccion_producto,
    mostrar_productos_categoria,
    ver_carrito,
    finalizar_pedido_handler,
    manejar_botones_carrito,
    manejar_confirmacion_eliminar
)

# Configuración de logging
#logging.basicConfig(
#    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#    level=logging.DEBUG
#)
logger = logging.getLogger(__name__)

# ==================== CREACIÓN DE LA APP TELEGRAM ====================
def create_and_initialize_app(bot_token, bot_mode):
    """Crea e inicializa una Application de python-telegram-bot"""
    from telegram.ext import Application, CommandHandler
    
    logger.info("🔄 Creando e inicializando Application...")
    
    if bot_mode == "POLLING":
        logger.info("⚙️ Modo POLLING seleccionado")
        from database.db import init_db_polling
        basedir = os.path.abspath(os.path.dirname(__file__))
        db_path = os.path.join(basedir, 'pedidos_bot.db')
        init_db_polling(db_path)  # Asegurarse de que la DB esté inicializada

    # 1. Crear la aplicación
    app = Application.builder().token(bot_token).build()
    
    app.add_handler(CallbackQueryHandler(manejar_confirmacion_eliminar, pattern='^(confirm_del_|cancel_del)'))
    app.add_handler(CallbackQueryHandler(manejar_seleccion_producto, pattern='^(add_|rem_|info_)'))
    app.add_handler(CallbackQueryHandler(mostrar_productos_categoria, pattern='^cat_'))
    app.add_handler(CallbackQueryHandler(ver_carrito, pattern='^ver_carrito$'))
    app.add_handler(CallbackQueryHandler(finalizar_pedido_handler, pattern='^finalizar_'))
    app.add_handler(CallbackQueryHandler(manejar_botones_carrito))

    app.add_handler(CommandHandler("start", start))

    # Manejador de mensajes de texto (teclado principal)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensajes_texto))
    
    # 3. ✅ INICIALIZAR LA APLICACIÓN (ESTO ES CLAVE)
    # Creamos un event loop para inicializar
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if bot_mode == "POLLING":
        print("🚀 Iniciando bot en modo POLLING...")
        app.run_polling(drop_pending_updates=True) 
    else:
        try:
            loop.run_until_complete(app.initialize())
            logger.info("✅ Application inicializada correctamente")
            return app
        except Exception as e:
            logger.error(f"❌ Error inicializando Application: {e}")
            raise
        finally:
            loop.close()
        

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    BOT_MODE = os.getenv('BOT_MODE', 'POLLING')

    create_and_initialize_app(TOKEN, BOT_MODE)