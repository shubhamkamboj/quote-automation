import json
import random
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "generated"
DATA_DIR = ROOT / "data"
STATE_FILE = DATA_DIR / "state.json"
FONT_FILE = ROOT / "fonts" / "NotoSansDevanagari-Regular.ttf"

WIDTH, HEIGHT = 1080, 1800
RNG = random.SystemRandom()

# Quote area inside the diary page.
# This keeps the quote centered in the usable page area rather than at the bottom.
PAGE_TOP = 250
PAGE_BOTTOM = 1450
PAGE_LEFT = 120
PAGE_RIGHT = 960


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def pick_quote_and_template():
    from quote_source import get_quote

    quote, source, priority_line = get_quote()

    templates = sorted(TEMPLATE_DIR.glob("template-*.jpg"))
    if not templates:
        raise RuntimeError("No templates found in templates/.")

    state = load_json(STATE_FILE, {"last_template": None})

    candidates = [
        p for p in templates
        if p.name != state.get("last_template")
    ] or templates

    template = RNG.choice(candidates)

    new_state = {
        **state,
        "last_template": template.name,
        "last_quote_source": source,
        "last_run_utc": datetime.now(timezone.utc).isoformat(),
    }
    save_json(STATE_FILE, new_state)

    return quote, template, source, priority_line


def get_font(size):
    if not FONT_FILE.exists():
        raise RuntimeError(f"Hindi font not found: {FONT_FILE}")
    return ImageFont.truetype(str(FONT_FILE), size=size)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        candidate = word if not current else current + " " + word
        bbox = draw.textbbox((0, 0), candidate, font=font)

        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return "\n".join(lines)


def fit_quote(draw, quote, max_width, max_height):
    for size in range(62, 27, -2):
        font = get_font(size)
        wrapped = wrap_text(draw, quote, font, max_width)

        bbox = draw.multiline_textbbox(
            (0, 0),
            wrapped,
            font=font,
            spacing=18,
            align="center",
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if text_width <= max_width and text_height <= max_height:
            return wrapped, font

    font = get_font(28)
    return wrap_text(draw, quote, font, max_width), font


def render(quote, template_path):
    image = (
        Image.open(template_path)
        .convert("RGB")
        .resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    )

    draw = ImageDraw.Draw(image)

    # Remove the old bottom quote-card behavior entirely.
    # The selected templates are already blank, so the quote is drawn directly
    # onto the diary page.

    max_width = PAGE_RIGHT - PAGE_LEFT
    max_height = PAGE_BOTTOM - PAGE_TOP

    wrapped, font = fit_quote(
        draw,
        quote,
        max_width=max_width,
        max_height=max_height,
    )

    # True visual center of the usable diary page.
    center_x = (PAGE_LEFT + PAGE_RIGHT) // 2
    center_y = (PAGE_TOP + PAGE_BOTTOM) // 2

    bbox = draw.multiline_textbbox(
        (0, 0),
        wrapped,
        font=font,
        spacing=18,
        align="center",
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Very subtle quote color; no large background box.
    text_color = (72, 55, 42)

    draw.multiline_text(
        (center_x, center_y),
        wrapped,
        font=font,
        anchor="mm",
        align="center",
        spacing=18,
        fill=text_color,
    )

    # Small ornamental divider below the quote.
    divider_y = center_y + (text_height // 2) + 50
    divider_width = 160

    if divider_y < PAGE_BOTTOM - 40:
        draw.line(
            (
                center_x - divider_width,
                divider_y,
                center_x - 25,
                divider_y,
            ),
            fill=(150, 116, 79),
            width=2,
        )

        draw.text(
            (center_x, divider_y),
            "♥",
            font=get_font(24),
            anchor="mm",
            fill=(150, 116, 79),
        )

        draw.line(
            (
                center_x + 25,
                divider_y,
                center_x + divider_width,
                divider_y,
            ),
            fill=(150, 116, 79),
            width=2,
        )

    return image


def main():
    quote, template, source, priority_line = pick_quote_and_template()
    image = render(quote, template)

    now = datetime.now(timezone.utc)
    filename = f"quote-{now.strftime('%Y%m%d-%H%M%S-%f')}.jpg"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = OUTPUT_DIR / filename
    latest = OUTPUT_DIR / "latest.jpg"

    image.save(
        output,
        format="JPEG",
        quality=94,
        optimize=True,
        progressive=False,
    )

    image.save(
        latest,
        format="JPEG",
        quality=94,
        optimize=True,
        progressive=False,
    )

    from quote_source import generate_hashtags

    metadata = {
        "quote": quote,
        "template": template.name,
        "filename": filename,
        "latest_filename": "latest.jpg",
        "generated_at_utc": now.isoformat(),
        "quote_source": source,
        "priority_line": priority_line,
        "hashtags": generate_hashtags(quote),
    }

    (OUTPUT_DIR / "latest.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
