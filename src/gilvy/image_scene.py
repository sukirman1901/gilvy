"""Image plates for the opt-in vox-explainer and history-story presets.

Drawn at delivery resolution, in the same design space (1080×1920) the house
show uses, then fitted. House episodes never reach this module.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from gilvy.easing import cl, eio, eo
from gilvy.errors import EpisodeError, GilvyError
from gilvy.formats import DESIGN_H, DESIGN_W
from gilvy.presets import HISTORY, PHOTO_PRESETS, RULES, VOX

_CACHE: dict[tuple, Image.Image] = {}
_FONTS: dict[tuple, ImageFont.FreeTypeFont] = {}
_EASE = {"linear", "ease-out", "ease-in-out", "exponential"}
_GRADES = {"none", "sepia", "paper"}
_TRANSITIONS = {"cut", "dissolve", "zoom"}
_OVERLAYS = {"text", "highlighter", "circle", "arrow"}
_ENTRANCES = {"fade", "pop", "slide"}
_FONTS_NAMED = {"serif", "sans"}

# Median of red text pixels on the attached ref3 frame at 5.0s. Antialiased,
# so this is a swatch, not a vector fill recovered from the edit.
MEASURED_RED = (178, 74, 66)


def parse_image_params(raw: dict, index: int, style: str) -> dict:
    """Validate one image scene's extra fields. Paths are not required to exist yet."""
    if style not in PHOTO_PRESETS:
        raise EpisodeError(
            f"scene {index}: type image needs style: vox-explainer or style: history-story. "
            "House episodes keep a still camera and drawn scenes."
        )
    rules = RULES[style]
    params = {}
    layers = _layers(raw, index)
    params["layers"] = layers
    params["camera"] = _camera(raw.get("camera"), index, rules)
    grade = raw.get("grade", rules["default_grade"])
    if grade not in _GRADES:
        raise EpisodeError(f"scene {index}: grade must be none, sepia, or paper")
    params["grade"] = grade
    params["grain"] = _unit(raw.get("grain", rules["default_grain"]), index, "grain")
    params["paper"] = _unit(raw.get("paper", 0.12 if grade == "paper" else 0.0), index, "paper")
    show = raw.get("show_caption", False)
    if not isinstance(show, bool):
        raise EpisodeError(f"scene {index}: show_caption must be true or false")
    params["show_caption"] = show
    kind = raw.get("transition_out", rules["default_transition"])
    if kind not in _TRANSITIONS:
        raise EpisodeError(f"scene {index}: transition_out must be cut, dissolve, or zoom")
    params["transition_out"] = kind
    if kind == "cut":
        seconds = float(raw.get("transition") or 0)
    elif raw.get("transition") is None:
        seconds = 0.30 if kind == "zoom" else max(0.40, float(rules["default_transition_s"] or 0.40))
    else:
        seconds = float(raw["transition"])
    if not math.isfinite(seconds) or not 0 <= seconds <= 1.2:
        raise EpisodeError(f"scene {index}: transition must be seconds from 0 to 1.2")
    params["transition"] = seconds
    prompt = raw.get("prompt", "")
    if not isinstance(prompt, str):
        raise EpisodeError(f"scene {index}: prompt must be a string")
    params["prompt"] = prompt.strip()
    params["text_fade_s"] = _fade_seconds(raw.get("text_fade_s", rules["text_fade_s"]), index)
    params["overlays"] = _overlays(raw.get("overlays") or [], index, rules, params["text_fade_s"])
    _metrics_or_raise(params["camera"], index, style)
    return params


