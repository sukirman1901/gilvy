"""A copied skill must not depend on its original repository layout."""
from pathlib import Path
import re
import shutil

from gilvy.product import load_product


ROOT = Path(__file__).resolve().parents[1]


def test_skill_local_links_survive_standalone_copy(tmp_path):
    target = tmp_path / 'skills' / 'gilvy'
    shutil.copytree(ROOT / 'skills' / 'gilvy', target)
    for document in target.rglob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)', document.read_text()):
            if '://' in link or link.startswith('#'):
                continue
            resource = (document.parent / link.split('#')[0]).resolve()
            assert resource.is_relative_to(target.resolve()), (document.name, link)
            assert resource.exists(), (document.name, link)


def test_skill_bundled_compositor_example_runs_outside_checkout(tmp_path, monkeypatch):
    target = tmp_path / 'copied'
    shutil.copytree(ROOT / 'skills' / 'gilvy', target)
    monkeypatch.chdir(tmp_path)
    film = load_product(target / 'examples' / 'kinetic.yaml')
    assert film.frame_at(0).size == (640, 360)
    assert film.frame_at(15).tobytes() != film.frame_at(0).tobytes()
