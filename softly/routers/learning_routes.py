from fastapi import APIRouter, Query

from .. import learning

router = APIRouter(prefix="/learning")


@router.get("/stats")
def stats():
    return learning.stats()


@router.get("/events")
def events(limit: int = Query(60, ge=1, le=500)):
    return {"events": learning.read_events(limit)}
