from datetime import datetime, timedelta, timezone


def parse_period(period: str) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    p = (period or "today").strip().lower()
    if p in ("today", "day"):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if p in ("3_days", "3days", "last_3_days"):
        start = (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if p in ("7_days", "7days", "last_7_days", "week"):
        start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if p in ("1_month", "1month", "month", "30_days", "last_30_days"):
        start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    raise ValueError(f"Unknown period: {period}")
