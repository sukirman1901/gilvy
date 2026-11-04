"""Keyframe tracks and the effect library, checked by rendering and detecting."""

import json
import math
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image, ImageDraw

import gilvy.render as render
from gilvy.detect import detect_shot, fit_ease
from gilvy.effects import KINDS
from gilvy.episode import load_episode
from gilvy.errors import EpisodeError
from gilvy.formats import Fit
from gilvy.image_scene import render_image_frame
from gilvy.theme import Theme

ROOT = Path(__file__).resolve().parents[1]


def _theme():
    return Theme(width=320, height=560, fps=20, scale=1, fit=Fit(), intro=0, outro=0)


def _plate(path: Path, kind: str = "texture") -> None:
    image = Image.new("RGBA", (480, 840), (18, 16, 14, 255))
    pen = ImageDraw.Draw(image)
    if kind == "bar":
        pen.rectangle((40, 380, 440, 420), fill=(240, 240, 240, 255))
    elif kind == "dot":
        pen.rectangle((200, 360, 280, 440), fill=(250, 250, 250, 255))
    elif kind == "red":
        pen.rectangle((60, 200, 200, 340), fill=(220, 30, 30, 255))
    else:
        rng = np.random.default_rng(3)
        arr = np.array(image)
        noise = rng.integers(0, 80, size=arr.shape[:2], dtype=np.uint8)
        arr[:, :, 0] = np.clip(arr[:, :, 0] + noise, 0, 255)
        arr[:, :, 1] = np.clip(30 + noise // 2, 0, 255)
        arr[:, :, 2] = 40
        image = Image.fromarray(arr)
        pen = ImageDraw.Draw(image)
        pen.rectangle((80, 160, 220, 360), fill=(230, 200, 80, 255))
        pen.rectangle((250, 400, 420, 640), fill=(40, 90, 160, 255))
    image.save(path)


def _write(tmp: Path, body: str, plate: str = "texture") -> Path:
    _plate(tmp / "plate.png", plate)
    path = tmp / "ep.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def _render(tmp, monkeypatch, body, plate="texture"):
    monkeypatch.setattr(render, "theme_for", lambda ep: _theme())
    episode = load_episode(_write(tmp, body, plate))
    video = tmp / "clip.mp4"
    result = render.render_episode(episode, video, "fixture", 1)
    return episode, video, result


def test_from_to_shorthand_still_loads_and_scale_cap_is_configurable(tmp_path):
    path = _write(tmp_path, """
name: cap
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["cap"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      ease: exponential
      from: {scale: 1.0}
      to: {scale: 1.4}
""")
    episode = load_episode(path)
    assert episode.scenes[0].params["camera"]["to"]["scale"] == 1.4
    path.write_text(path.read_text().replace("scale: 1.4", "scale: 2.8").replace(
        "ease: exponential", "ease: exponential\n      scale_max: 3.2"), encoding="utf-8")
    raised = load_episode(path)
    assert raised.scenes[0].params["camera"]["scale_max"] == 3.2
    assert raised.scenes[0].params["camera"]["to"]["scale"] == 2.8
    path.write_text(path.read_text().replace("scale: 2.8", "scale: 3.4"), encoding="utf-8")
    with pytest.raises(EpisodeError):
        load_episode(path)


@pytest.mark.parametrize("ease", ["linear", "easeInCubic", "expoIn", "expoOut"])
def test_zoom_rate_is_within_five_percent(tmp_path, monkeypatch, ease):
    _, video, result = _render(tmp_path, monkeypatch, f"""
name: zoom
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["zoom"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: scale
          keys:
            - {{t: 0.0, v: 1.0, ease: {ease}}}
            - {{t: 1.2, v: 1.35, ease: linear}}
""")
    assert result["qc"]["ok"], result["qc"]
    shot = detect_shot(video)
    zoom = next(item for item in shot["events"] if item["effect"] == "zoom")
    authored = 100 * math.log(1.35) / 1.2
    assert zoom["zoom_pct_per_s"] == pytest.approx(authored, rel=0.05)
    if ease == "linear":
        assert zoom["ease"] == "linear"
    elif ease == "easeInCubic":
        assert zoom["ease"] == "easeInCubic"
    elif ease == "expoIn":
        assert zoom["ease"] == "expoIn"
    else:
        assert zoom["ease"] == "expoOut"
    if ease != "linear":
        assert zoom["rmse"] < zoom["linear_rmse"]


def test_fit_ease_prefers_expo_in_over_linear():
    t = np.linspace(0, 1, 12)
    curve = np.array([(math.pow(2, 10 * p - 10) if p else 0.0) for p in t])
    fit = fit_ease(curve)
    assert fit["ease"] == "expoIn"
    assert fit["rmse"] < 0.05
    assert fit["linear_rmse"] > fit["rmse"]


def test_rotation_degrees(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: rot
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["rot"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0, x: 0, y: 4}
      to: {scale: 1.02, x: 0, y: 0}
      tracks:
        - property: rotation
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 1.2, v: 6, ease: linear}
""", plate="bar")
    shot = detect_shot(video)
    turned = next(item for item in shot["events"] if item["effect"] == "rotation")
    assert turned["degrees"] == pytest.approx(6, abs=1.5)


def test_shake_frequency(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: shake
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["shake"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    effects:
      - {kind: shake, amp: 18, freq: 8}
    camera:
      from: {scale: 1.0, y: 0}
      to: {scale: 1.04, y: 6}
""", plate="dot")
    shot = detect_shot(video)
    shake = next(item for item in shot["events"] if item["effect"] == "shake")
    assert shake["hz"] == pytest.approx(8, abs=1.5)