def camera_metrics(camera: dict, duration: float) -> dict:
    """Plate rates. Exponential zoom reports the constant relative %/s a measurement sees."""
    duration = max(float(duration), 1e-6)
    start, end = camera["from"], camera["to"]
    zoom = _zoom_percent(camera, duration)
    pan_x = (end["x"] - start["x"]) / duration
    pan_y = (end["y"] - start["y"]) / duration
    moving = abs(zoom) >= 0.4 or math.hypot(pan_x, pan_y) >= 6.0
    return {
        "ease": camera["ease"],
        "duration": round(duration, 4),
        "zoom_pct_per_s": round(zoom, 4),
        "pan_px_per_s": {"x": round(pan_x, 3), "y": round(pan_y, 3)},
        "static": not moving,
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


def render_image_frame(theme, scene: dict, u: float, duration: float, episode_dir: str) -> np.ndarray:
    """One RGB float32 frame at the theme's delivery size."""
    params = scene["params"]
    frame = np.empty((theme.height, theme.width, 3), np.float32)
    frame[:] = np.array(theme.bg, np.float32)
    x0, y0, cw, ch = _content_box(theme)
    if cw < 2 or ch < 2:
        return frame
    plate = np.zeros((ch, cw, 3), np.float32)
    plate[:] = np.array(theme.bg, np.float32)
    cam = _camera_at(params["camera"], u, duration)
    for layer in params["layers"]:
        gain = 0.25 + 0.75 * float(layer["depth"])
        scale = 1.0 + (cam[0] - 1.0) * gain
        ox = cam[1] * gain * theme.fit.scale
        oy = cam[2] * gain * theme.fit.scale
        span = params["camera"]
        margin_x = max(abs(span["from"]["x"]), abs(span["to"]["x"])) * gain * theme.fit.scale
        margin_y = max(abs(span["from"]["y"]), abs(span["to"]["y"])) * gain * theme.fit.scale
        _blit(plate, _load(Path(episode_dir) / layer["src"]), scale, ox, oy, margin_x, margin_y)
    plate = _grade(plate, params["grade"])
    plate = _paper(plate, params["paper"], int(u * 30) + 3)
    plate = _grain(plate, params["grain"], u)
    plate = _paint_overlays(
        plate, theme, params["overlays"], u, duration, scene.get("vo") or "", scene.get("style") or VOX
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
    if camera.get("ease") == "exponential" and a["scale"] > 0 and b["scale"] > 0:
        # Constant relative rate: scale(t) = s0 * (s1/s0)^t. Linear scale reads ~0.7–0.85× this.
        scale = a["scale"] * (b["scale"] / a["scale"]) ** t
        p = t
    else:
        p = _apply_ease(camera["ease"], t)
        scale = a["scale"] + (b["scale"] - a["scale"]) * p
    return (
        scale,
        a["x"] + (b["x"] - a["x"]) * p,
        a["y"] + (b["y"] - a["y"]) * p,
    )


def _apply_ease(name: str, p: float) -> float:
    if name == "ease-out":
        return eo(p)
    if name == "ease-in-out":
        return eio(p)
    return cl(p)


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


def _blit(plate: np.ndarray, image: Image.Image, scale: float, ox: float, oy: float,
          margin_x: float = 0, margin_y: float = 0) -> None:
    ch, cw = plate.shape[:2]
    scale = max(1.0, float(scale))
    base = max(cw / max(1, image.width), ch / max(1, image.height))
    # Reserve the shot's full pan even when this frame's zoom is 1. The reserve
    # does not grow with the current offset, so the picture actually travels.
    need_x = 1.0 + (2.0 * margin_x / cw if cw else 0.0)
    need_y = 1.0 + (2.0 * margin_y / ch if ch else 0.0)
    draw = base * max(scale, need_x, need_y)
    sw = max(cw + 2, int(math.ceil(image.width * draw)))
    sh = max(ch + 2, int(math.ceil(image.height * draw)))
    resized = image.resize((sw, sh), Image.Resampling.BILINEAR)
    left = int(round((sw - cw) / 2 - ox))
    top = int(round((sh - ch) / 2 - oy))
    left = min(max(0, left), max(0, sw - cw))
    top = min(max(0, top), max(0, sh - ch))
    crop = resized.crop((left, top, min(sw, left + cw), min(sh, top + ch)))
    if crop.size != (cw, ch):
        fitted = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        fitted.paste(crop, (0, 0))
        crop = fitted
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


def _grain(plate: np.ndarray, amount: float, u: float) -> np.ndarray:
    if amount <= 0:
        return plate
    seed = (int(round(u * 480.0)) * 997 + 13) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((plate.shape[0], plate.shape[1], 1)).astype(np.float32)
    return np.clip(plate + noise * (amount * 18.0), 0, 255)


def _paint_overlays(plate, theme, overlays, u, duration, vo, style):
    if not overlays:
        return plate
    image = Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)).convert("RGBA")
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pen = ImageDraw.Draw(layer)
    x0, y0, _, _ = _content_box(theme)
    for item in overlays:
        start = overlay_start(item, vo, duration, style or VOX)
        _draw_overlay(pen, layer, item, u, start, theme, x0, y0)
    image = Image.alpha_composite(image, layer)
    return np.asarray(image.convert("RGB"), np.float32)


def _draw_overlay(pen, layer, item, u, start, theme, x0, y0):
    kind = item["kind"]
    if u < start:
        return
    if kind == "text":
        _draw_text(layer, item, u, start, theme, x0, y0)
        return
    duration = float(item["duration"])
    progress = cl((u - start) / duration) if duration else 1.0
    color = item["color"]
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
    if item["entrance"] == "fade":
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
    lines = [word for word in item["text"].split(" ") if word] or [item["text"]]
    anchor = _map(theme, item["x"], item["y"], x0, y0)
    slide = 0.0
    if item["entrance"] == "slide":
        slide = (1.0 - appear) * 36 * theme.fit.scale
    pop = 1.0
    if item["entrance"] == "pop":
        p = cl(local / 0.20)
        pop = 0.86 + 0.22 * eo(p)
        if p > 0.7:
            pop = 1.0 + (pop - 1.0) * (1.0 - cl((p - 0.7) / 0.3))
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


