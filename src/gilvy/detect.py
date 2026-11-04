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
    path = Path(video)
    frames, fps, audio = _load(path)
    if len(frames) < 4 or fps <= 0:
        return {"fps": fps, "tracks": [], "events": []}
    times, scale = _scale_curve(frames, fps)
    scale = _despike_scale(scale)
    # A 2% zoom is a fraction of a pixel at the 96px analysis width, so the
    # signed rate comes from a wider match. Larger punches stay on the fast path.
    if len(scale) >= 2 and abs(float(scale[-1]) - 1.0) <= 0.15:
        wide, wide_fps, _ = _load(path, width=240)
        if len(wide) >= 4 and wide_fps > 0:
            times, scale = _scale_curve(wide, wide_fps)
            scale = _despike_scale(scale)
    # Shake is a >4Hz wobble on top of the zoom. Measure the rate on the
    # low-passed trend so a 10Hz camera shake is not read as extra scale.
    scale, shook = _detach_shake(scale, fps)
    ease = fit_ease(scale)
    # The encoder's last frame is one tick before the shot length (n/fps).
    # A back-loaded ease still has zoom left in that tick. Project the fitted
    # curve to the shot length instead of multiplying per-frame guesses, which
    # ran high while expoOut was steep and reported 29.5 for an authored 25.
    duration = len(frames) / fps if fps else 0.0
    project_ease = (ease or {}).get("ease")
    # A 2% line can look stepped at the search grain and fit a fake ease-in
    # that is barely better than linear. A real expo fit beats linear by a lot.
    if (
        ease
        and ease.get("rmse", 1.0) > 0.08
        and ease.get("rmse", 1.0) > 0.7 * ease.get("linear_rmse", 1.0)
        and abs(float(scale[-1]) - float(scale[0])) <= 0.10
    ):
        project_ease = "linear"
    end_scale = _robust_end(times, scale, duration, project_ease)
    tracks = [{
        "property": "scale",
        "keys": [
            {"t": 0.0, "v": round(float(scale[0]), 4), "ease": (ease or {}).get("ease", "linear")},
            {"t": round(duration, 4), "v": round(float(end_scale), 4), "ease": "linear"},
        ],
    }]
    zoom = _zoom_rate(times, scale, duration, end_scale, shook)
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


def _load(path: Path, width: int = 96):
    import json
    from fractions import Fraction

    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", str(path),
    ]))
    stream = info["streams"][0]
    src_w, src_h = int(stream["width"]), int(stream["height"])
    fps = float(Fraction(stream["avg_frame_rate"]))
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


def _project_end(scale: np.ndarray, times: np.ndarray, duration: float, ease: str | None) -> float:
    """Scale at the shot length, one tick past the last encoded frame."""
    s0, s_last = float(scale[0]), float(scale[-1])
    t_last = float(times[-1])
    if not ease or duration <= 0 or t_last >= duration - 1e-4:
        return s_last
    covered = apply_ease(ease, t_last / duration)
    if covered < 0.2:
        return s_last
    return s0 + (s_last - s0) / covered


def _despike_scale(scale: np.ndarray) -> np.ndarray:
    """Drop a one-frame snap back toward scale 1.

    A scene trim that includes the first frame of the next shot reads as the
    zoom undoing itself. A real ease keeps moving away from 1, so those steps stay.
    """
    y = np.asarray(scale, float).copy()
    for index in range(3, len(y)):
        ref = float(np.median(y[index - 3:index]))
        jump = float(y[index] - ref)
        toward_one = (ref - 1.0) * jump < 0
        if toward_one and abs(jump) > 0.01:
            y[index] = ref
    return y


def _robust_end(times: np.ndarray, scale: np.ndarray, duration: float, ease: str | None) -> float:
    """End scale from every frame the ease has actually moved, not the last one.

    Projecting only the final sample amplifies a single noisy frame, and an
    expoIn tail is exactly where that sample is noisiest.
    """
    # A linear move is a straight chord. The last sample, projected across the
    # final tick, is that chord. Averaging earlier samples reintroduces the
    # search steps and steepens a 2% pull.
    if not ease or ease == "linear" or duration <= 0 or len(scale) < 4:
        return _project_end(scale, times, duration, ease)
    s0 = float(scale[0])
    guesses = []
    for time, value in zip(times, scale):
        covered = apply_ease(ease, float(np.clip(time / duration, 0.0, 1.0)))
        if covered < 0.4:
            continue
        guesses.append(s0 + (float(value) - s0) / covered)
    if len(guesses) < 3:
        return _project_end(scale, times, duration, ease)
    med = float(np.median(guesses))
    if not 0.4 <= med <= 4.0:
        return _project_end(scale, times, duration, ease)
    return med


