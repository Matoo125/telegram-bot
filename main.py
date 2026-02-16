import os

import re

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from deep_translator import GoogleTranslator
from mistralai import Mistral
from dotenv import load_dotenv
import markdown

load_dotenv()

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
MISTRAL_API_KEY = os.environ["MISTRAL_API_KEY"]

translator = GoogleTranslator(source="auto", target="de")
mistral = Mistral(api_key=MISTRAL_API_KEY)

MODES = {"translate", "llm"}
DEFAULT_MODE = "translate"


ALLOWED_TAGS = {"b", "i", "s", "u", "code", "pre", "a", "blockquote"}


def md_to_telegram_html(text: str) -> str:
    """Convert markdown to Telegram-compatible HTML."""
    html = markdown.markdown(text, extensions=["fenced_code"])
    # Normalize tags to Telegram-supported equivalents
    html = html.replace("<strong>", "<b>").replace("</strong>", "</b>")
    html = html.replace("<em>", "<i>").replace("</em>", "</i>")
    html = html.replace("<del>", "<s>").replace("</del>", "</s>")
    # Replace <p> with newlines
    html = html.replace("<p>", "").replace("</p>", "\n")
    # Replace list items with bullet points, strip surrounding list tags
    html = html.replace("<li>", "• ").replace("</li>", "")
    # Strip all tags not supported by Telegram
    html = re.sub(r"</?(\w+)[^>]*>", lambda m: m.group(0) if m.group(1) in ALLOWED_TAGS else "", html)
    # Collapse excessive blank lines
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


async def process_message(mode: str, text: str, context: ContextTypes.DEFAULT_TYPE) -> str:
    if mode == "translate":
        result = translator.translate(text)
        context.chat_data.setdefault("history", []).append((text, result))
    else:
        messages = context.chat_data.setdefault("llm_messages", [])
        messages.append({"role": "user", "content": text})
        response = await mistral.chat.complete_async(
            model="mistral-small-latest",
            messages=messages,
        )
        result = response.choices[0].message.content
        messages.append({"role": "assistant", "content": result})
    return result


async def send_result(update: Update, result: str, mode: str) -> None:
    if mode == "llm":
        html = md_to_telegram_html(result)
        try:
            await update.message.reply_text(html, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(result)
    else:
        await update.message.reply_text(result)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mode = context.chat_data.get("mode", DEFAULT_MODE)
    result = await process_message(mode, update.message.text, context)
    await send_result(update, result, mode)


async def llm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /llm <your message>")
        return
    result = await process_message("llm", text, context)
    await send_result(update, result, "llm")


async def translate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /translate <your message>")
        return
    result = await process_message("translate", text, context)
    await send_result(update, result, "translate")


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current = context.chat_data.get("mode", DEFAULT_MODE)

    if not context.args:
        await update.message.reply_text(f"Current mode: <b>{current}</b>", parse_mode="HTML")
        return

    new_mode = context.args[0].lower()
    if new_mode not in MODES:
        await update.message.reply_text(f"Unknown mode. Use: {', '.join(MODES)}")
        return

    context.chat_data["mode"] = new_mode
    await update.message.reply_text(f"Switched to <b>{new_mode}</b> mode.", parse_mode="HTML")


async def review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history = context.chat_data.get("history", [])
    if not history:
        await update.message.reply_text("No translations yet.")
        return

    original_header = "Original"
    translated_header = "German"
    col1 = max(len(original_header), *(len(orig) for orig, _ in history))
    col2 = max(len(translated_header), *(len(trans) for _, trans in history))

    sep = f"+-{'-' * col1}-+-{'-' * col2}-+"
    header = f"| {original_header:<{col1}} | {translated_header:<{col2}} |"
    rows = [f"| {orig:<{col1}} | {trans:<{col2}} |" for orig, trans in history]

    table = "\n".join([sep, header, sep, *rows, sep])
    await update.message.reply_text(f"<pre>{table}</pre>", parse_mode="HTML")


app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("mode", mode_command))
app.add_handler(CommandHandler("llm", llm_command))
app.add_handler(CommandHandler("translate", translate_command))
app.add_handler(CommandHandler("review", review))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
