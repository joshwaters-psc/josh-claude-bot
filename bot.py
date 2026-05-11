import logging
from collections import defaultdict
from typing import Any
import anthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from config import config
from mba_skill import MODES as MBA_MODES, compose_system_prompt as compose_mba_prompt, mode_summary as mba_mode_summary

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=config.anthropic_api_key)

DEFAULT_SYSTEM_PROMPT = (
    "You are Josh's personal AI assistant, accessible via Telegram. "
    "Josh is a WalkMe consultant based in Brisbane, Australia. "
    "He's building a personal wellness app called ZenPath, grounded in Eastern metaphysics. "
    "He also runs BRAINS 3.0, an AI-powered WalkMe consulting system. "
    "Be concise, helpful, and direct."
)

# Per-chat conversation state.
histories: dict[int, list[dict[str, Any]]] = defaultdict(list)
# Per-chat MBA mode: None = default assistant, otherwise a key from MBA_MODES.
mba_mode: dict[int, str | None] = defaultdict(lambda: None)


def system_prompt_for(chat_id: int) -> str:
    mode = mba_mode[chat_id]
    if mode is None:
        return DEFAULT_SYSTEM_PROMPT
    return compose_mba_prompt(mode)


def cacheable_system(chat_id: int) -> list[dict]:
    # The MBA system prompt is ~3.5k tokens and identical across turns within
    # a conversation. cache_control makes Anthropic cache it for ~5 min and
    # bill subsequent reads at ~10% of the normal input rate. The small default
    # prompt falls below the cache minimum and is silently uncached.
    return [{
        "type": "text",
        "text": system_prompt_for(chat_id),
        "cache_control": {"type": "ephemeral"},
    }]


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
            system=cacheable_system(chat_id),
            messages=histories[chat_id],
        )
        u = response.usage
        logger.info(
            "tokens in=%s out=%s cache_read=%s cache_write=%s",
            u.input_tokens, u.output_tokens,
            getattr(u, "cache_read_input_tokens", 0),
            getattr(u, "cache_creation_input_tokens", 0),
        )
        reply = response.content[0].text
        histories[chat_id].append({"role": "assistant", "content": reply})
        return reply
    except anthropic.APIError:
        histories[chat_id].pop()
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hey Josh! Your Claude assistant is online. Just send me a message.\n\n"
        "/help - all commands\n"
        "/mba - enter MBA Coach mode\n"
        "/clear - reset history\n"
        "/status - bot status"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "General:\n"
        "  /start - welcome\n"
        "  /help - this message\n"
        "  /clear - reset conversation\n"
        "  /status - model + mode\n\n"
        "MBA Coach:\n"
        "  /mba - enter MBA mode (default: Coach / Socratic)\n"
        f"{mba_mode_summary()}\n"
        "  /mba_off - leave MBA mode"
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    histories[update.effective_chat.id].clear()
    await update.message.reply_text("Cleared. Fresh start!")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    mode = mba_mode[chat_id]
    mode_label = f"MBA / {MBA_MODES[mode]['label']}" if mode else "Default assistant"
    await update.message.reply_text(
        f"Model: {config.model}\n"
        f"Mode: {mode_label}\n"
        f"History: {len(histories[chat_id])} messages"
    )


async def _enter_mba_mode(update: Update, mode_id: str) -> None:
    chat_id = update.effective_chat.id
    mba_mode[chat_id] = mode_id
    histories[chat_id].clear()
    mode = MBA_MODES[mode_id]
    await update.message.reply_text(
        f"MBA Coach - {mode['label']} mode.\n"
        f"{mode['description']}\n\n"
        f"Frameworks will always be cited by name.\n"
        f"Switch with /validate, /coach, /teach. Leave with /mba_off."
    )


async def mba(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _enter_mba_mode(update, "coach")


async def mba_validate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _enter_mba_mode(update, "validate")


async def mba_coach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _enter_mba_mode(update, "coach")


async def mba_teach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _enter_mba_mode(update, "teach")


async def mba_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    mba_mode[chat_id] = None
    histories[chat_id].clear()
    await update.message.reply_text("MBA Coach off. Back to default assistant.")


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
    app.add_handler(CommandHandler("mba", mba))
    app.add_handler(CommandHandler("validate", mba_validate))
    app.add_handler(CommandHandler("coach", mba_coach))
    app.add_handler(CommandHandler("teach", mba_teach))
    app.add_handler(CommandHandler("mba_off", mba_off))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
