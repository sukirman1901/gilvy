"""Bottom caption. Poppins Light 52, key words SemiBold, never green unless the word starts with $."""

from __future__ import annotations

from gilvy.draw import Ctx
from gilvy.easing import eo, R
from gilvy.errors import CaptionError


def caption(ctx: Ctx, lines: list[str], keys: list[str], u: float) -> None:
    wi = 0
    lead = ctx.theme.lead
    scale = ctx.theme.scale
    keyset = keys or []
    for li, line in enumerate(lines):
        y = 1290 + li * 78
        words = line.split(" ")
        fonts = [ctx.font("SemiBold", 52) if w in keyset else ctx.font("Light", 52) for w in words]
        space = ctx.font("Light", 52).getlength(" ") / scale
        widths = [font.getlength(word) / scale for font, word in zip(fonts, words)]
        total = sum(widths) + space * (len(words) - 1)
        if not (total < 780 and len(words) <= 5):
            raise CaptionError(
                f"{line!r} is {total:.0f}px wide with {len(words)} words "
                "(max 780px and 5 words). Shorten the line and keep punctuation on the word."
            )
        x = ctx.theme.cx - total / 2
        for word, font, width in zip(words, fonts, widths):
            alpha = eo(R(u, lead + wi * 0.16, lead + wi * 0.16 + 0.5))
            color = ctx.theme.green if word.startswith("$") else ctx.theme.white
            ctx.text((x, y + 14 * (1 - alpha)), word, font, alpha, col=color, anchor="ls")
            x += width + space
            wi += 1


def check_captions(ctx: Ctx, scenes: list[dict]) -> None:
    """Draw every caption at full opacity so a bad line fails before a long render."""
    for index, scene in enumerate(scenes):
        try:
            caption(ctx, scene["caption"], scene["key"], 10)
        except CaptionError as exc:
            label = scene.get("id") or scene["type"]
            raise CaptionError(f"scene {index + 1} ({label}): {exc}") from exc
