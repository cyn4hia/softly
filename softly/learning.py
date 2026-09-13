"""append-only event log + derived stats.

events.jsonl is the raw signal the reward function will eventually train on
(later joined with view/interaction statistics once those are imported).
stats are always derived fresh from the session documents, which remain the
source of truth — the event log is never read back to reconstruct state.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from .config import LEARNING_DIR
from .store import list_sessions, now_iso

EVENTS_FILE = LEARNING_DIR / "events.jsonl"

_STOPWORDS = {
    "the", "and", "but", "for", "with", "this", "that", "was", "are", "you",
    "not", "too", "very", "more", "less", "like", "just", "its", "it's",
    "bit", "little", "make", "made", "maybe", "could", "should", "would",
    "want", "need", "feel", "feels", "think", "video", "clip", "there",
    "have", "has", "had", "can", "will", "into", "out", "than", "then",
}


def record(event_type: str, session_id: str | None, payload: dict) -> None:
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": now_iso(), "type": event_type, "session_id": session_id, "payload": payload}
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(limit: int = 60) -> list[dict]:
    if not EVENTS_FILE.exists():
        return []
    events: list[dict] = []
    for line in EVENTS_FILE.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    events.reverse()
    return events


def stats() -> dict:
    sessions = list_sessions()
    versions = feedback_count = 0
    ratings: list[int] = []
    tag_counter: Counter = Counter()
    tag_ratings: dict[str, list[int]] = {}
    aspects: dict[str, dict[str, int]] = {}
    words: Counter = Counter()

    for s in sessions:
        for t in s.get("tags", []):
            tag_counter[t] += 1
        for v in s.get("versions", []):
            versions += 1
            for fb in v.get("feedback", []):
                feedback_count += 1
                if fb.get("rating"):
                    ratings.append(fb["rating"])
                    for t in s.get("tags", []):
                        tag_ratings.setdefault(t, []).append(fb["rating"])
                for name, vote in (fb.get("aspects") or {}).items():
                    slot = aspects.setdefault(name, {"up": 0, "down": 0})
                    if vote in slot:
                        slot[vote] += 1
                for word in re.findall(r"[a-zA-Z']{3,}", fb.get("text", "").lower()):
                    if word not in _STOPWORDS:
                        words[word] += 1

    return {
        "sessions": len(sessions),
        "versions": versions,
        "feedback": feedback_count,
        "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "tags": tag_counter.most_common(),
        "tag_ratings": {t: round(sum(r) / len(r), 2) for t, r in tag_ratings.items()},
        "aspects": aspects,
        "keywords": words.most_common(12),
    }
