import re
from typing import Any

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.core.errors import ValidationError

SORT_PATTERN = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)(:(asc|desc))?$")


def apply_sorting(stmt: Select, sort: str | None, allowed: dict[str, ColumnElement], default: str) -> Select:
    key = default
    direction = "asc"
    if sort:
        match = SORT_PATTERN.match(sort.strip())
        if not match:
            raise ValidationError(f"Invalid sort expression: {sort}")
        key = match.group(1)
        direction = match.group(3) or "asc"
        if key not in allowed:
            raise ValidationError(f"Sort field not allowed: {key}")
    column = allowed[key]
    return stmt.order_by(desc(column) if direction == "desc" else asc(column))


def build_q_filter(q: str | None, columns: list[ColumnElement]) -> ColumnElement | None:
    if not q or not q.strip() or not columns:
        return None
    term = f"%{q.strip().lower()}%"
    return or_(*(func.lower(col).like(term) for col in columns))


class PaginationResult:
    def __init__(self, items: list[Any], total: int, page: int, limit: int) -> None:
        self.items = items
        self.total = total
        self.page = page
        self.limit = limit

    @property
    def meta(self) -> dict:
        total_pages = (self.total + self.limit - 1) // self.limit if self.limit else 0
        return {"page": self.page, "limit": self.limit, "total": self.total, "totalPages": total_pages}


async def paginate(session, stmt: Select, page: int, limit: int) -> PaginationResult:
    page = max(1, page)
    limit = min(max(1, limit), 100)
    total_result = await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
    total = int(total_result.scalar() or 0)
    result = await session.execute(stmt.offset((page - 1) * limit).limit(limit))
    items = list(result.scalars().all())
    return PaginationResult(items=items, total=total, page=page, limit=limit)
