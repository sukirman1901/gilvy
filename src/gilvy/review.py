"""Version comparison evidence, deliberately not a creative-quality score."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from gilvy.errors import GilvyError
from gilvy.qc import _grab, _probe


def _fitted_frame(path: Path, time: float, native: tuple[int, int], target: tuple[int, int]) -> np.ndarray:
    """Decode at the file's size, then scale to the reference frame when they differ."""
    frame = _grab(path, time, native[0], native[1])
    if native == target:
        return frame
    image = Image.fromarray(frame).resize(target, Image.Resampling.BILINEAR)
    return np.asarray(image)


def compare_versions(reference_video: str | Path, candidate_video: str | Path,
                     output_dir: str | Path, reference_start: float = 0,
                     candidate_start: float = 0, duration: float = 8,
                     sample_fps: float = 2) -> dict:
    """Compare sampled decoded frames at aligned playback times.

    Pixel differences include codec noise and intended changes such as an old
    outro being removed when a clip is extended. No metric proves continuity,
    equivalence, creative quality, or approval. Inspect the paired evidence.
    """
    values = (reference_start, candidate_start, duration, sample_fps)
    if not all(math.isfinite(v) for v in values) or min(reference_start, candidate_start) < 0:
        raise GilvyError("comparison values must be finite and starts must be >= 0")
    if not 0 < duration <= 600 or not 0 < sample_fps <= 4:
        raise GilvyError("comparison duration must be > 0 and <= 600; sample_fps must be > 0 and <= 4")
    paths = [Path(reference_video).expanduser().resolve(), Path(candidate_video).expanduser().resolve()]
    pictures = []
    lengths = []
    rates = []
    for path in paths:
        if not path.is_file():
            raise GilvyError(f"video not found: {path}")
        info = _probe(path)
        picture = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        if picture is None:
            raise GilvyError(f"no video stream in {path}")
        pictures.append((int(picture["width"]), int(picture["height"])))
        try:
            rate = float(Fraction(picture.get("avg_frame_rate", "0/1")))
        except (ValueError, ZeroDivisionError):
            rate = 0
        rates.append(rate)
        lengths.append(float(info.get("format", {}).get("duration", 0)))
    available = min(lengths[0] - reference_start, lengths[1] - candidate_start)
    duration = min(duration, available)
    if duration <= 0:
        raise GilvyError("comparison start is outside a video")
    count = max(1, math.ceil(duration * sample_fps))
    if count > 240:
        raise GilvyError("comparison would sample more than 240 frames; lower --sample-fps or --duration")
    # Seek only at playable frame starts, including on low-fps material.
    offsets = np.linspace(0, duration, count, endpoint=False)
    width, height = pictures[0]
    rescaled = pictures[0] != pictures[1]
    thumb_w = 240
    thumb_h = max(1, round(height * thumb_w / width))
    row_h = thumb_h + 24
    sheet = Image.new("RGB", (thumb_w * 3, row_h * count), (10, 10, 10))
    pen = ImageDraw.Draw(sheet)
    rows = []
    for i, offset in enumerate(offsets):
        times = [reference_start + float(offset), candidate_start + float(offset)]
        for j, rate in enumerate(rates):
            if rate > 0:
                times[j] = math.floor(min(times[j], max(0, lengths[j] - 1 / rate)) * rate + 1e-7) / rate
        a = _fitted_frame(paths[0], times[0], pictures[0], (width, height))
        b = _fitted_frame(paths[1], times[1], pictures[1], (width, height))
        delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
        rows.append({
            "reference_time": round(times[0], 6),
            "candidate_time": round(times[1], 6),
            "identical": bool(np.array_equal(a, b)),
            "mean_absolute_error": float(delta.mean()),
            "max_channel_delta": int(delta.max()),
            "changed_pixel_ratio": float((delta.max(axis=2) > 0).mean()),
        })
        for j, (frame, label) in enumerate(((a, "reference"), (b, "candidate"),
                                          (np.minimum(delta * 4, 255).astype(np.uint8), "difference x4"))):
            im = Image.fromarray(frame).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            sheet.paste(im, (j * thumb_w, i * row_h + 24))
            pen.text((j * thumb_w + 4, i * row_h + 4), f"{label} +{float(offset):.2f}s", fill="white")
    dest = Path(output_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)
    sheet_path = dest / "comparison.png"
    sheet.save(sheet_path)
    result = {
        "reference_video": str(paths[0]), "candidate_video": str(paths[1]),
        "reference_start": reference_start, "candidate_start": candidate_start,
        "duration": duration, "sheet": str(sheet_path), "samples": rows,
        "identical_sampled_frames": sum(r["identical"] for r in rows),
        "sample_count": count, "rescaled": rescaled, "creative_review": "required",
        "limitations": "Sampled pixel evidence only; encoding noise, fades, and timing changes also differ. Not an approval or quality score.",
    }
    (dest / "comparison.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
