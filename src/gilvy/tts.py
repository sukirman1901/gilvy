"""Voice-over. House scenes add a 0.6s breath; a preset can set its own pad and lead."""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

from gilvy.errors import GilvyError


def probe_ok(path: Path) -> bool:
    run = subprocess.run(["ffprobe", "-v", "error", str(path)], capture_output=True)
    return run.returncode == 0 and path.stat().st_size > 2000


def trim_edge_silence(path: Path) -> Path:
    """Drop leading and trailing silence. Internal pauses stay.

    edge-tts pads each clip. On a history-story voice cut that padding, plus the
    house 0.6s breath, stretched a 31.9s reference to 35.6s. A failed trim keeps
    the original file.
    """
    dest = path.with_name(path.stem + ".trim" + path.suffix)
    audio_filter = (
        "silenceremove=start_periods=1:start_threshold=0.015:start_silence=0:detection=peak,"
        "areverse,"
        "silenceremove=start_periods=1:start_threshold=0.015:start_silence=0:detection=peak,"
        "areverse"
    )
    run = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-af", audio_filter, str(dest)],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0 or not dest.exists() or dest.stat().st_size < 200:
        dest.unlink(missing_ok=True)
        return path
    try:
        if probe_duration(dest) < 0.05:
            dest.unlink(missing_ok=True)
            return path
    except GilvyError:
        dest.unlink(missing_ok=True)
        return path
    dest.replace(path)
    return path


def probe_duration(path: Path) -> float:
    run = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
    )
    text = run.stdout.strip()
    if run.returncode != 0 or not text or text == "N/A":
        raise GilvyError(f"ffprobe could not read a duration from {path}")
    return float(text)


def fixture_duration(text: str, scene_min: float) -> float:
    """Offline stand-in. Fills the authored scene and leaves the usual 0.6s breath."""
    guess = max(0.8, 0.42 * max(1, len(text.split())))
    return max(guess, max(0.4, scene_min - 0.6))


class FixtureTTS:
    name = "fixture"

    def synthesize(self, text: str, voice: str, rate: str, dest: Path, scene_min: float) -> Path:
        dur = fixture_duration(text, scene_min)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=880:sample_rate=48000:duration={dur:.3f}",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(dest),
        ]
        run = subprocess.run(cmd, capture_output=True, text=True)
        if run.returncode != 0:
            wav = dest.with_suffix(".wav")
            fallback = [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=880:sample_rate=48000:duration={dur:.3f}",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ]
            subprocess.run(fallback, check=True, capture_output=True)
            return wav
        return dest


class EdgeTTS:
    name = "edge"

    def synthesize(self, text: str, voice: str, rate: str, dest: Path, scene_min: float) -> Path:
        import edge_tts

        dest.parent.mkdir(parents=True, exist_ok=True)
        last: Exception | None = None
        for _ in range(5):
            try:
                if dest.exists():
                    dest.unlink()

                async def _save() -> None:
                    comm = edge_tts.Communicate(text, voice, rate=rate)
                    await comm.save(str(dest))

                asyncio.run(_save())
            except Exception as exc:  # network and service errors are retried
                last = exc
                time.sleep(3)
                continue
            if dest.exists() and probe_ok(dest):
                return trim_edge_silence(dest)
            time.sleep(3)
        raise GilvyError(f"edge-tts failed for {voice}: {last}")


def backend_for(name: str):
    if name == "fixture":
        return FixtureTTS()
    if name == "edge":
        return EdgeTTS()
    raise GilvyError(f"unknown tts {name!r}. Use edge or fixture.")


def stamp_for(backend: str, voice: str, rate: str, text: str, scene_min: float) -> str:
    if backend == "fixture":
        return f"fixture\n{scene_min}\n{text}"
    return f"edge\n{voice}\n{rate}\ntrim1\n{text}"
