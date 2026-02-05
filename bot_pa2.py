# pythonanywhere_safe.py - VERSIÓN SIMPLIFICADA
import os
import logging
import asyncio
import nest_asyncio

from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from dotenv import load_dotenv
from database.db import init_db
from routes.csv_routes import csv_bp
from shared.handlers.commands import (
    start, mensajes_texto, manejar_seleccion_producto, mostrar_productos_categoria,
    ver_carrito, finalizar_pedido_handler, manejar_botones_carrito, manejar_confirmacion_eliminar
)

# ==================== CONFIGURACIÓN BÁSICA ====================
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import asyncio
import nest_asyncio

# Permite event loops anidados
nest_asyncio.apply()

app_flask = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# Configuración Flask
app_flask.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app_flask.config['DATABASE_PATH'] = os.path.join(basedir, 'pedidos_bot.db')
app_flask.config['UPLOAD_FOLDER'] = './uploads'
app_flask.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024
app_flask.config['ALLOWED_EXTENSIONS'] = {'csv'}

init_db(app_flask)
app_flask.register_blueprint(csv_bp, url_prefix='/api')

#===============================================================
botapp = Application.builder().token(TOKEN).build()

botapp.add_handler(CallbackQueryHandler(manejar_confirmacion_eliminar, pattern='^(confirm_del_|cancel_del)'))
botapp.add_handler(CallbackQueryHandler(manejar_seleccion_producto, pattern='^(add_|rem_|info_)'))
botapp.add_handler(CallbackQueryHandler(mostrar_productos_categoria, pattern='^cat_'))
botapp.add_handler(CallbackQueryHandler(ver_carrito, pattern='^ver_carrito$'))
botapp.add_handler(CallbackQueryHandler(finalizar_pedido_handler, pattern='^finalizar_'))
botapp.add_handler(CallbackQueryHandler(manejar_botones_carrito))
botapp.add_handler(CommandHandler("start", start))
botapp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensajes_texto))

initialized = False

@app_flask.route('/webhook', methods=['POST'])
def webhook():
    global initialized
    loop = asyncio.get_event_loop()
    
    # Inicializar la primera vez
    if not initialized:
        loop.run_until_complete(botapp.initialize())
        initialized = True
    
    update_data = request.get_json()
    
    async def process():
        update = Update.de_json(update_data, botapp.bot)
        await botapp.process_update(update)
    
    loop.run_until_complete(process())
    return 'ok', 200

# ==================== ENDPOINTS AUXILIARES ====================
@app_flask.route('/')
def index():
    return '''
        <html>
            <head><title>Sistema CSV + Telegram Bot</title></head>
            <body>
                <h1>Sistema de Gestión CSV + Telegram Bot</h1>
                <p>Endpoints disponibles:</p>
                <ul>
                    <li><a href="/api/upload">/api/upload</a> - Subir CSV (GET para formulario, POST para subir)</li>
                    <li><a href="/api/uploads">/api/uploads</a> - Ver uploads realizados</li>
                    <li><a href="/api/customers">/api/customers</a> - Listar clientes</li>
                    <li><a href="/api/stats">/api/stats</a> - Estadísticas</li>
                </ul>
                <p>Telegram Bot también está activo y usando la misma base de datos.</p>
            </body>
        </html>
        '''

@app_flask.route('/health')
def health():
    """Verificación de salud"""
    import requests
    status = {
        'service': 'telegram-bot',
        'status': 'running',
        'pythonanywhere': True
    }
    
    # Verificar Telegram API
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/getMe"
        response = requests.get(url, timeout=5)
        status['telegram_api'] = 'reachable' if response.status_code == 200 else 'unreachable'
    except Exception as e:
        status['telegram_api'] = f'unreachable: {str(e)}'
    
    return jsonify(status)

@app_flask.route('/health_db')
def health_db():
    from database.db import get_db
    try:
        get_db().execute("SELECT 1")
        return jsonify({'status': 'healthy', 'database': 'ok'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# ==================== CONFIGURACIÓN INICIAL ====================
def setup_webhook():
    """Configura el webhook en Telegram"""
    if not TOKEN or not WEBHOOK_URL:
        logger.warning("⚠️ No se puede configurar webhook: Token o URL faltantes")
        return
    
    import requests
    
    webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    payload = {
        "url": webhook_endpoint,
        "drop_pending_updates": True,
        "allowed_updates": ["message", "callback_query"]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        data = response.json()
        
        if data.get('ok'):
            logger.info(f"✅ Webhook configurado en: {webhook_endpoint}")
        else:
            logger.error(f"❌ Error configurando webhook: {data.get('description')}")
    except Exception as e:
        logger.error(f"❌ Error al configurar webhook: {e}")

# ==================== INICIALIZACIÓN EN PYTHONANYWHERE ====================
# Configurar webhook al cargar
if __name__ != '__main__' and os.getenv('PYTHONANYWHERE_DOMAIN'):
    logger.info("🚀 Iniciando bot en PythonAnywhere...")
    setup_webhook()

# WSGI para PythonAnywhere
application = app_flask

if __name__ == '__main__':
    print("🤖 Bot Flask - Modo Prueba Local")
    app_flask.run(host='0.0.0.0', port=5001, debug=True)