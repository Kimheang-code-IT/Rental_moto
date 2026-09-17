from datetime import datetime, timezone

from app.repositories.admin import UserRepository


async def test_duplicate_telegram_link_resolves_to_most_recent(db_session):
    # The production database can contain legacy duplicate links. Lookups must not
    # crash the bot while the next successful link operation cleans them up.
    users = (await UserRepository(db_session).list(None, 1, 10))[0]
    first, second = users[0], users[1]
    first.telegram_user_id = second.telegram_user_id = "legacy-telegram-user"
    first.telegram_chat_id = second.telegram_chat_id = "legacy-telegram-chat"
    first.telegram_linked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second.telegram_linked_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    await db_session.flush()

    linked = await UserRepository(db_session).get_by_telegram_ids(
        "legacy-telegram-user", "legacy-telegram-chat"
    )
    assert linked is not None
    assert linked.id == second.id

    await db_session.rollback()
