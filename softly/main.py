from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__, media, store
from .config import WEB_DIR, ensure_data_dirs, get_settings
from .routers import learning_routes, library, sessions


class NoCacheStaticFiles(StaticFiles):
    """always revalidate static assets — the frontend has no build step or
    fingerprinted filenames, so heuristic browser caching would happily serve
    stale JS modules after an update."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def _reconcile_orphaned_renders() -> None:
    """a restart mid-generation would otherwise leave takes stuck in
    'rendering' forever (the in-flight set is memory-only)."""
    for session in store.list_sessions():
        dirty = False
        for version in session.get("versions", []):
            if version.get("status") == "rendering":
                version["status"] = "failed"
                version["note"] = "interrupted by a server restart — revise to try again"
                dirty = True
        if dirty:
            store.save_session(session)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _reconcile_orphaned_renders()
    yield


def create_app() -> FastAPI:
    ensure_data_dirs()
    settings = get_settings()
    app = FastAPI(title="softly", version=__version__, lifespan=_lifespan)

    # the server can stream files from the private library — refuse requests
    # whose Host isn't local (DNS-rebinding defense)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", settings.host],
    )

    api = APIRouter(prefix="/api")
    api.include_router(sessions.router)
    api.include_router(library.router)
    api.include_router(learning_routes.router)

    @api.get("/health")
    def health():
        return {"ok": True, "version": __version__}

    @api.get("/config")
    def config_info():
        s = get_settings()
        return {
            "provider": s.provider,
            "model": s.model,
            "effort": s.effort,
            "sources": media.source_status(),
            "version": __version__,
        }

    app.include_router(api)
    app.mount("/", NoCacheStaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()


def run() -> None:
    s = get_settings()
    uvicorn.run(app, host=s.host, port=s.port, log_level="info")
