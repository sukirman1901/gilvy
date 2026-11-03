"""Reusable geometry for persistent dots; index is identity, never rematched per frame."""
import math

import numpy as np
from PIL import Image, ImageDraw

from gilvy.errors import GilvyError


def resample_contour(points, count, *, closed=False):
    """Even arc-length samples of ONE polyline; do not join unrelated contours."""
    if type(count) is not int or not 1 <= count <= 2048:
        raise GilvyError("sample count must be 1..2048")
    pts = checked_points(points)
    if closed and not np.array_equal(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[0]])
    lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cumulative = np.r_[0, np.cumsum(lengths)]
    if cumulative[-1] == 0:
        return np.repeat(pts[:1], count, axis=0).tolist()
    keep = np.r_[True, np.diff(cumulative) > 0]
    distance = np.linspace(0, cumulative[-1], count, endpoint=not closed)
    return np.column_stack([np.interp(distance, cumulative[keep], pts[keep, axis])
                            for axis in (0, 1)]).tolist()


def checked_points(value, expected=None):
    if (not isinstance(value, list) or not 1 <= len(value) <= 2048
        or expected is not None and len(value) != expected
        or any(not isinstance(p, list) or len(p) != 2
               or any(isinstance(v, bool) or not isinstance(v, (int, float))
                      or not math.isfinite(v) or abs(v) > 8192 for v in p) for p in value)):
        raise GilvyError("particles require 1..2048 finite [x,y] points and equal pose counts")
    return np.asarray(value, dtype=float)


def particle_positions(node, t, ease):
    """Pure indexed interpolation; callers supply their house/product easing."""
    poses = node.get("poses", [])
    current = node["points"]
    previous_time = 0
    for pose in poses:
        at, target = pose[:2]
        if t < at:
            u = max(0, (t - previous_time) / (at - previous_time))
            u = ease(pose[2] if len(pose) == 3 else "smooth", u)
            return (np.asarray(current) * (1-u) + np.asarray(target) * u).tolist()
        previous_time, current = at, target
    return [list(p) for p in current]


def particle_plane(node, t, ease):
    aa = 2
    im = Image.new("RGBA", (node["width"] * aa, node["height"] * aa))
    draw = ImageDraw.Draw(im)
    radius = node.get("dot_radius", 2)
    for x, y in particle_positions(node, t, ease):
        draw.ellipse(((x-radius)*aa, (y-radius)*aa, (x+radius)*aa, (y+radius)*aa),
                     fill=node.get("color", "#ffffff"))
    return im.resize((node["width"], node["height"]), Image.Resampling.LANCZOS)
