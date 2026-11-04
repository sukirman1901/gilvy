"""Opt-in image presets stay off the house path and obey their measured bands."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import gilvy.render as render
from gilvy.assets import build_manifest
from gilvy.cli import run
from gilvy.episode import load_episode
from gilvy.errors import EpisodeError, GilvyError
from gilvy.formats import Fit
from gilvy.image_scene import overlay_start, render_image_frame
from gilvy.mcp_server import asset_manifest, reference_styles
from gilvy.qc import _preset_conformance, QCReport
from gilvy.render import render_episode, scene_payload
from gilvy.theme import Theme

ROOT = Path(__file__).resolve().parents[1]


def _plate(path: Path, color):
    Image.new("RGBA", (320, 480), color).save(path)


def _episode(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "ep.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_house_rejects_image_plates_and_static_cameras(tmp_path: Path):
    _plate(tmp_path / "a.png", (40, 50, 70, 255))
    with pytest.raises(EpisodeError, match="still camera"):
        load_episode(_episode(tmp_path, """
name: houseimg
audio_mode: silent
scenes:
  - type: image
    caption: ["no photo"]
    min: 2
    image: a.png
    camera:
      from: {scale: 1}
      to: {scale: 1.05}
"""))
    with pytest.raises(EpisodeError, match="have to push"):
        load_episode(_episode(tmp_path, """
name: frozen
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["held still"]
    min: 2.4
    image: a.png
    camera:
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.0, x: 0, y: 0}
"""))


def test_missing_asset_fails_before_encode_and_manifest_names_it(tmp_path: Path):
    path = _episode(tmp_path, """
name: missing
style: vox-explainer
audio_mode: silent
scenes:
  - id: plate
    type: image
    caption: ["need art"]
    min: 1.6
    prompt: "A desk."
    image: nowhere.png
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04, x: -12}
""")
    episode = load_episode(path)
    manifest = build_manifest(episode)
    assert manifest["missing"] == ["nowhere.png"]
    assert manifest["style_prompt"] in manifest["assets"][0]["prompt"]
    assert "A desk." in manifest["assets"][0]["prompt"]
    with pytest.raises(GilvyError, match="nowhere.png"):
        render_episode(episode, tmp_path / "out.mp4", "fixture", 1)


def test_parallax_highlighter_and_keyword_lead(tmp_path: Path):
    bg = Image.new("RGBA", (400, 700), (20, 24, 32, 255))
    from PIL import ImageDraw
    ImageDraw.Draw(bg).rectangle((30, 30, 90, 90), fill=(0, 40, 255, 255))
    bg.save(tmp_path / "bg.png")
    fg = Image.new("RGBA", (400, 700), (0, 0, 0, 0))
    ImageDraw.Draw(fg).rectangle((30, 400, 90, 460), fill=(255, 30, 30, 255))
    fg.save(tmp_path / "fg.png")
    episode = load_episode(_episode(tmp_path, """
name: par
style: vox-explainer
audio_mode: silent
scenes:
  - id: layers
    type: image
    caption: ["split it"]
    vo: "Split the tower layer."
    min: 1.6
    grade: none
    grain: 0
    paper: 0
    layers:
      - {src: bg.png, depth: 0.0}
      - {src: fg.png, depth: 1.0}
    camera:
      from: {scale: 1.0, x: -40, y: 0}
      to: {scale: 1.02, x: 40, y: 0}
    overlays:
      - kind: highlighter
        x: 200
        y: 900
        w: 500
        h: 40
        at: 0.2
        duration: 0.5
      - kind: text
        text: TOWER
        keyword: tower
        entrance: pop
        font: sans
        hold: 1
