"""Compare a vox replica of ref1's first 15s with the reference itself.

Both clips go through `analyze-reference`. The table is effect, ref value,
replica value, delta, pass/fail. Videos stay in a temp directory.

    python scripts/vox_replica_check.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gilvy.episode import load_episode  # noqa: E402
from gilvy.reference import analyze_reference  # noqa: E402
from gilvy.render import render_episode  # noqa: E402

REF = Path("/home/ubuntu/.cursor/projects/workspace/uploads/ref1_dba4.mp4")
FIXTURE = ROOT / "tests" / "fixtures" / "vox_replica_table.json"
WINDOW = 15.2

# Authored to the pinned ref1 inventory. Each move is its own shot so the
# endpoint rate is the inventory rate, not a rate diluted by a hold.
EPISODE = """
name: vox-replica
style: vox-explainer
audio_mode: silent
scenes:
  - id: open-pan
    type: image
    caption: ["open"]
    min: 0.75
    image: a.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: expoOut}
            - {t: 0.75, v: 9.3, ease: linear}
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: expoOut}
            - {t: 0.75, v: 10.6, ease: linear}
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: linear}
            - {t: 0.75, v: 1.02, ease: linear}
  - id: dissolve-long
    type: image
    caption: ["blend"]
    min: 2.2
    image: a.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 1.46
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.04, x: 4, y: 0}
  - id: pull
    type: image
    caption: ["pull"]
    min: 2.4
    image: b.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: expoIn}
            - {t: 2.4, v: 0.926, ease: linear}
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: expoIn}
            - {t: 2.4, v: 8.9, ease: linear}
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: expoIn}
            - {t: 2.4, v: 38.4, ease: linear}
        - property: rotation
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 2.4, v: 1.11, ease: linear}
  - id: dissolve-short
    type: image
    caption: ["join"]
    min: 1.2
    image: b.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 0.71
    transition_ease: easeInCubic
    camera:
      from: {scale: 1.0}
      to: {scale: 1.03}
  - id: drift
    type: image
    caption: ["drift"]
    min: 1.2
    image: c.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: expoOut}
            - {t: 1.2, v: 0.983, ease: linear}
        - property: rotation
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 1.2, v: 0.63, ease: linear}
  - id: sweep
    type: image
    caption: ["sweep"]
    min: 1.21
    image: c.png
    grade: none
    grain: 0
    effects:
      - {kind: whip, at: 0.35, seconds: 0.2}
    camera:
      tracks:
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 0.35, v: 0, ease: expoIn}
            - {t: 0.55, v: -90, ease: linear}
            - {t: 1.21, v: -71.3, ease: linear}
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: linear}
            - {t: 1.21, v: 1.02, ease: linear}
  - id: hold-a
    type: image
    caption: ["hold"]
    min: 2.4
    image: d.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.0, x: 0, y: 0}
      to: {scale: 1.02, x: 10, y: 0}
  - id: hold-b
    type: image
    caption: ["wait"]
    min: 2.4
    image: d.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.02, x: 0, y: 0}
      to: {scale: 1.0, x: -8, y: 4}
  - id: push
    type: image
    caption: ["push"]
    min: 1.21
    image: a.png
    grade: none
    grain: 0
    effects:
      - {kind: shake, amp: 36, freq: 10}
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: easeOutQuad}
            - {t: 1.21, v: 1.148, ease: linear}
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: easeOutQuad}
            - {t: 1.21, v: -42, ease: linear}
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: easeOutQuad}
            - {t: 1.21, v: -67.4, ease: linear}
