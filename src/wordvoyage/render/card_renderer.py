from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    top: tuple[int, int, int]
    mid: tuple[int, int, int]
    bottom: tuple[int, int, int]
    glow: tuple[int, int, int, int]
    panel_fill: tuple[int, int, int, int]
    panel_border: tuple[int, int, int, int]
    pill_fill: tuple[int, int, int, int]
    pill_text: str
    heading_text: str
    body_text: str
    muted_text: str


THEMES = {
    "orbital": ThemeSpec(
        name="orbital",
        top=(14, 36, 64),
        mid=(27, 72, 119),
        bottom=(183, 111, 36),
        glow=(255, 203, 128, 125),
        panel_fill=(7, 24, 45, 212),
        panel_border=(233, 188, 115, 210),
        pill_fill=(255, 235, 203, 255),
        pill_text="#22405E",
        heading_text="#FFE9C9",
        body_text="#F8FBFF",
        muted_text="#F0DAB6",
    ),
    "sunset": ThemeSpec(
        name="sunset",
        top=(52, 33, 81),
        mid=(129, 66, 102),
        bottom=(222, 121, 72),
        glow=(255, 191, 146, 130),
        panel_fill=(36, 23, 52, 214),
        panel_border=(255, 209, 160, 212),
        pill_fill=(255, 226, 204, 255),
        pill_text="#4B2D54",
        heading_text="#FFE6CC",
        body_text="#FFF8F2",
        muted_text="#FFD9B7",
    ),
    "minimal": ThemeSpec(
        name="minimal",
        top=(16, 36, 54),
        mid=(24, 66, 88),
        bottom=(90, 127, 151),
        glow=(184, 220, 238, 80),
        panel_fill=(8, 24, 37, 214),
        panel_border=(174, 212, 232, 205),
        pill_fill=(224, 241, 251, 255),
        pill_text="#14344B",
        heading_text="#DDF2FF",
        body_text="#F4FBFF",
        muted_text="#CDE3F1",
    ),
}


def resolve_theme_name(target_date: date, theme_override: str | None) -> str:
    if theme_override and theme_override.lower() != "auto":
        requested = theme_override.lower().strip()
        if requested in THEMES:
            return requested
    names = sorted(THEMES.keys())
    return names[target_date.toordinal() % len(names)]


def _font(size: int, *, bold: bool, unicode_safe: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    latin_bold = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "Avenir Next Demi Bold.ttf",
        "Arial Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ]
    latin_regular = [
        "/System/Library/Fonts/Helvetica.ttc",
        "Avenir Next Regular.ttf",
        "Arial.ttf",
        "DejaVuSans.ttf",
    ]
    unicode_fallback = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "DejaVuSans.ttf",
    ]
    candidates = list(unicode_fallback if unicode_safe else (latin_bold if bold else latin_regular))
    if unicode_safe:
        candidates.extend(latin_bold if bold else latin_regular)
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _line_wrap_px(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    if not text:
        return [""]
    words = text.split(" ")
    if len(words) == 1:
        # Handle CJK/no-space strings by char-based wrapping.
        units = list(text)
        joiner = ""
    else:
        units = words
        joiner = " "

    lines: list[str] = []
    current = ""
    for unit in units:
        proposal = unit if not current else f"{current}{joiner}{unit}"
        if draw.textlength(proposal, font=font) <= max_width:
            current = proposal
            continue
        if current:
            lines.append(current)
        current = unit
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]
    if len(lines) == max_lines and units:
        original = joiner.join(units)
        combined = joiner.join(lines)
        if combined != original:
            last = lines[-1]
            while last and draw.textlength(f"{last}...", font=font) > max_width:
                last = last[:-1]
            lines[-1] = f"{last}..." if last else "..."
    return lines


def _draw_section(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    title: str,
    body: str,
    heading_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    body_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    heading_color: str,
    body_color: str,
    body_max_lines: int,
    trailing_gap: int = 12,
) -> int:
    draw.text((x, y), title, fill=heading_color, font=heading_font)
    heading_h = heading_font.getbbox("Ag")[3] - heading_font.getbbox("Ag")[1]
    y += heading_h + 8
    lines = _line_wrap_px(draw, body, body_font, max_width=width, max_lines=body_max_lines)
    body_h = body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1]
    for line in lines:
        draw.text((x, y), line, fill=body_color, font=body_font)
        y += body_h + 6
    return y + trailing_gap


