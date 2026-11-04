"""Per-shot effect detectors. They read a rendered or reference clip and return
the same track schema the episode camera uses, plus the effect events.

Ease fitting compares the normalized progress with the library curves and
keeps the lowest RMSE. A flat line has no ease.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from gilvy.keyframes import apply_ease

# The curves the reference inventory was scored against, plus the quad/cubic set.
FIT_EASES = (
    "linear",
    "easeInQuad", "easeOutQuad", "easeInOutQuad",
    "easeInCubic", "easeOutCubic", "easeInOutCubic",
    "expoIn", "expoOut",
)


def fit_ease(values) -> dict | None:
    """Best ease for a progress series. Returns name, rmse, and the linear rmse."""
    y = np.asarray(values, float)
    if len(y) < 4 or abs(y[-1] - y[0]) < 1e-6:
        return None
    progress = (y - y[0]) / (y[-1] - y[0])
    t = np.linspace(0, 1, len(y))
    scores = {}
    for name in FIT_EASES:
        curve = np.array([apply_ease(name, float(p)) for p in t])
        scores[name] = float(np.sqrt(np.mean((curve - progress) ** 2)))
    best = min(scores, key=scores.get)
    return {"ease": best, "rmse": round(scores[best], 4), "linear_rmse": round(scores["linear"], 4)}


def detect_shot(video: str | Path) -> dict:
    """Curves and events for one clip. Safe on a still: it returns empty events."""
    frames, fps, audio = _load(Path(video))
    if len(frames) < 4 or fps <= 0:
        return {"fps": fps, "tracks": [], "events": []}
    scale = _scale_curve(frames)
    ease = fit_ease(scale)
    duration = (len(frames) - 1) / fps
    tracks = [{
        "property": "scale",
        "keys": [
            {"t": 0.0, "v": round(float(scale[0]), 4), "ease": (ease or {}).get("ease", "linear")},
            {"t": round(duration, 4), "v": round(float(scale[-1]), 4), "ease": "linear"},
        ],
    }]
    zoom = 0.0
    if scale[0] > 0 and scale[-1] > 0 and duration > 0:
        zoom = float(np.log(scale[-1] / scale[0]) / duration * 100)
    events = []
    if ease:
        events.append({"effect": "zoom", "zoom_pct_per_s": round(zoom, 3), **ease})
    turned = _rotation(frames)
    if abs(turned) >= 0.4:
        events.append({"effect": "rotation", "degrees": round(turned, 2)})
        tracks.append({
            "property": "rotation",
            "keys": [{"t": 0.0, "v": 0.0, "ease": "linear"}, {"t": round(duration, 4), "v": round(turned, 2), "ease": "linear"}],
        })
    hz = _shake_hz(frames, fps)
    if hz:
        events.append({"effect": "shake", **hz})
    flash = _flash_frame(frames)
    if flash is not None:
        events.append({"effect": "flash", "frame": flash, "time": round(flash / fps, 4)})
    whip = _whip_frame(frames)
    if whip is not None:
        events.append({"effect": "whip", "frame": whip, "time": round(whip / fps, 4)})
    dissolve = _dissolve(frames, fps)
    if dissolve:
        events.append({"effect": "dissolve", **dissolve})
    words = _word_times(frames, fps)
    if words:
        events.append({"effect": "typewriter", "times": words})
    if audio is not None:
        onset = _onset(audio, fps)
        if onset is not None:
            events.append({"effect": "sfx", "time": round(onset, 4)})
    return {"fps": fps, "duration": round(duration, 4), "tracks": tracks, "events": events, "zoom_pct_per_s": round(zoom, 3)}


def keyframe_document(shot: dict, name: str = "template") -> dict:
    """Episode-shaped tracks so analyze-reference output can be saved as a template."""
    return {
        "name": name,
        "scenes": [{
            "tracks": shot.get("tracks") or [],
            "events": shot.get("events") or [],
        }],
    }


def _load(path: Path):
    import json
    from fractions import Fraction

    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", str(path),
    ]))
    stream = info["streams"][0]
    src_w, src_h = int(stream["width"]), int(stream["height"])
    fps = float(Fraction(stream["avg_frame_rate"]))
    width = 96
    height = max(2, int(round(width * src_h / src_w)))
    height -= height % 2
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-an",
        "-vf", f"scale={width}:{height}:flags=area",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    frame = width * height * 3
    count = len(raw) // frame
    frames = np.frombuffer(raw[:count * frame], np.uint8).reshape(count, height, width, 3)
    audio = None
    probed = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if probed.stdout.strip():
        wav = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
            capture_output=True,
        )
        if wav.returncode == 0 and wav.stdout:
            audio = np.frombuffer(wav.stdout, np.int16).astype(np.float32)
    return frames, fps, audio


def _scale_curve(frames: np.ndarray) -> np.ndarray:
    """Cumulative scale, 1 at the first frame. Pairs use a short SSD search."""
    gray = frames.mean(axis=3)
    scale = np.ones(len(frames), np.float64)
    for i in range(1, len(frames)):
        ratio = _pair_scale(gray[i - 1], gray[i])
        scale[i] = scale[i - 1] * ratio
    return scale


def _pair_scale(a: np.ndarray, b: np.ndarray) -> float:
    best_s, best = 1.0, 1e18
    h, w = a.shape
    crop = (slice(h // 5, h - h // 5), slice(w // 5, w - w // 5))
    for scale in np.linspace(0.88, 1.14, 27):
        warped = _resize_center(a, float(scale))
        err = float(np.mean((warped[crop] - b[crop]) ** 2))
        if err < best:
            best, best_s = err, float(scale)
    return best_s


def _resize_center(frame: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1) < 1e-4:
        return frame
    image = Image.fromarray(frame.astype(np.uint8))
    w, h = image.size
    nw, nh = max(2, int(round(w * scale))), max(2, int(round(h * scale)))
    resized = np.asarray(image.resize((nw, nh), Image.Resampling.BILINEAR), np.float32)
    canvas = np.zeros_like(frame, np.float32)
    y0 = max(0, (nh - h) // 2)
    x0 = max(0, (nw - w) // 2)
    y1 = max(0, (h - nh) // 2)
    x1 = max(0, (w - nw) // 2)
    src = resized[y0:y0 + (h - 2 * y1), x0:x0 + (w - 2 * x1)]
    canvas[y1:y1 + src.shape[0], x1:x1 + src.shape[1]] = src
    return canvas


def _rotation(frames: np.ndarray) -> float:
    """Change in the principal axis of the bright pixels, first frame to last."""
    return _axis(frames[-1]) - _axis(frames[0])


def _axis(frame: np.ndarray) -> float:
    gray = frame.mean(axis=2)
    mask = gray > float(gray.mean()) + 40
    ys, xs = np.nonzero(mask)
    if len(xs) < 30:
        return 0.0
    x = xs.astype(float) - xs.mean()
    y = ys.astype(float) - ys.mean()
    cxx, cyy, cxy = (x * x).mean(), (y * y).mean(), (x * y).mean()
    return float(np.degrees(0.5 * np.arctan2(2 * cxy, cxx - cyy)))


def _shake_hz(frames: np.ndarray, fps: float) -> dict | None:
    gray = frames.mean(axis=3)
    # A bright marker's centroid. A full-frame plate falls back to the luma centroid.
    cents = []
    for frame in gray:
        mask = frame > np.percentile(frame, 90)
        ys, xs = np.nonzero(mask)
        if len(xs) < 5:
            return None
        cents.append((xs.mean(), ys.mean()))
    series = np.array(cents)
    signal = series[:, 0] - series[:, 0].mean()
    if len(signal) < 8 or signal.std() < 0.15:
        return None
    spec = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / fps)
    spec[0] = 0
    peak = int(spec.argmax())
    if freqs[peak] < 1:
        return None
    return {"hz": round(float(freqs[peak]), 2), "amp_px": round(float(signal.std() * 2), 2)}


def _flash_frame(frames: np.ndarray) -> int | None:
    luma = frames.mean(axis=(1, 2, 3))
    if len(luma) < 3:
        return None
    peak = int(luma.argmax())
    neighbors = np.median(np.delete(luma, peak))
    if luma[peak] - neighbors > 25:
        return peak
    return None


def _whip_frame(frames: np.ndarray) -> int | None:
    if len(frames) < 3:
        return None
    diff = np.mean(np.abs(np.diff(frames.astype(np.int16), axis=0)), axis=(1, 2, 3))
    peak = int(diff.argmax())
    if diff[peak] > np.median(diff) * 2.5 and diff[peak] > 8:
        return peak + 1
    return None


def _dissolve(frames: np.ndarray, fps: float) -> dict | None:
    red = frames[:, :, :, 0].astype(float).mean(axis=(1, 2))
    if abs(red[0] - red[-1]) < 15:
        return None
    delta = np.abs(np.diff(red))
    hot = np.where(delta > max(0.6, float(np.median(delta)) * 3))[0]
    if len(hot) < 2:
        return None
    start, end = int(hot[0]), int(hot[-1]) + 1
    if end <= start:
        return None
    duration = (end - start) / fps
    if duration < 0.2 or duration > 2.5:
        return None
    ease = fit_ease(red[start:end + 1])
    return {
        "start": round(start / fps, 4),
        "end": round(end / fps, 4),
        "duration": round(duration, 4),
        "ease": (ease or {}).get("ease", "linear"),
        "rmse": (ease or {}).get("rmse", 0),
    }


def _word_times(frames: np.ndarray, fps: float) -> list[float]:
    white = ((frames[:, :, :, 0] > 210) & (frames[:, :, :, 1] > 210) & (frames[:, :, :, 2] > 210)).sum(axis=(1, 2))
    if white.max() < 30:
        return []
    jumps = []
    for i in range(1, len(white)):
        if white[i] - white[i - 1] > max(20, 0.25 * white.max()):
            jumps.append(round(i / fps, 4))
    return jumps


def _onset(audio: np.ndarray, video_fps: float) -> float | None:
    if audio is None or len(audio) < 1600:
        return None
    hop = 160
    energy = np.array([
        float(np.sqrt(np.mean(audio[i:i + hop] ** 2)))
        for i in range(0, len(audio) - hop, hop)
    ])
    if energy.max() < 200:
        return None
    return float(np.argmax(energy) * hop / 16000)
