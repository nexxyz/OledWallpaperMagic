from __future__ import annotations

import random
import math
from typing import Literal

RGB = tuple[int, int, int]


def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    if s == 0:
        return (int(v * 255), int(v * 255), int(v * 255))
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    channels = [
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    ]
    r, g, b = channels[i]
    return (int(r * 255), int(g * 255), int(b * 255))


def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    max_c = max(r_n, g_n, b_n)
    min_c = min(r_n, g_n, b_n)
    delta = max_c - min_c
    if delta == 0:
        h = 0.0
    elif max_c == r_n:
        h = (60 * ((g_n - b_n) / delta)) % 360
    elif max_c == g_n:
        h = 60 * ((b_n - r_n) / delta) + 120
    else:
        h = 60 * ((r_n - g_n) / delta) + 240
    s = 0.0 if max_c == 0 else delta / max_c
    v = max_c
    return (h / 360.0, s, v)


def random_vivid_color(rng: random.Random) -> RGB:
    h = rng.uniform(0, 1)
    s = rng.uniform(0.65, 1.0)
    v = rng.uniform(0.65, 1.0)
    return hsv_to_rgb(h, s, v)


def ensure_hue_separation(primary: RGB, secondary: RGB, min_degrees: float = 35.0) -> RGB:
    hp, sp, vp = rgb_to_hsv(*primary)
    hs, ss, vs = rgb_to_hsv(*secondary)
    diff = abs(hp - hs)
    diff = min(diff, 1.0 - diff)
    if diff * 360 < min_degrees:
        delta = min_degrees / 360
        hs_new = (hp + delta) % 1.0
        return hsv_to_rgb(hs_new, ss, vs)
    return secondary


class ColorPalette:
    bg: RGB
    primary: RGB
    secondary: RGB
    glow: RGB

    def __init__(
        self,
        bg: RGB,
        primary: RGB | Literal["random"],
        secondary: RGB | Literal["random"],
        glow: RGB,
        rng: random.Random,
    ):
        self.bg = bg
        self.glow = glow
        if primary == "random":
            self.primary = random_vivid_color(rng)
        else:
            self.primary = primary
        if secondary == "random":
            self.secondary = random_vivid_color(rng)
            self.secondary = ensure_hue_separation(self.primary, self.secondary)
        else:
            self.secondary = secondary
