"""Opt-in plate effects. House scenes never call this module.

Each effect is a small function of the RGB plate and the scene clock. The
episode names them under `effects:` or as an overlay kind. `overlays[].sfx`
is mixed in `render.prepare_audio`.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from gilvy.errors import EpisodeError
from gilvy.keyframes import apply_ease

KINDS = (
    "shake", "whip", "flash", "wipe", "glitch", "flicker", "vignette",
    "light_leak", "dust", "rotation",
)
SFX = {"click", "whoosh", "stamp"}


def parse_effects(raw, index: int) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise EpisodeError(f"scene {index}: effects must be a list")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or item.get("kind") not in KINDS:
            raise EpisodeError(
                f"scene {index}: effect {i + 1} kind must be one of {', '.join(KINDS)}"
            )
        kind = item["kind"]
        parsed = {"kind": kind}
        if kind == "shake":
            parsed["amp"] = _num(item.get("amp", 2.4), 0, 40)
            parsed["freq"] = _num(item.get("freq", 10), 0.5, 30)
        elif kind == "whip":
            parsed["seconds"] = _num(item.get("seconds", 0.12), 0.04, 0.5)
            parsed["at"] = _num(item.get("at", 0.0), 0, 30)
        elif kind == "flash":
            parsed["at"] = _num(item.get("at", 0.2), 0, 30)
            parsed["seconds"] = _num(item.get("seconds", 0.06), 0.02, 0.4)
        elif kind == "wipe":
            parsed["at"] = _num(item.get("at", 0.0), 0, 30)
            parsed["seconds"] = _num(item.get("seconds", 0.4), 0.05, 2.5)
            parsed["ease"] = str(item.get("ease") or "easeInCubic")
            parsed["axis"] = item.get("axis") if item.get("axis") in ("x", "y") else "x"
        elif kind == "glitch":
            parsed["at"] = _num(item.get("at", 0.3), 0, 30)
            parsed["seconds"] = _num(item.get("seconds", 0.08), 0.02, 0.4)
        elif kind == "flicker":
            parsed["amount"] = _num(item.get("amount", 0.08), 0, 0.5)
            parsed["freq"] = _num(item.get("freq", 12), 1, 30)
        elif kind == "vignette":
            parsed["amount"] = _num(item.get("amount", 0.45), 0, 1)
        elif kind == "light_leak":
            parsed["amount"] = _num(item.get("amount", 0.35), 0, 1)
        elif kind == "dust":
            parsed["amount"] = _num(item.get("amount", 0.5), 0, 1)
        elif kind == "rotation":
            parsed["degrees"] = _num(item.get("degrees", 0), -45, 45)
        out.append(parsed)
    return out


def _num(value, lo: float, hi: float) -> float:
    number = float(value)
    if not math.isfinite(number) or not lo <= number <= hi:
        raise EpisodeError(f"effect value {value} must be from {lo} to {hi}")
    return number


def shake_offset(effect: dict, time: float) -> tuple[float, float]:
    amp = float(effect["amp"])
    freq = float(effect["freq"])
    return (
        amp * math.sin(2 * math.pi * freq * time),
        amp * 0.65 * math.cos(2 * math.pi * freq * time),
    )


def apply_plate_effects(plate: np.ndarray, effects: list[dict], time: float, velocity: tuple[float, float]) -> np.ndarray:
    """Film effects after the plate is drawn. Shake is applied by the caller as a pan."""
    image = plate
    for effect in effects:
        kind = effect["kind"]
        if kind == "rotation" and abs(effect["degrees"]) > 0.05:
            image = _rotate(image, effect["degrees"])
        elif kind == "flicker":
            wave = 1 + effect["amount"] * math.sin(2 * math.pi * effect["freq"] * time)
            image = np.clip(image * wave, 0, 255)
        elif kind == "vignette":
            image = _vignette(image, effect["amount"])
        elif kind == "light_leak":
            image = _leak(image, effect["amount"])
        elif kind == "dust":
            image = _dust(image, effect["amount"], time)
        elif kind == "flash":
            image = _flash(image, time, effect["at"], effect["seconds"])
        elif kind == "wipe":
            image = _wipe(image, time, effect)
        elif kind == "glitch":
            image = _glitch(image, time, effect["at"], effect["seconds"])
        elif kind == "whip":
            if effect["at"] <= time <= effect["at"] + effect["seconds"]:
                image = _blur(image, velocity)
    # A fast camera move blurs even without an authored whip, when the caller asks.
    return image


def whip_blur(plate: np.ndarray, velocity: tuple[float, float], floor: float = 28.0) -> np.ndarray:
    speed = math.hypot(*velocity)
    if speed < floor:
        return plate
    return _blur(plate, velocity)


def _rotate(plate: np.ndarray, degrees: float) -> np.ndarray:
    image = Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8))
    turned = image.rotate(-degrees, resample=Image.Resampling.BICUBIC, expand=False)
    return np.asarray(turned, np.float32)


def _vignette(plate: np.ndarray, amount: float) -> np.ndarray:
    height, width = plate.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    rx = (xx - (width - 1) / 2) / max(1, width / 2)
    ry = (yy - (height - 1) / 2) / max(1, height / 2)
    fall = np.clip(1 - amount * (rx ** 2 + ry ** 2), 0.25, 1)
    return plate * fall[..., None]


def _leak(plate: np.ndarray, amount: float) -> np.ndarray:
    height, width = plate.shape[:2]
    ramp = np.linspace(1, 0, width, dtype=np.float32)
    color = np.array([255, 150, 70], np.float32)
    veil = color * ramp[None, :, None] * amount
    return np.clip(plate * (1 - amount * 0.35) + veil, 0, 255)


def _dust(plate: np.ndarray, amount: float, time: float) -> np.ndarray:
    rng = np.random.default_rng(int(time * 24) + 17)
    height, width = plate.shape[:2]
    specks = int(8 + amount * 40)
    ys = rng.integers(0, height, specks)
    xs = rng.integers(0, width, specks)
    out = plate.copy()
    out[ys, xs] = np.clip(out[ys, xs] + rng.integers(40, 140, (specks, 1)), 0, 255)
    # One scratch, a thin vertical line.
    x = int(rng.integers(0, width))
    out[:, x] = np.clip(out[:, x] * (1 - 0.25 * amount) + 40 * amount, 0, 255)
    return out


def _flash(plate: np.ndarray, time: float, at: float, seconds: float) -> np.ndarray:
    if time < at or time > at + seconds:
        return plate
    k = 1 - abs((time - at) / seconds * 2 - 1)
    return plate * (1 - k) + 255 * k


def _wipe(plate: np.ndarray, time: float, effect: dict) -> np.ndarray:
    if time < effect["at"]:
        return plate * 0
    p = apply_ease(effect["ease"], min(1.0, (time - effect["at"]) / effect["seconds"]))
    height, width = plate.shape[:2]
    if effect["axis"] == "y":
        cut = int(height * p)
        out = np.zeros_like(plate)
        out[:cut] = plate[:cut]
        return out
    cut = int(width * p)
    out = np.zeros_like(plate)
    out[:, :cut] = plate[:, :cut]
    return out


def _glitch(plate: np.ndarray, time: float, at: float, seconds: float) -> np.ndarray:
    if time < at or time > at + seconds:
        return plate
    out = plate.copy()
    shift = 6
    out[:, shift:, 0] = plate[:, :-shift, 0]
    out[:, :-shift, 2] = plate[:, shift:, 2]
    band = slice(out.shape[0] // 3, out.shape[0] // 3 + 8)
    out[band] = np.roll(out[band], 12, axis=1)
    return out


def _blur(plate: np.ndarray, velocity: tuple[float, float]) -> np.ndarray:
    dx, dy = velocity
    image = Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8))
    radius = int(min(12, max(2, round(math.hypot(dx, dy) / 12))))
    if abs(dx) >= abs(dy):
        blurred = image.filter(ImageFilter.BoxBlur(radius))
        # Keep the blur mostly horizontal by mixing a vertical-unblurred copy weakly.
        out = np.asarray(blurred, np.float32)
    else:
        out = np.asarray(image.filter(ImageFilter.BoxBlur(radius)), np.float32)
    return out


def typewriter_count(text: str, local: float, word_seconds: float) -> int:
    words = [word for word in text.split(" ") if word]
    if local < 0 or not words:
        return 0
    return min(len(words), int(local / max(0.04, word_seconds)) + 1)


def word_times(start: float, count: int, word_seconds: float) -> list[float]:
    return [start + i * word_seconds for i in range(count)]


def write_sfx(path: Path, kind: str, sr: int = 48000) -> None:
    """A short deterministic cue. click is a noise burst, whoosh a falling tone, stamp a thud."""
    import wave

    n = int(sr * (0.04 if kind == "click" else 0.12))
    t = np.arange(n) / sr
    rng = np.random.default_rng(3 if kind == "stamp" else 1)
    if kind == "whoosh":
        tone = np.sin(2 * np.pi * (900 - 700 * t / max(t[-1], 1e-6)) * t)
        data = tone * np.linspace(0.2, 0, n)
    elif kind == "stamp":
        data = np.sin(2 * np.pi * 90 * t) * np.exp(-t * 40)
    else:
        data = rng.standard_normal(n) * np.linspace(1, 0, n) ** 2
    pcm = np.clip(data * 0.85, -1, 1)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes((pcm * 32767).astype(np.int16).tobytes())


def draw_strike(pen: ImageDraw.ImageDraw, box: tuple[float, float, float, float], progress: float, color: tuple[int, int, int]) -> None:
    x0, y0, x1, y1 = box
    y = (y0 + y1) / 2
    pen.line([(x0, y), (x0 + (x1 - x0) * progress, y)], fill=(*color, 230), width=4)


def draw_mask(pen: ImageDraw.ImageDraw, origin: tuple[float, float], size: tuple[float, float], progress: float) -> None:
    w, h = size
    pen.rectangle([origin[0], origin[1], origin[0] + w * progress, origin[1] + h], fill=(255, 255, 255, 255))