def _zoom_rate(times: np.ndarray, scale: np.ndarray, duration: float, end_scale: float, shook: bool) -> float:
    """Endpoint log rate, or the robust log-scale slope for a steady small zoom.

    A 2% pull is a nearly straight line in log-scale, and the slope carries the
    sign. An eased punch is not that line; its rate stays the projected endpoints.
    Shake uses those endpoints on the low-passed trend, not the raw wiggle.
    """
    s0 = float(scale[0]) if len(scale) else 1.0
    if s0 <= 0 or end_scale <= 0 or duration <= 0:
        return 0.0
    endpoint = float(np.log(end_scale / s0) / duration * 100.0)
    if shook or not _log_linear(times, scale):
        return endpoint
    slope = _theil_sen_log(times, scale)
    # Early search steps make pairwise slopes steeper than the shot endpoints.
    # The endpoints carry the rate; the slope is there to keep the sign when
    # the two agree, and to reject a slope that flipped it.
    if endpoint * slope < 0 and abs(endpoint) >= 0.3:
        return endpoint
    if abs(slope - endpoint) > max(0.12, 0.04 * abs(endpoint)):
        return endpoint
    return slope


def _log_linear(times: np.ndarray, scale: np.ndarray) -> bool:
    y = np.log(np.clip(scale, 1e-4, None))
    t = np.asarray(times, float)
    if len(y) < 4 or float(t[-1] - t[0]) <= 0:
        return False
    slope = (y[-1] - y[0]) / (t[-1] - t[0])
    resid = y - (y[0] + slope * (t - t[0]))
    return float(np.median(np.abs(resid))) < 0.004


def _theil_sen_log(times: np.ndarray, scale: np.ndarray) -> float:
    """Median pairwise slope of ln(scale) versus time, in percent per second."""
    y = np.log(np.clip(np.asarray(scale, float), 1e-4, None))
    t = np.asarray(times, float)
    pick = np.linspace(0, len(y) - 1, min(len(y), 16)).astype(int)
    slopes = []
    for i in pick:
        for j in pick:
            if j <= i:
                continue
            dt = float(t[j] - t[i])
            if dt > 0.05:
                slopes.append((y[j] - y[i]) / dt)
    if not slopes:
        return 0.0
    return float(np.median(slopes) * 100.0)


