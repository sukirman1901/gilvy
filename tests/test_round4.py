"""Round 4: measured zoom and pan on photo plates, and the dissolve clock."""

import math
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

import gilvy.render as render
from gilvy.assets import plate_pixel_size
from gilvy.episode import load_episode
from gilvy.formats import Fit
from gilvy.image_scene import render_image_frame
from gilvy.measure import linear_dissolve_clocks, motion
from gilvy.reference import detect_soft_transitions
from gilvy.theme import Theme

SECONDS = 1.6


def _texture(width: int, height: int, seed: int, contrast: float, vignette: bool) -> Image.Image:
    rng = np.random.default_rng(seed)
    field = np.zeros((height, width), np.float32)
    for cell, amp in ((6, 0.35), (18, 0.55), (48, 0.8), (140, 1.0)):
        small = rng.random((max(2, height // cell), max(2, width // cell))).astype(np.float32)
        up = np.asarray(
            Image.fromarray((small * 255).astype(np.uint8)).resize((width, height), Image.Resampling.BILINEAR),
            np.float32,
        ) / 255.0
        field += amp * up
    field = (field - field.min()) / max(1e-6, float(field.max() - field.min()))
    field = np.clip(0.5 + (field - 0.5) * contrast, 0, 1)
    yy, xx = np.mgrid[0:height, 0:width]
    field[(yy > height * 0.22) & (yy < height * 0.72) & (xx > width * 0.28) & (xx < width * 0.68)] *= 0.75
    if vignette:
        cy, cx = (height - 1) / 2, (width - 1) / 2
        falloff = ((yy - cy) / (height * 0.62)) ** 2 + ((xx - cx) / (width * 0.62)) ** 2
        field *= np.clip(1.12 - falloff, 0.35, 1.0)
    rgb = np.stack([field * 200 + 25, field * 165 + 20, field * 120 + 15], axis=2)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")


def _camera(zoom: float, pan_x: float, pan_y: float) -> tuple[dict, float, float, float]:
    """Pulls stay at scale >= 1, which is what the episode schema allows."""
    if zoom >= 0:
        start, end = 1.0, math.exp(zoom / 100.0 * SECONDS)
        x0 = y0 = 0.0
        x1, y1 = pan_x * SECONDS, pan_y * SECONDS
    else:
        start, end = math.exp(-zoom / 100.0 * SECONDS), 1.0
        x0, y0 = 0.0, 0.0
        x1, y1 = pan_x * SECONDS, pan_y * SECONDS
    camera = {
        "ease": "exponential",
        "from": {"scale": round(start, 4), "x": round(x0, 2), "y": round(y0, 2)},
        "to": {"scale": round(end, 4), "x": round(x1, 2), "y": round(y1, 2)},
    }
    return camera, zoom, pan_x, pan_y


def _episode(tmp: Path, zoom: float, pan_x: float, pan_y: float, kind: str) -> Path:
    camera, _, _, _ = _camera(zoom, pan_x, pan_y)
    size = plate_pixel_size(camera)
    contrast = 0.42 if kind == "sepia" else 1.0
    image = _texture(size["width"], size["height"], 11, contrast, vignette=kind == "grain")
    image.save(tmp / "plate.png")
    grade = "sepia" if kind in {"sepia", "grain"} else "none"
    grain = 0.22 if kind == "grain" else 0
    path = tmp / "ep.yaml"
    path.write_text(f"""
name: truth
style: history-story
audio_mode: silent
scenes:
  - id: move
    type: image
    caption: ["one move"]
    min: {SECONDS}
    image: plate.png
    grade: {grade}
    grain: {grain}
    paper: 0
    camera:
      ease: exponential
      from: {{scale: {camera['from']['scale']}, x: {camera['from']['x']}, y: {camera['from']['y']}}}
      to: {{scale: {camera['to']['scale']}, x: {camera['to']['x']}, y: {camera['to']['y']}}}
""", encoding="utf-8")
    return path


def _within(actual: float, expected: float, rel: float, abs_tol: float) -> bool:
    return abs(actual - expected) <= max(abs_tol, rel * abs(expected))


CASES = (
    ("photo", 8.0, 0.0, 0.0),
    ("photo", -12.0, 0.0, 0.0),
    ("photo", 1.25, 0.0, 0.0),
    ("photo", -1.25, 0.0, 50.0),
    ("photo", 24.0, 50.0, 0.0),
    ("sepia", 8.0, 20.0, -20.0),
    ("grain", -12.0, 0.0, 20.0),
)


def test_synthetic_plates_match_authored_zoom_and_pan(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(
        width=1080, height=1920, fps=10, scale=1, fit=Fit(), intro=0, outro=0))
    failures = []
    print("\nkind     zoom authored measured   pan authored -> measured")
    for kind, zoom, pan_x, pan_y in CASES:
        case_dir = tmp_path / f"{kind}-{zoom:+g}-{pan_x:+g}"
        case_dir.mkdir()
        episode = load_episode(_episode(case_dir, zoom, pan_x, pan_y, kind))
        video = case_dir / "move.mp4"
        result = render.render_episode(episode, video, "fixture", 1)
        assert result["qc"]["ok"], result["qc"]
        measured = motion(video, dt=0.4)
        got_z = measured["zoom_pct_per_s"]
        got_x = measured["pan_px_per_s"]["x"]
        got_y = measured["pan_px_per_s"]["y"]
        print(f"{kind:8} {zoom:7.2f} {got_z:8.2f}   ({pan_x:6.1f},{pan_y:6.1f}) -> ({got_x:6.1f},{got_y:6.1f})")
        if not _within(got_z, zoom, 0.05, 0.15):
            failures.append(f"{kind} zoom {got_z} vs {zoom}")
        if not _within(got_x, pan_x, 0.05, 1.5):
            failures.append(f"{kind} pan x {got_x} vs {pan_x}")
        if not _within(got_y, pan_y, 0.05, 1.5):
            failures.append(f"{kind} pan y {got_y} vs {pan_y}")
        if kind == "photo" and zoom == 24.0:
            import json
            camera = json.loads(Path(result["camera"]).read_text(encoding="utf-8"))
            row = camera["scenes"][0]
            assert row["effective"]["zoom_pct_per_s"] == pytest.approx(row["authored"]["zoom_pct_per_s"], abs=0.05)
            assert row["effective"]["pan_px_per_s"]["x"] == pytest.approx(pan_x, abs=0.05)
    assert not failures, "; ".join(failures)


def test_oversized_plate_keeps_the_margin(tmp_path):
    image = Image.new("RGBA", (1600, 2400), (20, 18, 16, 255))
    pen = ImageDraw.Draw(image)
    pen.rectangle((180, 0, 220, 2400), fill=(40, 220, 60, 255))
    image.save(tmp_path / "wide.png")
    scene = {
        "type": "image",
        "params": {
            "layers": [{"src": "wide.png", "depth": 1.0}],
            "camera": {
                "ease": "linear",
                "from": {"scale": 1.0, "x": 0.0, "y": 0.0},
                "to": {"scale": 1.0, "x": 120.0, "y": 0.0},
            },
            "grade": "none", "grain": 0, "paper": 0, "overlays": [], "show_caption": False,
        },
        "vo": "", "caption": ["pan"], "key": [], "style": "history-story",
    }
    theme = Theme(width=1080, height=1920, fps=10, scale=1, fit=Fit(), intro=0, outro=0)
    early = render_image_frame(theme, scene, 0.0, 1.0, str(tmp_path))
    late = render_image_frame(theme, scene, 1.0, 1.0, str(tmp_path))
    green = lambda frame: int(((frame[:, :, 1] > 180) & (frame[:, :, 0] < 80)).sum())
    assert green(early) < 50
    assert green(late) > 500


def test_linear_dissolve_ten_ninety_is_eighty_percent_of_the_overlap():
    clocks = linear_dissolve_clocks(1.4)
    assert clocks["full_s"] == pytest.approx(1.4)
    assert clocks["ten_ninety_s"] == pytest.approx(1.12)


def test_rendered_dissolve_reaches_both_ends(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(
        width=320, height=560, fps=20, scale=1, fit=Fit(), intro=0, outro=0))
    Image.new("RGBA", (400, 700), (180, 40, 30, 255)).save(tmp_path / "a.png")
    Image.new("RGBA", (400, 700), (20, 40, 160, 255)).save(tmp_path / "b.png")
    path = tmp_path / "ep.yaml"
    path.write_text("""
name: fade
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["out"]
    min: 2.0
    image: a.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 1.4
    camera:
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.04, x: 4, y: 0}
  - type: image
    caption: ["in"]
    min: 1.2
    image: b.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.04, x: 0, y: 0}
      to: {scale: 1.0, x: 0, y: 0}
""", encoding="utf-8")
    episode = load_episode(path)
    video = tmp_path / "fade.mp4"
    render.render_episode(episode, video, "fixture", 1)
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(video), "-an",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ])
    width, height, fps = 320, 560, 20
    frame = width * height * 3
    count = len(raw) // frame
    frames = np.frombuffer(raw[:count * frame], np.uint8).reshape(count, height, width, 3)
    red = frames[:, :, :, 0].astype(np.float32).mean(axis=(1, 2))
    # Dissolve occupies the last 1.4s of the 2.0s outgoing shot.
    start = int(round(0.6 * fps))
    end = int(round(2.0 * fps))
    level = red[start:end + 1]
    span = float(level[0] - level[-1])
    assert span > 40
    progress = (level[0] - level) / span
    def crossing(mark: float) -> float:
        hit = np.where(progress >= mark)[0]
        assert len(hit), mark
        index = int(hit[0])
        if index == 0:
            return start / fps
        prev, cur = float(progress[index - 1]), float(progress[index])
        frac = 0 if cur == prev else (mark - prev) / (cur - prev)
        return (start + index - 1 + frac) / fps
    ten, ninety = crossing(0.10), crossing(0.90)
    assert ninety - ten == pytest.approx(1.12, abs=0.08)
    assert crossing(0.98) - crossing(0.02) == pytest.approx(1.4, abs=0.12)


def test_a_long_crossfade_is_not_capped_at_point_eight_seconds(tmp_path):
    fade = tmp_path / "long.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=0x8a3030:s=160x284:d=2.2",
        "-f", "lavfi", "-i", "color=c=0x203060:s=160x284:d=2.2",
        "-filter_complex", "xfade=transition=fade:duration=1.4:offset=0.8",
        "-pix_fmt", "yuv420p", "-r", "20", str(fade),
    ], check=True)
    rows = detect_soft_transitions(fade)
    match = next(row for row in rows if row["start"] < 1.2 < row["end"])
    assert match["duration"] == pytest.approx(1.4, abs=0.2)
