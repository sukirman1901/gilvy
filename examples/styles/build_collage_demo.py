"""Make procedural diagnostic assets; these are not generated art or a reference match."""
import argparse
from pathlib import Path
import shutil

from PIL import Image, ImageDraw


def build(output):
    root = Path(output).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=False)
    assets = root / 'collage-assets'
    assets.mkdir()
    im = Image.new('RGB', (1080, 1920), '#e6decd')
    pen = ImageDraw.Draw(im)
    for y in range(0, 1920, 32):
        pen.line((0, y, 1080, y), fill='#e3daca', width=1)
    im.save(assets / 'paper.png')
    im = Image.new('RGB', (590, 960), '#899a98')
    pen = ImageDraw.Draw(im)
    pen.polygon([(0, 650), (180, 290), (430, 700)], fill='#4f6664')
    pen.polygon([(190, 800), (440, 350), (590, 700), (590, 960), (0, 960)], fill='#394d49')
    pen.ellipse((60, 100, 180, 220), fill='#d6c5a0')
    im.save(assets / 'photo.png')
    Image.new('RGB', (700, 1100), '#faf5e8').save(assets / 'page.png')
    spec = Path(__file__).with_name('editorial-collage.yaml')
    shutil.copyfile(spec, root / spec.name)
    return root / spec.name


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='new directory for the diagnostic')
    print(build(parser.parse_args().out))
