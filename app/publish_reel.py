import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LATEST_FILE = ROOT / "generated" / "latest.json"

ACCESS_TOKEN = os.getenv(
    "INSTAGRAM_ACCESS_TOKEN",
    "",
).strip()

IG_USER_ID = os.getenv(
    "INSTAGRAM_ACCOUNT_ID",
    "",
).strip()

META_API_VERSION = (
    os.getenv(
        "META_API_VERSION",
        "",
    ).strip()
    or "v25.0"
)

REEL_URL = os.getenv(
    "REEL_URL",
    "",
).strip()

DEFAULT_HASHTAGS = (
    "#HindiQuotes #LifeQuotes #Zindagi "
    "#Motivation #PositiveVibes"
)


def fail(message: str):
    raise RuntimeError(message)


def require_config():
    missing = []

    if not ACCESS_TOKEN:
        missing.append("INSTAGRAM_ACCESS_TOKEN")

    if not IG_USER_ID:
        missing.append("INSTAGRAM_ACCOUNT_ID")

    if not REEL_URL:
        missing.append("REEL_URL")

    if missing:
        fail(
            "Missing required GitHub Actions value(s): "
            + ", ".join(missing)
        )

    if not REEL_URL.startswith("https://"):
        fail("REEL_URL must be a public HTTPS URL.")


def api_url(path: str) -> str:
    return (
        f"https://graph.instagram.com/"
        f"{META_API_VERSION}/"
        f"{path.lstrip('/')}"
    )


def api_post(path: str, data: dict) -> dict:
    response = requests.post(
        api_url(path),
        data=data,
        timeout=120,
    )

    if not response.ok:
        raise RuntimeError(
            f"Instagram API error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Instagram returned a non-JSON response: "
            f"{response.text}"
        ) from exc


def api_get(path: str, params: dict) -> dict:
    response = requests.get(
        api_url(path),
        params=params,
        timeout=90,
    )

    if not response.ok:
        raise RuntimeError(
            f"Instagram API error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError(
            "Instagram returned a non-JSON response: "
            f"{response.text}"
        ) from exc


def load_metadata() -> dict:
    if not LATEST_FILE.exists():
        fail(
            f"Generated metadata file not found: "
            f"{LATEST_FILE}"
        )

    try:
        return json.loads(
            LATEST_FILE.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON in {LATEST_FILE}: {exc}"
        ) from exc


def build_caption(metadata: dict) -> str:
    quote = str(
        metadata.get(
            "quote",
            "",
        )
    ).strip()

    if not quote:
        fail("Generated quote is empty.")

    hashtags = str(
        metadata.get(
            "hashtags",
            "",
        )
        or os.getenv(
            "HASHTAGS",
            DEFAULT_HASHTAGS,
        )
    ).strip()

    return f"{quote}\n\n{hashtags}".strip()


def verify_reel_url():
    """
    GitHub Raw may serve MP4 files as application/octet-stream.
    That is acceptable here because the URL is publicly reachable and the
    file was generated as an MP4 by ffmpeg.

    Do NOT require video/mp4 Content-Type.
    """
    response = requests.get(
        REEL_URL,
        stream=True,
        allow_redirects=True,
        timeout=45,
        headers={
            "User-Agent": "quote-automation/1.0"
        },
    )

    content_type = (
        response.headers.get(
            "Content-Type",
            "",
        )
        or ""
    ).lower()

    print(
        f"Reel URL HTTP: {response.status_code}"
    )
    print(
        f"Reel URL Content-Type: {content_type}"
    )
    print(
        f"Reel URL final URL: {response.url}"
    )

    # GitHub Raw can return:
    #   video/mp4
    #   application/octet-stream
    # The important requirement is that the URL is public and returns 200.
    if not response.ok:
        fail(
            "Reel URL is not publicly reachable: "
            f"HTTP {response.status_code}"
        )

    return content_type


def wait_for_container(
    container_id: str,
):
    """
    Instagram processes Reels asynchronously.
    Poll until the container is FINISHED.
    """
    for attempt in range(24):
        result = api_get(
            container_id,
            {
                "fields": (
                    "status_code,status"
                ),
                "access_token": ACCESS_TOKEN,
            },
        )

        status_code = result.get(
            "status_code"
        )
        status = result.get(
            "status",
            "",
        )

        print(
            f"Reel container "
            f"[{attempt + 1}/24]: "
            f"{status_code} - {status}"
        )

        if status_code == "FINISHED":
            return

        if status_code in {
            "ERROR",
            "EXPIRED",
        }:
            fail(
                "Instagram Reel media container "
                f"failed: {result}"
            )

        time.sleep(10)

    fail(
        "Instagram Reel media container did not "
        "reach FINISHED status."
    )


def main():
    require_config()

    metadata = load_metadata()
    caption = build_caption(
        metadata
    )

    content_type = verify_reel_url()

    print(
        f"Instagram User ID: {IG_USER_ID}"
    )
    print(
        f"Instagram API version: "
        f"{META_API_VERSION}"
    )
    print(
        f"Reel URL: {REEL_URL}"
    )
    print(
        f"Reel source Content-Type: "
        f"{content_type}"
    )

    # Instagram Login / Instagram User Access Token flow.
    # Create a Reel media container.
    container = api_post(
        f"{IG_USER_ID}/media",
        {
            "media_type": "REELS",
            "video_url": REEL_URL,
            "caption": caption,
            "access_token": ACCESS_TOKEN,
        },
    )

    creation_id = container.get(
        "id"
    )

    if not creation_id:
        fail(
            "Instagram did not return a Reel "
            f"creation ID: {container}"
        )

    print(
        f"Created Reel container: "
        f"{creation_id}"
    )

    wait_for_container(
        creation_id
    )

    published = api_post(
        f"{IG_USER_ID}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": ACCESS_TOKEN,
        },
    )

    media_id = published.get(
        "id"
    )

    if not media_id:
        fail(
            "Instagram did not return a published "
            f"Reel media ID: {published}"
        )

    print(
        "Instagram Reel published successfully. "
        f"Media ID: {media_id}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
