"""Easing used by every scene. These formulas are part of the look."""

from __future__ import annotations


def cl(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def eio(x: float) -> float:
    x = cl(x)
    return 4 * x * x * x if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def eo(x: float) -> float:
    x = cl(x)
    return 1 - (1 - x) ** 3


def eexp(x: float) -> float:
    x = cl(x)
    if x in (0, 1):
        return x
    return 2 ** (20 * x - 10) / 2 if x < 0.5 else (2 - 2 ** (-20 * x + 10)) / 2


def R(u: float, a: float, b: float) -> float:
    """Ramp u from a..b into 0..1 and clamp."""
    return cl((u - a) / (b - a))


def lerp(a: tuple[float, float], b: tuple[float, float], p: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p)


SETTLE = 0.65


def span(u: float, start: float, end: float, dur: float, settle: float = SETTLE) -> float:
    """Ramp u from start..stop into 0..1.

    stop is the authored `end` when that already covers the scene. On a longer
    scene stop moves to `settle * dur` (65%), so the verb lasts most of the
    sentence and the pose at 72% and later matches the authored pose.
    """
    stop = end
    stretched = dur * settle
    if stretched > end:
        stop = stretched
    if stop <= start:
        stop = start + 1e-6
    return R(u, start, stop)
