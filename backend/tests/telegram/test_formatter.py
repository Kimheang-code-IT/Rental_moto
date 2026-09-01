from telegram_bot.formatter import Formatter


def test_money_default_format():
    fmt = Formatter({"currency": "USD", "numberFormat": "1,234.56"})
    assert fmt.money(1234.5) == "1,234.50 USD"


def test_money_european_format():
    fmt = Formatter({"currency": "KHR", "numberFormat": "1.234,56"})
    assert fmt.money(1234.5) == "1.234,50 KHR"


def test_translation_en_and_km():
    en = Formatter({"defaultLanguage": "en"})
    assert en.tr("Income", "ចំណូល") == "Income"
    km = Formatter({"defaultLanguage": "km"})
    assert km.tr("Income", "ចំណូល") == "ចំណូល"


def test_date_formats():
    fmt = Formatter({"dateFormat": "YYYY-MM-DD"})
    assert fmt.format_date("2026-09-01T10:30:00+00:00") == "2026-09-01"
    fmt2 = Formatter({"dateFormat": "D MMM YYYY"})
    assert fmt2.format_date("2026-09-01T10:30:00+00:00") == "1 Sep 2026"


def test_datetime_12h():
    fmt = Formatter({"dateFormat": "DD/MM/YYYY", "timeFormat": "h:mm A"})
    assert fmt.format_datetime("2026-09-01T14:30:00+00:00") == "01/09/2026 2:30 PM"
