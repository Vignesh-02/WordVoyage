from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class PostRef:
    uri: str
    cid: str


def _state_path(day_root: Path) -> Path:
    return day_root / "thread_state.json"


def _load(day_root: Path) -> dict:
    path = _state_path(day_root)
    if not path.exists():
        return {"posts": {}, "contexts": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if "posts" not in loaded:
            loaded["posts"] = {}
        if "contexts" not in loaded:
            loaded["contexts"] = {}
        return loaded
    except Exception:
        return {"posts": {}, "contexts": {}}


def _save(day_root: Path, state: dict) -> None:
    day_root.mkdir(parents=True, exist_ok=True)
    path = _state_path(day_root)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_post_ref(day_root: Path, slot: str) -> PostRef | None:
    state = _load(day_root)
    slot_obj = state.get("posts", {}).get(slot)
    if not isinstance(slot_obj, dict):
        return None
    uri = slot_obj.get("uri")
    cid = slot_obj.get("cid")
    if not uri or not cid:
        return None
    return PostRef(uri=uri, cid=cid)


def set_post_ref(day_root: Path, slot: str, ref: PostRef) -> None:
    state = _load(day_root)
    state.setdefault("posts", {})
    state["posts"][slot] = {"uri": ref.uri, "cid": ref.cid}
    _save(day_root, state)


def get_slot_context(day_root: Path, slot: str) -> dict | None:
    state = _load(day_root)
    obj = state.get("contexts", {}).get(slot)
    if isinstance(obj, dict):
        return obj
    return None


def set_slot_context(day_root: Path, slot: str, context: dict) -> None:
    state = _load(day_root)
    state.setdefault("contexts", {})
    state["contexts"][slot] = context
    _save(day_root, state)


def synthetic_ref(post_date: date, slot: str, word: str) -> PostRef:
    seed = f"{post_date.isoformat()}::{slot}::{word}".encode("utf-8")
    digest = hashlib.sha256(seed).hexdigest()
    return PostRef(
        uri=f"at://dry-run.wordvoyage/app.bsky.feed.post/{post_date.isoformat()}-{slot}-{digest[:10]}",
        cid=f"dryrun-{digest[:24]}",
    )


def is_synthetic_ref(ref: PostRef) -> bool:
    return ref.uri.startswith("at://dry-run.wordvoyage/") or ref.cid.startswith("dryrun-")
