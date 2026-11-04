"""Image plates for the opt-in vox-explainer and history-story presets.

Drawn at delivery resolution, in the same design space (1080×1920) the house
show uses, then fitted. House episodes never reach this module.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gilvy.easing import cl, eio, eo
from gilvy.collage import parse_fragment, blit_fragment, track_time
from gilvy.effects import apply_plate_effects, draw_mask, draw_strike, parse_effects, shake_offset, typewriter_count
from gilvy.errors import EpisodeError, GilvyError
from gilvy.formats import DESIGN_H, DESIGN_W
from gilvy.keyframes import EASES, apply_ease, parse_tracks, sample_keys
from gilvy.presets import HISTORY, PHOTO_PRESETS, RULES, VOX
from gilvy.voxlook import (
    PALETTE,
    cork_image,
    draw_card,
    draw_chip,
    draw_headline,
    draw_tag,
    sans_path,
    serif_path,
)

_CACHE: dict[tuple, Image.Image] = {}
_FONTS: dict[tuple, ImageFont.FreeTypeFont] = {}
_EASE = {"linear", "ease-out", "ease-in-out", "exponential", *EASES}
_GRADES = {"none", "sepia", "paper"}
_TRANSITIONS = {"cut", "dissolve", "zoom", "match"}
# High-frequency std of unit gaussian noise after a 1.5px blur is removed.
# grain_std asks for that measured std, so the noise amplitude is std / this gain.
_GRAIN_HF_GAIN = 0.945
_OVERLAYS = {
    "text", "highlighter", "circle", "arrow", "strike", "mask", "stamp",
    "headline", "tag", "chip", "card",
}
_ENTRANCES = {"fade", "pop", "slide", "typewriter"}
_FONTS_NAMED = {"serif", "sans"}

# Median of red text pixels on the attached ref3 frame at 5.0s. Antialiased,
# so this is a swatch, not a vector fill recovered from the edit.
MEASURED_RED = (178, 74, 66)


def parse_image_params(raw: dict, index: int, style: str, *, timing_final: bool = True) -> dict:
    """Validate one image scene's extra fields. Paths are not required to exist yet."""
    if style not in PHOTO_PRESETS:
        raise EpisodeError(
            f"scene {index}: type image needs style: vox-explainer or style: history-story. "
            "House episodes keep a still camera and drawn scenes."
        )
    rules = RULES[style]
    params = {}
    composition = raw.get("composition", "plate")
    if composition not in ("plate", "collage"):
        raise EpisodeError(f"scene {index}: composition must be plate or collage")
    params["composition"] = composition
    layers = _layers(raw, index)
    params["layers"] = layers
    params["camera"] = _camera(raw.get("camera"), index, rules)
    grade = raw.get("grade", "none" if composition == "collage" else rules["default_grade"])
    if not isinstance(grade, str) or grade not in _GRADES:
        raise EpisodeError(f"scene {index}: grade must be none, sepia, or paper")
    params["grade"] = grade
    params["grain"] = _unit(raw.get("grain", 0 if composition == "collage" else rules["default_grain"]), index, "grain")
    params["grain_std"] = _grain_std(raw.get("grain_std"), index)
    params["paper"] = _unit(raw.get("paper", 0.12 if grade == "paper" else 0.0), index, "paper")
    params["color_tracks"] = _color_tracks(raw.get("color"), index)
    params["backdrop"] = _backdrop(raw.get("backdrop"), index)
    show = raw.get("show_caption", False)
    if not isinstance(show, bool):
        raise EpisodeError(f"scene {index}: show_caption must be true or false")
    params["show_caption"] = show
    kind = raw.get("transition_out", rules["default_transition"])
    if not isinstance(kind, str) or kind not in _TRANSITIONS:
        raise EpisodeError(f"scene {index}: transition_out must be cut, dissolve, zoom, or match")
    params["transition_out"] = kind
    params["match_tracks"] = _match_tracks(raw.get("match"), index) if kind == "match" else {}
    if kind == "cut":
        seconds = _num(raw.get("transition", 0), index, "transition", 0, 4)
    elif kind == "match" and raw.get("transition") is None:
        seconds = 0.40
    elif raw.get("transition") is None:
        seconds = 0.30 if kind == "zoom" else max(0.40, float(rules["default_transition_s"] or 0.40))
    else:
        seconds = _num(raw["transition"], index, "transition", 0, 4)
    ease_name = raw.get("transition_ease") or "linear"
    if ease_name not in EASES and ease_name != "linear":
        raise EpisodeError(f"scene {index}: transition_ease must be a track ease")
    # An eased dissolve may run to 4s. ref1 has a 3.7s join; a plain linear
    # one stays at 2.0 so older episodes keep the same bound.
    limit = 4.0 if ease_name != "linear" else 2.0
    if not math.isfinite(seconds) or not 0 <= seconds <= limit:
        raise EpisodeError(f"scene {index}: transition must be seconds from 0 to {limit}")
    params["transition"] = seconds
    params["transition_ease"] = ease_name
    prompt = raw.get("prompt", "")
    if not isinstance(prompt, str):
        raise EpisodeError(f"scene {index}: prompt must be a string")
    params["prompt"] = prompt.strip()
    params["text_fade_s"] = _fade_seconds(raw.get("text_fade_s", rules["text_fade_s"]), index)
    params["overlays"] = _overlays(raw.get("overlays", []), index, rules, params["text_fade_s"])
    placed_ids = {layer["id"] for layer in layers if "placement" in layer}
    for overlay in params["overlays"]:
        if overlay.get("parent") is not None and overlay["parent"] not in placed_ids:
            raise EpisodeError(f"scene {index}: overlay parent must name a placed layer")
    params["effects"] = parse_effects(raw.get("effects"), index)
    if composition != "collage" and timing_final:
        duration = raw.get("min")
        if duration is None:
            duration = max((key["t"] for keys in params["camera"]["tracks"].values() for key in keys), default=2.5)
        _metrics_or_raise(params["camera"], index, style, float(duration))
    return params


def camera_path(camera: dict, duration: float) -> list[tuple[float, dict]]:
    """Sample every segment, including exact keys and cubic-bezier extrema.

    Segment-local sampling prevents a short or delayed move from disappearing
    between global samples. Peak derivatives are numerical estimates (256 steps).
    """
    times = {0.0, float(duration)}
    for keys in (camera.get("tracks") or {}).values():
        times.update(float(k["t"]) for k in keys if 0 <= k["t"] <= duration)
        for a, b in zip(keys, keys[1:]):
            if a.get("ease") != "cubic-bezier":
                continue
            x1, y1, x2, y2 = a["bezier"]
            # dy/ds = 3 * (A*s² + B*s + C).
            roots = np.roots([1 + 3*y1 - 3*y2, 2*y2 - 4*y1, y1])
            for root in roots:
                if np.isreal(root) and 0 < float(root.real) < 1:
                    s = float(root.real)
                    x = 3*(1-s)**2*s*x1 + 3*(1-s)*s*s*x2 + s**3
                    t = a["t"] + (b["t"]-a["t"])*x
                    if 0 < t < duration:
                        times.add(t)
    boundaries = sorted(times)
    for a, b in zip(boundaries, boundaries[1:]):
        times.update(float(t) for t in np.linspace(a, b, 257))
    return [(t, camera_pose(camera, t, duration)) for t in sorted(times)]


