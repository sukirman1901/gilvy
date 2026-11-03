"""Product rendering is opt-in, deterministic, and preserves group geometry/time."""

import copy
import json
import wave
from pathlib import Path

import numpy as np
import pytest
import yaml

from gilvy.cli import run
from gilvy.errors import GilvyError
from gilvy.mcp_server import (
    render_product as mcp_render,
    preview_product as mcp_preview,
)
from gilvy.product import ProductFilm, DEFAULTS, interpolate, project, validate
from gilvy.product_render import render_product
from gilvy.product_ui import component


def spec():
    return {
        "style": "product",
        "size": [160, 160],
        "fps": 10,
        "duration": 1.2,
        "background": {"base": "#000000"},
        "layers": [
            {
                "id": "box",
                "type": "rect",
                "width": 10,
                "height": 10,
                "radius": 0,
                "fill": "#ffffff",
                "x": 25,
                "y": 80,
                "keyframes": {"x": [[0, 25], [1.2, 125, "linear"]]},
            }
        ],
    }


def test_absolute_clock_geometry_group_and_alpha():
    s = spec()
    film = ProductFilm(s)
    for t, x in ((0, 25), (0.6, 75)):
        pixels = np.array(film.frame(t))[:, :, 0]
        assert pixels[80, x] > 240
        assert abs(np.where(pixels > 200)[1].mean() - x) < 1
    # Parent positions are centers; child centers are in the local group plane.
    child = {
        "id": "child",
        "type": "rect",
        "width": 10,
        "height": 10,
        "radius": 0,
        "fill": "#ffffff",
        "x": 30,
        "y": 20,
    }
    s["layers"] = [
        {
            "id": "group",
            "type": "group",
            "width": 60,
            "height": 40,
            "x": 90,
            "y": 70,
            "children": [child],
        }
    ]
    p = np.array(ProductFilm(s).frame(0.6))
    assert p[70, 90, 0] == 255 and p[20, 30, 0] == 0
    s["layers"][0]["opacity"] = 0
    assert np.array(ProductFilm(s).frame(0.6)).max() == 0
    identity = {**DEFAULTS, "x": 50, "y": 40}
    assert np.allclose(
        project((100, 80), identity), [[0, 0], [100, 0], [100, 80], [0, 80]]
    )
    tilted = project((100, 80), {**identity, "tilt_y": 30})
    assert not np.allclose(tilted, project((100, 80), identity))
    assert not np.isclose(
        tilted[1, 1] - tilted[0, 1], 0
    )  # perspective creates unequal edge heights


def test_temporal_sampling_spreads_motion_but_keeps_static_frames():
    s = spec()
    plain = np.array(ProductFilm(s).frame(0.6))
    s.update(samples=5, shutter=1)
    blurred = np.array(ProductFilm(s).frame(0.6))
    assert (blurred[:, :, 0].max(axis=0) > 5).sum() > (
        plain[:, :, 0].max(axis=0) > 5
    ).sum()
    del s["layers"][0]["keyframes"]
    static = np.array(ProductFilm(s).frame(0.6))
    s["samples"] = 1
    assert np.array_equal(static, np.array(ProductFilm(s).frame(0.6)))
    assert interpolate([[0, 0], [1, 10, "linear"]], 0.25) == 2.5
    assert interpolate([[0, 0], [1, 10, "out_cubic"]], 0.25) > 2.5


def test_components_are_alpha_planes_and_progress_reveals_content():
    for kind in ("text", "rect", "cursor", "progress", "menu", "panel"):
        node = {
            "type": kind,
            "width": 640,
            "height": 420,
            "text": "Clear motion",
            "items": ["First", "Second", "Third"],
        }
        for variant in ("inbox", "form", "workflow") if kind == "panel" else ("inbox",):
            node["variant"] = variant
            im = component(node, 0.5)
            assert im.mode == "RGBA" and im.getbbox()
    text = {
        "type": "text",
        "width": 300,
        "height": 90,
        "text": "One two three",
        "reveal": "words",
    }
    assert component(text, 0).getbbox() is None
    assert component(text, 1).getbbox() is not None


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(style="house"),
        lambda s: s.update(duration=float("nan")),
        lambda s: s.update(samples=99),
        lambda s: s.update(size=[161, 160]),
        lambda s: s["layers"][0].update(scale=0),
        lambda s: s["layers"][0].update(tilt_y=89),
        lambda s: s["layers"][0].update(keyframes={"x": [[1, 0], [0, 1]]}),
        lambda s: s["layers"][0].update(keyframes={"opacity": [[0, 1], [1, 2]]}),
        lambda s: s["layers"][0].update(keyframes={"x": [[0, 0], [1, 1, "unknown"]]}),
        lambda s: s["layers"][0].update(fill=7),
        lambda s: s["layers"].append(copy.deepcopy(s["layers"][0])),
    ],
)
def test_invalid_specs_fail_before_render(change):
    s = spec()
    change(s)
    with pytest.raises(GilvyError):
        validate(s)


def test_real_encode_window_audio_cli_and_mcp(tmp_path):
    s = spec()
    path = tmp_path / "film.yaml"
    path.write_text(yaml.safe_dump(s))
    result = render_product(path, tmp_path / "silent.mp4", start=0.4, duration=0.5)
    assert result["frames"] == 5 and result["audio_mode"] == "silent"
    assert result["qc"] == {"ok": True, "scope": "technical_integrity"}
    assert result["creative_review"] == "required"
    # The encoded window keeps the global clock instead of replaying the entrance.
    import subprocess

    frame = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            result["video"],
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    pixels = np.frombuffer(frame, np.uint8).reshape(160, 160, 3)
    assert abs(np.where(pixels[:, :, 0] > 200)[1].mean() - (25 + 100 / 3)) < 2
    with wave.open(str(tmp_path / "short.wav"), "w") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(
            (np.sin(np.arange(1600) * 0.3) * 4000).astype("int16").tobytes()
        )
    s["audio"] = "short.wav"
    path.write_text(yaml.safe_dump(s))
    sound = json.loads(mcp_render(str(path), str(tmp_path / "audio.mp4")))
    assert sound["ok"] and sound["audio_mode"] == "file" and sound["frames"] == 12
    assert (
        run(
            [
                "preview-product",
                str(path),
                "--out",
                str(tmp_path / "preview"),
                "--times",
                ".1",
                ".8",
            ]
        )
        == 0
    )
    assert not json.loads(mcp_preview(str(path), str(tmp_path / "preview")))["ok"]
    assert not json.loads(mcp_render(str(path), str(tmp_path / "bad.mp4"), start=-1))[
        "ok"
    ]
    assert (
        run(
            [
                "render-product",
                str(path),
                "--out",
                str(tmp_path / "cli.mp4"),
                "--duration",
                ".2",
            ]
        )
        == 0
    )
    assert Path(tmp_path / "cli.product.json").is_file()
