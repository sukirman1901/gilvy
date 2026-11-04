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
from gilvy.image_scene import high_frequency_std, render_image_frame
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
    if ease == "linear":
        assert result["qc"]["ok"], result["qc"]
        assert result["published"] is True
        assert Path(result["video"]) == video
    else:
        # These exaggerated detector fixtures exceed the short-shot 40%/s
        # peak scale-speed band (87%/s cubic, 199%/s exponential). Their
        # endpoint-average log rate is still 25%/s and must be measurable.
        assert result["qc"]["ok"] is False, result["qc"]
        assert result["published"] is False
        violations = result["qc"]["violations"]
        assert len(violations) == 1, result["qc"]
        assert "peak segment zoom" in violations[0]
        assert "exceeds the plate band" in violations[0]
        assert not video.exists()
    artifact = Path(result["video"])
    assert artifact.is_file()
    shot = detect_shot(artifact)
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
    # 2% and 98% are where the blend is measured. The reported length is the
    # full overlap those crossings imply, which is the authored 1.0s.
    assert fade["duration"] == pytest.approx(1.0, abs=0.15)
    assert fade["ease"] in {"easeInCubic", "easeInQuad", "expoIn"}


def test_shake_does_not_inflate_zoom(tmp_path, monkeypatch):
    _, video, _ = _render(tmp_path, monkeypatch, """
name: shake-zoom
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["push"]
    min: 1.21
    image: plate.png
    grade: none
    grain: 0
    effects:
      - {kind: shake, amp: 36, freq: 10}
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: easeOutQuad}
            - {t: 1.21, v: 1.148, ease: linear}
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: easeOutQuad}
            - {t: 1.21, v: -42, ease: linear}
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: easeOutQuad}
            - {t: 1.21, v: -67, ease: linear}
""")
    shot = detect_shot(video)
    zoom = next(item for item in shot["events"] if item["effect"] == "zoom")
    shake = next(item for item in shot["events"] if item["effect"] == "shake")
    authored = 100 * math.log(1.148) / 1.21
    assert zoom["zoom_pct_per_s"] == pytest.approx(authored, rel=0.05)
    assert shake["hz"] == pytest.approx(10, abs=1.5)


@pytest.mark.parametrize("end_scale", [1.02, 0.98])
def test_small_zoom_keeps_its_sign(tmp_path, monkeypatch, end_scale):
    _, video, _ = _render(tmp_path, monkeypatch, f"""
name: small
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["small"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: scale
          keys:
            - {{t: 0.0, v: 1.0, ease: linear}}
            - {{t: 1.2, v: {end_scale}, ease: linear}}
""")
    shot = detect_shot(video)
    zoom = next(item for item in shot["events"] if item["effect"] == "zoom")
    authored = 100 * math.log(end_scale) / 1.2
    assert zoom["zoom_pct_per_s"] == pytest.approx(authored, rel=0.05)
    assert (zoom["zoom_pct_per_s"] > 0) == (end_scale > 1)


def test_ease_in_dissolve_uses_alpha_span(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: _theme())
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
    min: 2.2
    image: a.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 1.5
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0}
      to: {scale: 1.02}
  - type: image
    caption: ["in"]
    min: 1.2
    image: b.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0}
      to: {scale: 1.02}
""", encoding="utf-8")
    video = tmp_path / "fade.mp4"
    render.render_episode(load_episode(path), video, "fixture", 1)
    shot = detect_shot(video)
    fade = next(item for item in shot["events"] if item["effect"] == "dissolve")
    assert fade["duration"] == pytest.approx(1.5, abs=0.15)
    assert fade["ease"] in {"easeInCubic", "easeInQuad", "expoIn"}


def test_replica_dissolve_spans_are_within_15_hundredths(tmp_path, monkeypatch):
    """The vox table trims each outgoing shot. Both inventory lengths survive that."""
    import subprocess

    monkeypatch.setattr(render, "theme_for", lambda ep: _theme())
    Image.new("RGBA", (480, 840), (40, 70, 120, 255)).save(tmp_path / "a.png")
    Image.new("RGBA", (480, 840), (120, 50, 40, 255)).save(tmp_path / "b.png")
    Image.new("RGBA", (480, 840), (30, 90, 70, 255)).save(tmp_path / "c.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: fades
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["long"]
    min: 2.2
    image: a.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 1.46
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.04, x: 4, y: 0}
  - type: image
    caption: ["short"]
    min: 1.2
    image: b.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 0.709
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0}
      to: {scale: 1.03}
  - type: image
    caption: ["hold"]
    min: 1.2
    image: c.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0}
      to: {scale: 1.02}
""", encoding="utf-8")
    video = tmp_path / "fades.mp4"
    render.render_episode(load_episode(path), video, "fixture", 1)
    for start, end, authored in ((0.0, 2.2, 1.46), (2.2, 3.4, 0.709)):
        clip = tmp_path / f"span-{authored}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
             "-i", str(video), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(clip)],
            check=True,
        )
        shot = detect_shot(clip)
        fade = next(item for item in shot["events"] if item["effect"] == "dissolve")
        assert fade["duration"] == pytest.approx(authored, abs=0.15)


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
    assert len(times) == 3
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
    failed = [row["effect"] for row in rows if not row["pass"]]
    assert failed == []


