from datetime import timedelta

from app.tasks.deadline_alerts import reminder_delta, reminder_label, reminder_value


def test_reminder_delta_uses_configured_duration():
    assert reminder_delta({"deadlineReminderValue": 30, "deadlineReminderUnit": "minutes"}) == timedelta(minutes=30)
    assert reminder_delta({"deadlineReminderValue": 2, "deadlineReminderUnit": "hours"}) == timedelta(hours=2)
    assert reminder_delta({"deadlineReminderValue": 3, "deadlineReminderUnit": "days"}) == timedelta(days=3)


def test_reminder_delta_can_be_disabled():
    assert reminder_delta({"deadlineReminderEnabled": False}) is None
    assert reminder_delta({"enabled": False}) is None


def test_reminder_label_is_readable():
    assert reminder_label(1, "hours") == "1 hour"
    assert reminder_label(3, "days") == "3 days"


def test_invalid_legacy_value_falls_back_safely():
    assert reminder_value({"deadlineReminderValue": "invalid"}) == 1
