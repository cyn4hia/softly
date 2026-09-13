# example clip: pulsing radial rings (energetic / dance / meme)
# follows softly's render contract — see softly/render_cli.py
import math

import numpy as np

WIDTH = 540
HEIGHT = 960
FPS = 24
DURATION = 5.0

_yy, _xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
U = (_xx / WIDTH - 0.5) * (WIDTH / HEIGHT)
V = _yy / HEIGHT - 0.5
D = np.sqrt(U * U + V * V)

INK = np.array([56, 44, 52], np.float32)
PINK = np.array([236, 143, 181], np.float32)
HOT = np.array([255, 214, 232], np.float32)

BEAT_HZ = 1.6


def draw_frame(t: float) -> np.ndarray:
    beat = (math.sin(2 * math.pi * BEAT_HZ * t - math.pi / 2) + 1) / 2
    beat = beat ** 3  # sharpen into a thump

    rings = np.sin(D * 26.0 - t * 7.5)
    rings = np.clip(rings, 0.55, 1.0) - 0.55
    rings = rings / 0.45

    core = np.exp(-(D ** 2) / (2 * (0.05 + 0.10 * beat) ** 2))

    img = INK[None, None, :] * np.ones_like(D)[..., None]
    img = img + (PINK - img) * (0.30 + 0.45 * beat) * rings[..., None]
    img = img + (HOT - img) * core[..., None]
    return np.clip(img, 0, 255).astype(np.uint8)
