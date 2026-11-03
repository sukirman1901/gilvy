"""Product-specific preview, encode and integrity checks, without house-style QC."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from gilvy.errors import GilvyError
from gilvy.product import finite, load_product


def preview_product(spec_path, output_dir, times=None):
    film = load_product(spec_path)
    times = (
        times if times is not None else [film.duration * f for f in (0.12, 0.45, 0.8)]
    )
    if (
        not isinstance(times, list)
        or not 1 <= len(times) <= 24
        or any(not finite(t) or not 0 <= t < film.duration for t in times)
    ):
        raise GilvyError("preview requires 1..24 finite times within the film")
    dest = Path(output_dir).expanduser().resolve()
    if dest.exists():
        raise GilvyError("preview directory exists; choose a new directory")
    dest.mkdir(parents=True)
    rows = []
    tw = 320
    th = round(tw * film.size[1] / film.size[0])
    cols = min(3, len(times))
    sheet = Image.new(
        "RGB", (cols * tw, math.ceil(len(times) / cols) * (th + 28)), "#18263a"
    )
    draw = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        frame = film.frame(t)
        path = dest / f"f{i:03}.png"
        frame.save(path)
        x, y = i % cols * tw, i // cols * (th + 28)
        sheet.paste(frame.resize((tw, th), Image.Resampling.LANCZOS), (x, y + 28))
        draw.text((x + 7, y + 7), f"{t:.3f}s", fill="white")
        rows.append({"time": t, "path": str(path)})
    path = dest / "sheet.jpg"
    sheet.save(path, quality=92)
    return {"frames": rows, "sheet": str(path), "creative_review": "required"}


def render_product(spec_path, output, start=0.0, duration=None):
    film = load_product(spec_path)
    if not finite(start) or not 0 <= start < film.duration:
        raise GilvyError("invalid product start time")
    duration = film.duration - start if duration is None else duration
    if not finite(duration) or duration <= 0 or start + duration > film.duration + 1e-9:
        raise GilvyError("product window must be positive and within the film")
    if any(shutil.which(x) is None for x in ("ffmpeg", "ffprobe")):
        raise GilvyError("ffmpeg and ffprobe are required")
    audio = film.spec.get("audio")
    if audio is not None:
        if not isinstance(audio, str):
            raise GilvyError("audio must be a local filename or null")
        audio = (film.source_dir / audio).resolve()
        if not audio.is_file():
            raise GilvyError(f"audio not found: {audio}")
    dest = Path(output).expanduser().resolve()
    if dest.suffix.lower() != ".mp4":
        raise GilvyError("product output must end in .mp4")
    if dest == Path(spec_path).expanduser().resolve() or audio == dest:
        raise GilvyError("output must not replace an input")
    dest.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, math.ceil(duration * film.fps - 1e-8))
    actual = frames / film.fps
    with tempfile.TemporaryDirectory(prefix=".product-", dir=dest.parent) as temp:
        temp = Path(temp)
        video = temp / "video.mp4"
        log_path = temp / "ffmpeg.log"
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{film.size[0]}x{film.size[1]}",
            "-r",
            str(film.fps),
            "-i",
            "pipe:0",
        ]
        if audio:
            cmd += [
                "-ss",
                str(start),
                "-i",
                str(audio),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-af",
                "apad",
                "-c:a",
                "aac",
            ]
        else:
            cmd += ["-an"]
        cmd += [
            "-t",
            str(actual),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "2",
            "-movflags",
            "+faststart",
            str(video),
        ]
        with log_path.open("w") as log:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
            try:
                for n in range(frames):
                    t = min(start + n / film.fps, film.duration - 1e-9)
                    proc.stdin.write(film.frame(t).tobytes())
                proc.stdin.close()
                code = proc.wait(timeout=120)
            except (OSError, subprocess.TimeoutExpired) as exc:
                proc.kill()
                proc.wait()
                raise GilvyError(f"product encode failed: {exc}") from exc
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        if code:
            raise GilvyError(f"product encode failed: {log_path.read_text()[-2000:]}")
        # Decode/count the finished artifact before publishing an atomic result.
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-count_frames",
                    "-show_entries",
                    "stream=codec_type,width,height,nb_read_frames:format=duration",
                    "-of",
                    "json",
                    str(video),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            info = json.loads(probe.stdout)
            v = next(s for s in info["streams"] if s["codec_type"] == "video")
            ok = (
                int(v["nb_read_frames"]) == frames
                and (v["width"], v["height"]) == film.size
                and abs(float(info["format"]["duration"]) - actual) < 0.15
                and any(s["codec_type"] == "audio" for s in info["streams"])
                == bool(audio)
                and not probe.stderr.strip()
            )
        except (
            OSError,
            ValueError,
            KeyError,
            StopIteration,
            subprocess.SubprocessError,
        ) as exc:
            raise GilvyError(f"could not validate product encode: {exc}") from exc
        if not ok:
            raise GilvyError(
                "product output failed frame/dimension/duration/audio integrity checks"
            )
        os.replace(video, dest)
    result = {
        "video": str(dest),
        "style": "product",
        "start": start,
        "requested_duration": duration,
        "duration": actual,
        "frames": frames,
        "width": film.size[0],
        "height": film.size[1],
        "fps": film.fps,
        "audio_mode": "file" if audio else "silent",
        "qc": {"ok": True, "scope": "technical_integrity"},
        "creative_review": "required",
    }
    dest.with_suffix(".product.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
