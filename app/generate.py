import json
import os
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


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_quote_and_template():
    from quote_source import get_quote

    quote, source, priority_line = get_quote()

    templates = sorted(TEMPLATE_DIR.glob("template-*.jpg"))
    if not templates:
        raise RuntimeError("No templates found in templates/.")

    state = load_json(STATE_FILE, {"last_template": None})
    candidates = [p for p in templates if p.name != state.get("last_template")] or templates
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
    for size in range(58, 28, -2):
        font = get_font(size)
        wrapped = wrap_text(draw, quote, font, max_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=16, align="center")
        if bbox[2] - bbox[0] <= max_width and bbox[3] - bbox[1] <= max_height:
            return wrapped, font
    font = get_font(28)
    return wrap_text(draw, quote, font, max_width), font


def render(quote, template_path):
    image = Image.open(template_path).convert("RGB").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image, "RGBA")

    # The supplied templates contain a sample quote near the bottom.
    # Cover that area with a subtle parchment panel before writing the dynamic quote.
    left, top, right, bottom = 115, 1390, 965, 1685
    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=28,
        fill=(246, 238, 222, 228),
        outline=(128, 101, 73, 80),
        width=2,
    )

    # Small decorative quote mark.
    draw.text((540, 1435), "❝", font=get_font(38), anchor="mm", fill=(103, 78, 55, 150))

    max_w = right - left - 90
    max_h = bottom - top - 105
    wrapped, font = fit_quote(draw, quote, max_w, max_h)
    draw.multiline_text(
        (540, 1540),
        wrapped,
        font=font,
        anchor="mm",
        align="center",
        spacing=16,
        fill=(72, 55, 42, 255),
    )

    draw.line((350, 1650, 730, 1650), fill=(128, 101, 73, 150), width=2)
    draw.text((540, 1665), "♡", font=get_font(26), anchor="mm", fill=(103, 78, 55, 190))
    return image


def main():
    quote, template, source, priority_line = pick_quote_and_template()
    image = render(quote, template)
    now = datetime.now(timezone.utc)
    filename = f"quote-{now.strftime('%Y%m%d-%H%M%S')}.jpg"
    output = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(output, format="JPEG", quality=94, optimize=True, progressive=True)

    metadata = {
        "quote": quote,
        "template": template.name,
        "filename": filename,
        "generated_at_utc": now.isoformat(),
        "quote_source": source,
        "priority_line": priority_line,
        "hashtags": __import__("quote_source").generate_hashtags(quote),
    }
    (OUTPUT_DIR / "latest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
