"""renders a softly animation script into an mp4.

runs in its own process so a misbehaving script can be timed out and killed
without taking the app down. the script contract (what the generation model
is asked to produce):

    WIDTH, HEIGHT   int    canvas size, default 720x1280 (vertical)
    FPS             int    default 30
    DURATION        float  seconds, default 6.0
    def draw_frame(t: float) -> np.ndarray   # (HEIGHT, WIDTH, 3) uint8 RGB

usage: python -m softly.render_cli script.py out.mp4 [sound_file]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

MAX_EDGE = 1920
MAX_DURATION = 15.0
MAX_FPS = 30
AUDIO_RATE = 44100


def _load_script(path: Path) -> dict:
    namespace: dict = {"__name__": "softly_script"}
    code = compile(path.read_text(), str(path), "exec")
    exec(code, namespace)
    return namespace


def _open_audio(container, sound_path: Path):
    """returns (audio_in, audio_stream, resampler) or (None, None, None).
    must be called BEFORE any packet is muxed — streams can't be added once
    the container header is written."""
    import av

    try:
        audio_in = av.open(str(sound_path))
        audio_in.streams.audio[0]  # raises if the file has no audio stream
        audio_stream = container.add_stream("aac", rate=AUDIO_RATE)
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=AUDIO_RATE)
        return audio_in, audio_stream, resampler
    except Exception as exc:
        print(f"warning: couldn't open sound file ({exc}); rendering silent", file=sys.stderr)
        return None, None, None


def _mux_audio(container, audio_stream, resampler, audio_in, duration: float) -> None:
    max_samples = int(duration * AUDIO_RATE)
    written = 0

    def encode_frames(frames) -> bool:
        nonlocal written
        for out_frame in frames:
            if written >= max_samples:
                return False
            written += out_frame.samples
            out_frame.pts = None
            for packet in audio_stream.encode(out_frame):
                container.mux(packet)
        return True

    for frame in audio_in.decode(audio=0):
        if not encode_frames(resampler.resample(frame)):
            break
    else:
        encode_frames(resampler.resample(None))  # flush the resampler
    for packet in audio_stream.encode():
        container.mux(packet)


def main() -> int:
    import av

    script_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    sound_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    ns = _load_script(script_path)
    draw_frame = ns.get("draw_frame")
    if not callable(draw_frame):
        print("script error: draw_frame(t) is not defined", file=sys.stderr)
        return 2

    width = max(64, min(int(ns.get("WIDTH", 720)), MAX_EDGE)) // 2 * 2
    height = max(64, min(int(ns.get("HEIGHT", 1280)), MAX_EDGE)) // 2 * 2
    fps = max(8, min(int(ns.get("FPS", 30)), MAX_FPS))
    duration = max(1.0, min(float(ns.get("DURATION", 6.0)), MAX_DURATION))
    total = int(duration * fps)

    container = av.open(str(out_path), mode="w", options={"movflags": "+faststart"})
    stream = container.add_stream("h264", rate=fps)
    stream.width = width
    stream.height = height
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "18", "preset": "slow"}

    # audio stream must exist before the first mux writes the header
    audio_in = audio_stream = resampler = None
    if sound_path is not None and sound_path.exists():
        audio_in, audio_stream, resampler = _open_audio(container, sound_path)

    try:
        for i in range(total):
            arr = np.asarray(draw_frame(i / fps), dtype=np.uint8)
            if arr.shape != (height, width, 3):
                print(
                    f"script error: draw_frame returned shape {arr.shape}, "
                    f"expected {(height, width, 3)}",
                    file=sys.stderr,
                )
                return 3
            frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)

        if audio_in is not None:
            try:
                _mux_audio(container, audio_stream, resampler, audio_in, duration)
            except Exception as exc:  # sound is best-effort; silent video still ships
                print(f"warning: sound mux failed ({exc}); video is silent", file=sys.stderr)
            finally:
                audio_in.close()
    finally:
        container.close()

    print(f"rendered {total} frames at {width}x{height}@{fps}fps -> {out_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
