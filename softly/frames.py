"""samples still frames from inspo clips so the generation model can *see*
the visual reference, not just read a filename."""
from __future__ import annotations

import io
from pathlib import Path

FRAME_POINTS = (0.15, 0.5, 0.85)  # early / middle / late
MAX_EDGE = 768
JPEG_QUALITY = 80


def extract_frames(path: Path, count: int = 3) -> list[bytes]:
    """returns up to `count` JPEG-encoded frames; empty list if the clip
    can't be decoded (frames are a best-effort enrichment, never a blocker)."""
    try:
        import av
        from PIL import Image  # noqa: F401  (frame.to_image needs pillow)
    except ImportError:
        return []

    frames: list[bytes] = []
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            duration = 0.0
            if stream.duration and stream.time_base:
                duration = float(stream.duration * stream.time_base)
            elif container.duration:
                duration = container.duration / av.time_base

            for frac in FRAME_POINTS[: max(1, count)]:
                try:
                    if duration > 0 and stream.time_base:
                        offset = int((duration * frac) / stream.time_base)
                        container.seek(offset, stream=stream)
                    for frame in container.decode(stream):
                        img = frame.to_image().convert("RGB")
                        img.thumbnail((MAX_EDGE, MAX_EDGE))
                        buf = io.BytesIO()
                        img.save(buf, "JPEG", quality=JPEG_QUALITY)
                        frames.append(buf.getvalue())
                        break
                except Exception:
                    continue
    except Exception:
        return frames
    return frames
