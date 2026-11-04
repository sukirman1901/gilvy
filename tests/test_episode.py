from pathlib import Path

import pytest

from gilvy.episode import load_episode
from gilvy.errors import EpisodeError

ROOT = Path(__file__).resolve().parents[1]


def test_examples_load():
    indo = load_episode(ROOT / "tests/fixtures/episodes" / "ep01-mie-ayam.yaml")
    assert indo.voice == "id-ID-ArdiNeural"
    assert indo.language == "id-ID"
    assert indo.rate == "-8%"
    assert [scene.type for scene in indo.scenes] == [
        "bowl_hook",
        "coin_drop",
        "ring_drain",
        "ring_drain",
        "compare",
        "bowl_cta",
    ]
    assert indo.scenes[3].params["count_from"] == 268
    english = load_episode(ROOT / "tests/fixtures/episodes" / "day30-january.yaml")
    assert english.voice == "en-US-AndrewNeural"
    assert english.scenes[0].type == "timeline"
    custom = load_episode(ROOT / "examples" / "custom.yaml")
    assert custom.scenes[0].entry.endswith("custom_scene.py:draw") or "custom_scene.py:draw" in custom.scenes[0].entry


def test_language_picks_a_default_voice(tmp_path: Path):
    path = tmp_path / "ep.yaml"
    path.write_text(
        "language: id-ID\nscenes:\n  - type: coin_cta\n    caption: ['satu angka']\n    vo: Halo.\n    min: 3\n",
        encoding="utf-8",
    )
    episode = load_episode(path)
    assert episode.voice == "id-ID-ArdiNeural"


def test_bad_key_and_unknown_type(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        """
name: bad
scenes:
  - type: bowl_hook
    caption: ["too many words in this line"]
    vo: Hello.
    price: "$1"
""",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError):
        load_episode(path)
    path.write_text(
        """
name: bad
scenes:
  - type: not_a_scene
    caption: ["hello"]
    vo: Hello.
""",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError, match="unknown type"):
        load_episode(path)
    path.write_text(
        """
name: bad
scenes:
  - type: bowl_cta
    caption: ["hello there"]
    key: ["missing"]
    vo: Hello.
    label: hi
""",
        encoding="utf-8",
    )
    with pytest.raises(EpisodeError, match="not a whole caption word"):
        load_episode(path)


def test_palette_override(tmp_path: Path):
    path = tmp_path / "color.yaml"
    path.write_text(
        """
name: color
palette:
  green: [1, 2, 3]
scenes:
  - type: coin_cta
    caption: ["hello"]
    vo: Hello there friend.
    min: 3
""",
        encoding="utf-8",
    )
    episode = load_episode(path)
    assert episode.green == (1, 2, 3)
    assert episode.bg == (10, 10, 10)
