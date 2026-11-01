"""Locked canvas. Palette and fonts are the knobs; the geometry is the look."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gilvy.formats import Fit, fit_of, get_profile


BG = (10, 10, 10)
WHITE = (236, 236, 236)
GREEN = (218, 255, 89)  # #daff59 — one focus idea per screen

WIDTH = 1080
HEIGHT = 1920
FPS = 60
SCALE = 2  # supersample, then Lanczos down to 1080x1920
CX = 513  # focal x, 27px left of center
PAD = 0.4
LEAD = 0.2
CROSSFADE = 0.45
MIN_DURATION = 2.8
INTRO = 0.3
OUTRO = 0.6
CRF = "17"
PRESET = "medium"
SAMPLE_RATE = 48000


def bundled_fonts() -> Path:
    return Path(__file__).resolve().parent / "fonts"


@dataclass(frozen=True)
class Theme:
    bg: tuple[int, int, int] = BG
    white: tuple[int, int, int] = WHITE
    green: tuple[int, int, int] = GREEN
    width: int = WIDTH
    height: int = HEIGHT
    fps: int = FPS
    scale: int = SCALE
    cx: int = CX
    pad: float = PAD
    lead: float = LEAD
    crossfade: float = CROSSFADE
    min_duration: float = MIN_DURATION
    intro: float = INTRO
    outro: float = OUTRO
    font_dir: str = ""
    fit: Fit = Fit()

    def fonts(self) -> str:
        return self.font_dir or str(bundled_fonts())

    @classmethod
    def from_profile(cls, name: str, **overrides: object) -> Theme:
        profile = get_profile(name)
        fit = fit_of(profile)
        return cls(width=profile.width, height=profile.height, fit=fit, **overrides)
