import json
import os
import re
from pathlib import Path

from google import genai

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / "state.json"
PRIORITY_FILE = ROOT / "priority.txt"

DEFAULT_HASHTAGS = "#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"


def _clean_text(value: str) -> str:
    value = value.replace("\r", " ").replace("\n", " ")
    return " ".join(value.split()).strip()


def get_priority_quote() -> tuple[str | None, int | None]:
    """Return the first non-empty priority line and its 1-based line number.

    priority.txt is an optional addon. Missing or empty file is intentionally
    treated as normal and simply falls back to Gemini.
    """
    if not PRIORITY_FILE.exists():
        return None, None

    lines = PRIORITY_FILE.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        text = _clean_text(line)
        if not text or text.startswith("#"):
            continue
        return text, line_number
    return None, None


def remove_priority_quote(line_number: int | None) -> None:
    """Remove one priority line after Instagram publication succeeds."""
    if not line_number or not PRIORITY_FILE.exists():
        return

    lines = PRIORITY_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    index = line_number - 1
    if index < 0 or index >= len(lines):
        return

    del lines[index]
    PRIORITY_FILE.write_text("".join(lines), encoding="utf-8")


def _state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=api_key)


def _gemini_model() -> str:
    # Keep the model fixed so an empty GitHub secret can never produce
    # the Gemini SDK error: "model is required."
    return "gemini-2.5-flash"


def generate_gemini_quote() -> str:
    client = _gemini_client()

    state = _state()
    recent = state.get("recent_gemini_quotes", [])
    recent_text = "\n".join(f"- {q}" for q in recent[-20:]) or "(none)"

    prompt = f"""
Generate exactly ONE original Hindi life quote for a daily Instagram diary page.

Rules:
- Write only the quote, nothing else.
- Hindi/Devanagari only.
- 8 to 22 Hindi words.
- Natural, emotional, positive and meaningful.
- Suitable for a clean diary / life-quotes Instagram page.
- Do not use hashtags, quotation marks, emojis, attribution, numbering, or explanations.
- Do not repeat or closely paraphrase any recent quotes below.

Recent quotes:
{recent_text}
""".strip()

    response = client.models.generate_content(model=_gemini_model(), contents=prompt)
    quote = _clean_text(response.text or "")
    if not quote:
        raise RuntimeError("Gemini returned an empty quote.")
    if len(quote.split()) < 4:
        raise RuntimeError(f"Gemini quote is too short: {quote!r}")
    if any(token in quote for token in ["#", "http://", "https://"]):
        raise RuntimeError(f"Gemini returned invalid quote text: {quote!r}")

    recent.append(quote)
    state["recent_gemini_quotes"] = recent[-20:]
    _save_state(state)
    return quote


def _extract_hashtags(text: str) -> list[str]:
    tags = []
    for token in re.findall(r"#[\w\u0900-\u097F]+", text):
        tag = token.strip(".,!?;:()[]{}")
        if tag.lower() not in {t.lower() for t in tags}:
            tags.append(tag)
    return tags


def generate_hashtags(quote: str) -> str:
    """Generate five relevant/popular hashtags; fall back without failing the post."""
    if os.getenv("AUTO_HASHTAGS", "true").lower() not in {"1", "true", "yes", "on"}:
        return os.getenv("HASHTAGS", DEFAULT_HASHTAGS)

    try:
        client = _gemini_client()
        prompt = f"""
For this Hindi Instagram life quote, return exactly 5 popular, high-discovery,
currently relevant hashtags for Hindi quotes, motivation, life and positive content.

Quote:
{quote}

Rules:
- Return only hashtags separated by spaces.
- Exactly 5 hashtags.
- Use common Instagram hashtags, mostly English for discoverability.
- No explanation, numbering, commas, emojis, or quotes.
- Every item must start with #.
""".strip()
        response = client.models.generate_content(model=_gemini_model(), contents=prompt)
        tags = _extract_hashtags(response.text or "")
        if len(tags) >= 5:
            return " ".join(tags[:5])
    except Exception as exc:
        print(f"Hashtag generation failed; using fallback hashtags: {exc}")

    return os.getenv("HASHTAGS", DEFAULT_HASHTAGS)


def get_quote() -> tuple[str, str, int | None]:
    """Priority text first; otherwise generate a fresh Gemini quote."""
    priority_quote, line_number = get_priority_quote()
    if priority_quote:
        return priority_quote, "priority", line_number

    return generate_gemini_quote(), "gemini", None
