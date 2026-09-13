# example clip: soft pink gradient waves (aesthetic / cozy)
# follows softly's render contract — see softly/render_cli.py
import math

import numpy as np

WIDTH = 540
HEIGHT = 960
FPS = 24
DURATION = 5.0

_yy, _xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
U = _xx / WIDTH
V = _yy / HEIGHT

CREAM = np.array([252, 240, 246], np.float32)
PINK = np.array([243, 167, 199], np.float32)
DEEP = np.array([219, 111, 158], np.float32)


def draw_frame(t: float) -> np.ndarray:
    phase = t / DURATION * 2 * math.pi
    w1 = np.sin(2 * math.pi * (V * 1.1 + 0.07 * np.sin(2 * math.pi * U * 1.6 + phase)) + phase)
    w2 = np.sin(2 * math.pi * (U * 0.7) - phase * 1.4 + 1.7)
    mix = np.clip(0.5 + 0.28 * w1 + 0.22 * w2, 0.0, 1.0)[..., None]
    img = CREAM * (1.0 - mix) + PINK * mix

    gy = 0.34 + 0.05 * math.sin(phase)
    glow = np.exp(-(((U - 0.5) ** 2) * 5.0 + ((V - gy) ** 2) * 3.2))[..., None]
    img = img + (DEEP - img) * 0.38 * glow

    vign = (1.0 - 0.16 * ((U - 0.5) ** 2 + (V - 0.5) ** 2) * 2.4)[..., None]
    return np.clip(img * vign, 0, 255).astype(np.uint8)