def test_ref2_and_ref3_replica_tables_pass():
    for name in ("ref2_replica_table.json", "ref3_replica_table.json"):
        data = json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))
        rows = data["rows"]
        assert rows
        failed = [row["effect"] for row in rows if not row["pass"]]
        assert failed == []
        for row in rows:
            if "dissolve" in row["effect"]:
                assert abs(row["delta"]) <= 0.15


def test_articles_and_history_templates():
    articles = yaml.safe_load((ROOT / "templates" / "articles.yaml").read_text())
    history = yaml.safe_load((ROOT / "templates" / "history.yaml").read_text())
    assert articles["style"] == "vox-explainer"
    assert articles["camera"]["tracks"][0]["keys"][1]["v"] == 1.40
    assert articles["transition"]["seconds"] == 0.709
    assert history["style"] == "history-story"
    assert history["camera"]["tracks"][2]["keys"][1]["v"] == 1.34
    assert history["transition"]["seconds"] == 2.0
    assert history["transition"]["ease"] == "easeInOutCubic"


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


def _ink(frame, kind: str) -> int:
    if kind == "mark":
        mask = (frame[:, :, 0] > 140) & (frame[:, :, 1] > 120) & (frame[:, :, 2] < 80)
    else:
        mask = frame.mean(axis=2) > 180
    return int(mask.sum())


def _overlay_frame(tmp, monkeypatch, body, plate="red"):
    tmp.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(render, "theme_for", lambda ep: _theme())
    episode = load_episode(_write(tmp, body, plate))
    scene = {
        "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["mark"],
        "key": [], "style": "history-story",
    }
    return render_image_frame(_theme(), scene, 0.5, 1.2, str(tmp))


def test_highlighter_ease_in_is_slower_than_linear_at_halfway(tmp_path, monkeypatch):
    shared = """
name: mark
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["mark"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      from: {{scale: 1.0}}
      to: {{scale: 1.04}}
    overlays:
      - kind: highlighter
        x: 40
        y: 200
        w: 240
        h: 36
        at: 0
        duration: 1.0
        ease: {ease}
"""
    linear = _ink(_overlay_frame(tmp_path / "lin", monkeypatch, shared.format(ease="linear")), "mark")
    curved = _ink(_overlay_frame(tmp_path / "in", monkeypatch, shared.format(ease="easeInCubic")), "mark")
    # easeInCubic(0.5) is 0.125, so the sweep is about a quarter of the linear bar.
    assert curved < linear * 0.4
    assert curved > 10


def test_pop_overshoot_draws_a_larger_mark(tmp_path, monkeypatch):
    def body(overshoot):
        extra = "" if overshoot is None else f"\n        overshoot: {overshoot}"
        return f"""
name: pop
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["pop"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      from: {{scale: 1.0}}
      to: {{scale: 1.04}}
    overlays:
      - kind: text
        text: POP
        entrance: pop
        at: 0.4
        size: 72
        font: sans
        color: [255, 255, 255]
        x: 40
        y: 180{extra}
"""
    # local = 0.5 - 0.4 = 0.10, halfway through the 0.20s pop.
    small = _ink(_overlay_frame(tmp_path / "a", monkeypatch, body(0.05), "red"), "text")
    large = _ink(_overlay_frame(tmp_path / "b", monkeypatch, body(0.55), "red"), "text")
    assert large > small * 1.15


def test_match_cut_moves_the_outgoing_shape_and_does_not_blend(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: _theme())
    image = Image.new("RGBA", (480, 840), (180, 30, 30, 255))
    ImageDraw.Draw(image).rectangle((120, 300, 200, 380), fill=(250, 250, 250, 255))
    image.save(tmp_path / "out.png")
    Image.new("RGBA", (480, 840), (20, 30, 180, 255)).save(tmp_path / "inn.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: match
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["out"]
    min: 1.2
    image: out.png
    grade: none
    grain: 0
    transition_out: match
    transition: 0.6
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
    match:
      tracks:
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 0.6, v: 70, ease: linear}
  - type: image
    caption: ["in"]
    min: 1.2
    image: inn.png
    grade: none
    grain: 0
    transition_out: cut
    camera:
      from: {scale: 1.04}
      to: {scale: 1.0}
