import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LATEST = ROOT / "generated" / "latest.json"

API_VERSION = os.getenv("META_API_VERSION", "v25.0")
IG_USER_ID = os.environ["IG_USER_ID"]
ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
IMAGE_URL = os.environ["IMAGE_URL"]


def api_post(path, data):
    url = f"https://graph.instagram.com/{API_VERSION}/{path}"
    response = requests.post(url, data=data, timeout=60)
    if not response.ok:
        raise RuntimeError(f"Instagram API error {response.status_code}: {response.text}")
    return response.json()


def api_get(path, params):
    url = f"https://graph.instagram.com/{API_VERSION}/{path}"
    response = requests.get(url, params=params, timeout=60)
    if not response.ok:
        raise RuntimeError(f"Instagram API error {response.status_code}: {response.text}")
    return response.json()


def main():
    if not IMAGE_URL.startswith("https://"):
        raise RuntimeError("IMAGE_URL must be a public HTTPS URL.")

    metadata = json.loads(LATEST.read_text(encoding="utf-8")) if LATEST.exists() else {}
    quote = metadata.get("quote", "")
    hashtags = metadata.get("hashtags") or os.getenv(
        "HASHTAGS", "#HindiQuotes #LifeQuotes #Zindagi #Motivation #PositiveVibes"
    )
    # The Instagram caption intentionally starts with the exact same quote used on the image.
    caption = f"{quote}\n\n{hashtags}".strip()

    # Step 1: create the image media container.
    container = api_post(
        f"{IG_USER_ID}/media",
        {
            "image_url": IMAGE_URL,
            "caption": caption,
            "alt_text": quote,
            "access_token": ACCESS_TOKEN,
        },
    )
    creation_id = container["id"]
    print(f"Created media container: {creation_id}")

    # Give Instagram a moment to fetch/process the public image.
    for _ in range(10):
        status = api_get(
            creation_id,
            {"fields": "status_code,status", "access_token": ACCESS_TOKEN},
        )
        code = status.get("status_code")
        print(f"Container status: {code} - {status.get('status', '')}")
        if code == "FINISHED":
            break
        if code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Container failed: {status}")
        time.sleep(5)

    # Step 2: publish the container.
    result = api_post(
        f"{IG_USER_ID}/media_publish",
        {"creation_id": creation_id, "access_token": ACCESS_TOKEN},
    )
    print(f"Published Instagram media: {result.get('id')}")

    # A priority quote is removed only after Instagram confirms publication.
    metadata = json.loads(LATEST.read_text(encoding="utf-8")) if LATEST.exists() else {}
    if metadata.get("quote_source") == "priority" and metadata.get("priority_line"):
        from quote_source import remove_priority_quote
        remove_priority_quote(int(metadata["priority_line"]))
        print("Consumed priority item from priority.txt.")


if __name__ == "__main__":
    try:
        main()
    except KeyError as exc:
        print(f"Missing environment variable: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
