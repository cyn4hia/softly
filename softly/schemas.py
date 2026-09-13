"""API input models. session documents themselves are stored as plain JSON
dicts so the shape can evolve without migrations while the project is young."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Source = Literal["mine", "examples", "generated", "sounds"]


class MediaRef(BaseModel):
    source: Source
    path: str
    name: str | None = None


class SessionCreate(BaseModel):
    title: str = ""
    prompt: str = Field(min_length=1)
    tags: list[str] = []
    inspo: list[MediaRef] = []
    sound: MediaRef | None = None

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("prompt must not be blank")
        return value


class FeedbackIn(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    text: str = ""
    aspects: dict[str, Literal["up", "down"]] = {}


class ReviseIn(BaseModel):
    instructions: str = ""


class TagUpdate(BaseModel):
    source: Source
    path: str
    tags: list[str]
