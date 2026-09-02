import asyncio
import logging
import os

from redis import asyncio as aioredis
from telegram import Update
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

    async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await h.handle_message(update, context, api, state)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("link", link))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))

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
        await application.start()
        await application.updater.start_polling()
        logger.info("Telegram bot started in %s mode", mode)
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            await application.updater.stop()
            await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
