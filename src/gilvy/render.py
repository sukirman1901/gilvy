"""Timing, frames, and the ffmpeg encode. One code path for preview and the final mp4."""

from __future__ import annotations

import json
import math
import multiprocessing
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from gilvy.caption import caption, check_captions
from gilvy.draw import Ctx, compose, grid
from gilvy.easing import cl, eio
from gilvy.episode import Episode, Scene, resolve_output
from gilvy.errors import GilvyError
from gilvy.qc import _probe, qc_video
from gilvy.scenes import SCENES, invoke_python
from gilvy.theme import CRF, PRESET, SAMPLE_RATE, Theme, bundled_fonts
from gilvy.tts import backend_for, probe_duration, probe_ok, stamp_for

_STATE: RenderState | None = None


def theme_for(episode: Episode) -> Theme:
    return Theme.from_profile(
        episode.format,
        bg=tuple(episode.bg),
        white=tuple(episode.white),
        green=tuple(episode.green),
        font_dir=episode.font_dir or str(bundled_fonts()),
    )


def scene_payload(scene: Scene, episode: Episode) -> dict:
    entry = scene.entry
    if scene.type == "python" and entry:
        file_part, _, func = entry.partition(":")
        path = Path(file_part)
        if not path.is_absolute():
            path = episode.source_dir / path
        entry = f"{path.resolve()}:{func}"
    return {
        "type": scene.type,
        "caption": list(scene.caption),
        "key": list(scene.key),
        "vo": scene.vo,
        "id": scene.id or "",
        "params": dict(scene.params),
        "entry": entry,
        "green": scene.green_role,
    }


@dataclass
class RenderState:
    theme: Theme
    scenes: list
    impls: list
    durations: list
    starts: np.ndarray
    total: float
    episode_dir: str

    def paint(self, index: int, u: float) -> Ctx:
        ctx = Ctx(self.theme)
        grid(ctx)
        scene = self.scenes[index]
        dur = self.durations[index]
        impl = self.impls[index]
        if impl is not None:
            impl(ctx, index, u, dur)
        elif scene["type"] == "python":
            invoke_python(scene["entry"], self.episode_dir, ctx, u, dur, scene["params"])
        else:
            SCENES[scene["type"]].draw(ctx, u, dur, scene["params"])
        caption(ctx, scene["caption"], scene["key"], u)
        return ctx

    def frame_array(self, n: int) -> np.ndarray:
        fps = self.theme.fps
        t = n / fps
        i = min(int(np.searchsorted(self.starts, t, side="right") - 1), len(self.durations) - 1)
        u = t - self.starts[i]
        image = compose(self.paint(i, u))
        xf = self.theme.crossfade
        if i + 1 < len(self.durations) and u > self.durations[i] - xf:
            k = eio((u - (self.durations[i] - xf)) / xf)
            nxt_u = u - self.durations[i]
            nxt = compose(self.paint(i + 1, nxt_u))
            image = image * (1 - k) + nxt * k
        bg = np.array(self.theme.bg)
        if t < self.theme.intro:
            fade = cl(t / self.theme.intro)
            image = image * fade + bg * (1 - fade)
        if t > self.total - self.theme.outro:
            fade = cl((self.total - t) / self.theme.outro)
            image = image * fade + bg * (1 - fade)
        return image.astype(np.uint8)

    def frame_bytes(self, n: int) -> bytes:
        return self.frame_array(n).tobytes()


def build_state(episode: Episode, durations: list[float], impls: list | None = None) -> RenderState:
    durs = [float(d) for d in durations]
    starts = np.cumsum([0.0] + durs)
    if impls is None:
        impls = [scene.impl for scene in episode.scenes]
    return RenderState(
        theme=theme_for(episode),
        scenes=[scene_payload(scene, episode) for scene in episode.scenes],
        impls=list(impls),
        durations=durs,
        starts=starts,
        total=float(starts[-1]),
        episode_dir=str(episode.source_dir),
    )


