"""Extract evidence for reference study; never claim to recover source layers."""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from gilvy.errors import GilvyError


LIMITATIONS = (
    "Evidence extraction only, not automatic visual understanding or editable reconstruction. "
    "Hard-cut scores can miss morphs/fades or mistake large motion for a cut. "
    "soft_transitions are dissolve candidates from a low-resolution blend test. "
    "A fast join can still look like a hard cut, and a push can occasionally look like a dissolve. "
    "They are not used as scene boundaries until you pass --boundaries. "
    "Frame timestamps are requested seek times, not recovered keyframes. "
    "Inspect every motion clip; fill observations separately from inferred easing, camera, and layers."
)


def _run(args: list[str], timeout: int = 180) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GilvyError(f"reference extraction failed: {exc}") from exc
    if result.returncode:
        raise GilvyError(f"reference extraction failed: {result.stderr[-2000:].strip()}")
    return result.stdout


def _cuts(text: str, duration: float, threshold: float, minimum: float) -> list[dict]:
    """Pair metadata timestamps with scene scores, then suppress short scenes."""
    candidates = []
    time = None
    for line in text.splitlines():
        match = re.search(r"pts_time:([0-9.eE+-]+)", line)
        if match:
            time = float(match.group(1))
        match = re.search(r"lavfi.scene_score=([0-9.eE+-]+)", line)
        if match and time is not None:
            score = float(match.group(1))
            if math.isfinite(time) and math.isfinite(score) and 0 < time < duration:
                candidates.append({"time": time, "score": score, "accepted": False})
    last = 0.0
    for row in candidates:
        t = row["time"]
        if row["score"] >= threshold and t - last >= minimum and duration - t >= minimum:
            row["accepted"] = True
            last = t
    return candidates


def _gray_frames(source: Path, dimensions: tuple[int, int]) -> tuple[np.ndarray, int, int]:
    """Native-rate gray frames, area-scaled. Duplicate source frames are kept."""
    width = 80
    height = int(round(width * dimensions[1] / dimensions[0]))
    height -= height % 2
    height = max(2, height)
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-nostdin", "-i", str(source), "-an",
             "-vf", f"scale={width}:{height}:flags=area",
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GilvyError(f"reference extraction failed: {exc}") from exc
    if result.returncode:
        raise GilvyError(f"reference extraction failed: {result.stderr[-2000:].decode(errors='replace').strip()}")
    frame = width * height
    count = len(result.stdout) // frame
    if count < 2:
        raise GilvyError("reference extraction failed: not enough frames to test dissolves")
    frames = np.frombuffer(result.stdout[:count * frame], np.uint8).reshape(count, height, width).copy()
    return frames, width, height


