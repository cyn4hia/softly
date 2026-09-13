import asyncio

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from .. import learning, media
from ..schemas import TagUpdate

router = APIRouter()


@router.get("/library")
def library(kind: str = Query("video", pattern="^(video|audio)$")):
    return {"items": media.list_library(kind), "sources": media.source_status()}


@router.post("/library/upload")
async def upload(files: list[UploadFile] = File(...)):
    """drag-and-drop target: files land in data/examples/ only."""
    saved, errors = [], []
    for f in files:
        try:
            item = await asyncio.to_thread(media.save_upload, f.filename, f.file)
            saved.append(item)
            learning.record("library_upload", None, {"path": item["path"], "size": item["size"]})
        except media.MediaInvalid as exc:
            errors.append({"name": f.filename or "unnamed file", "error": str(exc)})
        finally:
            await f.close()
    return {"saved": saved, "errors": errors}


@router.post("/library/tags")
def set_tags(update: TagUpdate):
    media.set_tags(update.source, update.path, update.tags)
    learning.record("library_tag", None, update.model_dump())
    return {"ok": True}


@router.get("/media/{source}/{rel:path}")
def stream_media(source: str, rel: str, range: str | None = Header(default=None)):
    try:
        path = media.resolve(source, rel)
    except media.MediaNotFound as exc:
        raise HTTPException(404, str(exc))
    except media.MediaForbidden as exc:
        raise HTTPException(403, str(exc))
    return media.media_response(path, range)
