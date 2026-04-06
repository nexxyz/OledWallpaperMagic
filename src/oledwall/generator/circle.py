from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Callable

from oledwall.generator.palette import RGB
from oledwall.generator.fuzzy_circle import get_alpha_curve, glow_ring_alpha


@dataclass
class FuzzyCircle:
    cx: float
    cy: float
    radius: float
    color: RGB
    opacity: float
    curve_name: str
    curve_param: float
    glow_color: RGB
    glow_strength: float
    glow_mu: float
    glow_sigma: float

    def render(self, canvas: np.ndarray) -> None:
        h, w = canvas.shape[:2]
        y_coords, x_coords = np.ogrid[:h, :w]
        dist = np.sqrt((x_coords - self.cx) ** 2 + (y_coords - self.cy) ** 2)
        t = dist / self.radius

        alpha_fn = get_alpha_curve(self.curve_name)
        fill_alpha = alpha_fn(t, self.curve_param) * self.opacity

        glow_alpha = glow_ring_alpha(t, self.glow_mu, self.glow_sigma) * self.glow_strength

        fill_color = np.array(self.color, dtype=np.float32)
        glow_color = np.array(self.glow_color, dtype=np.float32)

        if canvas.dtype != np.float32:
            canvas = canvas.astype(np.float32)

        if canvas.ndim == 3 and canvas.shape[2] == 3:
            bg = np.full_like(canvas, fill_color)
            canvas[:] = bg * fill_alpha[..., np.newaxis] + canvas * (1.0 - fill_alpha[..., np.newaxis])

            canvas[:] = np.clip(
                canvas + glow_color * glow_alpha[..., np.newaxis],
                0.0,
                255.0,
            )
        else:
            raise ValueError(f"Canvas must be HxWx3, got shape {canvas.shape}")
