"""Whole-frame zoom and pan.

Zoom is the constant relative rate, 100·ln(s₁/s₀)/Δt. Pan is how far the
picture travels, in source pixels per second. +x is right, +y is down.

The scale is the factor that makes the earlier frame line up with the later
one, scored by pixel error after a shift of a few pixels. A phase-correlation
peak is the wrong score for that scale: on a real photograph it locks at 1,
the rate falls to the search step (about 0.25%/s), and the leftover zoom is
reported as a huge pan. Pan itself still uses phase correlation, which is
what the reference meter used.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from gilvy.errors import GilvyError

# 10%–90% of a linear crossfade. A 1.4s dissolve reads as 1.12s on that clock.
LINEAR_DISSOLVE_10_90 = 0.8


def motion(video: str | Path, dt: float = 0.4) -> dict:
    """Median zoom %/s and pan px/s across the clip."""
    path = Path(video)
    if not path.is_file():
        raise GilvyError(f"video not found: {path}")
    frames, fps, src_w, src_h = _frames(path)
    return _motion_frames(frames, fps, src_w, src_h, dt)


def linear_dissolve_clocks(seconds: float) -> dict:
    """Full overlap versus the 10%–90% clock of a linear alpha dissolve.

    Photo dissolves use linear alpha across the authored seconds. The blend is
    not eased and it is not cut short. A 10%–90% measurement therefore spans
    80% of the overlap: 1.4s reads as 1.12s. House crossfades use ease-in-out
    and are a different curve.
    """
    seconds = float(seconds)
    return {
        "full_s": round(seconds, 3),
        "ten_ninety_s": round(seconds * LINEAR_DISSOLVE_10_90, 3),
    }


def _motion_frames(frames: np.ndarray, fps: float, src_w: int, src_h: int, dt: float) -> dict:
    if len(frames) < 3 or fps <= 0:
        raise GilvyError("not enough frames to measure motion")
    # A 0.4s pair at 1%/s changes scale by half a percent, which the search
    # cannot separate from resampling. Use a longer pair when the clip has it.
    duration = len(frames) / fps
    # Longer than ~0.5s and a real photograph's correlation locks onto the wrong
    # texture. Shorter than ~0.5s and a 1%/s zoom is inside the ratio step.
    span = max(float(dt), min(0.5, duration * 0.45))
    step = max(1, int(round(span * fps)))
    if len(frames) <= step:
        step = max(1, int(round(float(dt) * fps)))
    if len(frames) <= step:
        raise GilvyError("clip is shorter than the motion sample")
    prepared = [_soften(frame) for frame in frames]
    last = len(frames) - step
    count = min(16, last)
    if count == 1:
        indices = [0]
    else:
        indices = [int(round(i * (last - 1) / (count - 1))) for i in range(count)]
    sample_dt = step / fps
    rows = []
    for index in indices:
        ratio, shift_x, shift_y = _pair(prepared[index], prepared[index + step])
        rows.append((
            index / fps,
            ratio,
            shift_x * src_w / frames.shape[2],
            shift_y * src_h / frames.shape[1],
        ))
    zooms = [0.0 if row[1] <= 0 else 100.0 * float(np.log(row[1])) / sample_dt for row in rows]
    return {
        "zoom_pct_per_s": round(float(np.median(zooms)), 3),
        "pan_px_per_s": {
            "x": round(_velocity(rows, 2, sample_dt), 3),
            "y": round(_velocity(rows, 3, sample_dt), 3),
        },
        "samples": len(rows),
    }


def _velocity(rows: list[tuple], axis: int, dt: float) -> float:
    """Pan rate in source pixels per second.

    Scaling the earlier frame about the plate center also scales a pan that
    has already left that center. With the move starting on the first frame
    (the same clock as a scene cut), the shift over a pair is

        shift = v · (Δt + (1 − r) · t)

    and each pair estimates v. A free intercept fit treats resampling bias as
    a fake starting offset and overshoots. A slow zoom (r≈1) skips the
    correction; the raw shift/Δt is already the rate.
    """
    ratio = np.array([row[1] for row in rows], np.float64)
    time = np.array([row[0] for row in rows], np.float64)
    shift = np.array([row[axis] for row in rows], np.float64)
    if abs(float(np.median(ratio)) - 1.0) < 0.02:
        return float(np.median(shift / dt))
    denom = dt + (1.0 - ratio) * time
    good = np.abs(denom) > 1e-4
    if not np.any(good):
        return float(np.median(shift / dt))
    estimates = shift[good] / denom[good]
    med = float(np.median(estimates))
    # A real plate with type or a second move makes these estimates disagree.
    # The correction then invents a huge pan. Fall back to the raw shift.
    mad = float(np.median(np.abs(estimates - med)))
    if mad > max(6.0, 0.35 * abs(med)):
        return float(np.median(shift / dt))
    return med


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
    # 216 is the width the reference meter used. A 540-wide search locks onto
    # grain and type; the small frame keeps the photograph's scale.
    width = 216
    height = max(2, int(round(width * src_h / src_w)))
    height -= height % 2
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-an",
        "-vf", f"scale={width}:{height}:flags=area",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ])
    frame = width * height
    count = len(raw) // frame
    frames = np.frombuffer(raw[:count * frame], np.uint8).reshape(count, height, width)
    return frames, fps, src_w, src_h


def _soften(frame: np.ndarray) -> np.ndarray:
    image = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
    image = image.filter(ImageFilter.GaussianBlur(radius=0.4))
    return np.asarray(image, np.float32)


def _pair(earlier: np.ndarray, later: np.ndarray) -> tuple[float, float, float]:
    """Return push ratio (r>1 is a push-in) and the content shift in pixels."""
    ratio = _best_ratio(earlier, later)
    shift_x, shift_y = _phase_shift(_numpy_scale(earlier, ratio), later)
    return ratio, shift_x, shift_y


def _phase_shift(earlier: np.ndarray, later: np.ndarray) -> tuple[float, float]:
    """Phase correlation, the reference meter's pan. +x right, +y down."""
    a = earlier - float(earlier.mean())
    b = later - float(later.mean())
    cross = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    cross /= np.abs(cross) + 1e-9
    corr = np.abs(np.fft.ifft2(cross))
    height, width = corr.shape
    y, x = np.unravel_index(int(corr.argmax()), corr.shape)
    mid = float(corr[y, x])
    oy = _frac(float(corr[(y - 1) % height, x]), mid, float(corr[(y + 1) % height, x]))
    ox = _frac(float(corr[y, (x - 1) % width]), mid, float(corr[y, (x + 1) % width]))
    y = float(y) + oy
    x = float(x) + ox
    if y > height / 2:
        y -= height
    if x > width / 2:
        x -= width
    return -x, -y


