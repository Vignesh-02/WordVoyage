from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class SlotWindow:
    slot: str
    start: time
    end: time


SLOT_WINDOWS = (
    SlotWindow("main_reveal", time(hour=13, minute=0), time(hour=14, minute=0)),
    SlotWindow("deep_dive", time(hour=18, minute=0), time(hour=19, minute=0)),
    SlotWindow("quiz", time(hour=21, minute=0), time(hour=22, minute=0)),
)


def resolve_current_slot(now_utc: datetime, target_tz: ZoneInfo) -> str | None:
    local_now = now_utc.astimezone(target_tz)
    current = local_now.time()
    for window in SLOT_WINDOWS:
        if window.start <= current < window.end:
            return window.slot
    return None

