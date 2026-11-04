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
    assert 'references/house.md' in skill and 'directing_notes' in skill
    house=(ROOT/'skills/gilvy/references/house.md').read_text()
    assert 'directing_notes' in house and 'list_scene_types' in house
    from gilvy.mcp_server import directing_notes
    assert directing_notes().strip()==(ROOT/'src/gilvy/DIRECTING.md').read_text().strip()


def test_examples_preflight_and_bojonegoro_preserves_rounded_population():
    for relative,total in (('elements.yaml',14),('bojonegoro/episode.yaml',41),
                           ('elements-refined.yaml',8.4)):
        base=ROOT/'references/house' if relative.startswith('bojonegoro/') else ROOT/'tests/fixtures/episodes'
        ep=load_episode(base/relative)
        preflight(ep)
        state=build_state(ep,[s.min for s in ep.scenes])
        assert state.total==pytest.approx(total)
        # Actually invoke each custom scene once; imports and entry points work.
        for i,duration in enumerate(state.durations):
            assert np.any(np.array(state.paint(i,duration*.8).im)>20)
    ep=load_episode(ROOT/'references/house/bojonegoro/episode.yaml')
    assert [ep.scenes[i].min for i in (1,2)]==[3,5]
    assert ep.scenes[2].caption==['45 dari 100 pekerja.','di sektor pertanian.']
    assert 44.62<361706/810528*100<44.64


def test_accepted_other_elements_retain_original_pixels():
    import hashlib
    fixture=json.loads((ROOT/'tests/fixtures/accepted_elements.json').read_text())
    for name,expected in fixture['digests'].items():
        ctx=canvas()
        draw_element(ctx,name,phase=fixture['phase'],activity=fixture['activity'])
        assert hashlib.sha256(ctx.im.tobytes()).hexdigest()==expected,name


def test_side_gait_keeps_bone_lengths_and_planted_feet():
    from gilvy.elements import _walk_pose
    for activity in (0,.3,.7,1):
        for phase in np.linspace(0,1,121):
            hip,shoulder,legs,arms=_walk_pose(phase,activity)
            for a,b,c in legs:
                assert math.dist(a,b)==pytest.approx(.225,abs=1e-9)
                assert math.dist(b,c)==pytest.approx(.225,abs=1e-9)
                assert c[1]<=.47+1e-12
            for a,b,c in arms:
                assert math.dist(a,b)==pytest.approx(.16,abs=1e-9)
                assert math.dist(b,c)==pytest.approx(.145,abs=1e-9)
    contacts=[]
    for phase in (.04,.15,.28,.40):
        ankle=_walk_pose(phase,1)[2][1][-1]
        contacts.append((ankle[0]+.64*phase,ankle[1]))
    assert np.allclose(contacts,contacts[0])
    # Contact velocity is continuous: the swinging foot lands without a phase pop.
    eps=1e-6
    for phase in (.5,1):
        a=_walk_pose(phase-eps,1)[2][1][-1]
        b=_walk_pose(phase+eps,1)[2][1][-1]
        assert (b[0]-a[0])/(2*eps)==pytest.approx(-.64,abs=1e-4)


def test_joined_stroke_reveals_by_length_without_changing_other_primitives():
    ctx=canvas()
    points=[(400,700),(500,700),(500,800)]
    ctx.stroke(points,1,p=0)
    assert np.all(np.array(ctx.im)==10)
    ctx.stroke(points,1,p=.25)
    pixels=np.array(ctx.im)
    assert pixels[350,210,0]>100
    assert pixels[350,249,0]==10
    ctx.stroke(points,1,p=1)
    assert np.array(ctx.im)[398,250,0]>100