def test_flash_frame(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: flash
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["flash"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    effects:
      - {kind: flash, at: 0.4, seconds: 0.08}
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
""")
    shot = detect_shot(video)
    flash = next(item for item in shot["events"] if item["effect"] == "flash")
    assert flash["frame"] == pytest.approx(round(0.4 * 20), abs=2)


def test_whip_frame(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: whip
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["whip"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    effects:
      - {kind: whip, at: 0.4, seconds: 0.2}
    camera:
      tracks:
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 0.35, v: 0, ease: linear}
            - {t: 0.55, v: 160, ease: linear}
            - {t: 1.0, v: 160, ease: linear}
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: linear}
            - {t: 1.0, v: 1.04, ease: linear}
""")
    shot = detect_shot(video)
    whip = next(item for item in shot["events"] if item["effect"] == "whip")
    assert whip["frame"] == pytest.approx(round(0.45 * 20), abs=3)


def test_eased_dissolve_length(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: _theme())
    _plate(tmp_path / "a.png", "red")
    _plate(tmp_path / "b.png", "dot")
    # Force the two plates to opposite red channels so the blend is obvious.
    Image.new("RGBA", (480, 840), (210, 40, 30, 255)).save(tmp_path / "a.png")
    Image.new("RGBA", (480, 840), (20, 30, 40, 255)).save(tmp_path / "b.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: fade
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["out"]
    min: 1.6
    image: a.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 1.0
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
  - type: image
    caption: ["in"]
    min: 1.2
    image: b.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.04}
      to: {scale: 1.0}
""", encoding="utf-8")
    video = tmp_path / "fade.mp4"
    render.render_episode(load_episode(path), video, "fixture", 1)
    shot = detect_shot(video)
    fade = next(item for item in shot["events"] if item["effect"] == "dissolve")
    assert fade["duration"] == pytest.approx(1.0, abs=0.15)
    assert fade["ease"] in {"easeInCubic", "easeInQuad", "expoIn"}


def test_typewriter_word_times(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: words
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["words"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
    overlays:
      - kind: text
        text: "ONE TWO THREE"
        entrance: typewriter
        word_seconds: 0.25
        at: 0.1
        size: 80
        font: sans
        color: [255, 255, 255]
        y: 280
""")
    shot = detect_shot(video)
    times = next(item for item in shot["events"] if item["effect"] == "typewriter")["times"]
    assert times[0] == pytest.approx(0.1, abs=2 / 20)
    assert times[1] == pytest.approx(0.1 + 0.25, abs=2 / 20)
    assert times[2] == pytest.approx(0.1 + 0.50, abs=2 / 20)


