"""Opt-in product film compositor. Independent of the locked explainer renderer."""

from __future__ import annotations

import json
import math
import copy
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageFilter

from gilvy.timeline import timing, compile_timeline, frame_count
from gilvy.particles import checked_points, particle_plane
from gilvy.product_layout import layout_groups
from gilvy.errors import GilvyError
from gilvy.product_ui import color, component
from gilvy.product_design import PARTS, DEFAULT_CONTENT
from gilvy.product_primitives import (
    text_plane, text_layout, counter_text, shape_plane, clip_plane, filter_plane, average_planes, typeface,
)


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
    "value": 0.0,
    "clip_x": 0.0,
    "clip_y": 0.0,
    "clip_width": 1.0,
    "clip_height": 1.0,
    "clip_radius": 0.0,
    "pivot_x": 0.5,
    "pivot_y": 0.5,
    "scale_x": 1.0,
    "scale_y": 1.0,
    "blur_length": 0.0,
    "blur_angle": 0.0,
}
EASES = {
    "linear": lambda t: t,
    "smooth": lambda t: t * t * (3 - 2 * t),
    "out_cubic": lambda t: 1 - (1 - t) ** 3,
    "in_cubic": lambda t: t**3,
}
KINDS = {
    "text",
    "rect",
    "progress",
    "cursor",
    "panel",
    "menu",
    "group",
    "inbox-part",
    "image",
    "counter",
    "ellipse",
    "path",
    "particles",
}
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
    "content",
    "part",
    "src",
    "font", "align", "valign", "baseline", "padding", "line_height",
    "letter_spacing", "overflow", "decimals", "decimal_separator", "prefix", "suffix",
    "commands", "stroke", "stroke_width", "samples", "shutter",
    "time_space", "layout", "points", "poses", "dot_radius",
    "max_lines", "min_size",
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
            u = ease(b[2] if len(b) == 3 else "smooth", u)
            return a[1] + (b[1] - a[1]) * u
    return float(keys[-1][1])


def valid_ease(value):
    if isinstance(value, str):
        return value in EASES
    return (isinstance(value, list) and len(value) == 4
            and all(finite(v) and abs(v) <= 8 for v in value)
            and 0 <= value[0] <= 1 and 0 <= value[2] <= 1)


def ease(curve, u):
    if isinstance(curve, str):
        return EASES[curve](u)
    x1,y1,x2,y2=curve
    def bez(a,b,t): return 3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3
    lo,hi=0.0,1.0
    for _ in range(30):
        mid=(lo+hi)/2
        if bez(x1,x2,mid)<u: lo=mid
        else: hi=mid
    return bez(y1,y2,(lo+hi)/2)


