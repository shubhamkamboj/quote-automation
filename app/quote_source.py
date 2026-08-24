import hashlib
import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

from google import genai

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / "state.json"
PRIORITY_FILE = ROOT / "priority.txt"

DEFAULT_HASHTAGS = "#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"


def _clean_text(value: str) -> str:
    value = value.replace("\r", " ").replace("\n", " ")
    return " ".join(value.split()).strip()


def _normalize_quote(value: str) -> str:
    value = _clean_text(value).lower()
    return re.sub(r"[^\w\u0900-\u097F]+", "", value)


def _quote_hash(value: str) -> str:
    return hashlib.sha256(
        _normalize_quote(value).encode("utf-8")
    ).hexdigest()


def get_priority_quote() -> tuple[str | None, int | None]:
    if not PRIORITY_FILE.exists():
        return None, None

    lines = PRIORITY_FILE.read_text(
        encoding="utf-8"
    ).splitlines()

    for line_number, line in enumerate(lines, start=1):
        text = _clean_text(line)

        if not text or text.startswith("#"):
            continue

        return text, line_number

    return None, None


def remove_priority_quote(line_number: int | None) -> None:
    if not line_number or not PRIORITY_FILE.exists():
        return

    lines = PRIORITY_FILE.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    index = line_number - 1

    if index < 0 or index >= len(lines):
        return

    del lines[index]

    PRIORITY_FILE.write_text(
        "".join(lines),
        encoding="utf-8",
    )


def _state() -> dict:
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError:
        # Never let a broken generated state file prevent the workflow from
        # starting. A fresh state will be recreated.
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _gemini_model() -> str:
    model = os.getenv(
        "GEMINI_MODEL",
        "",
    ).strip()

    if not model:
        raise RuntimeError(
            "GEMINI_MODEL is not configured. "
            "Add it as a GitHub Actions Repository Variable."
        )

    return model


def _new_gemini_client() -> genai.Client:
    """
    IMPORTANT:
    A fresh client is created for every Gemini request.
    This avoids 'Cannot send a request, as the client has been closed'
    when a previous attempt/request lifecycle closes the client.
    """
    api_key = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(
        api_key=api_key
    )


def _is_too_similar(
    quote: str,
    recent_quotes: list[str],
) -> bool:
    candidate = _normalize_quote(quote)

    for previous in recent_quotes[-100:]:
        previous_normalized = _normalize_quote(
            previous
        )

        if not previous_normalized:
            continue

        if candidate == previous_normalized:
            return True

        similarity = SequenceMatcher(
            None,
            candidate,
            previous_normalized,
        ).ratio()

        if similarity >= 0.90:
            return True

    return False


def generate_gemini_quote() -> str:
    state = _state()

    recent_quotes = list(
        state.get(
            "recent_gemini_quotes",
            [],
        )
    )

    used_hashes = set(
        state.get(
            "used_gemini_quote_hashes",
            [],
        )
    )

    recent_text = "\n".join(
        f"- {q}"
        for q in recent_quotes[-50:]
    ) or "(none)"

    prompt = f"""
Generate exactly ONE original Hindi life quote for a daily Instagram diary page.

Rules:
- Write only the quote, nothing else.
- Hindi/Devanagari only.
- 8 to 22 Hindi words.
- Natural, emotional, positive and meaningful.
- Suitable for a clean diary / life-quotes Instagram page.
- No hashtags, quotation marks, emojis, attribution, numbering, or explanation.
- Do not repeat or closely paraphrase any recent quote below.

Recent quotes:
{recent_text}
""".strip()

    last_error = None

    for attempt in range(1, 6):
        client = None

        try:
            # NEW CLIENT FOR EVERY ATTEMPT
            client = _new_gemini_client()

            response = client.models.generate_content(
                model=_gemini_model(),
                contents=prompt,
            )

            quote = _clean_text(
                response.text or ""
            )

            if not quote:
                raise ValueError(
                    "Gemini returned an empty quote."
                )

            if len(quote.split()) < 4:
                raise ValueError(
                    f"Gemini quote is too short: {quote!r}"
                )

            if any(
                token in quote
                for token in [
                    "#",
                    "http://",
                    "https://",
                ]
            ):
                raise ValueError(
                    f"Gemini returned invalid quote: {quote!r}"
                )

            quote_hash = _quote_hash(quote)

            if quote_hash in used_hashes:
                raise ValueError(
                    "Gemini returned an already-used quote."
                )

            if _is_too_similar(
                quote,
                recent_quotes,
            ):
                raise ValueError(
                    "Gemini returned a quote too similar "
                    "to a recent quote."
                )

            # Reserve the quote immediately so the next post in the same
            # workflow cannot use it again.
            recent_quotes.append(quote)
            used_hashes.add(quote_hash)

            state["recent_gemini_quotes"] = (
                recent_quotes[-100:]
            )
            state["used_gemini_quote_hashes"] = list(
                used_hashes
            )[-10000:]

            _save_state(state)

            print(
                f"Unique Gemini quote accepted on attempt {attempt}."
            )

            return quote

        except Exception as exc:
            last_error = exc

            print(
                f"Quote attempt {attempt}/5 rejected: {exc}"
            )

        finally:
            # The google-genai client does not need to be explicitly closed
            # here. Each attempt gets its own client instance.
            client = None

    raise RuntimeError(
        "Could not generate a unique Gemini quote after 5 attempts. "
        f"Last error: {last_error}"
    )


def _extract_hashtags(text: str) -> list[str]:
    tags = []

    for token in re.findall(
        r"#[\w\u0900-\u097F]+",
        text,
    ):
        tag = token.strip(
            ".,!?;:()[]{}"
        )

        if tag.lower() not in {
            t.lower() for t in tags
        }:
            tags.append(tag)

    return tags


def generate_hashtags(quote: str) -> str:
    try:
        client = _new_gemini_client()

        prompt = f"""
For this Hindi Instagram life quote, return exactly 5 relevant and popular
hashtags for Hindi quotes, motivation, life and positive content.

Quote:
{quote}

Rules:
- Return only hashtags separated by spaces.
- Exactly 5 hashtags.
- Mostly English hashtags for discoverability.
- No explanation, numbering, commas, emojis, or quotes.
""".strip()

        response = client.models.generate_content(
            model=_gemini_model(),
            contents=prompt,
        )

        tags = _extract_hashtags(
            response.text or ""
        )

        if len(tags) >= 5:
            return " ".join(
                tags[:5]
            )

    except Exception as exc:
        print(
            "Hashtag generation failed; using "
            f"fallback hashtags: {exc}"
        )

    return os.getenv(
        "HASHTAGS",
        DEFAULT_HASHTAGS,
    )


def get_quote() -> tuple[str, str, int | None]:
    force_gemini = (
        os.getenv(
            "FORCE_GEMINI",
            "false",
        ).strip().lower()
        == "true"
    )

    # Post #1: priority.txt wins when available.
    # Posts #2-#4: workflow sets FORCE_GEMINI=true.
    if not force_gemini:
        priority_quote, line_number = (
            get_priority_quote()
        )

        if priority_quote:
            return (
                priority_quote,
                "priority",
                line_number,
            )

    return (
        generate_gemini_quote(),
        "gemini",
        None,
    )
