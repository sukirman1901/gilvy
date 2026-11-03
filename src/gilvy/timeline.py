"""Frame-addressable composition timing. No playback-dependent mutable state."""
from dataclasses import asdict, dataclass
import math

from gilvy.errors import GilvyError


def frame_count(seconds, fps):
    return math.ceil(seconds * fps - 1e-8)


def timing(node, duration, parent_start=0, parent_end=None):
    """Local start/end are parent-relative; local tracks start at the node's start.

    Legacy/global start/end and tracks remain film-relative, even inside groups.
    A parent's visibility always clips its descendants.
    """
    parent_end = duration if parent_end is None else parent_end
    space = node.get("time_space", "global")
    if space not in ("local", "global"):
        raise GilvyError(f"layer {node.get('id')}: time_space must be local/global")
    limit = parent_end - parent_start if space == "local" else duration
    a, b = node.get("start", 0), node.get("end", limit)
    if any(not isinstance(v, (int, float)) or isinstance(v, bool)
           or not math.isfinite(v) for v in (a, b)) or not 0 <= a < b <= limit:
        raise GilvyError(f"layer {node.get('id')}: invalid start/end in {space} time")
    origin = parent_start if space == "local" else 0
    return origin + a, origin + b, origin + a if space == "local" else 0


@dataclass(frozen=True)
class Span:
    id: str
    parent: str | None
    start: float
    end: float
    origin: float
    visible_start: float
    visible_end: float
    first_frame: int
    end_frame: int

    def active(self, seconds):
        return self.visible_start <= seconds < self.visible_end


def compile_timeline(spec):
    duration, fps = spec["duration"], spec.get("fps", 30)
    spans = {}

    def walk(nodes, parent=None):
        for node in nodes:
            a, b, origin = timing(node, duration,
                                  parent.start if parent else 0,
                                  parent.end if parent else duration)
            lo = max(a, parent.visible_start if parent else 0)
            hi = min(b, parent.visible_end if parent else duration)
            span = Span(node["id"], parent.id if parent else None, a, b, origin,
                        lo, hi, frame_count(lo, fps), max(frame_count(lo, fps), frame_count(hi, fps)))
            spans[span.id] = span
            if node["type"] == "group":
                walk(node["children"], span)

    walk(spec["layers"])
    return spans


def describe_timeline(film):
    return {"fps": film.fps, "frames": frame_count(film.duration, film.fps),
            "duration": film.duration, "end_exclusive": True,
            "layers": [asdict(span) for span in film.timeline.values()]}
