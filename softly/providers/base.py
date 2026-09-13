"""generation-provider contract.

everything downstream of the GUI talks to providers only through this
interface, so swapping the backend (claude ↔ mock ↔ whatever comes later)
is a config change, not a refactor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class ProviderUnavailable(Exception):
    """raised when a provider can't run at all (e.g. no API credentials);
    the caller may fall back to another provider."""


@dataclass
class GenerationRequest:
    session_id: str
    version_number: int
    prompt: str
    tags: list[str]
    inspo: list[dict]              # MediaRef dicts
    sound: dict | None             # MediaRef dict or None
    feedback_history: list[dict]   # prior feedback entries, oldest first
    instructions: str              # revision instructions ("" for the first take)
    previous_code: str | None      # last version's animation script, if any
    output_dir: Path


@dataclass
class GenerationResult:
    ok: bool
    media: dict | None             # MediaRef dict into the "generated" source
    note: str
    provider: str
    code: str | None = None        # the animation script behind the video
    log: str = ""


class GenerationProvider(Protocol):
    name: str

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...
