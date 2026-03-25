from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from wordvoyage.scheduler import resolve_current_slot


def test_main_reveal_window():
    # 17:30 UTC = 13:30 ET during DST
    now_utc = datetime(2026, 7, 10, 17, 30, tzinfo=timezone.utc)
    assert resolve_current_slot(now_utc, ZoneInfo("America/New_York")) == "main_reveal"


def test_outside_any_window():
    now_utc = datetime(2026, 7, 10, 3, 0, tzinfo=timezone.utc)
    assert resolve_current_slot(now_utc, ZoneInfo("America/New_York")) is None

