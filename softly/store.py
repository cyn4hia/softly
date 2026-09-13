"""JSON-file persistence for creation sessions.

one file per session under data/learning/sessions/ — this *is* part of the
learning data the repo tracks over time: prompts, generated code, feedback,
and revision history. the video binaries themselves stay out of git.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .config import GENERATED_DIR, SESSIONS_DIR


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return secrets.token_hex(5)


def atomic_write_json(path: Path, obj: dict, *, sort_keys: bool = False) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=sort_keys))
    os.replace(tmp, path)


def _path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def get_session(session_id: str) -> dict | None:
    p = _path(session_id)
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def save_session(session: dict) -> None:
    session["updated_at"] = now_iso()
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_path(session["id"]), session)


def list_sessions() -> list[dict]:
    sessions = []
    for p in SESSIONS_DIR.glob("*.json"):
        try:
            sessions.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return sessions


def create_session(data: dict) -> dict:
    """data: plain dict (router passes schemas.SessionCreate.model_dump()) —
    keeps this layer free of the API schema types."""
    session = {
        "id": new_id(),
        "title": (data.get("title") or "").strip(),
        "prompt": (data.get("prompt") or "").strip(),
        "tags": [t.strip() for t in data.get("tags") or [] if t and t.strip()],
        "inspo": data.get("inspo") or [],
        "sound": data.get("sound"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "versions": [],
    }
    save_session(session)
    return session


def delete_session(session_id: str) -> bool:
    p = _path(session_id)
    if not p.exists():
        return False
    p.unlink()
    shutil.rmtree(GENERATED_DIR / session_id, ignore_errors=True)
    return True
