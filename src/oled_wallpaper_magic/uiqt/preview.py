from __future__ import annotations

import importlib
import random

import numpy as np

_qt_pkg = "".join(["Py", "Side6"])
QtGui = importlib.import_module(".".join([_qt_pkg, "Qt" + "Gui"]))
QImage = QtGui.QImage
QPixmap = QtGui.QPixmap

from oled_wallpaper_magic.config import AppConfig
from oled_wallpaper_magic.generator.fuzzy_circle import get_alpha_curve, glow_ring_alpha
from oled_wallpaper_magic.generator.palette import ColorPalette


def _render_array(cfg: AppConfig, seed: int, width: int, height: int) -> np.ndarray:
    rng = random.Random(seed)
    res = cfg.resolution
    scale_x = width / max(res.width, 1)
    scale_y = height / max(res.height, 1)
    scale = min(scale_x, scale_y)
    draw_w = max(1, int(res.width * scale))
    draw_h = max(1, int(res.height * scale))

    palette = ColorPalette(
        bg=cfg.colors.background or (0, 0, 0),
        primary=cfg.colors.primary,
        secondary=cfg.colors.secondary,
        glow=cfg.colors.glow,
        rng=rng,
    )

    n = rng.randint(cfg.generation.min_circles, cfg.generation.max_circles)
    gc = cfg.generation

    canvas = np.full((draw_h, draw_w, 3), palette.bg, dtype=np.float32)

    if gc.enforce_both_colors and n >= 2:
        circle_colors = [palette.primary, palette.secondary] + [
            palette.primary if rng.random() < gc.primary_secondary_mix else palette.secondary
            for _ in range(n - 2)
        ]
        rng.shuffle(circle_colors)
    else:
        circle_colors = [
            palette.primary if rng.random() < gc.primary_secondary_mix else palette.secondary
            for _ in range(n)
        ]

    alpha_fn = get_alpha_curve(gc.curve)
    y_coords, x_coords = np.ogrid[:draw_h, :draw_w]

    for i in range(n):
        cx = rng.uniform(0, draw_w)
        cy = rng.uniform(0, draw_h)
        radius = max(1, int(rng.randint(gc.min_radius, gc.max_radius) * scale))
        opacity = rng.uniform(gc.primary_opacity_min, gc.primary_opacity_max)

        dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
        t = dist / radius
        fill_alpha = alpha_fn(t, gc.curve_param) * opacity
        glow_alpha = glow_ring_alpha(t, gc.glow_mu, gc.glow_sigma) * gc.glow_strength

        fill_color = np.array(circle_colors[i], dtype=np.float32)
        glow_color_np = np.array(palette.glow, dtype=np.float32)

        fg = np.full_like(canvas, fill_color)
        canvas[:] = fg * fill_alpha[..., np.newaxis] + canvas * (1.0 - fill_alpha[..., np.newaxis])
        canvas[:] = np.clip(canvas + glow_color_np * glow_alpha[..., np.newaxis], 0.0, 255.0)

    out = np.clip(canvas, 0, 255).astype(np.uint8)

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = np.array(palette.bg, dtype=np.uint8)
    ox = (width - draw_w) // 2
    oy = (height - draw_h) // 2
    frame[oy:oy + draw_h, ox:ox + draw_w, :] = out
    return frame


def render_preview_pixmap(cfg: AppConfig, seed: int, width: int, height: int) -> QPixmap:
    arr = _render_array(cfg, seed, width, height)
    h, w, _ = arr.shape
    image = QImage(arr.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(image)
