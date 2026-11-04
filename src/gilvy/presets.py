"""Opt-in reference presets. House episodes do not use these numbers.

Ranges are the conformance band for authored image scenes. The evidence behind
each number is written in REFERENCE_STYLES.md. A measured flash cut or a
saturated zoom-through can sit outside the band; those are transitions or
montage exceptions, not the plate the agent should author.
"""

from __future__ import annotations

HOUSE = "house"
VOX = "vox-explainer"
HISTORY = "history-story"
PRESETS = (HOUSE, VOX, HISTORY)
PHOTO_PRESETS = frozenset({VOX, HISTORY})

# zoom_lo/zoom_hi apply to a push (positive %/s) and pull_lo/pull_hi to a pull.
# Rates are absolute percent of frame scale per second.
RULES = {
    VOX: {
        "shot_min": 0.70,
        "shot_max": 5.00,
        "zoom_lo": 0.80,
        "zoom_hi": 3.50,
        "pull_lo": 0.80,
        "pull_hi": 3.50,
        "pan_min": 8.0,
        "default_ease": "linear",
        "default_grade": "paper",
        "default_grain": 0.08,
        "default_transition": "cut",
        "default_transition_s": 0.0,
        "text_entrance": "pop",
        "text_fade_s": 0.16,
        "text_size": 72,
        "keyword_lead": -0.10,
        # House breath. Vox has not had a timing pass; history has.
        "pad": 0.4,
        "lead": 0.2,
        "skip_green": False,
    },
    HISTORY: {
        "shot_min": 1.10,
        "shot_max": 7.00,
        # Reference pushes on the Lustig short run about 7.7–24%/s, including short punches.
        "zoom_lo": 0.80,
        "zoom_hi": 26.0,
        "pull_lo": 0.80,
        "pull_hi": 26.0,
        "punch_zoom_hi": 40.0,
        "punch_max_s": 1.5,
        "scale_max": 2.4,
        "pan_min": 8.0,
        "default_ease": "exponential",
        "default_grade": "sepia",
        "default_grain": 0.22,
        "default_transition": "dissolve",
        "default_transition_s": 0.40,
        "text_entrance": "fade",
        "text_fade_s": 0.15,
        # 3× the old 72px default. The Lustig pass still read about 9× under the reference.
        "text_size": 216,
        "keyword_lead": 0.15,
        # House pad+lead adds 0.6s per scene. That turned a 31.9s voice cut into 35.6s.
        "pad": 0.0,
        "lead": 0.0,
        "intro": 0.0,
        "loudness": -21.0,
        "skip_green": True,
    },
}

STYLE_PROMPTS = {
    VOX: (
        "Vertical 9:16 photographic plate for a Vox-style explainer, natural color, "
        "no letters, no watermark, no logo. Cutout layers need a clean edge and a "
        "transparent background."
    ),
    HISTORY: (
        "Archival photo, sepia, grain, vignette, vertical 9:16 framing. "
        "No letters, no watermark, no logo."
    ),
}


def _band(rules: dict, duration: float | None) -> tuple[float, float, float, float]:
    """Push/pull limits. A shot at or under punch_max_s may go faster."""
    push_hi = float(rules["zoom_hi"])
    pull_hi = float(rules["pull_hi"])
    if duration is not None and duration <= float(rules.get("punch_max_s", 1.5)):
        punch = float(rules.get("punch_zoom_hi", push_hi))
        push_hi = max(push_hi, punch)
        pull_hi = max(pull_hi, punch)
    return float(rules["zoom_lo"]), push_hi, float(rules["pull_lo"]), pull_hi


def zoom_in_band(rate: float, rules: dict, duration: float | None = None) -> bool:
    """True when a signed percent-per-second rate matches the preset's plate band."""
    push_lo, push_hi, pull_lo, pull_hi = _band(rules, duration)
    if rate >= 0:
        return push_lo <= rate <= push_hi
    return pull_lo <= abs(rate) <= pull_hi


def camera_problem(metrics: dict, rules: dict, label: str) -> str | None:
    """Return one conformance error, or None when the plate move is inside the band."""
    if metrics.get("static"):
        return f"{label} camera is static. This preset keeps every image plate moving."
    zoom = float(metrics["zoom_pct_per_s"])
    pan = metrics["pan_px_per_s"]
    speed = (float(pan["x"]) ** 2 + float(pan["y"]) ** 2) ** 0.5
    duration = metrics.get("duration")
    push_lo, push_hi, pull_lo, pull_hi = _band(rules, None if duration is None else float(duration))
    if metrics.get("explicit_tracks"):
        push = float(metrics.get("peak_push_pct_per_s", 0))
        pull = float(metrics.get("peak_pull_pct_per_s", 0))
        if push > push_hi or pull > pull_hi:
            return f"{label} peak segment zoom (push {push:.2f}, pull {pull:.2f}%/s) exceeds the plate band"
        # A round trip has zero net displacement, but is not a static shot.
        if max(push, pull) >= .4 or float(metrics.get("peak_pan_px_per_s", 0)) >= rules["pan_min"] or metrics.get("travel", {}).get("rotation", 0) >= .4:
            return None
    if abs(zoom) >= 0.4 and not zoom_in_band(zoom, rules, None if duration is None else float(duration)):
        return (
            f"{label} zoom {zoom:.2f}%/s is outside the plate band "
            f"(push {push_lo:.2f}–{push_hi:.2f}%/s, "
            f"pull {pull_lo:.2f}–{pull_hi:.2f}%/s). "
            "A short punch may go faster; a longer plate stays in the main band."
        )
    if abs(zoom) < 0.4 and speed < rules["pan_min"]:
        return (
            f"{label} camera barely moves (zoom {zoom:.2f}%/s, pan {speed:.1f}px/s). "
            f"Pan at least {rules['pan_min']:.0f}px/s or push/pull inside the plate band."
        )
    return None
