from telegram_bot import keyboards as kb


def test_main_menu_private_includes_account_help():
    markup = kb.main_menu({"finance": True, "motorcycles": False, "customers": False, "rentals": True}, private=True)
    labels = [btn.text for row in markup.keyboard for btn in row]
    assert "💰 Finance" in labels
    assert "🔐 Account Help" in labels


def test_main_menu_group_excludes_account_help():
    markup = kb.main_menu({"finance": True, "motorcycles": True, "customers": False, "rentals": True}, private=False)
    labels = [btn.text for row in markup.keyboard for btn in row]
    assert "🔐 Account Help" not in labels


def test_period_api_mapping():
    assert kb.PERIOD_API["📅 1 Week"] == "1_week"
    assert kb.PERIOD_API["📅 All"] == "all"


def test_pagination_keyboard():
    markup = kb.pagination_menu(2, 3)
    labels = [btn.text for row in markup.keyboard for btn in row]
    assert kb.BTN_PREV in labels
    assert kb.BTN_NEXT in labels
