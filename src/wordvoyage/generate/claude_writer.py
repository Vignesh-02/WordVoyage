from __future__ import annotations

import json
import re
from datetime import date

def _extract_json_object(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return None


def _validate_quality(data: dict) -> str | None:
    blocked_fragments = [
        "hiragana/kanji",
        "kanji + hiragana",
        "hiragana + kanji",
        "kanji and hiragana",
        "hiragana and kanji",
        "placeholder",
        "insert text",
        "lorem ipsum",
    ]
    blocked_chars = ["□", "�"]
    text_fields = [
        str(data.get("word", "")),
        str(data.get("script", "")),
        str(data.get("meaning", "")),
        str(data.get("etymology", "")),
        str(data.get("usage_example_native", "")),
        str(data.get("usage_example_translation", "")),
    ]
    combined = "\n".join(text_fields).casefold()
    for fragment in blocked_fragments:
        if fragment in combined:
            return f"Blocked placeholder fragment detected: {fragment}"
    for ch in blocked_chars:
        if ch in combined:
            return f"Blocked placeholder character detected: {ch}"
    return None


def _sanitize_placeholder_markers(data: dict) -> None:
    patterns = [
        r"kanji\s*(and|\+)\s*hiragana",
        r"hiragana\s*(and|\+)\s*kanji",
    ]

    def clean(value: str) -> str:
        output = value
        for pattern in patterns:
            output = re.sub(pattern, "", output, flags=re.IGNORECASE)
        return " ".join(output.split()).strip(" -–—,;:/")

    word = clean(str(data.get("word", "")))
    script = clean(str(data.get("script", "")))

    # If word becomes empty after cleanup, fall back to transliteration.
    translit = str(data.get("transliteration", "")).strip()
    if not word and translit:
        word = translit

    data["word"] = word
    data["script"] = script


def _validate_etymology_quality(data: dict) -> str | None:
    etymology = str(data.get("etymology", "")).strip()
    lower = etymology.casefold()
    if not etymology:
        return "Etymology is empty."

    # Reject hard speculative/hallucination-prone framing.
    hard_speculative = [
        "thought to come from",
        "believed to come from",
        "unclear origin",
        "unknown origin",
    ]
    for phrase in hard_speculative:
        if phrase in lower:
            return f"Etymology is too speculative ({phrase})."

    # Reject poetic filler in etymology sections.
    poetic_filler = [
        "poetic word",
        "cherished in literature",
        "evoking",
        "blending",
        "celestial",
        "soulful",
        "timeless beauty",
    ]
    for phrase in poetic_filler:
        if phrase in lower:
            return f"Etymology contains non-etymological filler ({phrase})."

    # Prefer linguistic anchors, but do not hard-fail if absent.
    # Claude sometimes returns concise valid etymology without explicit anchor words.
    anchors = [
        "from ",
        "derived from",
        "borrowed from",
        "ultimately from",
        "via ",
        "formed from",
        "compound of",
        "combines ",
        "combining ",
        "+",
    ]
    has_anchor = any(anchor in lower for anchor in anchors)
    if not has_anchor:
        # Without an anchor, soft speculative words are too weak.
        soft_speculative = [
            "possibly",
            "probably",
            "may come from",
            "might come from",
        ]
        for phrase in soft_speculative:
            if phrase in lower:
                return f"Etymology is too speculative ({phrase}) without linguistic anchor."

    # Keep it concise and factual.
    if len(etymology) > 220:
        return "Etymology is too long; likely verbose or speculative."

    return None


def _contains_ipa(text: str) -> bool:
    if "/" in text or "[" in text or "]" in text:
        return True
    # Common IPA Unicode blocks.
    for ch in text:
        cp = ord(ch)
        if 0x0250 <= cp <= 0x02AF:  # IPA Extensions
            return True
        if 0x1D00 <= cp <= 0x1D7F:  # Phonetic Extensions
            return True
        if 0x1D80 <= cp <= 0x1DBF:  # Phonetic Extensions Supplement
            return True
    return False


def _validate_pronunciation_quality(data: dict) -> str | None:
    pronunciation = str(data.get("pronunciation", "")).strip()
    if not pronunciation:
        return "Pronunciation is empty."
    if _contains_ipa(pronunciation):
        return "Pronunciation must be plain-English phonetic, not IPA."
    return None


def _ensure_english_usage_with_word(data: dict) -> None:
    if str(data.get("usage_example_english_with_word", "")).strip():
        return
    word = str(data.get("word", "")).strip()
    meaning = str(data.get("meaning", "")).strip().rstrip(".")
    if word:
        data["usage_example_english_with_word"] = f"I felt {word} today: {meaning}."
    else:
        data["usage_example_english_with_word"] = "I felt this word's meaning in real life today."


def _build_safe_alt_text(data: dict) -> str:
    word = str(data.get("word", "")).strip()
    language = str(data.get("language", "")).strip()
    script = str(data.get("script", "")).strip()
    meaning = str(data.get("meaning", "")).strip()
    native = str(data.get("usage_example_native", "")).strip()
    translation = str(data.get("usage_example_translation", "")).strip()
    usage = str(data.get("usage_example_english_with_word", "")).strip()
    script_part = f" ({script})" if script else ""
    text = (
        f"WordVoyage card for {word}{script_part} in {language}. "
        f"Meaning: {meaning} "
        f"Native example: {native} "
        f"English translation: {translation} "
        f"English usage: {usage}"
    )
    text = " ".join(text.split())
    return text[:497] + "..." if len(text) > 500 else text


def _claude_generate(
    api_key: str,
    model: str,
    target_date: date,
    excluded_words: list[str] | None = None,
) -> tuple[dict | None, str]:
    if not api_key:
        return None, "CLAUDE_API_KEY is missing."
    if not model.strip():
        return None, "CLAUDE_MODEL is blank."
    try:
        import anthropic
    except Exception as exc:
        return None, f"anthropic import failed: {exc}"

    prompt = f"""
You are writing one "word of the day" for a social media account.
Return STRICT JSON only.

Date: {target_date.isoformat()}
Priority languages: Spanish, Japanese, Brazilian Portuguese, French, Korean, Italian, German, English with foreign origins.
Choose a beautiful, culturally rich, or hard-to-translate word.
Use factual, concise etymology. Avoid speculation. If uncertain, choose a different word.
Pronunciation must be plain English phonetics (example: soh-breh-MEH-sah). Do NOT use IPA symbols, slashes, or brackets.
Do not pick a word from the excluded list.

JSON schema:
{{
  "word": "string",
  "language": "string",
  "script": "string (optional, empty if not applicable)",
  "transliteration": "string",
  "pronunciation": "string",
  "meaning": "1 sentence",
  "etymology": "1 concise sentence",
  "usage_example_native": "1 natural sentence in the original language",
  "usage_example_translation": "1 sentence in English translation",
  "usage_example_english_with_word": "1 English sentence that directly uses the word",
  "caption": "Bluesky-safe text under 300 chars",
  "alt_text": "image accessibility text under 500 chars"
}}
"""
    if excluded_words:
        sample = ", ".join(excluded_words[:200])
        prompt += f"\nExcluded words (already used): {sample}\n"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        json_text = _extract_json_object(raw)
        if not json_text:
            return None, "Claude response did not contain valid JSON object."
        data = json.loads(json_text)
        # Backward compatibility if model returns old keys.
        if not data.get("usage_example_native") and data.get("usage_example"):
            data["usage_example_native"] = data["usage_example"]
        if not data.get("usage_example_translation") and data.get("usage_translation"):
            data["usage_example_translation"] = data["usage_translation"]
        _ensure_english_usage_with_word(data)

        required = [
            "word",
            "language",
            "transliteration",
            "pronunciation",
            "meaning",
            "etymology",
            "usage_example_native",
            "usage_example_translation",
            "usage_example_english_with_word",
            "caption",
        ]
        if any(not str(data.get(k, "")).strip() for k in required):
            return None, "Claude JSON missing required fields."
        data.setdefault("script", "")
        _sanitize_placeholder_markers(data)
        if not str(data.get("word", "")).strip():
            return None, "Word became empty after sanitization."
        quality_error = _validate_quality(data)
        if quality_error:
            return None, quality_error
        ety_error = _validate_etymology_quality(data)
        if ety_error:
            return None, ety_error
        pron_error = _validate_pronunciation_quality(data)
        if pron_error:
            return None, pron_error
        # Always use deterministic alt text based on actual payload fields.
        data["alt_text"] = _build_safe_alt_text(data)
        data["source"] = f"claude:{model}"
        return data, ""
    except Exception as exc:
        return None, f"Claude request failed: {exc}"


def generate_word_payload(
    target_date: date,
    api_key: str,
    model: str,
    *,
    allow_fallback: bool,
    max_attempts: int = 3,
    excluded_words: list[str] | None = None,
) -> dict:
    """
    Generate one daily payload.
    Claude-only generation (no curated fallback).
    """
    _ = allow_fallback  # Reserved for backwards compatibility; fallback is intentionally disabled.
    errors: list[str] = []
    for _ in range(max(1, max_attempts)):
        claude_payload, err = _claude_generate(
            api_key=api_key,
            model=model,
            target_date=target_date,
            excluded_words=excluded_words,
        )
        if claude_payload:
            return claude_payload
        errors.append(err)

    raise RuntimeError(f"Claude generation failed. Errors: {' | '.join(errors)}")
