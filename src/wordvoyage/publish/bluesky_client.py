from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_]*)")
MAX_BSKY_GRAPHEME_SAFE = 300


def _enforce_text_limit(text: str, max_len: int = MAX_BSKY_GRAPHEME_SAFE) -> str:
    """
    Final safety net before publish.
    Python len() counts Unicode code points, so len(text) <= 300 guarantees
    grapheme count is not above 300.
    """
    if len(text) <= max_len:
        return text

    # Preserve hashtag tail when possible.
    tag_start = text.rfind("\n\n#")
    if tag_start > 0:
        body = text[:tag_start].rstrip()
        tags = text[tag_start:]
        body_limit = max_len - len(tags)
        if body_limit > 8:
            if len(body) > body_limit:
                body = body[: max(1, body_limit - 3)].rstrip() + "..."
            return f"{body}{tags}"

    return text[: max(1, max_len - 3)].rstrip() + "..."


def _build_hashtag_facets(text: str) -> list[dict]:
    facets: list[dict] = []
    for match in HASHTAG_RE.finditer(text):
        tag = match.group(1)
        start_char = match.start()
        end_char = match.end()
        byte_start = len(text[:start_char].encode("utf-8"))
        byte_end = len(text[:end_char].encode("utf-8"))
        facets.append(
            {
                "index": {
                    "byteStart": byte_start,
                    "byteEnd": byte_end,
                },
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#tag",
                        "tag": tag,
                    }
                ],
            }
        )
    return facets


def _client_login(handle: str, app_password: str):
    if not handle or not app_password:
        raise RuntimeError("Missing Bluesky credentials. Set BLUESKY_HANDLE and BLUESKY_APP_PASSWORD.")
    try:
        from atproto import Client
    except Exception as exc:
        raise RuntimeError("atproto dependency is not available. Install project dependencies first.") from exc
    client = Client()
    client.login(handle, app_password)
    return client


def _create_record(client, record: dict) -> dict:
    repo_did = getattr(getattr(client, "me", None), "did", None)
    if not repo_did:
        raise RuntimeError("Unable to resolve authenticated DID from Bluesky client.")
    created = client.com.atproto.repo.create_record(
        {
            "repo": repo_did,
            "collection": "app.bsky.feed.post",
            "record": record,
        }
    )
    uri = created.get("uri") if isinstance(created, dict) else getattr(created, "uri", None)
    cid = created.get("cid") if isinstance(created, dict) else getattr(created, "cid", None)
    if not uri or not cid:
        raise RuntimeError("Bluesky post was created but URI/CID were not returned.")
    return {"uri": uri, "cid": cid}


def post_with_image(
    *,
    handle: str,
    app_password: str,
    caption: str,
    alt_text: str,
    image_path: str,
    reply_to_uri: str | None = None,
    reply_to_cid: str | None = None,
) -> dict:
    """Create a Bluesky post with an image and optional reply threading."""
    caption = _enforce_text_limit(caption)
    image_file = Path(image_path)
    image_bytes = image_file.read_bytes()
    client = _client_login(handle=handle, app_password=app_password)

    upload = client.upload_blob(image_bytes)
    blob = upload.get("blob") if isinstance(upload, dict) else getattr(upload, "blob", None)
    if not blob:
        raise RuntimeError("Failed to upload image blob to Bluesky.")

    with Image.open(image_file) as img:
        img_w, img_h = img.size

    record: dict = {
        "$type": "app.bsky.feed.post",
        "text": caption,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [
                {
                    "alt": alt_text,
                    "image": blob,
                    "aspectRatio": {"width": int(img_w), "height": int(img_h)},
                }
            ],
        },
    }
    facets = _build_hashtag_facets(caption)
    if facets:
        record["facets"] = facets
    if reply_to_uri and reply_to_cid:
        ref = {"uri": reply_to_uri, "cid": reply_to_cid}
        record["reply"] = {"root": ref, "parent": ref}

    return _create_record(client, record)


def post_text(
    *,
    handle: str,
    app_password: str,
    caption: str,
    reply_to_uri: str | None = None,
    reply_to_cid: str | None = None,
) -> dict:
    """Create a text-only Bluesky post with optional reply threading."""
    caption = _enforce_text_limit(caption)
    client = _client_login(handle=handle, app_password=app_password)
    record: dict = {
        "$type": "app.bsky.feed.post",
        "text": caption,
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    facets = _build_hashtag_facets(caption)
    if facets:
        record["facets"] = facets
    if reply_to_uri and reply_to_cid:
        ref = {"uri": reply_to_uri, "cid": reply_to_cid}
        record["reply"] = {"root": ref, "parent": ref}
    return _create_record(client, record)
