import os
import asyncio
import logging
import threading
import hmac
import requests
import atexit

from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from telegram.ext import Application

from bot_core import create_and_initialize_app
from database import db_manager
from database.db_factory import DatabaseType
from routes.csv_routes import csv_bp
from routes.products_routes import products_bp
from routes.categories_routes import categories_bp
from routes.invoices_routes import invoices_bp
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from utils import mpago
from utils.logging_config import configure_logging
from utils.config import Config

# ==================== CONFIGURACIÓN ====================
load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
BOT_MODE = os.getenv('BOT_MODE', 'WEBHOOK')  
WEBHOOK_PATH_TOKEN = os.getenv('TELEGRAM_WEBHOOK_PATH_TOKEN')
WEBHOOK_SECRET_TOKEN = os.getenv('TELEGRAM_WEBHOOK_SECRET_TOKEN')

configure_logging()
logger = logging.getLogger(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

if BOT_MODE != 'WEBHOOK':
    logger.warning("BOT_MODE=%s ignorado: este servicio solo soporta WEBHOOK", BOT_MODE)
    BOT_MODE = 'WEBHOOK'

# ==================== FLASK APP ====================
app_flask = Flask(__name__, template_folder='templates',  # Por defecto ya es 'templates'
                            static_folder='static',       # Por defecto ya es 'static'
                            static_url_path='/static')

# Configuración para upload de archivos
app_flask.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '4D1xGWans1S6JBeUDJ1NebpG')
app_flask.config['UPLOAD_FOLDER'] = './uploads'  # Carpeta donde se guardarán los archivos
app_flask.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024  # Límite de 4MB
app_flask.config['ALLOWED_EXTENSIONS'] = {'csv'}

# JWT Configuration
app_flask.config['JWT_SECRET_KEY'] = Config.JWT_SECRET_KEY
app_flask.config['JWT_ALGORITHM'] = Config.JWT_ALGORITHM
app_flask.config['JWT_ACCESS_TOKEN_EXPIRES'] = Config.JWT_ACCESS_TOKEN_EXPIRES

# Initialize JWTManager
jwt = JWTManager(app_flask)

# Variable global para la app de Telegram (se inicializa una sola vez)
telegram_app: Application | None = None
telegram_loop: asyncio.AbstractEventLoop | None = None
telegram_loop_thread: threading.Thread | None = None
bootstrap_lock = threading.Lock()
bootstrap_done = False

os.makedirs(app_flask.config['UPLOAD_FOLDER'], exist_ok=True)


#db_manager.init_db(DatabaseType.SQLITE, db_path="./pedidos_bot.db")
db_manager.init_db(DatabaseType.POSTGRESQL, DATABASE_URL=os.getenv('DATABASE_URL'))

app_flask.register_blueprint(auth_bp, url_prefix='/api')
app_flask.register_blueprint(admin_bp, url_prefix='/api')
app_flask.register_blueprint(csv_bp, url_prefix='/api')
app_flask.register_blueprint(products_bp, url_prefix='/api')
app_flask.register_blueprint(categories_bp, url_prefix='/api')
app_flask.register_blueprint(invoices_bp, url_prefix='/api')


def get_or_create_telegram_app() -> Application:
    """Obtiene o crea la aplicación de Telegram (singleton)"""
    global telegram_app, telegram_loop, telegram_loop_thread
    
    if telegram_app is None:
        telegram_app = create_and_initialize_app(TOKEN, BOT_MODE, initialize_app=False)

    if telegram_app is None:
        raise RuntimeError("No se pudo crear la aplicación de Telegram.")

    if telegram_loop is None:
        telegram_loop = asyncio.new_event_loop()
        telegram_loop_thread = threading.Thread(
            target=_run_telegram_loop,
            args=(telegram_loop,),
            daemon=True,
            name="telegram-ptb-loop",
        )
        telegram_loop_thread.start()
        logger.info("Loop dedicado de PTB iniciado")

        init_future = asyncio.run_coroutine_threadsafe(
            telegram_app.initialize(),
            telegram_loop,
        )
        init_future.result(timeout=30)
        logger.info("Application PTB inicializada en loop dedicado")
    
    return telegram_app


