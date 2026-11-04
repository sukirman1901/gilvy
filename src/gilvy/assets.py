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
from PIL import Image

from gilvy.errors import GilvyError
from gilvy.formats import DESIGN_H, DESIGN_W
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


def plate_pixel_size(camera: dict) -> dict:
    """Source size that still covers the widest pan and the tightest zoom.

    At scale 1 the frame is 1080×1920. Pan needs a margin on every side. The
    tightest scale then multiplies that canvas so the zoomed crop is not a
    blow-up of too few pixels.
    """
    start, end = camera["from"], camera["to"]
    pan_x = max(abs(float(start["x"])), abs(float(end["x"])))
    pan_y = max(abs(float(start["y"])), abs(float(end["y"])))
    tight = max(float(start["scale"]), float(end["scale"]), 1.0)
    width = int(math.ceil((DESIGN_W + 2 * pan_x) * tight))
    height = int(math.ceil((DESIGN_H + 2 * pan_y) * tight))
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


def extract_style_refs(video: str | Path, dest: str | Path, count: int = 4) -> list[dict]:
    """Grab interior frames as style references. Does not copy them into the repo."""
    source = Path(video).expanduser().resolve()
    if not source.is_file():
        raise GilvyError(f"reference video not found: {source}")
    if count < 1 or count > 8:
        raise GilvyError("style reference frame count must be from 1 to 8")
    out = Path(dest).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    duration = _duration(source)
    if duration <= 0:
        raise GilvyError(f"reference video has no duration: {source}")
    # Stay off the first and last 8% so a fade-in or end card is not the style.
    fractions = [0.12 + (0.76 * (i + 0.5) / count) for i in range(count)]
    frames = []
    for index, fraction in enumerate(fractions, 1):
        moment = duration * fraction
        path = out / f"ref-{index:02d}.png"
        run = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{moment:.3f}", "-i", str(source),
             "-frames:v", "1", str(path)],
            capture_output=True, text=True,
        )
        if run.returncode != 0 or not path.is_file():
            raise GilvyError(f"could not extract a style frame at {moment:.2f}s from {source.name}")
        frames.append({"time": round(moment, 3), "path": str(path)})
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


def build_manifest(episode, style_refs: list | None = None) -> dict:
    """Asset list for an episode. Missing files are reported, not created."""
    style = episode.style
    prefix = STYLE_PROMPTS.get(style, "")
    assets = []
    for index, scene in enumerate(episode.scenes, 1):
        if scene.type != "image":
            continue
        layers = scene.params.get("layers") or []
        size = plate_pixel_size(scene.params["camera"])
        for layer in layers:
            src = layer["src"]
            path = Path(src)
            if not path.is_absolute():
                path = episode.source_dir / path
            path = path.resolve()
            role = _role(float(layer.get("depth", 1)), len(layers))
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
            if style_refs and path.is_file():
                item["image_qc"] = compare_asset(path, style_refs)
            assets.append(item)
    qc_rows = [item["image_qc"] for item in assets if "image_qc" in item]
    return {
        "name": episode.name,
        "style": style,
        "style_prompt": prefix,
        "prompt_template": prefix,
        "style_refs": list(style_refs or []),
        "assets": assets,
        "missing": [item["src"] for item in assets if not item["exists"]],
        "image_qc": {
            "checked": len(qc_rows),
            "ok": all(row["ok"] for row in qc_rows) if qc_rows else None,
            "flagged": [item["src"] for item in assets if item.get("image_qc") and not item["image_qc"]["ok"]],
        },
    }


def require_assets(episode) -> None:
    """Fail render before encode when a referenced plate is not on disk."""
    if episode.style not in PHOTO_PRESETS:
        return
    manifest = build_manifest(episode)
    if not manifest["missing"]:
        return
    lines = []
    for item in manifest["assets"]:
        if not item["exists"]:
            lines.append(f"- scene {item['scene_index']} ({item['scene_id']}): {item['src']}")
    joined = "\n".join(lines)
    raise GilvyError(
        "missing image assets:\n"
        f"{joined}\n"
        "Generate each file from its prompt (`gilvy assets <episode>`), then render again."
    )