def camera_metrics(camera: dict, duration: float) -> dict:
    """Plate rates. Exponential zoom reports the constant relative %/s a measurement sees.

    Keep legacy signed endpoint rates, alongside full-path travel and peaks.
    """
    duration = max(float(duration), 1e-6)
    s0, x0, y0 = _camera_at(camera, 0.0, duration)
    s1, x1, y1 = _camera_at(camera, duration, duration)
    if camera.get("ease") == "exponential" and "scale" not in (camera.get("tracks") or {}) and s0 > 0 and s1 > 0 and s0 != s1:
        zoom = math.log(s1 / s0) / duration * 100.0
    else:
        zoom = (s1 - s0) / duration * 100.0
    pan_x = (x1 - x0) / duration
    pan_y = (y1 - y0) / duration
    spun = 0.0
    if "rotation" in (camera.get("tracks") or {}):
        spun = abs(sample_keys(camera["tracks"]["rotation"], duration, duration) - sample_keys(camera["tracks"]["rotation"], 0.0, duration))
    path = camera_path(camera, duration)
    travel = {prop: 0.0 for prop in ("scale", "x", "y", "rotation")}
    peak_zoom = peak_pan = 0.0
    zoom_min = zoom_max = 0.0
    for (ta, a), (tb, b) in zip(path, path[1:]):
        dt = tb - ta
        for prop in travel:
            travel[prop] += abs(b[prop] - a[prop])
        rate = (b["scale"] - a["scale"]) / dt * 100
        peak_zoom = max(peak_zoom, abs(rate))
        zoom_min, zoom_max = min(zoom_min, rate), max(zoom_max, rate)
        peak_pan = max(peak_pan, math.hypot(b["x"]-a["x"], b["y"]-a["y"]) / dt)
    moving = travel["scale"] >= .004 or math.hypot(travel["x"], travel["y"]) >= 6 or travel["rotation"] >= .4
    return {
        "ease": camera["ease"],
        "duration": round(duration, 4),
        "zoom_pct_per_s": round(zoom, 4),
        "pan_px_per_s": {"x": round(pan_x, 3), "y": round(pan_y, 3)},
        "static": not moving,
        "travel": travel,
        "peak_zoom_pct_per_s": round(peak_zoom, 4),
        "peak_push_pct_per_s": round(zoom_max, 4),
        "peak_pull_pct_per_s": round(abs(zoom_min), 4),
        "peak_pan_px_per_s": round(peak_pan, 3),
        "explicit_tracks": bool(camera.get("tracks")),
        "peak_method": "segment-local finite differences (256 subdivisions)",
    }


def _zoom_percent(camera: dict, duration: float) -> float:
    start, end = camera["from"]["scale"], camera["to"]["scale"]
    if camera.get("ease") == "exponential" and start > 0 and end > 0 and start != end:
        return math.log(end / start) / duration * 100.0
    return (end - start) / duration * 100.0


def overlay_start(overlay: dict, vo: str, duration: float, style: str) -> float:
    """Seconds from the scene start. `at` wins. A keyword is a share of the line.

    Vox lead and history lag are the shot-study timings, not forced alignment.
    """
    if overlay.get("at") is not None:
        return float(overlay["at"])
    keyword = str(overlay.get("keyword") or "").strip(".,!?").lower()
    words = [word.strip(".,!?").lower() for word in str(vo).split() if word]
    index = 0
    for i, word in enumerate(words):
        if keyword and keyword == word:
            index = i
            break
    base = float(duration) * index / max(1, len(words))
    lead = RULES.get(style, {}).get("keyword_lead", 0.0)
    return max(0.0, base + lead)


def overlay_event(overlay: dict, vo: str, duration: float, style: str, scene_start: float) -> dict:
    """Resolve the visual onset into both clocks for audio and metadata consumers."""
    onset = overlay_start(overlay, vo, duration, style)
    clock = overlay.get("clock", "scene")
    episode_at = onset if clock == "episode" else scene_start + onset
    return {"at": onset, "clock": clock, "episode_at": episode_at,
            "scene_at": episode_at - scene_start, "event_id": overlay.get("event_id"),
            "timing": "keyword_estimate" if overlay.get("keyword") and overlay.get("at") is None else "explicit",
            "sfx": overlay.get("sfx")}


