"""List the stills an image episode needs before it can render.

`gilvy assets --reference` pulls style frames from a local video, asks for an
overscanned plate so pan and zoom stay inside the picture, and compares a
generated file to those frames.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont

from gilvy.errors import GilvyError
from gilvy.collage import asset_integrity
from gilvy.formats import DESIGN_H, DESIGN_W
from gilvy.keyframes import track_bounds
from gilvy.presets import PHOTO_PRESETS, STYLE_PROMPTS

# Image QC against extracted style frames. Absolute luma, relative contrast, per-channel mean.
BRIGHTNESS_TOL = 18.0
CONTRAST_TOL = 0.35
COLOUR_TOL = 28.0


def _role(depth: float, count: int) -> str:
    if count == 1:
        return "still"
    if depth <= 0.34:
        return "background"
    if depth <= 0.67:
        return "midground"
    return "foreground"


def _relative(episode_dir: Path, src: str) -> str:
    path = Path(src)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(episode_dir).as_posix()
        except ValueError:
            return str(path)
    return path.as_posix()


def plate_pixel_size(camera: dict, duration: float | None = None) -> dict:
    """Source size that still covers the widest pan and the tightest zoom.

    At scale 1 the frame is 1080×1920. Pan needs a margin on every side. The
    tightest scale then multiplies that canvas so the zoomed crop is not a
    blow-up of too few pixels.
    """
    # Manifest callers may supply a key-only envelope rather than parsed tracks.
    # Normalize that shorthand without changing the caller's camera dictionary.
    camera = {**camera, "ease": camera.get("ease", "linear"), "tracks": {
        prop: [{**key, "t": key.get("t", float(i))} for i, key in enumerate(keys)]
        for prop, keys in (camera.get("tracks") or {}).items()
    }}
    start, end = camera["from"], camera["to"]
    pan_x = max(abs(float(start["x"])), abs(float(end["x"])))
    pan_y = max(abs(float(start["y"])), abs(float(end["y"])))
    tight = max(float(start["scale"]), float(end["scale"]), 1.0)
    from gilvy.image_scene import camera_path
    if duration is None:
        duration = max((k["t"] for keys in (camera.get("tracks") or {}).values() for k in keys), default=2.5)
    poses = [pose for _, pose in camera_path(camera, max(duration, 1e-6))]
    pan_x = max(abs(p["x"]) for p in poses)
    pan_y = max(abs(p["y"]) for p in poses)
    tight = max(1.0, max(p["scale"] for p in poses))
    # A varying rotation may reach its bounding-box maximum between keys.
    # The diagonal is a conservative envelope for every angle, not just endpoints.
    rotated = any(abs(p["rotation"]) > 1e-8 for p in poses)
    canvas_w = math.hypot(DESIGN_W, DESIGN_H) if rotated else DESIGN_W
    canvas_h = math.hypot(DESIGN_W, DESIGN_H) if rotated else DESIGN_H
    width = int(math.ceil((canvas_w + 2 * pan_x) * tight))
    height = int(math.ceil((canvas_h + 2 * pan_y) * tight))
    return {"width": width, "height": height, "pan_x": pan_x, "pan_y": pan_y, "scale": tight}


def _duration(video: Path) -> float:
    run = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True,
    )
    text = run.stdout.strip()
    if run.returncode != 0 or not text or text == "N/A":
        raise GilvyError(f"could not read a duration from {video}")
    return float(text)


def shot_spans(episode) -> list[tuple[float, float, int]]:
    """Authored shot clock from each scene's min, for per-shot style frames."""
    clock = 0.0
    spans = []
    for index, scene in enumerate(episode.scenes, 1):
        if scene.type != "image":
            continue
        dur = float(scene.min or 0)
        spans.append((clock, clock + dur, index))
        clock += dur
    return spans


