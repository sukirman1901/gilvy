"""Independent final-review regressions; detector tests are owned separately."""
import json
import math
import shutil
import wave

import pytest
import yaml
from PIL import Image

from gilvy.errors import EpisodeError, GilvyError
from tests.test_collage import episode, scene


@pytest.mark.parametrize("dependency", ["spec", "audio", "image", "font", "hardlinked_spec"])
def test_product_sidecar_inputs_preserved_before_encode(tmp_path, monkeypatch, dependency):
    from gilvy.product_render import render_product
    from gilvy.theme import bundled_fonts
    output = tmp_path / "film.mp4"
    sidecar = output.with_suffix(".product.json")
    source = sidecar if dependency == "spec" else tmp_path / "spec.yaml"
    data = {"style": "product", "size": [160, 160], "fps": 2, "duration": 1,
            "layers": [{"id": "box", "type": "rect", "width": 20, "height": 20}]}
    if dependency == "audio":
        with wave.open(str(sidecar), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(b"\0\0" * 8000)
        data["audio"] = sidecar.name
    elif dependency == "image":
        Image.new("RGB", (20, 20), "red").save(sidecar, format="PNG")
        data["layers"] = [{"id": "parent", "type": "group", "width": 100, "height": 100, "children": [
            {"id": "image", "type": "image", "src": sidecar.name, "width": 20, "height": 20}]}]
    elif dependency == "font":
        shutil.copyfile(bundled_fonts() / "Poppins-Regular.ttf", sidecar)
        data["layers"] = [{"id": "title", "type": "text", "text": "Test", "width": 160, "height": 80, "font": sidecar.name}]
    source.write_text(yaml.safe_dump(data))
    if dependency == "hardlinked_spec":
        sidecar.hardlink_to(source)
    output.write_bytes(b"approved")
    before = {p: p.read_bytes() for p in {source, sidecar, output}}
    def forbidden(*args, **kwargs):
        pytest.fail("encoder must not start for an input/publication collision")
    monkeypatch.setattr("gilvy.product_render.subprocess.Popen", forbidden)
    with pytest.raises(GilvyError, match="input"):
        render_product(source, output)
    assert all(p.read_bytes() == data for p, data in before.items())


NUMERIC_EFFECTS = [
    ("shake", "amp"), ("shake", "freq"), ("whip", "seconds"), ("whip", "at"),
    ("flash", "at"), ("flash", "seconds"), ("wipe", "at"), ("wipe", "seconds"),
    ("glitch", "at"), ("glitch", "seconds"), ("flicker", "amount"), ("flicker", "freq"),
    ("vignette", "amount"), ("light_leak", "amount"), ("dust", "amount"), ("rotation", "degrees")]


@pytest.mark.parametrize("kind,field", NUMERIC_EFFECTS)
@pytest.mark.parametrize("value", ["oops", None, [], {}, True, float("nan"), float("inf")])
def test_every_numeric_effect_has_field_error(kind, field, value):
    from gilvy.effects import parse_effects
    with pytest.raises(EpisodeError) as caught:
        parse_effects([{"kind": "dust"}, {"kind": kind, field: value}], 2)
    assert caught.value.code == "invalid_input"
    assert caught.value.field == f"scenes[1].effects[1].{field}"


@pytest.mark.parametrize("value", ["oops", None, []])
def test_effect_error_reaches_mcp_without_render(tmp_path, monkeypatch, value):
    from gilvy.mcp_server import preview_frames
    path = tmp_path / "effects.yaml"
    path.write_text(yaml.safe_dump({"name": "effects", "style": "history-story", "audio_mode": "silent", "scenes": [{
        "type": "image", "composition": "collage", "caption": ["Test"], "min": 2, "backdrop": "cork",
        "effects": [{"kind": "shake", "amp": value}]}]}))
    monkeypatch.setattr("gilvy.mcp_server.preview_episode", lambda *a, **k: pytest.fail("must not render"))
    result = json.loads(preview_frames(str(path)))
    assert result["ok"] is False
    assert result["code"] == "invalid_input"
    assert result["field"] == "scenes[0].effects[0].amp"


@pytest.mark.parametrize("clock,times", [("scene", [0, 1, 2]), ("episode", [40, 50, 60])])
def test_unplaced_background_scale_and_pan_envelope(tmp_path, clock, times):
    from gilvy.assets import build_manifest
    layer = {"id": "background", "role": "background", "src": "paper.png", "depth": 1, "clock": clock,
             "tracks": [{"property": prop, "keys": [{"t": t, "v": v} for t, v in zip(times, values)]}
                        for prop, values in [("scale", [1, 4, 1]), ("x", [0, 400, 0]), ("y", [0, -200, 0])]]}
    ep = episode(tmp_path, scene([layer]))
    asset = build_manifest(ep)["assets"][0]
    assert asset["overscan"] == {"scale": 4, "pan_x": 400, "pan_y": 200}
    assert asset["width"] >= (1080 + 800) * 4
    assert asset["height"] >= (1920 + 400) * 4


def test_unplaced_bezier_extrema_and_camera_gain(tmp_path):
    from gilvy.assets import build_manifest
    from gilvy.keyframes import track_bounds
    tracks = [{"property": p, "keys": [{"t": 0, "v": a, "ease": "cubic-bezier", "bezier": [.2, 2, .8, 2]},
                                       {"t": 2, "v": b}]} for p, a, b in [("scale", 1, 2), ("x", 0, 100)]]
    ep = episode(tmp_path, scene([{"id": "bg", "role": "background", "src": "paper.png", "depth": .5,
                                  "tracks": tracks}], camera={"to": {"scale": 2, "x": 200}}))
    asset = build_manifest(ep)["assets"][0]
    gain = .25 + .75*.5
    scale = (1 + gain) * track_bounds(tracks[0]["keys"])[1]
    pan = 200*gain + track_bounds(tracks[1]["keys"])[1]
    assert asset["overscan"]["scale"] == pytest.approx(scale)
    assert asset["overscan"]["pan_x"] == pytest.approx(pan)
    assert asset["width"] >= math.ceil((1080 + 2*pan) * scale)


def test_unplaced_pan_accounts_for_legacy_output_pixel_tracks(tmp_path):
    from gilvy.assets import build_manifest
    from gilvy.formats import fit_of, get_profile
    layer = {"id": "bg", "role": "background", "src": "paper.png", "depth": 1,
             "tracks": [{"property": "x", "keys": [{"t": 0, "v": 0}, {"t": 2, "v": 400}]}]}
    ep = episode(tmp_path, scene([layer])).with_format("square_1x1")
    asset = build_manifest(ep)["assets"][0]
    assert asset["overscan"]["pan_x"] == pytest.approx(400 / fit_of(get_profile(ep.format)).scale)
