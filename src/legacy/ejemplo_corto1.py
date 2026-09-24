import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Función que se ejecuta con el comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Creamos los botones
    keyboard = [
        [InlineKeyboardButton("Click aquí", callback_data='1')],
        [InlineKeyboardButton("Información", callback_data='2')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Enviamos el mensaje con los botones
    await update.message.reply_text('Elige una opción:', reply_markup=reply_markup)

# Función que maneja el clic en los botones
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Esto es CLAVE: obtenemos el objeto 'query' del update
    query = update.callback_query
    
    # Siempre responde el callback para que Telegram deje de mostrar el "relojito"
    await query.answer()
    
    # Aquí viene la modificación: editamos el mensaje original
    if query.data == '1':
        # Cambiamos el texto del mensaje, los botones desaparecen
        await query.edit_message_text(text="¡Perfecto! Has activado la función.")
    elif query.data == '2':
        # También podemos dejar los botones pero con texto nuevo
        await query.edit_message_text(
            text="Esto es un bot de ejemplo. Para volver, usa /start",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Volver", callback_data='1')]])
        )

def main():
    from dotenv import load_dotenv

    load_dotenv()
    TOKEN:str|None = os.getenv('BOT_TOKEN', None)  # Reemplaza con tu token real

    if TOKEN is None:
        print("Error: El token del bot no está configurado. Asegúrate de tener un archivo .env con BOT_TOKEN.")
        return
    
    # Reemplaza con tu token real
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    # El CallbackQueryHandler manejará TODOS los clics en botones
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Bot iniciado...")
    app.run_polling()

if __name__ == '__main__':
    main()