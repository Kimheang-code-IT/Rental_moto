import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ContextTypes

from telegram_bot.api_client import ApiClient
from telegram_bot.formatter import Formatter
from telegram_bot import keyboards as kb
from telegram_bot.state import BotState

logger = logging.getLogger("hollywing.bot.handlers")

PAGE_SIZE = 8
MESSAGE_SEPARATOR = "———————————————————"


def _report_title(fmt: Formatter, report: str, period: str) -> str:
    readable_period = period.replace("_", " ")
    return fmt.tr(
        f"💰 {report.title()} ({readable_period})",
        f"💰 {report} ({readable_period})",
    )


def _finance_summary_lines(fmt: Formatter, data: dict, title: str) -> list[str]:
    return [
        title,
        "",
        f"- {fmt.tr('Income', 'ចំណូល')}: {fmt.money(data.get('income'))}",
        f"- {fmt.tr('Expense', 'ចំណាយ')}: {fmt.money(data.get('expense'))}",
        f"- {fmt.tr('Net', 'សុទ្ធ')}: {fmt.money(data.get('netIncome'))}",
        f"- {fmt.tr('Outstanding', 'នៅជំពាក់')}: {fmt.money(data.get('outstanding'))}",
    ]


def _ctx(update: Update) -> tuple[str, str, str, bool]:
    chat = update.effective_chat
    user = update.effective_user
    chat_type = chat.type if chat.type != "supergroup" else "supergroup"
    is_group = chat.type in ("group", "supergroup")
    return str(user.id), str(chat.id), chat_type, is_group


def _api_ctx(api: ApiClient, update: Update) -> dict:
    user_id, chat_id, chat_type, _ = _ctx(update)
    return {
        "telegram_user_id": user_id,
        "telegram_chat_id": chat_id,
        "telegram_chat_type": "private" if chat_type == "private" else chat_type,
    }


def _formatter(localization: dict) -> Formatter:
    return Formatter(localization)


async def _localization(api: ApiClient) -> dict:
    try:
        response = await api.get("/api/v2/telegram/localization")
        return response.get("data", {})
    except Exception:
        return {}


