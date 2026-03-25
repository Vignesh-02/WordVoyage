from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z][A-Za-z0-9_]*)")


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
    image_bytes = Path(image_path).read_bytes()
    client = _client_login(handle=handle, app_password=app_password)

    upload = client.upload_blob(image_bytes)
    blob = upload.get("blob") if isinstance(upload, dict) else getattr(upload, "blob", None)
    if not blob:
        raise RuntimeError("Failed to upload image blob to Bluesky.")

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
