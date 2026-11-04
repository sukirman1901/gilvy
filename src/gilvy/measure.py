"""Whole-frame zoom and pan, measured the way the reference rates are.

Zoom is the constant relative rate: -100·ln(s)/Δt, where s is the scale that
makes the later frame match the earlier one (s<1 is a push-in).

Pan is the picture's travel in source pixels per second. +x is right, +y is
down. Undoing the zoom about the plate center also shrinks a pan that has
already left that center, so the raw shift is not the pan. For a pan that
starts at 0 on the first frame and moves at a constant rate v,

    shift = v · ((s − 1)·t + s·Δt)

and v is that shift divided by the term in parentheses. A pan that does not
start at 0, or that eases, is outside what this reports.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from gilvy.errors import GilvyError


def motion(video: str | Path, dt: float = 0.4) -> dict:
    """Median zoom %/s and pan px/s across the clip."""
    path = Path(video)
    if not path.is_file():
        raise GilvyError(f"video not found: {path}")
    frames, fps, src_w, src_h = _frames(path)
    if len(frames) < 3 or fps <= 0:
        raise GilvyError("not enough frames to measure motion")
    step = max(1, int(round(dt * fps)))
    if len(frames) <= step:
        raise GilvyError("clip is shorter than the motion sample")
    last = len(frames) - step
    count = min(16, last)
    if count == 1:
        indices = [0]
    else:
        indices = [int(round(i * (last - 1) / (count - 1))) for i in range(count)]
    zooms = []
    pans_x = []
    pans_y = []
    sample_dt = step / fps
    for index in indices:
        zoom, px, py = _pair(
            frames[index], frames[index + step], index / fps, sample_dt, src_w, src_h,
        )
        zooms.append(zoom)
        pans_x.append(px)
        pans_y.append(py)
    return {
        "zoom_pct_per_s": round(float(np.median(zooms)), 3),
        "pan_px_per_s": {
            "x": round(float(np.median(pans_x)), 3),
            "y": round(float(np.median(pans_y)), 3),
        },
        "samples": len(zooms),
    }


def _frames(path: Path) -> tuple[np.ndarray, float, int, int]:
    import json
    from fractions import Fraction

    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", str(path),
    ]))
    stream = info["streams"][0]
    src_w, src_h = int(stream["width"]), int(stream["height"])
    fps = float(Fraction(stream["avg_frame_rate"]))
    width = 720
    height = max(2, int(round(width * src_h / src_w)))
    height -= height % 2
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-an",
        "-vf", f"scale={width}:{height}:flags=area",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ])
    frame = width * height
    count = len(raw) // frame
    frames = np.frombuffer(raw[:count * frame], np.uint8).reshape(count, height, width).astype(np.float32)
    return frames, fps, src_w, src_h


def _pair(a, b, t, dt, src_w, src_h):
    scale = _best_scale(a, b)
    scaled = _scale_center(b, scale)
    shift_x, shift_y = _shift(a, scaled, scale)
    zoom = 0.0 if scale <= 0 else -100.0 * float(np.log(scale)) / dt
    # Analysis pixels back to the source frame. Width and height can round apart.
    mx = shift_x * src_w / a.shape[1]
    my = shift_y * src_h / a.shape[0]
    denom = (scale - 1.0) * t + scale * dt
    if abs(denom) < 1e-6:
        return zoom, 0.0, 0.0
    return zoom, mx / denom, my / denom


def _best_scale(a: np.ndarray, b: np.ndarray) -> float:
    coarse = _scale_peak(a, b, np.linspace(0.80, 1.25, 31))
    return _scale_peak(a, b, np.linspace(coarse - 0.012, coarse + 0.012, 13))


def _scale_peak(a: np.ndarray, b: np.ndarray, scales) -> float:
    best_s, best = 1.0, -1.0
    for scale in scales:
        score = _phase_peak(a, _scale_center(b, float(scale)), float(scale))
        if score > best:
            best, best_s = score, float(scale)
    return best_s


def _phase_peak(a: np.ndarray, b: np.ndarray, scale: float) -> float:
    aa, bb = _overlap(a, b, scale)
    aa = aa - aa.mean()
    bb = bb - bb.mean()
    cross = np.fft.rfft2(aa) * np.conj(np.fft.rfft2(bb))
    cross /= np.abs(cross) + 1e-6
    return float(np.fft.irfft2(cross, s=aa.shape).max())


def _scale_center(frame: np.ndarray, scale: float) -> np.ndarray:
    """Scale about the frame center. scale<1 shrinks the later frame's push-in."""
    scale = float(scale)
    if abs(scale - 1.0) < 1e-4:
        return frame
    image = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
    width, height = image.size
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0
    inv = 1.0 / scale
    out = image.transform(
        image.size,
        Image.Transform.AFFINE,
        (inv, 0.0, cx - inv * cx, 0.0, inv, cy - inv * cy),
        resample=Image.Resampling.BICUBIC,
    )
    return np.asarray(out, np.float32)


def _overlap(a: np.ndarray, b: np.ndarray, scale: float):
    """Drop the border that a shrink (scale<1) fills with empty pixels."""
    frac = min(1.0, float(scale)) * 0.90
    height, width = a.shape
    crop_h = max(16, int(height * frac))
    crop_w = max(16, int(width * frac))
    top = (height - crop_h) // 2
    left = (width - crop_w) // 2
    return a[top:top + crop_h, left:left + crop_w], b[top:top + crop_h, left:left + crop_w]


def _shift(a: np.ndarray, b: np.ndarray, scale: float) -> tuple[float, float]:
    """Content motion of b relative to a, in pixels. +x right, +y down."""
    a, b = _overlap(a, b, scale)
    a0 = a - float(a.mean())
    b0 = b - float(b.mean())
    span = min(48, a0.shape[0] // 3, a0.shape[1] // 3)
    span = max(4, span)
    padded_h = a0.shape[0] + 2 * span
    padded_w = a0.shape[1] + 2 * span
    cross = np.fft.rfft2(a0, s=(padded_h, padded_w)) * np.conj(np.fft.rfft2(b0, s=(padded_h, padded_w)))
    corr = np.fft.irfft2(cross, s=(padded_h, padded_w))
    # corr[k] = Σ a[n] b[n−k]. Content that moved by +d peaks at k = −d.
    best = -1.0
    dx = dy = 0
    for step_y in range(-span, span + 1):
        for step_x in range(-span, span + 1):
            score = float(corr[(-step_y) % padded_h, (-step_x) % padded_w])
            if score > best:
                best = score
                dx, dy = step_x, step_y

    def at(x: int, y: int) -> float:
        return float(corr[(-y) % padded_h, (-x) % padded_w])

    return dx + _frac(at(dx - 1, dy), at(dx, dy), at(dx + 1, dy)), dy + _frac(at(dx, dy - 1), at(dx, dy), at(dx, dy + 1))


def _frac(left: float, mid: float, right: float) -> float:
    denom = left - 2.0 * mid + right
    if abs(denom) < 1e-8:
        return 0.0
    return float(np.clip(0.5 * (left - right) / denom, -0.5, 0.5))
