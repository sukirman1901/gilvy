"""Lustig round 2: zoom, pan, type, grade match, compare, and voice overrun."""

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import gilvy.render as render
from gilvy.assets import compare_asset
from gilvy.episode import load_episode
from gilvy.formats import Fit
from gilvy.image_scene import _camera_at, camera_metrics, render_image_frame
from gilvy.presets import HISTORY, RULES, camera_problem
from gilvy.qc import QCReport, _vo_warnings
from gilvy.render import build_state, scene_durations, theme_for
from gilvy.review import compare_versions
from gilvy.theme import Theme

ROOT = Path(__file__).resolve().parents[1]


def _plate(path: Path, draw) -> None:
    image = Image.new("RGBA", (1080, 1920), (30, 28, 26, 255))
    draw(ImageDraw.Draw(image))
    image.save(path)


def test_history_accepts_reference_pushes_and_a_short_punch():
    rules = RULES[HISTORY]
    assert rules["zoom_hi"] >= 24
    assert rules["scale_max"] > 1.45
    slow = {"static": False, "zoom_pct_per_s": 22.5, "pan_px_per_s": {"x": 0, "y": 0}, "duration": 2.0}
    assert camera_problem(slow, rules, "scene 1 (name)") is None
    punch = {"static": False, "zoom_pct_per_s": 36.0, "pan_px_per_s": {"x": 0, "y": 0}, "duration": 1.2}
    assert camera_problem(punch, rules, "scene 1 (punch)") is None
    long = {"static": False, "zoom_pct_per_s": 36.0, "pan_px_per_s": {"x": 0, "y": 0}, "duration": 4.0}
    assert camera_problem(long, rules, "scene 1 (long)")


def test_scale_above_the_old_cap_loads(tmp_path):
    plate = tmp_path / "a.png"
    Image.new("RGBA", (32, 48), (40, 30, 20, 255)).save(plate)
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: wide
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["push in"]
    min: 2.0
    image: a.png
    camera:
      ease: exponential
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.8, x: 40, y: 20}
""", encoding="utf-8")
    episode = load_episode(path)
    assert episode.scenes[0].params["camera"]["to"]["scale"] == 1.8


def test_pan_at_scale_one_still_moves_the_picture(tmp_path):
    def mark(pen):
        pen.rectangle((80, 900, 180, 1000), fill=(220, 40, 40, 255))

    _plate(tmp_path / "a.png", mark)
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: pan
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["hold still"]
    min: 2.0
    image: a.png
    grade: none
    grain: 0
    camera:
      ease: linear
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.0, x: 120, y: 0}
""", encoding="utf-8")
    episode = load_episode(path)
    scene = {
        "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["hold still"],
        "key": [], "style": "history-story",
    }
    theme = Theme()
    early = render_image_frame(theme, scene, 0.0, 2.0, str(tmp_path))
    late = render_image_frame(theme, scene, 2.0, 2.0, str(tmp_path))

    def center(frame):
        mask = (frame[:, :, 0] > 180) & (frame[:, :, 1] < 80)
        ys, xs = np.where(mask)
        return float(xs.mean())

    assert center(late) - center(early) > 80


def test_exponential_zoom_holds_a_constant_relative_rate():
    camera = {
        "ease": "exponential",
        "from": {"scale": 1.0, "x": 0, "y": 0},
        "to": {"scale": 1.45, "x": 0, "y": 0},
    }
    duration = 2.0
    rate = camera_metrics(camera, duration)["zoom_pct_per_s"]
    assert rate == pytest.approx(100.0 * math.log(1.45) / duration, rel=0.01)
    samples = [_camera_at(camera, t, duration)[0] for t in (0.0, 0.5, 1.0, 1.5)]
    ratios = [samples[i + 1] / samples[i] for i in range(3)]
    assert ratios[0] == pytest.approx(ratios[1], rel=0.01)
    assert ratios[1] == pytest.approx(ratios[2], rel=0.01)


def test_history_does_not_fade_in_from_black():
    episode = load_episode(ROOT / "examples" / "styles" / "history-story.yaml")
    assert theme_for(episode).intro == 0
    state = build_state(episode, [scene.min for scene in episode.scenes])
    assert float(state.frame_array(0).mean()) > 15


def test_emphasis_stacks_words_inside_the_frame(tmp_path):
    _plate(tmp_path / "a.png", lambda pen: None)
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: words
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["the deal"]
    min: 2.4
    image: a.png
    grade: none
    grain: 0
    camera:
      ease: linear
      from: {scale: 1.0}
      to: {scale: 1.06}
    overlays:
      - kind: text
        text: DEAL WAS REAL
        at: 0.0
        hold: 2.0
        entrance: fade
        text_fade_s: 0.01
        font: serif
        size: 480
        y: 200