async def _access(api: ApiClient, update: Update) -> dict:
    try:
        response = await api.get("/api/v2/telegram/access", **_api_ctx(api, update))
        return response.get("data", {})
    except Exception:
        logger.exception("telegram access lookup failed")
        chat = update.effective_chat
        private = bool(chat and chat.type == "private")
        return {
            "mode": "private" if private else "group",
            "linked": False,
            "modules": {},
            "accountHelp": private,
        }


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, state: BotState) -> None:
    user_id, chat_id, _, is_group = _ctx(update)
    await state.reset(chat_id, user_id)
    access = await _access(api, update)
    modules = access.get("modules") or {}
    private = access.get("mode") == "private"
    welcome = "Welcome to HollyWing Motor bot.\nសូមស្វាគមន៍មកកាន់ HollyWing Motor"
    reason = access.get("reason")
    if reason:
        welcome = f"{welcome}\n\n{reason}"
    await update.message.reply_text(
        welcome,
        reply_markup=kb.main_menu(modules, private, selective=is_group),
        reply_to_message_id=update.message.message_id if is_group else None,
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not update.message:
        return
    is_group = chat.type in ("group", "supergroup")
    title = chat.title or chat.username or "this chat"
    lines = [
        f"Chat ID: {chat.id}",
        f"Type: {chat.type}",
        f"Title: {title}",
    ]
    if user:
        lines.append(f"Your user ID: {user.id}")
    lines.extend(
        [
            "",
            "Paste Chat ID into Settings → Telegram → Chat / Group ID.",
            "បិទ Chat ID ក្នុង Settings → Telegram → Chat / Group ID។",
        ]
    )
    await update.message.reply_text(
        "\n".join(lines),
        reply_to_message_id=update.message.message_id if is_group else None,
    )


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


async def _reply(
    update: Update,
    text: str,
    markup,
    is_group: bool,
) -> None:
    await update.message.reply_text(
        text,
        reply_markup=markup,
        reply_to_message_id=update.message.message_id if is_group else None,
    )


async def _show_finance_report(
    update: Update,
    api: ApiClient,
    state: BotState,
    report: str,
    period: str,
    page: int = 1,
) -> None:
    user_id, chat_id, _, is_group = _ctx(update)
    fmt = _formatter(await _localization(api))
    path_map = {
        "income": "/api/v2/telegram/income",
        "expenses": "/api/v2/telegram/expenses",
        "summary": "/api/v2/telegram/finance-summary",
    }
    try:
        response = await api.get(
            path_map[report],
            params={"period": period, "page": page, "limit": PAGE_SIZE},
            **_api_ctx(api, update),
        )
    except Exception:
        await _reply(update, fmt.tr("Failed to load report.", "ផ្ទុករបាយការណ៍មិនបានសម្រេច។"), kb.finance_menu(is_group), is_group)
        return
    meta = response.get("meta", {})
    items = response.get("data", [])
    total = int(meta.get("total") or 0)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    title = _report_title(fmt, report, period)
    lines = [title, ""]
    if report == "summary":
        data = response.get("data", {})
        lines = _finance_summary_lines(fmt, data, title)
    else:
        for row in items:
            label = row.get("paymentNo") or row.get("expenseNo") or "—"
            amount = row.get("amount")
            event_at = row.get("paidAt") or row.get("date")
            suffix = f" — {fmt.format_datetime(event_at)}" if event_at else ""
            lines.append(f"- {label}: {fmt.money(amount) if amount is not None else '—'}{suffix}")
        if meta.get("totalAmount") is not None:
            lines.extend(["", MESSAGE_SEPARATOR, f"{fmt.tr('Total', 'សរុប')}: {fmt.money(meta.get('totalAmount'))}"])
        if not items:
            lines.append(fmt.tr("No records in this period.", "គ្មានកំណត់ត្រាក្នុងរយៈពេលនេះ។"))
    await state.set_page(chat_id, user_id, page, {"report": report, "period": period, "total_pages": total_pages})
    markup = kb.pagination_menu(page, total_pages, is_group) if total_pages > 1 else kb.period_menu(True, is_group)
    await _reply(update, "\n".join(lines), markup, is_group)


async def _show_motorcycles(update: Update, api: ApiClient, state: BotState, view: str, page: int = 1) -> None:
    user_id, chat_id, _, is_group = _ctx(update)
    fmt = _formatter(await _localization(api))
    try:
        response = await api.get(
            "/api/v2/telegram/motorcycles",
            params={"view": view.lower(), "page": page, "limit": PAGE_SIZE},
            **_api_ctx(api, update),
        )
    except Exception:
        await _reply(update, fmt.tr("Failed to load motorcycles.", "ផ្ទុកម៉ូតូមិនបានសម្រេច។"), kb.motorcycle_view_menu(is_group), is_group)
        return
    meta = response.get("meta", {})
    items = response.get("data", [])
    counts = meta.get("counts") or {}
    total = int(meta.get("total") or 0)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    lines = [fmt.tr(f"🏍 Motorcycles — {view}", f"🏍 ម៉ូតូ — {view}"), ""]
    if view.lower() == "all" and counts:
        for status, count in counts.items():
            lines.append(f"{status}: {count}")
    for row in items:
        lines.append(f"- {row.get('code')} {row.get('model')} ({row.get('plate') or ''}) — {row.get('status')}")
    if not items and view.lower() != "all":
        lines.append(fmt.tr("No motorcycles found.", "រកមិនឃើញម៉ូតូ។"))
    await state.set_page(chat_id, user_id, page, {"view": view, "module": "motorcycles", "total_pages": total_pages})
    markup = kb.pagination_menu(page, total_pages, is_group) if total_pages > 1 else kb.motorcycle_view_menu(is_group)
    await _reply(update, "\n".join(lines), markup, is_group)


async def _show_customers(update: Update, api: ApiClient, state: BotState, view: str, period: str, page: int = 1) -> None:
    user_id, chat_id, _, is_group = _ctx(update)
    fmt = _formatter(await _localization(api))
    try:
        response = await api.get(
            "/api/v2/telegram/customers",
            params={"view": view.lower().replace(" ", "_"), "period": period, "page": page, "limit": PAGE_SIZE},
            **_api_ctx(api, update),
        )
    except Exception:
        await _reply(update, fmt.tr("Failed to load customers.", "ផ្ទុកអតិថិជនមិនបានសម្រេច។"), kb.customer_view_menu(is_group), is_group)
        return
    meta = response.get("meta", {})
    items = response.get("data", [])
    total = int(meta.get("total") or 0)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    lines = [fmt.tr(f"👥 Customers — {view}", f"👥 អតិថិជន — {view}"), ""]
    for row in items:
        name = row.get("fullName") or "—"
        phone = row.get("phone") or ""
        lines.append(f"- {row.get('code')} {name} {phone}".strip())
    if not items:
        lines.append(fmt.tr("No customers found.", "រកមិនឃើញអតិថិជន។"))
    await state.set_page(chat_id, user_id, page, {"view": view, "period": period, "module": "customers", "total_pages": total_pages})
    markup = kb.pagination_menu(page, total_pages, is_group) if total_pages > 1 else kb.customer_view_menu(is_group)
    await _reply(update, "\n".join(lines), markup, is_group)


async def _show_rentals(update: Update, api: ApiClient, state: BotState, view: str, period: str, page: int = 1) -> None:
    user_id, chat_id, _, is_group = _ctx(update)
    fmt = _formatter(await _localization(api))
    try:
        response = await api.get(
            "/api/v2/telegram/rentals",
            params={"view": view.lower().replace(" ", "_"), "period": period, "page": page, "limit": PAGE_SIZE},
            **_api_ctx(api, update),
        )
    except Exception:
        await _reply(update, fmt.tr("Failed to load rentals.", "ផ្ទុកការជួលមិនបានសម្រេច។"), kb.rental_view_menu(is_group), is_group)
        return
    meta = response.get("meta", {})
    items = response.get("data", [])
    total = int(meta.get("total") or 0)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    lines = [fmt.tr(f"📋 Rentals — {view}", f"📋 ការជួល — {view}"), ""]
    for row in items:
        date_text = fmt.format_datetime(row.get("startDate")) if row.get("startDate") else ""
        lines.append(
            f"- {row.get('rentalNo')} {row.get('customer') or '—'} — {row.get('status')} "
            f"{fmt.money(row.get('outstanding')) if row.get('outstanding') is not None else ''}"
            f"{f' — {date_text}' if date_text else ''}"
        )
    if not items:
        lines.append(fmt.tr("No rentals found.", "រកមិនឃើញការជួល។"))
    await state.set_page(chat_id, user_id, page, {"view": view, "period": period, "module": "rentals", "total_pages": total_pages})
    markup = kb.pagination_menu(page, total_pages, is_group) if total_pages > 1 else kb.rental_view_menu(is_group)
    await _reply(update, "\n".join(lines), markup, is_group)


async def _account_help(update: Update, api: ApiClient, is_group: bool) -> None:
    fmt = _formatter(await _localization(api))
    text = fmt.tr(
        "🔐 Account Help\n\nLink: sign in on the web → profile → generate link code → /link CODE here.\n"
        "Forgot password: tap Forgot Password below (linked private chat only).\n"
        "Never share passwords or codes.",
        "🔐 ជំនួយគណនី\n\nភ្ជាប់: ចូលកម្មវិធី → បង្កើតលេខកូដ → /link CODE\n"
        "ភ្លេចពាក្យសម្ងាត់: ចុច Forgot Password (ជាមួយគណនីភ្ជាប់)។",
    )
    await _reply(update, text, kb.account_help_menu(is_group), is_group)


async def _forgot_password_start(update: Update, api: ApiClient, state: BotState, is_group: bool) -> None:
    user_id, chat_id, _, _ = _ctx(update)
    if is_group:
        await _reply(update, "Password reset is only available in a private linked chat.", kb.account_help_menu(False), False)
        return
    try:
        await api.post("/api/v2/telegram/password-reset/request", {}, **_api_ctx(api, update))
        await state.set_reset_flow(chat_id, user_id, "await_code")
        await _reply(
            update,
            "If your account is eligible, a 6-digit code was sent here. Reply with the code.",
            kb.custom_range_menu(False),
            False,
        )
    except Exception:
        await _reply(update, "Unable to start password reset.", kb.account_help_menu(False), False)


async def _verify_reset_code(update: Update, api: ApiClient, state: BotState, code: str) -> None:
    user_id, chat_id, _, _ = _ctx(update)
    try:
        response = await api.post(
            "/api/v2/telegram/password-reset/verify",
            {"code": code.strip()},
            **_api_ctx(api, update),
        )
        handoff = response.get("data", {}).get("handoffToken")
        base = api.base_url.rstrip("/")
        if "localhost" in base or "127.0.0.1" in base:
            web_base = base.replace(":8000", ":3000")
        else:
            web_base = base
        link = f"{web_base}/auth/reset-password?handoff={handoff}"
        await state.set_reset_flow(chat_id, user_id, None)
        await update.message.reply_text(
            f"Open this link within 10 minutes to set a new password (one-time use):\n{link}",
            reply_markup=kb.account_help_menu(False),
        )
    except Exception:
        await update.message.reply_text(
            "Invalid or expired code. Request a new code from Account Help.",
            reply_markup=kb.account_help_menu(False),
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, api: ApiClient, state: BotState) -> None:
    text = (update.message.text or "").strip()
    user_id, chat_id, _, is_group = _ctx(update)
    nav = await state.get_nav(chat_id, user_id)
    nav_data = nav.get("data", {})
    access = await _access(api, update)
    modules = access.get("modules") or {}
    private = access.get("mode") == "private"

    reset_step = await state.get_reset_flow(chat_id, user_id)
    if reset_step == "await_code" and text.isdigit():
        await _verify_reset_code(update, api, state, text)
        return

    if nav_data.get("mode") == "custom_range":
        try:
            datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            await _reply(update, "Send date as YYYY-MM-DD", kb.custom_range_menu(is_group), is_group)
            return
        if nav_data.get("step") == "start":
            nav_data["step"] = "end"
            nav_data["start"] = text
            nav["data"] = nav_data
            await state.set_nav(chat_id, user_id, nav)
            await _reply(update, "Start saved. Send end date (YYYY-MM-DD):", kb.custom_range_menu(is_group), is_group)
            return
        start_text = nav_data.get("start")
        end_value = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
        start_value = datetime.strptime(start_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        report = nav_data.get("report", "summary")
        nav_data.pop("mode", None)
        nav["data"] = nav_data
        await state.set_nav(chat_id, user_id, nav)
        try:
            response = await api.get(
                "/api/v2/telegram/finance-summary" if report == "summary" else f"/api/v2/telegram/{report}",
                params={"start": start_value.isoformat(), "end": end_value.isoformat(), "page": 1, "limit": PAGE_SIZE},
                **_api_ctx(api, update),
            )
            fmt = _formatter(await _localization(api))
            data = response.get("data", {})
            if isinstance(data, list):
                data = data[0] if data else {}
            title = fmt.tr("💰 Summary (custom range)", "💰 សង្ខេប (ចន្លោះថ្ងៃ)")
            summary_lines = _finance_summary_lines(fmt, data, title)
            summary_lines.extend(["", MESSAGE_SEPARATOR, f"{start_text} → {text}"])
            msg = "\n".join(summary_lines)
            await _reply(update, msg, kb.period_menu(True, is_group), is_group)
        except Exception:
            await _reply(update, "Failed to load custom range.", kb.finance_menu(is_group), is_group)
        return

    if text == kb.BTN_MAIN_MENU:
        await state.reset(chat_id, user_id)
        await _reply(update, "Main menu", kb.main_menu(modules, private, is_group), is_group)
        return

    if text == kb.BTN_BACK:
        await state.pop(chat_id, user_id)
        level = (await state.get_nav(chat_id, user_id))["stack"][-1]
        if level == "finance":
            await _reply(update, "Finance", kb.finance_menu(is_group), is_group)
        elif level == "motorcycles":
            await _reply(update, "Motorcycles", kb.motorcycle_view_menu(is_group), is_group)
        elif level == "customers":
            await _reply(update, "Customers", kb.customer_view_menu(is_group), is_group)
        elif level == "rentals":
            await _reply(update, "Rentals", kb.rental_view_menu(is_group), is_group)
        elif level == "account":
            await _account_help(update, api, is_group)
        else:
            await _reply(update, "Main menu", kb.main_menu(modules, private, is_group), is_group)
        return

    if text in (kb.BTN_PREV, kb.BTN_NEXT):
        page_state = await state.get_page(chat_id, user_id)
        page = int(page_state.get("page") or 1)
        meta = page_state.get("meta") or {}
        total_pages = int(meta.get("total_pages") or 1)
        page = page - 1 if text == kb.BTN_PREV else page + 1
        page = max(1, min(page, total_pages))
        module = meta.get("module")
        if meta.get("report"):
            await _show_finance_report(update, api, state, meta["report"], meta.get("period", "today"), page)
        elif module == "motorcycles":
            await _show_motorcycles(update, api, state, meta.get("view", "all"), page)
        elif module == "customers":
            await _show_customers(update, api, state, meta.get("view", "all"), meta.get("period", "all"), page)
        elif module == "rentals":
            await _show_rentals(update, api, state, meta.get("view", "all"), meta.get("period", "all"), page)
        return

    if text == "💰 Finance" and modules.get("finance"):
        await state.push(chat_id, user_id, "finance")
        await _reply(update, "Finance reports", kb.finance_menu(is_group), is_group)
        return
    if text == "🏍 Motorcycles" and modules.get("motorcycles"):
        await state.push(chat_id, user_id, "motorcycles")
        await _reply(update, "Choose motorcycle view", kb.motorcycle_view_menu(is_group), is_group)
        return
    if text == "👥 Customers" and modules.get("customers"):
        await state.push(chat_id, user_id, "customers")
        await _reply(update, "Choose customer view", kb.customer_view_menu(is_group), is_group)
        return
    if text == "📋 Rentals" and modules.get("rentals"):
        await state.push(chat_id, user_id, "rentals")
        await _reply(update, "Choose rental view", kb.rental_view_menu(is_group), is_group)
        return
    if text == "🔐 Account Help" and private:
        await state.push(chat_id, user_id, "account")
        await _account_help(update, api, is_group)
        return
    if text == "🔗 Link Account" and private:
        await update.message.reply_text("Generate a link code in the web app profile, then send /link CODE here.")
        return
    if text == "🔑 Forgot Password" and private:
        await _forgot_password_start(update, api, state, is_group)
        return

    if text in ("💵 Income", "📤 Expenses", "📊 Summary"):
        report = {"💵 Income": "income", "📤 Expenses": "expenses", "📊 Summary": "summary"}[text]
        nav_data["report"] = report
        nav["data"] = nav_data
        await state.set_nav(chat_id, user_id, nav)
        await _reply(update, "Select period", kb.period_menu(True, is_group), is_group)
        return

    if text in kb.PERIOD_API:
        period = kb.PERIOD_API[text]
        report = nav_data.get("report", "summary")
        if report:
            await _show_finance_report(update, api, state, report, period)
        elif nav_data.get("customer_view"):
            await _show_customers(update, api, state, nav_data["customer_view"], period)
        elif nav_data.get("rental_view"):
            await _show_rentals(update, api, state, nav_data["rental_view"], period)
        return

    if text == kb.PERIOD_LABELS["custom"]:
        nav_data["mode"] = "custom_range"
        nav_data["step"] = "start"
        nav["data"] = nav_data
        await state.set_nav(chat_id, user_id, nav)
        await _reply(update, "Send start date (YYYY-MM-DD):", kb.custom_range_menu(is_group), is_group)
        return

    moto_views = {"All", "Available", "Rented", "Maintenance"}
    if text in moto_views:
        await _show_motorcycles(update, api, state, text)
        return

    customer_views = {"All", "New", "Active Rental", "Completed Rental"}
    if text in customer_views:
        if text in ("Active Rental", "Completed Rental"):
            await _show_customers(update, api, state, text, "all")
        else:
            nav_data["customer_view"] = text
            nav["data"] = nav_data
            await state.set_nav(chat_id, user_id, nav)
            await _reply(update, "Select period", kb.period_menu(True, is_group), is_group)
        return

    rental_views = {"All", "Active", "Completed", "Overdue", "Upcoming Returns"}
    if text in rental_views:
        if text == "Upcoming Returns":
            await _show_rentals(update, api, state, text, "all")
        else:
            nav_data["rental_view"] = text
            nav["data"] = nav_data
            await state.set_nav(chat_id, user_id, nav)
            await _reply(update, "Select period", kb.period_menu(True, is_group), is_group)
        return

    await _reply(update, "Choose an option:", kb.main_menu(modules, private, is_group), is_group)
