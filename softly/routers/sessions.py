"""creation sessions: create → generate → feedback → revise.

generation runs as a background task (real providers take a while); the
frontend polls the session while a version is "rendering".
"""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, HTTPException

from .. import learning, store
from ..config import GENERATED_DIR, ROOT, get_settings
from ..providers import GenerationRequest, ProviderUnavailable, get_provider
from ..schemas import FeedbackIn, ReviseIn, SessionCreate

router = APIRouter(prefix="/sessions")

_rendering: set[str] = set()  # session ids with a generation in flight


def _scrub(text: str) -> str:
    """keep absolute local paths out of git-tracked session docs."""
    return text.replace(str(ROOT) + os.sep, "") if text else text


def _finish_version(session_id: str, version_id: str, patch: dict) -> None:
    """apply a generation outcome onto a FRESH read of the session doc —
    feedback may have been saved while the provider was working, and saving
    the task-start snapshot would silently destroy it (lost update)."""
    session = store.get_session(session_id)
    if session is None:
        return
    version = next((v for v in session["versions"] if v["id"] == version_id), None)
    if version is None:
        return
    version.update(patch)
    store.save_session(session)


def _summary(session: dict) -> dict:
    versions = session.get("versions", [])
    ratings = [
        fb["rating"]
        for v in versions
        for fb in v.get("feedback", [])
        if fb.get("rating")
    ]
    latest = versions[-1] if versions else None
    return {
        "id": session["id"],
        "title": session.get("title") or "",
        "prompt": session.get("prompt", ""),
        "tags": session.get("tags", []),
        "versions": len(versions),
        "feedback": sum(len(v.get("feedback", [])) for v in versions),
        "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "has_media": bool(latest and latest.get("media")),
        "status": latest.get("status") if latest else "empty",
        "rendering": session["id"] in _rendering,
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


def _get_or_404(session_id: str) -> dict:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(404, "creation not found")
    return session


def _with_state(session: dict) -> dict:
    return {**session, "rendering": session["id"] in _rendering}


async def _run_generation(session_id: str, version_id: str, instructions: str) -> None:
    try:
        session = store.get_session(session_id)
        if session is None:
            return
        version = next((v for v in session["versions"] if v["id"] == version_id), None)
        if version is None:
            return
        version_number = version["number"]
        settings = get_settings()
        previous = session["versions"][-2] if len(session["versions"]) > 1 else None
        request = GenerationRequest(
            session_id=session["id"],
            version_number=version_number,
            prompt=session["prompt"],
            tags=session.get("tags", []),
            inspo=session.get("inspo", []),
            sound=session.get("sound"),
            feedback_history=[fb for v in session["versions"] for fb in v.get("feedback", [])],
            instructions=instructions,
            previous_code=previous.get("code") if previous else None,
            output_dir=GENERATED_DIR / session["id"],
        )

        provider_name = settings.provider
        note_prefix = ""
        try:
            provider = get_provider(provider_name)
        except KeyError as exc:
            provider = get_provider("mock")
            provider_name = "mock"
            note_prefix = f"{exc.args[0]} — fell back to mock. "

        try:
            result = await provider.generate(request)
        except ProviderUnavailable as exc:
            provider_name = "mock"
            note_prefix = f"{exc} — fell back to mock. "
            result = await get_provider("mock").generate(request)
        except Exception as exc:  # a provider crash must never wedge the session
            _finish_version(session_id, version_id, {
                "status": "failed",
                "media": None,
                "note": _scrub((note_prefix + f"generation crashed: {exc}").strip()),
                "provider": provider_name,
            })
            learning.record("generation", session_id, {
                "version": version_number, "instructions": instructions,
                "provider": provider_name, "ok": False, "crashed": True,
            })
            return

        _finish_version(session_id, version_id, {
            "status": "ready" if result.ok else "failed",
            "media": result.media,
            "note": _scrub((note_prefix + result.note).strip()),
            "provider": result.provider,
            "code": result.code,
            "log": _scrub(result.log[-3000:] if result.log else ""),
        })
        learning.record(
            "generation",
            session_id,
            {
                "version": version_number,
                "prompt": session["prompt"],
                "tags": session.get("tags", []),
                "instructions": instructions,
                "provider": result.provider,
                "ok": result.ok,
            },
        )
    finally:
        _rendering.discard(session_id)


def _start_version(session: dict, instructions: str = "") -> dict:
    if session["id"] in _rendering:
        raise HTTPException(409, "a take is already rendering for this creation")
    version = {
        "id": store.new_id(),
        "number": len(session["versions"]) + 1,
        "status": "rendering",
        "provider": get_settings().provider,
        "media": None,
        "note": "",
        "code": None,
        "log": "",
        "instructions": instructions,
        "created_at": store.now_iso(),
        "feedback": [],
    }
    session["versions"].append(version)
    store.save_session(session)
    _rendering.add(session["id"])
    asyncio.get_running_loop().create_task(
        _run_generation(session["id"], version["id"], instructions)
    )
    return version


@router.get("")
def index():
    return {"sessions": [_summary(s) for s in store.list_sessions()]}


@router.post("")
async def create(payload: SessionCreate):
    session = store.create_session(payload.model_dump())
    learning.record(
        "creation",
        session["id"],
        {
            "prompt": session["prompt"],
            "tags": session["tags"],
            "inspo": [ref.get("name") or ref["path"] for ref in session["inspo"]],
            "sound": (session["sound"] or {}).get("name") if session["sound"] else None,
        },
    )
    _start_version(session)
    return _with_state(session)


@router.get("/{session_id}")
def show(session_id: str):
    return _with_state(_get_or_404(session_id))


@router.post("/{session_id}/versions/{version_id}/feedback")
def add_feedback(session_id: str, version_id: str, payload: FeedbackIn):
    session = _get_or_404(session_id)
    version = next((v for v in session["versions"] if v["id"] == version_id), None)
    if version is None:
        raise HTTPException(404, "take not found")
    if payload.rating is None and not payload.text.strip() and not payload.aspects:
        raise HTTPException(422, "feedback is empty")
    entry = {
        "id": store.new_id(),
        "rating": payload.rating,
        "text": payload.text.strip(),
        "aspects": payload.aspects,
        "created_at": store.now_iso(),
    }
    version["feedback"].append(entry)
    store.save_session(session)
    learning.record(
        "feedback",
        session["id"],
        {"version": version["number"], **{k: v for k, v in entry.items() if k != "id"}},
    )
    return _with_state(session)


@router.post("/{session_id}/revise")
async def revise(session_id: str, payload: ReviseIn):
    session = _get_or_404(session_id)
    if not session["versions"]:
        raise HTTPException(409, "nothing to revise yet")
    _start_version(session, payload.instructions.strip())
    return _with_state(session)


@router.delete("/{session_id}")
def destroy(session_id: str):
    if session_id in _rendering:
        raise HTTPException(409, "can't delete while a take is rendering")
    if not store.delete_session(session_id):
        raise HTTPException(404, "creation not found")
    learning.record("deleted", session_id, {})
    return {"ok": True}
