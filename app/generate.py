import json
import os
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from quote_source import get_next_post
from image_source import generate_background, use_gemini_image

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
OUT = ROOT / "generated"
STATE = ROOT / "data" / "state.json"
FONT = ROOT / "fonts" / "NotoSansDevanagari-Regular.ttf"

W, H = 1080, 1800

# Supported template image formats.
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def load(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_templates():
    """
    Read ALL template images dynamically.

    Any file matching template-* with a supported image extension
    is included. This means adding/removing images from templates/
    automatically changes the template count.
    """
    if not TEMPLATES.exists():
        raise RuntimeError(f"Templates folder not found: {TEMPLATES}")

    templates = sorted(
        [
            item
            for item in TEMPLATES.iterdir()
            if item.is_file()
            and item.name.lower().startswith("template-")
            and item.suffix.lower() in IMAGE_EXTENSIONS
        ],
        key=lambda p: (
            p.stem.lower(),
            p.suffix.lower(),
        ),
    )

    if not templates:
        raise RuntimeError(
            f"No template images found in: {TEMPLATES}"
        )

    return templates


def template_number(path):
    """
    Extract the numeric part from names such as:
    template-01.jpg
    template-29.png

    Non-numeric names are sorted after numeric names.
    """
    try:
        return int(path.stem.split("-", 1)[1])
    except (IndexError, ValueError):
        return 10**9


def get_ordered_templates():
    """
    Prefer numeric template order:
        template-01
        template-02
        ...
        template-30

    This keeps the sequence stable even when JPG/PNG are mixed.
    """
    templates = get_templates()

    return sorted(
        templates,
        key=lambda p: (
            template_number(p),
            p.name.lower(),
        ),
    )


def pick_template():
    """
    Sequential template rotation.

    Example with 30 templates:
        01, 02, 03 ... 29, 30, 01, 02 ...

    The current position is stored in data/state.json, so the next
    workflow run continues from where the previous one stopped.

    If new templates are added, the total count is detected
    automatically and the sequence continues using the new count.

    IMPORTANT:
    This function is intentionally NOT random.
    """
    templates = get_ordered_templates()
    total_templates = len(templates)

    state = load(STATE, {})

    # Primary state value: next_template_index (0-based).
    # Fall back to older last_template state for backward compatibility.
    if "next_template_index" in state:
        try:
            next_index = int(state["next_template_index"])
        except (TypeError, ValueError):
            next_index = 0
    else:
        last_template = state.get("last_template")

        if last_template:
            old_index = next(
                (
                    index
                    for index, item in enumerate(templates)
                    if item.name == last_template
                ),
                -1,
            )
            next_index = old_index + 1 if old_index >= 0 else 0
        else:
            next_index = 0

    # Automatically wrap around when the end is reached.
    next_index %= total_templates

    template = templates[next_index]

    # Next image position.
    state["next_template_index"] = (
        (next_index + 1) % total_templates
    )

    # Useful information for logs/debugging.
    state["last_template"] = template.name
    state["last_template_index"] = next_index
    state["template_count"] = total_templates
    state["last_run_utc"] = datetime.now(
        timezone.utc
    ).isoformat()

    save(STATE, state)

    print(
        f"Template rotation: "
        f"{next_index + 1}/{total_templates} -> "
        f"{template.name}"
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

    highlighted_words = [
        str(w).strip()
        for w in (highlighted_words or [])
        if str(w).strip()
    ]

    lines = text.split("\n")
    line_heights = []

    for line in lines:
        bb = draw.textbbox(
            (0, 0),
            line,
            font=fnt,
        )
        line_heights.append(
            bb[3] - bb[1]
        )

    line_spacing = 18

    total_h = (
        sum(line_heights)
        + line_spacing * max(0, len(lines) - 1)
    )

    y = cy - total_h / 2

    for idx, line in enumerate(lines):
        segments = [line]

        if highlighted_words:
            import re

            pattern = (
                "("
                + "|".join(
                    re.escape(h)
                    for h in sorted(
                        highlighted_words,
                        key=len,
                        reverse=True,
                    )
                )
                + ")"
            )

            segments = [
                seg
                for seg in re.split(
                    pattern,
                    line,
                )
                if seg
            ]

        cursor_x = (
            cx
            - draw.textlength(
                line,
                font=fnt,
            )
            / 2
        )

        for segment in segments:
            # Keep the existing visual behavior.
            fill = (
                (0, 0, 0, 255)
                if segment.strip() in highlighted_words
                else (0, 0, 0, 255)
            )

            draw.text(
                (cursor_x, y),
                segment,
                font=fnt,
                fill=fill,
            )

            cursor_x += draw.textlength(
                segment,
                font=fnt,
            )

        y += (
            line_heights[idx]
            + line_spacing
        )

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
    try:
        content_count = max(
            1,
            int(
                os.getenv(
                    "CONTENT_COUNT",
                    "1",
                )
            ),
        )
    except ValueError as exc:
        raise RuntimeError(
            "CONTENT_COUNT must be an integer."
        ) from exc

    # Print the current template count before generating.
    templates = get_ordered_templates()

    print(
        f"Total template images found: "
        f"{len(templates)}"
    )

    result = get_next_post(content_count)

    quote = result[0]
    hashtags = result[1]
    source = result[2]
    priority_line = result[3]

    # Newer quote_source versions may return a 5th metadata value.
    highlighted_words = (
        result[4]
        if len(result) > 4
        else []
    )

    if use_gemini_image():
        source_image = (
            OUT / "gemini-background.jpg"
        )

        generate_background(
            quote,
            source_image,
        )

        image = render(
            quote,
            source_image,
            highlighted_words,
        )

        image_source = "gemini"
        template_name = "gemini-generated"

    else:
        template = pick_template()

        image = render(
            quote,
            template,
            highlighted_words,
        )

        image_source = "template"
        template_name = template.name

    now = datetime.now(timezone.utc)

    filename = (
        "quote-"
        f"{now.strftime('%Y%m%d-%H%M%S-%f')}"
        ".jpg"
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

    # Read state again because pick_template() may have updated it.
    state = load(STATE, {})

    metadata = {
        "quote": quote,
        "hashtags": hashtags,
        "template": template_name,
        "image_source": image_source,
        "filename": filename,
        "latest_filename": "latest.jpg",
        "generated_at_utc": now.isoformat(),
        "quote_source": source,
        "priority_line": priority_line,
        "highlighted_words": highlighted_words,

        # Template rotation information.
        "template_count": len(templates),
        "template_rotation_index": state.get(
            "last_template_index"
        ),
        "next_template_index": state.get(
            "next_template_index"
        ),
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