def _layers(raw: dict, index: int) -> list[dict]:
    layers = raw.get("layers")
    image = raw.get("image")
    if layers is None and isinstance(image, str):
        layers = [{"src": image, "depth": 1.0}]
    if not isinstance(layers, list) or not layers:
        raise EpisodeError(f"scene {index}: image scenes need image: or a layers list")
    out = []
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
        out.append({"src": layer["src"], "depth": depth, "prompt": prompt.strip()})
    return out


def _camera(raw, index: int, rules: dict) -> dict:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise EpisodeError(f"scene {index}: camera must be a mapping")
    ease = raw.get("ease", rules["default_ease"])
    if ease not in _EASE:
        raise EpisodeError(f"scene {index}: camera.ease must be linear, ease-out, ease-in-out, or exponential")
    limit = float(rules.get("scale_max", 1.45))
    return {
        "ease": ease,
        "from": _point(raw.get("from") or {}, index, "from", limit),
        "to": _point(raw.get("to") or {}, index, "to", limit),
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
    if not isinstance(raw, list):
        raise EpisodeError(f"scene {index}: overlays must be a list")
    if len(raw) > 8:
        raise EpisodeError(f"scene {index}: at most 8 overlays")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or item.get("kind") not in _OVERLAYS:
            raise EpisodeError(f"scene {index}: overlay {i + 1} kind must be text, highlighter, circle, or arrow")
        kind = item["kind"]
        parsed = {"kind": kind, "color": _color(item.get("color"), index, MEASURED_RED if kind != "highlighter" else (185, 168, 10))}
        if item.get("at") is not None:
            parsed["at"] = _seconds(item.get("at"), index, "at")
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
            if entrance not in _ENTRANCES or font not in _FONTS_NAMED:
                raise EpisodeError(f"scene {index}: text entrance must be fade, pop, or slide; font must be serif or sans")
            parsed.update(text=item["text"], entrance=entrance, font=font,
                          size=_num(item.get("size", rules["text_size"]), index, "size", 12, 480),
                          fade=_fade_seconds(item.get("text_fade_s", fade_s), index),
                          hold=_seconds(item.get("hold", 1.6), index, "hold"),
                          x=_num(item.get("x", DESIGN_W / 2), index, "x", -200, 1400),
                          y=_num(item.get("y", 780), index, "y", -200, 2100))
        elif kind == "highlighter":
            parsed.update(duration=_seconds(item.get("duration", 0.40), index, "duration"),
                          x=_num(item["x"], index, "x", -200, 1400),
                          y=_num(item["y"], index, "y", -200, 2100),
                          w=_num(item["w"], index, "w", 1, 1200),
                          h=_num(item["h"], index, "h", 1, 400))
        elif kind == "circle":
            parsed.update(duration=_seconds(item.get("duration", 0.80), index, "duration"),
                          cx=_num(item.get("cx", item.get("x")), index, "cx", -200, 1400),
                          cy=_num(item.get("cy", item.get("y")), index, "cy", -200, 2100),
                          r=_num(item["r"], index, "r", 4, 800),
                          width=_num(item.get("width", 8), index, "width", 1, 40))
        else:
            points = item.get("points")
            if not isinstance(points, list) or len(points) < 2:
                raise EpisodeError(f"scene {index}: arrow overlay needs at least two points")
            parsed["points"] = [(_num(p[0], index, "x", -200, 1400), _num(p[1], index, "y", -200, 2100)) for p in points]
            parsed["duration"] = _seconds(item.get("duration", 0.50), index, "duration")
            parsed["width"] = _num(item.get("width", 8), index, "width", 1, 40)
        sfx = item.get("sfx")
        if sfx is not None:
            if not isinstance(sfx, str):
                raise EpisodeError(f"scene {index}: sfx must be a cue name")
            parsed["sfx"] = sfx
        out.append(parsed)
    return out


def _metrics_or_raise(camera, index, style):
    # Use a representative 2.5s plate so a frozen camera fails at load, before render.
    metrics = camera_metrics(camera, 2.5)
    if metrics["static"]:
        raise EpisodeError(
            f"scene {index}: camera from and to are the same. {style} image plates have to push, pull, or pan."
        )


def _unit(value, index, name) -> float:
    number = _num(value, index, name, 0, 1)
    return number


def _seconds(value, index, name) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 30:
        raise EpisodeError(f"scene {index}: {name} must be seconds from 0 to 30")
    return float(value)


def _num(value, index, name, lo, hi) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not lo <= float(value) <= hi:
        raise EpisodeError(f"scene {index}: {name} must be from {lo} to {hi}")
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