def _best_ratio(earlier: np.ndarray, later: np.ndarray) -> float:
    coarse = _ratio_peak(earlier, later, np.linspace(0.85, 1.18, 34))
    fine = _ratio_peak(earlier, later, np.linspace(coarse - 0.01, coarse + 0.01, 21))
    return _ratio_vertex(earlier, later, fine)


def _ratio_peak(earlier: np.ndarray, later: np.ndarray, ratios) -> float:
    """Same score as the reference meter: pixel error of a centered scale, no pre-shift."""
    best_r, best = 1.0, 1e18
    for ratio in ratios:
        err = _aligned_error(earlier, later, float(ratio))
        if err < best:
            best, best_r = err, float(ratio)
    return best_r


def _ratio_vertex(earlier: np.ndarray, later: np.ndarray, center: float) -> float:
    """Sub-step ratio from the pixel-error curve. A 0.002 grid is 0.5%/s at dt=0.4."""
    samples = np.linspace(center - 0.004, center + 0.004, 9)
    errors = [_aligned_error(earlier, later, float(ratio)) for ratio in samples]
    quad = np.polyfit(samples, errors, 2)
    if quad[0] <= 1e-6:
        return float(center)
    vertex = float(-quad[1] / (2.0 * quad[0]))
    if not math.isfinite(vertex) or abs(vertex - center) > 0.005:
        return float(center)
    return vertex