def _soft_transitions(frames: np.ndarray, fps: float, hard_times: list[float]) -> list[dict]:
    """Cross-dissolves: change spread across 0.25–2.0s that matches a linear blend.

    A one-frame jump stays a hard cut. Thresholds were checked against the
    attached history short: joins near 9.0s and 14.6s match; the 5.68s join
    is a single-frame cut and is left in the hard-cut list.
    """
    if fps <= 0 or len(frames) < 4:
        return []
    gray = frames.astype(np.float32)
    step = np.mean(np.abs(np.diff(gray, axis=0)), axis=(1, 2))
    kept = [0]
    for index in range(len(step)):
        if step[index] >= 0.8:
            kept.append(index + 1)
    if kept[-1] != len(gray) - 1:
        kept.append(len(gray) - 1)

    def distance(a: int, b: int) -> float:
        return float(np.mean(np.abs(gray[a] - gray[b])))

    found = []
    for start in range(len(kept)):
        ia = kept[start]
        for stop in range(start + 2, len(kept)):
            ib = kept[stop]
            span = (ib - ia) / fps
            if span < 0.25:
                continue
            # Photo dissolves may run to 2.0s. The old 0.80s ceiling cut a 1.4s
            # blend off before the 10%–90% clock (1.12s) could even be reported.
            if span > 2.0:
                break
            t0, t1 = ia / fps, ib / fps
            if any(t0 + 0.06 < cut < t1 - 0.06 for cut in hard_times):
                continue
            end = distance(ia, ib)
            # 18 separates a real plate change from sensor-scale noise. A mild
            # change only counts when it is very close to a linear blend, so a
            # slow push (blend residual around 0.4) does not qualify.
            if end < 18:
                continue
            sequence = kept[start:stop + 1]
            steps = [distance(sequence[i], sequence[i + 1]) for i in range(len(sequence) - 1)]
            peak = max(steps) if steps else end
            if peak > 0.72 * end:
                continue
            errors = []
            for sample in sequence[1:-1]:
                alpha = (sample - ia) / max(1, ib - ia)
                mix = (1 - alpha) * gray[ia] + alpha * gray[ib]
                errors.append(float(np.mean(np.abs(gray[sample] - mix))))
            if not errors:
                continue
            ratio = float(np.mean(errors)) / end
            if ratio > 0.42 or (end < 28 and ratio > 0.22):
                continue
            found.append((1 - ratio, t0, t1, end))
    # A tight linear blend is expanded to its longest passing span. The single
    # best score sits on the 10%–90% core (a 1.4s dissolve reads as 1.1s).
    # Weaker candidates stay, so a softer join is not dropped for a tighter one elsewhere.
    tight = [row for row in found if row[0] >= 0.95]
    rest = [row for row in found if row[0] < 0.95]
    tight.sort(key=lambda row: ((row[2] - row[1]), row[0]), reverse=True)
    rest.sort(reverse=True)
    found = tight + rest
    chosen = []
    for score, t0, t1, end in found:
        if any(not (t1 < row["start"] - 0.05 or t0 > row["end"] + 0.05) for row in chosen):
            continue
        chosen.append({
            "start": round(t0, 3),
            "end": round(t1, 3),
            "duration": round(t1 - t0, 3),
            "kind": "dissolve",
            "score": round(score, 3),
            "endpoint_delta": round(end, 2),
        })
    chosen.sort(key=lambda row: row["start"])
    return chosen


def detect_soft_transitions(video_path: str | Path, hard_times: list[float] | None = None) -> list[dict]:
    """Dissolve candidates for a local video. Hard-cut times are not re-labeled."""
    source = Path(video_path).expanduser().resolve()
    if not source.is_file():
        raise GilvyError(f"video not found: {source}")
    try:
        info = json.loads(_run(["ffprobe", "-v", "error", "-show_entries",
                               "stream=codec_type,width,height,avg_frame_rate",
                               "-of", "json", str(source)]))
        picture = next(s for s in info.get("streams", []) if s.get("codec_type") == "video")
        dimensions = (int(picture["width"]), int(picture["height"]))
        fps = float(Fraction(picture.get("avg_frame_rate", "0/1")))
    except (ValueError, KeyError, StopIteration, ZeroDivisionError) as exc:
        raise GilvyError("could not read video dimensions, rate and duration") from exc
    frames, _, _ = _gray_frames(source, dimensions)
    return _soft_transitions(frames, fps, list(hard_times or []))