def _range(prop, value):
    if not finite(value):
        return False
    if prop in ("opacity", "progress", "clip_x", "clip_y", "clip_width", "clip_height", "pivot_x", "pivot_y"):
        return 0 <= value <= 1
    if prop in ("scale", "scale_x", "scale_y"):
        return 0.01 <= value <= 8
    if prop in ("tilt_x", "tilt_y"):
        return abs(value) <= 65
    if prop == "blur":
        return 0 <= value <= 40
    if prop == "blur_length":
        return 0 <= value <= 128
    if prop == "clip_radius":
        return 0 <= value <= 2048
    if prop == "value":
        return abs(value) <= 1e15
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

    def walk(nodes, depth=0, sample_budget=1, parent_start=0, parent_end=duration):
        nonlocal pixels
        if depth > 6:
            raise GilvyError("group nesting exceeds six levels")
        for node in nodes:
            if not isinstance(node, dict) or node.get("type") not in KINDS:
                raise GilvyError("unknown product component")
            if set(node) - PROPS:
                raise GilvyError(f"unknown layer fields: {sorted(set(node)-PROPS)}")
            validate_tools(node)
            branch_samples=sample_budget*node.get('samples',1)
            if branch_samples>8:
                raise GilvyError('nested layer sampling exceeds eight samples per branch')
            identifier = node.get("id")
            if not isinstance(identifier, str) or identifier in ids:
                raise GilvyError("layer ids must be unique strings")
            ids.add(identifier)
            if len(ids) > 100:
                raise GilvyError("product film supports at most 100 layers")
            if node["type"] == "image" and (
                not isinstance(node.get("src"), str)
                or not node["src"]
                or "://" in node["src"]
            ):
                raise GilvyError("image src must be a local filename")
            if node["type"] == "inbox-part" and (
                not isinstance(node.get("part"), str) or node["part"] not in PARTS
            ):
                raise GilvyError("inbox-part requires a known part name")
            content = node.get("content", {})
            if not isinstance(content, dict) or set(content) - set(DEFAULT_CONTENT):
                raise GilvyError("unknown inbox content fields")
            for key, value in content.items():
                if key == "sent":
                    if not isinstance(value, bool):
                        raise GilvyError("sent must be boolean")
                elif not isinstance(value, str) or len(value) > 1000:
                    raise GilvyError(
                        "inbox content must be text of at most 1000 characters"
                    )
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
            a, b, origin = timing(node, duration, parent_start, parent_end)
            track_limit = b-a if node.get("time_space") == "local" else duration
            if "layout" in node and node["type"] != "group":
                raise GilvyError("layout is only supported on groups")
            if node["type"] == "particles":
                points = checked_points(node.get("points"))
                poses = node.get("poses", [])
                if not isinstance(poses, list) or len(poses) > 64:
                    raise GilvyError("particles support at most 64 poses")
                previous = 0
                for pose in poses:
                    if (not isinstance(pose, list) or len(pose) not in (2, 3)
                        or not finite(pose[0]) or not previous < pose[0] <= track_limit
                        or len(pose) == 3 and not valid_ease(pose[2])):
                        raise GilvyError("particle pose times must increase from >0 within the track clock")
                    checked_points(pose[1], len(points))
                    previous = pose[0]
                if not finite(node.get("dot_radius", 2)) or not .25 <= node.get("dot_radius", 2) <= 128:
                    raise GilvyError("dot_radius must be .25..128")
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
                        or not 0 <= key[0] <= track_limit
                        or key[0] <= previous
                    ):
                        raise GilvyError(
                            "keyframe times must be finite, unique, increasing seconds within their time space"
                        )
                    if (
                        not _range(prop, key[1])
                        or len(key) == 3
                        and not valid_ease(key[2])
                    ):
                        raise GilvyError(f"invalid {prop} keyframe/easing")
                    previous = key[0]
            for prop in ("color", "accent", "fill", "border", "stroke"):
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
                walk(node["children"], depth + 1, branch_samples, a, b)

    walk(spec["layers"])
    layout_groups(copy.deepcopy(spec["layers"]))
    bg = spec.get("background", {})
    if not isinstance(bg, dict) or set(bg) - {"base", "lights"}:
        raise GilvyError("invalid background")
    try:
        color(bg.get("base", "#f2f7ff"))
        lights = bg.get("lights", [])
        if not isinstance(lights, list) or len(lights)>16:
            raise ValueError("lights must be a list of at most sixteen")
        for light in lights:
            if not isinstance(light, dict) or set(light)-{'x','y','radius','color','keyframes'}:
                raise ValueError("unknown light fields")
            color(light["color"])
            if (
                any(not finite(light[k]) for k in ("x", "y", "radius"))
                or not 0.05 <= light["radius"] <= 3
            ):
                raise ValueError("invalid light geometry")
            tracks=light.get('keyframes',{})
            if not isinstance(tracks,dict) or set(tracks)-{'x','y','radius','red','green','blue'}:
                raise ValueError('invalid light tracks')
            for prop,keys in tracks.items():
                previous=-1
                if not isinstance(keys,list) or not keys: raise ValueError('empty light track')
                for key in keys:
                    if (not isinstance(key,list) or len(key) not in (2,3)
                        or not finite(key[0]) or not previous < key[0] <= duration
                        or key[0]<0 or not finite(key[1])
                        or (prop=='radius' and not .05<=key[1]<=3)
                        or (prop in ('red','green','blue') and not 0<=key[1]<=255)
                        or (prop in ('x','y') and abs(key[1])>8)
                        or (len(key)==3 and not valid_ease(key[2]))):
                        raise ValueError('invalid light keyframe')
                    previous=key[0]
    except (KeyError, ValueError, TypeError) as exc:
        raise GilvyError("invalid gradient light") from exc


