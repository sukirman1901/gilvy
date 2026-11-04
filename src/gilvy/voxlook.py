"""The Vox photographic look: cut-out layers, type, and collage cards.

House episodes never call this. `templates/vox.yaml` names the same palette
and the overlay kinds `headline`, `tag`, `chip`, and `card`.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from gilvy.errors import GilvyError

# Bright, high-contrast swatches measured against the Vox tutorial look:
# red label, orange tag, sky field, white type.
PALETTE = {
    "red": (226, 55, 45),
    "orange": (242, 122, 42),
    "sky": (86, 176, 232),
    "white": (255, 255, 255),
    "ink": (20, 20, 20),
}


def cork_image(width: int, height: int, seed: int = 7) -> Image.Image:
    """A cork board. Warm, speckled, not a flat fill."""
    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    field = rng.integers(0, 40, size=(max(2, height // 6), max(2, width // 6)), dtype=np.uint8)
    grain = np.asarray(
        Image.fromarray(field).resize((width, height), Image.Resampling.BILINEAR),
        np.int16,
    )
    base = np.array([168, 112, 64], np.int16)
    rgb = np.clip(base + grain[:, :, None] - 18, 0, 255).astype(np.uint8)
    speck = rng.random((height, width))
    rgb[speck > 0.985] = (92, 58, 32)
    rgb[speck < 0.01] = (214, 170, 112)
    return Image.fromarray(rgb)


def cutout_subject(image: Image.Image, segment=None) -> tuple[Image.Image, Image.Image]:
    """Split one photo into a foreground cut-out and a filled background.

    `segment` returns an L-mode mask (255 = subject). The default segmenter is
    rembg on CPU (`pip install 'gilvy[cutout]'`). The background keeps the
    original pixels outside the subject and a heavy blur inside the hole, so
    the two layers can parallax without a flat patch.
    """
    rgba = image.convert("RGBA")
    mask = (segment or _rembg_mask)(rgba).convert("L")
    if mask.size != rgba.size:
        mask = mask.resize(rgba.size, Image.Resampling.BILINEAR)
    foreground = rgba.copy()
    foreground.putalpha(mask)
    rgb = rgba.convert("RGB")
    blurred = rgb.filter(ImageFilter.GaussianBlur(radius=28))
    subject = np.asarray(mask, np.float32) / 255.0
    original = np.asarray(rgb, np.float32)
    soft = np.asarray(blurred, np.float32)
    filled = original * (1.0 - subject[:, :, None]) + soft * subject[:, :, None]
    background = Image.fromarray(np.clip(filled, 0, 255).astype(np.uint8))
    return foreground, background


def _rembg_mask(image: Image.Image) -> Image.Image:
    try:
        from rembg import new_session, remove
    except ImportError as exc:
        raise GilvyError(
            "subject cutout needs rembg on CPU: pip install 'gilvy[cutout]'"
        ) from exc
    session = new_session("u2net")
    cut = remove(image.convert("RGBA"), session=session).convert("RGBA")
    return cut.getchannel("A")


def draw_headline(layer: Image.Image, text: str, xy: tuple[float, float], size: int,
                  color: tuple[int, int, int], font_path: str, alpha: int = 255) -> None:
    pen = ImageDraw.Draw(layer)
    font = ImageFont.truetype(font_path, max(8, size))
    pen.text(xy, text, font=font, fill=(*color, alpha))


def draw_tag(layer: Image.Image, text: str, xy: tuple[float, float], size: int,
             fill: tuple[int, int, int], ink: tuple[int, int, int], font_path: str,
             alpha: int = 255) -> None:
    """Orange (or any) rectangular label sitting on the headline."""
    font = ImageFont.truetype(font_path, max(8, size))
    dummy = ImageDraw.Draw(layer)
    box = dummy.textbbox((0, 0), text, font=font)
    pad_x, pad_y = int(size * 0.45), int(size * 0.28)
    width, height = box[2] - box[0] + pad_x * 2, box[3] - box[1] + pad_y * 2
    x, y = int(xy[0]), int(xy[1])
    pen = ImageDraw.Draw(layer)
    pen.rectangle((x, y, x + width, y + height), fill=(*fill, alpha))
    pen.text((x + pad_x - box[0], y + pad_y - box[1]), text, font=font, fill=(*ink, alpha))


def draw_chip(layer: Image.Image, text: str, highlight: str, xy: tuple[float, float],
              size: int, color: tuple[int, int, int], box_color: tuple[int, int, int],
              font_path: str, alpha: int = 255) -> None:
    """White sans line. One word sits on a red or orange box, as in 'this is [bad]'."""
    font = ImageFont.truetype(font_path, max(8, size))
    pen = ImageDraw.Draw(layer)
    x, y = float(xy[0]), float(xy[1])
    gap = size * 0.28
    for word in text.split(" "):
        shown = word
        bbox = pen.textbbox((0, 0), shown, font=font)
        width, height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if word == highlight:
            pad_x, pad_y = int(size * 0.22), int(size * 0.16)
            pen.rectangle(
                (x - pad_x, y - pad_y, x + width + pad_x, y + height + pad_y),
                fill=(*box_color, alpha),
            )
        pen.text((x - bbox[0], y - bbox[1]), shown, font=font, fill=(*color, alpha))
        x += width + gap


def draw_card(layer: Image.Image, card: Image.Image, xy: tuple[float, float],
              size: tuple[int, int], tilt: float, shadow: float) -> None:
    """A photo card, tilted back in perspective, with a drop shadow."""
    width, height = max(8, int(size[0])), max(8, int(size[1]))
    fitted = card.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
    tilted = _perspective(fitted, tilt)
    tw, th = tilted.size
    pad = max(12, int(min(tw, th) * 0.08))
    plate = Image.new("RGBA", (tw + pad * 3, th + pad * 3), (0, 0, 0, 0))
    shade = Image.new("RGBA", plate.size, (0, 0, 0, 0))
    ink = ImageDraw.Draw(shade)
    alpha = int(max(0.0, min(1.0, shadow)) * 150)
    ink.rounded_rectangle(
        (pad + 10, pad + 16, pad + tw + 10, pad + th + 18),
        radius=8,
        fill=(0, 0, 0, alpha),
    )
    shade = shade.filter(ImageFilter.GaussianBlur(radius=6))
    plate.alpha_composite(shade)
    plate.alpha_composite(tilted, (pad, pad))
    x, y = int(xy[0]), int(xy[1])
    canvas = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    canvas.paste(plate, (x, y), plate)
    layer.alpha_composite(canvas)


def _perspective(image: Image.Image, tilt: float) -> Image.Image:
    """Positive tilt foreshortens the top; negative tilt foreshortens the bottom."""
    tilt = max(-18.0, min(18.0, float(tilt)))
    width, height = image.size
    inset = int(round(width * abs(tilt) / 18.0 * 0.16))
    if inset < 1:
        return image.convert("RGBA")
    target = [(inset, 0), (width - 1 - inset, 0), (width - 1, height - 1), (0, height - 1)]
    if tilt < 0:
        target = [(0, 0), (width - 1, 0), (width - 1 - inset, height - 1), (inset, height - 1)]
    source = [(0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1)]
    coeffs = _perspective_coeffs(source, target)
    warped = image.convert("RGBA").transform(
        (width, height), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC,
    )
    return warped


def _perspective_coeffs(source: list[tuple[int, int]], target: list[tuple[int, int]]) -> tuple:
    matrix = []
    vector = []
    for (x, y), (u, v) in zip(target, source):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        vector.extend((u, v))
    solution = np.linalg.lstsq(np.array(matrix, float), np.array(vector, float), rcond=None)[0]
    return tuple(float(n) for n in solution)


def serif_path() -> Path:
    return Path(__file__).resolve().parent / "fonts" / "LiberationSerif-Regular.ttf"


def sans_path(font_dir: str) -> Path:
    return Path(font_dir) / "Poppins-Medium.ttf"
