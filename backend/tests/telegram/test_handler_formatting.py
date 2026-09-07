from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from telegram_bot.formatter import Formatter
from telegram_bot.handlers import _finance_summary_lines, _report_title, cmd_id


def test_finance_summary_uses_dash_rows_and_readable_period():
    fmt = Formatter({"currency": "USD"})
    title = _report_title(fmt, "summary", "3_days")
    lines = _finance_summary_lines(
        fmt,
        {"income": 0, "expense": 0, "netIncome": 0, "outstanding": 0},
        title,
    )
    assert lines[0] == "💰 Summary (3 days)"
    assert lines[1] == ""
    assert lines[2] == "- Income: 0.00 USD"
    assert lines[-1] == "- Outstanding: 0.00 USD"


@pytest.mark.asyncio
async def test_cmd_id_replies_with_group_chat_id():
    message = SimpleNamespace(reply_text=AsyncMock(), message_id=42)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(
            id=-1001234567890,
            type="supergroup",
            title="HollyWing staff",
            username=None,
        ),
        effective_user=SimpleNamespace(id=555),
        message=message,
    )

    await cmd_id(update, SimpleNamespace())

    message.reply_text.assert_awaited_once()
    text = message.reply_text.await_args.args[0]
    assert "Chat ID: -1001234567890" in text
    assert "Type: supergroup" in text
    assert "Your user ID: 555" in text
    assert message.reply_text.await_args.kwargs["reply_to_message_id"] == 42
