"""Multi-segment camera tracks. `from`/`to` still works as a two-key shorthand.

A track is one property (scale, x, y, rotation, opacity) and a list of keys
`{t, v, ease}`. `t` is seconds from the scene start. The ease on a key is the
curve to the next key. `cubic-bezier` reads `bezier: [x1, y1, x2, y2]`.
"""

from __future__ import annotations

import math

from gilvy.errors import EpisodeError

EASES = (
    "linear",
    "easeInQuad", "easeOutQuad", "easeInOutQuad",
    "easeInCubic", "easeOutCubic", "easeInOutCubic",
    "expoIn", "expoOut",
    "cubic-bezier",
    # Shorthand names already used on camera.ease.
    "ease-out", "ease-in-out", "easeIn", "easeOut", "easeInOut",
)
PROPERTIES = ("scale", "x", "y", "rotation", "opacity")
# A 140% punch is scale 2.4. The cap is per camera and may sit above that.
SCALE_CAP_LIMIT = 4.0


def apply_ease(name: str, p: float, bezier: tuple[float, float, float, float] | None = None) -> float:
    """Unit interval to unit interval."""
    p = 0.0 if p < 0 else 1.0 if p > 1 else p
    if name in ("linear",):
        return p
    if name in ("easeIn", "easeInQuad"):
        return p * p
    if name in ("easeOut", "easeOutQuad"):
        return 1 - (1 - p) ** 2
    if name in ("easeInOut", "easeInOutQuad"):
        return 2 * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 2 / 2
    if name in ("easeInCubic", "ease-in"):
        return p ** 3
    if name in ("easeOutCubic", "ease-out"):
        return 1 - (1 - p) ** 3
    if name in ("easeInOutCubic", "ease-in-out"):
        return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2
    if name == "expoIn":
        return 0.0 if p == 0 else (math.pow(2, 10 * p - 10))
    if name == "expoOut":
        return 1.0 if p == 1 else 1 - math.pow(2, -10 * p)
    if name == "cubic-bezier":
        x1, y1, x2, y2 = bezier or (0.42, 0.0, 0.58, 1.0)
        return _bezier(x1, y1, x2, y2, p)
    return p


def _bezier(x1: float, y1: float, x2: float, y2: float, x: float) -> float:
    def curve(s: float, a: float, b: float) -> float:
        return 3 * (1 - s) ** 2 * s * a + 3 * (1 - s) * s ** 2 * b + s ** 3

    lo, hi = 0.0, 1.0
    for _ in range(24):
        mid = (lo + hi) / 2
        if curve(mid, x1, x2) < x:
            lo = mid
        else:
            hi = mid
    return curve((lo + hi) / 2, y1, y2)


def sample_keys(keys: list[dict], time: float, duration: float) -> float:
    """Value of one track at `time` seconds. Keys are already sorted."""
    if not keys:
        return 0.0
    if time <= keys[0]["t"]:
        return float(keys[0]["v"])
    if time >= keys[-1]["t"]:
        return float(keys[-1]["v"])
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if time > b["t"]:
            continue
        span = max(1e-6, float(b["t"]) - float(a["t"]))
        p = apply_ease(a.get("ease") or "linear", (time - float(a["t"])) / span, a.get("bezier"))
        return float(a["v"]) + (float(b["v"]) - float(a["v"])) * p
    return float(keys[-1]["v"])


def parse_tracks(raw, index: int, scale_max: float, *, time_limit: float = 30, scale_min: float = .5) -> dict[str, list[dict]]:
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise EpisodeError(f"scene {index}: camera.tracks must be a list")
    tracks: dict[str, list[dict]] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise EpisodeError(f"scene {index}: a track must be a mapping")
        prop = item.get("property")
        if prop not in PROPERTIES:
            raise EpisodeError(
                f"scene {index}: track property must be scale, x, y, rotation, or opacity"
            )
        if prop in tracks:
            raise EpisodeError(f"scene {index}: duplicate track property {prop}")
        keys = item.get("keys")
        if not isinstance(keys, list) or len(keys) < 2:
            raise EpisodeError(f"scene {index}: track {prop} needs at least two keys")
        parsed = [_key(key, index, prop, scale_max, time_limit, scale_min) for key in keys]
        if len({key["t"] for key in parsed}) != len(parsed):
            raise EpisodeError(f"scene {index}: track {prop} has duplicate key times")
        parsed.sort(key=lambda row: row["t"])
        tracks[prop] = parsed
    return tracks


def _key(raw, index: int, prop: str, scale_max: float, time_limit: float = 30, scale_min: float = .5) -> dict:
    if not isinstance(raw, dict):
        raise EpisodeError(f"scene {index}: a key must be a mapping")
    try:
        t = float(raw["t"])
        v = float(raw["v"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EpisodeError(f"scene {index}: a key needs numeric t and v") from exc
    if isinstance(raw.get("t"), bool) or isinstance(raw.get("v"), bool) or not math.isfinite(v):
        raise EpisodeError(f"scene {index}: key t and v must be finite numbers")
    if not math.isfinite(t) or t < 0 or t > time_limit:
        raise EpisodeError(f"scene {index}: key t must be seconds from 0 to {time_limit:g}")
    ease = raw.get("ease") or "linear"
    if ease not in EASES:
        raise EpisodeError(f"scene {index}: ease must be one of {', '.join(EASES)}")
    bezier = None
    if ease == "cubic-bezier":
        points = raw.get("bezier")
        if not isinstance(points, (list, tuple)) or len(points) != 4:
            raise EpisodeError(f"scene {index}: cubic-bezier needs bezier: [x1, y1, x2, y2]")
        try:
            bezier = tuple(float(n) for n in points)
        except (ValueError, TypeError) as exc:
            raise EpisodeError(f"scene {index}: invalid cubic-bezier control values") from exc
        if not all(math.isfinite(n) for n in bezier) or not 0 <= bezier[0] <= 1 or not 0 <= bezier[2] <= 1:
            raise EpisodeError(f"scene {index}: Bezier x controls must be 0..1 and all controls finite")
    if prop == "scale" and not scale_min <= v <= scale_max:
        raise EpisodeError(f"scene {index}: scale key must be from {scale_min} to {scale_max}")
    if prop == "opacity" and not 0 <= v <= 1:
        raise EpisodeError(f"scene {index}: opacity key must be from 0 to 1")
    if prop == "rotation" and not -180 <= v <= 180:
        raise EpisodeError(f"scene {index}: rotation key must be degrees from -180 to 180")
    key = {"t": t, "v": v, "ease": ease}
    if bezier is not None:
        key["bezier"] = bezier
    return key


def shorthand_tracks(camera: dict, duration: float) -> dict[str, list[dict]]:
    """Two keys from `from`/`to` for any property that has no explicit track."""
    ease = camera.get("ease") or "linear"
    if ease == "exponential":
        ease = "linear"
    start, end = camera["from"], camera["to"]
    made = {}
    for prop, a, b in (
        ("scale", start["scale"], end["scale"]),
        ("x", start["x"], end["x"]),
        ("y", start["y"], end["y"]),
    ):
        if prop in (camera.get("tracks") or {}):
            continue
        made[prop] = [
            {"t": 0.0, "v": float(a), "ease": ease},
            {"t": float(duration), "v": float(b), "ease": "linear"},
        ]
    return made
