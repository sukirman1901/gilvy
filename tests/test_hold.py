"""Long scenes keep moving. Short scenes stay on the authored frames."""

from gilvy.episode import load_episode
from gilvy.hold import hold_scale
from gilvy.render import build_state


def test_short_scene_is_not_scaled():
    assert hold_scale(3.0, 4.2) == 1.0
    assert hold_scale(1.6, 20.0) == 1.0


def test_long_scene_pushes_in_after_the_arrival():
    early = hold_scale(2.2, 18.0)
    later = hold_scale(10.0, 18.0)
    assert early > 1.0
    assert later > early


def test_long_compare_changes_during_the_hold():
    episode = load_episode("examples/ep01-mie-ayam.yaml")
    state = build_state(episode, [16.0] * len(episode.scenes))
    # Punch is scene 4. Sample after the authored beat, then a few seconds later.
    start = float(state.starts[4])
    first = state.frame_bytes(int((start + 2.4) * 60))
    second = state.frame_bytes(int((start + 6.0) * 60))
    assert first != second
