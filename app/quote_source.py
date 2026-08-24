import hashlib
import json
import os
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

from google import genai

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / "state.json"
PRIORITY_FILE = ROOT / "priority.txt"
FALLBACK_FILE = ROOT / "data" / "fallback_quotes.txt"
PENDING_FILE = ROOT / "data" / "pending_posts.json"

DEFAULT_HASHTAGS = "#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"


def clean(value: str) -> str:
    return " ".join(
        str(value or "")
        .replace("\r", " ")
        .replace("\n", " ")
        .split()
    ).strip()


def normalize(value: str) -> str:
    return re.sub(r"[^\w\u0900-\u097F]+", "", clean(value).lower())


def quote_hash(value: str) -> str:
    return hashlib.sha256(
        normalize(value).encode("utf-8")
    ).hexdigest()


def get_priority_quote():
    if not PRIORITY_FILE.exists():
        return None, None

    for line_number, line in enumerate(
        PRIORITY_FILE.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        text = clean(line)
        if text and not text.startswith("#"):
            return text, line_number

    return None, None


def remove_priority_quote(line_number: int | None):
    if not line_number or not PRIORITY_FILE.exists():
        return

    lines = PRIORITY_FILE.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    index = line_number - 1
    if 0 <= index < len(lines):
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
            STATE_FILE.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError:
        return {}


def _save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _pending() -> list[dict]:
    if not PENDING_FILE.exists():
        return []

    try:
        value = json.loads(
            PENDING_FILE.read_text(encoding="utf-8")
        )
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _save_pending(posts: list[dict]):
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)

    if posts:
        PENDING_FILE.write_text(
            json.dumps(
                posts,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    elif PENDING_FILE.exists():
        PENDING_FILE.unlink()


def _gemini_model() -> str:
    model = os.getenv("GEMINI_MODEL", "").strip()
    if not model:
        raise RuntimeError(
            "GEMINI_MODEL is not configured."
        )
    return model


def _gemini_client() -> genai.Client:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )
    return genai.Client(api_key=key)


def _too_similar(quote: str, previous: list[str]) -> bool:
    candidate = normalize(quote)

    for item in previous[-200:]:
        other = normalize(item)
        if not other:
            continue

        if candidate == other:
            return True

        if SequenceMatcher(
            None,
            candidate,
            other,
        ).ratio() >= 0.90:
            return True

    return False


def _extract_json(text: str):
    text = (text or "").strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            text,
            flags=re.I | re.S,
        ).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(
            r"\{.*\}",
            text,
            flags=re.S,
        )
        if not match:
            raise
        return json.loads(match.group(0))


def _generate_gemini_batch(count: int) -> list[dict]:
    state = _state()

    recent = list(
        state.get(
            "recent_gemini_quotes",
            [],
        )
    )

    recent_text = "\n".join(
        f"- {q}"
        for q in recent[-80:]
    ) or "(none)"

    prompt = f"""
Generate exactly {count} DIFFERENT original Hindi life quotes.

Return ONLY valid JSON:
{{
  "posts": [
    {{
      "quote": "Hindi quote",
      "hashtags": [
        "#HindiQuotes",
        "#LifeQuotes",
        "#Zindagi",
        "#Motivation",
        "#PositiveVibes"
      ]
    }}
  ]
}}

Rules:
- Exactly {count} posts.
- All quotes must be different from each other.
- Hindi/Devanagari only.
- 8 to 22 Hindi words per quote.
- Emotional, natural, relatable and meaningful.
- No quotation marks, emojis, numbering, attribution or explanation.
- Exactly 5 hashtags for each quote.
- Prefer common English hashtags.
- Do not repeat or closely paraphrase these recent quotes:

{recent_text}
""".strip()

    response = _gemini_client().models.generate_content(
        model=_gemini_model(),
        contents=prompt,
    )

    data = _extract_json(response.text)
    posts = data.get("posts") if isinstance(data, dict) else data

    if not isinstance(posts, list) or len(posts) != count:
        raise ValueError(
            f"Expected {count} Gemini posts."
        )

    accepted = []
    local_quotes = list(recent)
    used = set(
        state.get(
            "used_gemini_quote_hashes",
            [],
        )
    )

    for item in posts:
        quote = clean(item.get("quote"))

        if not quote or len(quote.split()) < 4:
            raise ValueError(
                f"Invalid Gemini quote: {quote!r}"
            )

        if any(
            bad in quote
            for bad in ["#", "http://", "https://"]
        ):
            raise ValueError(
                f"Invalid Gemini quote: {quote!r}"
            )

        if _too_similar(
            quote,
            local_quotes,
        ):
            raise ValueError(
                f"Duplicate/similar Gemini quote: {quote!r}"
            )

        hashtags = []
        raw_tags = item.get("hashtags", [])

        if isinstance(raw_tags, list):
            for tag in raw_tags:
                tag = clean(tag)
                if (
                    tag.startswith("#")
                    and tag.lower()
                    not in {
                        x.lower()
                        for x in hashtags
                    }
                ):
                    hashtags.append(tag)

        if len(hashtags) < 5:
            hashtags = DEFAULT_HASHTAGS.split()

        accepted.append(
            {
                "quote": quote,
                "hashtags": " ".join(
                    hashtags[:5]
                ),
                "quote_source": "gemini",
                "priority_line": None,
            }
        )

        local_quotes.append(quote)
        used.add(quote_hash(quote))

    state["recent_gemini_quotes"] = (
        recent
        + [
            item["quote"]
            for item in accepted
        ]
    )[-200:]

    state["used_gemini_quote_hashes"] = list(
        used
    )[-20000:]

    _save_state(state)

    return accepted


