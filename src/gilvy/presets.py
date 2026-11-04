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
        "zoom_lo": 0.80,
        "zoom_hi": 6.00,
        "pull_lo": 0.80,
        "pull_hi": 16.0,
        "pan_min": 8.0,
        "default_ease": "linear",
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


def zoom_in_band(rate: float, rules: dict) -> bool:
    """True when a signed percent-per-second rate matches the preset's plate band."""
    if rate >= 0:
        return rules["zoom_lo"] <= rate <= rules["zoom_hi"]
    return rules["pull_lo"] <= abs(rate) <= rules["pull_hi"]


def camera_problem(metrics: dict, rules: dict, label: str) -> str | None:
    """Return one conformance error, or None when the plate move is inside the band."""
    if metrics.get("static"):
        return f"{label} camera is static. This preset keeps every image plate moving."
    zoom = float(metrics["zoom_pct_per_s"])
    pan = metrics["pan_px_per_s"]
    speed = (float(pan["x"]) ** 2 + float(pan["y"]) ** 2) ** 0.5
    if abs(zoom) >= 0.4 and not zoom_in_band(zoom, rules):
        return (
            f"{label} zoom {zoom:.2f}%/s is outside the plate band "
            f"(push {rules['zoom_lo']:.2f}–{rules['zoom_hi']:.2f}%/s, "
            f"pull {rules['pull_lo']:.2f}–{rules['pull_hi']:.2f}%/s). "
            "A punch zoom belongs on transition_out: zoom, not on the plate."
        )
    if abs(zoom) < 0.4 and speed < rules["pan_min"]:
        return (
            f"{label} camera barely moves (zoom {zoom:.2f}%/s, pan {speed:.1f}px/s). "
            f"Pan at least {rules['pan_min']:.0f}px/s or push/pull inside the plate band."
        )
    return None
