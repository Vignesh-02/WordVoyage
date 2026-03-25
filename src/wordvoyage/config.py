import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - safe fallback when deps not installed yet.
    def load_dotenv(*args, **kwargs) -> bool:
        return False


@dataclass(frozen=True)
class Settings:
    database_url: str
    claude_api_key: str
    claude_model: str
    bluesky_handle: str
    bluesky_app_password: str
    timezone: ZoneInfo
    dry_run: bool
    posting_enabled: bool
    force_slot: str | None
    output_dir: Path
    card_theme: str
    allow_curated_fallback: bool
    deep_dive_with_image: bool
    quiz_with_image: bool


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def load_settings() -> Settings:
    # Local development should honor values in .env even if the shell has stale exports.
    load_dotenv(dotenv_path=".env", override=True)
    return Settings(
        database_url=os.getenv("DATABASE_URL", ""),
        claude_api_key=os.getenv("CLAUDE_API_KEY", ""),
        claude_model=_env_str("CLAUDE_MODEL", "claude-haiku-4-5-20251001"),
        bluesky_handle=os.getenv("BLUESKY_HANDLE", ""),
        bluesky_app_password=os.getenv("BLUESKY_APP_PASSWORD", ""),
        timezone=ZoneInfo("America/New_York"),
        dry_run=_env_bool("DRY_RUN", True),
        posting_enabled=_env_bool("POSTING_ENABLED", False),
        force_slot=os.getenv("FORCE_SLOT"),
        output_dir=Path(os.getenv("OUTPUT_DIR", "artifacts")),
        card_theme=_env_str("CARD_THEME", "auto"),
        allow_curated_fallback=_env_bool("ALLOW_CURATED_FALLBACK", False),
        deep_dive_with_image=_env_bool("DEEP_DIVE_WITH_IMAGE", False),
        quiz_with_image=_env_bool("QUIZ_WITH_IMAGE", False),
    )
