import json
from pathlib import Path

from gilvy.cli import run
from gilvy.mcp_server import directing_notes, list_scene_types


def test_new_and_preview(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run(["new", "ep02"]) == 0
    episode = tmp_path / "ep02" / "ep02.yaml"
    assert episode.is_file()
    out = tmp_path / "preview"
    assert run(["preview", str(episode), "--tts", "fixture", "--out", str(out)]) == 0
    assert (out / "sheet.png").is_file()
    assert (out / "s01.png").is_file()
    assert (out / "s02.png").is_file()


def test_custom_scene_previews(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    out = tmp_path / "custom"
    assert run(["preview", str(root / "examples" / "custom.yaml"), "--tts", "fixture", "--out", str(out)]) == 0
    assert (out / "s01.png").is_file()


def test_directing_notes_are_what_the_skill_loads():
    notes = directing_notes()
    skill = Path(__file__).resolve().parents[1].joinpath("skills", "gilvy", "SKILL.md").read_text(encoding="utf-8")
    assert "You are the director" in notes
    assert "python" in notes
    assert notes.strip() in skill


def test_scene_catalog_lists_the_library():
    rows = json.loads(list_scene_types())
    names = [row["name"] for row in rows]
    for required in ("bowl_hook", "coin_drop", "ring_drain", "compare", "highlight", "bowl_cta", "python"):
        assert required in names
    by_name = {row["name"]: row for row in rows}
    assert "tips" in by_name["checklist"]["slide_if"]
    assert "verb" in by_name["python"]
    assert "not in the list" in by_name["python"]["verb"]


def test_render_smoke_passes_qc(tmp_path: Path):
    episode = tmp_path / "smoke.yaml"
    episode.write_text(
        """
name: smoke
language: en-US
voice: en-US-AndrewNeural
rate: "-8%"
poster: 0
scenes:
  - id: hook
    type: bowl_hook
    caption: ["one number."]
    key: ["number."]
    vo: "One number."
    min: 1.4
    price: "$25"
    note: example
  - id: close
    type: bowl_cta
    caption: ["say it."]
    key: ["it."]
    vo: "Say it."
    min: 1.4
    label: comment
""",
        encoding="utf-8",
    )
    dest = tmp_path / "smoke.mp4"
    code = run(["render", str(episode), "--tts", "fixture", "--out", str(dest), "--workers", "2"])
    assert dest.is_file()
    assert code == 0, dest.with_suffix(".timeline.json").read_text()
