"""Locks from the Lustig timing pass: cuts, zoom, and text, plus the grade and voice gap."""

import json
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from gilvy.assets import (
    STYLE_PROMPTS,
    build_manifest,
    compare_asset,
    extract_style_refs,
    plate_pixel_size,
)
from gilvy.episode import load_episode
from gilvy.errors import EpisodeError
from gilvy.image_scene import _grade, camera_metrics
from gilvy.presets import HISTORY, HOUSE, RULES
from gilvy.qc import checks_green, qc_video
from gilvy.reference import detect_soft_transitions
from gilvy.render import scene_durations, theme_for
from gilvy.tts import probe_duration, trim_edge_silence

ROOT = Path(__file__).resolve().parents[1]
CUT_TOL = 0.1
ZOOM_TOL = 0.20
TEXT_TOL = 0.2


def test_detected_dissolve_stays_within_a_tenth_of_the_cut(tmp_path):
    fade = tmp_path / "fade.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=0x8a3030:s=160x120:d=1.6",
        "-f", "lavfi", "-i", "color=c=0x203060:s=160x120:d=1.6",
        "-filter_complex", "xfade=transition=fade:duration=0.4:offset=1.2",
        "-pix_fmt", "yuv420p", str(fade),
    ], check=True)
    rows = detect_soft_transitions(fade)
    match = next(row for row in rows if row["start"] < 1.5 < row["end"])
    assert abs(match["start"] - 1.2) <= CUT_TOL
    assert abs(match["end"] - 1.6) <= CUT_TOL


def test_zoom_rate_stays_within_twenty_percent_of_the_camera():
    episode = load_episode(ROOT / "tests/fixtures/episodes" / "styles" / "history-story.yaml")
    camera = episode.scenes[0].params["camera"]
    duration = 2.4
    expected = (camera["to"]["scale"] - camera["from"]["scale"]) / duration * 100.0
    rate = camera_metrics(camera, duration)["zoom_pct_per_s"]
    assert abs(rate - expected) <= abs(expected) * ZOOM_TOL
    assert 0.80 <= rate <= RULES[HISTORY]["zoom_hi"]


def test_history_text_is_full_within_two_tenths_and_two_to_three_times_larger():
    rules = RULES[HISTORY]
    assert 2.0 <= rules["text_size"] / 72.0 <= 3.0
    assert rules["text_fade_s"] == pytest.approx(0.15)
    episode = load_episode(ROOT / "tests/fixtures/episodes" / "styles" / "history-story.yaml")
    overlay = episode.scenes[0].params["overlays"][0]
    # Pinned schedule: the phrase is authored at 0.45s and the fade is 0.15s.
    full = overlay["at"] + overlay["fade"]
    assert abs(full - 0.60) <= TEXT_TOL
    assert overlay["size"] == rules["text_size"]


def test_history_voice_gap_is_zero_and_house_keeps_the_breath(tmp_path):
    assert RULES[HISTORY]["pad"] == 0 and RULES[HISTORY]["lead"] == 0
    assert RULES[HISTORY]["shot_min"] == pytest.approx(1.1)
    history = load_episode(ROOT / "tests/fixtures/episodes" / "styles" / "history-story.yaml")
    assert theme_for(history).pad == 0 and theme_for(history).lead == 0
    house = tmp_path / "house.yaml"
    house.write_text("""
name: gap
audio_mode: voiceover
scenes:
  - type: bowl_cta
    caption: ["one."]
    vo: "One."
    min: 1.2
    label: one
""", encoding="utf-8")
    tight = tmp_path / "tight.yaml"
    tight.write_text("""
name: tight
style: history-story
audio_mode: voiceover
scenes:
  - type: image
    caption: ["one."]
    vo: "One."
    min: 1.2
    image: missing.png
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
""", encoding="utf-8")
    assert scene_durations(load_episode(house), [2.0]) == [2.6]
    assert scene_durations(load_episode(tight), [2.0]) == [2.0]
    assert theme_for(load_episode(house)).pad == 0.4
    short = tmp_path / "short.yaml"
    short.write_text("""
name: short
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["too short"]
    min: 1.0
    image: missing.png
    camera:
      from: {scale: 1}
      to: {scale: 1.05}
""", encoding="utf-8")
    with pytest.raises(EpisodeError, match="shot range"):
        load_episode(short)


