from __future__ import annotations

import os
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image

from oledwall.config import AppConfig
from oledwall.generator.palette import ColorPalette, RGB
from oledwall.generator.circle import FuzzyCircle


@dataclass
class ImageData:
    pixels: np.ndarray
    palette: dict[str, RGB]
    circle_count: int
    generation_time_ms: float
    index: int = 0
    seed: int = 0

    def save(self, path: str | bytes | Path) -> None:
        img = Image.fromarray(self.pixels.astype(np.uint8), mode="RGB")
        img.save(path)

    def to_dict(self) -> dict:
        return {
            "pixels": self.pixels,
            "palette": self.palette,
            "circle_count": self.circle_count,
            "generation_time_ms": self.generation_time_ms,
            "index": self.index,
            "seed": self.seed,
        }


def _render_single(args: tuple) -> tuple:
    (
        index,
        seed,
        width,
        height,
        bg,
        primary,
        secondary,
        glow,
        min_circles,
        max_circles,
        min_radius,
        max_radius,
        curve,
        curve_param,
        glow_strength,
        glow_mu,
        glow_sigma,
        primary_opacity_min,
        primary_opacity_max,
        primary_secondary_mix,
        enforce_both_colors,
    ) = args

    rng = random.Random(seed)
    t0 = time.perf_counter()

    palette = ColorPalette(
        bg=bg,
        primary=primary,
        secondary=secondary,
        glow=glow,
        rng=rng,
    )

    canvas = np.full((height, width, 3), palette.bg, dtype=np.float32)

    n_circles = rng.randint(min_circles, max_circles)

    if enforce_both_colors and n_circles >= 2:
        circle_colors = [palette.primary, palette.secondary] + [
            palette.primary if rng.random() < primary_secondary_mix else palette.secondary
            for _ in range(n_circles - 2)
        ]
        rng.shuffle(circle_colors)
    else:
        circle_colors = [
            palette.primary if rng.random() < primary_secondary_mix else palette.secondary
            for _ in range(n_circles)
        ]

    for i in range(n_circles):
        cx = rng.uniform(0, width)
        cy = rng.uniform(0, height)
        radius = rng.randint(min_radius, max_radius)
        opacity = rng.uniform(primary_opacity_min, primary_opacity_max)

        circle = FuzzyCircle(
            cx=cx,
            cy=cy,
            radius=radius,
            color=circle_colors[i],
            opacity=opacity,
            curve_name=curve,
            curve_param=curve_param,
            glow_color=palette.glow,
            glow_strength=glow_strength,
            glow_mu=glow_mu,
            glow_sigma=glow_sigma,
        )
        circle.render(canvas)

    canvas_u8 = np.clip(canvas, 0, 255).astype(np.uint8)
    dt_ms = (time.perf_counter() - t0) * 1000

    return (
        index,
        seed,
        canvas_u8,
        {
            "primary": palette.primary,
            "secondary": palette.secondary,
            "glow": palette.glow,
        },
        n_circles,
        round(dt_ms, 1),
    )


class GenerationEngine:
    def __init__(self, config: AppConfig):
        self.config = config
        self.gen_cfg = config.generation
        self.color_cfg = config.colors
        self.res = config.resolution

    def _build_args(self, count: int, session_seed: int) -> list:
        args_list = []
        for i in range(count):
            per_image_seed = session_seed + i if session_seed else random.randint(0, 2**31 - 1)
            args_list.append((
                i,
                per_image_seed,
                self.res.width,
                self.res.height,
                self.color_cfg.background,
                self.color_cfg.primary,
                self.color_cfg.secondary,
                self.color_cfg.glow,
                self.gen_cfg.min_circles,
                self.gen_cfg.max_circles,
                self.gen_cfg.min_radius,
                self.gen_cfg.max_radius,
                self.gen_cfg.curve,
                self.gen_cfg.curve_param,
                self.gen_cfg.glow_strength,
                self.gen_cfg.glow_mu,
                self.gen_cfg.glow_sigma,
                self.gen_cfg.primary_opacity_min,
                self.gen_cfg.primary_opacity_max,
                self.gen_cfg.primary_secondary_mix,
                self.gen_cfg.enforce_both_colors,
            ))
        return args_list

    def generate_single(self, seed: int) -> ImageData:
        args = self._build_args(1, seed)[0]
        index, img_seed, pixels, palette, circle_count, gen_ms = _render_single(args)
        return ImageData(
            pixels=pixels,
            palette=palette,
            circle_count=circle_count,
            generation_time_ms=gen_ms,
            index=index,
            seed=img_seed,
        )

    def generate_batch(self, count: int, session_seed: int) -> Iterator[ImageData]:
        workers = self.gen_cfg.workers
        if workers == 0:
            workers = os.cpu_count() or 1

        if workers == 1:
            for args in self._build_args(count, session_seed):
                index, img_seed, pixels, palette, circle_count, gen_ms = _render_single(args)
                yield ImageData(
                    pixels=pixels,
                    palette=palette,
                    circle_count=circle_count,
                    generation_time_ms=gen_ms,
                    index=index,
                    seed=img_seed,
                )
        else:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(_render_single, args): args[0]
                    for args in self._build_args(count, session_seed)
                }
                results: dict[int, tuple] = {}
                next_index = 0
                for future in as_completed(futures):
                    result = future.result()
                    results[result[0]] = result
                    while next_index in results:
                        index, img_seed, pixels, palette, circle_count, gen_ms = results.pop(next_index)
                        yield ImageData(
                            pixels=pixels,
                            palette=palette,
                            circle_count=circle_count,
                            generation_time_ms=gen_ms,
                            index=index,
                            seed=img_seed,
                        )
                        next_index += 1
