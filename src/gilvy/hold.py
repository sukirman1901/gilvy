"""Keep a long scene alive after its authored beat has finished.

Scenes of seven seconds or less are left alone, so the original frames stay
byte-identical. A longer voice-over gets a slow push-in and a small
oscillation instead of a still picture under the narration.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from gilvy.easing import R, eio

HOLD_AFTER = 7.0
ARRIVAL = 1.6


def holding(u: float, dur: float, start: float = ARRIVAL) -> bool:
    return dur > HOLD_AFTER and u > start


def hold_wave(u: float, dur: float, start: float = 1.8) -> float:
    """Smooth −1..1 cycle. Zero until the authored beat has finished."""
    if not holding(u, dur, start):
        return 0.0
    return math.sin(2 * math.pi * (u - start) / 3.4)


def hold_scale(u: float, dur: float) -> float:
    """1.0 during the arrival and for every short scene. Then a slow push plus a breath."""
    if not holding(u, dur):
        return 1.0
    end = max(dur - 0.35, ARRIVAL + 0.05)
    creep = 0.06 * eio(R(u, ARRIVAL, end))
    bob = 0.016 * math.sin(2 * math.pi * (u - ARRIVAL) / 3.4)
    return 1.0 + creep + bob


def hold_frame(image: np.ndarray, scale: float, focal: tuple[float, float]) -> np.ndarray:
    """Scale around the focal point. Identity when scale is 1."""
    if scale == 1.0:
        return image
    height, width = image.shape[:2]
    fx, fy = focal
    scaled_w = max(width + 2, int(round(width * scale)))
    scaled_h = max(height + 2, int(round(height * scale)))
    plate = Image.fromarray(np.clip(image, 0, 255).astype(np.uint8))
    plate = plate.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    left = int(round(fx * (scaled_w / width) - fx))
    top = int(round(fy * (scaled_h / height) - fy))
    left = max(0, min(left, scaled_w - width))
    top = max(0, min(top, scaled_h - height))
    cropped = plate.crop((left, top, left + width, top + height))
    return np.asarray(cropped, np.float32)
