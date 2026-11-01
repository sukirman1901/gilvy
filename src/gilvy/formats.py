"""Delivery canvases. The drawing stays in 1080×1920 design space and is fitted into a safe rectangle."""

from __future__ import annotations

from dataclasses import dataclass


DESIGN_W = 1080
DESIGN_H = 1920


@dataclass(frozen=True)
class Fit:
    """Uniform map from design pixels to output pixels. Identity is scale 1 and offset 0."""

    scale: float = 1.0
    ox: float = 0.0
    oy: float = 0.0

    def map(self, x: float, y: float) -> tuple[float, float]:
        return (self.ox + x * self.scale, self.oy + y * self.scale)


@dataclass(frozen=True)
class DeliveryProfile:
    name: str
    width: int
    height: int
    insets: tuple[int, int, int, int]  # left, top, right, bottom


# Insets are a starting safe area for platform chrome, not a claim of each app's current UI.
PROFILES: dict[str, DeliveryProfile] = {
    "vertical_9x16": DeliveryProfile("vertical_9x16", 1080, 1920, (0, 0, 0, 0)),
    "vertical_9x16_safe": DeliveryProfile("vertical_9x16_safe", 1080, 1920, (80, 160, 120, 420)),
    "portrait_4x5": DeliveryProfile("portrait_4x5", 1080, 1350, (60, 80, 60, 220)),
    "square_1x1": DeliveryProfile("square_1x1", 1080, 1080, (60, 80, 60, 160)),
    "landscape_16x9": DeliveryProfile("landscape_16x9", 1920, 1080, (80, 60, 80, 140)),
}


def get_profile(name: str) -> DeliveryProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        known = ", ".join(PROFILES)
        raise KeyError(f"unknown format {name!r}. Known formats: {known}") from exc


def fit_of(profile: DeliveryProfile) -> Fit:
    left, top, right, bottom = profile.insets
    safe_w = profile.width - left - right
    safe_h = profile.height - top - bottom
    if safe_w <= 0 or safe_h <= 0:
        raise ValueError(f"{profile.name} insets leave no safe area")
    scale = min(safe_w / DESIGN_W, safe_h / DESIGN_H)
    ox = left + (safe_w - DESIGN_W * scale) / 2
    oy = top + (safe_h - DESIGN_H * scale) / 2
    if scale == 1.0 and ox == 0.0 and oy == 0.0:
        return Fit()
    return Fit(scale, ox, oy)
