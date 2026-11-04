"""Replica checks for the ref2 articles template and the ref3 history template.

Placeholder plates, not the reference frames. Zoom refs are the log rate of
the authored endpoints, 100·ln(s1/s0)/duration, which is what the detector
reports. The inventory's rate_pct_per_s is linear percent and is close only
for small zooms. Videos stay in /tmp.

    python scripts/reference_replica_check.py
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path("/workspace")
sys.path.insert(0, str(ROOT / "src"))

from gilvy.episode import load_episode  # noqa: E402
from gilvy.render import render_episode  # noqa: E402

OUT = Path("/tmp/reference-replica-check")


def row(effect, ref, replica, kind):
    if ref is None or replica is None:
        return {"effect": effect, "ref": ref, "replica": replica, "delta": None, "pass": False}
    if kind == "eq":
        return {"effect": effect, "ref": ref, "replica": replica, "delta": None, "pass": ref == replica}
    delta = round(float(replica) - float(ref), 3)
    if kind == "dissolve":
        ok = abs(delta) <= 0.15
    elif kind == "rel":
        ok = abs(delta) <= max(0.4, 0.05 * abs(float(ref)))
    elif kind == "pan":
        ok = abs(delta) <= max(3.0, 0.20 * abs(float(ref)))
    elif kind == "deg":
        ok = abs(delta) <= 1.5
    elif kind == "hz":
        ok = abs(delta) <= 2.0
    elif kind == "flash":
        ok = abs(delta) <= 2 / 24
    else:
        ok = False
    return {"effect": effect, "ref": ref, "replica": replica, "delta": delta, "pass": ok}


def plates(dest: Path) -> None:
    specs = {"a.png": (3, (40, 70, 120)), "c.png": (9, (30, 90, 70)), "d.png": (15, (50, 50, 80))}
    for name, (seed, bg) in specs.items():
        rng = np.random.default_rng(seed)
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
    Image.new("RGBA", (1400, 2488), (210, 40, 30, 255)).save(dest / "red.png")
    Image.new("RGBA", (1400, 2488), (20, 40, 160, 255)).save(dest / "blue.png")
    Image.new("RGBA", (1400, 2488), (20, 140, 60, 255)).save(dest / "green.png")


def pan_rates(path: Path) -> dict:
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    from fractions import Fraction
    info = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate", "-of", "json", str(path)]))
    stream = info["streams"][0]
    w, h = int(stream["width"]), int(stream["height"])
    fps = float(Fraction(stream["avg_frame_rate"]))
    n = len(raw) // (w * h * 3)
    frames = np.frombuffer(raw[: n * w * h * 3], np.uint8).reshape(n, h, w, 3)

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


def measure(video: Path, episode, work: Path) -> dict:
    from gilvy.detect import detect_shot
    clock = 0.0
    out = {}
    for scene in episode.scenes:
        dur = float(scene.min)
        clip = work / f"span-{scene.id}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-ss", f"{clock:.3f}", "-to", f"{clock + dur:.3f}",
             "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(clip)],
            check=True,
        )
        shot = detect_shot(clip)
        shot.update(pan_rates(clip))
        out[scene.id] = shot
        clock += dur
    return out


def value(shot, kind):
    events = shot.get("events") or []
    def first(effect, field):
        for event in events:
            if event.get("effect") == effect:
                return event.get(field)
        return None
    if kind == "zoom":
        return first("zoom", "zoom_pct_per_s")
    if kind == "dissolve":
        return first("dissolve", "duration")
    if kind == "shake":
        return first("shake", "hz")
    if kind == "rotation":
        return first("rotation", "degrees")
    if kind == "flash":
        return first("flash", "time")
    if kind == "pan_x":
        return shot.get("pan_x")
    if kind == "pan_y":
        return shot.get("pan_y")
    return None


def run(name, episode_yaml, targets):
    work = OUT / name
    if work.exists():
        subprocess.run(["rm", "-rf", str(work)], check=True)
    work.mkdir(parents=True)
    plates(work)
    path = work / "episode.yaml"
    path.write_text(episode_yaml, encoding="utf-8")
    video = work / "replica.mp4"
    episode = load_episode(path)
    import gilvy.render as render_mod
    from gilvy.formats import Fit
    from gilvy.theme import Theme
    render_mod.theme_for = lambda ep: Theme(width=1080, height=1920, fps=24, scale=1, fit=Fit(), intro=0, outro=0)
    render_episode(episode, video, "fixture", 1)
    measured = measure(video, episode, work)
    rows = []
    for effect, ref, scene_id, kind, tol in targets:
        rows.append(row(effect, ref, value(measured[scene_id], kind), tol))
    print("\n==", name)
    for item in rows:
        print(f"{item['effect']:22} {str(item['ref']):>10} {str(item['replica']):>10} {str(item['delta']):>10} {item['pass']}")
    fixture = ROOT / "tests" / "fixtures" / f"{name}_replica_table.json"
    fixture.write_text(json.dumps({"rows": rows}, indent=2) + "\n", encoding="utf-8")
    print("wrote", fixture)
    return rows


REF2 = r'''
name: articles-replica
style: vox-explainer
audio_mode: silent
scenes:
  - id: open
    type: image
    caption: ["open"]
    min: 1.25
    image: a.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: expoIn}
            - {t: 1.25, v: 1.10, ease: linear}
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: expoOut}
            - {t: 1.25, v: -19.5, ease: linear}
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: expoOut}
            - {t: 1.25, v: -70, ease: linear}
  - id: fade
    type: image
    caption: ["fade"]
    min: 1.25
    image: red.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 0.709
    transition_ease: easeInCubic
    camera:
      tracks:
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 1.25, v: 30, ease: linear}
  - id: after
    type: image
    caption: ["after"]
    min: 1.25
    image: blue.png
    grade: none
    grain: 0
    effects:
      - {kind: flash, at: 0.40, seconds: 0.08}
    camera:
      from: {scale: 1.0}
      to: {scale: 1.04}
  - id: punch
    type: image
    caption: ["punch"]
    min: 1.375
    image: c.png
    grade: none
    grain: 0
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: easeOutQuad}
            - {t: 1.375, v: 1.40, ease: linear}
  - id: shake
    type: image
    caption: ["shake"]
    min: 1.25
    image: d.png
    grade: none
    grain: 0
    effects:
      - {kind: shake, amp: 28, freq: 5}
    camera:
      from: {scale: 1.0}
      to: {scale: 1.06}
'''

# Log rates of the authored endpoints. Inventory rates are linear percent
# (40% / 1.377s = 29); the detector reports 100*ln(s1/s0)/duration.
REF2_TARGETS = (
    ("open zoom %/s", 100 * math.log(1.10) / 1.25, "open", "zoom", "rel"),
    ("open pan x px/s", -19.5 / 1.25, "open", "pan_x", "pan"),
    ("open pan y px/s", -70 / 1.25, "open", "pan_y", "pan"),
    ("dissolve s", 0.709, "fade", "dissolve", "dissolve"),
    ("flash s", 0.40, "after", "flash", "flash"),
    ("punch zoom %/s", 100 * math.log(1.40) / 1.375, "punch", "zoom", "rel"),
    ("shake Hz", 5.05, "shake", "shake", "hz"),
)

REF3 = r'''
name: history-replica
style: history-story
audio_mode: silent
scenes:
  - id: long
    type: image
    caption: ["long"]
    min: 2.5
    image: red.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 1.8
    transition_ease: linear
    camera:
      tracks:
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 2.5, v: 40, ease: linear}
  - id: hold
    type: image
    caption: ["hold"]
    min: 2.5
    image: blue.png
    grade: none
    grain: 0
    transition_out: dissolve
    transition: 2.0
    transition_ease: easeInOutCubic
    camera:
      tracks:
        - property: x
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 2.5, v: -40, ease: linear}
  - id: push
    type: image
    caption: ["push"]
    min: 1.25
    image: a.png
    grade: none
    grain: 0
    transition_out: cut
    camera:
      tracks:
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: expoIn}
            - {t: 1.25, v: 1.166, ease: linear}
        - property: rotation
          keys:
            - {t: 0.0, v: 0, ease: linear}
            - {t: 1.25, v: 1.34, ease: linear}
  - id: sweep
    type: image
    caption: ["sweep"]
    min: 1.25
    image: c.png
    grade: none
    grain: 0
    transition_out: cut
    camera:
      tracks:
        - property: y
          keys:
            - {t: 0.0, v: 0, ease: expoOut}
            - {t: 1.25, v: -48, ease: linear}
        - property: scale
          keys:
            - {t: 0.0, v: 1.0, ease: linear}
            - {t: 1.25, v: 1.03, ease: linear}
  - id: shake
    type: image
    caption: ["shake"]
    min: 1.25
    image: d.png
    grade: none
    grain: 0
    transition_out: cut
    effects:
      - {kind: shake, amp: 28, freq: 11}
    camera:
      from: {scale: 1.0}
      to: {scale: 1.06}
  - id: tail
    type: image
    caption: ["tail"]
    min: 1.25
    image: green.png
    grade: none
    grain: 0
    camera:
      from: {scale: 1.04}
      to: {scale: 1.0}
'''

REF3_TARGETS = (
    ("dissolve linear s", 1.8, "long", "dissolve", "dissolve"),
    ("dissolve inout s", 2.0, "hold", "dissolve", "dissolve"),
    ("push zoom %/s", 100 * math.log(1.166) / 1.25, "push", "zoom", "rel"),
    ("push rotation deg", 1.34, "push", "rotation", "deg"),
    ("sweep pan y px/s", -48 / 1.25, "sweep", "pan_y", "pan"),
    ("shake Hz", 11.16, "shake", "shake", "hz"),
)


if __name__ == "__main__":
    run("ref2", REF2, REF2_TARGETS)
    run("ref3", REF3, REF3_TARGETS)
