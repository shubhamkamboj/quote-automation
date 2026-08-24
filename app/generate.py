"""
Generate one quote image.

This file is intentionally self-contained around the existing project modules.
It:
1. Picks priority.txt first, otherwise Gemini.
2. Picks a random diary template.
3. Renders the quote.
4. Writes both a timestamped JPEG and a stable generated/latest.jpg.
5. Writes generated/latest.json metadata.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from quote_source import get_quote, generate_hashtags
from render import render_quote

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT / "templates"
GENERATED_DIR = ROOT / "generated"
LATEST_JSON = GENERATED_DIR / "latest.json"
LATEST_JPG = GENERATED_DIR / "latest.jpg"


def pick_template() -> Path:
    templates = sorted(
        [
            p for p in TEMPLATES_DIR.iterdir()
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        ]
    )
    if not templates:
        raise RuntimeError(f"No image templates found in {TEMPLATES_DIR}")

    # Use the existing random selection helper if available.
    import random
    return random.choice(templates)


def pick_quote_and_template():
    quote, source, priority_line = get_quote()
    template = pick_template()
    return quote, template, source, priority_line


def main():
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    quote, template, source, priority_line = pick_quote_and_template()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    timestamped_name = f"quote-{timestamp}.jpg"
    timestamped_path = GENERATED_DIR / timestamped_name

    # render_quote is the existing project's renderer.
    rendered = render_quote(
        template_path=template,
        quote=quote,
        output_path=timestamped_path,
    )

    rendered_path = Path(rendered) if rendered else timestamped_path

    if not rendered_path.exists():
        raise RuntimeError(
            f"Quote image was not created: {rendered_path}"
        )

    # Stable public URL target. This file is committed to GitHub and remains
    # addressable without depending on a commit SHA.
    shutil.copyfile(rendered_path, LATEST_JPG)

    hashtags = generate_hashtags(quote)

    metadata = {
        "quote": quote,
        "hashtags": hashtags,
        "quote_source": source,
        "priority_line": priority_line,
        "template": template.name,
        "filename": timestamped_name,
        "latest_filename": "latest.jpg",
    }

    LATEST_JSON.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Generated: {rendered_path}")
    print(f"Stable latest image: {LATEST_JPG}")
    print(f"Source: {source}")
    print(f"Quote: {quote}")


if __name__ == "__main__":
    main()
