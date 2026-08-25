import json
import random
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from quote_source import get_next_post

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
OUT = ROOT / "generated"
STATE = ROOT / "data" / "state.json"
FONT = ROOT / "fonts" / "NotoSansDevanagari-Regular.ttf"

W, H = 1080, 1800


def load(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError:
        return default


def save(path, data):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def pick_template():
    templates = sorted(
        TEMPLATES.glob("template-*.jpg")
    )

    if not templates:
        raise RuntimeError(
            "No templates found."
        )

    state = load(
        STATE,
        {},
    )

    candidates = [
        item
        for item in templates
        if item.name
        != state.get("last_template")
    ] or templates

    template = random.SystemRandom().choice(
        candidates
    )

    state["last_template"] = template.name
    state["last_run_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    save(
        STATE,
        state,
    )

    return template


def font(size):
    return ImageFont.truetype(
        str(FONT),
        size,
    )


def wrap(draw, text, fnt, max_width):
    lines = []
    current = ""

    for word in text.split():
        candidate = (
            word
            if not current
            else f"{current} {word}"
        )

        if draw.textbbox(
            (0, 0),
            candidate,
            font=fnt,
        )[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return "\n".join(lines)


def fit(draw, quote, max_width, max_height):
    for size in range(58, 27, -2):
        fnt = font(size)
        text = wrap(
            draw,
            quote,
            fnt,
            max_width,
        )

        bbox = draw.multiline_textbbox(
            (0, 0),
            text,
            font=fnt,
            spacing=18,
            align="center",
        )

        if (
            bbox[2] - bbox[0] <= max_width
            and bbox[3] - bbox[1] <= max_height
        ):
            return text, fnt

    fnt = font(28)
    return (
        wrap(
            draw,
            quote,
            fnt,
            max_width,
        ),
        fnt,
    )


def render(quote, template, highlighted_words=None):
    image = (
        Image.open(template)
        .convert("RGB")
        .resize(
            (W, H),
            Image.Resampling.LANCZOS,
        )
    )

    draw = ImageDraw.Draw(image)

    left, right = 115, 965
    top, bottom = 170, 1690

    text, fnt = fit(
        draw,
        quote,
        right - left - 80,
        bottom - top - 80,
    )

    cx = (left + right) // 2
    cy = (top + bottom) // 2

    bbox = draw.multiline_textbbox(
        (0, 0),
        text,
        font=fnt,
        spacing=18,
        align="center",
    )

    text_height = bbox[3] - bbox[1]

    # Render quote line-by-line so highlighted words can use a distinct color.
    highlighted_words = [str(w).strip() for w in (highlighted_words or []) if str(w).strip()]

    def _contains_highlight(line):
        return any(h in line for h in highlighted_words)

    lines = text.split("\n")
    line_heights = []
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fnt)
        line_heights.append(bb[3] - bb[1])

    line_spacing = 18
    total_h = sum(line_heights) + line_spacing * max(0, len(lines) - 1)
    y = cy - total_h / 2

    for idx, line in enumerate(lines):
        bb = draw.textbbox((0, 0), line, font=fnt)
        line_w = bb[2] - bb[0]
        x = cx - line_w / 2

        # Preserve simple wrapping while giving matching words a different color.
        segments = [line]
        if highlighted_words:
            import re
            pattern = "(" + "|".join(re.escape(h) for h in sorted(highlighted_words, key=len, reverse=True)) + ")"
            segments = [seg for seg in re.split(pattern, line) if seg]

        cursor_x = cx - draw.textlength(line, font=fnt) / 2
        for segment in segments:
            fill = (150, 100, 45, 255) if segment.strip() in highlighted_words else (72, 55, 42, 255)
            draw.text((cursor_x, y), segment, font=fnt, fill=fill)
            cursor_x += draw.textlength(segment, font=fnt)

        y += line_heights[idx] + line_spacing

    divider_y = (
        cy
        + text_height // 2
        + 48
    )

    if divider_y < bottom - 25:
        draw.line(
            (
                cx - 106,
                divider_y,
                cx - 26,
                divider_y,
            ),
            fill=(150, 116, 79, 180),
            width=2,
        )

        draw.text(
            (cx, divider_y),
            "♥",
            font=font(24),
            anchor="mm",
            fill=(150, 116, 79, 210),
        )

        draw.line(
            (
                cx + 26,
                divider_y,
                cx + 106,
                divider_y,
            ),
            fill=(150, 116, 79, 180),
            width=2,
        )

    return image


def main():
    result = get_next_post()
    quote = result[0]
    hashtags = result[1]
    source = result[2]
    priority_line = result[3]
    # Newer quote_source versions may return a 5th metadata value.
    highlighted_words = result[4] if len(result) > 4 else []

    template = pick_template()
    image = render(
        quote,
        template,
        highlighted_words,
    )

    now = datetime.now(timezone.utc)
    filename = (
        f"quote-"
        f"{now.strftime('%Y%m%d-%H%M%S-%f')}"
        f".jpg"
    )

    OUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = OUT / filename
    latest = OUT / "latest.jpg"

    image.save(
        output,
        "JPEG",
        quality=94,
        optimize=True,
        progressive=False,
    )

    image.save(
        latest,
        "JPEG",
        quality=94,
        optimize=True,
        progressive=False,
    )

    metadata = {
        "quote": quote,
        "hashtags": hashtags,
        "template": template.name,
        "filename": filename,
        "latest_filename": "latest.jpg",
        "generated_at_utc": now.isoformat(),
        "quote_source": source,
        "priority_line": priority_line,
        "highlighted_words": highlighted_words,
    }

    (OUT / "latest.json").write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            metadata,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
