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


def settle_at(dur: float) -> float:
    """The verb owns the frame until 65% of the scene. The hold starts after that."""
    return max(ARRIVAL, dur * 0.65)


def holding(u: float, dur: float, start: float | None = None) -> bool:
    if start is None:
        start = settle_at(dur)
    return dur > HOLD_AFTER and u > start


def hold_wave(u: float, dur: float, start: float = 1.8) -> float:
    """Smooth −1..1 cycle. Zero while the verb is still running, and on every short scene."""
    begin = max(start, settle_at(dur))
    if not holding(u, dur, begin):
        return 0.0
    return math.sin(2 * math.pi * (u - begin) / 3.4)


def hold_scale(u: float, dur: float) -> float:
    """1.0 while the verb plays and for every short scene. Then a slow push plus a breath."""
    begin = settle_at(dur)
    if not holding(u, dur, begin):
        return 1.0
    end = max(dur - 0.35, begin + 0.05)
    creep = 0.06 * eio(R(u, begin, end))
    bob = 0.012 * (0.5 - 0.5 * math.cos(2 * math.pi * (u - begin) / 3.4))
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
