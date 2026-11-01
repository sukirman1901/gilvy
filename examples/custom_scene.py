"""Escape hatch used by examples/custom.yaml.

The ring draws on in the first beat. The coin then travels for most of the
scene, and the price finishes as the sentence settles. Copy this timing when
the library has no verb for the line.
"""

from gilvy.easing import R, eio, eo, lerp


def draw(ctx, u, duration, params):
    appear = eo(R(u, 0, 0.6))
    travel = eio(R(u, 0.3, max(1.4, duration * 0.65)))
    center = (ctx.theme.cx, 780)
    ctx.glow(center, 140, appear * 0.55)
    ctx.circ(center, 78, appear, w=2)
    ctx.coin(lerp((ctx.theme.cx, 420), center, travel), appear, r=18)
    ctx.money(
        (ctx.theme.cx, 980),
        str(params.get("price", "$25")),
        eo(R(u, duration * 0.35, max(1.6, duration * 0.65))),
        sz=34,
        ex=True,
    )