def analyze_reference(video_path: str | Path, output_dir: str | Path,
                      threshold: float = .3, min_scene: float = .8,
                      scene_boundaries: list[float] | None = None,
                      clip_seconds: float = 8, width: int = 640) -> dict:
    """Extract local video into scene evidence, full-coverage clips and review notes.

    Manual boundaries are interior seconds; [] deliberately selects one scene.
    Clips overlap scene/chunk edges by .25s to retain transition context. Source
    audio is retained when present. No network downloader or vision model runs.
    The output directory must be new, preventing stale or overwritten evidence.
    """
    values = (threshold, min_scene, clip_seconds)
    if not all(math.isfinite(v) for v in values):
        raise GilvyError("reference options must be finite")
    if not 0 < threshold <= 1 or not .1 <= min_scene <= 60 or not 1 <= clip_seconds <= 12:
        raise GilvyError("threshold: (0,1]; min_scene: [.1,60]; clip_seconds: [1,12]")
    if not isinstance(width, int) or isinstance(width, bool) or not 160 <= width <= 1280 or width % 2:
        raise GilvyError("width must be an even integer from 160 to 1280")
    if str(video_path).startswith(("http:", "https:")):
        raise GilvyError("use a local video file; run download-reference first and pass its returned video path")
    source = Path(video_path).expanduser().resolve()
    dest = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise GilvyError(f"video not found: {source}")
    if dest.exists():
        raise GilvyError("reference output already exists; choose a new directory")
    if any(shutil.which(tool) is None for tool in ("ffmpeg", "ffprobe")):
        raise GilvyError("ffmpeg and ffprobe are required")
    try:
        info = json.loads(_run(["ffprobe", "-v", "error", "-show_entries",
                               "format=duration:stream=codec_type,width,height,avg_frame_rate,duration",
                               "-of", "json", str(source)]))
        picture = next(s for s in info.get("streams", []) if s.get("codec_type") == "video")
        duration = float(picture.get("duration") or info.get("format", {}).get("duration", 0))
        dimensions = (int(picture["width"]), int(picture["height"]))
        rate = float(Fraction(picture.get("avg_frame_rate", "0/1")))
    except (ValueError, KeyError, StopIteration, ZeroDivisionError) as exc:
        raise GilvyError("could not read video dimensions, rate and duration") from exc
    if not math.isfinite(duration) or not 0 < duration <= 600 or min(dimensions) <= 0 or rate <= 0:
        raise GilvyError("reference must have video and a duration > 0 and <= 600 seconds")
    candidates = []
    if scene_boundaries is None:
        metadata = _run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(source), "-an", "-vf",
                         f"scale=160:-2,select=gte(scene\\,{threshold}),metadata=print:file=-",
                         "-f", "null", "-"])
        candidates = _cuts(metadata, duration, threshold, min_scene)
        interior = [row["time"] for row in candidates if row["accepted"]]
        method = "automatic_cut_candidates"
    else:
        if len(scene_boundaries) > 59 or any(
            not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t)
            or not 0 < t < duration for t in scene_boundaries
        ):
            raise GilvyError("supply at most 59 finite interior boundary times")
        interior = list(scene_boundaries)
        if interior != sorted(set(interior)):
            raise GilvyError("manual boundaries must be unique and increasing")
        method = "manual_boundaries"
    bounds = [0.0, *interior, duration]
    if len(bounds) - 1 > 60:
        raise GilvyError("more than 60 scenes detected; increase threshold/min_scene or pass manual boundaries")
    soft = _soft_transitions(_gray_frames(source, dimensions)[0], rate, interior)
    # All validation precedes output creation. Failure leaves evidence for diagnosis;
    # the manifest is written only when every extraction succeeded.
    dest.mkdir(parents=True)
    scenes = []
    all_frames = []
    for i, (start, end) in enumerate(zip(bounds, bounds[1:]), 1):
        scene_dir = dest / f"scene-{i:03}"
        scene_dir.mkdir()
        frames, clips = [], []
        # Always sample long uncut scenes too: every <=8s chunk gets 3 stills
        # and a playable clip, rather than pretending one settled frame is study.
        count = max(1, math.ceil((end - start) / clip_seconds))
        for chunk in range(count):
            a = start + chunk * (end - start) / count
            b = start + (chunk + 1) * (end - start) / count
            for j, fraction in enumerate((.12, .45, .80), 1):
                t = a + (b - a) * fraction
                frame_path = scene_dir / f"c{chunk+1:03}-f{j}.png"
                _run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{t:.9f}", "-i", str(source),
                      "-frames:v", "1", "-vf", f"scale={width}:-2", "-threads", "1", str(frame_path)])
                if not frame_path.is_file():
                    raise GilvyError(f"no frame decoded at {t:.6f}s")
                frame = {"time": round(t, 6), "path": str(frame_path), "chunk": chunk + 1}
                frames.append(frame)
                all_frames.append((i, frame))
            lo, hi = max(0, a - .25), min(duration, b + .25)
            clip = scene_dir / f"motion-{chunk+1:03}.mp4"
            _run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{lo:.9f}", "-i", str(source),
                  "-t", f"{hi-lo:.9f}", "-map", "0:v:0", "-map", "0:a:0?",
                  "-vf", f"scale={width}:-2,setsar=1", "-c:v", "libx264", "-preset", "fast",
                  "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
                  "-threads", "2", str(clip)])
            clips.append({"path": str(clip), "start": lo, "end": hi,
                          "content_start": a, "content_end": b})
        scenes.append({"id": i, "start": start, "end": end, "duration": end-start,
                       "frames": frames, "clips": clips, "review_status": "not_reviewed",
                       "observed": {"composition": None, "typography": None, "color": None,
                                    "object_actions": None, "transition": None, "audio_sync": None},
                       "inferred": {"camera": None, "easing": None, "layers": None},
                       "reconstruction_notes": None})
    sheets = []
    # Fixed pages: at most 18 thumbnails per image, including portrait references.
    for offset in range(0, len(all_frames), 18):
        page = all_frames[offset:offset+18]
        with Image.open(page[0][1]["path"]) as im:
            h = max(1, round(im.height * 240 / im.width))
        sheet = Image.new("RGB", (720, (h+28)*math.ceil(len(page)/3)), "#151515")
        pen = ImageDraw.Draw(sheet)
        for index, (scene_id, frame) in enumerate(page):
            x, y = index % 3 * 240, index // 3 * (h+28)
            with Image.open(frame["path"]) as im:
                sheet.paste(im.convert("RGB").resize((240, h)), (x, y+28))
            pen.text((x+5, y+7), f"scene {scene_id:03} | {frame['time']:.3f}s", fill="white")
        path = dest / f"contact-{len(sheets)+1:03}.jpg"
        sheet.save(path, quality=90)
        sheets.append(str(path))
    result = {"schema_version": 1, "source": str(source), "duration": duration,
              "source_width": dimensions[0], "source_height": dimensions[1], "average_fps": rate,
              "segmentation": method, "threshold": threshold, "min_scene": min_scene,
              "candidate_cuts": candidates, "soft_transitions": soft, "scenes": scenes, "contact_sheets": sheets,
              "creative_review": "required", "limitations": LIMITATIONS}
    manifest = dest / "reference.json"
    report = dest / "REVIEW.md"
    result.update(manifest=str(manifest), review=str(report))
    lines = ["# Reference study", "", LIMITATIONS, "",
             "Do not infer a reference style from its title/description or force it into Gilvy's house style.",
             "Watch every clip at normal speed; use stills for layout only. Separate observation from inference.",
             "Fill the observed/inferred fields in reference.json after inspection. No OCR, object tracking,",
             "beat detection or automatic easing/layer recovery has been performed.", "",
             f"Segmentation: {method}. Boundaries are provisional unless reviewed.",
             "soft_transitions are dissolve candidates. They do not split scenes until you rerun with --boundaries.",
             "To correct boundaries, rerun in a new directory with --boundaries 4.2 9.8 (interior seconds).", ""]
    if soft:
        lines += ["## Soft transitions", ""]
        for row in soft:
            lines.append(
                f"- dissolve candidate {row['start']:.3f}–{row['end']:.3f}s "
                f"(score {row['score']:.2f}, endpoint delta {row['endpoint_delta']:.1f})"
            )
        lines.append("")
    for scene in scenes:
        lines += [f"## Scene {scene['id']:03}: {scene['start']:.3f}–{scene['end']:.3f}s", ""]
        for clip in scene["clips"]:
            rel = Path(clip["path"]).relative_to(dest).as_posix()
            lines += [f"[Watch {clip['start']:.3f}–{clip['end']:.3f}s]({rel})", ""]
        lines += ["- Observed: composition, type, palette, actions, transition, sound timing.",
                  "- Inferred: camera, easing, layer structure (state uncertainty).",
                  "- Reconstruction: carry, geometry, timing; compare a short proof before full render.", ""]
    report.write_text("\n".join(lines), encoding="utf-8")
    manifest.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result
