"""Extract evidence for reference study; never claim to recover source layers."""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw

from gilvy.errors import GilvyError


LIMITATIONS = (
    "Evidence extraction only, not automatic visual understanding or editable reconstruction. "
    "Cut scores can miss morphs/fades or mistake large motion for a cut. "
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
        raise GilvyError("use a local video file; downloading URLs is not part of analyze-reference")
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
              "candidate_cuts": candidates, "scenes": scenes, "contact_sheets": sheets,
              "creative_review": "required", "limitations": LIMITATIONS}
    manifest = dest / "reference.json"
    report = dest / "REVIEW.md"
    result.update(manifest=str(manifest), review=str(report))
    lines = ["# Reference study", "", LIMITATIONS, "",
             "Do not infer a reference style from its title/description or force it into Gilvy's house style.",
             "Watch every clip at normal speed; use stills for layout only. Separate observation from inference.",
             "Fill the observed/inferred fields in reference.json after inspection. No OCR, object tracking,",
             "beat detection or automatic easing/layer recovery has been performed.", "",
             f"Segmentation: {method}. Boundaries are provisional unless reviewed.", "",
             "To correct boundaries, rerun in a new directory with --boundaries 4.2 9.8 (interior seconds).", ""]
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