def render_image_frame(theme, scene: dict, u: float, duration: float, episode_dir: str, *, scene_start: float = 0, episode_time: float | None = None) -> np.ndarray:
    """One RGB float32 frame at the theme's delivery size."""
    params = scene["params"]
    frame = np.empty((theme.height, theme.width, 3), np.float32)
    frame[:] = np.array(theme.bg, np.float32)
    x0, y0, cw, ch = _content_box(theme)
    if cw < 2 or ch < 2:
        return frame
    plate = np.zeros((ch, cw, 3), np.float32)
    plate[:] = np.array(theme.bg, np.float32)
    if params.get("backdrop") == "cork":
        cork = np.asarray(cork_image(cw, ch, seed=11), np.float32)
        plate[:] = cork
    pose = camera_pose(params["camera"], u, duration)
    shake = (0.0, 0.0)
    for effect in params.get("effects") or []:
        if effect["kind"] == "shake":
            dx, dy = shake_offset(effect, u)
            shake = (shake[0] + dx, shake[1] + dy)
    for layer in params["layers"]:
        if "placement" in layer:
            def paint_attached(plane):
                for item in params["overlays"]:
                    if item.get("parent") != layer["id"]: continue
                    annotation = Image.new("RGBA", plane.size, (0, 0, 0, 0))
                    pen = ImageDraw.Draw(annotation)
                    time = track_time(item, u, scene_start, episode_time)
                    start = overlay_start(item, scene.get("vo") or "", duration, scene.get("style") or VOX)
                    _draw_overlay(pen, annotation, item, time, start, theme, theme.fit.ox, theme.fit.oy, episode_dir)
                    plane.alpha_composite(annotation)
            blit_fragment(plate, _load(Path(episode_dir) / layer["src"]), layer, pose, u, duration, theme.fit.scale, scene_start, shake, episode_time, paint_attached)
            continue
        gain = 0.25 + 0.75 * float(layer["depth"])
        tracks = layer.get("tracks") or {}
        clock = track_time(layer, u, scene_start, episode_time)
        scale = 1.0 + (pose["scale"] - 1.0) * gain
        if "scale" in tracks:
            scale *= sample_keys(tracks["scale"], clock, duration)
        ox = pose["x"] * gain * theme.fit.scale + shake[0]
        oy = pose["y"] * gain * theme.fit.scale + shake[1]
        if "x" in tracks:
            ox += sample_keys(tracks["x"], clock, duration)
        if "y" in tracks:
            oy += sample_keys(tracks["y"], clock, duration)
        image = _load(Path(episode_dir) / layer["src"])
        if "rotation" in tracks:
            image = image.rotate(-sample_keys(tracks["rotation"], clock, duration), resample=Image.Resampling.BICUBIC, expand=False)
        if "opacity" in tracks:
            image = image.copy()
            opacity = sample_keys(tracks["opacity"], clock, duration)
            image.putalpha(image.getchannel("A").point(lambda a: round(a*opacity)))
        _blit(plate, image, scale, ox, oy)
    if abs(pose["rotation"]) > 0.05:
        turned = Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)).rotate(
            -pose["rotation"], resample=Image.Resampling.BICUBIC, expand=False,
        )
        plate = np.asarray(turned, np.float32)
    if pose["opacity"] < 0.999:
        plate *= pose["opacity"]
    plate = _grade(plate, params["grade"])
    plate = _animate_color(plate, params.get("color_tracks") or {}, u, duration)
    plate = _paper(plate, params["paper"], int(u * 30) + 3)
    plate = _grain(plate, params["grain"], u, params.get("grain_std"))
    prev = camera_pose(params["camera"], max(0.0, u - 1 / 60), duration)
    velocity = ((pose["x"] - prev["x"]) * max(theme.fps, 1), (pose["y"] - prev["y"]) * max(theme.fps, 1))
    plate = apply_plate_effects(plate, params.get("effects") or [], u, velocity)
    plate = _paint_overlays(
        plate, theme, [item for item in params["overlays"] if not item.get("parent")], u, duration,
        scene.get("vo") or "", scene.get("style") or VOX, episode_dir, scene_start, episode_time
    )
    frame[y0:y0 + ch, x0:x0 + cw] = plate
    if params.get("show_caption"):
        return _with_caption(theme, frame, scene, u)
    return frame


def _with_caption(theme, frame, scene, u):
    from gilvy.caption import caption
    from gilvy.draw import Ctx, compose

    ctx = Ctx(theme)
    image = Image.fromarray(np.clip(frame, 0, 255).astype(np.uint8), "RGB")
    if theme.scale != 1:
        image = image.resize((theme.width * theme.scale, theme.height * theme.scale), Image.Resampling.BILINEAR)
    ctx.im.paste(image)
    caption(ctx, scene["caption"], scene["key"], u)
    return compose(ctx)


def _content_box(theme) -> tuple[int, int, int, int]:
    x0, y0 = theme.fit.map(0, 0)
    x1, y1 = theme.fit.map(DESIGN_W, DESIGN_H)
    left, top = int(round(x0)), int(round(y0))
    width = max(0, int(round(x1)) - left)
    height = max(0, int(round(y1)) - top)
    left = min(max(0, left), theme.width)
    top = min(max(0, top), theme.height)
    width = min(width, theme.width - left)
    height = min(height, theme.height - top)
    return left, top, width, height


def _camera_at(camera, u, duration):
    t = 0.0 if duration <= 0 else cl(u / duration)
    a, b = camera["from"], camera["to"]
    tracks = camera.get("tracks") or {}
    if "scale" in tracks:
        scale = sample_keys(tracks["scale"], u, duration)
        p = t
    elif camera.get("ease") == "exponential" and a["scale"] > 0 and b["scale"] > 0:
        # Constant relative rate: scale(t) = s0 * (s1/s0)^t. Linear scale reads ~0.7–0.85× this.
        scale = a["scale"] * (b["scale"] / a["scale"]) ** t
        p = t
    else:
        p = _apply_ease(camera["ease"], t)
        scale = a["scale"] + (b["scale"] - a["scale"]) * p
    x = sample_keys(tracks["x"], u, duration) if "x" in tracks else a["x"] + (b["x"] - a["x"]) * p
    y = sample_keys(tracks["y"], u, duration) if "y" in tracks else a["y"] + (b["y"] - a["y"]) * p
    return scale, x, y


def camera_pose(camera, u, duration) -> dict:
    """Scale, pan, and the optional rotation/opacity tracks."""
    scale, x, y = _camera_at(camera, u, duration)
    tracks = camera.get("tracks") or {}
    rotation = sample_keys(tracks["rotation"], u, duration) if "rotation" in tracks else 0.0
    opacity = sample_keys(tracks["opacity"], u, duration) if "opacity" in tracks else 1.0
    return {"scale": scale, "x": x, "y": y, "rotation": rotation, "opacity": opacity}


def _apply_ease(name: str, p: float) -> float:
    if name == "ease-out":
        return eo(p)
    if name == "ease-in-out":
        return eio(p)
    if name in ("linear", "exponential"):
        return cl(p)
    return apply_ease(name, p)


def _load(path: Path) -> Image.Image:
    path = path.resolve()
    if not path.is_file():
        raise GilvyError(
            f"missing image asset: {path}. Run `gilvy assets` on the episode and generate this file before rendering."
        )
    key = (str(path), path.stat().st_mtime_ns)
    image = _CACHE.get(key)
    if image is None:
        try:
            with Image.open(path) as opened:
                image = opened.convert("RGBA")
        except OSError as exc:
            raise GilvyError(f"could not read image asset: {path}") from exc
        _CACHE[key] = image
    return image


def _blit(plate: np.ndarray, image: Image.Image, scale: float, ox: float, oy: float) -> None:
    """Zoom by `scale` only. Pan shifts the window and never raises the zoom.

    The previous blit used max(scale, pan margin), so a pan larger than the
    zoom froze or shrank the scale and the shift was measured as almost nothing.
    """
    ch, cw = plate.shape[:2]
    # Tracks may pull down to 0.5. A floor of 1 drew those pulls as a hold, so a
    # 7% zoom-out never reached the detector. From/to shorthand still rejects
    # scale below 1 before this blit runs.
    scale = max(0.5, float(scale))
    cover = max(cw / max(1, image.width), ch / max(1, image.height))
    # A plate smaller than the frame is scaled up to cover it. A plate that
    # already covers the frame keeps its extra pixels as pan and zoom margin.
    # Cover-fitting that larger plate used to shrink the margin away, and the
    # pan then repeated the edge.
    base = cover if cover > 1.0 else 1.0
    draw = base * scale
    sw = max(1, int(round(image.width * draw)))
    sh = max(1, int(round(image.height * draw)))
    resized = np.asarray(image.resize((sw, sh), Image.Resampling.BILINEAR))
    left = int(round((sw - cw) / 2 - ox))
    top = int(round((sh - ch) / 2 - oy))
    pad_l = max(0, -left)
    pad_t = max(0, -top)
    pad_r = max(0, left + cw - sw)
    pad_b = max(0, top + ch - sh)
    if pad_l or pad_t or pad_r or pad_b:
        resized = np.pad(resized, ((pad_t, pad_b), (pad_l, pad_r), (0, 0)), mode="edge")
        left += pad_l
        top += pad_t
    crop = resized[top:top + ch, left:left + cw]
    src = np.asarray(crop, np.float32)
    alpha = src[:, :, 3:4] / 255.0
    plate[:] = plate * (1.0 - alpha) + src[:, :, :3] * alpha


