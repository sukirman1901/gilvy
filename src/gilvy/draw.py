"""Frame drawing. User-space pixels, painted at 2x and composited with a white glow.

The method bodies match the proven renderer. Change a scene, not these formulas,
if a frame looks wrong.
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gilvy.easing import cl, eio, R, lerp
from gilvy.theme import Theme

_FONTS: dict[tuple, ImageFont.FreeTypeFont] = {}


def clear_font_cache() -> None:
    _FONTS.clear()


def load_font(font_dir: str, weight: str, size: float, scale: int) -> ImageFont.FreeTypeFont:
    key = (font_dir, weight, size, scale)
    font = _FONTS.get(key)
    if font is None:
        path = f"{font_dir}/Poppins-{weight}.ttf"
        font = ImageFont.truetype(path, int(size * scale))
        _FONTS[key] = font
    return font


class Ctx:
    """One supersampled frame plus a quarter-res glow mask."""

    def __init__(self, theme: Theme):
        self.theme = theme
        s = theme.scale
        self.im = Image.new("RGB", (theme.width * s, theme.height * s), theme.bg)
        self.d = ImageDraw.Draw(self.im)
        self.g = Image.new("L", (theme.width // 4, theme.height // 4), 0)
        self.gd = ImageDraw.Draw(self.g)

    def font(self, weight: str, size: float) -> ImageFont.FreeTypeFont:
        return load_font(self.theme.fonts(), weight, size, self.theme.scale)

    def mix(self, color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
        amount = cl(amount)
        bg = self.theme.bg
        return tuple(int(bg[i] + (color[i] - bg[i]) * amount) for i in range(3))

    def line(self, a, b, al, p=1.0, w=1.6, col=None, k=0.55):
        if al <= 0 or p <= 0:
            return
        if col is None:
            col = self.theme.white
        s = self.theme.scale
        e = lerp(a, b, p)
        self.d.line(
            [a[0] * s, a[1] * s, e[0] * s, e[1] * s],
            fill=self.mix(col, al * k),
            width=max(1, int(w * s)),
        )

    def poly(self, pts, al, p=1.0, w=1.6, k=0.7):
        # draw-on polyline by arclength
        if al <= 0 or p <= 0:
            return
        lengths = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        goal = sum(lengths) * p
        acc = 0.0
        for i, length in enumerate(lengths):
            if acc >= goal:
                break
            q = min(1, (goal - acc) / length) if length else 1
            self.line(pts[i], pts[i + 1], al, p=q, w=w, k=k)
            acc += length

    def circ(self, c, r, al, w=1.6, p=1.0, fill=None, col=None, start=-90):
        if al <= 0 or r <= 0:
            return
        if col is None:
            col = self.theme.white
        s = self.theme.scale
        bb = [(c[0] - r) * s, (c[1] - r) * s, (c[0] + r) * s, (c[1] + r) * s]
        if fill is not None:
            self.d.ellipse(bb, fill=self.mix(col, al * fill))
        width = max(1, int(w * s))
        if p >= 1:
            self.d.ellipse(bb, outline=self.mix(col, al), width=width)
        elif p > 0:
            self.d.arc(bb, start, start + 360 * p, fill=self.mix(col, al), width=width)

    def arc(self, c, r, a0, a1, al, w=2, col=None):
        if al <= 0 or a1 <= a0:
            return
        if col is None:
            col = self.theme.white
        s = self.theme.scale
        bb = [(c[0] - r) * s, (c[1] - r) * s, (c[0] + r) * s, (c[1] + r) * s]
        self.d.arc(bb, a0, a1, fill=self.mix(col, al), width=max(1, int(w * s)))

    def rect(self, x0, y0, x1, y1, al, w=1.6, fill=None, p=1.0, k=0.8):
        if al <= 0:
            return
        s = self.theme.scale
        if fill is not None:
            self.d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], fill=self.mix(self.theme.white, al * fill))
        if w:
            self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], al, p=p, w=w, k=k)

    def glow(self, c, r, al):
        q = 4
        self.gd.ellipse(
            [(c[0] - r) / q, (c[1] - r) / q, (c[0] + r) / q, (c[1] + r) / q],
            fill=int(90 * cl(al)),
        )

    def dot(self, c, r, al, glow=True):
        if al <= 0:
            return
        self.circ(c, r, al, fill=1.0)
        if glow:
            self.glow(c, r * 2.2, al)

    def text(self, xy, t, font, al, col=None, anchor="mm"):
        if al <= 0:
            return
        if col is None:
            col = self.theme.white
        s = self.theme.scale
        self.d.text((xy[0] * s, xy[1] * s), t, font=font, fill=self.mix(col, al), anchor=anchor)

    def coin(self, c, al, r=15):
        if al <= 0:
            return
        self.circ(c, r, al, w=1.8, fill=0.10)
        self.text(c, "$", self.font("Medium", int(r * 1.13)), al)
        self.gd.ellipse(
            [(c[0] - r * 1.6) / 4, (c[1] - r * 1.6) / 4, (c[0] + r * 1.6) / 4, (c[1] + r * 1.6) / 4],
            fill=int(45 * cl(al)),
        )

    def bar(self, x, y, w, lvl, al, h=5, k=0.9):
        if al <= 0:
            return
        s = self.theme.scale
        self.d.rectangle([(x - w / 2) * s, y * s, (x + w / 2) * s, (y + h) * s], fill=self.mix(self.theme.white, al * 0.15))
        if lvl > 0:
            self.d.rectangle(
                [(x - w / 2) * s, y * s, (x - w / 2 + w * cl(lvl)) * s, (y + h) * s],
                fill=self.mix(self.theme.white, al * k),
            )

    def fillrect(self, x0, y0, x1, y1, lvl, al, k=0.16):
        if al <= 0 or lvl <= 0:
            return
        s = self.theme.scale
        top = y1 - (y1 - y0) * cl(lvl)
        self.d.rectangle([x0 * s, top * s, x1 * s, y1 * s], fill=self.mix(self.theme.white, al * k))

    def fillcirc(self, c, r, lvl, al):
        if al <= 0 or lvl <= 0:
            return
        s = self.theme.scale
        mask = Image.new("L", (int(2 * r * s), int(2 * r * s)), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([0, 0, 2 * r * s - 1, 2 * r * s - 1], fill=int(255 * 0.16 * al))
        md.rectangle([0, 0, 2 * r * s, int(2 * r * s * (1 - lvl))], fill=0)
        self.im.paste(Image.new("RGB", mask.size, self.theme.white), (int((c[0] - r) * s), int((c[1] - r) * s)), mask)

    def check(self, c, al, p, sz=12):
        self.poly(
            [(c[0] - sz, c[1]), (c[0] - sz * 0.3, c[1] + sz * 0.7), (c[0] + sz, c[1] - sz * 0.8)],
            al,
            p=p,
            w=2.2,
            k=1,
        )

    def money(self, xy, val, al, sz=34, ex=True, anchor="mm", exdy=34, example="example"):
        self.text(xy, val, self.font("Medium", sz), al, col=self.theme.green, anchor=anchor)
        if ex:
            self.text((xy[0], xy[1] + exdy), example, self.font("Light", 20), al * 0.6, anchor=anchor)

    def label(self, xy, t, al, sz=22, w="Regular", anchor="mm"):
        self.text(xy, t, self.font(w, sz), al * 0.85, anchor=anchor)


def grid(ctx: Ctx, al: float = 1) -> None:
    s = ctx.theme.scale
    ink = ctx.mix(ctx.theme.white, al * 0.05)
    for x in range(108, 920, 81):
        ctx.d.line([x * s, 330 * s, x * s, 1420 * s], fill=ink, width=1)
    for y in range(330, 1421, 81):
        ctx.d.line([108 * s, y * s, 918 * s, y * s], fill=ink, width=1)


def coins_flow(ctx, a, b, u, t0, t1, n, al=1, stag=0.4, trav=1.0, r=15, path=None):
    for k in range(n):
        s0 = t0 + k * stag
        if s0 > t1:
            break
        p = R(u, s0, s0 + trav)
        if 0 < p < 1:
            pos = lerp(a, b, eio(p)) if path is None else path(eio(p))
            ctx.coin(pos, al * min(1, p * 6, (1 - p) * 6), r=r)


def compose(ctx: Ctx):
    """Downsample the 2x plate and add the blurred glow. Returns float32 RGB."""
    import numpy as np

    w, h = ctx.theme.width, ctx.theme.height
    im = ctx.im.resize((w, h), Image.LANCZOS)
    glow = ctx.g.filter(ImageFilter.GaussianBlur(5)).resize((w, h), Image.BILINEAR)
    return np.clip(np.asarray(im, np.float32) + np.asarray(glow, np.float32)[..., None] * 0.55, 0, 255)
