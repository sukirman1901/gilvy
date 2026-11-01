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

    def _identity(self) -> bool:
        fit = self.theme.fit
        return fit.scale == 1.0 and fit.ox == 0.0 and fit.oy == 0.0

    def _xy(self, x: float, y: float) -> tuple[float, float]:
        s = self.theme.scale
        if self._identity():
            return x * s, y * s
        mx, my = self.theme.fit.map(x, y)
        return mx * s, my * s

    def _len(self, value: float) -> float:
        s = self.theme.scale
        if self._identity():
            return value * s
        return value * self.theme.fit.scale * s

    def font(self, weight: str, size: float) -> ImageFont.FreeTypeFont:
        fitted = size if self._identity() else size * self.theme.fit.scale
        return load_font(self.theme.fonts(), weight, fitted, self.theme.scale)

    def mix(self, color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
        amount = cl(amount)
        bg = self.theme.bg
        return tuple(int(bg[i] + (color[i] - bg[i]) * amount) for i in range(3))

    def line(self, a, b, al, p=1.0, w=1.6, col=None, k=0.55):
        if al <= 0 or p <= 0:
            return
        if col is None:
            col = self.theme.white
        e = lerp(a, b, p)
        x0, y0 = self._xy(a[0], a[1])
        x1, y1 = self._xy(e[0], e[1])
        self.d.line(
            [x0, y0, x1, y1],
            fill=self.mix(col, al * k),
            width=max(1, int(self._len(w))),
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
        x0, y0 = self._xy(c[0] - r, c[1] - r)
        x1, y1 = self._xy(c[0] + r, c[1] + r)
        bb = [x0, y0, x1, y1]
        if fill is not None:
            self.d.ellipse(bb, fill=self.mix(col, al * fill))
        width = max(1, int(self._len(w)))
        if p >= 1:
            self.d.ellipse(bb, outline=self.mix(col, al), width=width)
        elif p > 0:
            self.d.arc(bb, start, start + 360 * p, fill=self.mix(col, al), width=width)

    def arc(self, c, r, a0, a1, al, w=2, col=None):
        if al <= 0 or a1 <= a0:
            return
        if col is None:
            col = self.theme.white
        x0, y0 = self._xy(c[0] - r, c[1] - r)
        x1, y1 = self._xy(c[0] + r, c[1] + r)
        self.d.arc([x0, y0, x1, y1], a0, a1, fill=self.mix(col, al), width=max(1, int(self._len(w))))

    def rect(self, x0, y0, x1, y1, al, w=1.6, fill=None, p=1.0, k=0.8):
        if al <= 0:
            return
        if fill is not None:
            ax, ay = self._xy(x0, y0)
            bx, by = self._xy(x1, y1)
            self.d.rectangle([ax, ay, bx, by], fill=self.mix(self.theme.white, al * fill))
        if w:
            self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], al, p=p, w=w, k=k)

    def glow(self, c, r, al):
        q = 4
        if self._identity():
            x, y, radius = c[0], c[1], r
        else:
            x, y = self.theme.fit.map(c[0], c[1])
            radius = r * self.theme.fit.scale
        self.gd.ellipse(
            [(x - radius) / q, (y - radius) / q, (x + radius) / q, (y + radius) / q],
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
        x, y = self._xy(xy[0], xy[1])
        self.d.text((x, y), t, font=font, fill=self.mix(col, al), anchor=anchor)

    def coin(self, c, al, r=15):
        if al <= 0:
            return
        self.circ(c, r, al, w=1.8, fill=0.10)
        self.text(c, "$", self.font("Medium", int(r * 1.13)), al)
        if self._identity():
            gx, gy, gr = c[0], c[1], r * 1.6
        else:
            gx, gy = self.theme.fit.map(c[0], c[1])
            gr = r * 1.6 * self.theme.fit.scale
        self.gd.ellipse(
            [(gx - gr) / 4, (gy - gr) / 4, (gx + gr) / 4, (gy + gr) / 4],
            fill=int(45 * cl(al)),
        )

    def bar(self, x, y, w, lvl, al, h=5, k=0.9):
        if al <= 0:
            return
        x0, y0 = self._xy(x - w / 2, y)
        x1, y1 = self._xy(x + w / 2, y + h)
        self.d.rectangle([x0, y0, x1, y1], fill=self.mix(self.theme.white, al * 0.15))
        if lvl > 0:
            fx, fy = self._xy(x - w / 2 + w * cl(lvl), y + h)
            self.d.rectangle([x0, y0, fx, fy], fill=self.mix(self.theme.white, al * k))

    def fillrect(self, x0, y0, x1, y1, lvl, al, k=0.16):
        if al <= 0 or lvl <= 0:
            return
        top = y1 - (y1 - y0) * cl(lvl)
        ax, ay = self._xy(x0, top)
        bx, by = self._xy(x1, y1)
        self.d.rectangle([ax, ay, bx, by], fill=self.mix(self.theme.white, al * k))

    def fillcirc(self, c, r, lvl, al):
        if al <= 0 or lvl <= 0:
            return
        side = self._len(2 * r)
        mask = Image.new("L", (max(1, int(side)), max(1, int(side))), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse([0, 0, side - 1, side - 1], fill=int(255 * 0.16 * al))
        md.rectangle([0, 0, side, int(side * (1 - lvl))], fill=0)
        px, py = self._xy(c[0] - r, c[1] - r)
        self.im.paste(Image.new("RGB", mask.size, self.theme.white), (int(px), int(py)), mask)

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
    ink = ctx.mix(ctx.theme.white, al * 0.05)
    width = 1 if ctx._identity() else max(1, int(ctx._len(0.5)))
    for x in range(108, 920, 81):
        x0, y0 = ctx._xy(x, 330)
        x1, y1 = ctx._xy(x, 1420)
        ctx.d.line([x0, y0, x1, y1], fill=ink, width=width)
    for y in range(330, 1421, 81):
        x0, y0 = ctx._xy(108, y)
        x1, y1 = ctx._xy(918, y)
        ctx.d.line([x0, y0, x1, y1], fill=ink, width=width)


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