def scene_durations(episode: Episode, voiced: list[float]) -> list[float]:
    theme = theme_for(episode)
    out = []
    for scene, spoken in zip(episode.scenes, voiced):
        floor = theme.min_duration if scene.min is None else scene.min
        out.append(max(floor, spoken + theme.pad + theme.lead))
    return out


def preflight(episode: Episode) -> None:
    ctx = Ctx(theme_for(episode))
    check_captions(ctx, [scene_payload(scene, episode) for scene in episode.scenes])


def require_ffmpeg() -> None:
    from shutil import which

    if which("ffmpeg") is None or which("ffprobe") is None:
        raise GilvyError("ffmpeg and ffprobe are required on PATH. Install the ffmpeg package.")


def _init_worker(state: RenderState) -> None:
    global _STATE
    _STATE = state


def _mp_frame(n: int) -> bytes:
    assert _STATE is not None
    return _STATE.frame_bytes(n)


def _encode(state: RenderState, dest: Path, workers: int, *,
            start_frame: int = 0, end_frame: int | None = None, width: int | None = None) -> None:
    fps = state.theme.fps
    end_frame = int(round(state.total * fps)) if end_frame is None else end_frame
    count = end_frame - start_frame
    if count < 1:
        raise GilvyError("the episode is empty")
    if workers > 1 and any(impl is not None for impl in state.impls):
        workers = 1
    workers = max(1, workers)
    dest.parent.mkdir(parents=True, exist_ok=True)
    log_path = dest.parent / "ffmpeg-video.log"
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
        f"{state.theme.width}x{state.theme.height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        CRF,
        "-preset",
        PRESET,
        *(["-vf", f"scale={width}:-2"] if width is not None else []),
        str(dest),
    ]
    print(f"rendering {count} frames ({count / fps:.1f}s) with {workers} workers", file=sys.stderr)
    with log_path.open("w") as log:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=log)
        assert proc.stdin is not None
        try:
            if workers <= 1:
                for n in range(count):
                    proc.stdin.write(state.frame_bytes(n + start_frame))
                    if n % 120 == 0:
                        print(f"  {n}/{count}", file=sys.stderr)
            else:
                ctx = multiprocessing.get_context("spawn")
                with ctx.Pool(workers, initializer=_init_worker, initargs=(state,)) as pool:
                    for n, blob in enumerate(pool.imap(_mp_frame, range(start_frame, end_frame), chunksize=8)):
                        proc.stdin.write(blob)
                        if n % 120 == 0:
                            print(f"  {n}/{count}", file=sys.stderr)
            proc.stdin.close()
            code = proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
    if code != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise GilvyError(f"ffmpeg video encode failed:\n{tail}")


def _write_pad(path: Path, total: float) -> None:
    sr = SAMPLE_RATE
    t = np.arange(int(sr * total)) / sr
    audio = np.zeros_like(t)
    for freq, amp in [(110, 0.5), (164.81, 0.32), (220, 0.28), (277.18, 0.16), (329.63, 0.14)]:
        audio += amp * np.sin(2 * np.pi * freq * t) * (0.65 + 0.35 * np.sin(2 * np.pi * 0.08 * t + freq))
    audio = audio / np.abs(audio).max() * 0.25 * np.minimum(1, t / 2) * np.minimum(1, (total - t) / 2.5)
    stereo = np.stack([audio, np.roll(audio, 400)], 1)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes((stereo * 32767).astype(np.int16).tobytes())


def _mix_audio(pad: Path, voices: list[Path], starts: np.ndarray, lead: float, total: float, dest: Path) -> None:
    inputs: list[str] = []
    graph = ""
    for i, voice in enumerate(voices):
        delay = int((float(starts[i]) + lead) * 1000)
        inputs += ["-i", str(voice)]
        graph += f"[{i + 1}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[v{i}];"
    n = len(voices)
    graph += "".join(f"[v{i}]" for i in range(n))
    graph += f"amix=inputs={n}:normalize=0,apad,asplit[vo][sc];"
    graph += "[0:a][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck];"
    graph += "[duck][vo]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.9[out]"
    run = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(pad), *inputs, "-filter_complex", graph, "-map", "[out]", "-t", f"{total:.3f}", str(dest)],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise GilvyError(f"ffmpeg audio mix failed:\n{run.stderr[-2000:]}")


