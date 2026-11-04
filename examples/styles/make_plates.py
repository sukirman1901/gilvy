"""Procedural stand-in plates for the style samples. Not frames from the references."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent


def _save(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, optimize=True)


def history() -> None:
    year = Image.new("RGB", (1080, 1920), (92, 64, 46))
    pen = ImageDraw.Draw(year)
    for y in range(1920):
        tone = 70 + int(50 * y / 1920)
        pen.line([(0, y), (1080, y)], fill=(tone + 30, tone, tone - 10))
    pen.rounded_rectangle((180, 280, 900, 1280), radius=24, outline=(48, 32, 22), width=28)
    pen.ellipse((340, 460, 740, 980), fill=(62, 48, 40))
    _save(ROOT / "history" / "year.png", year)

    board = Image.new("RGB", (1080, 1920), (92, 70, 48))
    pen = ImageDraw.Draw(board)
    pen.rectangle((140, 220, 940, 1500), fill=(164, 132, 90))
    for box in ((220, 340, 520, 720), (520, 420, 860, 860), (260, 860, 700, 1320)):
        pen.rectangle(box, fill=(214, 204, 186), outline=(120, 90, 60))
    _save(ROOT / "history" / "board.png", board)

    street = Image.new("RGB", (1080, 1920), (48, 36, 28))
    pen = ImageDraw.Draw(street)
    pen.polygon([(540, 180), (760, 980), (320, 980)], fill=(86, 70, 56))
    pen.rectangle((470, 980, 620, 1500), fill=(36, 32, 30))
    pen.rectangle((0, 1500, 1080, 1920), fill=(62, 48, 36))
    _save(ROOT / "history" / "street.png", street)


def vox() -> None:
    bg = Image.new("RGB", (1080, 1920), (58, 72, 86))
    pen = ImageDraw.Draw(bg)
    pen.rectangle((0, 0, 1080, 720), fill=(168, 186, 196))
    pen.rectangle((80, 780, 1000, 1680), fill=(42, 48, 56))
    _save(ROOT / "vox" / "bg.png", bg)

    mid = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    pen = ImageDraw.Draw(mid)
    pen.ellipse((390, 620, 690, 980), fill=(196, 122, 86, 255))
    pen.rounded_rectangle((430, 960, 650, 1460), radius=40, fill=(48, 56, 64, 255))
    _save(ROOT / "vox" / "mid.png", mid)

    fg = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    pen = ImageDraw.Draw(fg)
    pen.rectangle((0, 1420, 1080, 1920), fill=(28, 30, 34, 255))
    pen.rectangle((120, 1320, 420, 1460), fill=(70, 74, 78, 255))
    _save(ROOT / "vox" / "fg.png", fg)

    article = Image.new("RGB", (1080, 1920), (218, 214, 206))
    pen = ImageDraw.Draw(article)
    pen.rectangle((120, 280, 960, 420), fill=(48, 48, 48))
    y = 520
    for width in (760, 820, 700, 800, 640, 780, 720):
        pen.rectangle((140, y, 140 + width, y + 28), fill=(90, 90, 90))
        y += 70
    _save(ROOT / "vox" / "article.png", article)


if __name__ == "__main__":
    history()
    vox()
