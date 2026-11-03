"""Regression checks for carried objects at long-film shot boundaries."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from gilvy.product import load_product, validate


@pytest.fixture
def launch(tmp_path):
    source = Path(__file__).parents[1] / "examples/product/launch/build.py"
    spec = importlib.util.spec_from_file_location("launch_example", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.assets(tmp_path / "assets")
    specs = module.shots(tmp_path)
    return module, specs, tmp_path


def test_launch_specs_cover_95_seconds_and_keep_all_ui_legal(launch):
    module, specs, _ = launch
    assert sum(module.DURATIONS) == 95 and len(specs) == 21
    for spec in specs:
        validate(spec)


def test_workflow_steps_and_inbox_pose_carry_across_cuts(launch):
    _, _, root = launch
    # A previously observed glitch faded out all steps immediately before Save.
    before = load_product(root / "shots/15.yaml")
    after = load_product(root / "shots/16.yaml")
    pixels_before = np.array(before.frame(before.duration - 1 / 30), dtype=float)
    pixels_after = np.array(after.frame(0), dtype=float)
    assert np.abs(pixels_before - pixels_after).mean() < 1
    # The overview/close-up must start at the same pose rather than jumping 17px.
    overview = load_product(root / "shots/04.yaml")
    closeup = load_product(root / "shots/05.yaml")
    a = overview.state(overview.spec["layers"][1], overview.duration)
    b = closeup.state(closeup.spec["layers"][0], 0)
    for key in ("x", "y", "scale", "tilt_x", "tilt_y"):
        assert a[key] == b[key]
