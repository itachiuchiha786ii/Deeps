import logging
import os
import asyncio
import aiosqlite
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)
from dotenv import load_dotenv
load_dotenv()  # Load variables from .env

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
BASE_URL = "https://api.novita.ai/v3/openai"
MODEL = "deepseek/deepseek-r1-turbo"
DATABASE_URL = "bot_data.db"
MAX_MESSAGE_LENGTH = 4096
LONG_RESPONSE_LIMIT = 3500


# Format code blocks
def format_code_blocks(text):
    return re.sub(r"`(.*?)`", r"```\1```", text)


async def get_deepseek_response(user_id, new_message):
    url = f"{BASE_URL}/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}

    async with aiosqlite.connect(DATABASE_URL) as db:
        async with db.execute("SELECT message, response FROM chat_history WHERE user_id = ? ORDER BY timestamp ASC", (user_id,)) as cursor:
            rows = await cursor.fetchall()

    chat_messages = [{"role": "system", "content": "You are a helpful AI that remembers past conversations."}]

    for row in rows[-10:]:
        chat_messages.append({"role": "user", "content": row[0]})
        chat_messages.append({"role": "assistant", "content": row[1]})

    chat_messages.append({"role": "user", "content": new_message})

    data = {"model": MODEL, "messages": chat_messages, "stream": False, "max_tokens": 1500}

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    json_response = response.json()
    answer = json_response["choices"][0]["message"]["content"]

    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute(
            "INSERT INTO chat_history (user_id, message, response, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (user_id, new_message, answer)
        )
        await db.commit()

    return answer


# Menu
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Ask a Question", callback_data="ask")],
        [InlineKeyboardButton("📁 Upload a Code File", callback_data="upload")],
        [InlineKeyboardButton("🧹 Clear Chat History", callback_data="clear")],
        [InlineKeyboardButton("🧠 About", callback_data="about")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🤖 Deepseek Bot Menu:", reply_markup=reply_markup)


# Menu actions
async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "about":
        await query.edit_message_text("🤖 *Deepseek AI Bot*\nBuilt to assist with smart replies, code fixes, and file handling.", parse_mode="Markdown")
    elif query.data == "clear":
        user_id = query.from_user.id
        async with aiosqlite.connect(DATABASE_URL) as db:
            await db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
            await db.commit()
        await query.edit_message_text("🧹 Chat history cleared.")
    else:
        await query.edit_message_text("✅ Now send your message or upload a code file.")


# Chat handler
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    user_message = update.message.text
    temp = await update.message.reply_text("⏳ Forming response...")

    try:
        response = await get_deepseek_response(user_id, user_message)
        await temp.delete()
        response = format_code_blocks(response)
        if len(response) > LONG_RESPONSE_LIMIT:
            await update.message.reply_text("⚠️ Response too long to show here.")
        else:
            await update.message.reply_text(response[:MAX_MESSAGE_LENGTH], parse_mode="Markdown")
    except Exception as e:
        await temp.delete()
        await update.message.reply_text(f"❌ Error: {e}")


# File handler
async def upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    file_path = f"downloads/{doc.file_name}"
    os.makedirs("downloads", exist_ok=True)
    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)

    if doc.file_name.endswith((".py", ".js", ".java", ".c", ".cpp")):
        with open(file_path, "r", encoding="utf-8") as f:
            code = f.read().replace("\t", "    ")

        corrected_path = f"corrected_{doc.file_name}"
        with open(corrected_path, "w", encoding="utf-8") as f:
            f.write(code)

        await update.message.reply_document(document=open(corrected_path, "rb"), caption="✅ Corrected code file.")
    else:
        await update.message.reply_text("📂 File received. I'll analyze it soon.")


# Init DB
async def init_db():
    async with aiosqlite.connect(DATABASE_URL) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                response TEXT,
                timestamp DATETIME
            )
        """)
        await db.commit()



async def start_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", show_menu))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CallbackQueryHandler(handle_menu_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    app.add_handler(MessageHandler(filters.Document.ALL, upload_file))

    await init_db()
    await app.run_polling()

import asyncio
import sys

async def safe_main():
    try:
        await start_bot()
    except RuntimeError as e:
        if "already running" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            await start_bot()
        else:
            raise

if __name__ == "__main__":
    if sys.platform.startswith("linux") and "termux" in sys.executable.lower():
        # ✅ Termux-specific: Apply nest_asyncio and run
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(start_bot())
    else:
        # ✅ Normal/Render-safe: Try asyncio.run, fallback to patched loop
        try:
            asyncio.run(safe_main())
        except RuntimeError as e:
            # Handles cases like Render or Jupyter where event loop is already running
            import nest_asyncio
            nest_asyncio.apply()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(start_bot())