def _read_fallback_quotes() -> list[str]:
    if not FALLBACK_FILE.exists():
        return []

    values = []

    for line in FALLBACK_FILE.read_text(
        encoding="utf-8"
    ).splitlines():
        quote = clean(line)

        if not quote or quote.startswith("#"):
            continue

        if quote not in values:
            values.append(quote)

    return values


def _generate_fallback_batch(
    count: int,
    reason: Exception,
) -> list[dict]:
    quotes = _read_fallback_quotes()

    if len(quotes) < count:
        raise RuntimeError(
            "Gemini failed and fallback_quotes.txt does not "
            f"contain at least {count} quotes. "
            f"Available: {len(quotes)}. "
            f"Gemini error: {reason}"
        )

    chosen = random.SystemRandom().sample(
        quotes,
        count,
    )

    print(
        f"Gemini unavailable. Selected {count} quotes "
        "from data/fallback_quotes.txt."
    )

    return [
        {
            "quote": quote,
            "hashtags": DEFAULT_HASHTAGS,
            "quote_source": "fallback",
            "priority_line": None,
        }
        for quote in chosen
    ]


def _ensure_pending_posts():
    pending = _pending()
    if pending:
        return

    priority_quote, priority_line = (
        get_priority_quote()
    )

    # One Gemini request per run:
    # priority present -> 3 Gemini posts
    # priority absent  -> 4 Gemini posts
    gemini_count = 3 if priority_quote else 4

    try:
        generated = _generate_gemini_batch(
            gemini_count
        )
    except Exception as exc:
        print(
            "Gemini batch failed; switching to fallback_quotes.txt"
        )
        print(f"Gemini failure: {exc}")
        generated = _generate_fallback_batch(
            gemini_count,
            exc,
        )

    if priority_quote:
        pending = [
            {
                "quote": priority_quote,
                "hashtags": DEFAULT_HASHTAGS,
                "quote_source": "priority",
                "priority_line": priority_line,
            }
        ] + generated
    else:
        pending = generated

    _save_pending(pending)


def get_next_post():
    """
    Prepare the complete 4-post batch once and then return one post at a time.
    """
    _ensure_pending_posts()

    pending = _pending()
    if not pending:
        raise RuntimeError(
            "No pending post is available."
        )

    item = pending.pop(0)
    _save_pending(pending)

    return (
        item["quote"],
        item.get(
            "hashtags",
            DEFAULT_HASHTAGS,
        ),
        item.get("quote_source", "gemini"),
        item.get("priority_line"),
    )


def get_quote():
    quote, _, source, priority_line = get_next_post()
    return (
        quote,
        source,
        priority_line,
    )


def generate_hashtags(quote: str) -> str:
    # Kept for compatibility with older code. No Gemini request.
    return DEFAULT_HASHTAGS