def _mux(video: Path, audio: Path | None, total: float, dest: Path, audio_start: float = 0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            *(["-ss", f"{audio_start:.6f}", "-i", str(audio)] if audio is not None else []),
            "-c:v",
            "copy",
            *(["-c:a", "aac", "-b:a", "160k"] if audio is not None else ["-an"]),
            "-t",
            f"{total:.3f}",
            "-movflags",
            "+faststart",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise GilvyError(f"ffmpeg mux failed:\n{run.stderr[-2000:]}")


def _hstack(images: list[Path], dest: Path) -> None:
    if len(images) == 1:
        dest.write_bytes(images[0].read_bytes())
        return
    inputs: list[str] = []
    for image in images:
        inputs += ["-i", str(image)]
    n = len(images)
    run = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", f"hstack={n},scale={n * 300}:-1", str(dest)],
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise GilvyError(f"could not build the contact sheet:\n{run.stderr[-1500:]}")


def _sheet_from_video(video: Path, starts: np.ndarray, durations: list[float], dest: Path) -> None:
    mids = []
    for i, dur in enumerate(durations):
        t = float(starts[i] + dur * 0.7)
        frame = dest.parent / f"m{i}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:-1", str(frame)],
            check=True,
        )
        mids.append(frame)
    if len(mids) == 1:
        dest.write_bytes(mids[0].read_bytes())
        return
    inputs: list[str] = []
    for frame in mids:
        inputs += ["-i", str(frame)]
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", f"hstack={len(mids)}", str(dest)],
        check=True,
    )


def _poster(video: Path, starts: np.ndarray, durations: list[float], index: int, dest: Path) -> None:
    t = float(starts[index] + durations[index] * 0.75)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", str(dest)],
        check=True,
    )


def synthesize(episode: Episode, build: Path, tts_name: str) -> tuple[list[Path], list[float]]:
    backend = backend_for(tts_name)
    build.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    spoken: list[float] = []
    for i, scene in enumerate(episode.scenes):
        floor = episode.min_duration if scene.min is None else scene.min
        dest = build / f"vo{i + 1}.mp3"
        meta = build / f"vo{i + 1}.txt"
        stamp = stamp_for(backend.name, episode.voice, episode.rate, scene.vo, floor)
        cached = None
        if meta.exists() and meta.read_text(encoding="utf-8") == stamp:
            for cand in (dest, dest.with_suffix(".wav")):
                if cand.exists() and probe_ok(cand):
                    cached = cand
                    break
        path = cached if cached is not None else backend.synthesize(scene.vo, episode.voice, episode.rate, dest, floor)
        if not probe_ok(path):
            raise GilvyError(f"voice-over {i + 1} is missing or too small: {path}")
        meta.write_text(stamp, encoding="utf-8")
        paths.append(path)
        spoken.append(probe_duration(path))
        print(f"voice {i + 1}/{len(episode.scenes)} {spoken[-1]:.2f}s  {scene.id or scene.type}", file=sys.stderr)
    return paths, spoken


def prepare_timing(episode: Episode, build: Path, tts_name: str) -> tuple[list[Path], list[float]]:
    if episode.audio_mode == "voiceover":
        if any(not scene.vo.strip() for scene in episode.scenes):
            raise GilvyError("voiceover mode requires vo on every scene")
        paths, spoken = synthesize(episode, build, tts_name)
        return paths, scene_durations(episode, spoken)
    if any(scene.min is None for scene in episode.scenes):
        raise GilvyError("ambient/silent modes require explicit min on every scene")
    return [], [float(scene.min) for scene in episode.scenes]