def _run_telegram_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Ejecuta un loop dedicado para PTB en un hilo separado."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _shutdown_telegram_app() -> None:
    """Cierra correctamente PTB y su loop dedicado al terminar el proceso."""
    global telegram_app, telegram_loop, telegram_loop_thread

    if telegram_loop is None:
        return

    try:
        if telegram_app is not None:
            shutdown_future = asyncio.run_coroutine_threadsafe(
                telegram_app.shutdown(),
                telegram_loop,
            )
            shutdown_future.result(timeout=15)
    except Exception:
        logger.exception("Error al cerrar Application PTB")
    finally:
        telegram_loop.call_soon_threadsafe(telegram_loop.stop)
        if telegram_loop_thread is not None:
            telegram_loop_thread.join(timeout=5)
        telegram_loop.close()


atexit.register(_shutdown_telegram_app)


# ==================== ENDPOINTS FLASK ====================
@app_flask.route('/')
def index():
    return '''
        <html>
            <head><title>Sistema Telegram Bot</title></head>
            <body>
                <h1>Sistema de Gestión Telegram Bot</h1>
                <p>Endpoints disponibles:</p>
                <ul>
                    <li><a href="/api/upload">/api/upload</a> - Subir CSV (GET para formulario, POST para subir)</li>
                    <li><a href="/api/uploads">/api/uploads</a> - Ver uploads realizados</li>
                    <li><a href="/api/customers">/api/customers</a> - Listar clientes</li>
                    <li><a href="/api/categories">/api/categories</a> - Listar categorias</li>
                    <li><a href="/api/products">/api/products</a> - Listar productos</li>
                    <li><a href="/api/stats">/api/stats</a> - Estadísticas</li>
                </ul>
                <p>Telegram Bot también está activo y usando la misma base de datos.</p>
            </body>
        </html>
        '''

@app_flask.route('/webhook/<string:webhook_token>', methods=['POST'])
def webhook(webhook_token: str):
    """Endpoint principal para recibir updates de Telegram"""
    logger.info("Webhook de Telegram recibido")
    
    try:
        if not WEBHOOK_PATH_TOKEN or not WEBHOOK_SECRET_TOKEN:
            logger.error("Webhook Telegram deshabilitado: falta configuracion de seguridad")
            return jsonify({"status": "error", "message": "webhook_misconfigured"}), 503

        if not hmac.compare_digest(webhook_token, WEBHOOK_PATH_TOKEN):
            logger.warning("Webhook Telegram rechazado por token de ruta invalido")
            return jsonify({"status": "error", "message": "forbidden"}), 403

        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(header_secret, WEBHOOK_SECRET_TOKEN):
            logger.warning("Webhook Telegram rechazado por secret header invalido")
            return jsonify({"status": "error", "message": "forbidden"}), 403

        # 1. Obtener datos
        json_data = request.get_json()

        if not json_data:
            logger.error("Webhook de Telegram sin JSON")
            return 'No JSON received', 400
        
        logger.debug(
            "Webhook Telegram payload resumido",
            extra={
                "payload_keys": sorted(json_data.keys()),
                "update_id": json_data.get("update_id"),
            },
        )
        
        # 2. ✅ Obtener la app TELEGRAM (ya inicializada)
        app_ptb = get_or_create_telegram_app()
        
        # 3. Convertir JSON a Update
        from telegram import Update
        update = Update.de_json(json_data, app_ptb.bot)
        
        # 4. Procesar en el loop dedicado de PTB para evitar crear loops por request
        if telegram_loop is None:
            raise RuntimeError("Loop de Telegram no inicializado")

        future = asyncio.run_coroutine_threadsafe(app_ptb.process_update(update), telegram_loop)
        future.result(timeout=20)
        logger.info("Update de Telegram procesado", extra={"update_id": update.update_id})
        return 'ok'
            
    except Exception as e:
        logger.error("Error procesando webhook de Telegram: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": "internal_error"}), 500
    

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
    
    logger.info("Webhook de retorno de pago", extra={"estado": estado, "method": request.method})
    
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
        logger.debug(
            "Webhook de retorno con payload resumido",
            extra={"estado": estado, "payload_keys": sorted(datos_recibidos.keys()) if isinstance(datos_recibidos, dict) else []},
        )
    
    return jsonify({
        "status": estado,
        "message": mensaje,
        "endpoint": f"/{estado}",
        "datos_recibidos": datos_recibidos
    }), codigo


