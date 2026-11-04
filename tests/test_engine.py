"""The refactored frame must match the proven renderer byte for byte."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from gilvy.draw import clear_font_cache
from gilvy.easing import R, eexp, eio, eo
from gilvy.episode import Scene, load_episode
from gilvy.render import build_state
from tests.support import load_original, load_scene, namespace

ROOT = Path(__file__).resolve().parents[1]


def _episode_from_yaml(path: Path):
    return load_episode(path)


def _arm_original(original, scenes, sc, durations):
    video = original.Video("oracle", scenes, sc)
    video.durs = [float(d) for d in durations]
    video.starts = np.cumsum([0.0] + video.durs)
    video.T = float(video.starts[-1])
    return video


def _gilvy_bytes(episode, durations, impl=None):
    if impl is not None:
        for scene in episode.scenes:
            scene.impl = impl
    state = build_state(episode, durations)
    return state


def _sample_ns(durations):
    starts = np.cumsum([0.0] + [float(d) for d in durations])
    frames = []
    for i, dur in enumerate(durations):
        frames.append(int((float(starts[i]) + float(dur) * 0.72) * 60))
    frames.append(int((float(starts[1]) - 0.2) * 60))
    return frames


def _assert_equal(got: bytes, expected: bytes, label: str):
    if got == expected:
        return
    a = np.frombuffer(got, np.uint8)
    b = np.frombuffer(expected, np.uint8)
    delta = np.abs(a.astype(np.int16) - b.astype(np.int16))
    raise AssertionError(f"{label} drifted: max {int(delta.max())} sum {int(delta.sum())} bytes {len(got)}")


@pytest.mark.parametrize("fn", [eo, eio, eexp, R])
def test_easing_matches_oracle(fn):
    original = load_original()
    samples = [0, 0.0, 0.2, 0.5, 0.8, 1, 1.0, -0.4, 1.7]
    ref = {"eo": original.eo, "eio": original.eio, "eexp": original.eexp, "R": original.R}[fn.__name__]
    for value in samples:
        if fn is R:
            assert fn(value, 0.2, 1.4) == ref(value, 0.2, 1.4)
        else:
            assert fn(value) == ref(value)


def test_engine_matches_oracle_on_day30():
    """Same scene function, two canvases. A miss here is the drawing engine, not the YAML."""
    original = load_original()
    clear_font_cache()
    original._fc.clear()
    episode = _episode_from_yaml(ROOT / "tests/fixtures/episodes" / "day30-january.yaml")
    durations = [scene.min for scene in episode.scenes]
    sc = load_scene("day30_draw.py", namespace())
    state = _gilvy_bytes(episode, durations, impl=sc)
    video = _arm_original(
        original,
        [{"text": s.caption, "key": s.key} for s in episode.scenes],
        load_scene("day30_draw.py", namespace(original)),
        durations,
    )
    for n in (90, int((durations[0] - 0.2) * 60)):
        _assert_equal(state.frame_bytes(n), video.frame(n), f"engine n={n}")


def test_yaml_scenes_match_original_episodes():
    original = load_original()
    clear_font_cache()
    original._fc.clear()
    cases = (
        ("day30-january.yaml", "day30_draw.py"),
        ("ep01-mie-ayam.yaml", "ep01_draw.py"),
    )
    digests = {}
    for yaml_name, draw_name in cases:
        episode = _episode_from_yaml(ROOT / "tests/fixtures/episodes" / yaml_name)
        durations = [scene.min for scene in episode.scenes]
        state = build_state(episode, durations)
        video = _arm_original(
            original,
            [{"text": s.caption, "key": s.key} for s in episode.scenes],
            load_scene(draw_name, namespace(original)),
            durations,
        )
        for n in _sample_ns(durations):
            got = state.frame_bytes(n)
            expected = video.frame(n)
            _assert_equal(got, expected, f"{yaml_name} n={n}")
            digest = hashlib.sha256(got).hexdigest()
            assert digest == hashlib.sha256(expected).hexdigest()
            digests[f"{yaml_name}:{n}"] = digest
    assert len(digests) >= 12


def test_ep01_green_ratios_follow_the_color_rule():
    """Frames at 80% of the recorded scene lengths. Bands are the measured style, not a guess."""
    from gilvy.qc import green_ratio

    episode = load_episode(ROOT / "tests/fixtures/episodes" / "ep01-mie-ayam.yaml")
    # Recorded ep01 scene lengths (seconds): 4.78, 4.32, 6.21, 6.12, 5.88, 5.59.
    durations = [4.78, 4.32, 6.21, 6.12, 5.88, 5.59]
    state = build_state(episode, durations)
    ratios = []
    for i, dur in enumerate(durations):
        n = int((float(state.starts[i]) + dur * 0.8) * 60)
        frame = state.frame_array(n)
        ratios.append(green_ratio(frame))
    hook, setup, umk, jakarta, punch, cta = ratios
    assert 0.005 < hook < 0.06
    assert setup < 0.005
    assert 0.04 < umk < 0.20
    assert 0.03 < jakarta < 0.18
    assert 0.15 < punch < 0.40
    assert cta < 0.005


def test_scene_impl_roundtrip_type():
    episode = load_episode(ROOT / "examples" / "custom.yaml")
    assert isinstance(episode.scenes[0], Scene)
    assert episode.scenes[0].type == "python"
