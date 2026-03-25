from __future__ import annotations

import json
from datetime import datetime

from wordvoyage.content.post_copy import build_quiz_caption
from wordvoyage.config import Settings
from wordvoyage.generate.claude_writer import generate_word_payload
from wordvoyage.publish.bluesky_client import post_text, post_with_image
from wordvoyage.render.card_renderer import render_card_image
from wordvoyage.storage.thread_state import (
    PostRef,
    get_post_ref,
    get_slot_context,
    is_synthetic_ref,
    set_post_ref,
    set_slot_context,
    synthetic_ref,
)


def run_quiz_job(settings: Settings, now_utc: datetime) -> None:
    """Optional interactive prompt post for engagement."""
    local_now = now_utc.astimezone(settings.timezone)
    target_date = local_now.date()
    day_root = settings.output_dir / target_date.isoformat()
    run_dir = day_root / "quiz"
    run_dir.mkdir(parents=True, exist_ok=True)

    main_context = get_slot_context(day_root=day_root, slot="main_reveal")
    if main_context:
        payload = dict(main_context)
    else:
        payload = generate_word_payload(
            target_date=target_date,
            api_key=settings.claude_api_key,
            model=settings.claude_model,
            allow_fallback=settings.allow_curated_fallback,
        )
    image_path = None
    theme_name = settings.card_theme
    if settings.quiz_with_image:
        image_path, theme_name = render_card_image(
            payload=payload,
            output_dir=run_dir,
            target_date=target_date,
            theme_override=settings.card_theme,
        )

    deep_context = get_slot_context(day_root=day_root, slot="deep_dive")
    quiz_caption = build_quiz_caption(payload, has_deep_dive=bool(deep_context))
    quiz_alt_text = (
        f"Quiz card for word {payload['word']} in {payload['language']}. "
        "Prompt asks users to write their own sentence."
    )
    main_ref = get_post_ref(day_root=day_root, slot="main_reveal")

    intended_post = {
        "mode": "dry_run" if settings.dry_run or not settings.posting_enabled else "live_post",
        "slot": "quiz",
        "target_date": target_date.isoformat(),
        "generated_at_utc": now_utc.isoformat(),
        "source": payload.get("source", "unknown"),
        "fallback_reason": payload.get("fallback_reason"),
        "theme": theme_name,
        "word": payload["word"],
        "language": payload["language"],
        "caption": quiz_caption,
        "alt_text": quiz_alt_text,
        "image_path": str(image_path) if image_path else None,
        "reply_to_uri": main_ref.uri if main_ref else None,
        "reply_to_cid": main_ref.cid if main_ref else None,
    }

    log_file = run_dir / "intended_post_quiz.json"
    log_file.write_text(json.dumps(intended_post, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated word: {payload['word']} ({payload['language']})")
    print(f"Theme: {theme_name}")
    if image_path:
        print(f"Card image: {image_path}")
    else:
        print("Card image: disabled for quiz (text-only mode).")
    print(f"Intended post log: {log_file}")
    if main_ref:
        print(f"Will reply to main URI: {main_ref.uri}")
    else:
        print("Main post reference not found for today.")
    if main_context:
        print("Quiz content anchored to main_reveal context.")
    else:
        print("Fallback generation used because main_reveal context was missing.")
    if deep_context:
        print("Quiz wording confirmed to build on deep_dive.")

    if settings.dry_run or not settings.posting_enabled:
        ref = synthetic_ref(post_date=target_date, slot="quiz", word=payload["word"])
        set_post_ref(day_root=day_root, slot="quiz", ref=ref)
        set_slot_context(
            day_root=day_root,
            slot="quiz",
            context={
                "word": payload["word"],
                "language": payload["language"],
                "caption": quiz_caption,
            },
        )
        if not main_ref:
            print("Dry-run saved anyway, but live run should post main_reveal first.")
        print(f"Thread reply saved (dry-run): uri={ref.uri}")
        print("Dry-run mode active. Skipping Bluesky publish.")
        return
    if not main_ref:
        print("Skipping publish: main_reveal post ref missing.")
        return
    if is_synthetic_ref(main_ref):
        print("Skipping publish: main_reveal ref is from dry-run and invalid for live reply.")
        print("Run FORCE_SLOT=main_reveal with DRY_RUN=false first, then retry quiz.")
        return

    if image_path:
        post_result = post_with_image(
            handle=settings.bluesky_handle,
            app_password=settings.bluesky_app_password,
            caption=quiz_caption,
            alt_text=quiz_alt_text,
            image_path=str(image_path),
            reply_to_uri=main_ref.uri,
            reply_to_cid=main_ref.cid,
        )
    else:
        post_result = post_text(
            handle=settings.bluesky_handle,
            app_password=settings.bluesky_app_password,
            caption=quiz_caption,
            reply_to_uri=main_ref.uri,
            reply_to_cid=main_ref.cid,
        )
    set_post_ref(
        day_root=day_root,
        slot="quiz",
        ref=PostRef(uri=post_result["uri"], cid=post_result["cid"]),
    )
    set_slot_context(
        day_root=day_root,
        slot="quiz",
        context={
            "word": payload["word"],
            "language": payload["language"],
            "caption": quiz_caption,
        },
    )
    print(f"Published successfully: {post_result}")