def _grade(plate: np.ndarray, grade: str) -> np.ndarray:
    if grade == "none":
        return plate
    r, g, b = plate[:, :, 0], plate[:, :, 1], plate[:, :, 2]
    if grade == "sepia":
        # Round 2 poles: darker shadow #1a1411, warmer highlight #ead0b3.
        luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
        shadow = np.array([0x1A, 0x14, 0x11], np.float32)
        highlight = np.array([0xEA, 0xD0, 0xB3], np.float32)
        return shadow + (highlight - shadow) * luma[..., None]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # Measured ref2 paper poles are about #131313 and #dadada.
    paper = 19.0 + y / 255.0 * (218.0 - 19.0)
    return np.repeat(paper[:, :, None], 3, axis=2)


def _paper(plate: np.ndarray, amount: float, seed: int) -> np.ndarray:
    if amount <= 0:
        return plate
    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    ch, cw = plate.shape[:2]
    field = rng.random((max(1, ch // 8), max(1, cw // 8))).astype(np.float32)
    fiber = np.array(Image.fromarray((field * 255).astype(np.uint8)).resize((cw, ch), Image.Resampling.BILINEAR), np.float32)
    fiber = 210 + fiber * 0.18
    mix = cl(amount) * 0.28
    return plate * (1 - mix) + fiber[:, :, None] * mix


def _grain(plate: np.ndarray, amount: float, u: float, grain_std: float | None = None) -> np.ndarray:
    if grain_std is not None and grain_std > 0:
        sigma = float(grain_std) / _GRAIN_HF_GAIN
    elif amount <= 0:
        return plate
    else:
        sigma = amount * 18.0
    seed = (int(round(u * 480.0)) * 997 + 13) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((plate.shape[0], plate.shape[1], 1)).astype(np.float32)
    return np.clip(plate + noise * sigma, 0, 255)


def high_frequency_std(plate: np.ndarray) -> float:
    """Std of the picture minus a 1.5px blur. This is the inventory grain measure."""
    gray = plate.mean(axis=2) if plate.ndim == 3 else np.asarray(plate, np.float32)
    image = Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8))
    blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=1.5)), np.float32)
    return float((np.asarray(image, np.float32) - blurred).std())


def _animate_color(plate: np.ndarray, tracks: dict, u: float, duration: float) -> np.ndarray:
    """Hue, saturation, and brightness after the static plate grade.

    The sepia or paper grade still runs first. These tracks are a second grade
    that can move on its own keys.
    """
    if not tracks:
        return plate
    hue = sample_keys(tracks["hue"], u, duration) if "hue" in tracks else 0.0
    sat = sample_keys(tracks["sat"], u, duration) if "sat" in tracks else 1.0
    bright = sample_keys(tracks["bright"], u, duration) if "bright" in tracks else 1.0
    if abs(hue) < 1e-3 and abs(sat - 1.0) < 1e-3 and abs(bright - 1.0) < 1e-3:
        return plate
    r, g, b = plate[:, :, 0], plate[:, :, 1], plate[:, :, 2]
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    chroma = plate - luma[:, :, None]
    if abs(hue) >= 1e-3:
        chroma = _rotate_chroma(chroma, hue)
    return np.clip(luma[:, :, None] * bright + chroma * sat, 0, 255)