def _measure_section_height(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    body: str,
    heading_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    body_font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    body_max_lines: int,
) -> int:
    heading_h = heading_font.getbbox("Ag")[3] - heading_font.getbbox("Ag")[1]
    lines = _line_wrap_px(draw, body, body_font, max_width=width, max_lines=body_max_lines)
    body_h = body_font.getbbox("Ag")[3] - body_font.getbbox("Ag")[1]
    return (heading_h + 8) + len(lines) * (body_h + 6)


def _fit_font_for_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    *,
    start_size: int,
    min_size: int,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = start_size
    while size >= min_size:
        f = _font(size, bold=True, unicode_safe=True)
        if draw.textlength(text, font=f) <= max_width:
            return f
        size -= 2
    return _font(min_size, bold=True, unicode_safe=True)


def _clip_text(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(1, limit - 3)].rstrip() + "..."


def render_card_image(
    payload: dict,
    output_dir: Path,
    target_date: date,
    theme_override: str | None = "auto",
) -> tuple[Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    theme_name = resolve_theme_name(target_date=target_date, theme_override=theme_override)
    theme = THEMES[theme_name]

    width, height = 1080, 1350
    image = Image.new("RGBA", (width, height), color=theme.top + (255,))
    draw = ImageDraw.Draw(image)

    # Smooth 3-stop vertical gradient.
    for y in range(height):
        ratio = y / max(1, height - 1)
        if ratio < 0.58:
            t = ratio / 0.58
            r = int(theme.top[0] * (1 - t) + theme.mid[0] * t)
            g = int(theme.top[1] * (1 - t) + theme.mid[1] * t)
            b = int(theme.top[2] * (1 - t) + theme.mid[2] * t)
        else:
            t = (ratio - 0.58) / 0.42
            r = int(theme.mid[0] * (1 - t) + theme.bottom[0] * t)
            g = int(theme.mid[1] * (1 - t) + theme.bottom[1] * t)
            b = int(theme.mid[2] * (1 - t) + theme.bottom[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Soft glow to match avatar vibe.
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    # Softer, slightly shifted glow so top title area stays high-contrast.
    r, g, b, a = theme.glow
    softened_glow = (r, g, b, max(45, int(a * 0.62)))
    gdraw.ellipse((700, -240, 1260, 300), fill=softened_glow)
    glow = glow.filter(ImageFilter.GaussianBlur(64))
    image = Image.alpha_composite(image, glow)
    draw = ImageDraw.Draw(image)

    brand_font = _font(46, bold=True)
    meta_font = _font(27, bold=True, unicode_safe=True)
    heading_font = _font(36, bold=True, unicode_safe=True)
    body_font = _font(31, bold=False, unicode_safe=True)
    footer_font = _font(40, bold=True, unicode_safe=True)

    margin_x = 74
    top_y = 52

    draw.text((margin_x, top_y), "WordVoyage", fill="#F8FBFF", font=brand_font, stroke_width=1, stroke_fill="#0D2137")
    top_y += 78

    # Title priority: use canonical word first, transliteration only as fallback.
    language = str(payload.get("language", "")).strip().casefold()
    translit = str(payload.get("transliteration", "")).strip()
    raw_word = str(payload.get("word", "")).strip()
    _ = language
    word_line = raw_word if raw_word else translit
    word_font = _fit_font_for_text(
        draw,
        word_line,
        max_width=width - (margin_x * 2),
        start_size=82,
        min_size=48,
    )
    draw.text((margin_x, top_y), word_line, fill="#FFFFFF", font=word_font, stroke_width=1, stroke_fill="#0E233B")
    word_w = draw.textlength(word_line, font=word_font)
    word_box = draw.textbbox((margin_x, top_y), word_line, font=word_font, stroke_width=1)
    word_h = word_box[3] - word_box[1]
    pill_text = f"{payload['language']} · {payload['pronunciation']}"
    pill_pad_x = 20
    pill_h = 48
    pill_w = int(draw.textlength(pill_text, font=meta_font) + pill_pad_x * 2)
    pill_w = min(pill_w, width - 2 * margin_x)

    # Prefer adjacent only when title is short enough; otherwise force below for readability.
    pill_x = margin_x + int(word_w) + 18
    pill_y = word_box[1] + max(0, (word_h - pill_h) // 2) + 2
    has_adjacent_room = pill_x + pill_w <= width - margin_x
    title_too_wide = word_w > (width - 2 * margin_x) * 0.56
    title_too_tall = word_h > 86
    if (not has_adjacent_room) or title_too_wide or title_too_tall:
        pill_x = margin_x
        # Use rendered title bottom to prevent overlap with tall glyphs/stroke.
        pill_y = word_box[3] + 14
    else:
        # Even in adjacent mode, never allow vertical overlap with title.
        pill_y = max(pill_y, word_box[3] + 8)

    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=20,
        fill=theme.pill_fill,
    )
    meta_h = meta_font.getbbox("Ag")[3] - meta_font.getbbox("Ag")[1]
    pill_text_y = pill_y + (pill_h - meta_h) // 2 - 1
    draw.text((pill_x + pill_pad_x, pill_text_y), pill_text, fill=theme.pill_text, font=meta_font)
    top_y = max(top_y + word_h + 14, pill_y + pill_h + 12)
    top_y += 22

    panel_x1 = margin_x - 12
    panel_x2 = width - margin_x + 12
    panel_y1 = top_y
    panel_y2 = height - 112
    draw.rounded_rectangle(
        (panel_x1, panel_y1, panel_x2, panel_y2),
        radius=28,
        fill=theme.panel_fill,
        outline=theme.panel_border,
        width=3,
    )

    x = panel_x1 + 26
    section_width = panel_x2 - panel_x1 - 52
    sections = [
        {
            "title": "Meaning",
            "body": _clip_text(payload["meaning"], 165),
            "max_lines": 3,
            "min_lines": 2,
        },
        {
            "title": "Etymology",
            "body": _clip_text(payload["etymology"], 180),
            "max_lines": 3,
            "min_lines": 2,
        },
        {
            "title": "Native Example",
            "body": _clip_text(payload["usage_example_native"], 120),
            "max_lines": 2,
            "min_lines": 1,
        },
        {
            "title": "Native Translation",
            "body": _clip_text(payload["usage_example_translation"], 120),
            "max_lines": 2,
            "min_lines": 1,
        },
        {
            "title": "English Usage",
            "body": _clip_text(
                payload.get("usage_example_english_with_word", payload["usage_example_translation"]),
                120,
            ),
            "max_lines": 2,
            "min_lines": 1,
        },
    ]

    panel_top_pad = 24
    panel_bottom_pad = 24
    available_height = (panel_y2 - panel_bottom_pad) - (panel_y1 + panel_top_pad)
    # Adaptive fitting: preserve Meaning/Etymology readability first, then trim lower-priority
    # sections if panel height gets tight.
    gap_count = max(1, len(sections) - 1)
    min_gap = 10
    max_gap = 84
    while True:
        measured_heights = [
            _measure_section_height(
                draw,
                width=section_width,
                body=section["body"],
                heading_font=heading_font,
                body_font=body_font,
                body_max_lines=section["max_lines"],
            )
            for section in sections
        ]
        content_height = sum(measured_heights)
        if content_height + (gap_count * min_gap) <= available_height:
            break

        reduced = False
        # Reduce lower-priority blocks first to protect Meaning/Etymology.
        for section in sections[::-1]:
            if section["max_lines"] > section["min_lines"]:
                section["max_lines"] -= 1
                reduced = True
                break
        if not reduced:
            break

    raw_gap = (available_height - content_height) // gap_count
    section_gap = max(min_gap, min(max_gap, raw_gap))

    y = panel_y1 + panel_top_pad
    for idx, section in enumerate(sections):
        trailing_gap = section_gap if idx < len(sections) - 1 else 0
        y = _draw_section(
            draw,
            x=x,
            y=y,
            width=section_width,
            title=section["title"],
            body=section["body"],
            heading_font=heading_font,
            body_font=body_font,
            heading_color=theme.heading_text,
            body_color=theme.body_text,
            body_max_lines=section["max_lines"],
            trailing_gap=trailing_gap,
        )

    draw.text((margin_x, height - 82), "#WordVoyage", fill="#FFFDF5", font=footer_font)
    draw.text((width - 390, height - 82), "Word of the Day", fill="#FFFDF5", font=footer_font)

    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in payload["word"]).strip("-")
    file_path = output_dir / f"wordvoyage-{slug}-{theme_name}.png"
    image.convert("RGB").save(file_path, format="PNG")
    return file_path, theme_name
