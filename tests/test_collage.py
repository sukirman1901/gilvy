"""Editorial fragments keep their scale, clock, annotations and asset identity."""
import copy
import json

import numpy as np
from PIL import Image, ImageDraw
import pytest
import yaml

from gilvy.assets import build_manifest, require_assets, plate_pixel_size
from gilvy.episode import load_episode
from gilvy.errors import EpisodeError, GilvyError
from gilvy.formats import Fit
from gilvy.image_scene import render_image_frame
from gilvy.render import build_state, render_episode
from gilvy.theme import Theme


def scene(layers, **extra):
    return {"id": "collage", "type": "image", "composition": "collage", "min": 2,
            "caption": ["One clear relationship"], "layers": layers, "transition_out": "cut", **extra}


def fragment(**extra):
    return {"id": "subject", "src": "subject.png", "role": "subject", "alpha": "transparent", "depth": 1,
            "placement": {"x": 540, "y": 960, "width": 200, "height": 100}, **extra}


def episode(tmp_path, *scenes):
    path = tmp_path/"ep.yaml"
    path.write_text(yaml.safe_dump({"name": "collage", "style": "history-story", "audio_mode": "silent", "scenes": list(scenes)}))
    return load_episode(path)


def assets(tmp_path):
    im = Image.new("RGBA", (80, 40))
    ImageDraw.Draw(im).rectangle((1, 1, 78, 38), fill=(255, 0, 0, 255))
    im.save(tmp_path/"subject.png")
    Image.new("RGB", (270, 480), (65, 60, 55)).save(tmp_path/"paper.png")


def theme():
    return Theme(width=270, height=480, fps=4, scale=1, fit=Fit(scale=.25), intro=0, outro=0)


def picture(ep, u, start=0):
    from gilvy.render import scene_payload
    return render_image_frame(theme(), scene_payload(ep.scenes[0], ep), u, 2, str(ep.source_dir), scene_start=start)


def red_bounds(frame):
    y, x = np.where((frame[:,:,0]>160) & (frame[:,:,1]<40))
    return x.min(), y.min(), x.max(), y.max()


def test_fragment_size_position_rotation_and_opacity_do_not_cover_fit(tmp_path):
    assets(tmp_path)
    item=fragment(tracks=[{"property":"rotation","keys":[{"t":0,"v":0},{"t":1,"v":90}]},
                          {"property":"opacity","keys":[{"t":1,"v":1},{"t":2,"v":0}]}])
    ep=episode(tmp_path,scene([item]))
    assert ep.scenes[0].params["grade"]=="none" and ep.scenes[0].params["grain"]==0
    a,b=red_bounds(picture(ep,0)),red_bounds(picture(ep,1))
    assert 45 <= a[2]-a[0] <= 50 and 20 <= a[3]-a[1] <= 25
    assert abs((a[0]+a[2])/2-135)<2
    assert b[3]-b[1] > b[2]-b[0]
    assert picture(ep,2).max() < 30


def test_global_tracks_continue_through_negative_transition_handles(tmp_path,monkeypatch):
    assets(tmp_path)
    item=fragment(clock="episode",tracks=[{"property":"x","keys":[{"t":0,"v":0},{"t":4,"v":400}]}])
    base={"id":"paper","src":"paper.png","role":"background","alpha":"opaque","depth":0}
    overlays=[{"kind":"highlighter","parent":"subject","clock":"episode","at":1.5,
               "duration":1,"x":10,"y":10,"w":80,"h":30,"color":"#0000ff"}]
    ep=episode(tmp_path,scene([base,item],transition_out="dissolve",transition=.5,overlays=overlays),
               scene([base,copy.deepcopy(item)],id="second",overlays=copy.deepcopy(overlays)))
    import gilvy.render as render
    monkeypatch.setattr(render,"theme_for",lambda _:theme())
    state=build_state(ep,[2,2])
    # Incoming scene-local time is clamped for its entrances; episode time must
    # still refer to 1.75s, not the incoming shot's nominal 2.0s start.
    assert np.array_equal(state.picture(0,1.75),state.picture(1,-.25))
    assert np.array_equal(state.frame_array(7),state.picture(0,1.75).astype("uint8"))


def test_parent_annotation_moves_with_paper_and_can_be_occluded(tmp_path):
    assets(tmp_path)
    Image.new("RGBA",(80,40),"white").save(tmp_path/"sheet.png")
    paper=fragment(id="sheet",src="sheet.png",role="paper",alpha="any",tracks=[
        {"property":"x","keys":[{"t":0,"v":0},{"t":1,"v":200}]}])
    highlight={"kind":"highlighter","parent":"sheet","at":0,"duration":.1,"x":20,"y":20,"w":40,"h":20,"color":"#ff0000"}
    ep=episode(tmp_path,scene([paper],overlays=[highlight]))
    early=red_bounds(picture(ep,.2));late=red_bounds(picture(ep,1))
    assert 38 <= late[0]-early[0] <= 42
    cover=fragment(id="cover",src="sheet.png",role="paper",alpha="any")
    ep=episode(tmp_path,scene([paper,cover],overlays=[highlight]))
    frame=picture(ep,.2)
    assert not ((frame[:,:,0]>160) & (frame[:,:,1]<40)).any()


