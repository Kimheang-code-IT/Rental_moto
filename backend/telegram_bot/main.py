import asyncio
import logging
import os

from redis import asyncio as aioredis
from telegram import Update
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_bot.api_client import ApiClient
from telegram_bot.state import BotState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
# python-telegram-bot calls URLs containing the bot token. Keep HTTP request URLs
# out of normal application logs so the credential is never written to stdout.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("hollywing.bot")


def build_application() -> Application:
    api = ApiClient(
        base_url=os.environ.get("API_INTERNAL_URL", "http://localhost:8000"),
        client_id=os.environ.get("TELEGRAM_BOT_CLIENT_ID", "rental-telegram-bot"),
        client_secret=os.environ.get("TELEGRAM_BOT_CLIENT_SECRET", ""),
    )
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    application = Application.builder().token(token).build()
    state_redis = aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/1"), decode_responses=True)
    state = BotState(state_redis)

    from telegram_bot import handlers as h

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await h.cmd_start(update, context, api, state)

    async def link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await h.cmd_link(update, context, api)

    async def chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await h.cmd_id(update, context)

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await h.handle_message(update, context, api, state)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("id", chat_id))
    application.add_handler(CommandHandler("chatid", chat_id))
    application.add_handler(CommandHandler("link", link))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        err = context.error
        if isinstance(err, Conflict):
            logger.error(
                "Telegram polling conflict: another process is already calling getUpdates "
                "with this bot token. Stop duplicate telegram-bot containers or other pollers."
            )
            return
        logger.exception("Telegram handler error: %s", err)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text("Something went wrong. Please try /start again.")
            except Exception:
                pass

    application.add_error_handler(on_error)
    application.bot_data["api"] = api
    application.bot_data["state"] = state
    return application


async def main() -> None:
    mode = os.environ.get("TELEGRAM_BOT_MODE", "polling")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN is not set; bot is idle. Set the token and restart the container.")
        while True:
            await asyncio.sleep(3600)
    application = build_application()
    async with application:
        await application.bot.delete_webhook(drop_pending_updates=False)
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Telegram bot started in %s mode", mode)
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await application.updater.stop()
            await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
