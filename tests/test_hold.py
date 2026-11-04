"""Long scenes keep a local idle. The camera stays still."""

from gilvy.episode import load_episode
from gilvy.hold import hold_wave
from gilvy.render import build_state


def test_short_scene_has_no_idle():
    assert hold_wave(3.0, 4.2) == 0.0
    assert hold_wave(1.6, 20.0) == 0.0


def test_long_scene_idles_only_after_the_verb():
    assert hold_wave(2.2, 18.0) == 0.0
    assert hold_wave(11.0, 18.0) == 0.0
    assert hold_wave(14.0, 18.0) != 0.0


def test_long_compare_changes_during_the_hold():
    episode = load_episode("tests/fixtures/episodes/ep01-mie-ayam.yaml")
    state = build_state(episode, [16.0] * len(episode.scenes))
    # Punch is scene 4. The verb is still running at both samples (65% of 16s).
    start = float(state.starts[4])
    first = state.frame_bytes(int((start + 2.4) * 60))
    second = state.frame_bytes(int((start + 6.0) * 60))
    assert first != second
