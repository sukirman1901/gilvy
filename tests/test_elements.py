"""Reusable components remain seekable, fit-aware, and harmless to old scenes."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from gilvy.cli import run
from gilvy.draw import Ctx
from gilvy.elements import draw_element, element_catalog, motion_reference_notes
from gilvy.episode import load_episode
from gilvy.errors import GilvyError
from gilvy.formats import Fit
from gilvy.mcp_server import list_visual_elements, motion_reference
from gilvy.render import build_state, preflight
from gilvy.theme import Theme

ROOT=Path(__file__).resolve().parents[1]
NAMES=[row['name'] for row in element_catalog()]


def canvas():
    return Ctx(Theme(width=540,height=960,scale=1,fit=Fit(.5)))


def picture(name, **kwargs):
    ctx=canvas()
    draw_element(ctx,name,**kwargs)
    return np.array(ctx.im)


@pytest.mark.parametrize('name',NAMES)
def test_every_element_is_seekable_visible_and_white(name):
    # A worker may request .9s before .1s; no accumulated state may matter.
    a=picture(name,phase=.9,activity=.7)
    picture(name,phase=.1,activity=.7)
    b=picture(name,phase=.9,activity=.7)
    assert np.array_equal(a,b)
    assert np.array_equal(a[:,:,0],a[:,:,1]) and np.array_equal(a[:,:,1],a[:,:,2])
    ys,xs=np.where(a[:,:,0]>20)
    assert len(xs)>10
    # Default center/size stay local after profile mapping, including collars.
    assert abs(xs-513*.5).max()<45
    assert abs(ys-780*.5).max()<45
    assert np.all(picture(name,progress=0)==10)
    assert np.all(picture(name,alpha=0)==10)


@pytest.mark.parametrize('name',['person','people','flame','smoke','tree','sprout','flow','sun','book','road'])
def test_local_motion_changes_pose_without_randomness(name):
    assert not np.array_equal(picture(name,phase=.1,activity=1),picture(name,phase=.63,activity=1))
    assert np.array_equal(picture(name,phase=.1),picture(name,phase=.63))


def test_controls_and_identity_are_explicit():
    for params in ({'size':0},{'phase':math.inf},{'center':(math.nan,0)},
                   {'activity':2},{'progress':-.1},{'alpha':1.1},{'col':(1,2)},
                   {'col':(255,256,0)}):
        with pytest.raises(GilvyError):
            picture('person',**params)
    with pytest.raises(GilvyError,match='unknown visual element'):
        picture('emoji')
    # A continuation with an offset asks for precisely the same absolute pose.
    assert np.array_equal(picture('person',phase=4+.2,activity=.8),
                          picture('person',phase=4.2,activity=.8))
    # Callers explicitly choose a measured unit's green; no default accent.
    a=picture('drop',col=(218,255,89))
    assert (a[:,:,1]>a[:,:,2]).any()


def test_catalog_cli_mcp_and_packaged_guide_agree(capsys):
    assert len(NAMES)==14 and len(set(NAMES))==14
    catalog=element_catalog()
    catalog[0]['verbs'].append('mutated by caller')
    assert 'mutated by caller' not in element_catalog()[0]['verbs']
    assert json.loads(list_visual_elements())==element_catalog()
    assert run(['elements'])==0
    assert json.loads(capsys.readouterr().out)==element_catalog()
    assert run(['motion-reference'])==0
    assert capsys.readouterr().out.strip()==motion_reference_notes().strip()
    assert motion_reference()==motion_reference_notes()
    guide=motion_reference_notes()
    assert 'not YAML scene types' in guide and '2025' in guide
    for name in NAMES:
        assert f'`{name}`' in guide
    skill=(ROOT/'skills/gilvy/SKILL.md').read_text()
    section=skill.split('<!-- directing:start -->')[1].split('<!-- directing:end -->')[0].strip()
    assert section==(ROOT/'src/gilvy/DIRECTING.md').read_text().strip()


def test_examples_preflight_and_bojonegoro_preserves_rounded_population():
    for relative in ('elements.yaml','bojonegoro/episode.yaml'):
        ep=load_episode(ROOT/'examples'/relative)
        preflight(ep)
        state=build_state(ep,[s.min for s in ep.scenes])
        assert state.total==(14 if relative=='elements.yaml' else 41)
        # Actually invoke each custom scene once; imports and entry points work.
        for i,duration in enumerate(state.durations):
            assert np.any(np.array(state.paint(i,duration*.8).im)>20)
    ep=load_episode(ROOT/'examples/bojonegoro/episode.yaml')
    assert [ep.scenes[i].min for i in (1,2)]==[3,5]
    assert ep.scenes[2].caption==['45 dari 100 pekerja.','di sektor pertanian.']
    assert 44.62<361706/810528*100<44.64