"""))
    scene = scene_payload(episode.scenes[0], episode)
    theme = Theme()

    def centroid(frame, pred):
        ys, xs = np.where(pred(frame))
        return float(xs.mean())

    early = render_image_frame(theme, scene, 0.02, 1.6, str(tmp_path))
    late = render_image_frame(theme, scene, 1.55, 1.6, str(tmp_path))
    blue = lambda frame: (frame[:, :, 2] > 180) & (frame[:, :, 0] < 60)
    red = lambda frame: (frame[:, :, 0] > 200) & (frame[:, :, 1] < 80)
    bg_dx = centroid(late, blue) - centroid(early, blue)
    fg_dx = centroid(late, red) - centroid(early, red)
    assert fg_dx > bg_dx + 30
    assert bg_dx > 5 and fg_dx > 0

    def yellow(frame):
        return int(((frame[:, :, 0] > 140) & (frame[:, :, 1] > 120) & (frame[:, :, 2] < 40)).sum())

    mid = render_image_frame(theme, scene, 0.35, 1.6, str(tmp_path))
    done = render_image_frame(theme, scene, 0.85, 1.6, str(tmp_path))
    assert yellow(done) > yellow(mid) > 100
    # "tower" is the third of four words on a 1.6s plate, 0.1s before the share.
    assert overlay_start({"keyword": "tower"}, "Split the tower layer.", 1.6, "vox-explainer") == pytest.approx(0.7)


def test_circle_and_arrow_draw_on_over_time(tmp_path: Path):
    _plate(tmp_path / "a.png", (210, 196, 170, 255))
    episode = load_episode(_episode(tmp_path, """
name: ink
style: history-story
audio_mode: silent
scenes:
  - type: image
    caption: ["red ink"]
    min: 2.4
    image: a.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0}
      to: {scale: 1.06}
    overlays:
      - kind: circle
        cx: 540
        cy: 780
        r: 180
        at: 0.2
        duration: 0.8
        color: [178, 74, 66]
      - kind: arrow
        points: [[200, 400], [700, 900]]
        at: 0.2
        duration: 0.8
        color: [178, 74, 66]
"""))
    scene = scene_payload(episode.scenes[0], episode)
    theme = Theme()

    def ink(frame):
        return int(((frame[:, :, 0] > 140) & (frame[:, :, 1] < 110) & (frame[:, :, 2] < 100)).sum())

    early = render_image_frame(theme, scene, 0.35, 2.4, str(tmp_path))
    late = render_image_frame(theme, scene, 1.2, 2.4, str(tmp_path))
    assert ink(late) > ink(early) > 20


def test_preset_qc_rejects_a_static_or_overspeed_plate():
    report = QCReport(ok=True, video="x", duration=3, width=1080, height=1920)
    _preset_conformance(report, {
        "style": "history-story",
        "scenes": [{
            "index": 0, "id": "year", "type": "image", "duration": 2.4,
            "camera": {"static": True, "zoom_pct_per_s": 0, "pan_px_per_s": {"x": 0, "y": 0}},
        }, {
            "index": 1, "id": "rush", "type": "image", "duration": 2.0,
            "camera": {"static": False, "zoom_pct_per_s": 48.0, "pan_px_per_s": {"x": 0, "y": 0}, "duration": 4.0},
        }],
    })
    assert any("static" in item for item in report.violations)
    assert any("48.00%/s" in item for item in report.violations)
    house = QCReport(ok=True, video="x", duration=3, width=1080, height=1920)
    _preset_conformance(house, {"style": "house", "scenes": [{"type": "image", "duration": 0.2, "index": 0, "id": "a"}]})
    assert house.violations == []


@pytest.fixture
def tiny_theme(monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(
        width=216, height=384, fps=10, scale=1, fit=Fit(0.2)))


def test_sample_episodes_render_and_pass_preset_qc(tiny_theme):
    for name in ("history-story.yaml", "vox-explainer.yaml"):
        episode = load_episode(ROOT / "tests/fixtures/episodes" / "styles" / name)
        manifest = build_manifest(episode)
        assert manifest["missing"] == []
        assert manifest["assets"]
        # Keep the encoded proof out of the repo; the test only needs QC.
        dest = Path("/tmp") / f"{episode.name}.mp4"
        result = render_episode(episode, dest, "fixture", 1)
        assert result["qc"]["ok"], result["qc"]["violations"]
        assert result["audio_mode"] == "silent"


def test_cli_and_mcp_expose_styles_and_assets(capsys):
    assert "shot length" in reference_styles().lower() or "Shot length" in reference_styles()
    assert run(["reference-styles"]) == 0
    assert "history-story" in capsys.readouterr().out
    manifest = json.loads(asset_manifest(str(ROOT / "tests/fixtures/episodes" / "styles" / "vox-explainer.yaml")))
    assert manifest["ok"] and manifest["missing"] == []
    assert run(["assets", str(ROOT / "tests/fixtures/episodes" / "styles" / "history-story.yaml")]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["style"] == "history-story"
    assert all(item["exists"] for item in listed["assets"])
