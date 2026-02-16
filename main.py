import os

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from deep_translator import GoogleTranslator

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

translator = GoogleTranslator(source="auto", target="de")


async def translate_to_german(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    translated = translator.translate(update.message.text)
    await update.message.reply_text(translated)


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_to_german))
app.run_polling()