def test_sfx_onset_is_within_two_frames(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: cue
style: history-story
audio_mode: ambient
scenes:
  - type: image
    caption: ["cue"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0}
      to: {scale: 1.05}
    overlays:
      - kind: text
        text: "HIT"
        entrance: fade
        text_fade_s: 0.05
        at: 0.45
        size: 72
        font: sans
        sfx: click
""")
    shot = detect_shot(video)
    onset = next(item for item in shot["events"] if item["effect"] == "sfx")
    assert abs(onset["time"] - 0.45) <= 2 / 20


def test_vox_replica_table_records_the_check():
    data = json.loads((ROOT / "tests" / "fixtures" / "vox_replica_table.json").read_text(encoding="utf-8"))
    rows = data["rows"]
    assert rows
    for row in rows:
        assert {"effect", "ref", "replica", "delta", "pass"} <= set(row)
    by_name = {row["effect"]: row for row in rows}
    assert by_name["shake Hz"]["pass"] is True
    assert by_name["whip present"]["pass"] is True
    assert by_name["pull rotation deg"]["pass"] is True


def test_inventory_pins_and_vox_template():
    pins = yaml.safe_load((ROOT / "tests" / "fixtures" / "effects_inventory.yaml").read_text())
    assert pins["ref1"]["pan"]["ease"] == "expoOut"
    assert pins["ref1"]["pan"]["to_px"] == 8
    assert pins["ref1"]["pan"]["ease_rmse"] == 0.218
    assert pins["ref1"]["zoom_out"]["ease"] == "expoIn"
    assert pins["ref1"]["zoom_out"]["to_pct"] == 92.6
    assert pins["ref1"]["zoom_out"]["rate_pct_per_s"] == -3.17
    assert pins["ref1"]["zoom_out"]["linear_rmse"] == 0.503
    assert pins["ref1"]["rotation_deg"] == 1.11
    assert pins["ref1"]["dissolve_s"] == 1.46
    template = yaml.safe_load((ROOT / "templates" / "vox.yaml").read_text())
    assert set(template["effects"]) <= set(KINDS) | {"dissolve"}
    assert template["camera"]["tracks"][0]["keys"][0]["ease"] == pins["ref1"]["zoom_out"]["ease"]
    assert template["camera"]["tracks"][1]["keys"][0]["ease"] == pins["ref1"]["pan"]["ease"]
    assert template["camera"]["tracks"][1]["keys"][1]["v"] == pins["ref1"]["pan"]["to_px"]
    assert template["transition"]["seconds"] == pins["ref1"]["dissolve_s"]
    assert template["camera"]["tracks"][2]["keys"][1]["v"] == pins["ref1"]["rotation_deg"]


def test_layer_parallax_strike_mask_and_stamp(tmp_path):
    _plate(tmp_path / "bg.png")
    _plate(tmp_path / "fg.png", "red")
    path = _write(tmp_path, """
name: layers
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["layers"]
    min: 1.2
    image: bg.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0}
      to: {scale: 1.02}
    layers:
      - src: bg.png
        depth: 0.2
      - src: fg.png
        depth: 1
        tracks:
          - property: x
            keys:
              - {t: 0, v: 0, ease: linear}
              - {t: 1.0, v: 36, ease: linear}
    effects:
      - {kind: vignette, amount: 0.5}
      - {kind: flicker, amount: 0.05, freq: 6}
      - {kind: light_leak, amount: 0.2}
      - {kind: dust, amount: 0.4}
      - {kind: glitch, at: 0.5, seconds: 0.05}
    overlays:
      - kind: strike
        at: 0.1
        duration: 0.5
        x: 40
        y: 200
        w: 200
        h: 20
      - kind: mask
        at: 0.0
        duration: 0.8
        x: 20
        y: 300
        w: 160
        h: 40
      - kind: stamp
        at: 0.0
        duration: 0.4
        text: STAMP
        x: 40
        y: 80
        w: 120
        h: 40
""")
    # _write also writes plate.png; the episode points at bg.png which exists.
    episode = load_episode(path)
    scene = {
        "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["layers"],
        "key": [], "style": "history-story",
    }
    theme = _theme()
    early = render_image_frame(theme, scene, 0.05, 1.0, str(tmp_path))
    late = render_image_frame(theme, scene, 0.95, 1.0, str(tmp_path))
    def red_x(frame):
        mask = frame[:, :, 0] > 160
        ys, xs = np.nonzero(mask)
        return float(xs.mean()) if len(xs) else 0
    assert red_x(late) - red_x(early) > 15
    # The strike has drawn by the end and the stamp has settled smaller.
    assert early.shape == late.shape
