"""Vox photographic look: cut-out layers, type, and collage cards."""

from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

from gilvy.episode import load_episode
from gilvy.errors import GilvyError
from gilvy.image_scene import render_image_frame
from gilvy.theme import Theme
from gilvy.formats import Fit
from gilvy.voxlook import PALETTE, cork_image, cutout_subject

ROOT = Path(__file__).resolve().parents[1]


def _theme():
    return Theme(width=320, height=560, fps=20, scale=1, fit=Fit(), intro=0, outro=0)


def test_cork_is_speckled_and_the_palette_is_the_template():
    cork = np.asarray(cork_image(200, 120, seed=3))
    assert cork.std() > 8
    assert cork[:, :, 0].mean() > cork[:, :, 2].mean()
    template = yaml.safe_load((ROOT / "templates" / "vox.yaml").read_text())
    assert template["look"]["palette"]["red"] == "#e2372d"
    assert template["look"]["palette"]["orange"] == "#f27a2a"
    assert template["look"]["palette"]["sky"] == "#56b0e8"
    assert template["look"]["headline"]["font"] == "serif"
    assert template["look"]["card"]["tilt"] == 8
    assert PALETTE["red"] == (226, 55, 45)
    assert PALETTE["orange"] == (242, 122, 42)


def test_cutout_uses_the_supplied_mask_and_fills_the_hole(tmp_path):
    image = Image.new("RGBA", (80, 80), (20, 40, 160, 255))
    ImageDraw.Draw(image).rectangle((30, 20, 55, 60), fill=(220, 30, 30, 255))

    def segment(_image):
        mask = Image.new("L", (80, 80), 0)
        ImageDraw.Draw(mask).rectangle((30, 20, 55, 60), fill=255)
        return mask

    foreground, background = cutout_subject(image, segment=segment)
    alpha = np.asarray(foreground.getchannel("A"))
    assert alpha[10, 10] == 0
    assert alpha[40, 40] == 255
    # The subject hole in the background is no longer the flat red.
    back = np.asarray(background)
    assert int(back[40, 40, 0]) < 180


def test_missing_rembg_names_the_extra(tmp_path):
    image = Image.new("RGB", (16, 16), (10, 10, 10))
    try:
        import rembg  # noqa: F401
    except ImportError:
        with pytest.raises(GilvyError, match="gilvy\\[cutout\\]"):
            cutout_subject(image)
    else:
        pytest.skip("rembg is installed; the missing-extra path is covered by the message")


def test_vox_type_and_tilted_card_render(tmp_path):
    card = Image.new("RGB", (80, 110), (220, 30, 30))
    card.save(tmp_path / "card.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: look
style: vox-explainer
audio_mode: silent
scenes:
  - type: image
    caption: ["look"]
    min: 1.2
    backdrop: cork
    grade: none
    grain: 0
    paper: 0
    camera:
      from: {scale: 1.0, x: -8, y: 0}
      to: {scale: 1.03, x: 8, y: 0}
    overlays:
      - kind: tag
        text: LABEL
        x: 24
        y: 36
        size: 22
      - kind: headline
        text: Salt
        x: 24
        y: 80
        size: 48
      - kind: chip
        text: "this is bad"
        highlight: bad
        x: 24
        y: 460
        size: 22
      - kind: card
        src: card.png
        x: 70
        y: 150
        w: 120
        h: 160
        tilt: 12
        shadow: 0.8
""", encoding="utf-8")
    episode = load_episode(path)
    scene = {
        "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["look"],
        "key": [], "style": "vox-explainer",
    }
    frame = render_image_frame(_theme(), scene, 0.6, 1.2, str(tmp_path))
    orange = (frame[:, :, 0] > 200) & (frame[:, :, 1] > 80) & (frame[:, :, 1] < 170) & (frame[:, :, 2] < 80)
    red_box = (frame[:, :, 0] > 190) & (frame[:, :, 1] < 90) & (frame[:, :, 2] < 80)
    assert int(orange.sum()) > 40
    assert int(red_box.sum()) > 20
    # The card's top edge is foreshortened: fewer red pixels than the bottom edge.
    card_band = red_box[160:340]
    red_rows = np.where(card_band.any(axis=1))[0]
    assert len(red_rows) > 10
    top = int(card_band[red_rows[2]].sum())
    bottom = int(card_band[red_rows[-3]].sum())
    assert top < bottom