def validate_tools(node):
    if type(node.get("max_lines", 100)) is not int or not 1 <= node.get("max_lines", 100) <= 100:
        raise GilvyError("max_lines must be 1..100")
    if not finite(node.get("size", 48)) or not finite(node.get("min_size", 1)) or not 1 <= node.get("min_size", 1) <= node.get("size", 48):
        raise GilvyError("min_size must be positive and <= size")
    for prop in ('font','prefix','suffix'):
        if prop in node and (not isinstance(node[prop],str) or len(node[prop])>4096):
            raise GilvyError(f'{prop} must be text')
    if 'font' in node and (not node['font'] or '://' in node['font']):
        raise GilvyError('font must be a local filename')
    for prop, choices in [('align',('left','center','right')),('valign',('top','center','bottom')),
                          ('overflow',('clip','error','wrap','fit')),('decimal_separator',('.',','))]:
        if prop in node and node[prop] not in choices: raise GilvyError(f'invalid {prop}')
    for prop,lo,hi in [('padding',0,2048),('baseline',-4096,8192),('line_height',.5,5),
                      ('letter_spacing',-20,100),('stroke_width',.1,512)]:
        if prop in node and (not finite(node[prop]) or not lo<=node[prop]<=hi):
            raise GilvyError(f'invalid {prop}')
    if type(node.get('decimals',0)) is not int or not 0<=node.get('decimals',0)<=6:
        raise GilvyError('decimals must be an integer from zero to six')
    if (type(node.get('samples',1)) is not int or not 1<=node.get('samples',1)<=8
        or not finite(node.get('shutter',.5)) or not 0<=node.get('shutter',.5)<=1):
        raise GilvyError('layer samples: 1..8; shutter: 0..1 frame')
    if node.get('type')=='path':
        commands=node.get('commands')
        if not isinstance(commands,list) or not 2<=len(commands)<=2048:
            raise GilvyError('path requires 2..2048 M/L/Q/C/Z commands')
        opened=False
        for cmd in commands:
            if (not isinstance(cmd,list) or not cmd or not isinstance(cmd[0],str)
                or cmd[0] not in {'M','L','Q','C','Z'}
                or len(cmd)!={'M':3,'L':3,'Q':5,'C':7,'Z':1}[cmd[0]]
                or any(not finite(v) or abs(v)>8192 for v in cmd[1:])
                or (cmd[0]!='M' and not opened)):
                raise GilvyError('invalid path command or missing M')
            if cmd[0]=='M':opened=True


def load_product(path):
    p = Path(path).expanduser().resolve()
    try:
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise GilvyError(f"could not load product film: {exc}") from exc
    validate(spec)
    return ProductFilm(spec, p.parent)


def gradient(size, background, t=0):
    # Low-res Gaussian light fields are deliberately smooth, then upsampled.
    w, h = size
    sw, sh = 256, max(16, round(256 * h / w))
    y, x = np.mgrid[0:sh, 0:sw].astype(float)
    x /= sw
    y /= sh
    rgb = np.zeros((sh, sw, 3)) + np.array(color(background.get("base", "#f2f7ff"))[:3])
    for light in background.get("lights", []):
        tracks=light.get('keyframes',{})
        lx=interpolate(tracks.get('x'),t,light['x'])
        ly=interpolate(tracks.get('y'),t,light['y'])
        radius=max(.05,interpolate(tracks.get('radius'),t,light['radius']))
        base_color=color(light['color'])[:3]
        tint=np.clip([interpolate(tracks.get(k),t,v) for k,v in zip(('red','green','blue'),base_color)],0,255)
        a = np.exp(
            -2 * ((x - lx) ** 2 + (y - ly) ** 2) / radius ** 2
        )[..., None]
        rgb = rgb * (1 - a) + tint * a
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
                [-w*state['pivot_x'], -h*state['pivot_y'], 0],
                [w*(1-state['pivot_x']), -h*state['pivot_y'], 0],
                [w*(1-state['pivot_x']), h*(1-state['pivot_y']), 0],
                [-w*state['pivot_x'], h*(1-state['pivot_y']), 0],
            ],
            float,
        )
        * state["scale"]
    )
    pts *= [state['scale_x'],state['scale_y'],1]
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
    distance = 3 * max(w, h) * max(1, state["scale"]) * max(1,state['scale_x'],state['scale_y'])
    xy = pts[:, :2] * distance / (distance + pts[:, 2:3])
    return xy + np.array([state["x"], state["y"]])


