"""(re)builds the bundled example media by running scripts/examples/*.py
through softly's own render pipeline — the same one generated code uses.

usage: uv run python scripts/make_examples.py
"""
from __future__ import annotations

import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_OUT = ROOT / "data" / "examples"
SCRIPTS = Path(__file__).parent / "examples"


def make_chime(path: Path) -> None:
    rate, duration = 44100, 2.5
    samples = []
    for i in range(int(rate * duration)):
        t = i / rate
        env = math.exp(-2.1 * t)
        s = 0.32 * env * (
            math.sin(2 * math.pi * 659.25 * t)
            + 0.6 * math.sin(2 * math.pi * 880.0 * t)
            + 0.4 * math.sin(2 * math.pi * 987.77 * t) * math.exp(-3.5 * t)
        )
        samples.append(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(samples))


def main() -> int:
    EXAMPLES_OUT.mkdir(parents=True, exist_ok=True)
    for script in sorted(SCRIPTS.glob("*.py")):
        out = EXAMPLES_OUT / f"{script.stem}.mp4"
        print(f"rendering {script.stem} …", flush=True)
        res = subprocess.run(
            [sys.executable, "-m", "softly.render_cli", str(script), str(out)],
            capture_output=True, text=True, cwd=ROOT,
        )
        print((res.stdout + res.stderr).strip())
        if res.returncode != 0:
            return res.returncode
    make_chime(EXAMPLES_OUT / "soft-chime.wav")
    print("done — examples live in data/examples/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