def _aligned_error(earlier: np.ndarray, later: np.ndarray, ratio: float) -> float:
    height, width = later.shape
    crop = (slice(height // 8, height - height // 8), slice(width // 12, width - width // 12))
    scaled = _numpy_scale(earlier, ratio)
    # A few pixels of shift, so a pan is not scored as zoom. Wider than this
    # and a repeated texture wins over the real scale.
    shift_x, shift_y = _corr_shift(scaled[crop], later[crop], span=6)
    moved = _translate(scaled, shift_x, shift_y)
    diff = moved[crop] - later[crop]
    return float(np.mean(diff * diff))


def _numpy_scale(frame: np.ndarray, ratio: float) -> np.ndarray:
    """Magnify about the center. ratio>1 makes a push-in match the later frame."""
    if abs(ratio - 1.0) < 1e-4:
        return frame
    height, width = frame.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cy, cx = (height - 1) / 2.0, (width - 1) / 2.0
    inv = 1.0 / ratio
    sy = np.clip((yy - cy) * inv + cy, 0, height - 1.001)
    sx = np.clip((xx - cx) * inv + cx, 0, width - 1.001)
    y0 = sy.astype(np.int32)
    x0 = sx.astype(np.int32)
    wy = sy - y0
    wx = sx - x0
    return (
        frame[y0, x0] * (1 - wy) * (1 - wx)
        + frame[y0, x0 + 1] * (1 - wy) * wx
        + frame[y0 + 1, x0] * wy * (1 - wx)
        + frame[y0 + 1, x0 + 1] * wy * wx
    )


def _corr_shift(earlier: np.ndarray, later: np.ndarray, span: int | None = None) -> tuple[float, float]:
    """Content motion from `earlier` to `later`, in pixels. +x right, +y down.

    Plain correlation, not a phase peak. Phase whitening locks onto grain and
    reports no shift on a low-contrast plate.
    """
    if earlier.shape != later.shape:
        earlier = _match_shape(earlier, later.shape)
    a = earlier - float(earlier.mean())
    b = later - float(later.mean())
    corr = np.fft.ifft2(np.fft.fft2(a) * np.conj(np.fft.fft2(b))).real
    height, width = corr.shape
    # A peak on the far side of the frame is a repeated texture, not the pan.
    if span is None:
        span = 12
    span = min(int(span), height // 3, width // 3)
    ys = np.arange(-span, span + 1) % height
    xs = np.arange(-span, span + 1) % width
    window = corr[np.ix_(ys, xs)]
    local_y, local_x = np.unravel_index(int(window.argmax()), window.shape)
    y, x = int(ys[local_y]), int(xs[local_x])
    mid = float(corr[y, x])
    oy = _frac(float(corr[(y - 1) % height, x]), mid, float(corr[(y + 1) % height, x]))
    ox = _frac(float(corr[y, (x - 1) % width]), mid, float(corr[y, (x + 1) % width]))
    y = float(y) + oy
    x = float(x) + ox
    if y > height / 2:
        y -= height
    if x > width / 2:
        x -= width
    # The peak sits at the inverse shift. Negating it makes +x content-right.
    return -x, -y


def _translate(frame: np.ndarray, dx: float, dy: float) -> np.ndarray:
    image = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
    out = image.transform(
        image.size,
        Image.Transform.AFFINE,
        (1.0, 0.0, -dx, 0.0, 1.0, -dy),
        resample=Image.Resampling.BICUBIC,
    )
    return np.asarray(out, np.float32)


def _match_shape(frame: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    canvas = np.zeros(shape, np.float32)
    height = min(shape[0], frame.shape[0])
    width = min(shape[1], frame.shape[1])
    canvas[:height, :width] = frame[:height, :width]
    return canvas


def _frac(left: float, mid: float, right: float) -> float:
    denom = left - 2.0 * mid + right
    if abs(denom) < 1e-8:
        return 0.0
    return float(np.clip(0.5 * (left - right) / denom, -0.5, 0.5))
