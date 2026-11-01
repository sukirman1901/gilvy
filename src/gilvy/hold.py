"""Keep a long scene alive after its authored beat has finished.

Scenes of seven seconds or less are left alone, so the original frames stay
byte-identical. A longer voice-over keeps a small idle on the object that
already landed. The camera does not zoom.
"""

from __future__ import annotations

import math

HOLD_AFTER = 7.0
ARRIVAL = 1.6


def settle_at(dur: float) -> float:
    """The verb owns the frame until 65% of the scene. The hold starts after that."""
    return max(ARRIVAL, dur * 0.65)


def holding(u: float, dur: float, start: float | None = None) -> bool:
    if start is None:
        start = settle_at(dur)
    return dur > HOLD_AFTER and u > start


def hold_wave(u: float, dur: float, start: float = 1.8) -> float:
    """Smooth −1..1 cycle. Zero while the verb is still running, and on every short scene."""
    begin = max(start, settle_at(dur))
    if not holding(u, dur, begin):
        return 0.0
    return math.sin(2 * math.pi * (u - begin) / 3.4)