def _detach_shake(scale: np.ndarray, fps: float) -> tuple[np.ndarray, bool]:
    """Split a scale series into a smooth zoom and a >4Hz shake residual.

    The moving average is one cycle of a 4Hz oscillation. A 8–10Hz shake
    averages out; a Ken Burns zoom does not. The raw curve is kept when the
    residual is just search noise, so an expo corner is not rounded off.
    """
    y = np.asarray(scale, float)
    if len(y) < 8 or fps < 8:
        return y, False
    win = int(round(fps / 4.0))
    if win % 2 == 0:
        win += 1
    win = max(3, min(win, len(y) - 1))
    trend = np.convolve(np.pad(y, win // 2, mode="edge"), np.ones(win) / win, mode="valid")
    trend = trend[:len(y)]
    resid = y - trend
    signs = np.sign(resid)
    crossings = int(np.sum(signs[1:] * signs[:-1] < 0))
    spread = float(np.std(y - np.median(y)))
    # A real shake keeps changing sign. The lag of an expo corner does not.
    shook = (
        crossings >= 4
        and float(np.std(resid)) > 0.008
        and (spread < 1e-6 or float(np.std(resid)) > 0.45 * spread)
    )
    return (trend if shook else y), shook


def _scale_curve(frames: np.ndarray, fps: float) -> tuple[np.ndarray, np.ndarray]:
    """Signed scale of each frame against the first.

    Every frame is matched, not a running product of a dozen guesses. The
    sample rate stays above 20Hz on short shots so a 10Hz shake is visible
    as its own component and can be filtered off the zoom.
    """
    gray = frames.mean(axis=3)
    n = len(gray)
    step = 1 if n <= 80 else max(1, int(round(fps / 24.0)))
    indexes = list(range(0, n, step))
    if indexes[-1] != n - 1:
        indexes.append(n - 1)
    scales = [1.0]
    times = [0.0]
    for index in indexes[1:]:
        # Each frame is searched on its own. A hint from the previous frame
        # lags an expoIn snap and reports a slow zoom.
        scales.append(_match_scale(gray[0], gray[index]))
        times.append(index / fps)
    return np.asarray(times, float), np.asarray(scales, float)


def _match_scale(earlier: np.ndarray, later: np.ndarray, hint: float | None = None) -> float:
    """Scale of `later` relative to `earlier`. Greater than 1 is a push-in.

    The search is signed: one correlation peak over scales below and above 1,
    after a translation that absorbs pan and shake. A pull used to lose a
    two-way error contest to a slightly better push. When the photometric
    peak is barely better than its reciprocal, pairwise feature distances
    (the same scale ORB would vote) break the tie.
    """
    scale, score = _ecc_scale(earlier, later, hint)
    if abs(scale - 1.0) > 0.12:
        return scale
    reciprocal = 1.0 / scale if scale > 1e-3 else 1.0
    if abs(reciprocal - scale) < 1e-3:
        return scale
    flip = _aligned_ncc(earlier, later, reciprocal)
    if score - flip >= 0.015:
        return scale
    feature = _feature_scale(earlier, later)
    if feature is None:
        return scale
    # Keep the photometric scale unless the feature alignment actually fits better.
    if _aligned_ncc(earlier, later, feature) + 0.005 < score:
        return scale
    return feature


def _ecc_scale(earlier: np.ndarray, later: np.ndarray, hint: float | None = None) -> tuple[float, float]:
    """Best signed scale by normalized correlation after translation."""
    del hint  # a previous-frame hint lags an expo snap; every pair is searched
    best_s, best_n = 1.0, _aligned_ncc(earlier, later, 1.0)
    for scale in np.linspace(0.90, 1.50, 31):
        score = _aligned_ncc(earlier, later, float(scale))
        if score > best_n:
            best_n, best_s = score, float(scale)
    center = best_s
    for scale in np.linspace(center - 0.02, center + 0.02, 17):
        if scale < 0.85:
            continue
        score = _aligned_ncc(earlier, later, float(scale))
        if score > best_n:
            best_n, best_s = score, float(scale)
    samples = np.linspace(best_s - 0.008, best_s + 0.008, 7)
    scores = [_aligned_ncc(earlier, later, float(scale)) for scale in samples]
    peak = int(np.argmax(scores))
    if 0 < peak < len(samples) - 1:
        x0, x1, x2 = (float(v) for v in samples[peak - 1:peak + 2])
        y0, y1, y2 = scores[peak - 1:peak + 2]
        denom = y0 - 2.0 * y1 + y2
        step = x1 - x0
        if abs(denom) > 1e-8 and step > 0:
            vertex = x1 + 0.5 * (y0 - y2) / denom * step
            if abs(vertex - best_s) < 0.012:
                return float(vertex), best_n
    return best_s, best_n


def _aligned_ncc(earlier: np.ndarray, later: np.ndarray, scale: float) -> float:
    """Correlation of `later` with `earlier` warped by `scale`, shift removed."""
    if scale >= 1.0:
        warped = _resize_center(earlier, scale)
        target = later.astype(np.float32)
    else:
        warped = _resize_center(later, 1.0 / scale)
        target = earlier.astype(np.float32)
    if warped.shape != target.shape:
        return -1.0
    dx, dy = _phase_shift(warped, target)
    limit_x, limit_y = warped.shape[1] * 0.4, warped.shape[0] * 0.4
    if abs(dx) > limit_x or abs(dy) > limit_y:
        dx, dy = 0.0, 0.0
    shifted, mask = _shift(warped, dx, dy)
    return _ncc(shifted, target, mask)


def _phase_shift(src: np.ndarray, dst: np.ndarray) -> tuple[float, float]:
    """Pixels to move `src` (x right, y down) so it lines up with `dst`."""
    a = src.astype(np.float32)
    b = dst.astype(np.float32)
    a -= float(a.mean())
    b -= float(b.mean())
    window = np.hanning(a.shape[0]).astype(np.float32)[:, None] * np.hanning(a.shape[1]).astype(np.float32)[None, :]
    cross = np.fft.rfft2(b * window) * np.conj(np.fft.rfft2(a * window))
    cross /= np.maximum(np.abs(cross), 1e-8)
    corr = np.fft.irfft2(cross, s=a.shape)
    iy, ix = np.unravel_index(int(np.argmax(corr)), a.shape)
    height, width = a.shape
    if iy > height // 2:
        iy -= height
    if ix > width // 2:
        ix -= width
    return float(ix), float(iy)


def _shift(image: np.ndarray, dx: float, dy: float) -> tuple[np.ndarray, np.ndarray]:
    height, width = image.shape
    ix, iy = int(round(dx)), int(round(dy))
    out = np.zeros_like(image, np.float32)
    mask = np.zeros(image.shape, bool)
    src_x0, dst_x0 = max(0, -ix), max(0, ix)
    src_y0, dst_y0 = max(0, -iy), max(0, iy)
    span_x = width - abs(ix)
    span_y = height - abs(iy)
    if span_x < 8 or span_y < 8:
        mask[:] = True
        return image, mask
    out[dst_y0:dst_y0 + span_y, dst_x0:dst_x0 + span_x] = image[src_y0:src_y0 + span_y, src_x0:src_x0 + span_x]
    mask[dst_y0:dst_y0 + span_y, dst_x0:dst_x0 + span_x] = True
    return out, mask


def _ncc(left: np.ndarray, right: np.ndarray, mask: np.ndarray) -> float:
    if int(mask.sum()) < 32:
        return -1.0
    a = left[mask].astype(np.float32)
    b = right[mask].astype(np.float32)
    a -= float(a.mean())
    b -= float(b.mean())
    denom = float(np.sqrt(np.dot(a, a) * np.dot(b, b))) + 1e-8
    return float(np.dot(a, b) / denom)


def _feature_scale(earlier: np.ndarray, later: np.ndarray) -> float | None:
    """Scale from pairwise distances of matched corners. Translation cancels."""
    left = _corners(earlier)
    right = _corners(later)
    if len(left) < 6 or len(right) < 6:
        return None
    matches = []
    for x, y in left:
        patch = _patch(earlier, x, y)
        if patch is None:
            continue
        best, where = 0.55, None
        for u, v in right:
            if abs(u - x) > 24 or abs(v - y) > 24:
                continue
            other = _patch(later, u, v)
            if other is None:
                continue
            score = _ncc(patch, other, np.ones(patch.shape, bool))
            if score > best:
                best, where = score, (u, v)
        if where is not None:
            matches.append(((x, y), where))
    if len(matches) < 5:
        return None
    ratios = []
    for i in range(len(matches)):
        for j in range(i + 1, len(matches)):
            (x0, y0), (u0, v0) = matches[i]
            (x1, y1), (u1, v1) = matches[j]
            span = float(np.hypot(x1 - x0, y1 - y0))
            if span < 10:
                continue
            ratios.append(float(np.hypot(u1 - u0, v1 - v0)) / span)
    if len(ratios) < 6:
        return None
    ratios = np.asarray(ratios, float)
    med = float(np.median(ratios))
    keep = np.abs(ratios - med) < max(0.02, 0.35 * abs(med - 1.0) + 0.01)
    if int(keep.sum()) < 4:
        return None
    return float(np.median(ratios[keep]))


def _corners(gray: np.ndarray) -> list[tuple[int, int]]:
    g = gray.astype(np.float32)
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
    gy[1:-1, :] = g[2:, :] - g[:-2, :]
    mag = gx * gx + gy * gy
    mag[:5, :] = 0
    mag[-5:, :] = 0
    mag[:, :5] = 0
    mag[:, -5:] = 0
    points = []
    cell_y = max(1, mag.shape[0] // 6)
    cell_x = max(1, mag.shape[1] // 6)
    for y0 in range(0, mag.shape[0] - cell_y + 1, cell_y):
        for x0 in range(0, mag.shape[1] - cell_x + 1, cell_x):
            block = mag[y0:y0 + cell_y, x0:x0 + cell_x]
            if float(block.max()) < 80:
                continue
            iy, ix = np.unravel_index(int(block.argmax()), block.shape)
            points.append((x0 + int(ix), y0 + int(iy)))
    return points


def _patch(gray: np.ndarray, x: int, y: int, radius: int = 4) -> np.ndarray | None:
    if x - radius < 0 or y - radius < 0 or x + radius >= gray.shape[1] or y + radius >= gray.shape[0]:
        return None
    return gray[y - radius:y + radius + 1, x - radius:x + radius + 1].astype(np.float32)


def _resize_center(frame: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1) < 1e-4:
        return frame.astype(np.float32)
    image = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8))
    w, h = image.size
    nw, nh = max(2, int(round(w * scale))), max(2, int(round(h * scale)))
    resized = np.asarray(image.resize((nw, nh), Image.Resampling.BILINEAR), np.float32)
    canvas = np.zeros(frame.shape, np.float32)
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


def _centroid(frame: np.ndarray) -> tuple[float, float]:
    """Bright-pixel centroid, or the luma centroid when that mask is a speck."""
    mask = frame > np.percentile(frame, 90)
    ys, xs = np.nonzero(mask)
    if len(xs) >= 15:
        return float(xs.mean()), float(ys.mean())
    total = float(frame.sum()) + 1e-6
    yy, xx = np.indices(frame.shape)
    return float((frame * xx).sum() / total), float((frame * yy).sum() / total)


def _highpass(signal: np.ndarray, fps: float, cutoff: float) -> np.ndarray:
    """Remove the trend slower than `cutoff` Hz. What remains is the shake."""
    y = np.asarray(signal, float)
    if len(y) < 8 or fps <= 0:
        return y
    win = int(round(fps / cutoff))
    if win % 2 == 0:
        win += 1
    win = max(3, min(win, len(y) - 1))
    trend = np.convolve(np.pad(y, win // 2, mode="edge"), np.ones(win) / win, mode="valid")
    return y - trend[:len(y)]


def _shake_hz(frames: np.ndarray, fps: float) -> dict | None:
    gray = frames.mean(axis=3)
    # A bright marker's centroid. A full-frame plate falls back to the luma centroid.
    cents = []
    for frame in gray:
        cents.append(_centroid(frame))
    series = np.array(cents)
    signal = series[:, 0] - series[:, 0].mean()
    signal = _highpass(signal, fps, 4.0)
    if len(signal) < 8 or signal.std() < 0.15:
        return None
    spec = np.abs(np.fft.rfft(signal * np.hanning(len(signal))))
    freqs = np.fft.rfftfreq(len(signal), 1 / fps)
    # Pan and zoom live below 4Hz. The shake is the oscillation above that.
    spec[freqs < 4.0] = 0
    if float(spec.max()) <= 0:
        return None
    peak = int(spec.argmax())
    if freqs[peak] < 4:
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
    """Dissolve length from the blend coefficient, 2% to 98% alpha.

    A frame is (1 − α) × outgoing + α × incoming. Ease-in spends most of its
    time under a frame-diff threshold, so the slow tail was dropped. α is the
    least-squares coefficient against the first and last frames, and the
    length is the time α spends between 0.02 and 0.98. A zoom is not a blend:
    its residual against that pair stays large, and a hard cut crosses the
    band in one frame.
    """
    small = frames[:, ::2, ::2, :].astype(np.float32)
    outgoing = small[0]
    incoming = small[-1]
    delta = incoming - outgoing
    denom = float(np.dot(delta.ravel(), delta.ravel()))
    if denom < 1.0 or float(np.mean(np.abs(delta))) < 8.0:
        return None
    alphas = np.empty(len(small), np.float64)
    flat = delta.ravel()
    base = outgoing.ravel()
    for i, frame in enumerate(small):
        alphas[i] = float(np.dot(frame.ravel() - base, flat) / denom)
    if float(alphas[-1] - alphas[0]) < 0.45:
        return None
    # Intermediate frames of a real dissolve land on the segment. A zoom does not.
    mid = len(alphas) // 2
    sample_at = (int(len(alphas) * 0.25), mid, int(len(alphas) * 0.75))
    residuals = []
    for index in sample_at:
        alpha = float(np.clip(alphas[index], 0.0, 1.0))
        guess = outgoing * (1.0 - alpha) + incoming * alpha
        residuals.append(float(np.mean(np.abs(small[index] - guess))))
    if float(np.median(residuals)) > 14.0:
        return None
    start = _alpha_time(alphas, 0.02, fps)
    end = _alpha_time(alphas, 0.98, fps)
    if start is None or end is None or end <= start:
        return None
    duration = end - start
    if duration < 0.2 or duration > 2.5:
        return None
    i0 = max(0, int(start * fps))
    i1 = min(len(alphas) - 1, int(round(end * fps)))
    ease = fit_ease(alphas[i0:i1 + 1]) if i1 - i0 >= 3 else None
    return {
        "start": round(start, 4),
        "end": round(end, 4),
        "duration": round(duration, 4),
        "ease": (ease or {}).get("ease", "linear"),
        "rmse": (ease or {}).get("rmse", 0),
    }


def _alpha_time(alphas: np.ndarray, level: float, fps: float) -> float | None:
    """First time a rising alpha series crosses `level`, linearly interpolated."""
    if level <= 0.5 and float(alphas[0]) >= level:
        return 0.0
    for index in range(1, len(alphas)):
        a0, a1 = float(alphas[index - 1]), float(alphas[index])
        if a0 < level <= a1:
            span = a1 - a0
            frac = 0.0 if abs(span) < 1e-8 else (level - a0) / span
            return (index - 1 + float(np.clip(frac, 0.0, 1.0))) / fps
    return None


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
