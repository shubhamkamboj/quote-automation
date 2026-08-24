import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LATEST_FILE = ROOT / "generated" / "latest.json"

# Existing GitHub repository secret names
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
IG_USER_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()

# Optional GitHub repository variable.
# If META_API_VERSION is not configured, use the default below.
META_API_VERSION = (
    os.getenv("META_API_VERSION", "").strip()
    or "v25.0"
)

IMAGE_URL = os.getenv("IMAGE_URL", "").strip()
DEFAULT_HASHTAGS = "#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"


def fail(message: str):
    raise RuntimeError(message)


def require_config():
    missing = []

    if not ACCESS_TOKEN:
        missing.append("INSTAGRAM_ACCESS_TOKEN")

    if not IG_USER_ID:
        missing.append("INSTAGRAM_ACCOUNT_ID")

    if not IMAGE_URL:
        missing.append("IMAGE_URL")

    if missing:
        fail(
            "Missing required GitHub Actions value(s): "
            + ", ".join(missing)
        )

    if not IMAGE_URL.startswith("https://"):
        fail("IMAGE_URL must be a public HTTPS URL.")


def api_url(path: str) -> str:
    return f"https://graph.instagram.com/{META_API_VERSION}/{path.lstrip('/')}"


def post(path: str, data: dict) -> dict:
    response = requests.post(
        api_url(path),
        data=data,
        timeout=90,
    )

    if not response.ok:
        raise RuntimeError(
            f"Instagram API error {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Instagram API returned invalid JSON: {response.text}"
        ) from exc


def get(path: str, params: dict) -> dict:
    response = requests.get(
        api_url(path),
        params=params,
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            f"Instagram API error {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"Instagram API returned invalid JSON: {response.text}"
        ) from exc


def load_metadata() -> dict:
    if not LATEST_FILE.exists():
        fail(f"Generated metadata file not found: {LATEST_FILE}")

    try:
        return json.loads(LATEST_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON in {LATEST_FILE}: {exc}"
        ) from exc


def build_caption(metadata: dict) -> str:
    quote = str(metadata.get("quote", "")).strip()

    if not quote:
        fail("Generated quote is empty.")

    hashtags = str(
        metadata.get("hashtags")
        or os.getenv("HASHTAGS", DEFAULT_HASHTAGS)
    ).strip()

    return f"{quote}\n\n{hashtags}".strip()


def wait_until_finished(container_id: str):
    for attempt in range(18):
        result = get(
            container_id,
            {
                "fields": "status_code,status",
                "access_token": ACCESS_TOKEN,
            },
        )

        status_code = result.get("status_code")
        status = result.get("status", "")

        print(
            f"Instagram container [{attempt + 1}/18]: "
            f"{status_code} - {status}"
        )

        if status_code == "FINISHED":
            return

        if status_code in {"ERROR", "EXPIRED"}:
            fail(f"Instagram media container failed: {result}")

        time.sleep(5)

    fail("Instagram media container did not reach FINISHED status.")


def consume_priority_if_needed(metadata: dict):
    if metadata.get("quote_source") != "priority":
        return

    priority_line = metadata.get("priority_line")
    if not priority_line:
        print("Priority source detected but priority_line is missing.")
        return

    from quote_source import remove_priority_quote

    remove_priority_quote(int(priority_line))
    print("Priority item consumed successfully.")


def main():
    require_config()

    metadata = load_metadata()
    caption = build_caption(metadata)

    print(f"Instagram User ID: {IG_USER_ID}")
    print(f"Instagram API version: {META_API_VERSION}")
    print(f"Image URL: {IMAGE_URL}")
    print(f"Quote source: {metadata.get('quote_source', 'unknown')}")

    # Instagram Login / Instagram User Access Token flow.
    # Host: graph.instagram.com
    # Step 1: create media container
    container = post(
        f"{IG_USER_ID}/media",
        {
            "image_url": IMAGE_URL,
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        },
    )

    creation_id = container.get("id")

    if not creation_id:
        fail(f"No creation ID returned by Instagram: {container}")

    print(f"Created media container: {creation_id}")

    wait_until_finished(creation_id)

    # Step 2: publish the media container
    published = post(
        f"{IG_USER_ID}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": ACCESS_TOKEN,
        },
    )

    media_id = published.get("id")

    if not media_id:
        fail(f"No published media ID returned by Instagram: {published}")

    print(f"Instagram post published successfully. Media ID: {media_id}")

    # Only consume priority after Instagram confirms publication.
    consume_priority_if_needed(metadata)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
