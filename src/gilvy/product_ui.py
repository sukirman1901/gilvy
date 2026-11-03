"""Code-drawn product components; no screenshots or network assets required."""

from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

from gilvy.theme import bundled_fonts
from gilvy.product_design import inbox, inbox_part


@lru_cache(maxsize=256)
def font(size: int, weight: str = "Regular"):
    return ImageFont.truetype(
        str(bundled_fonts() / f"Poppins-{weight}.ttf"), max(1, size)
    )


def color(value):
    if not isinstance(value, str):
        raise ValueError("color must be a string")
    return ImageColor.getcolor(value, "RGBA")


def text(draw, xy, value, size=18, fill="#183049", weight="Regular"):
    draw.text(xy, str(value), font=font(size, weight), fill=fill)


def component(node, progress=1.0):
    """Paint at local coordinates. Each panel can be grouped/transformed as a unit."""
    w, h = node["width"], node["height"]
    im = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(im)
    kind = node["type"]
    accent = node.get("accent", "#178cf2")
    if kind == "inbox-part":
        return inbox_part(node["part"], node.get("content"), progress).resize(
            (w, h), Image.Resampling.LANCZOS
        )
    if kind == "panel" and node.get("variant", "inbox") == "inbox":
        return inbox(node.get("content"), progress).resize(
            (w, h), Image.Resampling.LANCZOS
        )
    if kind == "text":
        value = node.get("text", "")
        reveal = node.get("reveal", "none")
        if reveal == "characters":
            value = value[: int(len(value) * progress + 1e-8)]
        elif reveal == "words":
            words = value.split()
            value = " ".join(words[: int(len(words) * progress + 1e-8)])
        size = int(node.get("size", 48))
        f = font(size, node.get("weight", "Regular"))
        box = d.multiline_textbbox((0, 0), value, font=f, spacing=10, align="center")
        x = (w - (box[2] - box[0])) / 2 - box[0]
        y = (h - (box[3] - box[1])) / 2 - box[1]
        d.multiline_text(
            (x, y),
            value,
            font=f,
            fill=node.get("color", "#101e2f"),
            spacing=10,
            align="center",
        )
    elif kind == "rect":
        d.rounded_rectangle(
            (0, 0, w - 1, h - 1),
            radius=node.get("radius", 16),
            fill=node.get("fill", "#ffffff"),
            outline=node.get("border"),
            width=1,
        )
    elif kind == "progress":
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=12, fill=accent)
        text(
            d,
            (20, 10),
            node.get("label", "Learning..."),
            max(12, min(22, h // 4)),
            "white",
        )
        y = h - 18
        d.rounded_rectangle((20, y, w - 20, y + 5), radius=2, fill="#1063a9")
        d.rounded_rectangle(
            (20, y, 20 + max(2, (w - 40) * progress), y + 5), radius=2, fill="white"
        )
    elif kind == "cursor":
        d.polygon(
            [
                (4, 2),
                (4, h - 10),
                (w * 0.35, h * 0.67),
                (w * 0.59, h - 2),
                (w * 0.77, h - 8),
                (w * 0.52, h * 0.56),
                (w - 3, h * 0.52),
            ],
            fill=node.get("color", "#17283b"),
            outline="white",
            width=2,
        )
    elif kind == "menu":
        d.rounded_rectangle(
            (0, 0, w - 1, h - 1), radius=12, fill="#fffffff5", outline="#dbe5f0"
        )
        text(d, (18, 14), node.get("title", "Workspace"), 15, accent, "SemiBold")
        rows = node.get("items", [])
        for i, row in enumerate(rows[: int(progress * len(rows) + 1e-8)]):
            y = 54 + i * 36
            if y + 27 > h:
                break
            if i == node.get("selected", 0):
                d.rounded_rectangle(
                    (10, y - 2, w - 10, y + 28), radius=6, fill="#e5f3ff"
                )
            text(d, (23, y + 3), row, 12)
    elif kind == "panel":
        # Shared frame; content rows remain separately identifiable and readable.
        d.rounded_rectangle(
            (0, 0, w - 1, h - 1),
            radius=18,
            fill=node.get("fill", "#fffffff5"),
            outline="#dbe5f0",
            width=2,
        )
        d.line((0, 58, w, 58), fill="#e7edf5", width=1)
        d.rounded_rectangle((20, 17, 44, 41), radius=7, fill=accent)
        text(d, (27, 17), node.get("mark", "G"), 14, "white", "SemiBold")
        text(d, (56, 18), node.get("brand", "Gilvy"), 17, accent, "SemiBold")
        text(d, (w - 127, 21), node.get("badge", "WORKSPACE"), 9, "#73859a", "SemiBold")
        variant = node.get("variant", "inbox")
        if variant == "form":
            text(d, (25, 78), node.get("title", "Edit workflow"), 23, weight="SemiBold")
            for i, row in enumerate(node.get("items", [])[:3]):
                y = 125 + i * 72
                if y + 60 > h - 55:
                    break
                label, _, value = row.partition(":")
                text(d, (26, y), label, 11, "#72849a")
                d.rounded_rectangle(
                    (24, y + 23, w - 24, y + 61), radius=8, fill="#edf5ff"
                )
                text(d, (37, y + 31), value.strip(), 13)
            d.rounded_rectangle(
                (w - 156, h - 47, w - 24, h - 17), radius=7, fill=accent
            )
            text(
                d,
                (w - 145, h - 42),
                node.get("button", "Save workflow"),
                11,
                "white",
                "SemiBold",
            )
        elif variant == "workflow":
            text(
                d,
                (25, 78),
                node.get("title", "One repeatable workflow"),
                23,
                weight="SemiBold",
            )
            rows = node.get("items", [])[:4]
            visible = min(len(rows), int(progress * len(rows) + 1e-8))
            for i, row in enumerate(rows[:visible]):
                y = 128 + i * 65
                if y + 50 > h:
                    break
                if i:
                    d.line((39, y - 15, 39, y), fill="#bcd9f3", width=2)
                d.ellipse((25, y + 11, 53, y + 39), fill=accent)
                text(d, (34, y + 14), str(i + 1), 12, "white", "SemiBold")
                d.rounded_rectangle((68, y, w - 25, y + 50), radius=9, fill="#eef6ff")
                text(d, (83, y + 15), row, 13)
            if node.get("button"):
                d.rounded_rectangle(
                    (w - 156, h - 47, w - 24, h - 17), radius=7, fill=accent
                )
                text(d, (w - 145, h - 42), node["button"], 11, "white", "SemiBold")
        else:
            raise ValueError(f"unknown panel variant: {variant}")
    else:
        raise ValueError(f"unknown component: {kind}")
    return im
