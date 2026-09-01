from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

MAIN_BUTTONS = [
    ["📋 All Rental Transactions", "🏍 Motorcycle Status"],
    ["💰 Income / Expense", "🔐 Account Help"],
]

PERIOD_BUTTONS = [
    ["Today", "Last 3 Days"],
    ["Last 7 Days", "Last 1 Month"],
    ["Custom Range"],
]

BACK_BUTTON = "⬅ Back"


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(MAIN_BUTTONS, resize_keyboard=True)


def period_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(PERIOD_BUTTONS + [[BACK_BUTTON]], resize_keyboard=True)


def status_group_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Available", callback_data="status:Available"),
                InlineKeyboardButton("Progressing", callback_data="status:Progressing"),
            ],
            [
                InlineKeyboardButton("Maintenance", callback_data="status:Maintenance"),
                InlineKeyboardButton("⬅ Back", callback_data="back:main"),
            ],
        ]
    )


def pagination_keyboard(view: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("◀ Prev", callback_data=f"page:{view}:{page - 1}"))
    if page < total_pages:
        row.append(InlineKeyboardButton("Next ▶", callback_data=f"page:{view}:{page + 1}"))
    row.append(InlineKeyboardButton("⬅ Back", callback_data="back:main"))
    return InlineKeyboardMarkup([row] if row else [["⬅ Back"]])
