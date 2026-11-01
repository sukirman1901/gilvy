"""Motion windows retain the original clock; comparison reports evidence only."""
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

import gilvy.render as render
from gilvy.cli import run
from gilvy.episode import load_episode
from gilvy.errors import EpisodeError, GilvyError
from gilvy.formats import Fit
from gilvy.mcp_server import compare_versions as mcp_compare, preview_motion as mcp_preview
from gilvy.qc import _grab, _probe, qc_video
from gilvy.review import compare_versions
from gilvy.theme import Theme


def episode_file(tmp_path, mode="silent", duration=2):
    p = tmp_path / f"{mode}.yaml"
    p.write_text(f"""name: review
audio_mode: {mode}
scenes:
  - type: bowl_cta
    caption: ["first beat."]
    label: first
    min: {duration}
  - type: coin_cta
    caption: ["second beat."]
    label: second
    min: {duration}
""")
    return p


@pytest.fixture
def tiny_theme(monkeypatch):
    monkeypatch.setattr(render, "theme_for", lambda ep: Theme(
        width=216, height=384, fps=10, scale=1, fit=Fit(.2)))


@pytest.mark.parametrize("mode", ["ambient", "silent"])
def test_nonvoice_modes_skip_tts_and_use_authored_durations(tmp_path, tiny_theme, monkeypatch, mode):
    p = episode_file(tmp_path, mode, .9)
    monkeypatch.setattr(render, "synthesize", lambda *a: pytest.fail("nonvoice mode called TTS"))
    ep = load_episode(p)
    result = render.render_episode(ep, tmp_path / f"{mode}.mp4", "edge", 1)
    assert result["qc"]["ok"], result["qc"]["violations"]
    assert result["duration"] == 1.8
    assert result["qc"]["scope"] == "technical"
    assert result["creative_review"] == "not_evaluated"
    meta = json.loads(Path(result["timeline"]).read_text())
    assert meta["audio_mode"] == mode and meta["tts"] == "none"
    streams = _probe(Path(result["video"]))["streams"]
    assert any(s["codec_type"] == "audio" for s in streams) == (mode == "ambient")
    if mode == "silent":
        wrong_mode = qc_video(result["video"], audio_mode="voiceover")
        assert "no audio stream" in wrong_mode.violations
    else:
        assert "silent mode should have no audio stream" in qc_video(result["video"], audio_mode="silent").violations


def test_audio_validation_and_voiceover_backward_compatibility(tmp_path):
    p = episode_file(tmp_path, "silent")
    text = p.read_text()
    for mode in ("unknown", "voiceover"):
        p.write_text(text.replace("audio_mode: silent", f"audio_mode: {mode}"))
        with pytest.raises(EpisodeError):
            load_episode(p)
    p.write_text(text.replace("    min: 2\n", ""))
    with pytest.raises(EpisodeError, match="set min explicitly"):
        load_episode(p)
    for bad in (".nan", ".inf"):
        p.write_text(text.replace("min: 2", f"min: {bad}"))
        with pytest.raises(EpisodeError):
            load_episode(p)
    p.write_text(text.replace("audio_mode: silent\n", "").replace("    label:", "    vo: Hello.\n    label:"))
    assert load_episode(p).audio_mode == "voiceover"


def test_window_preserves_clock_crossfade_and_fps(tmp_path, tiny_theme):
    ep = load_episode(episode_file(tmp_path))
    video = tmp_path / "window.mp4"
    result = render.preview_motion(ep, video, start=1.8, duration=.8, workers=1, width=216)
    assert result["start"] == 1.8 and result["duration"] == .8
    assert result["preview_only"] and result["creative_review"] == "required"
    assert result["height"] == 384
    assert qc_video(video).audio_mode == "silent"
    assert not result["timing_estimated"]
    state = render.build_state(ep, [2, 2])
    # The first frame includes the original crossfade; the second crosses into scene 2.
    # A reset scene clock or extra preview fade would cause a large difference.
    for offset, n in ((0, 18), (.4, 22), (.7, 25)):
        actual = _grab(video, offset, 216, 384)
        expected = state.frame_array(n)
        assert np.abs(actual.astype(float) - expected).mean() < 2
    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "stream=r_frame_rate,width,height",
        "-of", "json", str(video)]))
    assert info["streams"][0]["r_frame_rate"] == "10/1"
    assert json.loads(video.with_suffix(".preview.json").read_text())["end"] == 2.6


@pytest.mark.parametrize("kwargs", [
    {"start": -1}, {"start": float("nan")}, {"start": 10},
    {"duration": 0}, {"duration": 13}, {"duration": float("inf")},
    {"width": 161}, {"width": 400},
])
def test_motion_rejects_invalid_ranges_and_sizes(tmp_path, tiny_theme, kwargs):
    ep = load_episode(episode_file(tmp_path))
    with pytest.raises(GilvyError):
        render.preview_motion(ep, tmp_path / "bad.mp4", workers=1, **kwargs)


def test_comparison_detects_changes_and_requires_human_interpretation(tmp_path):
    def clip(name, x):
        p = tmp_path / name
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
            "color=c=0x0a0a0a:s=160x240:r=10:d=1",
            "-vf", f"drawbox=x={x}:y=60:w=20:h=20:color=white:t=fill",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p)], check=True)
        return p
    ref = clip("ref.mp4", 20)
    changed = clip("changed.mp4", 40)
    same = compare_versions(ref, ref, tmp_path / "same", sample_fps=2)
    assert same["identical_sampled_frames"] == same["sample_count"]
    diff = compare_versions(ref, changed, tmp_path / "diff", sample_fps=2)
    assert diff["identical_sampled_frames"] == 0
    assert all(r["mean_absolute_error"] > 0 for r in diff["samples"])
    assert diff["creative_review"] == "required" and "quality score" in diff["limitations"]
    assert Path(diff["sheet"]).is_file()
    for kwargs in ({"reference_start": 2}, {"duration": float("nan")}, {"sample_fps": 0}):
        with pytest.raises(GilvyError):
            compare_versions(ref, changed, tmp_path / "bad", **kwargs)


def test_cli_and_mcp_review_paths_and_errors(tmp_path, tiny_theme):
    ep = episode_file(tmp_path, duration=1)
    output = tmp_path / "cli.mp4"
    assert run(["preview-motion", str(ep), "--duration", ".5", "--width", "216",
                "--workers", "1", "--out", str(output)]) == 0
    mcp_output = tmp_path / "mcp.mp4"
    result = json.loads(mcp_preview(str(ep), str(mcp_output), duration=.5, workers=1, width=216))
    assert result["ok"] and result["preview_only"]
    assert json.loads(mcp_compare(str(output), str(mcp_output), str(tmp_path / "compare")))["ok"]
    assert not json.loads(mcp_preview(str(ep), start=-1))["ok"]
    assert not json.loads(mcp_compare("/missing.mp4", str(output)))["ok"]
