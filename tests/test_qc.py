"""QC rules on synthetic pictures and on raw arrays."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from gilvy.qc import green_ratio, is_blank, is_dark, qc_video


def _write(path: Path, draw: str | None, audio: str, duration: float, color: str) -> None:
    video = f"color=c={color}:s=320x180:r=10:d={duration}"
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        video,
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=880:sample_rate=48000:duration={duration}",
    ]
    if draw:
        cmd += ["-filter_complex", f"[0:v]{draw}[v];[1:a]{audio}[a]", "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-filter_complex", f"[1:a]{audio}[a]", "-map", "0:v", "-map", "[a]"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True)


def test_array_rules():
    blank = np.full((40, 40, 3), 10, np.uint8)
    assert is_blank(blank)
    assert not is_dark(blank)
    assert green_ratio(blank) == 0
    dark = np.zeros((40, 40, 3), np.uint8)
    assert is_dark(dark)
    assert is_blank(dark)
    ink = blank.copy()
    ink[5:25, 5:25] = (236, 236, 236)
    assert not is_blank(ink)
    green = np.zeros((40, 40, 3), np.uint8)
    green[:, :] = (218, 255, 89)
    assert green_ratio(green) > 0.9


def test_qc_pass_blank_green_and_silence(tmp_path: Path):
    ok = tmp_path / "ok.mp4"
    _write(ok, "drawbox=x=20:y=20:w=120:h=50:color=white:t=fill", "anull", 3, "0x0a0a0a")
    # Synthetic fixtures have no sidecar: explicitly select house VO checks.
    report = qc_video(ok, audio_mode="voiceover")
    assert report.ok, report.violations

    blank = tmp_path / "blank.mp4"
    _write(blank, None, "anull", 3, "0x0a0a0a")
    report = qc_video(blank, audio_mode="voiceover")
    assert not report.ok
    assert any("blank" in item for item in report.violations)

    green = tmp_path / "green.mp4"
    _write(green, None, "anull", 3, "0xdaff59")
    report = qc_video(green, audio_mode="voiceover")
    assert not report.ok
    assert any("green" in item for item in report.violations)

    quiet = tmp_path / "quiet.mp4"
    _write(
        quiet,
        "drawbox=x=20:y=20:w=120:h=50:color=white:t=fill",
        "volume=0:enable='between(t,1.0,4.3)'",
        6,
        "0x0a0a0a",
    )
    report = qc_video(quiet, audio_mode="voiceover")
    assert not report.ok
    assert any("silence" in item for item in report.violations)
