"""Explicitly sized editorial fragments, sharing the existing product projection kernel."""
import math

import numpy as np
from PIL import Image, ImageColor, ImageOps

from gilvy.errors import EpisodeError
from gilvy.keyframes import parse_tracks, sample_keys

ROLES = {"background", "texture", "subject", "object", "photo", "paper", "foreground"}


def parse_fragment(layer, index):
    extra = {}
    for key in ("id", "role", "alpha", "clock", "placement"):
        if key in layer:
            extra[key] = layer[key]
    identifier = extra.get("id")
    if identifier is not None and (not isinstance(identifier, str) or not identifier.strip()):
        raise EpisodeError(f"scene {index}: layer id must be nonempty text")
    if not isinstance(extra.get("role", "object"), str) or extra.get("role", "object") not in ROLES:
        raise EpisodeError(f"scene {index}: unknown collage asset role")
    if extra.get("alpha", "any") not in ("any", "transparent", "opaque"):
        raise EpisodeError(f"scene {index}: alpha must be any, transparent, or opaque")
    if extra.get("clock", "scene") not in ("scene", "episode"):
        raise EpisodeError(f"scene {index}: layer clock must be scene or episode")
    if "placement" in extra:
        if identifier is None:
            raise EpisodeError(f"scene {index}: a placed layer needs a stable id")
        raw = extra["placement"]
        allowed = {"width", "height", "x", "y", "scale", "rotation", "opacity", "fit", "matte", "padding"}
        if not isinstance(raw, dict) or set(raw)-allowed:
            raise EpisodeError(f"scene {index}: invalid placement fields")
        values = {"x": 540, "y": 960, "scale": 1, "rotation": 0, "opacity": 1, "padding": 0}
        values.update(raw)
        for prop, lo, hi in (("width", 1, 4096), ("height", 1, 4096), ("x", -8192, 8192),
                             ("y", -8192, 8192), ("scale", .05, 4), ("rotation", -180, 180),
                             ("opacity", 0, 1), ("padding", 0, 128)):
            v = values.get(prop)
            if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not lo <= v <= hi:
                raise EpisodeError(f"scene {index}: placement {prop} must be finite {lo}..{hi}")
        if values.get("fit", "contain") not in ("contain", "cover"):
            raise EpisodeError(f"scene {index}: placement fit must be contain or cover")
        if 2*values["padding"] >= min(values["width"], values["height"]):
            raise EpisodeError(f"scene {index}: placement padding consumes its plane")
        if "matte" in values:
            try:
                if not isinstance(values["matte"], str): raise ValueError()
                ImageColor.getrgb(values["matte"])
            except (ValueError, TypeError) as exc:
                raise EpisodeError(f"scene {index}: invalid matte colour") from exc
        elif values["padding"]:
            raise EpisodeError(f"scene {index}: padding requires a matte colour")
        extra["placement"] = values
    tracks = layer.get("tracks")
    if tracks:
        extra["tracks"] = parse_tracks(tracks, index, 4, time_limit=600 if extra.get("clock") == "episode" else 30, scale_min=.05 if "placement" in extra else .5)
        for prop in ("x", "y"):
            if any(abs(k["v"]) > 8192 for k in extra["tracks"].get(prop, [])):
                raise EpisodeError(f"scene {index}: layer offsets must stay within 8192px")
    return extra


def track_time(layer, u, scene_start, episode_time=None):
    return (u + scene_start if episode_time is None else episode_time) if layer.get("clock") == "episode" else u


def placed_pose(layer, pose, u, duration, fit_scale, canvas_size, scene_start=0, shake=(0, 0), episode_time=None):
    p = layer["placement"]
    tracks = layer.get("tracks") or {}
    time = track_time(layer, u, scene_start, episode_time)
    def value(prop, default):
        return sample_keys(tracks[prop], time, duration) if prop in tracks else default
    gain = .25+.75*layer["depth"]
    camera_scale = 1+(pose["scale"]-1)*gain
    cw, ch = canvas_size
    return {"x": cw/2 + (p["x"]+value("x", 0)-540)*fit_scale*camera_scale + pose["x"]*gain*fit_scale + shake[0],
            "y": ch/2 + (p["y"]+value("y", 0)-960)*fit_scale*camera_scale + pose["y"]*gain*fit_scale + shake[1],
            "scale": camera_scale*p["scale"]*max(.05, value("scale", 1)),
            "rotation": p["rotation"]+value("rotation", 0),
            "opacity": p["opacity"]*min(1, max(0, value("opacity", 1)))}


def blit_fragment(plate, image, layer, pose, u, duration, fit_scale, scene_start=0, shake=(0, 0), episode_time=None, paint=None):
    from gilvy.product import DEFAULTS, composite
    p = layer["placement"]
    width, height = max(1, round(p["width"]*fit_scale)), max(1, round(p["height"]*fit_scale))
    pad = round(p["padding"]*fit_scale)
    # For small derivatives the border may round into the last pixel.
    pad = min(pad, (min(width, height)-1)//2)
    inner = (width-2*pad, height-2*pad)
    plane = Image.new("RGBA", (width, height), p.get("matte", (0, 0, 0, 0)))
    content = (ImageOps.fit(image, inner, method=Image.Resampling.LANCZOS)
               if p.get("fit") == "cover" else ImageOps.contain(image, inner, method=Image.Resampling.LANCZOS))
    plane.alpha_composite(content, ((width-content.width)//2, (height-content.height)//2))
    if paint is not None:
        paint(plane)
    canvas = Image.fromarray(np.clip(plate, 0, 255).astype("uint8")).convert("RGBA")
    state = placed_pose(layer, pose, u, duration, fit_scale, canvas.size, scene_start, shake, episode_time)
    composite(canvas, plane, {**DEFAULTS, **state})
    plate[:] = np.asarray(canvas.convert("RGB"), dtype=np.float32)


def asset_integrity(path, expected="any"):
    """Only file/alpha evidence. Does not decide whether the depicted scene makes sense."""
    try:
        with Image.open(path) as source:
            if source.width*source.height > 16_777_216:
                return {"ok": False, "flags": ["asset_exceeds_16_megapixels"]}
            image = source.convert("RGBA")
            lo, hi = image.getchannel("A").getextrema()
            flags = []
            if hi == 0: flags.append("empty_alpha")
            if expected == "transparent" and lo == 255: flags.append("missing_transparency")
            if expected == "opaque" and lo != 255: flags.append("unexpected_transparency")
            return {"ok": not flags, "flags": flags, "alpha_range": [lo, hi], "pixels": list(image.size)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "flags": ["unreadable_image"], "error": str(exc)}