@app_flask.route('/mercadopago-webhook/', methods=['POST'])
def mercadopago_webhook():
    """Endpoint para recibir notificaciones de MercadoPago"""
    try:
        data = request.get_json(silent=True) or {}
        topic = data.get('type') or data.get('topic') or request.args.get('type') or request.args.get('topic')

        # Mercado Pago puede enviar el ID por JSON o query params
        resource_id = (
            data.get('data', {}).get('id')
            or request.args.get('id')
            or request.args.get('data.id')
        )

        logger.info(
            "Webhook de Mercado Pago recibido",
            extra={
                "topic": topic,
                "resource_id": resource_id,
                "has_json_payload": bool(data),
                "query_keys": sorted(request.args.keys()),
            },
        )

        if not topic:
            logger.warning("Webhook MP descartado: topic ausente")
            return jsonify({"status": "ignored", "reason": "missing_topic"}), 400

        if topic == 'payment':
            if not resource_id:
                logger.warning("Webhook MP payment descartado: payment id ausente")
                return jsonify({"status": "ignored", "reason": "missing_payment_id"}), 400

            signature_ok = mpago.verificar_firma(request, resource_id)
            logger.info(
                "Validacion de firma webhook MP",
                extra={"resource_id": resource_id, "signature_ok": signature_ok},
            )

            if not signature_ok:
                return jsonify({"status": "ignored", "reason": "invalid_signature"}), 400

            mp = mpago.MercadoPagoSimple()
            result = mp.procesar_notificacion_pago(resource_id)
            logger.info(
                "Resultado procesamiento payment webhook MP",
                extra={"resource_id": resource_id, "result": result},
            )
            return jsonify({"status": "ok", "topic": topic}), 200

        if topic == 'merchant_order':
            if not resource_id:
                logger.warning("Webhook MP merchant_order descartado: resource id ausente")
                return jsonify({"status": "ignored", "reason": "missing_merchant_order_id"}), 400

            mp = mpago.MercadoPagoSimple()
            mp.procesar_merchant_order(resource_id)
            logger.info(
                "merchant_order procesada",
                extra={"resource_id": resource_id},
            )
            return jsonify({"status": "ok", "topic": topic}), 200

        logger.info("Webhook MP ignorado por topic no manejado", extra={"topic": topic})
        return jsonify({"status": "ignored", "topic": topic}), 200

    except Exception as e:
        logger.exception("Error en webhook de Mercado Pago")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==================== CONFIGURACIÓN INICIAL ====================
def setup_webhook():
    """Configura el webhook en Telegram (se ejecuta al inicio)"""
    if not TOKEN or not WEBHOOK_URL or not WEBHOOK_PATH_TOKEN or not WEBHOOK_SECRET_TOKEN:
        logger.warning("⚠️  No se puede configurar webhook: faltan variables requeridas")
        return

    base_url = WEBHOOK_URL.rstrip('/')
    if base_url.endswith('/webhook'):
        webhook_base = base_url
    else:
        webhook_base = f"{base_url}/webhook"

    webhook_endpoint = f"{webhook_base}/{WEBHOOK_PATH_TOKEN}"

    if not webhook_endpoint.lower().startswith('https://'):
        logger.error("❌ WEBHOOK_URL debe usar HTTPS en produccion")
        return
    
    # Configurar webhook
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    payload = {
        "url": webhook_endpoint,
        "drop_pending_updates": True,
        "allowed_updates": ["message", "callback_query"],
        "secret_token": WEBHOOK_SECRET_TOKEN,
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


def bootstrap_webhook_runtime() -> None:
    """Inicializa recursos de webhook/PTB una sola vez por proceso."""
    global bootstrap_done

    with bootstrap_lock:
        if bootstrap_done:
            return

        setup_webhook()
        get_or_create_telegram_app()
        bootstrap_done = True

# ==================== INICIALIZACIÓN ====================
# WSGI para PythonAnywhere
application = app_flask

if __name__ != '__main__' and os.getenv('PYTHONANYWHERE_DOMAIN'):
    try:
        bootstrap_webhook_runtime()
    except Exception:
        logger.exception("Error inicializando webhook/PTB en import WSGI")

# ==================== EJECUCIÓN LOCAL (para pruebas) ====================
if __name__ == '__main__':
    logger.info("Bot Flask en modo prueba local")
    logger.info("Estado de configuracion", extra={"token_configurado": bool(TOKEN), "webhook_configurado": bool(WEBHOOK_URL)})

    # Evita doble inicialización con el reloader: el bootstrap corre solo una vez.
    run_main_flag = os.environ.get('WERKZEUG_RUN_MAIN')
    if run_main_flag == 'true' or run_main_flag is None:
        try:
            bootstrap_webhook_runtime()
        except Exception:
            logger.exception("Error inicializando webhook/PTB en arranque")
    else:
        logger.info("Proceso padre del reloader: se omite bootstrap")

    # Para pruebas locales, no configuramos webhook real
    app_flask.run(host='0.0.0.0', port=5000, debug=True, use_reloader=True)