def test_edge_silence_is_trimmed(tmp_path):
    src = tmp_path / "padded.wav"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.45",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.50",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=0.45",
        "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1",
        str(src),
    ], check=True)
    before = probe_duration(src)
    trim_edge_silence(src)
    after = probe_duration(src)
    assert before > 1.2
    assert abs(after - 0.50) <= 0.15


def test_sepia_poles_and_green_check():
    white = np.full((4, 4, 3), 255, np.float32)
    black = np.zeros((4, 4, 3), np.float32)
    hi = _grade(white, "sepia")[0, 0]
    lo = _grade(black, "sepia")[0, 0]
    assert hi == pytest.approx((0xEA, 0xD0, 0xB3), abs=1)
    assert lo == pytest.approx((0x1A, 0x14, 0x11), abs=1)
    assert checks_green(HISTORY) is False
    assert checks_green(HOUSE) is True
    assert checks_green("vox-explainer") is True


def test_sepia_style_does_not_fail_a_green_frame(tmp_path):
    video = tmp_path / "green.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0xdaff59:s=64x64:d=2",
        "-pix_fmt", "yuv420p", str(video),
    ], check=True)
    meta = {
        "audio_mode": "silent", "style": HISTORY, "duration": 2.0, "width": 64, "height": 64,
        "scenes": [{
            "index": 0, "id": "year", "type": "image", "green": "none",
            "start": 0, "duration": 2.0, "caption": ["in 1925"],
            "camera": {"static": False, "zoom_pct_per_s": 2.0, "pan_px_per_s": {"x": 0, "y": 0}},
        }],
    }
    side = tmp_path / "green.timeline.json"
    side.write_text(json.dumps(meta), encoding="utf-8")
    report = qc_video(video, str(side))
    assert not any("green" in item for item in report.violations)
    meta["style"] = HOUSE
    side.write_text(json.dumps(meta), encoding="utf-8")
    house = qc_video(video, str(side))
    assert any("green" in item for item in house.violations)


def test_prompt_template_overscan_and_image_qc(tmp_path):
    template = STYLE_PROMPTS[HISTORY].lower()
    for word in ("archival photo", "sepia", "grain", "vignette", "framing"):
        assert word in template
    episode = load_episode(ROOT / "tests/fixtures/episodes" / "styles" / "history-story.yaml")
    size = plate_pixel_size(episode.scenes[0].params["camera"])
    assert size["width"] >= 1080
    assert size["height"] >= 1920 + 2 * size["pan_y"]
    assert size["width"] == pytest.approx(math_ceil((1080 + 2 * size["pan_x"]) * size["scale"]))
    manifest = build_manifest(episode)
    assert manifest["assets"][0]["width"] == size["width"]
    assert manifest["prompt_template"] == STYLE_PROMPTS[HISTORY]

    ref = tmp_path / "ref.png"
    close = tmp_path / "close.png"
    bright = tmp_path / "bright.png"
    Image.new("RGB", (48, 80), (90, 70, 55)).save(ref)
    Image.new("RGB", (48, 80), (96, 76, 60)).save(close)
    Image.new("RGB", (48, 80), (245, 230, 150)).save(bright)
    assert compare_asset(close, [{"path": str(ref)}])["ok"]
    missed = compare_asset(bright, [{"path": str(ref)}])
    assert missed["ok"] is False
    assert missed["regen"] and "brightness" in missed["regen"]

    video = tmp_path / "ref.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x5a4632:s=80x80:d=1",
        "-pix_fmt", "yuv420p", str(video),
    ], check=True)
    frames = extract_style_refs(video, tmp_path / "style-refs", count=2)
    assert len(frames) == 2 and all(Path(item["path"]).is_file() for item in frames)


def math_ceil(value: float) -> int:
    import math
    return int(math.ceil(value))