def _rotate_chroma(chroma: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate RGB around the gray axis. That is a hue change at constant luma."""
    angle = math.radians(degrees)
    c, s = math.cos(angle), math.sin(angle)
    axis = 1.0 / math.sqrt(3.0)
    # Rodrigues: c*I + s*[axis]_x + (1-c)*axis*axis^T
    one_c = 1.0 - c
    ax = axis
    matrix = np.array([
        [c + one_c * ax * ax, one_c * ax * ax - s * ax, one_c * ax * ax + s * ax],
        [one_c * ax * ax + s * ax, c + one_c * ax * ax, one_c * ax * ax - s * ax],
        [one_c * ax * ax - s * ax, one_c * ax * ax + s * ax, c + one_c * ax * ax],
    ], np.float32)
    flat = chroma.reshape(-1, 3)
    return (flat @ matrix.T).reshape(chroma.shape)


def match_warp(image: np.ndarray, scale: float, ox: float, oy: float, rotation: float) -> np.ndarray:
    """Scale, shift, and rotate a finished frame about its centre.

    A match cut uses this on the outgoing shot so a shape can land on the
    incoming shot's position. The next frame is the incoming shot, unblended.
    """
    height, width = image.shape[:2]
    picture = Image.fromarray(np.clip(image, 0, 255).astype(np.uint8))
    scale = max(0.2, float(scale))
    if abs(scale - 1.0) >= 1e-3:
        picture = picture.resize(
            (max(2, int(round(width * scale))), max(2, int(round(height * scale)))),
            Image.Resampling.BILINEAR,
        )
    canvas = Image.new("RGB", (width, height))
    left = int(round((width - picture.size[0]) / 2 + ox))
    top = int(round((height - picture.size[1]) / 2 + oy))
    canvas.paste(picture, (left, top))
    if abs(rotation) > 0.05:
        canvas = canvas.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=False)
    return np.asarray(canvas, np.float32)


def _paint_overlays(plate, theme, overlays, u, duration, vo, style, episode_dir="", scene_start=0, episode_time=None):
    if not overlays:
        return plate
    image = Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(layer)
    x0, y0, _, _ = _content_box(theme)
    for item in overlays:
        start = overlay_start(item, vo, duration, style or VOX)
        time = track_time(item, u, scene_start, episode_time)
        _draw_overlay(pen, layer, item, time, start, theme, x0, y0, episode_dir)
    image = Image.alpha_composite(image, layer)
    return np.asarray(image.convert("RGB"), np.float32)


def _draw_overlay(pen, layer, item, u, start, theme, x0, y0, episode_dir=""):
    kind = item["kind"]
    if u < start:
        return
    if kind == "text":
        _draw_text(layer, item, u, start, theme, x0, y0)
        return
    if kind in ("headline", "tag", "chip", "card"):
        _draw_vox_overlay(pen, layer, item, u, start, theme, x0, y0, episode_dir)
        return
    duration = float(item.get("duration") or 0.4)
    progress = cl((u - start) / duration) if duration else 1.0
    progress = apply_ease(item.get("ease") or "linear", progress)
    color = item["color"]
    if kind == "strike":
        origin = _map(theme, item["x"], item["y"], x0, y0)
        draw_strike(pen, (origin[0], origin[1], origin[0] + item["w"], origin[1] + item["h"]), progress, color)
        return
    if kind == "mask":
        origin = _map(theme, item["x"], item["y"], x0, y0)
        draw_mask(pen, origin, (item["w"] * theme.fit.scale, item["h"] * theme.fit.scale), progress)
        return
    if kind == "stamp":
        _draw_stamp(layer, item, progress, theme, x0, y0)
        return
    if kind == "highlighter":
        width = item["w"] * theme.fit.scale * progress
        origin = _map(theme, item["x"], item["y"], x0, y0)
        height = max(1, item["h"] * theme.fit.scale)
        pen.rectangle([origin[0], origin[1], origin[0] + width, origin[1] + height], fill=(*color, 210))
    elif kind == "circle":
        c = _map(theme, item["cx"], item["cy"], x0, y0)
        r = item["r"] * theme.fit.scale
        box = [c[0] - r, c[1] - r, c[0] + r, c[1] + r]
        pen.arc(box, start=-90, end=-90 + 360 * progress, fill=(*color, 230), width=max(1, int(round(item["width"] * theme.fit.scale))))
    elif kind == "arrow":
        points = [_map(theme, x, y, x0, y0) for x, y in item["points"]]
        partial = _partial(points, progress)
        if len(partial) >= 2:
            pen.line(partial, fill=(*color, 230), width=max(1, int(round(item["width"] * theme.fit.scale))))


def _draw_text(layer, item, u, start, theme, x0, y0):
    local = u - start
    hold = float(item["hold"])
    if item["entrance"] == "typewriter":
        appear = 1.0
    elif item["entrance"] == "fade":
        fade_s = float(item.get("fade", 0.45))
        appear = 1.0 if fade_s <= 0 else cl(local / fade_s)
    elif item["entrance"] == "slide":
        appear = eo(cl(local / 0.28))
    else:
        appear = cl(local / 0.16)
    if local > hold:
        appear *= 1.0 - cl((local - hold) / 0.25)
    if appear <= 0:
        return
    words = [word for word in item["text"].split(" ") if word] or [item["text"]]
    if item["entrance"] == "typewriter":
        words = words[:typewriter_count(item["text"], local, float(item.get("word_seconds") or 0.2))]
        if not words:
            return
    lines = [" ".join(words)] if item.get("layout") == "line" else words
    anchor = _map(theme, item["x"], item["y"], x0, y0)
    slide = 0.0
    if item["entrance"] == "slide":
        slide = (1.0 - appear) * 36 * theme.fit.scale
    pop = 1.0
    if item["entrance"] == "pop":
        p = cl(local / 0.20)
        if item.get("overshoot") is None:
            pop = 0.86 + 0.22 * eo(p)
            if p > 0.7:
                pop = 1.0 + (pop - 1.0) * (1.0 - cl((p - 0.7) / 0.3))
        else:
            # Peak is 1 + overshoot, then it settles to 1. The default path above
            # stays put so existing pops do not change size.
            overshoot = float(item["overshoot"])
            peak = 1.0 + overshoot
            pop = (1.0 - overshoot) + (peak - (1.0 - overshoot)) * eo(p)
            if p > 0.7:
                pop = 1.0 + (peak - 1.0) * (1.0 - cl((p - 0.7) / 0.3))
    chip, left, top = _stack_text(layer.size, lines, item, theme, anchor, slide, pop, int(appear * 255))
    _stamp(layer, chip, left, top)


def _stack_text(frame_size, lines, item, theme, anchor, slide, pop, alpha):
    """One word per line, shrunk until the block sits inside the frame."""
    width, height = frame_size
    margin = max(8, int(round(48 * theme.fit.scale)))
    safe_w = max(16, width - 2 * margin)
    safe_h = max(16, height - 2 * margin)
    size_px = max(8, int(round(item["size"] * theme.fit.scale)))
    font = _font(item["font"], size_px, theme.fonts())
    gap = 0
    blocks = []
    for _ in range(24):
        font = _font(item["font"], size_px, theme.fonts())
        pen = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        blocks = []
        for line in lines:
            box = pen.textbbox((0, 0), line, font=font)
            blocks.append((line, box[2] - box[0], box[3] - box[1], box))
        gap = max(0, int(round(size_px * 0.12)))
        block_w = max(block[1] for block in blocks)
        block_h = sum(block[2] for block in blocks) + gap * (len(blocks) - 1)
        if block_w <= safe_w and block_h <= safe_h:
            break
        size_px = max(8, int(size_px * 0.9))
        if size_px == 8:
            break
    block_w = max(block[1] for block in blocks) + 8
    block_h = sum(block[2] for block in blocks) + gap * (len(blocks) - 1) + 8
    chip = Image.new("RGBA", (max(1, block_w), max(1, block_h)), (0, 0, 0, 0))
    pen = ImageDraw.Draw(chip)
    y = 4
    for line, tw, th, box in blocks:
        x = 4 + (block_w - 8 - tw) / 2
        pen.text((x - box[0], y - box[1]), line, font=font, fill=(*item["color"], alpha))
        y += th + gap
    if abs(pop - 1.0) > 0.02:
        chip = chip.resize((max(1, int(chip.width * pop)), max(1, int(chip.height * pop))), Image.Resampling.BILINEAR)
    left = int(round(anchor[0] - chip.width / 2 + slide))
    top = int(round(anchor[1] - chip.height / 2))
    left = min(max(margin, left), max(margin, width - margin - chip.width))
    top = min(max(margin, top), max(margin, height - margin - chip.height))
    return chip, left, top


def _draw_stamp(layer, item, progress, theme, x0, y0):
    """A stamp settles from a larger, tilted mark down to the authored size."""
    pop = 1.35 - 0.35 * progress
    angle = -8 * (1 - progress)
    chip = Image.new("RGBA", (max(8, int(item["w"])), max(8, int(item["h"]))), (0, 0, 0, 0))
    pen = ImageDraw.Draw(chip)
    pen.text((8, 8), item.get("text") or "STAMP", fill=(*item["color"], 255))
    chip = chip.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    chip = chip.resize((max(1, int(chip.width * pop)), max(1, int(chip.height * pop))), Image.Resampling.BILINEAR)
    origin = _map(theme, item["x"], item["y"], x0, y0)
    _stamp(layer, chip, int(origin[0]), int(origin[1]))


def _stamp(base: Image.Image, chip: Image.Image, left: int, top: int) -> None:
    canvas = Image.new("RGBA", base.size, (0, 0, 0, 0))
    canvas.paste(chip, (left, top))
    stamped = Image.alpha_composite(base, canvas)
    base.paste(stamped)


def _partial(points, progress):
    if progress >= 1:
        return [tuple(p) for p in points]
    lengths = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    total = sum(lengths) or 1.0
    budget = total * progress
    out = [tuple(points[0])]
    for i, length in enumerate(lengths):
        if budget >= length:
            out.append(tuple(points[i + 1]))
            budget -= length
            continue
        t = budget / length if length else 0
        a, b = points[i], points[i + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
        break
    return out


def _map(theme, x, y, x0, y0):
    px, py = theme.fit.map(float(x), float(y))
    return px - x0, py - y0


def _font(name: str, size: int, font_dir: str) -> ImageFont.FreeTypeFont:
    key = (name, size, font_dir)
    font = _FONTS.get(key)
    if font is not None:
        return font
    if name == "serif":
        path = Path(__file__).resolve().parent / "fonts" / "LiberationSerif-Regular.ttf"
    else:
        path = Path(font_dir) / "Poppins-Medium.ttf"
    font = ImageFont.truetype(str(path), size)
    _FONTS[key] = font
    return font


def _overlay_text(item: dict, index: int) -> str:
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        raise EpisodeError(f"scene {index}: this overlay needs text")
    return text.strip()


def _backdrop(value, index: int) -> str:
    if value is None:
        return ""
    if value != "cork":
        raise EpisodeError(f"scene {index}: backdrop must be cork")
    return "cork"


def _draw_vox_overlay(pen, layer, item, u, start, theme, x0, y0, episode_dir):
    del pen
    origin = _map(theme, item.get("x", 0), item.get("y", 0), x0, y0)
    scale = theme.fit.scale
    fonts = theme.fonts()
    if item["kind"] == "headline":
        draw_headline(
            layer, item["text"], origin, max(8, int(round(item["size"] * scale))),
            item["color"], str(serif_path()),
        )
    elif item["kind"] == "tag":
        draw_tag(
            layer, item["text"], origin, max(8, int(round(item["size"] * scale))),
            item["fill"], item["ink"], str(sans_path(fonts)),
        )
    elif item["kind"] == "chip":
        draw_chip(
            layer, item["text"], item["highlight"], origin,
            max(8, int(round(item["size"] * scale))),
            item["color"], item["fill"], str(sans_path(fonts)),
        )
    elif item["kind"] == "card":
        path = Path(episode_dir) / item["src"]
        if not path.is_file():
            raise GilvyError(f"missing card image: {path}")
        with Image.open(path) as opened:
            card = opened.convert("RGB")
        draw_card(
            layer, card, origin,
            (max(8, int(round(item["w"] * scale))), max(8, int(round(item["h"] * scale)))),
            item["tilt"], item["shadow"],
        )


def _layers(raw: dict, index: int) -> list[dict]:
    layers = raw.get("layers")
    image = raw.get("image")
    if layers is None and isinstance(image, str):
        layers = [{"src": image, "depth": 1.0}]
    if (not layers) and raw.get("backdrop") == "cork":
        return []
    if not isinstance(layers, list) or not layers:
        raise EpisodeError(f"scene {index}: image scenes need image: or a layers list")
    out = []
    ids = set()
    for i, layer in enumerate(layers):
        if isinstance(layer, str):
            layer = {"src": layer}
        if not isinstance(layer, dict) or not isinstance(layer.get("src"), str) or not layer["src"].strip():
            raise EpisodeError(f"scene {index}: layer {i + 1} needs a src path")
        if layer["src"].startswith(("/", "http:", "https:")) and not layer["src"].startswith("/"):
            raise EpisodeError(f"scene {index}: layer src must be a local file")
        depth = layer.get("depth", i / max(1, len(layers) - 1) if len(layers) > 1 else 1.0)
        depth = _unit(depth, index, f"layer {i + 1} depth")
        prompt = layer.get("prompt", "")
        if not isinstance(prompt, str):
            raise EpisodeError(f"scene {index}: layer prompt must be a string")
        parsed = {"src": layer["src"], "depth": depth, "prompt": prompt.strip()}
        parsed.update(parse_fragment(layer, index))
        if "id" in parsed:
            if parsed["id"] in ids:
                raise EpisodeError(f"scene {index}: duplicate layer id {parsed['id']}")
            ids.add(parsed["id"])
        if raw.get("composition") == "collage" and ("id" not in parsed or "role" not in parsed):
            raise EpisodeError(f"scene {index}: collage layers need id and role")
        out.append(parsed)
    return out


def _camera(raw, index: int, rules: dict) -> dict:
    raw = {} if raw is None else raw
    if not isinstance(raw, dict):
        raise EpisodeError(f"scene {index}: camera must be a mapping")
    ease = raw.get("ease", rules["default_ease"])
    if not isinstance(ease, str) or ease not in _EASE:
        raise EpisodeError(f"scene {index}: camera.ease must be linear, ease-out, ease-in-out, exponential, or a track ease")
    preset = float(rules.get("scale_max", 2.4))
    limit = _num(raw.get("scale_max", preset), index, "camera.scale_max", preset, 4)
    if not math.isfinite(limit) or not preset <= limit <= 4.0:
        raise EpisodeError(f"scene {index}: scale_max must be from {preset} to 4")
    return {
        "ease": ease,
        "scale_max": limit,
        "from": _point(raw.get("from") or {}, index, "from", limit),
        "to": _point(raw.get("to") or {}, index, "to", limit),
        "tracks": parse_tracks(raw.get("tracks"), index, limit),
    }


def _point(raw, index: int, name: str, scale_max: float = 2.4) -> dict:
    if not isinstance(raw, dict):
        raise EpisodeError(f"scene {index}: camera.{name} must be a mapping")
    scale = raw.get("scale", 1.0)
    x = raw.get("x", 0.0)
    y = raw.get("y", 0.0)
    for label, value, lo, hi in (("scale", scale, 1.0, scale_max), ("x", x, -400, 400), ("y", y, -700, 700)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= float(value) <= hi:
            raise EpisodeError(f"scene {index}: camera.{name}.{label} must be from {lo} to {hi}")
    return {"scale": float(scale), "x": float(x), "y": float(y)}


def _fade_seconds(value, index: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= float(value) <= 2:
        raise EpisodeError(f"scene {index}: text_fade_s must be seconds from 0 to 2")
    return float(value)


def _overlays(raw, index: int, rules: dict, fade_s: float) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > 8:
        raise EpisodeError(f"scene {index}: overlays must be a list of at most 8 items",
                           field=f"scenes[{index - 1}].overlays")
    out = []
    for i, item in enumerate(raw):
        try:
            out.extend(_parse_overlays([item], index, rules, fade_s))
        except EpisodeError as exc:
            suffix = f".{exc.field}" if exc.field else ""
            raise EpisodeError(str(exc), field=f"scenes[{index - 1}].overlays[{i}]{suffix}") from exc
    return out


def _parse_overlays(raw, index: int, rules: dict, fade_s: float) -> list[dict]:
    if not isinstance(raw, list):
        raise EpisodeError(f"scene {index}: overlays must be a list")
    if len(raw) > 8:
        raise EpisodeError(f"scene {index}: at most 8 overlays")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("kind"), str) or item.get("kind") not in _OVERLAYS:
            raise EpisodeError(
                f"scene {index}: overlay {i + 1} kind must be text, headline, tag, chip, card, highlighter, circle, arrow, strike, mask, or stamp"
            )
        kind = item["kind"]
        parsed = {"kind": kind, "color": _color(item.get("color"), index, MEASURED_RED if kind != "highlighter" else (185, 168, 10))}
        if item.get("parent") is not None:
            if not isinstance(item["parent"], str) or not item["parent"].strip():
                raise EpisodeError(f"scene {index}: invalid overlay parent")
            parsed["parent"] = item["parent"]
        if item.get("clock", "scene") not in ("scene", "episode"):
            raise EpisodeError(f"scene {index}: overlay clock must be scene or episode")
        if "clock" in item: parsed["clock"] = item["clock"]
        if "event_id" in item:
            event_id = item["event_id"]
            if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 128:
                raise EpisodeError(f"scene {index}: event_id must be nonempty text up to 128 characters", field="event_id")
            if parsed.get("clock") != "episode" or not item.get("sfx"):
                raise EpisodeError(f"scene {index}: event_id requires an episode-clock SFX", field="event_id")
            parsed["event_id"] = event_id
        if parsed.get("clock") == "episode" and item.get("at") is None:
            raise EpisodeError(f"scene {index}: episode-clock overlay requires explicit at")
        if item.get("at") is not None:
            parsed["at"] = _num(item["at"], index, "at", 0, 600 if parsed.get("clock") == "episode" else 30)
        elif item.get("keyword") is not None:
            if not isinstance(item["keyword"], str) or not item["keyword"].strip():
                raise EpisodeError(f"scene {index}: overlay keyword must be a word from the spoken line")
            parsed["keyword"] = item["keyword"]
        else:
            parsed["at"] = 0.35
        if kind == "text":
            if not isinstance(item.get("text"), str) or not item["text"].strip():
                raise EpisodeError(f"scene {index}: text overlay needs text")
            entrance = item.get("entrance", rules["text_entrance"])
            font = item.get("font", "serif" if rules is RULES[HISTORY] else "sans")
            if not isinstance(entrance, str) or not isinstance(font, str) or entrance not in _ENTRANCES or font not in _FONTS_NAMED:
                raise EpisodeError(
                    f"scene {index}: text entrance must be fade, pop, slide, or typewriter; font must be serif or sans"
                )
            if item.get("layout", "stack") not in ("stack", "line"):
                raise EpisodeError(f"scene {index}: text layout must be stack or line")
            if "layout" in item: parsed["layout"] = item["layout"]
            parsed.update(text=item["text"], entrance=entrance, font=font,
                          size=_num(item.get("size", rules["text_size"]), index, "size", 12, 480),
                          fade=_fade_seconds(item.get("text_fade_s", fade_s), index),
                          hold=_seconds(item.get("hold", 1.6), index, "hold"),
                          x=_num(item.get("x", DESIGN_W / 2), index, "x", -200, 1400),
                          y=_num(item.get("y", 780), index, "y", -200, 2100),
                          word_seconds=_num(item.get("word_seconds", 0.2), index, "word_seconds", 0.04, 2))
            if item.get("overshoot") is not None:
                parsed["overshoot"] = _num(item.get("overshoot"), index, "overshoot", 0, 0.8)
        elif kind == "headline":
            parsed.update(
                text=_overlay_text(item, index),
                size=_num(item.get("size", 108), index, "size", 24, 240),
                x=_num(item.get("x", 80), index, "x", -200, 1400),
                y=_num(item.get("y", 280), index, "y", -200, 2100),
                color=_color(item.get("color"), index, PALETTE["white"]),
            )
        elif kind == "tag":
            parsed.update(
                text=_overlay_text(item, index),
                size=_num(item.get("size", 36), index, "size", 16, 120),
                x=_num(item.get("x", 80), index, "x", -200, 1400),
                y=_num(item.get("y", 220), index, "y", -200, 2100),
                fill=_color(item.get("fill"), index, PALETTE["orange"]),
                ink=_color(item.get("color"), index, PALETTE["white"]),
            )
        elif kind == "chip":
            text = _overlay_text(item, index)
            highlight = item.get("highlight")
            if not isinstance(highlight, str) or highlight not in text.split(" "):
                raise EpisodeError(f"scene {index}: chip highlight must be one whole word of the text")
            parsed.update(
                text=text,
                highlight=highlight,
                size=_num(item.get("size", 42), index, "size", 16, 96),
                x=_num(item.get("x", 80), index, "x", -200, 1400),
                y=_num(item.get("y", 1500), index, "y", -200, 2100),
                color=_color(item.get("color"), index, PALETTE["white"]),
                fill=_color(item.get("fill"), index, PALETTE["red"]),
            )
        elif kind == "card":
            src = item.get("src")
            if not isinstance(src, str) or not src.strip() or src.startswith(("http:", "https:")):
                raise EpisodeError(f"scene {index}: card overlay needs a local src")
            parsed.update(
                src=src.strip(),
                x=_num(item.get("x", 140), index, "x", -200, 1400),
                y=_num(item.get("y", 480), index, "y", -200, 2100),
                w=_num(item.get("w", 420), index, "w", 40, 1000),
                h=_num(item.get("h", 560), index, "h", 40, 1200),
                tilt=_num(item.get("tilt", 8), index, "tilt", -18, 18),
                shadow=_num(item.get("shadow", 0.55), index, "shadow", 0, 1),
            )
        elif kind == "highlighter":
            parsed.update(duration=_seconds(item.get("duration", 0.40), index, "duration"),
                          ease=_overlay_ease(item.get("ease"), index),
                          x=_num(item.get("x"), index, "x", -200, 1400),
                          y=_num(item.get("y"), index, "y", -200, 2100),
                          w=_num(item.get("w"), index, "w", 1, 1200),
                          h=_num(item.get("h"), index, "h", 1, 400))
        elif kind == "circle":
            parsed.update(duration=_seconds(item.get("duration", 0.80), index, "duration"),
                          ease=_overlay_ease(item.get("ease"), index),
                          cx=_num(item.get("cx", item.get("x")), index, "cx", -200, 1400),
                          cy=_num(item.get("cy", item.get("y")), index, "cy", -200, 2100),
                          r=_num(item.get("r"), index, "r", 4, 800),
                          width=_num(item.get("width", 8), index, "width", 1, 40))
        elif kind == "arrow":
            points = item.get("points")
            if (not isinstance(points, list) or len(points) < 2
                    or any(not isinstance(p, (list, tuple)) or len(p) != 2 for p in points)):
                raise EpisodeError(f"scene {index}: arrow overlay needs at least two points")
            parsed["points"] = [(_num(p[0], index, "x", -200, 1400), _num(p[1], index, "y", -200, 2100)) for p in points]
            parsed["duration"] = _seconds(item.get("duration", 0.50), index, "duration")
            parsed["width"] = _num(item.get("width", 8), index, "width", 1, 40)
            parsed["ease"] = _overlay_ease(item.get("ease"), index)
        if kind in ("strike", "mask", "stamp"):
            parsed.update(
                duration=_seconds(item.get("duration", 0.4), index, "duration"),
                ease=_overlay_ease(item.get("ease"), index),
                x=_num(item.get("x", 80), index, "x", -200, 1400),
                y=_num(item.get("y", 400), index, "y", -200, 2100),
                w=_num(item.get("w", 400), index, "w", 4, 1200),
                h=_num(item.get("h", 80), index, "h", 4, 800),
                text=item.get("text") if isinstance(item.get("text"), str) else "STAMP",
            )
        sfx = item.get("sfx")
        if sfx is not None:
            if not isinstance(sfx, str):
                raise EpisodeError(f"scene {index}: sfx must be a cue name")
            parsed["sfx"] = sfx
        out.append(parsed)
    return out


def _metrics_or_raise(camera, index, style, duration):
    metrics = camera_metrics(camera, duration)
    if metrics["static"]:
        raise EpisodeError(
            f"scene {index}: camera from and to are the same. {style} image plates have to push, pull, or pan."
        )


def _grain_std(value, index: int) -> float | None:
    if value is None:
        return None
    number = _num(value, index, "grain_std", 0, 80)
    return number


def _color_tracks(raw, index: int) -> dict:
    """Hue, saturation, and brightness tracks. Independent of grade: none/sepia/paper."""
    if raw is None:
        return {}
    tracks = raw.get("tracks") if isinstance(raw, dict) else None
    if not isinstance(tracks, list):
        raise EpisodeError(f"scene {index}: color.tracks must be a list")
    bounds = {"hue": (-180.0, 180.0), "sat": (0.0, 3.0), "bright": (0.0, 3.0)}
    out = {}
    for position, item in enumerate(tracks):
        if not isinstance(item, dict):
            raise EpisodeError(f"scene {index}: a color track must be a mapping")
        prop = item.get("property")
        if not isinstance(prop, str) or prop not in bounds:
            raise EpisodeError(f"scene {index}: color property must be hue, sat, or bright",
                               field=f"scenes[{index - 1}].color.tracks[{position}].property")
        keys = item.get("keys")
        if not isinstance(keys, list) or len(keys) < 2:
            raise EpisodeError(f"scene {index}: color track {prop} needs at least two keys")
        lo, hi = bounds[prop]
        built = []
        for key in keys:
            if not isinstance(key, dict):
                raise EpisodeError(f"scene {index}: a color key must be a mapping")
            try:
                t, v = float(key["t"]), float(key["v"])
            except (KeyError, TypeError, ValueError) as exc:
                raise EpisodeError(f"scene {index}: a color key needs numeric t and v") from exc
            if not math.isfinite(t) or not 0 <= t <= 30:
                raise EpisodeError(f"scene {index}: color key t must be seconds from 0 to 30")
            if not math.isfinite(v) or not lo <= v <= hi:
                raise EpisodeError(f"scene {index}: {prop} key must be from {lo} to {hi}")
            ease = key.get("ease") or "linear"
            if ease not in EASES:
                raise EpisodeError(f"scene {index}: color ease must be a track ease")
            built.append({"t": t, "v": v, "ease": ease})
        built.sort(key=lambda row: row["t"])
        out[prop] = built
    return out


def _match_tracks(raw, index: int) -> dict:
    """Scale, x, y, and rotation that align the outgoing frame onto the next shot."""
    if raw is None:
        raw = {}
    tracks = raw.get("tracks") if isinstance(raw, dict) else None
    if tracks is None:
        raise EpisodeError(f"scene {index}: a match cut needs match.tracks")
    parsed = parse_tracks(tracks, index, 4.0)
    extra = set(parsed) - {"scale", "x", "y", "rotation"}
    if extra:
        raise EpisodeError(f"scene {index}: match tracks must be scale, x, y, or rotation")
    if not parsed:
        raise EpisodeError(f"scene {index}: a match cut needs match.tracks")
    return parsed


def _unit(value, index, name) -> float:
    number = _num(value, index, name, 0, 1)
    return number


def _overlay_ease(value, index: int) -> str:
    name = "linear" if value is None else str(value)
    if name not in EASES or name == "cubic-bezier":
        raise EpisodeError(f"scene {index}: overlay ease must be a named track ease")
    return name


def _seconds(value, index, name) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 30:
        raise EpisodeError(f"scene {index}: {name} must be seconds from 0 to 30")
    return float(value)


def _num(value, index, name, lo, hi) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not lo <= float(value) <= hi:
        raise EpisodeError(f"scene {index}: {name} must be from {lo} to {hi}", field=name)
    return float(value)


def _color(value, index, default):
    if value is None:
        return default
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        try:
            return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        except ValueError as exc:
            raise EpisodeError(f"scene {index}: color must be #rrggbb or three integers") from exc
    if isinstance(value, (list, tuple)) and len(value) == 3 and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value):
        return (value[0], value[1], value[2])
    raise EpisodeError(f"scene {index}: color must be #rrggbb or three integers")


def zoom_through(outgoing: np.ndarray, incoming: np.ndarray, k: float) -> np.ndarray:
    """Punch/zoom-through: outgoing rushes in and fades, incoming settles down."""
    k = cl(k)
    a = _zoom(outgoing, 1.0 + 0.28 * k)
    b = _zoom(incoming, 1.22 - 0.22 * k)
    return a * (1.0 - k) + b * k


def _zoom(image: np.ndarray, scale: float) -> np.ndarray:
    if abs(scale - 1.0) < 1e-3:
        return image
    height, width = image.shape[:2]
    scaled_w = max(width + 2, int(round(width * scale)))
    scaled_h = max(height + 2, int(round(height * scale)))
    picture = Image.fromarray(np.clip(image, 0, 255).astype(np.uint8))
    picture = picture.resize((scaled_w, scaled_h), Image.Resampling.BILINEAR)
    left = (scaled_w - width) // 2
    top = (scaled_h - height) // 2
    picture = picture.crop((left, top, left + width, top + height))
    return np.asarray(picture, np.float32)