def prepare_audio(episode: Episode, state: RenderState, build: Path, voices: list[Path]) -> Path | None:
    if episode.audio_mode == "silent":
        return None
    pad = build / "pad.wav"
    _write_pad(pad, state.total)
    if episode.audio_mode == "ambient":
        return pad
    mix = build / "mix.wav"
    _mix_audio(pad, voices, state.starts, state.theme.lead, state.total, mix)
    return mix


def write_timeline(episode: Episode, state: RenderState, dest: Path, tts_name: str) -> None:
    payload = {
        "gilvy": "0.1.0",
        "name": episode.name,
        "language": episode.language,
        "voice": episode.voice,
        "rate": episode.rate,
        "tts": tts_name if episode.audio_mode == "voiceover" else "none",
        "audio_mode": episode.audio_mode,
        "duration": state.total,
        "fps": state.theme.fps,
        "format": episode.format,
        "width": state.theme.width,
        "height": state.theme.height,
        "palette": {"bg": list(episode.bg), "white": list(episode.white), "green": list(episode.green)},
        "scenes": [],
    }
    for i, scene in enumerate(episode.scenes):
        payload["scenes"].append(
            {
                "index": i,
                "id": scene.id or f"s{i + 1}",
                "type": scene.type,
                "green": scene.green_role,
                "start": float(state.starts[i]),
                "duration": float(state.durations[i]),
                "caption": scene.caption,
                "key": scene.key,
                "vo": scene.vo,
            }
        )
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


PREVIEW_MARKS = (0.12, 0.45, 0.80)


def save_png(state: RenderState, t: float, dest: Path) -> None:
    n = int(t * state.theme.fps)
    raw = state.frame_bytes(n)
    Image.frombytes("RGB", (state.theme.width, state.theme.height), raw).save(dest)


def default_workers() -> int:
    return max(1, min(8, multiprocessing.cpu_count() or 2))


def preview_episode(episode: Episode, out_dir: Path | None, tts_name: str, fraction: float = 0.8) -> dict:
    require_ffmpeg()
    if not 0 < fraction < 1:
        raise GilvyError("fraction must be between 0 and 1")
    preflight(episode)
    build = (out_dir or (Path.cwd() / "out" / episode.name / "preview")).resolve()
    build.mkdir(parents=True, exist_ok=True)
    _voices, durations = prepare_timing(episode, build, tts_name)
    state = build_state(episode, durations)
    stills = []
    motion = []
    for i, dur in enumerate(durations):
        start = float(state.starts[i])
        for mark in PREVIEW_MARKS:
            dest = build / f"s{i + 1:02d}-t{int(round(mark * 100)):02d}.png"
            save_png(state, start + dur * mark, dest)
            motion.append(str(dest))
        settled = build / f"s{i + 1:02d}.png"
        save_png(state, start + dur * fraction, settled)
        stills.append(str(settled))
        print(f"still {i + 1} {settled.name}", file=sys.stderr)
    sheet = build / "sheet.png"
    _hstack([Path(p) for p in stills], sheet)
    motion_sheet = build / "motion.png"
    _hstack([Path(p) for p in motion], motion_sheet)
    timeline = build / "timeline.json"
    write_timeline(episode, state, timeline, tts_name)
    return {
        "stills": stills,
        "sheet": str(sheet),
        "motion": motion,
        "motion_sheet": str(motion_sheet),
        "timeline": str(timeline),
        "duration": state.total,
        "scenes": len(durations),
        "width": state.theme.width,
        "height": state.theme.height,
        "format": episode.format,
        "creative_review": "required",
    }


def output_paths(base: Path, formats: list[str]) -> list[Path]:
    """One format keeps the caller's path. Several formats suffix the profile name."""
    if len(formats) <= 1:
        return [base]
    return [base.with_name(f"{base.stem}-{name}{base.suffix}") for name in formats]


