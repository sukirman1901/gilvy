"""Regressions for the November 2026 engine audit (F1–F9)."""
import json
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from gilvy.episode import load_episode
from gilvy.errors import GilvyError


def episode(tmp_path, *, camera=None, overlays=None, **extra):
    data = dict(name="audit", style="vox-explainer", audio_mode="silent", scenes=[{
        "type": "image", "caption": ["Audit"], "min": 3, "backdrop": "cork",
        "camera": camera or {"from": {"scale": 1}, "to": {"scale": 1.1}},
        "overlays": overlays or [], "vo": "one two three four five",
    }])
    data.update(extra)
    path = tmp_path / "episode.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


def track_camera(keys, prop="scale"):
    return {"tracks": [{"property": prop, "keys": [{"t": t, "v": v} for t, v in keys]}]}


@pytest.mark.parametrize("keys", [[(0, 1), (1, 2.4), (3, 1)], [(0, 1), (2.6, 1), (3, 1.2)]])
def test_f2_full_camera_path(tmp_path, keys):
    from gilvy.image_scene import camera_metrics
    ep = load_episode(episode(tmp_path, camera=track_camera(keys)))
    metrics = camera_metrics(ep.scenes[0].params["camera"], 3)
    assert not metrics["static"]
    assert metrics["travel"]["scale"] > 0
    assert metrics["peak_zoom_pct_per_s"] >= 49


def test_f2_speed_conformance_uses_segments(tmp_path):
    from gilvy.image_scene import camera_metrics
    from gilvy.presets import camera_problem, RULES
    ep = load_episode(episode(tmp_path, camera=track_camera([(0, 1), (.1, 2.4), (3, 1.1)])))
    metrics = camera_metrics(ep.scenes[0].params["camera"], 3)
    assert camera_problem(metrics, RULES[ep.style], "test") is not None


@pytest.mark.parametrize("onset", [{"keyword": "five"}, {"keyword": "five", "at": .7}])
def test_f3_audio_uses_visual_clock(tmp_path, onset):
    from gilvy.render import build_state, _sfx_cues
    from gilvy.image_scene import overlay_start
    ep = load_episode(episode(tmp_path, overlays=[{"kind": "tag", "text": "five", "sfx": "click", **onset}]))
    state = build_state(ep, [3])
    overlay = ep.scenes[0].params["overlays"][0]
    assert _sfx_cues(ep, state)[0][0] == overlay_start(overlay, ep.scenes[0].vo, 3, ep.style)


@pytest.mark.parametrize("corrupt", [False, True])
def test_f4_card_dependency_preflight(tmp_path, corrupt):
    from gilvy.assets import build_manifest, require_assets
    if corrupt:
        (tmp_path / "card.png").write_bytes(b"broken image")
    ep = load_episode(episode(tmp_path, overlays=[{"kind": "card", "src": "card.png"}]))
    manifest = build_manifest(ep)
    assert any(a["src"] == "card.png" and a["field"] == "overlays[0].src" for a in manifest["assets"])
    with pytest.raises(GilvyError, match="card.png"):
        require_assets(ep)


@pytest.mark.parametrize("overlay", [{"kind": "highlighter"}, {"kind": "circle"},
    {"kind": "arrow", "points": [[1], [2, 3]]},
    {"kind": "highlighter", "x": float("nan"), "y": 0, "w": 1, "h": 1}])
def test_f6_structured_overlay_errors(tmp_path, overlay):
    from gilvy.mcp_server import preview_frames
    reply = json.loads(preview_frames(str(episode(tmp_path, overlays=[overlay])), str(tmp_path / "preview"), "fixture"))
    assert reply["ok"] is False
    assert reply["code"] == "invalid_input"
    assert reply["field"].startswith("scenes[0].overlays[0]")
    assert not (tmp_path / "preview").exists()


