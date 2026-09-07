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
from telegram_bot.runtime import resolve_bot_token
from telegram_bot.state import BotState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
# python-telegram-bot calls URLs containing the bot token. Keep HTTP request URLs
# out of normal application logs so the credential is never written to stdout.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("hollywing.bot")

POLL_WAIT_SECONDS = 15


def build_application(token: str, api: ApiClient) -> Application:
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


async def _poll_until_token_changes(api: ApiClient, token: str) -> None:
    while True:
        await asyncio.sleep(POLL_WAIT_SECONDS)
        latest = await resolve_bot_token(api)
        if not latest.ok:
            continue
        if latest.token != token:
            logger.info("Telegram bot token or enabled flag changed; restarting poller")
            return


async def run_poller(token: str, api: ApiClient) -> None:
    mode = os.environ.get("TELEGRAM_BOT_MODE", "polling")
    application = build_application(token, api)
    async with application:
        await application.bot.delete_webhook(drop_pending_updates=False)
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)
        logger.info("Telegram bot started in %s mode", mode)
        try:
            await _poll_until_token_changes(api, token)
        finally:
            await application.updater.stop()
            await application.stop()


async def main() -> None:
    api = ApiClient(
        base_url=os.environ.get("API_INTERNAL_URL", "http://localhost:8000"),
        client_id=os.environ.get("TELEGRAM_BOT_CLIENT_ID", "rental-telegram-bot"),
        client_secret=os.environ.get("TELEGRAM_BOT_CLIENT_SECRET", ""),
    )
    idle_logged = False
    while True:
        resolved = await resolve_bot_token(api)
        if not resolved.ok:
            if not idle_logged:
                logger.warning("Waiting for API before loading the Telegram bot token")
                idle_logged = True
            await asyncio.sleep(POLL_WAIT_SECONDS)
            continue
        if not resolved.token:
            if not idle_logged:
                logger.warning(
                    "Telegram bot token is not set. Save Bot token in System Settings → Telegram "
                    "(or set TELEGRAM_BOT_TOKEN) and wait; the bot will start automatically."
                )
                idle_logged = True
            await asyncio.sleep(POLL_WAIT_SECONDS)
            continue
        idle_logged = False
        await run_poller(resolved.token, api)


if __name__ == "__main__":
    asyncio.run(main())
