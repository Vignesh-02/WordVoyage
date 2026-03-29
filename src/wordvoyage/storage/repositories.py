from __future__ import annotations

from datetime import date
from typing import Any

from wordvoyage.storage.db import connect


def upsert_daily_post_stub(post_date: date, slot: str) -> None:
    """TODO: Upsert daily_posts by (post_date, slot) for idempotent runs."""
    _ = (post_date, slot)


def load_used_word_terms(database_url: str, limit: int = 1000) -> list[str]:
    """
    Return recent used word terms for prompt-level avoidance.
    """
    if not database_url:
        return []
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT word
                FROM words
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    return [str(r[0]).strip() for r in rows if str(r[0]).strip()]


def claim_word_if_new(database_url: str, payload: dict[str, Any]) -> bool:
    """
    Insert selected word into words table using uniqueness as the source of truth.
    Returns True when inserted; False when duplicate already exists.
    """
    if not database_url:
        return True
    word = str(payload.get("word", "")).strip()
    language = str(payload.get("language", "")).strip()
    if not word or not language:
        return False
    with connect(database_url) as conn:
        with conn.cursor() as cur:
            # Global case-insensitive guard: avoid repeats like "Komorebi" vs "komorebi"
            # regardless of language label variations.
            cur.execute(
                """
                SELECT 1
                FROM words
                WHERE lower(word) = lower(%s)
                LIMIT 1
                """,
                (word,),
            )
            if cur.fetchone() is not None:
                return False

            cur.execute(
                """
                INSERT INTO words (
                    word,
                    language_name,
                    script_form,
                    transliteration,
                    pronunciation_guide,
                    meaning,
                    etymology,
                    usage_example,
                    usage_example_translation,
                    source_notes,
                    is_untranslatable
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (word, language_name) DO NOTHING
                RETURNING id
                """,
                (
                    word,
                    language,
                    payload.get("script") or None,
                    payload.get("transliteration") or None,
                    payload.get("pronunciation") or None,
                    payload["meaning"],
                    payload["etymology"],
                    payload["usage_example_native"],
                    payload["usage_example_translation"],
                    payload.get("source"),
                    True,
                ),
            )
            inserted = cur.fetchone() is not None
        conn.commit()
    return inserted
