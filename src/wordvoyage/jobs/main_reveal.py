from __future__ import annotations

import json
from datetime import datetime

from wordvoyage.content.post_copy import build_main_caption
from wordvoyage.config import Settings
from wordvoyage.generate.claude_writer import generate_word_payload
from wordvoyage.publish.bluesky_client import post_with_image
from wordvoyage.render.card_renderer import render_card_image
from wordvoyage.storage.repositories import claim_word_if_new, load_used_word_terms
from wordvoyage.storage.thread_state import PostRef, set_post_ref, set_slot_context, synthetic_ref


def run_main_reveal_job(settings: Settings, now_utc: datetime) -> None:
    """Main daily word generation + image + post flow."""
    local_now = now_utc.astimezone(settings.timezone)
    target_date = local_now.date()
    day_root = settings.output_dir / target_date.isoformat()
    run_dir = day_root / "main_reveal"
    run_dir.mkdir(parents=True, exist_ok=True)

    used_words = load_used_word_terms(settings.database_url, limit=1200)
    payload = None
    claim_done = False
    max_claim_attempts = 6
    for attempt in range(1, max_claim_attempts + 1):
        candidate = generate_word_payload(
            target_date=target_date,
            api_key=settings.claude_api_key,
            model=settings.claude_model,
            allow_fallback=settings.allow_curated_fallback,
            excluded_words=used_words,
        )
        # In live-post mode with DB configured, claim uniqueness before proceeding.
        if settings.posting_enabled and settings.database_url:
            inserted = claim_word_if_new(settings.database_url, candidate)
            if not inserted:
                used_words.append(candidate["word"])
                print(f"Duplicate word detected in DB, regenerating (attempt {attempt}/{max_claim_attempts}).")
                continue
            claim_done = True
        payload = candidate
        break

    if payload is None:
        raise RuntimeError("Failed to produce a new unique word after multiple attempts.")
    set_slot_context(
        day_root=day_root,
        slot="main_reveal",
        context={
            "word": payload["word"],
            "language": payload["language"],
            "script": payload.get("script", ""),
            "transliteration": payload.get("transliteration", ""),
            "meaning": payload["meaning"],
            "etymology": payload["etymology"],
            "pronunciation": payload["pronunciation"],
            "usage_example_native": payload["usage_example_native"],
            "usage_example_translation": payload["usage_example_translation"],
            "usage_example_english_with_word": payload["usage_example_english_with_word"],
            "source": payload.get("source", "unknown"),
            "fallback_reason": payload.get("fallback_reason"),
        },
    )
    image_path, theme_name = render_card_image(
        payload=payload,
        output_dir=run_dir,
        target_date=target_date,
        theme_override=settings.card_theme,
    )
    caption = build_main_caption(payload)

    intended_post = {
        "mode": "dry_run" if settings.dry_run or not settings.posting_enabled else "live_post",
        "slot": "main_reveal",
        "target_date": target_date.isoformat(),
        "generated_at_utc": now_utc.isoformat(),
        "source": payload.get("source", "unknown"),
        "fallback_reason": payload.get("fallback_reason"),
        "theme": theme_name,
        "word": payload["word"],
        "language": payload["language"],
        "usage_example_native": payload["usage_example_native"],
        "usage_example_translation": payload["usage_example_translation"],
        "usage_example_english_with_word": payload["usage_example_english_with_word"],
        "caption": caption,
        "alt_text": payload["alt_text"],
        "image_path": str(image_path),
        "reply_to_uri": None,
        "reply_to_cid": None,
    }

    log_file = run_dir / "intended_post_main_reveal.json"
    log_file.write_text(json.dumps(intended_post, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated word: {payload['word']} ({payload['language']})")
    print(f"Source: {payload.get('source', 'unknown')}")
    if payload.get("fallback_reason"):
        print(f"Fallback reason: {payload['fallback_reason']}")
    print(f"Theme: {theme_name}")
    print(f"Card image: {image_path}")
    print(f"Intended post log: {log_file}")

    if settings.dry_run or not settings.posting_enabled:
        ref = synthetic_ref(post_date=target_date, slot="main_reveal", word=payload["word"])
        set_post_ref(day_root=day_root, slot="main_reveal", ref=ref)
        print(f"Thread root saved (dry-run): uri={ref.uri}")
        print("Dry-run mode active. Skipping Bluesky publish.")
        return

    post_result = post_with_image(
        handle=settings.bluesky_handle,
        app_password=settings.bluesky_app_password,
        caption=caption,
        alt_text=payload["alt_text"],
        image_path=str(image_path),
    )
    set_post_ref(
        day_root=day_root,
        slot="main_reveal",
        ref=PostRef(uri=post_result["uri"], cid=post_result["cid"]),
    )
    if not claim_done and settings.database_url:
        # Safety net when posting_enabled True but claim step wasn't executed for some reason.
        _ = claim_word_if_new(settings.database_url, payload)
    print(f"Published successfully: {post_result}")