def test_f7_keyframe_overscan(tmp_path):
    from gilvy.assets import plate_pixel_size
    cam = track_camera([(0, 1), (1, 2.4), (3, 1.1)])
    cam["tracks"].extend(track_camera([(0, 0), (1, 400), (3, 0)], "x")["tracks"])
    ep = load_episode(episode(tmp_path, camera=cam))
    size = plate_pixel_size(ep.scenes[0].params["camera"])
    assert size["scale"] >= 2.4
    assert size["pan_x"] >= 400
    assert size["width"] >= 4512


def test_f8_rate_percent_only(tmp_path):
    with pytest.raises(GilvyError, match="rate"):
        load_episode(episode(tmp_path, rate="+0Hz"))


def test_f8_invalid_tts_parameters_not_retried(tmp_path, monkeypatch):
    from gilvy.tts import EdgeTTS
    import edge_tts
    attempts = []
    monkeypatch.setattr("gilvy.tts.time.sleep", lambda _: None)
    def invalid(*args, **kwargs):
        attempts.append(1)
        raise ValueError("invalid voice")
    monkeypatch.setattr(edge_tts, "Communicate", invalid)
    with pytest.raises(GilvyError, match="invalid voice"):
        EdgeTTS().synthesize("hello", "bad", "+0%", tmp_path / "vo.mp3", 3)
    assert len(attempts) == 1


def test_f9_signed_tilt():
    from gilvy.voxlook import _perspective
    source = Image.new("RGBA", (100, 140), "white")
    positive = np.asarray(_perspective(source, 12))[:, :, 3]
    negative = np.asarray(_perspective(source, -12))[:, :, 3]
    assert not np.array_equal(positive, negative)
    assert positive[0].sum() < positive[-1].sum()
    assert negative[0].sum() > negative[-1].sum()


@pytest.fixture
def publication(tmp_path, monkeypatch):
    import gilvy.render as r
    from gilvy.qc import QCReport
    ep = load_episode(episode(tmp_path))
    ep.poster = 0
    output = tmp_path / "film.mp4"
    for path in [output, output.with_suffix(".timeline.json"), output.with_suffix(".camera.json"), tmp_path / "film_poster.png"]:
        path.write_bytes(b"approved")
    monkeypatch.setattr(r, "require_ffmpeg", lambda: None)
    monkeypatch.setattr(r, "preflight", lambda e: None)
    monkeypatch.setattr(r, "_encode", lambda state, dest, workers: dest.write_bytes(b"encoded"))
    monkeypatch.setattr(r, "_mux", lambda v, a, t, dest: dest.write_bytes(b"candidate"))
    monkeypatch.setattr(r, "_sheet_from_video", lambda v, s, d, dest: dest.write_bytes(b"sheet"))
    monkeypatch.setattr(r, "_poster", lambda v, s, d, i, dest: dest.write_bytes(b"poster"))
    monkeypatch.setattr(r, "qc_video", lambda v, t: QCReport(True, str(v), 3, 1080, 1920))
    return r, ep, output


@pytest.mark.parametrize("phase", ["_encode", "_mux", "_sheet_from_video", "_poster", "write_timeline", "qc_video"])
def test_f1_failure_preserves_publication(publication, monkeypatch, phase):
    r, ep, output = publication
    before = {p: p.read_bytes() for p in output.parent.glob("film*") if p.is_file()}
    def fail(*args, **kwargs):
        raise GilvyError("injected failure")
    monkeypatch.setattr(r, phase, fail)
    with pytest.raises(GilvyError, match="injected"):
        r.render_episode(ep, output, "fixture", 1)
    assert all(p.read_bytes() == content for p, content in before.items())


def test_f1_qc_rejection_preserves_publication(publication, monkeypatch):
    r, ep, output = publication
    from gilvy.qc import QCReport
    monkeypatch.setattr(r, "qc_video", lambda v, t: QCReport(False, str(v), 3, 1080, 1920, ["rejected"]))
    result = r.render_episode(ep, output, "fixture", 1)
    assert output.read_bytes() == b"approved"
    assert not result["qc"]["ok"]
    assert result["published"] is False


def test_f1_success_paths_point_at_published_artifacts(publication):
    r, ep, output = publication
    result = r.render_episode(ep, output, "fixture", 1)
    assert result["published"] is True
    assert result["qc"]["video"] == str(output)
    for key in ("video", "timeline", "camera", "sheet", "poster"):
        assert Path(result[key]).is_file()