def render_episode(episode: Episode, output: Path, tts_name: str, workers: int) -> dict:
    require_ffmpeg()
    preflight(episode)
    build = output.parent / output.stem
    build.mkdir(parents=True, exist_ok=True)
    voices, durations = prepare_timing(episode, build, tts_name)
    state = build_state(episode, durations)
    video = build / "vid.mp4"
    _encode(state, video, workers or default_workers())
    audio = prepare_audio(episode, state, build, voices)
    _mux(video, audio, state.total, output)
    sheet = build / "sheet.png"
    _sheet_from_video(output, state.starts, durations, sheet)
    poster = None
    if episode.poster is not None:
        poster_path = output.with_name(output.stem + "_poster.png")
        _poster(output, state.starts, durations, episode.poster, poster_path)
        poster = str(poster_path)
    timeline = output.with_suffix(".timeline.json")
    write_timeline(episode, state, timeline, tts_name)
    report = qc_video(output, str(timeline))
    return {
        "video": str(output),
        "timeline": str(timeline),
        "sheet": str(sheet),
        "poster": poster,
        "duration": state.total,
        "build": str(build),
        "qc": report.to_dict(),
        "creative_review": "not_evaluated",
        "audio_mode": episode.audio_mode,
        "publishable_audio": episode.audio_mode != "voiceover" or tts_name != "fixture",
    }


def preview_motion(episode: Episode, output: Path, start: float = 0, duration: float = 8,
                   tts_name: str = "fixture", workers: int = 0, width: int = 540) -> dict:
    """Render an exact timeline window, including existing crossfades, for review.

    Downscale only after drawing. Do not reset scene time, re-ease a clipped
    scene, or apply a new intro/outro at the edges of the selected window.
    """
    require_ffmpeg()
    if not math.isfinite(start) or start < 0 or not math.isfinite(duration) or not 0 < duration <= 12:
        raise GilvyError("start must be finite and >= 0; duration must be > 0 and <= 12 seconds")
    if isinstance(width, bool) or not isinstance(width, int) or width < 160 or width % 2:
        raise GilvyError("preview width must be an even integer >= 160")
    if output.suffix.lower() != ".mp4":
        raise GilvyError("preview output must end in .mp4")
    preflight(episode)
    if width > theme_for(episode).width:
        raise GilvyError("preview width must not exceed the delivery width")
    build = output.parent / (output.stem + "-build")
    build.mkdir(parents=True, exist_ok=True)
    voices, durations = prepare_timing(episode, build, tts_name)
    state = build_state(episode, durations)
    fps = state.theme.fps
    first = int(round(start * fps))
    stop = min(int(round((start + duration) * fps)), int(round(state.total * fps)))
    if first >= stop:
        raise GilvyError("preview range contains no frames; start is outside the episode")
    actual_start, actual_duration = first / fps, (stop - first) / fps
    picture = build / "picture.mp4"
    _encode(state, picture, workers or default_workers(), start_frame=first, end_frame=stop, width=width)
    audio = prepare_audio(episode, state, build, voices)
    _mux(picture, audio, actual_duration, output, audio_start=actual_start)
    source_timeline = build / "source.timeline.json"
    write_timeline(episode, state, source_timeline, tts_name)
    picture_info = next(s for s in _probe(output)["streams"] if s["codec_type"] == "video")
    result = {
        "video": str(output), "source_timeline": str(source_timeline),
        "start": actual_start, "duration": actual_duration,
        "end": stop / fps, "source_duration": state.total,
        "width": picture_info["width"], "height": picture_info["height"],
        "fps": fps, "audio_mode": episode.audio_mode,
        "timing_estimated": episode.audio_mode == "voiceover" and tts_name == "fixture",
        "preview_only": True, "creative_review": "required",
        "review_questions": [
            "What can the action communicate with the captions hidden?",
            "Does the action change a relationship or create a consequence?",
            "Does the object and its motion survive the scene boundary?",
            "Is the visual legible at phone size, and does its rhythm support the sentence?",
        ],
    }
    output.with_suffix(".preview.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
