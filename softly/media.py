"""media sources + range-aware streaming.

sources map to directories on disk. the user's own library ("mine"/"sounds")
lives outside the repo and is only ever read from — never copied, never
written. resolve() raises domain exceptions so non-web callers (providers)
don't inherit the web framework; routers translate them to HTTP.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
from pathlib import Path

from fastapi.responses import Response, StreamingResponse

from .config import EXAMPLES_DIR, GENERATED_DIR, LEARNING_DIR, get_settings
from .store import atomic_write_json

VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".avi", ".mkv"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
CHUNK = 512 * 1024
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
TAGS_FILE = LEARNING_DIR / "library_tags.json"

_UNSAFE_NAME = re.compile(r"[^a-zA-Z0-9._ -]+")


class MediaNotFound(Exception):
    pass


class MediaForbidden(Exception):
    pass


class MediaInvalid(Exception):
    pass


def source_roots() -> dict[str, Path | None]:
    s = get_settings()
    return {
        "mine": s.videos_dir,
        "sounds": s.sounds_dir,
        "examples": EXAMPLES_DIR,
        "generated": GENERATED_DIR,
    }


def source_status() -> dict[str, dict]:
    status = {}
    for name, root in source_roots().items():
        status[name] = {
            "configured": root is not None,
            "exists": root is not None and root.exists(),
            "path": str(root) if root else None,
        }
    return status


def resolve(source: str, rel: str) -> Path:
    """map a {source, relative path} ref to a real file, or raise.
    only media files inside the source root are ever served."""
    root = source_roots().get(source)
    if root is None or not root.exists():
        raise MediaNotFound(f"media source '{source}' is not configured")
    rel_path = Path(rel)
    if rel_path.is_absolute() or any(part.startswith(".") for part in rel_path.parts):
        raise MediaForbidden("path escapes its media source")
    root = root.resolve()
    path = (root / rel_path).resolve()
    if not path.is_relative_to(root):
        raise MediaForbidden("path escapes its media source")
    if path.suffix.lower() not in VIDEO_EXT | AUDIO_EXT:
        raise MediaForbidden("only media files are served")
    if not path.is_file():
        raise MediaNotFound("file not found")
    return path


def load_tags() -> dict[str, list[str]]:
    try:
        return json.loads(TAGS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def set_tags(source: str, rel: str, tags: list[str]) -> None:
    all_tags = load_tags()
    key = f"{source}:{rel}"
    cleaned = list(dict.fromkeys(t.strip() for t in tags if t.strip()))  # dedupe, keep order
    if cleaned:
        all_tags[key] = cleaned
    else:
        all_tags.pop(key, None)
    TAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(TAGS_FILE, all_tags, sort_keys=True)


def _unique_path(directory: Path, name: str) -> Path:
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate = directory / name
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


def save_upload(filename: str, fileobj) -> dict:
    """streams an uploaded file into data/examples/ — the only library source
    softly ever writes to (private folders stay read-only, always).
    returns a library item dict; raises MediaInvalid on bad input."""
    name = _UNSAFE_NAME.sub("_", Path(filename or "").name).strip("._ ")
    if not name or not Path(name).stem:
        raise MediaInvalid("that filename is a little too mysterious")
    suffix = Path(name).suffix.lower()
    if suffix not in VIDEO_EXT | AUDIO_EXT:
        allowed = ", ".join(sorted(e.lstrip(".") for e in VIDEO_EXT | AUDIO_EXT))
        raise MediaInvalid(f"only media files can join the library ({allowed})")

    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    dest = _unique_path(EXAMPLES_DIR, name)
    tmp = dest.with_name(dest.name + ".part")
    written = 0
    try:
        with tmp.open("wb") as out:
            while chunk := fileobj.read(CHUNK):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise MediaInvalid("that file is over 512 MB — a bit much for an example clip")
                out.write(chunk)
        if written == 0:
            raise MediaInvalid("that file is empty")
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)

    stat = dest.stat()
    return {
        "source": "examples",
        "path": dest.relative_to(EXAMPLES_DIR).as_posix(),
        "name": dest.stem,
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "tags": [],
    }


def _iter_files(root: Path, exts: set[str]):
    for path in sorted(root.rglob("*")):
        try:
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            if path.suffix.lower() in exts:
                yield path
        except OSError:
            continue  # vanished mid-scan or unreadable — skip, don't 500


def list_library(kind: str = "video") -> list[dict]:
    exts = VIDEO_EXT if kind == "video" else AUDIO_EXT
    sources = ("mine", "examples", "generated") if kind == "video" else ("sounds", "examples")
    tags = load_tags()
    roots = source_roots()
    items: list[dict] = []
    for source in sources:
        root = roots.get(source)
        if root is None or not root.exists():
            continue
        for path in _iter_files(root, exts):
            rel = path.relative_to(root).as_posix()
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append(
                {
                    "source": source,
                    "path": rel,
                    "name": path.stem,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "tags": tags.get(f"{source}:{rel}", []),
                }
            )
    items.sort(key=lambda i: i["modified"], reverse=True)
    return items


def _parse_range(range_header: str, size: int):
    """returns (start, end), 'unsatisfiable', or None (malformed → ignore
    the header and serve the full file, per RFC 9110)."""
    try:
        unit, _, spec = range_header.partition("=")
        if unit.strip().lower() != "bytes":
            return None
        spec = spec.split(",")[0].strip()  # browsers send single ranges for video
        first, dash, last = spec.partition("-")
        if not dash:
            return None
        if first:
            start = int(first)
            end = int(last) if last else size - 1
        elif last:
            start = max(size - int(last), 0)
            end = size - 1
        else:
            return None
        if start > end:
            return None
        if start >= size:
            return "unsatisfiable"
        return start, min(end, size - 1)
    except ValueError:
        return None


def media_response(path: Path, range_header: str | None) -> Response:
    size = path.stat().st_size
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {"Accept-Ranges": "bytes", "Content-Type": content_type}

    start, end, status = 0, size - 1, 200
    if range_header:
        parsed = _parse_range(range_header, size)
        if parsed == "unsatisfiable":
            return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
        if parsed is not None:
            start, end = parsed
            status = 206
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    length = end - start + 1
    headers["Content-Length"] = str(length)

    def reader(offset: int = start, remaining: int = length):
        with path.open("rb") as f:
            f.seek(offset)
            while remaining > 0:
                chunk = f.read(min(CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(reader(), status_code=status, headers=headers)
