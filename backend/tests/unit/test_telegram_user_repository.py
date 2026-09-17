from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.repositories.admin import UserRepository


class _CaptureSession:
    def __init__(self) -> None:
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(scalar_one_or_none=lambda: SimpleNamespace(id=2))


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})).lower()


async def test_duplicate_telegram_link_resolves_to_most_recent():
    # Lookups must pick one row when legacy duplicates exist, so the bot does not crash.
    session = _CaptureSession()
    linked = await UserRepository(session).get_by_telegram_ids("legacy-telegram-user", "legacy-telegram-chat")
    sql = _sql(session.statement)

    assert linked.id == 2
    assert "telegram_user_id" in sql
    assert "telegram_chat_id" in sql
    assert "order by users.telegram_linked_at desc" in sql
    assert "limit 1" in sql


async def test_telegram_chat_and_user_lookups_also_limit_to_most_recent():
    session = _CaptureSession()
    repo = UserRepository(session)

    await repo.get_by_telegram_chat("legacy-telegram-chat")
    assert "order by users.telegram_linked_at desc" in _sql(session.statement)
    assert "limit 1" in _sql(session.statement)

    await repo.get_by_telegram_user_id("legacy-telegram-user")
    assert "order by users.telegram_linked_at desc" in _sql(session.statement)
    assert "limit 1" in _sql(session.statement)
