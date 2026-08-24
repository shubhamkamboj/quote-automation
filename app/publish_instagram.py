import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "generated" / "latest.json"

# Existing GitHub secret names used by the user's repository.
ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
IG_USER_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
META_API_VERSION = os.getenv("META_API_VERSION", "").strip() or "v25.0"
IMAGE_URL = os.getenv("IMAGE_URL", "").strip()
DEFAULT_HASHTAGS = "#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"


def api_url(path: str) -> str:
    return f"https://graph.instagram.com/{META_API_VERSION}/{path.lstrip('/')}"


def api_post(path: str, data: dict) -> dict:
    response = requests.post(api_url(path), data=data, timeout=90)
    if not response.ok:
        raise RuntimeError(
            f"Instagram API error {response.status_code}: {response.text}"
        )
    return response.json()


def api_get(path: str, params: dict) -> dict:
    response = requests.get(api_url(path), params=params, timeout=60)
    if not response.ok:
        raise RuntimeError(
            f"Instagram API error {response.status_code}: {response.text}"
        )
    return response.json()


def load_metadata() -> dict:
    if not LATEST.exists():
        raise RuntimeError(f"Missing generated metadata: {LATEST}")
    return json.loads(LATEST.read_text(encoding="utf-8"))


def verify_public_image() -> None:
    response = requests.get(
        IMAGE_URL,
        stream=True,
        allow_redirects=True,
        timeout=30,
        headers={"User-Agent": "quote-automation/1.0"},
    )
    content_type = (response.headers.get("Content-Type") or "").lower()
    print(f"Public image HTTP: {response.status_code}")
    print(f"Public image Content-Type: {content_type}")
    print(f"Public image final URL: {response.url}")

    if not response.ok:
        raise RuntimeError(
            f"IMAGE_URL is not publicly reachable: HTTP {response.status_code}"
        )
    if not content_type.startswith("image/jpeg"):
        raise RuntimeError(
            f"IMAGE_URL must return JPEG. Got Content-Type={content_type}"
        )


def wait_until_finished(container_id: str):
    for attempt in range(18):
        status = api_get(
            container_id,
            {"fields": "status_code,status", "access_token": ACCESS_TOKEN},
        )
        code = status.get("status_code")
        print(f"Container status [{attempt + 1}/18]: {code} - {status.get('status', '')}")

        if code == "FINISHED":
            return
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Instagram container failed: {status}")
        time.sleep(5)

    raise RuntimeError("Instagram media container did not reach FINISHED status.")


def consume_priority_if_needed(metadata: dict):
    if metadata.get("quote_source") != "priority":
        return

    priority_line = metadata.get("priority_line")
    if not priority_line:
        raise RuntimeError("Priority quote was published but priority_line is missing.")

    from quote_source import remove_priority_quote
    remove_priority_quote(int(priority_line))
    print("Priority item consumed after successful Instagram publication.")


def main():
    missing = []
    if not ACCESS_TOKEN:
        missing.append("INSTAGRAM_ACCESS_TOKEN")
    if not IG_USER_ID:
        missing.append("INSTAGRAM_ACCOUNT_ID")
    if not IMAGE_URL:
        missing.append("IMAGE_URL")
    if missing:
        raise RuntimeError("Missing required value(s): " + ", ".join(missing))

    if not IMAGE_URL.startswith("https://"):
        raise RuntimeError("IMAGE_URL must be HTTPS.")

    metadata = load_metadata()
    quote = str(metadata.get("quote", "")).strip()
    hashtags = str(metadata.get("hashtags") or os.getenv("HASHTAGS", DEFAULT_HASHTAGS)).strip()
    caption = f"{quote}\n\n{hashtags}".strip()

    print(f"Instagram API version: {META_API_VERSION}")
    print(f"Quote source: {metadata.get('quote_source', 'unknown')}")
    print(f"Image URL: {IMAGE_URL}")

    # Instagram fetches image_url itself, so verify the public resource first.
    verify_public_image()

    container = api_post(
        f"{IG_USER_ID}/media",
        {
            "image_url": IMAGE_URL,
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        },
    )
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(f"Instagram did not return a container ID: {container}")

    print(f"Created media container: {creation_id}")
    wait_until_finished(creation_id)

    published = api_post(
        f"{IG_USER_ID}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": ACCESS_TOKEN,
        },
    )
    media_id = published.get("id")
    if not media_id:
        raise RuntimeError(f"Instagram did not return a media ID: {published}")

    print(f"Instagram post published successfully: {media_id}")
    consume_priority_if_needed(metadata)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
