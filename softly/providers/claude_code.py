"""the real generation engine: Claude Fable 5 writes a renderable animation
script from the prompt + inspo frames + accumulated feedback, and the local
renderer turns it into a video. revisions feed feedback back into the code.
"""
from __future__ import annotations

import asyncio
import base64
import re

from ..config import get_settings, has_anthropic_credentials
from ..frames import extract_frames
from ..media import resolve
from ..rendering import render
from .base import GenerationRequest, GenerationResult, ProviderUnavailable

MAX_TOKENS = 32000
MAX_REPAIRS = 2  # render-failure round-trips before giving up

SYSTEM_PROMPT = """\
You are softly, a motion-graphics generation agent. You write Python animation \
scripts that render into short vertical videos for a content creator's social feeds.

## Output contract
Reply with exactly one Python code block containing a complete, self-contained \
script that defines:

    WIDTH = 720          # canvas width  (vertical format; long edge <= 1920)
    HEIGHT = 1280        # canvas height
    FPS = 30
    DURATION = 6.0       # seconds, 1 - 15
    def draw_frame(t: float) -> np.ndarray
        # returns an (HEIGHT, WIDTH, 3) uint8 RGB array for time t in seconds

Hard rules:
- Import only: numpy (as np), math, random, colorsys. No file, network, or OS \
access — the script runs in a bare renderer that just calls draw_frame per frame.
- Vectorize with numpy. No per-pixel Python loops; each frame must render in \
well under a second at the chosen resolution.
- Seed all randomness (random.seed, np.random.seed) so re-renders are identical.
- There is no text/font rendering. Build everything from shapes, gradients, \
particles, glows, waves, and motion.

## Craft
This is feed content: land a visual hook in the first second, keep motion \
smooth (ease in/out, no jitter), keep the palette cohesive, and end cleanly — \
loop seamlessly when it suits the vibe. Match the requested genre tags. When \
inspo frames are attached, treat them as the visual reference for palette, \
density, mood, and composition — you are making something in that family, not \
copying it. If a sound is described, shape the energy and pacing of the motion \
to suit it; the harness muxes the audio in afterwards.

## Revisions
When previous code and feedback are provided, the feedback is ground truth for \
what the creator wants. Apply it surgically: keep what was praised, change what \
was criticized, and return the complete revised script (never a diff).
"""


def _extract_code(text: str) -> str | None:
    blocks = re.findall(r"```[\w+-]*[ \t]*\r?\n(.*?)```", text, re.DOTALL)
    candidates = [b for b in blocks if "def draw_frame" in b] or blocks
    if candidates:
        return max(candidates, key=len).strip()
    if "def draw_frame" in text:
        return text.strip()
    return None


def _image_block(jpeg: bytes) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(jpeg).decode("ascii"),
        },
    }


def _format_feedback(feedback_history: list[dict]) -> str:
    lines = []
    for fb in feedback_history:
        parts = []
        if fb.get("rating"):
            parts.append(f"{fb['rating']}/5 hearts")
        for aspect, vote in (fb.get("aspects") or {}).items():
            parts.append(f"{aspect}: {'liked' if vote == 'up' else 'needs work'}")
        if fb.get("text"):
            parts.append(f'"{fb["text"]}"')
        if parts:
            lines.append("- " + " | ".join(parts))
    return "\n".join(lines) if lines else "(none yet)"


