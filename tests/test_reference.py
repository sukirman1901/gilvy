"""Reference evidence covers the source and preserves uncertainty."""
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from gilvy.cli import run
from gilvy.errors import GilvyError
from gilvy.mcp_server import analyze_reference as mcp_analyze
from gilvy.reference import analyze_reference


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "two-scenes.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=black:s=160x120:r=10:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-vf", "drawbox=color=white:t=fill:enable='gte(t,1)'", "-c:v", "libx264",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def test_auto_cut_frames_and_transition_handles(video, tmp_path):
    result = analyze_reference(video, tmp_path / "auto", width=160)
    assert result["segmentation"] == "automatic_cut_candidates"
    assert len(result["scenes"]) == 2
    assert result["scenes"][0]["end"] == pytest.approx(1)
    assert result["candidate_cuts"][0]["accepted"]
    a, b = result["scenes"]
    assert a["clips"][0]["end"] == pytest.approx(1.25)
    assert b["clips"][0]["start"] == pytest.approx(.75)
    for scene, expected in ((a, 0), (b, 255)):
        for frame in scene["frames"]:
            with Image.open(frame["path"]) as image:
                assert image.getpixel((80, 60))[0] == pytest.approx(expected, abs=2)
        assert scene["review_status"] == "not_reviewed"
        assert all(v is None for v in scene["observed"].values())
        assert all(v is None for v in scene["inferred"].values())
    assert Path(result["contact_sheets"][0]).is_file()
    assert json.loads(Path(result["manifest"]).read_text())["creative_review"] == "required"
    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", a["clips"][0]["path"]]))
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}


def test_uncut_scene_still_gets_full_coverage_and_manual_override(video, tmp_path):
    result = analyze_reference(video, tmp_path / "uncut", scene_boundaries=[], clip_seconds=1, width=160)
    assert result["segmentation"] == "manual_boundaries" and len(result["scenes"]) == 1
    clips = result["scenes"][0]["clips"]
    assert len(clips) == 2 and len(result["scenes"][0]["frames"]) == 6
    assert clips[0]["content_start"] == 0 and clips[-1]["content_end"] == result["duration"]
    assert clips[0]["content_end"] == clips[1]["content_start"]
    manual = analyze_reference(video, tmp_path / "manual", scene_boundaries=[.6], width=160)
    assert manual["scenes"][0]["end"] == .6
    with pytest.raises(GilvyError, match="already exists"):
        analyze_reference(video, tmp_path / "manual")


@pytest.mark.parametrize("options", [
    {"threshold": 0}, {"threshold": float("nan")}, {"min_scene": float("inf")},
    {"width": 161}, {"clip_seconds": 0}, {"scene_boundaries": [1, .5]},
    {"scene_boundaries": [1, 1]}, {"scene_boundaries": [float("nan")]},
    {"scene_boundaries": [2]},
])
def test_invalid_options_do_not_create_outputs(video, tmp_path, options):
    dest = tmp_path / "bad"
    with pytest.raises(GilvyError):
        analyze_reference(video, dest, **options)
    assert not dest.exists()


def test_cli_mcp_and_local_only_errors(video, tmp_path, capsys):
    assert run(["analyze-reference", str(video), "--out", str(tmp_path / "cli"),
                "--boundaries", "1", "--width", "160"]) == 0
    assert len(json.loads(capsys.readouterr().out)["scenes"]) == 2
    result = json.loads(mcp_analyze(str(video), str(tmp_path / "mcp"), scene_boundaries=[], width=160))
    assert result["ok"] and result["scene_count"] == 1 and result["creative_review"] == "required"
    assert "scenes" not in result  # compact navigation; details remain in manifest
    assert not json.loads(mcp_analyze("https://example.com/video.mp4", str(tmp_path / "url")))["ok"]
    assert run(["analyze-reference", "/missing.mp4", "--out", str(tmp_path / "missing")]) == 2


def test_silent_source_and_decode_failure(tmp_path):
    path = tmp_path / "silent.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=blue:s=120x160:r=5:d=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    result = analyze_reference(path, tmp_path / "silent", width=160)
    assert len(result["scenes"]) == 1 and not result["candidate_cuts"]
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(GilvyError):
        analyze_reference(bad, tmp_path / "broken")
