import os
import requests

from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

NEW_URL = "https://pablofranzoni.pythonanywhere.com/webhook"

# 1. Eliminar webhook antiguo
print("Eliminando webhook antiguo...")
del_resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=true")
print(del_resp.json())

# 2. Configurar nuevo webhook
print(f"\nConfigurando nuevo webhook en: {NEW_URL}")
set_resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={NEW_URL}")
print(set_resp.json())

# 3. Verificar
print("\nVerificando estado...")
info_resp = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo")
print(info_resp.json())