import os
import asyncio
import logging
import requests

from flask import Flask, jsonify, request
from dotenv import load_dotenv

from bot_core import create_and_initialize_app
from database import db_manager
from database.db_factory import DatabaseType
from routes.csv_routes import csv_bp
from utils import mpago

# ==================== CONFIGURACIÓN ====================
load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
BOT_MODE = os.getenv('BOT_MODE', 'WEBHOOK')  

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# ==================== FLASK APP ====================
app_flask = Flask(__name__, template_folder='templates',  # Por defecto ya es 'templates'
                            static_folder='static',       # Por defecto ya es 'static'
                            static_url_path='/static')

# Configuración para upload de archivos
app_flask.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '4D1xGWans1S6JBeUDJ1NebpG')
app_flask.config['UPLOAD_FOLDER'] = './uploads'  # Carpeta donde se guardarán los archivos
app_flask.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # Límite de 4MB
app_flask.config['ALLOWED_EXTENSIONS'] = {'csv'}

# Variable global para la app de Telegram (se inicializa una sola vez)
telegram_app = None

os.makedirs(app_flask.config['UPLOAD_FOLDER'], exist_ok=True)

db_manager.init_db(DatabaseType.SQLITE, db_path="./pedidos_bot.db")

app_flask.register_blueprint(csv_bp, url_prefix='/api')


def get_or_create_telegram_app():
    """Obtiene o crea la aplicación de Telegram (singleton)"""
    global telegram_app
    
    if telegram_app is None:
        telegram_app = create_and_initialize_app(TOKEN, BOT_MODE)
    
    return telegram_app


# ==================== ENDPOINTS FLASK ====================
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

@app_flask.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint principal para recibir updates de Telegram"""
    logger.info("📨 Webhook recibido")
    
    try:
        # 1. Obtener datos
        json_data = request.get_json()

        if not json_data:
            logger.error("❌ No se recibió JSON")
            return 'No JSON received', 400
        
        logger.debug(f"Datos recibidos: {json_data}")
        
        # 2. ✅ Obtener la app TELEGRAM (ya inicializada)
        app_ptb = get_or_create_telegram_app()
        
        # 3. Convertir JSON a Update
        from telegram import Update
        update = Update.de_json(json_data, app_ptb.bot)
        
        # 4. ✅ Procesar el update EN EL LOOP CORRECTO
        # Método 1: Usando el loop existente de la app
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Procesar el update
            loop.run_until_complete(app_ptb.process_update(update))
            logger.info(f"✅ Update {update.update_id} procesado")
            
            return 'ok'
        finally:
            # No cerramos el loop completamente para mantener la app inicializada
            pass
            
    except Exception as e:
        logger.error(f"❌ Error procesando webhook: {e}", exc_info=True)
        return f'Error: {str(e)}', 500
    

@app_flask.route('/health')
def health():
    """Endpoint para verificar salud"""
    import requests
    
    status = {
        'service': 'telegram-bot',
        'status': 'running',
        'webhook_url': WEBHOOK_URL,
        'telegram_app_initialized': telegram_app is not None
    }
    
    # Verificar conexión con Telegram API
    if TOKEN:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getMe"
            response = requests.get(url, timeout=5)
            status['telegram_api'] = 'reachable' if response.status_code == 200 else 'unreachable'
        except:
            status['telegram_api'] = 'unreachable'
    
    return status

@app_flask.route('/health_db')
def health_db():
    from database.db_manager import get_db
    try:
        # Verificar base de datos
        get_db().execute("SELECT 1")
        return {'status': 'healthy', 'database': 'ok'}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500


@app_flask.route('/<string:estado>', methods=['GET', 'POST'])
def procesar_pago(estado):
    # Validar que el estado sea uno de los permitidos
    estados_permitidos = ['okpago', 'failpago', 'pendpago']
    
    if estado not in estados_permitidos:
        return jsonify({
            "status": "error",
            "message": "Estado no válido"
        }), 404
    
    print(f"Procesando estado: {estado}")
    
    # Lógica según el estado
    if estado == 'okpago':
        mensaje = "Pago procesado correctamente"
        codigo = 200
    elif estado == 'pending':
        mensaje = "Pago en proceso"
        codigo = 202
    elif estado == 'error':
        mensaje = "Error en el procesamiento del pago"
        codigo = 400
    
    # Obtener datos si es POST
    datos_recibidos = None
    if request.method == 'POST':
        datos_recibidos = request.get_json() or request.form.to_dict()
        print(f"Datos recibidos para {estado}: {datos_recibidos}")
    
    return jsonify({
        "status": estado,
        "message": mensaje,
        "endpoint": f"/{estado}",
        "datos_recibidos": datos_recibidos
    }), codigo


@app_flask.route('/mercadopago-webhook/', methods=['POST'])
def mercadopago_webhook():
    """Endpoint para recibir notificaciones de MercadoPago"""
    data = request.get_json()
    topic = data.get('type') or data.get('topic') or request.args.get('topic')
    
    print(f"📌 Webhook recibido - Topic: {topic}")
    
    # Obtener el ID según el tipo
    resource_id = data.get('data', {}).get('id')
    
    if topic == 'payment':
        # Procesar pago directo
        mp = mpago.MercadoPagoSimple()
        if mpago.verificar_firma(request, resource_id):
            mp.procesar_notificacion_pago(resource_id)
    
    elif topic == 'merchant_order':
        # Consultar la orden para obtener los pagos
        mp = mpago.MercadoPagoSimple()
        mp.procesar_merchant_order(resource_id)
        
    return jsonify({"status": "ok"}), 200

# ==================== CONFIGURACIÓN INICIAL ====================
def setup_webhook():
    """Configura el webhook en Telegram (se ejecuta al inicio)"""
    if not TOKEN or not WEBHOOK_URL:
        logger.warning("⚠️  No se puede configurar webhook: Token o URL faltantes")
        return
    
    webhook_endpoint = f"{WEBHOOK_URL.rstrip('/')}/webhook"
    
    # Configurar webhook
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
            logger.info(f"📝 {data.get('description', '')}")
        else:
            logger.error(f"❌ Error configurando webhook: {data.get('description')}")
            
    except Exception as e:
        logger.error(f"❌ Error al configurar webhook: {e}")

# ==================== INICIALIZACIÓN ====================
# WSGI para PythonAnywhere
application = app_flask

# Configurar webhook al cargar (solo en producción)
if __name__ != '__main__' and os.getenv('PYTHONANYWHERE_DOMAIN'):
    logger.info("🚀 Iniciando bot en PythonAnywhere...")
    
    # 1. Configurar webhook
    setup_webhook()
    
    # 2. Pre-inicializar la app de Telegram (opcional, se inicializa lazy)
    # get_or_create_telegram_app()

# ==================== EJECUCIÓN LOCAL (para pruebas) ====================
if __name__ == '__main__':
    print("🤖 Bot Flask - Modo Prueba")
    print(f"Token: {'✅' if TOKEN else '❌'} {'Configurado' if TOKEN else 'Faltante'}")
    print(f"Webhook URL: {WEBHOOK_URL or 'No configurada'}")
    
    setup_webhook()

    # Para pruebas locales, no configuramos webhook real
    app_flask.run(host='0.0.0.0', port=5000, debug=True)