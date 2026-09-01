import logging

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.api_client import ApiClient
from telegram_bot.formatter import Formatter
from telegram_bot.state import BotState

logger = logging.getLogger("hollywing.bot.handlers")

PERIOD_MAP = {
    "Today": "today",
    "Last 3 Days": "3_days",
    "Last 7 Days": "7_days",
    "Last 1 Month": "1_month",
}

PAGE_SIZE = 8


def _formatter(localization: dict) -> Formatter:
    return Formatter(localization)


async def _localization(api: ApiClient) -> dict:
    try:
        response = await api.get("/api/v2/settings/app-config")
        return response.get("data", {}).get("localization", {})
    except Exception:
        return {}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram_bot.keyboards import main_keyboard

    await update.message.reply_text(
        "Welcome to HollyWing Motor bot.\nសូមស្វាគមន៍មកកាន់ HollyWing Motor",
        reply_markup=main_keyboard(),
    )


async def help_account(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient) -> None:
    fmt = _formatter(await _localization(api))
    text = fmt.tr(
        "🔐 Account Help\n\n"
        "To link your Telegram account:\n"
        "1. Sign in to the web app\n"
        "2. Request a link code from your profile\n"
        "3. Send /link CODE here in this private chat\n\n"
        "Forgot your password? If your account is linked, use Forgot Password in the app and we will send a one-time reset code here.\n\n"
        "Never share your password or codes with anyone.",
        "🔐 ជំនួយគណនី\n\n"
        "ដើម្បីភ្ជាប់គណនី Telegram:\n"
        "១. ចូលគណនីក្នុងកម្មវិធី\n"
        "២. ស្នើសុំលេខកូដភ្ជាប់ពីផ្ទាំងព័ត៌មានរបស់អ្នក\n"
        "៣. ផ្ញើ /link CODE នៅទីនេះ\n\n"
        "បើភ្លេចពាក្យសម្ងាត់ ប្រើ Forgot Password ក្នុងកម្មវិធី ហើយកូដសម្ងាត់នឹងត្រូវបានផ្ញើមកទីនេះ។",
    )
    await update.message.reply_text(text)


async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient) -> None:
    chat = update.effective_chat
    if chat.type != "private":
        await update.message.reply_text("Please use /link in a private chat.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /link CODE")
        return
    code = context.args[0]
    try:
        await api.post(
            "/api/v2/telegram/link",
            {
                "code": code,
                "telegramUserId": str(update.effective_user.id),
                "telegramChatId": str(chat.id),
            },
        )
        await update.message.reply_text("Account linked successfully. ✅")
    except Exception:
        logger.exception("link failed")
        await update.message.reply_text("Link failed. The code may be invalid or expired.")


async def show_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, state: BotState, period: str = "today") -> None:
    chat_id = str(update.effective_chat.id)
    localization = await _localization(api)
    fmt = _formatter(localization)
    try:
        response = await api.get(
            "/api/v2/telegram/transactions",
            params={"period": period, "page": 1, "limit": PAGE_SIZE},
        )
    except Exception:
        await update.message.reply_text(fmt.tr("Failed to load transactions.", "ផ្ទុកប្រតិបត្តិការណ៍មិនបានសម្រេច។"))
        return
    meta = response.get("meta", {})
    events = response.get("data", [])
    lines = [fmt.tr(f"📋 Transactions ({meta.get('startDate', '')[:10]} → {meta.get('endDate', '')[:10]})", f"📋 ប្រតិបត្តិការណ៍ ({meta.get('startDate', '')[:10]} → {meta.get('endDate', '')[:10]})")]
    for event in events:
        type_labels = {
            "rental_created": "Rental",
            "rental_completed": "Return",
            "rental_cancelled": "Cancel",
            "rental_overdue": "Overdue",
            "payment_recorded": "Payment",
            "charge_recorded": "Charge",
        }
        label = type_labels.get(event.get("type"), event.get("type"))
        amount = event.get("amount")
        lines.append(
            f"• {label} {event.get('rental_no', '')} — {fmt.money(amount) if amount is not None else ''} {event.get('status', '')}"
        )
    if not events:
        lines.append(fmt.tr("No transactions in this period.", "គ្មានប្រតិបត្តិការណ៍ក្នុងរយៈពេលនេះ។"))
    await state.set_page(chat_id, "transactions", 1, {"period": period, "total": meta.get("total", 0)})
    await update.message.reply_text("\n".join(lines))


async def show_motorcycle_status(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient) -> None:
    from telegram_bot.keyboards import status_group_keyboard

    fmt = _formatter(await _localization(api))
    try:
        response = await api.get("/api/v2/telegram/motorcycle-status")
    except Exception:
        await update.message.reply_text(fmt.tr("Failed to load motorcycle status.", "ផ្ទុកស្ថានភាពម៉ូតូមិនបានសម្រេច។"))
        return
    counts = response.get("data", {}).get("counts", {})
    lines = [fmt.tr("🏍 Motorcycle Status", "🏍 ស្ថានភាពម៉ូតូ")]
    for status in ("Available", "Progressing", "Maintenance"):
        lines.append(f"{status}: {counts.get(status, 0)}")
    await update.message.reply_text("\n".join(lines), reply_markup=status_group_keyboard)


