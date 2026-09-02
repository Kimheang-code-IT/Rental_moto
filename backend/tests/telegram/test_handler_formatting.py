from telegram_bot.formatter import Formatter
from telegram_bot.handlers import _finance_summary_lines, _report_title


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