def extract_style_refs(video: str | Path, dest: str | Path, count: int = 4,
                       shots: list[tuple[float, float, int]] | None = None) -> list[dict]:
    """Grab style frames. `shots` takes one frame at each shot's midpoint.

    Without shots, `count` samples the interior of the file (1..32). Does not
    copy the frames into the repo.
    """
    source = Path(video).expanduser().resolve()
    if not source.is_file():
        raise GilvyError(f"reference video not found: {source}")
    out = Path(dest).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    duration = _duration(source)
    if duration <= 0:
        raise GilvyError(f"reference video has no duration: {source}")
    moments: list[tuple[float, int | None]] = []
    if shots:
        if not 1 <= len(shots) <= 60:
            raise GilvyError("per-shot style frames need 1 to 60 shots")
        for start, end, scene_index in shots:
            moments.append((min(duration - 0.05, max(0.0, (start + end) / 2)), scene_index))
    else:
        if count < 1 or count > 32:
            raise GilvyError("style reference frame count must be from 1 to 32")
        for index in range(count):
            fraction = 0.12 + (0.76 * (index + 0.5) / count)
            moments.append((duration * fraction, None))
    frames = []
    for index, (moment, scene_index) in enumerate(moments, 1):
        path = out / f"ref-{index:02d}.png"
        run = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{moment:.3f}", "-i", str(source),
             "-frames:v", "1", str(path)],
            capture_output=True, text=True,
        )
        if run.returncode != 0 or not path.is_file():
            raise GilvyError(f"could not extract a style frame at {moment:.2f}s from {source.name}")
        row = {"time": round(moment, 3), "path": str(path)}
        if scene_index is not None:
            row["scene_index"] = scene_index
        frames.append(row)
    return frames


def _stats(path: Path) -> dict:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((160, 280))
        arr = np.asarray(image, np.float32)
    luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    return {"luma": float(luma.mean()), "contrast": float(luma.std()), "rgb": arr.mean(axis=(0, 1))}


def compare_asset(path: str | Path, refs: list) -> dict:
    """Match the plate to the reference frame in the nearest brightness bucket.

    One global average made a dark shot fail against a bright title card.
    """
    pairs = []
    for item in refs:
        ref_path = Path(item["path"] if isinstance(item, dict) else item)
        if ref_path.is_file():
            pairs.append((item if isinstance(item, dict) else {"path": str(ref_path)}, ref_path))
    if not pairs:
        raise GilvyError("image QC needs at least one style reference frame")
    plate = _stats(Path(path))
    samples = [(item, _stats(ref_path)) for item, ref_path in pairs]
    match_item, match = min(samples, key=lambda pair: abs(plate["luma"] - pair[1]["luma"]))
    luma = float(match["luma"])
    contrast = float(match["contrast"])
    rgb = match["rgb"]
    flags = []
    if abs(plate["luma"] - luma) > BRIGHTNESS_TOL:
        flags.append(f"brightness {plate['luma']:.0f} vs reference {luma:.0f}")
    if contrast > 1.0 and abs(plate["contrast"] - contrast) / contrast > CONTRAST_TOL:
        flags.append(f"contrast {plate['contrast']:.0f} vs reference {contrast:.0f}")
    channel = float(np.max(np.abs(plate["rgb"] - rgb)))
    if channel > COLOUR_TOL:
        flags.append(
            f"colour RGB {tuple(int(v) for v in plate['rgb'])} vs reference {tuple(int(v) for v in rgb)}"
        )
    regen = None
    if flags:
        regen = (
            "regenerate this plate closer to the style frames: "
            + "; ".join(flags)
            + ". Keep the preset template (archival photo, sepia, grain, vignette, framing for history-story)."
        )
    return {
        "ok": not flags,
        "brightness": round(plate["luma"], 2),
        "reference_brightness": round(luma, 2),
        "contrast": round(plate["contrast"], 2),
        "reference_contrast": round(contrast, 2),
        "colour": [round(float(v), 2) for v in plate["rgb"]],
        "reference_colour": [round(float(v), 2) for v in rgb],
        "flags": flags,
        "regen": regen,
        "matched_ref": match_item.get("time"),
        "match": "brightness",
    }