""", encoding="utf-8")
    episode = load_episode(path)
    scene = {
        "type": "image", "params": episode.scenes[0].params, "vo": "", "caption": ["the deal"],
        "key": [], "style": "history-story",
    }
    frame = render_image_frame(Theme(), scene, 1.0, 2.4, str(tmp_path))
    mask = (frame[:, :, 0] > 140) & (frame[:, :, 1] < 120)
    ys, xs = np.where(mask)
    assert len(xs) > 50
    assert xs.min() > 20 and xs.max() < frame.shape[1] - 20
    assert ys.min() > 20 and ys.max() < frame.shape[0] - 20
    assert ys.max() - ys.min() > 200


def test_image_qc_uses_the_nearest_brightness_bucket(tmp_path):
    dark = tmp_path / "dark.png"
    bright = tmp_path / "bright.png"
    plate = tmp_path / "plate.png"
    Image.new("RGB", (40, 60), (40, 32, 28)).save(dark)
    Image.new("RGB", (40, 60), (230, 210, 180)).save(bright)
    Image.new("RGB", (40, 60), (46, 36, 30)).save(plate)
    report = compare_asset(plate, [
        {"path": str(dark), "time": 1.0},
        {"path": str(bright), "time": 12.0},
    ])
    assert report["ok"]
    assert report["matched_ref"] == 1.0
    assert report["match"] == "brightness"


def test_music_bed_hits_the_loudness_target(tmp_path, monkeypatch):
    tone = tmp_path / "bed.wav"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
        "-i", "sine=frequency=220:sample_rate=48000:duration=6",
        str(tone),
    ], check=True)
    Image.new("RGBA", (32, 48), (80, 60, 40, 255)).save(tmp_path / "a.png")
    path = tmp_path / "ep.yaml"
    path.write_text(f"""
name: bed
style: history-story
audio_mode: ambient
loudness: -21
music: {tone}
scenes:
  - type: image
    caption: ["one bed"]
    min: 2.0
    image: a.png
    camera:
      from: {{scale: 1.0}}
      to: {{scale: 1.05}}
""", encoding="utf-8")
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(
        width=216, height=384, fps=8, scale=1, fit=Fit(0.2), intro=0))
    episode = load_episode(path)
    assert episode.loudness == -21
    video = tmp_path / "bed.mp4"
    result = render.render_episode(episode, video, "fixture", 1)
    assert result["qc"]["ok"], result["qc"]
    log = subprocess.run(
        ["ffmpeg", "-i", str(video), "-af", "ebur128=framelog=verbose", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    integrated = [line for line in log.stderr.splitlines() if "I:" in line and "LUFS" in line]
    assert integrated, log.stderr[-500:]
    value = float(integrated[-1].split("I:")[1].split("LUFS")[0])
    assert value == pytest.approx(-21, abs=5)


def test_compare_rescales_and_allows_a_long_window(tmp_path):
    def clip(name, size, x):
        dest = tmp_path / name
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            f"color=c=0x202020:s={size}:r=10:d=1",
            "-vf", f"drawbox=x={x}:y=10:w=8:h=8:color=white:t=fill",
            "-pix_fmt", "yuv420p", str(dest),
        ], check=True)
        return dest

    wide = clip("wide.mp4", "80x80", 10)
    small = clip("small.mp4", "40x40", 4)
    result = compare_versions(wide, small, tmp_path / "cmp", duration=30, sample_fps=2)
    assert result["rescaled"] is True
    assert result["sample_count"] >= 1
    assert result["duration"] <= 1.05


def test_long_voice_warns_unless_it_may_overrun(tmp_path):
    plate = tmp_path / "a.png"
    Image.new("RGBA", (16, 24), (40, 30, 20, 255)).save(plate)
    body = """
name: overrun
style: history-story
audio_mode: voiceover
vo_overrun: {flag}
scenes:
  - type: image
    caption: ["one line"]
    vo: "One long spoken line that will not fit."
    min: 1.5
    image: a.png
    camera:
      from: {{scale: 1.0}}
      to: {{scale: 1.06}}
  - type: image
    caption: ["next"]
    vo: "Next."
    min: 1.5
    image: a.png
    camera:
      from: {{scale: 1.06}}
      to: {{scale: 1.0}}
"""
    held = tmp_path / "held.yaml"
    held.write_text(body.format(flag="false"), encoding="utf-8")
    free = tmp_path / "free.yaml"
    free.write_text(body.format(flag="true"), encoding="utf-8")
    assert scene_durations(load_episode(held), [4.0, 1.0]) == [4.0, 1.5]
    assert scene_durations(load_episode(free), [4.0, 1.0]) == [1.5, 1.5]
    report = QCReport(ok=True, video="x", duration=3, width=64, height=64)
    _vo_warnings(report, {"scenes": [{
        "index": 6, "id": "money", "type": "image", "vo_extends_shot": True,
        "vo_seconds": 5.2, "shot_min": 3.88,
    }]})
    assert report.ok
    assert any("3.88" in item and "vo_overrun" in item for item in report.warnings)
