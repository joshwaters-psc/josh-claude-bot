import logging
from collections import defaultdict
from typing import Any
import anthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from config import config

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=config.anthropic_api_key)

SYSTEM_PROMPT = (
    "You are Josh's personal AI assistant, accessible via Telegram. "
    "Josh is a WalkMe consultant based in Brisbane, Australia. "
    "He's building a personal wellness app called ZenPath, grounded in Eastern metaphysics. "
    "He also runs BRAINS 3.0, an AI-powered WalkMe consulting system. "
    "Be concise, helpful, and direct."
)

histories: dict[int, list[dict[str, Any]]] = defaultdict(list)

def trim_history(chat_id: int) -> None:
    h = histories[chat_id]
    if len(h) > config.max_history * 2:
        histories[chat_id] = h[-(config.max_history * 2):]

async def ask_claude(chat_id: int, user_text: str) -> str:
    histories[chat_id].append({"role": "user", "content": user_text})
    trim_history(chat_id)
    try:
        response = client.messages.create(
            model=config.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=histories[chat_id],
        )
        reply = response.content[0].text
        histories[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except anthropic.APIError as e:
        histories[chat_id].pop()
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hey Josh! Your Claude assistant is online. Just send me a message.\n\n/help - commands\n/clear - reset history\n/status - bot status")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("/start - welcome\n/help - this message\n/clear - reset conversation\n/status - model info")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    histories[update.effective_chat.id].clear()
    await update.message.reply_text("Cleared. Fresh start!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Model: {config.model}\nHistory: {len(histories[update.effective_chat.id])} messages")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    if not user_text:
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        reply = await ask_claude(chat_id, user_text)
        if len(reply) <= 4096:
            await update.message.reply_text(reply, parse_mode=None)
        else:
            for chunk in [reply[i:i+4096] for i in range(0, len(reply), 4096)]:
                await update.message.reply_text(chunk, parse_mode=None)
    except anthropic.RateLimitError:
        await update.message.reply_text("Rate limited — try again in a moment.")
    except anthropic.AuthenticationError:
        await update.message.reply_text("API key issue.")
    except Exception as e:
        logger.exception("Error handling message")
        await update.message.reply_text(f"Something went wrong: {type(e).__name__}. Try /clear.")

def main() -> None:
    app = Application.builder().token(config.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