def test_f5_product_standalone_qc(tmp_path):
    from gilvy.product_render import render_product
    from gilvy.qc import qc_video
    spec = {"style": "product", "size": [160, 160], "fps": 10, "duration": 1,
            "background": {"base": "#00ff00"}, "layers": [{"id": "box", "type": "rect", "width": 20, "height": 20}]}
    path = tmp_path / "product.yaml"
    path.write_text(yaml.safe_dump(spec))
    output = tmp_path / "product.mp4"
    render_product(path, output)
    report = qc_video(output).to_dict()
    assert report["ok"], report
    assert report["scope"] == "technical_integrity"
    meta = json.loads(output.with_suffix(".product.json").read_text())
    meta["frames"] += 1
    output.with_suffix(".product.json").write_text(json.dumps(meta))
    assert not qc_video(output).ok
    output.with_suffix(".product.json").unlink()
    unknown = qc_video(output).to_dict()
    assert not unknown["ok"]
    assert unknown["status"] == "needs_context"


def test_f1_concurrent_destination_rejected(publication):
    r, ep, output = publication
    with r._publication_lock(output):
        with pytest.raises(GilvyError, match="already in progress"):
            r.render_episode(ep, output, "fixture", 1)
    assert output.read_bytes() == b"approved"


def test_f1_cancel_after_encode_preserves_output(publication, monkeypatch):
    from gilvy.render_jobs import RenderControl
    r, ep, output = publication
    control = RenderControl()
    def cancel(*args):
        control.cancelled.set()
    monkeypatch.setattr(r, "_encode", cancel)
    with pytest.raises(GilvyError, match="cancelled"):
        r.render_episode(ep, output, "fixture", 1, control=control)
    assert output.read_bytes() == b"approved"


def test_f1_publication_rollback(publication, monkeypatch):
    r, ep, output = publication
    original = r.os.replace
    def fail_video(source, dest):
        if Path(dest) == output:
            raise OSError("injected replace failure")
        return original(source, dest)
    monkeypatch.setattr(r.os, "replace", fail_video)
    with pytest.raises(OSError, match="replace failure"):
        r.render_episode(ep, output, "fixture", 1)
    for path in output.parent.glob("film*"):
        if path.is_file():
            assert path.read_bytes() == b"approved"


def test_f1_stale_metadata_removed_on_success(publication):
    r, ep, output = publication
    ep.poster = None
    for suffix in (".product.json", ".preview.json"):
        output.with_suffix(suffix).write_text("stale")
    r.render_episode(ep, output, "fixture", 1)
    for path in [output.with_suffix(".product.json"), output.with_suffix(".preview.json"), output.with_name("film_poster.png")]:
        assert not path.exists()


def test_f2_actual_duration_cannot_hide_static_track(tmp_path):
    from gilvy.render import build_state
    path = episode(tmp_path, camera=track_camera([(0, 1), (2.6, 1), (3, 1.2)]))
    ep = load_episode(path)
    with pytest.raises(GilvyError, match="static|same"):
        build_state(ep, [2])


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_f6_nonfinite_camera_pan_rejected(tmp_path, value):
    camera = track_camera([(0, 0), (3, value)], "x")
    camera["to"] = {"scale": 1.1}
    with pytest.raises(GilvyError):
        load_episode(episode(tmp_path, camera=camera))


@pytest.mark.parametrize("change", [{"camera": {"scale_max": "bad"}}, {"transition": "bad"},
    {"overlays": [{"kind": []}]}, {"camera": {"tracks": [{"property": "x", "keys": [
        {"t": 0, "v": 0, "ease": "cubic-bezier", "bezier": [0, "bad", 1, 1]}, {"t": 3, "v": 2}]}]}}])