def test_manifest_keeps_asset_prompt_separate_from_narrative_and_checks_alpha(tmp_path):
    assets(tmp_path)
    ep=episode(tmp_path,scene([fragment(prompt="One isolated industrial pump.")],
                             prompt="Industrial pump and rice field tell a story about work."))
    ref=[{"time":1,"rgb":[90,80,70],"brightness":90,"contrast":15}]
    row=build_manifest(ep,ref)["assets"][0]
    assert "rice field" not in row["prompt"] and "rice field" in row["scene_brief"]
    assert (row["width"],row["height"])==(200,100)
    assert row["asset_integrity"]["ok"] and row["style_qc"]["status"]=="not_comparable"
    require_assets(ep)
    Image.new("RGB",(80,40),"red").save(tmp_path/"subject.png")
    with pytest.raises(GilvyError,match="missing_transparency"):require_assets(ep)


@pytest.mark.parametrize("edit", [
    {"placement":{"width":float("nan"),"height":100}},
    {"placement":{"width":100,"height":100,"padding":50,"matte":"white"}},
    {"placement":{"width":100,"height":100,"fit":"stretch"}},
    {"role":["subject"]}, {"clock":"wall"}, {"alpha":"png"}, {"id":None},
])
def test_invalid_fragment_fails_before_render(tmp_path,edit):
    with pytest.raises(EpisodeError):episode(tmp_path,scene([fragment(**edit)]))


def test_unknown_parent_and_duplicate_id_are_errors(tmp_path):
    with pytest.raises(EpisodeError,match="parent"):
        episode(tmp_path,scene([fragment()],overlays=[{"kind":"circle","parent":"missing","cx":40,"cy":40,"r":20}]))
    with pytest.raises(EpisodeError,match="duplicate"):
        episode(tmp_path,scene([fragment(),fragment()]))


def test_manifest_covers_intermediate_camera_keys(tmp_path):
    camera={"from":{"scale":1,"x":0,"y":0},"to":{"scale":1,"x":0,"y":0},
            "tracks":{"scale":[{"v":2}],"x":[{"v":300}]}}
    result=plate_pixel_size(camera)
    assert result["width"]==(1080+600)*2 and result["height"]==1920*2


def test_legacy_layer_opacity_is_applied_without_mutating_cache(tmp_path):
    assets(tmp_path)
    item={"src":"paper.png","depth":1,"tracks":[{"property":"opacity","keys":[{"t":0,"v":0},{"t":2,"v":1}]}]}
    ep=episode(tmp_path,scene([item],composition="plate",grade="none",grain=0,camera={"to":{"scale":1.05}}))
    assert picture(ep,0).max()<30 and picture(ep,2).max()>50
    assert picture(ep,0).max()<30


def test_real_collage_encode_keeps_static_camera_and_writes_mode(tmp_path,monkeypatch):
    assets(tmp_path)
    ep=episode(tmp_path,scene([{"id":"paper","role":"background","alpha":"opaque","src":"paper.png","depth":0},fragment()]))
    import gilvy.render as render
    monkeypatch.setattr(render,"theme_for",lambda _:theme())
    result=render_episode(ep,tmp_path/"film.mp4","fixture",1)
    assert result["qc"]["ok"], result["qc"]
    meta=json.loads((tmp_path/"film.timeline.json").read_text())
    assert meta["scenes"][0]["composition"]=="collage"


def test_small_fragment_scale_is_independent_of_camera_floor(tmp_path):
    assets(tmp_path)
    item=fragment(tracks=[{"property":"scale","keys":[{"t":0,"v":.42},{"t":2,"v":1}]}])
    ep=episode(tmp_path,scene([item]))
    early,late=red_bounds(picture(ep,0)),red_bounds(picture(ep,2))
    assert early[2]-early[0]<late[2]-late[0]


def test_packaged_collage_notes_and_cli_include_real_contract(capsys):
    from gilvy.mcp_server import collage_notes
    from gilvy.cli import run
    notes=collage_notes()
    assert '## Attached annotations and layering' in notes
    assert run(['collage-notes'])==0
    assert capsys.readouterr().out.rstrip()==notes.rstrip()


@pytest.mark.parametrize("value",[float('nan'),float('inf'),True])
def test_layer_tracks_reject_nonfinite_and_boolean_values(tmp_path,value):
    with pytest.raises(EpisodeError):
        episode(tmp_path,scene([fragment(tracks=[{"property":"x","keys":[{"t":0,"v":0},{"t":1,"v":value}]}])]))


def test_episode_annotation_requires_explicit_absolute_at(tmp_path):
    with pytest.raises(EpisodeError,match='explicit at'):
        episode(tmp_path,scene([fragment()],overlays=[{"kind":"text","clock":"episode","text":"Evidence"}]))


def test_duplicate_tracks_and_times_fail_before_encode(tmp_path):
    track={"property":"x","keys":[{"t":0,"v":0},{"t":1,"v":100}]}
    with pytest.raises(EpisodeError,match='duplicate track'):
        episode(tmp_path,scene([fragment(tracks=[track,track])]))
    track["keys"][1]["t"]=0
    with pytest.raises(EpisodeError,match='duplicate key times'):
        episode(tmp_path,scene([fragment(tracks=[track])]))


def test_new_vox_card_overlay_resolves_assets_inside_parent(tmp_path):
    assets(tmp_path)
    card={"kind":"card","parent":"subject","src":"paper.png","at":0,
          "x":10,"y":10,"w":80,"h":40,"tilt":0,"shadow":0}
    ep=episode(tmp_path,scene([fragment()],overlays=[card]))
    frame=picture(ep,1)
    assert frame.shape==(480,270,3) and np.isfinite(frame).all()
