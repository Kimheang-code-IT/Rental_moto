from telegram import KeyboardButton, ReplyKeyboardMarkup

BTN_MAIN_MENU = "🏠 Main Menu"
BTN_BACK = "⬅ Back"
BTN_PREV = "◀ Prev"
BTN_NEXT = "Next ▶"

PERIOD_LABELS = {
    "all": "📅 All",
    "today": "📅 Today",
    "3_days": "📅 3 Days",
    "1_week": "📅 1 Week",
    "1_month": "📅 1 Month",
    "custom": "📅 Custom Range",
}

PERIOD_API = {
    "📅 All": "all",
    "📅 Today": "today",
    "📅 3 Days": "3_days",
    "📅 1 Week": "1_week",
    "📅 1 Month": "1_month",
}


def _rows(buttons: list[str], per_row: int = 2) -> list[list[KeyboardButton]]:
    rows: list[list[KeyboardButton]] = []
    row: list[KeyboardButton] = []
    for label in buttons:
        row.append(KeyboardButton(label))
        if len(row) >= per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def _nav_footer(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        _rows([BTN_BACK, BTN_MAIN_MENU]),
        resize_keyboard=True,
        selective=selective,
    )


def main_menu(modules: dict[str, bool], private: bool, selective: bool = False) -> ReplyKeyboardMarkup:
    buttons: list[str] = []
    if modules.get("finance"):
        buttons.append("💰 Finance")
    if modules.get("motorcycles"):
        buttons.append("🏍 Motorcycles")
    if modules.get("customers"):
        buttons.append("👥 Customers")
    if modules.get("rentals"):
        buttons.append("📋 Rentals")
    if private:
        buttons.append("🔐 Account Help")
    if not buttons:
        buttons = ["🔐 Account Help"] if private else ["ℹ️ No modules enabled"]
    return ReplyKeyboardMarkup(_rows(buttons), resize_keyboard=True, selective=selective)


def finance_menu(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        _rows(["💵 Income", "📤 Expenses", "📊 Summary", BTN_BACK, BTN_MAIN_MENU]),
        resize_keyboard=True,
        selective=selective,
    )


def period_menu(include_all: bool = True, selective: bool = False) -> ReplyKeyboardMarkup:
    labels = [PERIOD_LABELS["today"], PERIOD_LABELS["3_days"], PERIOD_LABELS["1_week"], PERIOD_LABELS["1_month"]]
    if include_all:
        labels.insert(0, PERIOD_LABELS["all"])
    labels.append(PERIOD_LABELS["custom"])
    labels.extend([BTN_BACK, BTN_MAIN_MENU])
    return ReplyKeyboardMarkup(_rows(labels), resize_keyboard=True, selective=selective)


def motorcycle_view_menu(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        _rows(["All", "Available", "Rented", "Maintenance", BTN_BACK, BTN_MAIN_MENU]),
        resize_keyboard=True,
        selective=selective,
    )


def customer_view_menu(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        _rows(["All", "New", "Active Rental", "Completed Rental", BTN_BACK, BTN_MAIN_MENU]),
        resize_keyboard=True,
        selective=selective,
    )


def rental_view_menu(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        _rows(["All", "Active", "Completed", "Overdue", "Upcoming Returns", BTN_BACK, BTN_MAIN_MENU]),
        resize_keyboard=True,
        selective=selective,
    )


def account_help_menu(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        _rows(["🔗 Link Account", "🔑 Forgot Password", BTN_BACK, BTN_MAIN_MENU]),
        resize_keyboard=True,
        selective=selective,
    )


def pagination_menu(page: int, total_pages: int, selective: bool = False) -> ReplyKeyboardMarkup:
    nav: list[str] = []
    if page > 1:
        nav.append(BTN_PREV)
    if page < total_pages:
        nav.append(BTN_NEXT)
    nav.extend([BTN_BACK, BTN_MAIN_MENU])
    return ReplyKeyboardMarkup(_rows(nav, per_row=2), resize_keyboard=True, selective=selective)


def custom_range_menu(selective: bool = False) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(_rows([BTN_BACK, BTN_MAIN_MENU]), resize_keyboard=True, selective=selective)
