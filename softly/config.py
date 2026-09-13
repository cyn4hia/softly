"""settings — loaded from config/settings.yaml (gitignored), safe defaults otherwise.

the repo never stores paths to (or copies of) the user's private video folder;
that lives only in the local settings file. api keys are read from the
environment, never from tracked files.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "settings.yaml"
DATA_DIR = ROOT / "data"
EXAMPLES_DIR = DATA_DIR / "examples"
GENERATED_DIR = DATA_DIR / "generated"
LEARNING_DIR = DATA_DIR / "learning"
SESSIONS_DIR = LEARNING_DIR / "sessions"
WEB_DIR = ROOT / "web"


@dataclass(frozen=True)
class Settings:
    videos_dir: Path | None
    sounds_dir: Path | None
    provider: str
    model: str
    effort: str
    fallback_model: str | None
    host: str
    port: int


def _dir_or_none(raw: object) -> Path | None:
    if not raw:
        return None
    return Path(os.path.expanduser(str(raw)))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    raw: object = {}
    if CONFIG_FILE.exists():
        raw = yaml.safe_load(CONFIG_FILE.read_text()) or {}
    if not isinstance(raw, dict):  # a scalar/list yaml root shouldn't crash startup
        raw = {}
    library = raw.get("library") or {}
    generation = raw.get("generation") or {}
    server = raw.get("server") or {}
    fallback = generation.get("fallback_model", "claude-opus-4-8")
    return Settings(
        videos_dir=_dir_or_none(library.get("videos_dir")),
        sounds_dir=_dir_or_none(library.get("sounds_dir")),
        provider=str(generation.get("provider") or "claude"),
        model=str(generation.get("model") or "claude-fable-5"),
        effort=str(generation.get("effort") or "xhigh"),
        fallback_model=str(fallback) if fallback else None,
        host=str(server.get("host") or "127.0.0.1"),
        port=int(server.get("port") or 8765),
    )


def has_anthropic_credentials() -> bool:
    """single audited place that looks for credentials; the values themselves
    are never read here — the SDK resolves them itself."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    config_dir = Path(os.environ.get("ANTHROPIC_CONFIG_DIR", Path.home() / ".config" / "anthropic"))
    return config_dir.exists()


def ensure_data_dirs() -> None:
    for d in (EXAMPLES_DIR, GENERATED_DIR, SESSIONS_DIR):
        d.mkdir(parents=True, exist_ok=True)