class ClaudeCodeProvider:
    name = "claude"

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if not has_anthropic_credentials():
            raise ProviderUnavailable(
                "no Anthropic credentials found — set ANTHROPIC_API_KEY (or run "
                "`ant auth login`) and restart softly to generate for real"
            )
        try:
            import anthropic
        except ImportError:
            raise ProviderUnavailable("the 'anthropic' package is not installed — run `uv sync`")

        settings = get_settings()
        # frame sampling decodes video — keep it off the event loop
        content = await asyncio.to_thread(self._build_content, request)
        messages: list[dict] = [{"role": "user", "content": content}]
        request.output_dir.mkdir(parents=True, exist_ok=True)
        script_path = request.output_dir / f"v{request.version_number}.py"
        out_path = request.output_dir / f"v{request.version_number}.mp4"

        sound_path = None
        if request.sound:
            try:
                sound_path = resolve(request.sound["source"], request.sound["path"])
            except Exception:
                sound_path = None

        client = anthropic.AsyncAnthropic(max_retries=2)
        code = None
        log = ""
        try:
            for attempt in range(1 + MAX_REPAIRS):
                response = await self._call(client, settings, messages)
                if response.stop_reason == "refusal":
                    return GenerationResult(
                        ok=False, media=None, provider=self.name, code=code,
                        note="the model declined this request — try rephrasing the prompt",
                    )
                if response.stop_reason == "max_tokens":
                    return GenerationResult(
                        ok=False, media=None, provider=self.name, code=code,
                        note="the script ran out of room mid-write — try a simpler prompt",
                    )
                text = "".join(b.text for b in response.content if b.type == "text")
                code = _extract_code(text)
                if not code:
                    return GenerationResult(
                        ok=False, media=None, provider=self.name,
                        note="the model didn't return a renderable script — try again or adjust the prompt",
                        log=text[:2000],
                    )
                script_path.write_text(code)
                ok, log = await asyncio.to_thread(render, script_path, out_path, sound_path)
                if ok:
                    served_by = getattr(response, "model", settings.model)
                    note = f"generated by {served_by} (effort: {settings.effort})"
                    if request.version_number > 1:
                        note += " — revised from your feedback"
                    if attempt:
                        note += f" · self-repaired after {attempt} render error(s)"
                    if request.sound and sound_path is None:
                        note += " · sound file couldn't be read, so this take is silent"
                    elif "warning:" in log:
                        note += " · render finished with warnings — peek at the log"
                    return GenerationResult(
                        ok=True,
                        media={
                            "source": "generated",
                            "path": f"{request.session_id}/{out_path.name}",
                            "name": out_path.stem,
                        },
                        provider=self.name, code=code, note=note, log=log,
                    )
                # feed the render error back so the model can fix its own script
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        f"The renderer failed with:\n\n{log[-3000:]}\n\n"
                        "Return the complete corrected script (full code block, same contract)."
                    ),
                })
        except anthropic.AuthenticationError:
            raise ProviderUnavailable(
                "Anthropic credentials were rejected — check ANTHROPIC_API_KEY or re-run `ant auth login`"
            )
        except anthropic.APIConnectionError:
            return GenerationResult(
                ok=False, media=None, provider=self.name, code=code,
                note="couldn't reach the Anthropic API — check your connection and try revise again",
            )
        except anthropic.APIStatusError as exc:
            return GenerationResult(
                ok=False, media=None, provider=self.name, code=code,
                note=f"the Anthropic API returned an error ({exc.status_code}) — try again in a bit",
                log=str(getattr(exc, "message", exc))[:2000],
            )

        return GenerationResult(
            ok=False, media=None, provider=self.name, code=code,
            note=f"the script kept failing to render after {MAX_REPAIRS} repair attempts",
            log=log[-3000:],
        )

    async def _call(self, client, settings, messages):
        kwargs: dict = dict(
            model=settings.model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": settings.effort},
            messages=messages,
        )
        if settings.fallback_model:
            # refusal fallback: if fable declines, the API reruns on the fallback model
            async with client.beta.messages.stream(
                betas=["server-side-fallback-2026-06-01"],
                fallbacks=[{"model": settings.fallback_model}],
                **kwargs,
            ) as stream:
                return await stream.get_final_message()
        async with client.messages.stream(**kwargs) as stream:
            return await stream.get_final_message()

    def _build_content(self, request: GenerationRequest) -> list[dict]:
        content: list[dict] = []
        for i, ref in enumerate(request.inspo, 1):
            try:
                path = resolve(ref["source"], ref["path"])
            except Exception:
                continue
            frames = extract_frames(path)
            if not frames:
                continue
            content.append({
                "type": "text",
                "text": f"inspo clip {i}: \"{ref.get('name') or ref['path']}\" — sampled frames:",
            })
            content.extend(_image_block(f) for f in frames)

        brief = [f"prompt: {request.prompt}"]
        if request.tags:
            brief.append(f"genre / vibe tags: {', '.join(request.tags)}")
        if request.sound:
            brief.append(
                f"sound: \"{request.sound.get('name') or request.sound['path']}\" "
                "(will be muxed onto your video — match its energy)"
            )
        if request.previous_code:
            brief.append(
                "\nprevious version's script:\n```python\n" + request.previous_code + "\n```"
            )
            brief.append("feedback so far:\n" + _format_feedback(request.feedback_history))
            if request.instructions:
                brief.append(f"revision instructions: {request.instructions}")
            brief.append("Apply the feedback and return the complete revised script.")
        else:
            brief.append("Write the animation script for the first take.")
        content.append({"type": "text", "text": "\n".join(brief)})
        return content
