"""Delivery profiles fit the 1080×1920 show into a safe rectangle. The default is identity."""

from pathlib import Path

import pytest

from gilvy.easing import span
from gilvy.episode import EpisodeError, load_episode
from gilvy.formats import fit_of, get_profile
from gilvy.render import build_state, output_paths


ROOT = Path(__file__).resolve().parents[1]


def test_default_profile_is_identity():
    fit = fit_of(get_profile("vertical_9x16"))
    assert fit.scale == 1
    assert fit.ox == 0 and fit.oy == 0
    assert fit.map(513, 780) == (513, 780)
    assert fit.map(0, 1290) == (0, 1290)


def test_square_fits_inside_safe_rect_uniformly():
    profile = get_profile("square_1x1")
    fit = fit_of(profile)
    assert fit.scale < 1
    x0, y0 = fit.map(0, 0)
    x1, y1 = fit.map(1080, 1920)
    left, top, right, bottom = profile.insets
    assert left - 0.01 <= x0 <= x1 <= profile.width - right + 0.01
    assert top - 0.01 <= y0 <= y1 <= profile.height - bottom + 0.01
    assert abs((x1 - x0) / (y1 - y0) - 1080 / 1920) < 1e-6


def test_unknown_format_is_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "name: bad\nlanguage: en-US\nformat: poster\nscenes:\n  - type: bowl_cta\n    caption: ['hi']\n    key: ['hi']\n    vo: Hi.\n    label: hi\n",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError, match="format"):
        load_episode(path)


def test_span_keeps_a_short_scene_on_the_authored_beat():
    assert span(1.3, 0.3, 1.3, 2.0) == 1.0


def test_span_is_still_moving_halfway_through_a_long_scene():
    assert span(3.4, 0.3, 1.3, 10.0) < 1
    assert span(8.0, 0.3, 1.3, 10.0) == 1


def test_square_frame_is_the_profile_size_and_margin_is_background():
    episode = load_episode(ROOT / "examples" / "ep01-mie-ayam.yaml").with_format("square_1x1")
    state = build_state(episode, [4.0] * len(episode.scenes))
    frame = state.frame_array(30)
    assert frame.shape == (1080, 1080, 3)
    assert tuple(int(v) for v in frame[0, 0]) == episode.bg
    assert tuple(int(v) for v in frame[10, 10]) == episode.bg


def test_several_formats_suffix_the_output_name():
    base = Path("/tmp/out/ep.mp4")
    assert output_paths(base, ["vertical_9x16"]) == [base]
    assert output_paths(base, ["vertical_9x16", "square_1x1"]) == [
        Path("/tmp/out/ep-vertical_9x16.mp4"),
        Path("/tmp/out/ep-square_1x1.mp4"),
    ]
