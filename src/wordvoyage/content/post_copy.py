from __future__ import annotations


BASE_TAGS = ["#LangSky", "#WordVoyage"]
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
    tags = [BASE_TAGS[0], _language_tag(language), BASE_TAGS[1]]
    return " ".join(dict.fromkeys(tags))


def main_hashtags_for(language: str) -> str:
    return hashtags_for(language)


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


def _short_meaning_no_ellipsis(text: str, max_len: int = 96) -> str:
    cleaned = " ".join(str(text).split()).strip()
    if not cleaned:
        return ""
    first_sentence = cleaned.split(".")[0].strip()
    candidate = first_sentence if first_sentence else cleaned
    if len(candidate) <= max_len:
        return candidate
    return candidate[:max_len].rstrip(" ,;:-")


def build_main_caption(payload: dict) -> str:
    word = payload["word"]
    language = payload["language"]
    transliteration = payload.get("transliteration", "").strip()
    meaning = _short_meaning_no_ellipsis(payload.get("meaning", ""), 96)

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
        f"You know that feeling? In {language}, it’s {word}.\n\n"
        f"Native ({language}): {native}\n"
        f"English: {english}\n\n"
        f"English usage: {english_usage}\n"
        "How would you use it today?"
    )
    return _fit_caption(body, hashtags_for(language))


def build_quiz_caption(payload: dict, has_deep_dive: bool) -> str:
    word = payload["word"]
    language = payload["language"]
    english_usage = payload.get("usage_example_english_with_word") or f"I felt {word} today."
    intro = (
        f"Quick challenge on {word}."
        if has_deep_dive
        else f"New word challenge: {word}."
    )
    body = (
        f"{intro}\n\n"
        f"Example in English: {english_usage}\n\n"
        f"Reply with 1 sentence in {language} + 1 in English.\n"
        "Best one gets a shoutout next post."
    )
    return _fit_caption(body, hashtags_for(language))