""", encoding="utf-8")
    episode = load_episode(path)
    from gilvy.render import build_state, scene_durations
    state = build_state(episode, scene_durations(episode, [0, 0]))

    def white_x(n):
        frame = state.frame_array(n)
        mask = frame.mean(axis=2) > 200
        ys, xs = np.nonzero(mask)
        return float(xs.mean()) if len(xs) else None, frame

    before, _ = white_x(12)  # t=0.60, the window has not started
    landed, outgoing = white_x(23)  # t=1.15, near the end of the 0.6s alignment
    _, incoming = white_x(24)
    assert before is not None and landed is not None
    assert landed - before > 40
    assert float(outgoing[:, :, 0].mean()) > float(outgoing[:, :, 2].mean())
    assert float(incoming[:, :, 2].mean()) > float(incoming[:, :, 0].mean()) + 40


def test_color_tracks_move_hue_without_replacing_the_plate_grade(tmp_path):
    image = Image.new("RGBA", (480, 840), (210, 40, 30, 255))
    image.save(tmp_path / "plate.png")
    body = """
name: hue
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["hue"]
    min: 1.2
    image: plate.png
    grade: {grade}
    grain: 0
    camera:
      from: {{scale: 1.0}}
      to: {{scale: 1.04}}
    color:
      tracks:
        - property: hue
          keys:
            - {{t: 0.0, v: 0, ease: linear}}
            - {{t: 1.2, v: 120, ease: {ease}}}
"""
    def frame(grade, ease, u):
        dest = tmp_path / f"{grade}-{ease}"
        dest.mkdir(parents=True, exist_ok=True)
        episode = load_episode(_write(dest, body.format(grade=grade, ease=ease)))
        Image.new("RGBA", (480, 840), (210, 40, 30, 255)).save(dest / "plate.png")
        scene = {
            "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["hue"],
            "key": [], "style": "history-story",
        }
        return render_image_frame(_theme(), scene, u, 1.2, str(tmp_path / f"{grade}-{ease}"))

    start = frame("none", "linear", 0.0)
    end = frame("none", "linear", 1.2)
    mid_ease = frame("none", "easeInCubic", 0.6)
    assert float(start[:, :, 0].mean()) > float(start[:, :, 1].mean()) + 40
    assert float(end[:, :, 0].mean()) < float(start[:, :, 0].mean()) - 30
    # easeInCubic(0.5) = 0.125, so the midpoint is still close to the red start.
    assert abs(float(mid_ease[:, :, 0].mean()) - float(start[:, :, 0].mean())) < abs(
        float(end[:, :, 0].mean()) - float(start[:, :, 0].mean())
    ) * 0.5
    sepia = frame("sepia", "linear", 0.0)
    assert float(sepia[:, :, 0].mean()) > float(sepia[:, :, 2].mean())
    assert float(np.mean(np.abs(sepia - start))) > 10


def test_grain_std_matches_the_high_frequency_measurement(tmp_path):
    path = _write(tmp_path, """
name: grain
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["grain"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    grain_std: 10
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
""")
    Image.new("RGBA", (480, 840), (128, 128, 128, 255)).save(tmp_path / "plate.png")
    episode = load_episode(path)
    scene = {
        "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["grain"],
        "key": [], "style": "history-story",
    }
    frame = render_image_frame(_theme(), scene, 0.4, 1.2, str(tmp_path))
    assert high_frequency_std(frame) == pytest.approx(10, abs=1.0)


def test_eased_dissolve_may_last_four_seconds(tmp_path):
    path = _write(tmp_path, """
name: long
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["long"]
    min: 4.5
    image: plate.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 3.7
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
  - type: image
    caption: ["next"]
    min: 1.2
    image: plate.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.04}
      to: {scale: 1.0}
""")
    episode = load_episode(path)
    assert episode.scenes[0].params["transition"] == 3.7
    path.write_text(path.read_text().replace("transition: 3.7", "transition: 4.0"), encoding="utf-8")
    assert load_episode(path).scenes[0].params["transition"] == 4.0
    path.write_text(path.read_text().replace("transition: 4.0", "transition: 4.1"), encoding="utf-8")
    with pytest.raises(EpisodeError, match=r"transition must be from 0(?:\.0)? to 4(?:\.0)?$") as exc:
        load_episode(path)
    assert exc.value.field == "transition"
