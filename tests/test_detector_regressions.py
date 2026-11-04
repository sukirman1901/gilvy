"""Detector contracts on independent analytic images and controlled arrivals."""

import numpy as np
import pytest

from gilvy.detect import _aligned_ncc, _match_scale, _resize_center, _word_times


def _texture(scale=1.0, dx=0.0, dy=0.0):
    y, x = np.mgrid[:96, :96].astype(float)
    x = (x - 47.5 - dx) / scale
    y = (y - 47.5 - dy) / scale
    return 80 + 30 * np.sin(x / 4) + 25 * np.cos(y / 6) + 40 * np.exp(
        -((x - 17) ** 2 + (y + 11) ** 2) / 50
    )


def test_subpixel_scale_does_not_round_to_an_unchanged_image():
    image = _texture()
    warped = _resize_center(image, 1.002)
    assert np.mean(np.abs(warped - image)) > 0.1
    assert np.mean(np.abs(warped - _texture(1.002))) < 0.05


@pytest.mark.parametrize("scale", [0.98, 1.0, 1.02])
def test_analytic_small_scale_with_luma_noise(scale):
    rng = np.random.default_rng(41)
    measured = _match_scale(_texture(), _texture(scale) + rng.normal(0, 0.2, (96, 96)))
    assert measured == pytest.approx(scale, abs=0.001)


@pytest.mark.parametrize("scale", [0.98, 1.02])
def test_small_scale_with_translation(scale):
    later = np.roll(_texture(scale), (2, -3), axis=(0, 1))
    assert _match_scale(_texture(), later) == pytest.approx(scale, abs=0.001)


@pytest.mark.parametrize("scale", [0.98, 1.0, 1.02])
@pytest.mark.parametrize("shift", [(-3, 2), (4, -2)])
def test_identifiable_analytic_scale_pan_and_noise(scale, shift):
    # Evaluate the continuous field at translated coordinates: no wrapped
    # border or detector resampling is used to manufacture the expected image.
    earlier = _texture()
    later = _texture(scale, *shift) + np.random.default_rng(41).normal(0, 0.2, (96, 96))
    assert _match_scale(earlier, later) == pytest.approx(scale, abs=0.001)
    if scale != 1.0:
        assert _aligned_ncc(earlier, later, scale) > _aligned_ncc(earlier, later, 1 / scale) + 0.01


def _words():
    frames = np.zeros((24, 80, 96, 3), np.uint8)
    frames[2:, 25:35, 10:35] = 255
    frames[7:, 40:50, 10:35] = 255
    # Layout shrinks the old words as a smaller third word arrives.
    frames[12:, 25:35, 30:35] = 0
    frames[12:, 40:50, 30:35] = 0
    frames[12:, 55:65, 10:28] = 255
    return frames


def test_word_arrival_survives_layout_shrink():
    assert _word_times(_words(), 20) == [0.1, 0.35, 0.6]


@pytest.mark.parametrize("kind", ["still", "flash", "noise", "persistent_noise", "full_frame", "fade", "translation"])
def test_non_word_changes_do_not_report_arrivals(kind):
    frames = np.zeros((24, 80, 96, 3), np.uint8)
    if kind == "still":
        frames[:, 25:35, 10:35] = 255
    elif kind == "flash":
        frames[7] = 255
    elif kind == "noise":
        rng = np.random.default_rng(5)
        frames[rng.random(frames.shape[:3]) < 0.03] = 255
    elif kind == "persistent_noise":
        mask = np.random.default_rng(5).random(frames.shape[1:3]) < 0.05
        frames[7:, mask] = 255
    elif kind == "full_frame":
        frames[7:] = 255
    elif kind == "fade":
        for i in range(24):
            frames[i, 20:40, 10:40] = min(255, i * 12)
    else:
        for i in range(24):
            frames[i, 25:35, 10+i:35+i] = 255
    assert _word_times(frames, 20) == []