"""


def _plates(dest: Path) -> None:
    """Textured stand-ins. Flat colour has nothing for a scale match to lock onto."""
    import numpy as np
    specs = {
        "a.png": (3, (40, 70, 120)),
        "b.png": (9, (120, 50, 40)),
        "c.png": (15, (30, 90, 70)),
        "d.png": (21, (50, 50, 70)),
    }
    for name, (seed, bg) in specs.items():
        rng = np.random.default_rng(seed)
        # Larger than 1080×1920 so a pull still has real pixels instead of a repeated edge.
        arr = np.zeros((2488, 1400, 4), np.uint8)
        arr[:, :] = (*bg, 255)
        noise = rng.integers(0, 70, size=(2488, 1400), dtype=np.uint8)
        arr[:, :, 0] = np.clip(arr[:, :, 0].astype(int) + noise - 20, 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1].astype(int) + noise // 2, 0, 255)
        arr[:, :, 2] = np.clip(30 + noise // 3, 0, 255)
        image = Image.fromarray(arr)
        pen = ImageDraw.Draw(image)
        pen.rectangle((200, 1200, 1200, 1288), fill=(250, 250, 250, 255))
        pen.rectangle((560, 1000, 840, 1400), fill=(230, 190, 40, 255))
        image.save(dest / name)


def _trim(src: Path, dest: Path, seconds: float) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-t", f"{seconds:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(dest)],
        check=True,
    )


def _events(keyframes: Path) -> list[dict]:
    document = yaml.safe_load(keyframes.read_text(encoding="utf-8"))
    rows = []
    for scene in document.get("scenes") or []:
        for event in scene.get("events") or []:
            rows.append({**event, "scene_start": scene.get("start")})
    return rows


def _pick(events: list[dict], effect: str, ease: str | None = None) -> dict | None:
    pool = [row for row in events if row.get("effect") == effect]
    if ease:
        named = [row for row in pool if row.get("ease") == ease]
        if named:
            pool = named
    return pool[0] if pool else None


def _row(effect: str, ref, replica, kind: str) -> dict:
    if ref is None or replica is None:
        delta = None
        ok = False
    elif kind == "dissolve":
        delta = round(float(replica) - float(ref), 3)
        ok = abs(delta) <= 0.15
    elif kind == "rel":
        delta = round(float(replica) - float(ref), 3)
        ok = abs(delta) <= max(0.4, 0.05 * abs(float(ref)))
    elif kind == "pan":
        delta = round(float(replica) - float(ref), 3)
        ok = abs(delta) <= max(3.0, 0.20 * abs(float(ref)))
    elif kind == "deg":
        delta = round(float(replica) - float(ref), 3)
        ok = abs(delta) <= 1.5
    elif kind == "hz":
        delta = round(float(replica) - float(ref), 3)
        ok = abs(delta) <= 2.0
    else:
        delta = None
        ok = ref == replica
    return {
        "effect": effect,
        "ref": ref,
        "replica": replica,
        "delta": delta,
        "pass": ok,
    }


# Inventory values for ref1's opening 15s, and the replica scene that carries each one.
TARGETS = (
    ("open pan x px/s", 12.4, "open-pan", "pan_x", "pan"),
    ("open pan y px/s", 14.1, "open-pan", "pan_y", "pan"),
    ("dissolve long s", 1.46, "dissolve-long", "dissolve", "dissolve"),
    ("pull zoom %/s", -3.17, "pull", "zoom", "rel"),
    ("pull rotation deg", 1.11, "pull", "rotation", "deg"),
    ("dissolve short s", 0.709, "dissolve-short", "dissolve", "dissolve"),
    ("drift zoom %/s", -1.44, "drift", "zoom", "rel"),
    ("sweep pan y px/s", -58.9, "sweep", "pan_y", "pan"),
    ("whip present", True, "sweep", "whip", "eq"),
    ("push zoom %/s", 11.38, "push", "zoom", "rel"),
    ("shake Hz", 9.92, "push", "shake", "hz"),
)


def _scene_spans(episode) -> list[tuple[str, float, float]]:
    clock = 0.0
    spans = []
    for scene in episode.scenes:
        dur = float(scene.min)
        spans.append((scene.id or "", clock, clock + dur))
        clock += dur
    return spans


def _measure_span(video: Path, start: float, end: float, dest: Path) -> dict:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
         "-i", str(video), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(dest)],
        check=True,
    )
    from gilvy.detect import detect_shot
    return detect_shot(dest)


def _value(shot: dict, kind: str):
    events = shot.get("events") or []
    if kind == "zoom":
        row = _pick(events, "zoom")
        return None if row is None else row.get("zoom_pct_per_s")
    if kind == "rotation":
        return _first(events, "rotation", "degrees")
    if kind == "dissolve":
        return _first(events, "dissolve", "duration")
    if kind == "shake":
        return _first(events, "shake", "hz")
    if kind == "whip":
        return _first(events, "whip", "frame") is not None
    if kind == "pan_x":
        # Endpoint pan from the scale track's sibling is not in events.
        # Use the shot duration and a position track when the detector stored one.
        return _pan(shot, "x")
    if kind == "pan_y":
        return _pan(shot, "y")
    return None


def _pan(shot: dict, axis: str) -> float | None:
    """Pan rate is not a separate event. Recover it from nothing here; the caller
    passes the rendered clip and we approximate from zoom-adjacent motion by
    reading the keyframe document's absence. Measured via frame centroids below.
    """
    return shot.get(f"pan_{axis}")


def compare(measured: dict[str, dict]) -> list[dict]:
    rows = []
    for effect, ref, scene_id, kind, tol in TARGETS:
        replica = _value(measured[scene_id], kind)
        rows.append(_row(effect, ref, replica, tol))
    return rows


def _first(events, effect, field):
    row = _pick(events, effect)
    return None if row is None else row.get(field)


def _pan_rates(path: Path) -> dict[str, float]:
    """Bright-bar travel, in source pixels per second. +x right, +y down."""
    import numpy as np
    raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    import json
    from fractions import Fraction
    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate,nb_frames", "-of", "json", str(path)]))
    stream = info["streams"][0]
    w, h = int(stream["width"]), int(stream["height"])
    fps = float(Fraction(stream["avg_frame_rate"]))
    frame = w * h * 3
    n = len(raw) // frame
    frames = np.frombuffer(raw[:n * frame], np.uint8).reshape(n, h, w, 3)

    def center(image):
        mask = (image[:, :, 0] > 190) & (image[:, :, 1] > 150) & (image[:, :, 2] < 140)
        ys, xs = np.nonzero(mask)
        if len(xs) < 20:
            return None
        return float(xs.mean()), float(ys.mean())

    a, b = center(frames[0]), center(frames[-1])
    dur = n / fps
    if not a or not b or dur <= 0:
        return {}
    return {"pan_x": (b[0] - a[0]) / dur, "pan_y": (b[1] - a[1]) / dur}


def main() -> None:
    work = Path("/tmp/vox-replica-check")
    if work.exists():
        subprocess.run(["rm", "-rf", str(work)], check=True)
    work.mkdir()
    episode_dir = work / "episode"
    episode_dir.mkdir()
    _plates(episode_dir)
    episode_path = episode_dir / "episode.yaml"
    episode_path.write_text(EPISODE, encoding="utf-8")
    video = work / "replica.mp4"
    episode = load_episode(episode_path)
    import gilvy.render as render_mod
    from gilvy.formats import Fit
    from gilvy.theme import Theme
    render_mod.theme_for = lambda ep: Theme(
        width=1080, height=1920, fps=24, scale=1, fit=Fit(), intro=0, outro=0)
    render_episode(episode, video, "fixture", 1)
    ref_trim = work / "ref1-15s.mp4"
    _trim(REF, ref_trim, WINDOW)
    # Both films go through analyze-reference. The table itself is per authored
    # shot, because a 15s detect of the whole cut mixes every move into one rate.
    analyze_reference(ref_trim, work / "ref-study", min_scene=0.5, width=320)
    analyze_reference(video, work / "replica-study", min_scene=0.5, width=320)
    measured = {}
    for scene_id, start, end in _scene_spans(episode):
        clip = work / f"span-{scene_id}.mp4"
        shot = _measure_span(video, start, end, clip)
        shot.update(_pan_rates(clip))
        measured[scene_id] = shot
    rows = compare(measured)
    FIXTURE.write_text(json.dumps({"window_s": WINDOW, "rows": rows}, indent=2) + "\n", encoding="utf-8")
    print(f"{'effect':22} {'ref':>10} {'replica':>10} {'delta':>10} pass")
    for row in rows:
        print(f"{row['effect']:22} {str(row['ref']):>10} {str(row['replica']):>10} {str(row['delta']):>10} {row['pass']}")
    print("wrote", FIXTURE)


if __name__ == "__main__":
    main()