def composite(canvas, image, state, shadow=False):
    """Project a transparent plane using an inverse homography, clipped to viewport."""
    if state["opacity"] <= 0:
        return
    # Exact integer translations need no projective resampling. This is common
    # for native UI child planes and preserves their original glyph pixels.
    ix = state["x"] - image.width * state['pivot_x']
    iy = state["y"] - image.height * state['pivot_y']
    if (
        state["scale"] == 1
        and state['scale_x'] == 1 and state['scale_y'] == 1
        and state["rotation"] == 0
        and state["tilt_x"] == 0
        and state["tilt_y"] == 0
        and state["opacity"] == 1
        and state["blur"] == 0
        and state['blur_length'] == 0
        and not shadow
        and ix == round(ix)
        and iy == round(iy)
    ):
        canvas.alpha_composite(image, (int(ix), int(iy)))
        return
    points = project(image.size, state)
    pad = math.ceil(state["blur"] * 3 + state['blur_length']/2) + (50 if shadow else 2)
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
    layer = image.convert('RGBa').transform(
        (right - left, bottom - top),
        Image.Transform.PERSPECTIVE,
        coeff,
        Image.Resampling.BICUBIC,
    ).convert('RGBA')
    if state["blur"] or state['blur_length']:
        layer = filter_plane(layer,state['blur'],state['blur_length'],state['blur_angle'])
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
        self.spec = copy.deepcopy(spec)
        self.source_dir = Path(source_dir)
        self.timeline = compile_timeline(self.spec)

        def resolve_assets(nodes):
            for node in nodes:
                if 'font' in node:
                    path=(self.source_dir/node['font']).resolve()
                    if not path.is_file(): raise GilvyError(f'font not found: {path}')
                    node['font']=str(path)
                    typeface(str(path),node.get('size',48),node.get('weight','Regular'))
                if node["type"] == "image":
                    path = (self.source_dir / node["src"]).resolve()
                    if not path.is_file():
                        raise GilvyError(f"image not found: {path}")
                    node["src"] = str(path)
                if node["type"] == "group":
                    resolve_assets(node["children"])

        resolve_assets(self.spec["layers"])
        self.layers = copy.deepcopy(self.spec["layers"])
        layout_groups(self.layers)
        self.size = tuple(spec.get("size", [1280, 720]))
        self.fps = spec.get("fps", 30)
        self.duration = spec["duration"]
        self.background = gradient(self.size, spec.get("background", {}))
        self.dynamic_background=any(light.get('keyframes') for light in spec.get('background',{}).get('lights',[]))
        self.cache = {}
        # Decode static assets and validate full text before any encoder starts.
        def prepare(nodes):
            for node in nodes:
                if node["type"] == "group":
                    prepare(node["children"])
                elif node["type"] == "image":
                    self.cache[node["id"]] = component(node, 1)
                elif node["type"] == "text" and any(k in node for k in ("font", "align", "valign", "baseline", "padding", "line_height", "letter_spacing", "overflow")):
                    text_plane(node)
        prepare(self.layers)

    def state(self, node, t):
        t -= self.timeline[node["id"]].origin
        state = {
            k: interpolate(node.get("keyframes", {}).get(k), t, node.get(k, v))
            for k, v in DEFAULTS.items()
        }
        for k in ('opacity','progress','clip_x','clip_y','clip_width','clip_height','pivot_x','pivot_y'):
            state[k]=min(1,max(0,state[k]))
        for k in ('scale','scale_x','scale_y'):state[k]=max(.01,state[k])
        for k in ('blur','blur_length','clip_radius'):state[k]=max(0,state[k])
        return state

    def paint(self, nodes, canvas, t):
        for node in nodes:
            count=node.get('samples',1)
            shutter=node.get('shutter',.5)/self.fps
            if count>1 and shutter>0:
                images=[]
                for offset in np.linspace(-shutter/2,shutter/2,count):
                    plane=Image.new('RGBA',canvas.size)
                    tt=min(max(t+float(offset),0),self.duration-1e-9)
                    self.paint_one(node,plane,tt)
                    images.append(plane)
                canvas.alpha_composite(average_planes(images))
            else:
                self.paint_one(node,canvas,t)

    def paint_one(self, node, canvas, t):
        if not self.timeline[node["id"]].active(t):
            return
        state = self.state(node, t)
        if state["opacity"] <= 0:
            return
        if node["type"] == "group":
            image = Image.new("RGBA", (node["width"], node["height"]))
            self.paint(node["children"], image, t)
        else:
            dynamic = (
                node["type"] == "inbox-part"
                and node.get("part") == "reply"
                or node["type"] in ("progress", "menu")
                or node.get("reveal", "none") != "none"
                or node.get("variant") == "workflow"
                or node['type'] in ('counter','path','particles')
            )
            if not dynamic and node["id"] in self.cache:
                image = self.cache[node["id"]]
            else:
                if node['type']=='particles':
                    image=particle_plane(node,t-self.timeline[node['id']].origin,ease)
                elif node['type']=='counter':
                    image=text_plane(node,state['value'])
                elif node['type'] in ('path','ellipse'):
                    image=shape_plane(node,state['progress'])
                elif node['type']=='text' and any(k in node for k in ('font','align','valign','baseline','padding','line_height','letter_spacing','overflow')):
                    image=text_plane(node,progress=state['progress'])
                else:
                    image = component(node, state["progress"])
                if not dynamic:
                    self.cache[node["id"]] = image
        image=clip_plane(image,state)
        composite(canvas, image, state, node.get("shadow", False))

    def frame_at(self, index):
        """Exact integer seek through the same native kernel used for export."""
        if type(index) is not int or not 0 <= index < frame_count(self.duration, self.fps):
            raise GilvyError("frame index outside composition")
        return self.frame(index / self.fps)

    def inspect(self, index):
        if type(index) is not int or not 0 <= index < frame_count(self.duration, self.fps):
            raise GilvyError("frame index outside composition")
        t = index / self.fps
        def walk(nodes):
            rows = []
            for node in nodes:
                span = self.timeline[node["id"]]
                state = self.state(node, t)
                rows.append({"id": node["id"], "type": node["type"], "parent": span.parent,
                             "active": span.active(t), "time_space": node.get("time_space", "global"),
                             "track_seconds": t-span.origin,
                             "state": state, "quad_in_parent": project((node["width"],node["height"]),state).tolist()})
                if node["type"] in ("text", "counter") and (node["type"] == "counter" or any(k in node for k in ("font", "align", "valign", "baseline", "padding", "line_height", "letter_spacing", "overflow"))):
                    full = counter_text(node, state["value"]) if node["type"] == "counter" else node.get("text", "")
                    rows[-1]["text_layout"] = text_layout(node, full)[1]
                if node["type"] == "group": rows.extend(walk(node["children"]))
            return rows
        return {"frame": index, "time": t, "layers": walk(self.layers)}

    def background_at(self,t):
        return gradient(self.size,self.spec.get('background',{}),t) if self.dynamic_background else self.background.copy()

    def frame(self, t):
        """Temporal supersampling averages the complete composited frame in linear light."""
        samples = self.spec.get("samples", 1)
        shutter = self.spec.get("shutter", 0.5) / self.fps
        if samples == 1 or shutter == 0:
            canvas = self.background_at(t)
            self.paint(self.layers, canvas, t)
            return canvas.convert("RGB")
        acc = np.zeros((self.size[1], self.size[0], 3), np.float32)
        for offset in np.linspace(-shutter / 2, shutter / 2, samples):
            tt = min(max(t + float(offset), 0), max(0, self.duration - 1e-9))
            canvas = self.background_at(tt)
            self.paint(self.layers, canvas, tt)
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
