"""Integration regressions for the audited engine plus upstream collage."""
import copy

import numpy as np
import pytest
from PIL import Image

from gilvy.assets import build_manifest, require_assets
from gilvy.errors import GilvyError
from gilvy.render import build_state, _sfx_cues
from tests.test_collage import assets, episode, fragment, picture, scene, theme
from tests.test_audit_hardening import publication


def annotation(**extra):
    return {"kind": "highlighter", "parent": "subject", "clock": "episode", "at": 2.5,
            "x": 10, "y": 10, "w": 80, "h": 30, "duration": .1,
            "color": "#ff0000", "sfx": "click", **extra}


def test_episode_clock_sound_is_absolute(tmp_path):
    ep = episode(tmp_path, scene([fragment()]), scene([fragment()], overlays=[annotation()]))
    assert _sfx_cues(ep, build_state(ep, [2, 2])) == [(2.5, "click")]


def test_shared_event_identity_emits_once(tmp_path):
    shared = annotation(event_id="paper-mark")
    ep = episode(tmp_path, scene([fragment()], overlays=[shared]),
                 scene([fragment()], overlays=[copy.deepcopy(shared)]))
    assert _sfx_cues(ep, build_state(ep, [2, 2])) == [(2.5, "click")]


def test_distinct_simultaneous_sounds_are_not_deduplicated(tmp_path):
    ep = episode(tmp_path, scene([fragment()], overlays=[
        annotation(at=1, event_id="left"), annotation(at=1, event_id="right")]))
    assert _sfx_cues(ep, build_state(ep, [2])) == [(1, "click"), (1, "click")]


@pytest.mark.parametrize("change", [{"at": 2.7}, {"sfx": "pop"}])
def test_conflicting_shared_event_rejected_before_render(tmp_path, change):
    with pytest.raises(GilvyError, match="event_id"):
        ep = episode(tmp_path, scene([fragment()], overlays=[annotation(event_id="same")]),
                     scene([fragment()], overlays=[annotation(event_id="same", **change)]))
        build_state(ep, [2, 2])


def test_incoming_dissolve_sound_uses_absolute_handle_time(tmp_path, monkeypatch):
    assets(tmp_path)
    ep = episode(tmp_path, scene([fragment()], transition_out="dissolve", transition=.5),
                 scene([fragment()], overlays=[annotation(at=1.75)]))
    monkeypatch.setattr("gilvy.render.theme_for", lambda _: theme())
    state = build_state(ep, [2, 2])
    assert _sfx_cues(ep, state) == [(1.75, "click")]
    captured = {}
    def capture(*args, **kwargs):
        captured.update(local=args[2], **kwargs)
        return np.zeros((480, 270, 3))
    monkeypatch.setattr("gilvy.render.render_image_frame", capture)
    state.picture(1, -.25)
    assert captured["local"] == 0
    assert captured["episode_time"] == 1.75


def test_attached_annotations_source_over_opaque_parent(tmp_path, monkeypatch):
    assets(tmp_path)
    Image.new("RGBA", (200, 100), "white").save(tmp_path / "sheet.png")
    ep = episode(tmp_path, scene([fragment(src="sheet.png", alpha="opaque")],
                 overlays=[annotation(at=0, clock="scene", x=0, y=0, w=100, h=100)]))
    captured = []
    def capture(canvas, plane, state):
        captured.append(plane.copy())
    monkeypatch.setattr("gilvy.product.composite", capture)
    picture(ep, 1)
    assert captured[0].getpixel((5, 5)) == (255, 45, 45, 255)


def test_two_attached_overlays_blend_in_painter_order(tmp_path, monkeypatch):
    assets(tmp_path)
    Image.new("RGBA", (200, 100), "white").save(tmp_path / "sheet.png")
    red = annotation(at=0, clock="scene", x=0, y=0, w=100, h=100)
    blue = {**red, "color": "#0000ff"}
    ep = episode(tmp_path, scene([fragment(src="sheet.png", alpha="opaque")], overlays=[red, blue]))
    captured = []
    monkeypatch.setattr("gilvy.product.composite", lambda canvas, plane, state: captured.append(plane.copy()))
    picture(ep, 1)
    expected = Image.alpha_composite(Image.new("RGBA", (1, 1), (255, 45, 45, 255)),
                                    Image.new("RGBA", (1, 1), (0, 0, 255, 210))).getpixel((0, 0))
    assert captured[0].getpixel((5, 5)) == expected


def test_attached_card_missing_and_empty_alpha_are_preflight_errors(tmp_path):
    assets(tmp_path)
    ep = episode(tmp_path, scene([fragment()], overlays=[{
        "kind": "card", "parent": "subject", "src": "card.png", "at": 0}]))
    manifest = build_manifest(ep)
    row = next(a for a in manifest["assets"] if a["src"] == "card.png")
    assert row["field"] == "overlays[0].src"
    assert row["parent"] == "subject"
    with pytest.raises(GilvyError, match="card.png"):
        require_assets(ep)
    Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(tmp_path / "card.png")
    with pytest.raises(GilvyError, match="empty_alpha"):
        require_assets(ep)


def test_placement_envelope_includes_bezier_peak(tmp_path):
    assets(tmp_path)
    item = fragment(tracks=[{"property": "scale", "keys": [
        {"t": 0, "v": 1, "ease": "cubic-bezier", "bezier": [.2, 2, .8, 2]},
        {"t": 2, "v": 2}]}])
    ep = episode(tmp_path, scene([item]))
    row = build_manifest(ep)["assets"][0]
    assert row["overscan"]["scale"] > 2.5
    assert row["width"] > 500 and row["height"] > 250


