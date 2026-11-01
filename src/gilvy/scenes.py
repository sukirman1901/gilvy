"""Reusable scenes extracted from the proven episodes.

Green is one quantity: a money figure, and the counter or dots that are that same
quantity. Rings, bowls, tracks, and captions stay white.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gilvy.draw import coins_flow
from gilvy.easing import cl, eexp, eio, eo, R, lerp
from gilvy.errors import GilvyError
from gilvy.hold import hold_wave

DOT_COLS, DOT_ROWS, DOT_SP = 22, 26, 24
DOT_GY = 520
DOT_CAP = DOT_COLS * DOT_ROWS  # 572

DrawFn = Callable  # (ctx, u, duration, params) -> None


@dataclass(frozen=True)
class SceneType:
    name: str
    summary: str
    green: str
    params: dict[str, str]
    required: tuple[str, ...]
    draw: DrawFn


def _focal(ctx):
    return (ctx.theme.cx, 780)


def _gx(ctx) -> float:
    return ctx.theme.cx - (DOT_COLS - 1) * DOT_SP / 2


def bowl(ctx, xy, a, steam=0, sc=1.0, chop=1.0):
    x, y = xy
    r = 62 * sc
    ctx.arc((x, y - 6 * sc), r, 0, 180, a, w=1.8)
    ctx.line((x - r - 10 * sc, y - 6 * sc), (x + r + 10 * sc, y - 6 * sc), a, w=1.6, k=0.9)
    ctx.line((x - 24 * sc, y + r - 4 * sc), (x + 24 * sc, y + r - 4 * sc), a, w=1.6, k=0.7)
    if chop > 0:
        ctx.line((x + 8 * sc, y - 14 * sc), (x + 86 * sc, y - 96 * sc), a, p=chop, w=1.2, k=0.8)
        ctx.line((x + 22 * sc, y - 12 * sc), (x + 98 * sc, y - 86 * sc), a, p=chop, w=1.2, k=0.8)
    for j, dx in enumerate((-26, -6, 14)):
        ph = (steam * 0.45 + j * 0.33) % 1.0
        if steam <= 0:
            continue
        y0 = y - 20 * sc - ph * 40 * sc
        al = a * 0.6 * math_sin(ph)
        pts = [(x + dx * sc + 7 * sc * math_sin_phase(q, j, steam), y0 - q * 14 * sc) for q in range(5)]
        ctx.poly(pts, al, w=1.1, k=0.7)


def math_sin(ph: float) -> float:
    import math

    return math.sin(math.pi * ph)


def math_sin_phase(q: int, j: int, steam: float) -> float:
    import math

    return math.sin(q * 1.6 + j + steam * 1.5)


def dots(ctx, n_on, al, n_hi=0, fade=1.0):
    gx = _gx(ctx)
    for k in range(DOT_CAP):
        row, col = divmod(k, DOT_COLS)
        xy = (gx + col * DOT_SP, DOT_GY + row * DOT_SP)
        if k < n_hi:
            ctx.circ(xy, 3.2, al, fill=1.0, col=ctx.theme.green)
        elif k < n_on:
            ctx.circ(xy, 3.2, al, fill=1.0)
        else:
            ctx.circ(xy, 2.2, al * 0.18 * fade, fill=1.0)


def draw_bowl_hook(ctx, u, dur, params):
    c0 = _focal(ctx)
    a = eo(R(u, 0, 0.6))
    ctx.glow(c0, 150, a * 0.55)
    bowl(ctx, c0, a, steam=u, chop=eio(R(u, 0.5, 1.3)))
    aa = eo(R(u, 1.0, 1.5))
    ctx.money((ctx.theme.cx, c0[1] + 120), str(params["price"]), aa, sz=34, ex=False)
    note = params.get("note")
    if note:
        ctx.text((ctx.theme.cx, c0[1] + 152), str(note), ctx.font("Light", 20), aa * 0.6)


def draw_coin_drop(ctx, u, dur, params):
    c0 = _focal(ctx)
    bowl(ctx, c0, 1, steam=u + 3)
    p = R(u, 0.3, 1.3)
    if 0 < p < 1:
        ctx.coin((ctx.theme.cx, 420 + (c0[1] - 30 - 420) * eexp(p)), min(1, (1 - p) * 6), r=18)
    ctx.glow(c0, 140, eo(R(u, 1.2, 1.6)) * 0.6 * (1 - eo(R(u, 1.6, dur))))
    aa = eo(R(u, 1.2, 1.7))
    ctx.text((ctx.theme.cx, c0[1] + 120), str(params["label"]), ctx.font("Regular", 22), aa * 0.85)


def draw_ring_drain(ctx, u, dur, params):
    count_from = int(params.get("count_from", 0))
    count = int(params["count"])
    if count > DOT_CAP or count_from > DOT_CAP:
        raise GilvyError(f"ring_drain counts must be <= {DOT_CAP} (the dot grid is {DOT_COLS}x{DOT_ROWS})")
    unit = str(params.get("unit", "mangkok"))
    instant = bool(params.get("instant", count_from > 0))
    prog = eio(R(u, 0.6, dur - 0.8))
    rc = (ctx.theme.cx, 400)
    a = 1.0 if instant else eo(R(u, 0, 0.5))
    ctx.circ(rc, 44, a * 0.25, w=1.2)
    ctx.circ(rc, 44, a, w=2, p=1 - prog)
    ctx.text((ctx.theme.cx + 64, rc[1] - 8), str(params["label"]), ctx.font("Regular", 20), a * 0.7, anchor="lm")
    ctx.money((ctx.theme.cx + 64, rc[1] + 20), str(params["amount"]), a, sz=24, ex=False, anchor="lm")
    shown = int(count_from + (count - count_from) * prog)
    dots(ctx, shown, a)
    counter_a = 1.0 if instant else a * cl(prog * 4)
    ctx.money((ctx.theme.cx, DOT_GY + DOT_ROWS * DOT_SP + 40), f"{shown} {unit}", counter_a, sz=30, ex=False)


def draw_compare(ctx, u, dur, params):
    total = int(params["total"])
    highlight = int(params["highlight"])
    if total > DOT_CAP or highlight > total:
        raise GilvyError(f"compare total must be <= {DOT_CAP} and highlight <= total")
    h = eio(R(u, 0.3, 1.3))
    n_hi = int(highlight * h)
    wave = hold_wave(u, dur, 1.7)
    if wave:
        n_hi = max(0, min(total, n_hi + int(round(wave * min(10, max(2, highlight // 20))))))
    dots(ctx, total, 1, n_hi=n_hi)
    a = eo(R(u, 1.2, 1.7))
    yb = DOT_GY + DOT_ROWS * DOT_SP + 40
    gx = _gx(ctx)
    ctx.text((gx, yb), str(params["left"]), ctx.font("Regular", 22), a * 0.85, col=ctx.theme.green, anchor="lm")
    ctx.text((gx + (DOT_COLS - 1) * DOT_SP, yb), str(params["right"]), ctx.font("Regular", 22), a * 0.85, anchor="rm")


def draw_highlight(ctx, u, dur, params):
    heights = list(params.get("heights", [200, 150, 110, 70]))
    index = int(params.get("index", 0))
    bob = hold_wave(u, dur, 1.4) * 12
    for k, h in enumerate(heights):
        x = 270 + k * 162
        a = eo(R(u, k * 0.1, 0.5 + k * 0.1))
        hl = k == index
        lift = bob if hl else 0.0
        ctx.rect(x - 40, 1000 - h - lift, x + 40, 1000, a * (1 if hl else 0.35), w=1.4)
    a = eo(R(u, 0.8, 1.3))
    x = 270 + index * 162
    ctx.line((x, 690), (x, 770), a, w=2)
    ctx.poly([(x - 15, 755), (x, 775), (x + 15, 755)], a, w=2)
    ctx.glow((x, 900), 80, a * 0.5)


def draw_bowl_cta(ctx, u, dur, params):
    c0 = _focal(ctx)
    a = eo(R(u, 0, 0.6))
    ctx.glow(c0, 150, a * 0.6)
    bowl(ctx, c0, a, steam=u, chop=1)
    ctx.label((ctx.theme.cx, c0[1] + 120), str(params["label"]), eo(R(u, 0.6, 1.1)) * 0.7, sz=20)


def draw_timeline(ctx, u, dur, params):
    a = eo(R(u, 0, 0.6))
    ctx.line((180, 780), (846, 780), a * 0.5, w=1.2)
    x = lerp((180, 0), (600, 0), eio(R(u, 0.3, dur - 0.3)))[0]
    ctx.dot((x, 780), 7, a)
    ctx.line((560, 750), (560, 810), a * 0.6, w=1.4)
    ctx.label((560, 840), str(params.get("marker", "jan 1")), a * 0.6, sz=22)


def draw_checklist(ctx, u, dur, params):
    count = int(params.get("count", 14))
    for d in range(count):
        row, col = divmod(d, 7)
        x = 213 + col * 100
        y = 700 + row * 100
        a = eo(R(u, d * 0.05, 0.4 + d * 0.05))
        ctx.rect(x - 38, y - 38, x + 38, y + 38, a * 0.5, w=1)
        ctx.check((x, y), a, eio(R(u, 0.6 + d * 0.06, 0.9 + d * 0.06)), sz=8)
    if dur > 7.0 and u > 1.8 and count > 0:
        lit = int(((u - 1.8) / 0.28) % count)
        row, col = divmod(lit, 7)
        ctx.glow((213 + col * 100, 700 + row * 100), 40, 0.4)


def draw_jars(ctx, u, dur, params):
    spec = params.get("levels")
    n = 3 if spec is None else len(spec)
    for i in range(n):
        x = 300 + i * 213
        y = 860
        a = eo(R(u, i * 0.15, 0.5 + i * 0.15))
        ctx.poly([(x - 60, y - 90), (x - 52, y + 80), (x + 52, y + 80), (x + 60, y - 90)], a, w=1.5)
        level = (0.5 + 0.15 * i) if spec is None else float(spec[i])
        level = max(0.0, min(1.0, level + hold_wave(u, dur, 1.6) * 0.06))
        ctx.fillrect(x - 52, y - 80, x + 52, y + 78, eio(R(u, 0.5, 1.6)) * level, a, k=0.2)


def draw_converge(ctx, u, dur, params):
    c0 = _focal(ctx)
    m = eio(R(u, 0.2, 1.8))
    pts = [(300, 700), (726, 700), (300, 960), (726, 960)]
    for k, origin in enumerate(pts):
        xy = lerp(origin, c0, m)
        a = 1 - m * 0.8
        if k == 0:
            ctx.coin(xy, a, r=20)
        elif k == 1:
            ctx.poly(
                [(xy[0] - 24, xy[1] - 24), (xy[0] - 20, xy[1] + 24), (xy[0] + 20, xy[1] + 24), (xy[0] + 24, xy[1] - 24)],
                a,
                w=1.4,
            )
        elif k == 2:
            ctx.rect(xy[0] - 40, xy[1] - 8, xy[0] + 40, xy[1] + 8, a, w=1.4)
        else:
            ctx.circ(xy, 22, a, w=1.4)
    ctx.glow(c0, 140 * m, m * 0.7)
    ctx.circ(c0, 55 * (1 + 0.06 * hold_wave(u, dur, 1.8)), m, w=2)


def draw_coin_cta(ctx, u, dur, params):
    c0 = _focal(ctx)
    a = eo(R(u, 0, 0.6))
    ctx.glow(c0, 150, a * 0.7)
    ctx.circ(c0, 55, 1, w=2)
    ctx.coin(c0, a, r=22)
    coins_flow(ctx, (ctx.theme.cx, 520), c0, u, 0.4, dur - 0.4, 3, stag=0.5, trav=1.0)


def _type(name, summary, green, params, required, draw) -> SceneType:
    return SceneType(name, summary, green, params, required, draw)


SCENES: dict[str, SceneType] = {
    item.name: item
    for item in (
        _type(
            "bowl_hook",
            "Hook. A bowl draws on with chopsticks and steam, then one green price.",
            "focus",
            {"price": "green figure, e.g. Rp10rb or $25", "note": "optional small white note under the price, e.g. contoh or example"},
            ("price",),
            draw_bowl_hook,
        ),
        _type(
            "coin_drop",
            "One coin drops into the bowl. The label is white. No green.",
            "none",
            {"label": "white sentence under the bowl"},
            ("label",),
            draw_coin_drop,
        ),
        _type(
            "ring_drain",
            "A ring drains while a 22×26 dot grid counts up. The amount and the counter are the same green quantity.",
            "focus",
            {
                "label": "white name beside the ring",
                "amount": "green money figure",
                "count": f"final dot count, max {DOT_CAP}",
                "count_from": "dots already on at the start. Above 0, the ring is fully visible immediately.",
                "unit": "word after the counter, default mangkok",
                "instant": "force the fully-visible ring. Default true when count_from > 0.",
            },
            ("label", "amount", "count"),
            draw_ring_drain,
        ),
        _type(
            "compare",
            "The full dot grid is on. `highlight` dots turn green — the same quantity as the left label. The right label stays white.",
            "focus",
            {
                "total": f"dots on, max {DOT_CAP}",
                "highlight": "how many of those dots turn green",
                "left": "green label, the highlighted quantity",
                "right": "white label, the other quantity",
            },
            ("total", "highlight", "left", "right"),
            draw_compare,
        ),
        _type(
            "highlight",
            "Bars. One bar is brighter white, with an arrow. This emphasis is not green.",
            "none",
            {"heights": "bar heights, default 200,150,110,70", "index": "which bar is emphasized, default 0"},
            (),
            draw_highlight,
        ),
        _type(
            "bowl_cta",
            "Close on the bowl and a white call to action. No green.",
            "none",
            {"label": "short white CTA under the bowl"},
            ("label",),
            draw_bowl_cta,
        ),
        _type(
            "timeline",
            "A dot travels a line toward a date tick. White.",
            "none",
            {"marker": "label under the tick, default jan 1"},
            (),
            draw_timeline,
        ),
        _type(
            "checklist",
            "Boxes draw on and check themselves. White.",
            "none",
            {"count": "number of boxes, default 14 in a 7-column grid"},
            (),
            draw_checklist,
        ),
        _type(
            "jars",
            "Three jars fill to staggered levels. White.",
            "none",
            {"levels": "optional fill fractions. Default is 0.50, 0.65, 0.80."},
            (),
            draw_jars,
        ),
        _type(
            "converge",
            "A coin, a jar, a bar, and a ring meet in one circle. White.",
            "none",
            {},
            (),
            draw_converge,
        ),
        _type(
            "coin_cta",
            "A coin sits in a ring while three more fall in. White. Use for a paycheck close.",
            "none",
            {},
            (),
            draw_coin_cta,
        ),
    )
}


PYTHON_SCENE = {
    "name": "python",
    "summary": "Escape hatch. entry is file.py:draw. draw(ctx, u, duration, params) uses the same Ctx primitives and the green rule.",
    "green": "any",
    "params": {"entry": "path relative to the episode file, then :function", "any other key": "passed through in params"},
    "required": ["entry"],
}


# What an agent should match: the verb, not the topic word.
SENSE: dict[str, dict[str, str]] = {
    "bowl_hook": {
        "verb": "an object draws itself, then one price lands",
        "slide_if": "used as a title card, or the price appears with no object being born",
    },
    "coin_drop": {
        "verb": "one coin falls into the object already on screen",
        "slide_if": "used for any sentence that merely mentions money",
    },
    "ring_drain": {
        "verb": "a figure drains into a count of the same unit; count_from continues a previous count",
        "slide_if": "the grid resets when the sentence is a continuation",
    },
    "compare": {
        "verb": "two counts already shown share one grid",
        "slide_if": "used as a fresh chart for two new ideas",
    },
    "highlight": {
        "verb": "the sentence is a set of bars, one brighter",
        "slide_if": "used for a list, a ranking in words, or growth in general",
    },
    "bowl_cta": {
        "verb": "the opening object returns and asks one thing",
        "slide_if": "used as a text slide with a CTA pasted on",
    },
    "timeline": {
        "verb": "a marker travels to a date that is the subject",
        "slide_if": "used for history, steps, or anything that is not a date",
    },
    "checklist": {
        "verb": "boxes check themselves because the sentence is a checklist",
        "slide_if": "used for tips, reasons, or steps that are not checks",
    },
    "jars": {
        "verb": "vessels fill because the sentence is about filling",
        "slide_if": "used for any comparison of three numbers",
    },
    "converge": {
        "verb": "several distinct things become one",
        "slide_if": "used as a summary slide",
    },
    "coin_cta": {
        "verb": "coins fall into one coin for a paycheck close",
        "slide_if": "used for a generic ending",
    },
    "python": {
        "verb": "the sentence's verb is not in the list above, so you stage it yourself",
        "slide_if": "avoided because writing a scene feels like leaving the template",
    },
}


def catalog() -> list[dict]:
    rows = []
    for scene in SCENES.values():
        row = {
            "name": scene.name,
            "summary": scene.summary,
            "green": scene.green,
            "required": list(scene.required),
            "params": scene.params,
        }
        row.update(SENSE[scene.name])
        rows.append(row)
    python_row = dict(PYTHON_SCENE)
    python_row.update(SENSE["python"])
    rows.append(python_row)
    return rows


def invoke_python(entry: str, episode_dir: str, ctx, u: float, dur: float, params: dict) -> None:
    file_part, sep, func_name = entry.partition(":")
    if not sep or not file_part or not func_name:
        raise GilvyError(f"entry must look like scenes.py:draw, got {entry!r}")
    path = Path(file_part)
    if not path.is_absolute():
        path = Path(episode_dir) / path
    if not path.is_file():
        raise GilvyError(f"custom scene file not found: {path}")
    digest = hashlib.sha1(f"{path}:{path.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    mod_name = f"gilvy_user_{digest}"
    module = sys.modules.get(mod_name)
    if module is None:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            raise GilvyError(f"could not import {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        spec.loader.exec_module(module)
    try:
        fn = getattr(module, func_name)
    except AttributeError as exc:
        raise GilvyError(f"{path} has no function {func_name}") from exc
    try:
        inspect.signature(fn).bind(ctx, u, dur, params)
    except TypeError as exc:
        raise GilvyError(f"{entry} must be callable as draw(ctx, u, duration, params)") from exc
    fn(ctx, u, dur, params)
