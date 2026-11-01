"""Escape hatch used by examples/custom.yaml."""

from gilvy.easing import R, eo


def draw(ctx, u, duration, params):
    alpha = eo(R(u, 0, 0.6))
    center = (ctx.theme.cx, 780)
    ctx.glow(center, 140, alpha * 0.55)
    ctx.circ(center, 64, alpha, w=2)
    ctx.money((ctx.theme.cx, 980), str(params.get("price", "$25")), alpha, sz=34, ex=True)