async def show_status_group(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, status: str) -> None:
    query = update.callback_query
    fmt = _formatter(await _localization(api))
    response = await api.get("/api/v2/telegram/motorcycle-status")
    items = response.get("data", {}).get("groups", {}).get(status, [])
    lines = [f"{status} ({len(items)})"]
    for item in items[:20]:
        lines.append(f"• {item.get('code')} {item.get('model')} ({item.get('plate') or ''})")
    await query.message.reply_text("\n".join(lines))


async def show_finance(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, period: str = "today") -> None:
    fmt = _formatter(await _localization(api))
    try:
        response = await api.get("/api/v2/telegram/finance-summary", params={"period": period})
    except Exception:
        await update.message.reply_text(fmt.tr("Failed to load finance summary.", "ផ្ទុកសេចក្តីសង្ខេបហិរញ្ញវត្ថុមិនបានសម្រេច។"))
        return
    data = response.get("data", {})
    text = "\n".join(
        [
            fmt.tr("💰 Income / Expense", "💰 ចំណូល / ចំណាយ"),
            f"{fmt.tr('Income', 'ចំណូល')}: {fmt.money(data.get('income'))}",
            f"{fmt.tr('Expense', 'ចំណាយ')}: {fmt.money(data.get('expense'))}",
            f"{fmt.tr('Net', 'សុទ្ធ')}: {fmt.money(data.get('net'))}",
            f"{fmt.tr('Outstanding', 'នៅជំពាក់')}: {fmt.money(data.get('outstanding'))}",
        ]
    )
    await update.message.reply_text(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, state: BotState) -> None:
    text = (update.message.text or "").strip()
    chat_id = str(update.effective_chat.id)

    conversation = await state.get_conversation(chat_id)
    if conversation and conversation.get("mode") == "custom_range":
        from datetime import datetime, timedelta, timezone

        try:
            value = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            await update.message.reply_text("Please send a date as YYYY-MM-DD")
            return
        if conversation.get("step") == "start":
            await state.set_conversation(chat_id, {"mode": "custom_range", "step": "end", "start": text})
            await update.message.reply_text("Start date saved. Now send the end date (YYYY-MM-DD):")
            return
        start_text = conversation.get("start")
        try:
            end_value = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
            start_value = datetime.strptime(start_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            await update.message.reply_text("Invalid end date.")
            return
        await state.clear_conversation(chat_id)
        await _report_for_range(update, api, start_value.isoformat(), end_value.isoformat())
        return

    if text == "📋 All Rental Transactions":
        from telegram_bot.keyboards import period_keyboard

        await state.set_conversation(chat_id, {"mode": "period", "target": "transactions"})
        await update.message.reply_text("Select a period:", reply_markup=period_keyboard())
    elif text == "🏍 Motorcycle Status":
        await show_motorcycle_status(update, context, api)
    elif text == "💰 Income / Expense":
        from telegram_bot.keyboards import period_keyboard

        await state.set_conversation(chat_id, {"mode": "period", "target": "finance"})
        await update.message.reply_text("Select a period:", reply_markup=period_keyboard())
    elif text == "🔐 Account Help":
        await help_account(update, context, api)
    elif text in PERIOD_MAP:
        period = PERIOD_MAP[text]
        conversation = conversation or {}
        await state.clear_conversation(chat_id)
        from telegram_bot.keyboards import main_keyboard

        if conversation.get("target") == "finance":
            await show_finance(update, context, api, period)
        else:
            await show_transactions(update, context, api, state, period)
        await update.message.reply_text("⬅ Back to main menu", reply_markup=main_keyboard())
    elif text == "Custom Range":
        await state.set_conversation(chat_id, {"mode": "custom_range", "step": "start"})
        await update.message.reply_text("Send the start date (YYYY-MM-DD):")
    elif text == "⬅ Back":
        from telegram_bot.keyboards import main_keyboard

        await state.clear_conversation(chat_id)
        await update.message.reply_text("Main menu", reply_markup=main_keyboard())
    else:
        from telegram_bot.keyboards import main_keyboard

        await update.message.reply_text("Choose an option below:", reply_markup=main_keyboard())


async def _report_for_range(update: Update, api: ApiClient, start: str, end: str) -> None:
    fmt = _formatter(await _localization(api))
    try:
        response = await api.get(
            "/api/v2/telegram/finance-summary",
            params={"start": start, "end": end},
        )
    except Exception:
        await update.message.reply_text("Failed to load report.")
        return
    data = response.get("data", {})
    text = "\n".join(
        [
            fmt.tr("💰 Custom range report", "💰 របាយការណ៍តាមចន្លោះថ្ងៃ"),
            f"{start[:10]} → {end[:10]}",
            f"{fmt.tr('Income', 'ចំណូល')}: {fmt.money(data.get('income'))}",
            f"{fmt.tr('Expense', 'ចំណាយ')}: {fmt.money(data.get('expense'))}",
            f"{fmt.tr('Net', 'សុទ្ធ')}: {fmt.money(data.get('net'))}",
            f"{fmt.tr('Outstanding', 'នៅជំពាក់')}: {fmt.money(data.get('outstanding'))}",
        ]
    )
    await update.message.reply_text(text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, state: BotState) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split(":")
    if parts[0] == "status" and len(parts) == 2:
        await show_status_group(update, context, api, parts[1])
    elif parts[0] == "page" and len(parts) == 3:
        pass
    elif parts[0] == "back":
        from telegram_bot.keyboards import main_keyboard

        await query.message.reply_text("Main menu", reply_markup=main_keyboard())

