from __future__ import annotations

from collections.abc import Callable

import numpy as np


def linear_alpha(t: np.ndarray, k: float) -> np.ndarray:
    a = 1.0 - t
    a = np.clip(a, 0.0, 1.0)
    a[t > 1.0] = 0.0
    return a


def ease_alpha(t: np.ndarray, k: float) -> np.ndarray:
    base = np.clip(1.0 - t, 0.0, 1.0)
    a = base ** k
    return a


def exp_alpha(t: np.ndarray, k: float) -> np.ndarray:
    a = np.exp(-k * t)
    a = np.clip(a, 0.0, 1.0)
    a[t > 1.0] = 0.0
    return a


def gaussian_alpha(t: np.ndarray, k: float) -> np.ndarray:
    a = np.exp(-(t ** 2) * k)
    a = np.clip(a, 0.0, 1.0)
    a[t > 1.0] = 0.0
    return a


def flat_alpha(t: np.ndarray, k: float) -> np.ndarray:
    a = np.ones_like(t, dtype=np.float64)
    a[t > 1.0] = 0.0
    return a


def glow_ring_alpha(t: np.ndarray, mu: float = 0.88, sigma: float = 0.07) -> np.ndarray:
    a = np.exp(-((t - mu) ** 2) / (2 * sigma**2))
    a = np.clip(a, 0.0, 1.0)
    a[t > 1.1] = 0.0
    return a


ALPHA_CURVES: dict[str, Callable[[np.ndarray, float], np.ndarray]] = {
    "linear": linear_alpha,
    "ease": ease_alpha,
    "exp": exp_alpha,
    "gaussian": gaussian_alpha,
    "flat": flat_alpha,
}


def get_alpha_curve(name: str) -> Callable[[np.ndarray, float], np.ndarray]:
    if name not in ALPHA_CURVES:
        raise ValueError(f"Unknown curve: {name}. Choose from: {list(ALPHA_CURVES.keys())}")
    return ALPHA_CURVES[name]
