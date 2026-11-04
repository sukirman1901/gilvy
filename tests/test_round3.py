"""Round 3: measured zoom and pan match the plate, plus the other Lustig gaps."""

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import gilvy.render as render
from gilvy.assets import build_manifest, extract_style_refs, shot_spans
from gilvy.episode import load_episode
from gilvy.errors import EpisodeError
from gilvy.formats import Fit
from gilvy.measure import motion
from gilvy.presets import HISTORY
from gilvy.qc import QCReport, _vo_warnings
from gilvy.render import build_state, scene_durations, write_timeline
from gilvy.theme import Theme


def _pattern(path: Path) -> None:
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 256, size=(1920, 1080), dtype=np.uint8)
    image = Image.fromarray(arr).convert("RGBA")
    image.save(path)


def _episode(tmp_path: Path, scale_to: float, x: float, y: float, seconds: float = 1.2) -> Path:
    _pattern(tmp_path / "plate.png")
    path = tmp_path / "ep.yaml"
    path.write_text(f"""
name: measure
style: history-story
audio_mode: silent
scenes:
  - id: move
    type: image
    caption: ["one move"]
    min: {seconds}
    image: plate.png
    grade: none
    grain: 0
    paper: 0
    camera:
      ease: exponential
      from: {{scale: 1.0, x: 0, y: 0}}
      to: {{scale: {scale_to}, x: {x}, y: {y}}}
""", encoding="utf-8")
    return path


def _render(tmp_path, path, monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(
        width=1080, height=1920, fps=10, scale=1, fit=Fit(), intro=0))
    episode = load_episode(path)
    video = tmp_path / "move.mp4"
    result = render.render_episode(episode, video, "fixture", 1)
    assert result["qc"]["ok"], result["qc"]
    return episode, video, result


def test_measured_zoom_and_pan_match_authored_within_five_percent(tmp_path, monkeypatch):
    scale_to, pan_x, pan_y, seconds = 1.25, 48.0, -36.0, 1.2
    episode, video, result = _render(tmp_path, _episode(tmp_path, scale_to, pan_x, pan_y, seconds), monkeypatch)
    authored_zoom = 100.0 * math.log(scale_to) / seconds
    authored_px, authored_py = pan_x / seconds, pan_y / seconds
    measured = motion(video, dt=0.4)
    assert measured["zoom_pct_per_s"] == pytest.approx(authored_zoom, rel=0.05, abs=0.4)
    assert measured["pan_px_per_s"]["x"] == pytest.approx(authored_px, rel=0.05, abs=1.5)
    assert measured["pan_px_per_s"]["y"] == pytest.approx(authored_py, rel=0.05, abs=1.5)
    camera = json.loads(Path(result["camera"]).read_text())
    row = camera["scenes"][0]
    assert row["effective"]["zoom_pct_per_s"] == pytest.approx(row["authored"]["zoom_pct_per_s"], rel=0.05)
    assert row["effective"]["pan_px_per_s"]["x"] == pytest.approx(authored_px, abs=0.05)
    assert row["id"] == "move"


def test_small_zoom_with_a_large_pan_does_not_reverse(tmp_path, monkeypatch):
    # money: scale only to ~1.05 while y pan is 80. The old margin froze the zoom.
    seconds, pan_y = 1.5, 75.0
    episode, video, _ = _render(
        tmp_path, _episode(tmp_path, 1.05, -15.0, pan_y, seconds), monkeypatch)
    measured = motion(video, dt=0.5)
    authored_zoom = 100.0 * math.log(1.05) / seconds
    assert measured["zoom_pct_per_s"] > 0
    assert measured["zoom_pct_per_s"] == pytest.approx(authored_zoom, rel=0.05, abs=0.4)
    assert measured["pan_px_per_s"]["y"] == pytest.approx(pan_y / seconds, rel=0.05, abs=1.5)


def test_transition_may_last_two_seconds(tmp_path):
    Image.new("RGBA", (8, 12), (20, 20, 20, 255)).save(tmp_path / "a.png")
    path = tmp_path / "ep.yaml"
    text = """
name: fade
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["hold"]
    min: 2.0
    image: a.png
    transition_out: dissolve
    transition: {seconds}
    camera:
      from: {{scale: 1.0}}
      to: {{scale: 1.05}}
"""
    path.write_text(text.format(seconds=2.0), encoding="utf-8")
    assert load_episode(path).scenes[0].params["transition"] == 2.0
    path.write_text(text.format(seconds=2.1), encoding="utf-8")
    with pytest.raises(EpisodeError, match="2.0"):
        load_episode(path)


def test_per_shot_style_frames_and_frame_count(tmp_path):
    video = tmp_path / "ref.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x33281f:s=64x96:d=4",
        "-pix_fmt", "yuv420p", str(video),
    ], check=True)
    Image.new("RGBA", (8, 12), (40, 30, 20, 255)).save(tmp_path / "a.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: shots
style: history-story
audio_mode: silent
scenes:
  - id: one
    type: image
    caption: ["one"]
    min: 2.0
    image: a.png
    camera:
      from: {scale: 1.0}
      to: {scale: 1.05}
  - id: two
    type: image
    caption: ["two"]
    min: 2.0
    image: a.png
    camera:
      from: {scale: 1.05}
      to: {scale: 1.0}
""", encoding="utf-8")
    episode = load_episode(path)
    even = extract_style_refs(video, tmp_path / "even", count=6)
    assert len(even) == 6
    refs = extract_style_refs(video, tmp_path / "shots", shots=shot_spans(episode))
    assert [row["scene_index"] for row in refs] == [1, 2]
    assert refs[0]["time"] == pytest.approx(1.0, abs=0.05)
    manifest = build_manifest(episode, refs)
    assert manifest["assets"][0]["image_qc"]["matched_ref"] == pytest.approx(refs[0]["time"], abs=0.05)


def test_overrun_that_covers_the_next_line_warns(tmp_path):
    Image.new("RGBA", (8, 12), (40, 30, 20, 255)).save(tmp_path / "a.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: overlap
style: history-story
audio_mode: voiceover
scenes:
  - id: money
    type: image
    caption: ["gone"]
    vo: "This line is long enough to spill."
    min: 1.5
    vo_overrun: true
    image: a.png
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
  - id: card
    type: image
    caption: ["next"]
    vo: "Next line."
    min: 1.5
    image: a.png
    camera:
      from: {scale: 1.04}
      to: {scale: 1.0}
""", encoding="utf-8")
    episode = load_episode(path)
    episode.spoken_seconds = [3.2, 1.0]
    assert scene_durations(episode, episode.spoken_seconds) == [1.5, 1.5]
    state = build_state(episode, [1.5, 1.5])
    dest = tmp_path / "overlap.timeline.json"
    write_timeline(episode, state, dest, "fixture")
    meta = json.loads(dest.read_text(encoding="utf-8"))
    assert meta["scenes"][0]["vo_overlaps_next"] is True
    assert meta["scenes"][0]["vo_overlap_s"] == pytest.approx(1.7, abs=0.05)
    report = QCReport(ok=True, video="x", duration=3, width=64, height=64)
    _vo_warnings(report, meta)
    assert report.ok
    assert any("overlaps the next voice" in item for item in report.warnings)
