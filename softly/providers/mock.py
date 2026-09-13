"""placeholder provider: points the take at an inspo clip so the full
create → watch → feedback → revise loop can be exercised without API
credentials. nothing is ever copied — private files stay exactly where
they are and are only streamed for playback."""
from __future__ import annotations

from ..media import resolve
from .base import GenerationRequest, GenerationResult


class MockEchoProvider:
    name = "mock"

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if not request.inspo:
            return GenerationResult(
                ok=True,
                media=None,
                provider=self.name,
                note="mock provider: no inspo clip to echo, so no video this take. "
                     "add an inspo clip, or connect the claude provider for real generation.",
            )
        ref = request.inspo[0]
        try:
            resolve(ref["source"], ref["path"])  # existence check only — no copy
        except Exception:
            return GenerationResult(
                ok=False, media=None, provider=self.name,
                note=f"mock provider: couldn't read inspo clip '{ref.get('path')}'",
            )
        what = "revised take" if request.version_number > 1 else "first take"
        return GenerationResult(
            ok=True,
            media={"source": ref["source"], "path": ref["path"], "name": ref.get("name")},
            provider=self.name,
            note=f"mock {what}: showing inspo clip '{ref.get('name') or ref['path']}' in place "
                 "as a stand-in — the claude provider will generate for real once connected.",
        )