def test_f6_wrong_types_return_input_errors(tmp_path, change):
    from gilvy.mcp_server import preview_frames
    path = episode(tmp_path)
    data = yaml.safe_load(path.read_text())
    data["scenes"][0].update(change)
    path.write_text(yaml.safe_dump(data))
    reply = json.loads(preview_frames(str(path), str(tmp_path / "preview"), "fixture"))
    assert reply["ok"] is False
    assert reply["code"] == "invalid_input"


def test_f6_expected_io_failure_normalized(publication, monkeypatch):
    from gilvy.mcp_server import render_video
    r, ep, output = publication
    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(r, "_encode", fail)
    result = json.loads(render_video(str(ep.source_path), str(output), "fixture", 1))
    assert result["ok"] is False
    assert result["code"] == "io_error"


def test_f7_rotation_and_bezier_overshoot(tmp_path):
    from gilvy.assets import plate_pixel_size
    cam = track_camera([(0, 1), (3, 1.5)])
    cam["tracks"][0]["keys"][0].update(ease="cubic-bezier", bezier=[.2, 2, .8, 2])
    cam["tracks"] += track_camera([(0, 0), (1.5, 45), (3, 0)], "rotation")["tracks"]
    ep = load_episode(episode(tmp_path, camera=cam))
    size = plate_pixel_size(ep.scenes[0].params["camera"], 3)
    assert size["scale"] > 1.5
    assert size["width"] > 1920 * size["scale"]


def test_f6_missing_field_has_exact_path(tmp_path):
    from gilvy.mcp_server import preview_frames
    result = json.loads(preview_frames(str(episode(tmp_path, overlays=[{"kind": "highlighter"}]))))
    assert result["field"] == "scenes[0].overlays[0].x"


@pytest.mark.parametrize("field", ["entrance", "font", "ease"])
def test_f6_overlay_enum_wrong_type(tmp_path, field):
    from gilvy.mcp_server import preview_frames
    overlay = {"kind": "text", "text": "Hello", field: []}
    if field == "ease":
        overlay.update(kind="highlighter", x=0, y=0, w=20, h=20)
        overlay[field] = {"bad": True}
    result = json.loads(preview_frames(str(episode(tmp_path, overlays=[overlay]))))
    assert result["ok"] is False
    assert result["code"] == "invalid_input"


def test_f4_dependency_collector_includes_custom_code_and_music(tmp_path):
    from gilvy.assets import build_manifest, require_assets
    music = tmp_path / "music.wav"
    music.write_bytes(b"fixture")
    data = dict(name="deps", audio_mode="silent", music="music.wav", scenes=[{
        "type": "python", "caption": ["Audit"], "min": 3, "entry": "missing.py:draw"}])
    path = tmp_path / "deps.yaml"
    path.write_text(yaml.safe_dump(data))
    ep = load_episode(path)
    manifest = build_manifest(ep)
    assert {d["kind"] for d in manifest["dependencies"]} >= {"python", "audio", "font"}
    with pytest.raises(GilvyError, match="missing.py"):
        require_assets(ep)


def test_f3_timeline_labels_keyword_estimates(tmp_path):
    from gilvy.render import build_state, write_timeline
    ep = load_episode(episode(tmp_path, overlays=[{"kind": "tag", "text": "five", "keyword": "five", "sfx": "click"}]))
    path = tmp_path / "timeline.json"
    write_timeline(ep, build_state(ep, [3]), path, "fixture")
    events = json.loads(path.read_text())["scenes"][0]["overlay_events"]
    assert events[0]["at"] == pytest.approx(2.3)
    assert events[0]["timing"] == "keyword_estimate"


def test_f1_input_output_alias_rejected(publication):
    r, ep, output = publication
    ep.music = str(output)
    with pytest.raises(GilvyError, match="input"):
        r.render_episode(ep, output, "fixture", 1)
    assert output.read_bytes() == b"approved"


