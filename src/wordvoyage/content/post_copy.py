from __future__ import annotations


BASE_TAGS = ["#WordVoyage"]
MAX_BSKY_TEXT = 295

LANGUAGE_TAGS = {
    "spanish": "#LearnSpanish",
    "korean": "#LearnKorean",
    "german": "#LearnGerman",
    "brazilian portuguese": "#LearnPortuguese",
    "portuguese": "#LearnPortuguese",
    "japanese": "#LearnJapanese",
    "french": "#LearnFrench",
    "italian": "#LearnItalian",
    "english": "#LearnEnglish",
}


def _language_tag(language: str) -> str:
    return LANGUAGE_TAGS.get(language.strip().casefold(), f"#Learn{language.replace(' ', '')}")


def hashtags_for(language: str) -> str:
    _ = language
    return " ".join(BASE_TAGS)


def main_hashtags_for(language: str) -> str:
    # Keep main caption compact so etymology + native/english lines don't get truncated.
    return " ".join(["#WordVoyage", _language_tag(language)])


def _fit_caption(body: str, tags: str, max_len: int = MAX_BSKY_TEXT) -> str:
    """
    Keep caption safely below Bluesky post length limits.
    We reserve space for hashtag block and trim body if needed.
    """
    suffix = f"\n\n{tags}"
    if len(suffix) >= max_len:
        return suffix[:max_len]
    body_limit = max_len - len(suffix)
    trimmed = body.strip()
    if len(trimmed) > body_limit:
        trimmed = trimmed[: max(1, body_limit - 3)].rstrip() + "..."
    return f"{trimmed}{suffix}"


def _clip(text: str, max_len: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max(1, max_len - 3)].rstrip() + "..."


def build_main_caption(payload: dict) -> str:
    word = payload["word"]
    language = payload["language"]
    transliteration = payload.get("transliteration", "").strip()
    meaning = _clip(payload.get("meaning", ""), 120)

    translit_line = ""
    if language.strip().casefold() != "english" and transliteration:
        translit_line = f"How to say it: {transliteration}\n"

    body = (
        f"Today's word is '{word}' ({language}).\n"
        f"{translit_line}"
        f"Meaning: {meaning}\n\n"
        "Have you seen this word before?\n"
        "Tell us how you use it."
    )
    return _fit_caption(body, main_hashtags_for(language))


def build_deep_dive_caption(payload: dict) -> str:
    word = payload["word"]
    language = payload["language"]
    native = _clip(payload["usage_example_native"], 85)
    english = _clip(payload["usage_example_translation"], 85)
    english_usage = _clip(payload.get("usage_example_english_with_word") or f"I felt {word} today.", 95)
    body = (
        f"Quick deep-dive on {word}.\n\n"
        f"Native ({language}): {native}\n"
        f"English: {english}\n\n"
        f"English usage: {english_usage}\n"
        "When did you last feel this?"
    )
    return _fit_caption(body, hashtags_for(language))


def build_quiz_caption(payload: dict, has_deep_dive: bool) -> str:
    word = payload["word"]
    language = payload["language"]
    english_usage = payload.get("usage_example_english_with_word") or f"I felt {word} today."
    intro = (
        f"Ready for a {word} challenge?"
        if has_deep_dive
        else f"Quick challenge: {word}"
    )
    body = (
        f"{intro}\n\n"
        f"Example in English: {english_usage}\n\n"
        f"Reply with 1 sentence in {language} + 1 in English.\n"
        "First strong reply gets a shoutout next post.\n"
        "Have you used this word before?"
    )
    return _fit_caption(body, hashtags_for(language))