def test_attached_card_resolution_inherits_parent_scale(tmp_path):
    assets(tmp_path)
    item = fragment(tracks=[{"property": "scale", "keys": [
        {"t": 0, "v": 1, "ease": "cubic-bezier", "bezier": [.2, 2, .8, 2]},
        {"t": 2, "v": 2}]}])
    ep = episode(tmp_path, scene([item], overlays=[{
        "kind": "card", "parent": "subject", "src": "card.png", "at": 0, "w": 100, "h": 100}]))
    rows = build_manifest(ep)["assets"]
    parent = next(a for a in rows if a["src"] == "subject.png")
    card = next(a for a in rows if a["src"] == "card.png")
    assert card["overscan"]["scale"] == parent["overscan"]["scale"]
    assert card["width"] >= 100 * parent["overscan"]["scale"]


def test_event_timeline_reports_global_clock(tmp_path):
    import json
    from gilvy.render import write_timeline
    ep = episode(tmp_path, scene([fragment()]), scene([fragment()], overlays=[annotation(event_id="mark")]))
    path = tmp_path / "timeline.json"
    write_timeline(ep, build_state(ep, [2, 2]), path, "fixture")
    event = json.loads(path.read_text())["scenes"][1]["overlay_events"][0]
    assert event["clock"] == "episode"
    assert event["episode_at"] == 2.5
    assert event["scene_at"] == .5
    assert event["event_id"] == "mark"


@pytest.mark.parametrize("poster", [None, 0])
def test_publication_poster_destination_cannot_replace_dependency(publication, poster):
    render, ep, output = publication
    ep.poster = poster
    image = output.with_name("film_poster.png")
    Image.new("RGB", (10, 10), "red").save(image)
    before = image.read_bytes()
    ep.scenes[0].params["overlays"] = [{"kind": "card", "src": str(image)}]
    with pytest.raises(GilvyError, match="input"):
        render.render_episode(ep, output, "fixture", 1)
    assert image.read_bytes() == before


def test_product_writer_obeys_house_destination_lock(tmp_path):
    import yaml
    from gilvy.product_render import render_product
    from gilvy.render import _publication_lock
    spec = tmp_path / "product.yaml"
    spec.write_text(yaml.safe_dump({"style": "product", "size": [160, 160], "fps": 2, "duration": 1,
        "layers": [{"id": "box", "type": "rect", "width": 20, "height": 20}]}))
    output = tmp_path / "same.mp4"
    output.write_bytes(b"approved")
    with _publication_lock(output):
        with pytest.raises(GilvyError, match="already in progress"):
            render_product(spec, output)
    assert output.read_bytes() == b"approved"


def test_vid_output_does_not_alias_intermediate(publication, monkeypatch):
    render, ep, output = publication
    output = output.with_name("vid.mp4")
    paths = []
    def mux(video, audio, duration, dest):
        paths.extend([video, dest])
        assert video != dest, "mux input aliases output"
        dest.write_bytes(b"candidate")
    monkeypatch.setattr(render, "_mux", mux)
    render.render_episode(ep, output, "fixture", 1)
    assert paths[0].parent != paths[1].parent


def test_narrated_camera_deferred_until_resolved_timing(tmp_path):
    import yaml
    from gilvy.episode import load_episode
    data = {"name": "delayed", "style": "history-story", "audio_mode": "voiceover", "scenes": [{
        "type": "image", "caption": ["Later motion"], "vo": "A long narrated line", "min": 3,
        "image": "paper.png", "camera": {"tracks": [{"property": "scale", "keys": [
            {"t": 0, "v": 1}, {"t": 4, "v": 1}, {"t": 6, "v": 1.2}]}]}}]}
    path = tmp_path / "narrated.yaml"
    path.write_text(yaml.safe_dump(data))
    ep = load_episode(path)
    assert not build_state(ep, [6]).scenes[0]["params"]["camera"] is None
    with pytest.raises(GilvyError, match="same|static"):
        build_state(ep, [3])


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_scene_integer_is_field_error(tmp_path, bad):
    import json
    import yaml
    from gilvy.mcp_server import preview_frames
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"name": "bad", "audio_mode": "silent", "scenes": [{
        "type": "bowl_cta", "caption": ["Test"], "min": 2, "label": "Test", "count": bad}]}))
    result = json.loads(preview_frames(str(path)))
    assert not result["ok"]
    assert result["code"] == "invalid_input"
    assert result["field"] == "scenes[0].count"


def test_malformed_color_property_is_field_error(tmp_path):
    import json
    from gilvy.mcp_server import preview_frames
    ep_path = tmp_path / "ep.yaml"
    try:
        episode(tmp_path, scene([fragment()], color={"tracks": [{"property": [], "keys": []}]}))
    except GilvyError:
        pass
    result = json.loads(preview_frames(str(ep_path)))
    assert not result["ok"]
    assert result["code"] == "invalid_input"
    assert result["field"] == "scenes[0].color.tracks[0].property"


def test_real_collage_render_named_vid(tmp_path, monkeypatch):
    import gilvy.render as render
    assets(tmp_path)
    ep = episode(tmp_path, scene([{"id": "paper", "role": "background", "alpha": "opaque", "src": "paper.png", "depth": 0}, fragment()]))
    monkeypatch.setattr(render, "theme_for", lambda _: theme())
    result = render.render_episode(ep, tmp_path / "vid.mp4", "fixture", 1)
    assert result["published"] and result["qc"]["ok"]
    assert (tmp_path / "vid.mp4").is_file()
