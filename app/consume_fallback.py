import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
META_FILE = ROOT / "generated" / "latest.json"
FALLBACK_FILE = ROOT / "data" / "fallback_quotes.txt"


def clean(value: str) -> str:
    return " ".join(
        str(value or "")
        .replace("\r", " ")
        .replace("\n", " ")
        .split()
    ).strip()


def main():
    if not META_FILE.exists():
        raise RuntimeError(
            "generated/latest.json not found."
        )

    metadata = json.loads(
        META_FILE.read_text(
            encoding="utf-8"
        )
    )

    if metadata.get("quote_source") != "fallback":
        print("No fallback quote to consume.")
        return

    quote = clean(
        metadata.get("quote")
    )

    if not quote:
        raise RuntimeError(
            "Fallback post has no quote."
        )

    if not FALLBACK_FILE.exists():
        raise RuntimeError(
            "data/fallback_quotes.txt not found."
        )

    lines = FALLBACK_FILE.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    target = clean(quote)
    removed = False
    new_lines = []

    for line in lines:
        if not removed and clean(line) == target:
            removed = True
            continue

        new_lines.append(line)

    if not removed:
        raise RuntimeError(
            "The published fallback quote was not found "
            "in data/fallback_quotes.txt."
        )

    FALLBACK_FILE.write_text(
        "".join(new_lines),
        encoding="utf-8",
    )

    print(
        "Consumed fallback quote from "
        "data/fallback_quotes.txt."
    )


if __name__ == "__main__":
    main()