def collect_dependencies(episode) -> list[dict]:
    """Known local inputs shared by manifest, preflight and publication checks.

    Arbitrary files opened by custom Python cannot be inferred statically.
    """
    from gilvy.theme import bundled_fonts
    rows = []

    def add(src, kind, field, index=None, scene=None):
        path = Path(src)
        if not path.is_absolute():
            path = episode.source_dir / path
        path = path.resolve()
        rows.append({"src": _relative(episode.source_dir, str(src)), "path": str(path),
                     "kind": kind, "field": field, "scene_index": index,
                     "scene_id": (scene.id or f"s{index}") if scene else None,
                     "exists": path.is_file()})

    add(episode.source_path, "episode", "source_path")
    if episode.music:
        add(episode.music, "audio", "music")
    fonts = Path(episode.font_dir or bundled_fonts())
    for name in ("Poppins-Medium.ttf", "Poppins-SemiBold.ttf"):
        add(fonts / name, "font", f"font_dir/{name}")
    for index, scene in enumerate(episode.scenes, 1):
        if scene.type == "python":
            add(scene.entry.partition(":")[0], "python", "entry", index, scene)
        if scene.type != "image":
            continue
        for i, layer in enumerate(scene.params.get("layers") or []):
            add(layer["src"], "image", f"layers[{i}].src", index, scene)
        for i, overlay in enumerate(scene.params.get("overlays") or []):
            if overlay.get("kind") == "card":
                add(overlay["src"], "image", f"overlays[{i}].src", index, scene)
        if any(o.get("font") == "serif" or o.get("kind") == "headline" for o in scene.params.get("overlays") or []):
            add(bundled_fonts() / "LiberationSerif-Regular.ttf", "font", "overlays.font", index, scene)
    return rows


def build_manifest(episode, style_refs: list | None = None) -> dict:
    """Asset list for an episode. Missing files are reported, not created."""
    style = episode.style
    prefix = STYLE_PROMPTS.get(style, "")
    assets = []
    dependencies = collect_dependencies(episode)
    for index, scene in enumerate(episode.scenes, 1):
        if scene.type != "image":
            continue
        layers = scene.params.get("layers") or []
        camera = scene.params["camera"]
        duration = scene.min
        if episode.audio_mode == "voiceover" and not (episode.vo_overrun or scene.vo_overrun):
            # Before synthesis, a minimum is not a final shot duration. Include
            # all authored track extrema so a longer VO cannot under-size plates.
            duration = max(float(duration or 0), max((k["t"] for keys in camera["tracks"].values() for k in keys), default=0)) or None
        camera_size = plate_pixel_size(camera, duration)
        collage = scene.params.get("composition") == "collage"
        for dependency in dependencies:
            if dependency["kind"] != "image" or dependency["scene_index"] != index:
                continue
            field = dependency["field"]
            card = field.startswith("overlays")
            position = int(field.split("[")[1].split("]")[0])
            layer = (scene.params["overlays"] if card else layers)[position]
            src, path = layer["src"], Path(dependency["path"])
            role = "card" if card else layer.get("role") or _role(float(layer.get("depth", 1)), len(layers))
            size = camera_size.copy()
            if "placement" in layer:
                placement = layer["placement"]
                peak = _fragment_peak(layer, camera_size["scale"])
                size = {"width": math.ceil(placement["width"]*peak), "height": math.ceil(placement["height"]*peak),
                        "scale": peak, "pan_x": 0, "pan_y": 0}
            elif card:
                parent = next((p for p in layers if p.get("id") == layer.get("parent") and "placement" in p), None)
                peak = _fragment_peak(parent, camera_size["scale"]) if parent else 1.0
                size = {"width": math.ceil(layer["w"]*peak), "height": math.ceil(layer["h"]*peak),
                        "scale": peak, "pan_x": 0, "pan_y": 0}
            if collage:
                # The story brief is metadata, not a command to merge every noun
                # into this one asset (e.g. a pump physically standing in a field).
                prompt = (f"Create one {role} asset for an editorial collage. "
                          "Match the supplied material/lighting reference. "
                          "Include only the subject described for this asset; no narrative text or watermark. ")
                prompt += layer.get("prompt") or "Describe this asset's subject before generation."
                if layer.get("alpha") == "transparent":
                    prompt += " Isolate the complete silhouette on real transparent alpha; no drawn checkerboard or opaque scenery."
                elif layer.get("alpha") == "opaque":
                    prompt += " Produce a complete opaque plate. Fill areas that will be uncovered by moving cutouts."
                prompt += f" Target source size {size['width']}×{size['height']}px; preserve identity and framing from the selected master."
            else:
                subject = " ".join(part for part in (scene.params.get("prompt") or "", layer.get("prompt") or "") if part)
                prompt = prefix
                if role != "still":
                    prompt += f" This file is the {role} layer of a parallax stack."
                if subject:
                    prompt += " " + subject
                prompt += (
                    f" Generate {size['width']}×{size['height']} so a pan of "
                    f"{size['pan_x']:.0f}×{size['pan_y']:.0f}px and a zoom of {size['scale']:.2f} stay inside the picture."
                )
            item = {
                "scene_index": index,
                "scene_id": scene.id or f"s{index}",
                "field": field,
                "parent": layer.get("parent"),
                "role": role,
                "depth": layer.get("depth", 1),
                "src": _relative(episode.source_dir, src),
                "path": str(path),
                "exists": path.is_file(),
                "width": size["width"],
                "height": size["height"],
                "overscan": {"pan_x": size["pan_x"], "pan_y": size["pan_y"], "scale": size["scale"]},
                "prompt": prompt.strip(),
            }
            if path.is_file():
                try:
                    with Image.open(path) as opened:
                        opened.verify()
                    # Some formats (notably JPEG) only validate headers in
                    # verify(); force pixel decoding before timing/TTS begins.
                    with Image.open(path) as opened:
                        opened.load()
                    item["valid"] = True
                except (OSError, ValueError) as exc:
                    item["valid"] = False
                    item["error"] = str(exc)
            if collage:
                item.update({"layer_id": layer.get("id"), "alpha": layer.get("alpha", "any"),
                             "clock": layer.get("clock", "scene"), "placement": layer.get("placement"),
                             "scene_brief": scene.params.get("prompt", ""),
                             "style_qc": {"status": "not_comparable", "reason": "Compare the rendered collage, not a fragment against a complete reference frame."}})
                if path.is_file(): item["asset_integrity"] = asset_integrity(path, layer.get("alpha", "any"))
            if style_refs and path.is_file() and item.get("valid") and not collage:
                scoped = style_refs
                if any(ref.get("scene_index") is not None for ref in style_refs):
                    scoped = [ref for ref in style_refs if ref.get("scene_index") == index]
                if scoped:
                    item["image_qc"] = compare_asset(path, scoped)
            assets.append(item)
    qc_rows = [item["image_qc"] for item in assets if "image_qc" in item]
    return {
        "name": episode.name,
        "style": style,
        "style_prompt": prefix,
        "prompt_template": prefix,
        "style_refs": list(style_refs or []),
        "assets": assets,
        "dependencies": dependencies,
        "missing": [item["src"] for item in assets if not item["exists"]],
        "invalid": [item["src"] for item in assets if item.get("valid") is False or item.get("asset_integrity", {}).get("ok") is False],
        "image_qc": {
            "checked": len(qc_rows),
            "ok": all(row["ok"] for row in qc_rows) if qc_rows else None,
            "flagged": [item["src"] for item in assets if item.get("image_qc") and not item["image_qc"]["ok"]],
        },
    }