@pytest.mark.parametrize("change", [
    {"grade": []}, {"transition_out": {}}, {"transition_ease": [1]},
    {"camera": []}, {"camera": {"ease": [1]}}, {"overlays": {}},
    {"green": []}, {"camera": {"tracks": [{"property": [], "keys": []}]}},
    {"overlays": [{"kind": "highlighter", "x": 0, "y": 0, "w": 10, "h": 10, "ease": []}]},
])
def test_f6_malformed_tagged_fields(tmp_path, change):
    from gilvy.mcp_server import preview_frames
    path = episode(tmp_path)
    data = yaml.safe_load(path.read_text())
    data["scenes"][0].update(change)
    path.write_text(yaml.safe_dump(data))
    result = json.loads(preview_frames(str(path), str(tmp_path / "never"), "fixture"))
    assert not result["ok"]
    assert result["code"] == "invalid_input"
    assert not (tmp_path / "never").exists()


def test_f6_invalid_yaml(tmp_path):
    from gilvy.mcp_server import preview_frames
    path = tmp_path / "bad.yaml"
    path.write_text("scenes: [}")
    result = json.loads(preview_frames(str(path)))
    assert not result["ok"]
    assert result["code"] == "invalid_input"


def test_f2_camera_sidecar_records_track_endpoints_and_travel(tmp_path):
    from gilvy.render import build_state, write_camera_metrics
    ep = load_episode(episode(tmp_path, camera=track_camera([(0, 1.2), (1, 2), (3, 1.2)])))
    path = tmp_path / "camera.json"
    write_camera_metrics(ep, build_state(ep, [3]), path)
    authored = json.loads(path.read_text())["scenes"][0]["authored"]
    assert authored["scale_start"] == 1.2
    assert authored["scale_end"] == 1.2
    assert authored["travel"]["scale"] == pytest.approx(1.6)


def test_f1_real_encode_rejection_preserves_approved_video(tmp_path, monkeypatch):
    import hashlib
    import gilvy.render as render
    from gilvy.product_render import render_product
    from gilvy.theme import Theme
    from gilvy.formats import Fit
    product = tmp_path / "valid.yaml"
    product.write_text(yaml.safe_dump({"style": "product", "size": [160, 160], "duration": 1, "fps": 10,
        "layers": [{"id": "box", "type": "rect", "width": 30, "height": 30, "x": 80, "y": 80}]}))
    dest = tmp_path / "approved.mp4"
    render_product(product, dest)
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in [dest, dest.with_suffix(".product.json")]}
    house = tmp_path / "house.yaml"
    house.write_text(yaml.safe_dump({"name": "audit", "audio_mode": "silent", "scenes": [
        {"type": "bowl_cta", "caption": ["Hello"], "label": "Hello", "min": 1.8, "green": "focus"}]}))
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(width=216, height=384, fps=10, scale=1, fit=Fit(.2)))
    result = render.render_episode(load_episode(house), dest, "fixture", 1)
    assert not result["qc"]["ok"]
    assert not result["published"]
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == old for path, old in hashes.items())
    assert Path(result["video"]).is_file()
    assert Path(result["video"]) != dest


def test_f7_manifest_covers_tracks_if_voice_extends_shot(tmp_path):
    from gilvy.assets import build_manifest
    path = episode(tmp_path, camera=track_camera([(0, 1), (6, 2.4)]), audio_mode="voiceover")
    data = yaml.safe_load(path.read_text())
    data["scenes"][0]["image"] = "plate.png"
    path.write_text(yaml.safe_dump(data))
    ep = load_episode(path)
    manifest = build_manifest(ep)
    assert manifest["assets"][0]["overscan"]["scale"] >= 2.4


def test_f4_truncated_card_decodes_before_synthesis(tmp_path, monkeypatch):
    from gilvy.render import render_episode
    image = tmp_path / "truncated.jpg"
    Image.new("RGB", (100, 100), "red").save(image)
    image.write_bytes(image.read_bytes()[:-20])
    ep = load_episode(episode(tmp_path, overlays=[{"kind": "card", "src": image.name}]))
    def forbidden(*args, **kwargs):
        pytest.fail("timing must not start for a corrupt card")
    monkeypatch.setattr("gilvy.render.prepare_timing", forbidden)
    with pytest.raises(GilvyError, match="truncated.jpg"):
        render_episode(ep, tmp_path / "film.mp4", "fixture", 1)
