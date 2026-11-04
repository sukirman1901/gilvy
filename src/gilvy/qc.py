"""Quality check for a finished mp4.

Green is one focus idea. Measured as green pixels (G-B>35 and G>=R) divided by
pixels that are not background (max channel > 30). Silence is the voice, not the
low music bed: a high-pass leaves speech and drops the pad tones.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from gilvy.errors import GilvyError
from gilvy.presets import PHOTO_PRESETS, RULES, camera_problem


def checks_green(style: str | None) -> bool:
    """Sepia grades trip the green mask. Those styles skip the tint check."""
    return not bool(RULES.get(style or "", {}).get("skip_green"))

MAX_GREEN = 0.40
MAX_NONE_GREEN = 0.012
MIN_FOCUS_GREEN = 0.004
MAX_CAPTION_GREEN = 0.012
BLANK_NONBLACK = 0.00020
DARK_MEAN = 4.0
MAX_INTERNAL_GAP = 2.0
HEAD_SKIP = 0.45
TAIL_SKIP = 0.75
SAMPLE_FPS = 2


@dataclass
class QCReport:
    ok: bool
    video: str
    duration: float
    width: int
    height: int
    violations: list[str] = field(default_factory=list)
    green_ratio_max: float = 0.0
    scenes: list[dict] = field(default_factory=list)
    blank_times: list[float] = field(default_factory=list)
    dark_times: list[float] = field(default_factory=list)
    silence_gaps: list[dict] = field(default_factory=list)
    audio_mode: str = "voiceover"

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "scope": "technical",
            "creative_review": "not_evaluated",
            "audio_mode": self.audio_mode,
            "video": self.video,
            "duration": round(self.duration, 3),
            "width": self.width,
            "height": self.height,
            "violations": self.violations,
            "green_ratio_max": round(self.green_ratio_max, 4),
            "scenes": self.scenes,
            "blank_times": [round(t, 2) for t in self.blank_times[:12]],
            "dark_times": [round(t, 2) for t in self.dark_times[:12]],
            "silence_gaps": self.silence_gaps,
        }

    def text(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        lines = [f"QC {status} (technical only)  {self.video}  {self.duration:.2f}s  {self.width}x{self.height}"]
        if self.scenes:
            for scene in self.scenes:
                lines.append(
                    f"  scene {scene['index'] + 1} {scene['id']}  {scene['role']:5}  green {scene['ratio'] * 100:.1f}%"
                )
        lines.append(f"  green max {self.green_ratio_max * 100:.1f}%")
        if self.silence_gaps:
            for gap in self.silence_gaps:
                lines.append(f"  silence {gap['start']:.2f}s–{gap['end']:.2f}s ({gap['duration']:.2f}s)")
        else:
            lines.append("  silence gaps: none")
        lines.append(f"  blank frames: {len(self.blank_times)}")
        lines.append(f"  dark frames: {len(self.dark_times)}")
        for item in self.violations:
            lines.append(f"- {item}")
        return "\n".join(lines)


def _preset_conformance(report: QCReport, meta: dict) -> None:
    """Shot length and plate speed for opt-in image presets. House timelines skip this."""
    style = str(meta.get("style") or "house")
    if style not in PHOTO_PRESETS:
        return
    rules = RULES[style]
    for scene in meta.get("scenes") or []:
        if scene.get("type") != "image":
            continue
        label = f"scene {int(scene.get('index', 0)) + 1} ({scene.get('id') or 'image'})"
        duration = float(scene["duration"])
        if not rules["shot_min"] <= duration <= rules["shot_max"]:
            report.violations.append(
                f"{label} is {duration:.2f}s, outside the {style} shot range "
                f"{rules['shot_min']:.2f}–{rules['shot_max']:.2f}s"
            )
        camera = scene.get("camera")
        if not camera:
            report.violations.append(f"{label} is an image plate with no camera move recorded")
            continue
        problem = camera_problem(camera, rules, label)
        if problem:
            report.violations.append(problem)


def green_parts(frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    red = frame[:, :, 0].astype(np.int16)
    green = frame[:, :, 1].astype(np.int16)
    blue = frame[:, :, 2].astype(np.int16)
    nonblack = frame.max(axis=2) > 30
    mask = nonblack & ((green - blue) > 35) & (green >= red)
    return mask, nonblack


def green_ratio(frame: np.ndarray) -> float:
    mask, nonblack = green_parts(frame)
    total = int(nonblack.sum())
    if total == 0:
        return 0.0
    return float(mask.sum()) / total


def caption_green_ratio(frame: np.ndarray) -> float:
    height = frame.shape[0]
    y0 = int(round(1260 * height / 1920))
    mask, nonblack = green_parts(frame)
    total = int(nonblack.sum())
    if total == 0:
        return 0.0
    return float(mask[y0:].sum()) / total


def nonblack_ratio(frame: np.ndarray) -> float:
    return float((frame.max(axis=2) > 30).mean())


def is_blank(frame: np.ndarray) -> bool:
    return nonblack_ratio(frame) < BLANK_NONBLACK


def is_dark(frame: np.ndarray) -> bool:
    return float(frame.mean()) < DARK_MEAN


def _probe(path: Path) -> dict:
    run = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,avg_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise GilvyError(f"ffprobe failed on {path}: {run.stderr.strip()}")
    return json.loads(run.stdout or "{}")


def _grab(path: Path, t: float, width: int, height: int) -> np.ndarray:
    run = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-ss",
            f"{max(0.0, t):.3f}",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ],
        capture_output=True,
    )
    need = width * height * 3
    if run.returncode != 0 or len(run.stdout) < need:
        raise GilvyError(f"could not read a frame at {t:.2f}s from {path}")
    return np.frombuffer(run.stdout[:need], np.uint8).reshape(height, width, 3)


def _silence_gaps(path: Path, duration: float) -> list[dict]:
    run = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(path),
            "-af",
            "highpass=f=400,silencedetect=n=-35dB:d=0.3",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    text = run.stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", text)]
    gaps = []
    for i, start in enumerate(starts):
        end = ends[i] if i < len(ends) else duration
        gaps.append({"start": start, "end": end, "duration": round(end - start, 3)})
    return gaps


def _load_timeline(video: Path, override: str | None) -> dict | None:
    if override:
        path = Path(override)
        if not path.is_file():
            raise GilvyError(f"timeline not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    sidecar = video.with_suffix(".timeline.json")
    if sidecar.is_file():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    nested = video.parent / video.stem / "timeline.json"
    if nested.is_file():
        return json.loads(nested.read_text(encoding="utf-8"))
    preview = video.with_suffix(".preview.json")
    if preview.is_file():
        return json.loads(preview.read_text(encoding="utf-8"))
    return None


def _scene_body(t: float, meta: dict | None) -> bool:
    """True when t is past the draw-on and before the crossfade of some scene.

    A scene is allowed to start empty. Blank means it is still empty once the
    picture should be readable.
    """
    if not meta or not meta.get("scenes"):
        return True
    for scene in meta.get("scenes") or []:
        start = float(scene["start"])
        end = start + float(scene["duration"])
        if start <= t < end:
            return (t - start) >= 0.6 and (end - t) >= 0.5
    return False


def _caption_allows_green(scene: dict) -> bool:
    for line in scene.get("caption") or []:
        for word in str(line).split(" "):
            if word.startswith("$"):
                return True
    return False


def qc_video(path: str | Path, timeline: str | None = None, audio_mode: str | None = None) -> QCReport:
    video = Path(path)
    if not video.is_file():
        raise GilvyError(f"video not found: {video}")
    probed = _probe(video)
    streams = probed.get("streams") or []
    picture = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if picture is None:
        raise GilvyError(f"no video stream in {video}")
    width = int(picture.get("width") or 0)
    height = int(picture.get("height") or 0)
    duration = float((probed.get("format") or {}).get("duration") or 0)
    report = QCReport(ok=True, video=str(video), duration=duration, width=width, height=height)
    meta = _load_timeline(video, timeline)
    check_green = checks_green((meta or {}).get("style"))

    mode = audio_mode or (meta or {}).get("audio_mode", "voiceover")
    if mode not in {"voiceover", "ambient", "silent"}:
        raise GilvyError("audio_mode must be voiceover, ambient, or silent")
    report.audio_mode = mode
    if mode == "silent" and audio is not None:
        report.violations.append("silent mode should have no audio stream")
    elif mode != "silent" and audio is None:
        report.violations.append("no audio stream")
    elif mode == "voiceover":
        gaps = _silence_gaps(video, duration)
        speech = duration - sum(g["duration"] for g in gaps)
        if duration > 0 and speech < duration * 0.15:
            report.violations.append("voice-over missing: almost no energy above the music bed")
        for gap in gaps:
            internal = gap["start"] >= 0.35 and gap["end"] <= max(0.0, duration - 0.5)
            if internal and gap["duration"] >= MAX_INTERNAL_GAP:
                report.silence_gaps.append(gap)
                report.violations.append(
                    f"silence gap {gap['start']:.2f}s–{gap['end']:.2f}s ({gap['duration']:.2f}s) is longer than {MAX_INTERNAL_GAP:.0f}s"
                )

    if width > 0 and height > 0 and duration > 0:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps={SAMPLE_FPS}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        assert proc.stdout is not None
        frame_bytes = width * height * 3
        index = 0
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            frame = np.frombuffer(buf, np.uint8).reshape(height, width, 3).copy()
            t = index / SAMPLE_FPS
            index += 1
            ratio = green_ratio(frame)
            report.green_ratio_max = max(report.green_ratio_max, ratio)
            if check_green and ratio > MAX_GREEN:
                report.violations.append(f"green ratio {ratio * 100:.1f}% at {t:.2f}s exceeds {MAX_GREEN * 100:.0f}%")
            in_fade = t < HEAD_SKIP or t > duration - TAIL_SKIP
            readable = (not in_fade) and _scene_body(t, meta)
            if readable and is_blank(frame):
                report.blank_times.append(t)
            if readable and is_dark(frame):
                report.dark_times.append(t)
        proc.wait()
        if report.blank_times:
            shown = ", ".join(f"{t:.2f}s" for t in report.blank_times[:6])
            report.violations.append(f"blank frame(s) with no drawing: {shown}")
        if report.dark_times:
            shown = ", ".join(f"{t:.2f}s" for t in report.dark_times[:6])
            report.violations.append(f"dark frame(s) below the background: {shown}")

    if meta:
        expected_w = int(meta.get("width") or 1080)
        expected_h = int(meta.get("height") or 1920)
        if width != expected_w or height != expected_h:
            report.violations.append(f"frame size {width}x{height}, expected {expected_w}x{expected_h}")
        expected_dur = float(meta.get("duration") or 0)
        if expected_dur and abs(expected_dur - duration) > 0.35:
            report.violations.append(f"duration {duration:.2f}s does not match the timeline {expected_dur:.2f}s")
        for scene in meta.get("scenes") or []:
            start = float(scene["start"])
            dur = float(scene["duration"])
            t = start + dur * 0.8
            frame = _grab(video, min(t, max(0.0, duration - 0.05)), width, height)
            ratio = green_ratio(frame)
            role = scene.get("green") or "any"
            row = {
                "index": scene.get("index", 0),
                "id": scene.get("id") or scene.get("type"),
                "role": role,
                "t": round(t, 3),
                "ratio": ratio,
            }
            report.scenes.append(row)
            report.green_ratio_max = max(report.green_ratio_max, ratio)
            label = f"scene {row['index'] + 1} ({row['id']})"
            if check_green and ratio > MAX_GREEN:
                report.violations.append(f"{label} green ratio {ratio * 100:.1f}% exceeds {MAX_GREEN * 100:.0f}%")
            if check_green and role == "none" and ratio > MAX_NONE_GREEN:
                report.violations.append(
                    f"{label} should have no green (structure stays white) but green is {ratio * 100:.1f}%"
                )
            if check_green and role == "focus" and ratio < MIN_FOCUS_GREEN:
                report.violations.append(f"{label} is missing its one green focus ({ratio * 100:.1f}%)")
            if check_green and not _caption_allows_green(scene) and caption_green_ratio(frame) > MAX_CAPTION_GREEN:
                report.violations.append(f"{label} has green in the caption. Key words stay white.")
            if is_blank(frame):
                report.violations.append(f"{label} is blank at {t:.2f}s, when the scene should be readable")
        _preset_conformance(report, meta)

    # The scan can record the same overflow at several timestamps. Keep the first of each wording.
    deduped = []
    for item in report.violations:
        if item not in deduped:
            deduped.append(item)
    report.violations = deduped
    report.ok = not report.violations
    return report
