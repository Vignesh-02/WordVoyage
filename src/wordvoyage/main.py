from __future__ import annotations

from datetime import datetime, timezone

from wordvoyage.config import load_settings
from wordvoyage.jobs.deep_dive import run_deep_dive_job
from wordvoyage.jobs.main_reveal import run_main_reveal_job
from wordvoyage.jobs.quiz import run_quiz_job
from wordvoyage.scheduler import resolve_current_slot


def main() -> int:
    settings = load_settings()
    now_utc = datetime.now(timezone.utc)
    slot = settings.force_slot or resolve_current_slot(now_utc=now_utc, target_tz=settings.timezone)

    if slot is None:
        print("No active slot. Exiting.")
        return 0

    if settings.force_slot:
        print(f"FORCE_SLOT active: {settings.force_slot}")

    if slot == "main_reveal":
        run_main_reveal_job(settings=settings, now_utc=now_utc)
    elif slot == "deep_dive":
        run_deep_dive_job(settings=settings, now_utc=now_utc)
    elif slot == "quiz":
        run_quiz_job(settings=settings, now_utc=now_utc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
