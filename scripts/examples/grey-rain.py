# example clip: drifting grey bokeh (calm / moody)
# follows softly's render contract — see softly/render_cli.py
import math

import numpy as np

WIDTH = 540
HEIGHT = 960
FPS = 24
DURATION = 5.0

_rng = np.random.default_rng(7)
N = 12
_cx = _rng.random(N).astype(np.float32)
_cy = _rng.random(N).astype(np.float32)
_rad = (0.04 + _rng.random(N) * 0.09).astype(np.float32)
_speed = (0.05 + _rng.random(N) * 0.10).astype(np.float32)
_phase = (_rng.random(N) * 2 * math.pi).astype(np.float32)

_yy, _xx = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
U = _xx / WIDTH
V = _yy / HEIGHT

TOP = np.array([236, 231, 235], np.float32)
BOTTOM = np.array([187, 179, 186], np.float32)
ORB = np.array([252, 247, 250], np.float32)
BLUSH = np.array([240, 205, 220], np.float32)


def draw_frame(t: float) -> np.ndarray:
    img = TOP * (1.0 - V[..., None]) + BOTTOM * V[..., None]
    for i in range(N):
        x = (_cx[i] + 0.08 * math.sin(t * _speed[i] * 4.0 + _phase[i])) % 1.0
        y = (_cy[i] - t * _speed[i] / DURATION * 2.2) % 1.2 - 0.1
        d2 = ((U - x) * (WIDTH / HEIGHT)) ** 2 + (V - y) ** 2
        soft = np.exp(-d2 / (2 * _rad[i] ** 2))[..., None]
        tint = ORB if i % 3 else BLUSH
        img = img + (tint - img) * 0.5 * soft
    return np.clip(img, 0, 255).astype(np.uint8)
