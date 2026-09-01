"""Localization and formatting driven by backend localization settings."""

MONTHS_EN = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


class Formatter:
    def __init__(self, localization: dict | None = None) -> None:
        self.localization = localization or {}
        self.language = self.localization.get("defaultLanguage", "en")
        self.currency = self.localization.get("currency", "USD")
        self.number_format = self.localization.get("numberFormat", "1,234.56")
        self.date_format = self.localization.get("dateFormat", "DD/MM/YYYY")
        self.time_format = self.localization.get("timeFormat", "HH:mm")

    def tr(self, en: str, km: str) -> str:
        return km if self.language == "km" else en

    def money(self, value: float | int | None) -> str:
        value = value or 0
        if self.number_format == "1.234,56":
            text = f"{value:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
        elif self.number_format == "1 234,56":
            text = f"{value:,.2f}".replace(",", "@").replace(".", ",").replace("@", " ")
        else:
            text = f"{value:,.2f}"
        return f"{text} {self.currency}"

    def format_date(self, iso: str | None) -> str:
        if not iso:
            return ""
        from datetime import datetime

        try:
            value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            return iso
        if self.date_format == "YYYY-MM-DD":
            return value.strftime("%Y-%m-%d")
        if self.date_format == "MM/DD/YYYY":
            return value.strftime("%m/%d/%Y")
        if self.date_format == "DD-MM-YYYY":
            return value.strftime("%d-%m-%Y")
        if self.date_format == "D MMM YYYY":
            return f"{value.day} {MONTHS_EN[value.month - 1]} {value.year}"
        return value.strftime("%d/%m/%Y")

    def format_datetime(self, iso: str | None) -> str:
        if not iso:
            return ""
        from datetime import datetime

        try:
            value = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            return iso
        date_part = self.format_date(iso)
        if self.time_format == "h:mm A":
            time_part = value.strftime("%I:%M %p").lstrip("0")
        elif self.time_format == "HH:mm:ss":
            time_part = value.strftime("%H:%M:%S")
        elif self.time_format == "h:mm:ss A":
            time_part = value.strftime("%I:%M:%S %p").lstrip("0")
        else:
            time_part = value.strftime("%H:%M")
        return f"{date_part} {time_part}"