def _fragment_peak(layer: dict, camera_scale: float) -> float:
    keys = (layer.get("tracks") or {}).get("scale", [])
    peak = max(1.0, track_bounds(keys)[1]) if keys else 1.0
    gain = .25 + .75*layer["depth"]
    return peak * layer["placement"]["scale"] * (1 + (camera_scale-1)*gain)


def require_assets(episode) -> None:
    """Fail render before encode when a referenced plate is not on disk."""
    manifest = build_manifest(episode)
    missing_dependencies = [d for d in manifest["dependencies"] if not d["exists"]]
    for dependency in manifest["dependencies"]:
        if dependency["kind"] == "font" and dependency["exists"]:
            try:
                ImageFont.truetype(dependency["path"], 12)
            except OSError as exc:
                raise GilvyError(f"corrupt font: {dependency['path']}", field=dependency["field"]) from exc
    if not missing_dependencies and not manifest["invalid"]:
        return
    lines = [f"- {d['field']}: {d['src']}" for d in missing_dependencies if d["kind"] != "image"]
    for item in manifest["assets"]:
        if not item["exists"] or item["src"] in manifest["invalid"]:
            flags = item.get("asset_integrity", {}).get("flags", [])
            lines.append(f"- scene {item['scene_index']} ({item['scene_id']}) {item['field']}: {item['src']} {flags}")
    joined = "\n".join(lines)
    raise GilvyError(
        "missing image assets or corrupt images:\n"
        f"{joined}\n"
        "Generate each file from its prompt (`gilvy assets <episode>`), then render again."
    )
