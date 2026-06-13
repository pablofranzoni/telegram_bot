---
nombre: telegram-webhook-flask-ptb
descripcion: Convenciones de producción para bots de Telegram usando la librería python-telegram-bot (v20+) con Webhooks en un servidor Flask. Integra el bucle asíncrono de PTB dentro del flujo síncrono de Flask.
---

## Directrices para python-telegram-bot (v20+) con Flask Webhooks

La librería `python-telegram-bot` es completamente asíncrona (`async/await`). Para integrarla correctamente con Flask sin bloquear el servidor, sigue estas pautas estrictas.

### 1. Inicialización de la Aplicación de PTB
No uses `application.run_polling()`. Debes inicializar la aplicación en modo remoto usando `build()`, llamar a `initialize()` al arrancar Flask y usar un manejador de contexto o ciclo de vida para cerrarla adecuadamente.

### 2. Integración del Bucle Asíncrono (`asyncio`)
Flask maneja peticiones síncronas. Para pasar el objeto `Update` de Flask a la aplicación asíncrona de Telegram, utiliza `asyncio.run()` o un bucle de eventos existente para ejecutar `application.process_update()`.

```python
import asyncio
import os
from flask import Flask, request, abort
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app = Flask(__name__)

# 1. Configuración de la aplicación de PTB (Modo Webhook)
TOKEN = os.getenv("TELEGRAM_TOKEN")
ptb_app = Application.builder().token(TOKEN).build()

# Definición de comandos asíncronos nativos de PTB
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("¡Hola! Bot configurado correctamente con Flask y Webhook.")

ptb_app.add_handler(CommandHandler("start", start))

# Inicializar componentes internos de la librería (requisito de PTB v20+)
# En producción, se recomienda ejecutar esto antes de que Flask empiece a servir
asyncio.run(ptb_app.initialize())

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def telegram_webhook():
    if not request.is_json:
        abort(400)
        
    # 2. Convertir el JSON de Flask en un objeto Update de PTB
    update_data = request.get_json()
    update = Update.de_json(data=update_data, bot=ptb_app.bot)
    
    # 3. Procesar de forma asíncrona dentro del entorno síncrono de Flask
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ptb_app.process_update(update))
    except Exception as e:
        app.logger.error(f"Error procesando update: {e}")
    finally:
        loop.close()
        
    return "OK", 200
```

### 3. Registro Automático del Webhook (`setWebhook`)
Es una buena práctica configurar el webhook automáticamente cuando la aplicación de Flask se levanta, evitando tener que llamar a la API de Telegram manualmente con `curl`.

```python
# Script complementario de inicialización o comando CLI
async def configurar_webhook():
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Ej: https://tudominio.com
    url_completa = f"{WEBHOOK_URL}/webhook/{TOKEN}"
    
    async with ptb_app:
        await ptb_app.bot.set_webhook(url=url_completa)
        print(f"Webhook configurado exitosamente en: {url_completa}")

# Ejecutar al desplegar el proyecto
if __name__ == "__main__":
    asyncio.run(configurar_webhook())
```

### 4. Evitar fugas de memoria y bloqueos
* **Nunca** uses `ptb_app.start()` o `ptb_app.updater` si usas Flask; confía enteramente en `process_update`.
* Asegúrate de que el servidor WSGI de producción (como `gunicorn`) use hilos o procesos independientes para que `asyncio.new_event_loop()` no interfiera entre peticiones concurrentes.
