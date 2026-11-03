"""Opt-in product film compositor. Independent of the locked explainer renderer."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageFilter

from gilvy.errors import GilvyError
from gilvy.product_ui import color, component


DEFAULTS = {
    "x": 0.0,
    "y": 0.0,
    "scale": 1.0,
    "rotation": 0.0,
    "tilt_x": 0.0,
    "tilt_y": 0.0,
    "opacity": 1.0,
    "blur": 0.0,
    "progress": 1.0,
}
EASES = {
    "linear": lambda t: t,
    "smooth": lambda t: t * t * (3 - 2 * t),
    "out_cubic": lambda t: 1 - (1 - t) ** 3,
    "in_cubic": lambda t: t**3,
}
KINDS = {"text", "rect", "progress", "cursor", "panel", "menu", "group"}
PROPS = {
    "id",
    "type",
    "width",
    "height",
    "start",
    "end",
    "keyframes",
    "children",
    "shadow",
    "text",
    "reveal",
    "size",
    "weight",
    "color",
    "radius",
    "fill",
    "border",
    "accent",
    "label",
    "mark",
    "brand",
    "badge",
    "variant",
    "navigation",
    "title",
    "items",
    "subtitle",
    "button",
    "selected",
    *DEFAULTS,
}


def finite(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def interpolate(keys, t, default=0):
    if not keys:
        return default
    if t <= keys[0][0]:
        return float(keys[0][1])
    for a, b in zip(keys, keys[1:]):
        if t < b[0]:
            u = (t - a[0]) / (b[0] - a[0])
            u = EASES[b[2] if len(b) == 3 else "smooth"](u)
            return a[1] + (b[1] - a[1]) * u
    return float(keys[-1][1])


def _range(prop, value):
    if not finite(value):
        return False
    if prop in ("opacity", "progress"):
        return 0 <= value <= 1
    if prop == "scale":
        return 0.01 <= value <= 8
    if prop in ("tilt_x", "tilt_y"):
        return abs(value) <= 65
    if prop == "blur":
        return 0 <= value <= 40
    return abs(value) <= 8192


def validate(spec):
    if not isinstance(spec, dict) or spec.get("style") != "product":
        raise GilvyError(
            "product film requires style: product; use render for house episodes"
        )
    extra = set(spec) - {
        "style",
        "size",
        "fps",
        "duration",
        "samples",
        "shutter",
        "background",
        "layers",
        "audio",
    }
    if extra:
        raise GilvyError(f"unknown product fields: {sorted(extra)}")
    if spec.get("audio") is not None and not isinstance(spec["audio"], str):
        raise GilvyError("audio must be a local filename or null")
    size = spec.get("size", [1280, 720])
    fps = spec.get("fps", 30)
    duration = spec.get("duration")
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(type(v) != int or v % 2 or not 160 <= v <= 1920 for v in size)
    ):
        raise GilvyError("product size requires two even integers from 160 to 1920")
    if (
        type(fps) != int
        or not 1 <= fps <= 60
        or not finite(duration)
        or not 0 < duration <= 120
    ):
        raise GilvyError("fps must be 1..60 and duration >0 and <=120 seconds")
    samples = spec.get("samples", 1)
    shutter = spec.get("shutter", 0.5)
    if (
        type(samples) != int
        or not 1 <= samples <= 8
        or not finite(shutter)
        or not 0 <= shutter <= 1
    ):
        raise GilvyError("samples must be 1..8; shutter must be 0..1 frame")
    if not isinstance(spec.get("layers"), list) or not spec["layers"]:
        raise GilvyError("product film requires layers")
    ids = set()
    pixels = 0

    def walk(nodes, depth=0):
        nonlocal pixels
        if depth > 6:
            raise GilvyError("group nesting exceeds six levels")
        for node in nodes:
            if not isinstance(node, dict) or node.get("type") not in KINDS:
                raise GilvyError("unknown product component")
            if set(node) - PROPS:
                raise GilvyError(f"unknown layer fields: {sorted(set(node)-PROPS)}")
            identifier = node.get("id")
            if not isinstance(identifier, str) or identifier in ids:
                raise GilvyError("layer ids must be unique strings")
            ids.add(identifier)
            if len(ids) > 100:
                raise GilvyError("product film supports at most 100 layers")
            for prop in ("width", "height"):
                if type(node.get(prop)) != int or not 1 <= node[prop] <= 4096:
                    raise GilvyError(f"layer {identifier}: {prop} must be 1..4096")
            pixels += node["width"] * node["height"]
            if pixels > 32_000_000:
                raise GilvyError("product layer pixel budget exceeds 32 million")
            if node["type"] == "panel" and (
                node["width"] < 360 or node["height"] < 200
            ):
                raise GilvyError("panel requires at least 360x200 pixels")
            if node["type"] == "progress" and (
                node["width"] < 80 or node["height"] < 48
            ):
                raise GilvyError("progress requires at least 80x48 pixels")
            if node["type"] == "menu" and (node["width"] < 160 or node["height"] < 80):
                raise GilvyError("menu requires at least 160x80 pixels")
            if type(node.get("selected", 0)) != int or node.get("selected", 0) < 0:
                raise GilvyError("selected must be a nonnegative integer")
            if "shadow" in node and not isinstance(node["shadow"], bool):
                raise GilvyError("shadow must be boolean")
            if (
                not finite(node.get("radius", 16))
                or not 0 <= node.get("radius", 16) <= 2048
            ):
                raise GilvyError("invalid corner radius")
            a, b = node.get("start", 0), node.get("end", duration)
            if not finite(a) or not finite(b) or not 0 <= a < b <= duration:
                raise GilvyError(f"layer {identifier}: invalid start/end")
            for prop in DEFAULTS:
                if prop in node and not _range(prop, node[prop]):
                    raise GilvyError(f"invalid {prop}")
            tracks = node.get("keyframes", {})
            if not isinstance(tracks, dict) or set(tracks) - set(DEFAULTS):
                raise GilvyError("unknown animation property")
            for prop, keys in tracks.items():
                if not isinstance(keys, list) or not keys:
                    raise GilvyError("keyframes must be a nonempty list")
                previous = -1
                for key in keys:
                    if (
                        not isinstance(key, list)
                        or len(key) not in (2, 3)
                        or not finite(key[0])
                        or not 0 <= key[0] <= duration
                        or key[0] <= previous
                    ):
                        raise GilvyError(
                            "keyframe times must be finite, unique, increasing global seconds"
                        )
                    if (
                        not _range(prop, key[1])
                        or len(key) == 3
                        and (not isinstance(key[2], str) or key[2] not in EASES)
                    ):
                        raise GilvyError(f"invalid {prop} keyframe/easing")
                    previous = key[0]
            for prop in ("color", "accent", "fill", "border"):
                if node.get(prop) is not None:
                    try:
                        if not isinstance(node[prop], str):
                            raise ValueError("color must be text")
                        color(node[prop])
                    except (ValueError, TypeError) as exc:
                        raise GilvyError(f"invalid {prop} color") from exc
            if node.get("weight", "Regular") not in (
                "Light",
                "Regular",
                "Medium",
                "SemiBold",
            ):
                raise GilvyError("unknown Poppins weight")
            if not finite(node.get("size", 48)) or not 1 <= node.get("size", 48) <= 512:
                raise GilvyError("invalid text size")
            if node.get("reveal", "none") not in ("none", "words", "characters"):
                raise GilvyError("invalid text reveal")
            if node["type"] == "panel" and node.get("variant", "inbox") not in (
                "inbox",
                "form",
                "workflow",
            ):
                raise GilvyError("unknown panel variant")
            for prop in (
                "text",
                "label",
                "mark",
                "brand",
                "badge",
                "title",
                "subtitle",
                "button",
            ):
                if prop in node and not isinstance(node[prop], str):
                    raise GilvyError(f"{prop} must be text")
            for prop in ("items", "navigation"):
                if prop in node and (
                    not isinstance(node[prop], list)
                    or any(not isinstance(x, str) for x in node[prop])
                ):
                    raise GilvyError(f"{prop} must be a list of text")
            if node["type"] == "group":
                if not isinstance(node.get("children"), list):
                    raise GilvyError("group requires children")
                walk(node["children"], depth + 1)

    walk(spec["layers"])
    bg = spec.get("background", {})
    if not isinstance(bg, dict) or set(bg) - {"base", "lights"}:
        raise GilvyError("invalid background")
    try:
        color(bg.get("base", "#f2f7ff"))
        for light in bg.get("lights", []):
            color(light["color"])
            if (
                any(not finite(light[k]) for k in ("x", "y", "radius"))
                or not 0.05 <= light["radius"] <= 3
            ):
                raise ValueError("invalid light geometry")
    except (KeyError, ValueError, TypeError) as exc:
        raise GilvyError("invalid gradient light") from exc


def load_product(path):
    p = Path(path).expanduser().resolve()
    try:
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GilvyError(f"could not load product film: {exc}") from exc
    validate(spec)
    return ProductFilm(spec, p.parent)


def gradient(size, background):
    # Low-res Gaussian light fields are deliberately smooth, then upsampled.
    w, h = size
    sw, sh = 256, max(16, round(256 * h / w))
    y, x = np.mgrid[0:sh, 0:sw].astype(float)
    x /= sw
    y /= sh
    rgb = np.zeros((sh, sw, 3)) + np.array(color(background.get("base", "#f2f7ff"))[:3])
    for light in background.get("lights", []):
        a = np.exp(
            -2 * ((x - light["x"]) ** 2 + (y - light["y"]) ** 2) / light["radius"] ** 2
        )[..., None]
        rgb = rgb * (1 - a) + np.array(color(light["color"])[:3]) * a
    return (
        Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"))
        .resize((w, h), Image.Resampling.BICUBIC)
        .convert("RGBA")
    )


def project(size, state):
    w, h = size
    pts = (
        np.array(
            [
                [-w / 2, -h / 2, 0],
                [w / 2, -h / 2, 0],
                [w / 2, h / 2, 0],
                [-w / 2, h / 2, 0],
            ],
            float,
        )
        * state["scale"]
    )
    ax, ay, az = np.deg2rad([state["tilt_x"], state["tilt_y"], state["rotation"]])
    rx = np.array(
        [[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]]
    )
    ry = np.array(
        [[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]]
    )
    rz = np.array(
        [[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]]
    )
    pts = pts @ (rz @ ry @ rx).T
    distance = 3 * max(w, h) * max(1, state["scale"])
    xy = pts[:, :2] * distance / (distance + pts[:, 2:3])
    return xy + np.array([state["x"], state["y"]])


def composite(canvas, image, state, shadow=False):
    """Project a transparent plane using an inverse homography, clipped to viewport."""
    if state["opacity"] <= 0:
        return
    points = project(image.size, state)
    pad = math.ceil(state["blur"] * 3) + (50 if shadow else 2)
    left = max(-pad, math.floor(points[:, 0].min()) - pad)
    top = max(-pad, math.floor(points[:, 1].min()) - pad)
    right = min(canvas.width + pad, math.ceil(points[:, 0].max()) + pad)
    bottom = min(canvas.height + pad, math.ceil(points[:, 1].max()) + pad)
    if right <= left or bottom <= top:
        return
    target = points - [left, top]
    src = [(0, 0), (image.width, 0), (image.width, image.height), (0, image.height)]
    matrix = []
    values = []
    for (x, y), (u, v) in zip(target, src):
        matrix.extend(
            [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        )
        values.extend([u, v])
    coeff = np.linalg.solve(np.array(matrix), np.array(values))
    layer = image.transform(
        (right - left, bottom - top),
        Image.Transform.PERSPECTIVE,
        coeff,
        Image.Resampling.BICUBIC,
    )
    if state["blur"]:
        layer = layer.filter(ImageFilter.GaussianBlur(state["blur"]))
    if state["opacity"] < 1:
        layer.putalpha(
            layer.getchannel("A").point(lambda a: round(a * state["opacity"]))
        )
    if shadow:
        shade = Image.new("RGBA", layer.size, "#17355c")
        shade.putalpha(
            layer.getchannel("A")
            .filter(ImageFilter.GaussianBlur(16))
            .point(lambda a: round(a * 0.15))
        )
        canvas.alpha_composite(shade, (left, top + 13))
    canvas.alpha_composite(layer, (left, top))


class ProductFilm:
    def __init__(self, spec, source_dir=Path.cwd()):
        validate(spec)
        self.spec = spec
        self.source_dir = Path(source_dir)
        self.size = tuple(spec.get("size", [1280, 720]))
        self.fps = spec.get("fps", 30)
        self.duration = spec["duration"]
        self.background = gradient(self.size, spec.get("background", {}))
        self.cache = {}

    def state(self, node, t):
        return {
            k: interpolate(node.get("keyframes", {}).get(k), t, node.get(k, v))
            for k, v in DEFAULTS.items()
        }

    def paint(self, nodes, canvas, t):
        for node in nodes:
            if not node.get("start", 0) <= t < node.get("end", self.duration):
                continue
            state = self.state(node, t)
            if state["opacity"] <= 0:
                continue
            if node["type"] == "group":
                image = Image.new("RGBA", (node["width"], node["height"]))
                self.paint(node["children"], image, t)
            else:
                dynamic = (
                    node["type"] in ("progress", "menu")
                    or node.get("reveal", "none") != "none"
                    or node.get("variant") == "workflow"
                )
                if not dynamic and node["id"] in self.cache:
                    image = self.cache[node["id"]]
                else:
                    image = component(node, state["progress"])
                    if not dynamic:
                        self.cache[node["id"]] = image
            composite(canvas, image, state, node.get("shadow", False))

    def frame(self, t):
        """Temporal supersampling averages the complete composited frame in linear light."""
        samples = self.spec.get("samples", 1)
        shutter = self.spec.get("shutter", 0.5) / self.fps
        if samples == 1 or shutter == 0:
            canvas = self.background.copy()
            self.paint(self.spec["layers"], canvas, t)
            return canvas.convert("RGB")
        acc = np.zeros((self.size[1], self.size[0], 3), np.float32)
        for offset in np.linspace(-shutter / 2, shutter / 2, samples):
            tt = min(max(t + float(offset), 0), max(0, self.duration - 1e-9))
            canvas = self.background.copy()
            self.paint(self.spec["layers"], canvas, tt)
            # sRGB transfer, rather than averaging gamma-encoded pixel values.
            a = np.asarray(canvas.convert("RGB"), dtype=np.float32) / 255
            acc += (
                np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
                / samples
            )
        rgb = np.where(
            acc <= 0.0031308,
            acc * 12.92,
            1.055 * np.maximum(acc, 0) ** (1 / 2.4) - 0.055,
        )
        return Image.fromarray(np.clip(np.rint(rgb * 255), 0, 255).astype("uint8"))
