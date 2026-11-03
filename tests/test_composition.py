"""Behavior across composition clocks, native seek, assets and render cancellation."""
import copy
import io
import json
import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import numpy as np
from PIL import Image
import pytest
import yaml

from gilvy.errors import GilvyError
from gilvy.product import ProductFilm, ease, validate
from gilvy.product_primitives import text_layout
from gilvy.product_preview import PreviewSession, inspect_product_frame, preview_server
from gilvy.product_tracks import apply_measured_tracks
from gilvy.particles import particle_positions, resample_contour
from gilvy.render_jobs import RenderControl, RenderCancelled, RenderJobs
from gilvy.product_render import render_product
from gilvy.cli import run


def box(identifier="box", **fields):
    return {"id": identifier, "type": "rect", "width": 10, "height": 10,
            "radius": 0, "fill": "white", **fields}


def film(*layers):
    return {"style": "product", "size": [240, 160], "fps": 10, "duration": 4,
            "background": {"base": "black"}, "layers": list(layers)}


def scene(child, **fields):
    return {"id": "scene", "type": "group", "width": 160, "height": 120,
            "x": 120, "y": 80, "start": 1, "end": 3, "time_space": "local",
            "children": [child], **fields}


def save(tmp_path, spec):
    path = tmp_path/"film.yaml"
    path.write_text(yaml.safe_dump(spec))
    return path


def test_nested_local_clocks_and_persistent_global_object():
    child = box(time_space="local", start=.2, end=1.5, y=60,
                keyframes={"x": [[0, 20], [1, 100, "linear"]]})
    persistent = box("persistent", x=10, y=10,
                     keyframes={"x": [[0, 10], [4, 90, "linear"]]})
    original = film(scene(child), persistent)
    snapshot = copy.deepcopy(original)
    a = ProductFilm(original)
    assert original == snapshot
    assert a.timeline["box"].start == pytest.approx(1.2)
    assert a.state(child, 1.7)["x"] == pytest.approx(60)
    assert a.state(persistent, 1.7)["x"] == pytest.approx(44)
    # Moving a whole scene retains local choreography and global continuity.
    moved = copy.deepcopy(original)
    moved["layers"][0].update(start=2, end=4)
    b = ProductFilm(moved)
    assert b.state(child, 2.7)["x"] == pytest.approx(60)
    assert b.state(persistent, 2.7)["x"] == pytest.approx(64)
    # End is exclusive, including for a child with a longer global interval.
    assert not a.timeline["box"].active(2.5)
    assert not a.timeline["scene"].active(3)
    assert np.array_equal(a.frame_at(17), a.frame(1.7))
    a.frame_at(28)  # Seeking backwards must not replay an entrance.
    assert np.array_equal(a.frame_at(17), a.frame(1.7))


def test_legacy_children_keep_global_tracks_and_parent_visibility():
    child = box(x=40, y=40, keyframes={"x": [[0, 0], [4, 100, "linear"]]})
    spec = film(scene(child))
    f = ProductFilm(spec)
    assert f.state(child, 2)["x"] == 50
    assert not f.timeline["box"].active(.5)
    assert not f.timeline["box"].active(3)
    for index in (-1, 40, True, 2.5):
        with pytest.raises(GilvyError): f.frame_at(index)


@pytest.mark.parametrize("change", [
    {"time_space": "parent"}, {"start": float("nan")}, {"end": 3},
    {"keyframes": {"x": [[0, 10], [2, 20]]}},
])
def test_local_timing_rejects_outside_parent_or_track(change):
    child = box(time_space="local", start=.5, end=1.5, **{})
    child.update(change)
    with pytest.raises(GilvyError): validate(film(scene(child)))


def test_flow_layout_and_text_fit_wrap_are_measured_without_mutation():
    a,b=box("a",width=30,height=20),box("b",width=50,height=40)
    group=scene(a,start=0,end=4,layout={"direction":"row","gap":10,"padding":10,"align":"end"})
    group["children"].append(b)
    spec=film(group)
    f=ProductFilm(spec)
    assert "x" not in a
    left,right=f.layers[0]["children"]
    assert (left["x"],right["x"],left["y"],right["y"]) == (25,75,100,90)
    group["children"][0]["x"]=12
    with pytest.raises(GilvyError,match="layout-owned"): ProductFilm(spec)
    del group["children"][0]["x"]
    group["layout"]["gap"]=200
    with pytest.raises(GilvyError,match="overflows group"): ProductFilm(spec)
    text={"id":"money","width":120,"height":65,"text":"Rp 1,94 T", "size":40,
          "overflow":"fit","padding":5,"min_size":12}
    face,layout=text_layout(text,text["text"])
    assert 12<=layout["size"]<40 and len(layout["lines"])==1 and layout["fits"]
    assert text["size"]==40
    _,wrapped=text_layout({**text,"width":140,"height":120,"size":20,"overflow":"wrap","max_lines":3},"one two three four five")
    assert 1<len(wrapped["lines"])<=3
    with pytest.raises(GilvyError,match="max_lines"):
        text_layout({**text,"min_size":40},text["text"])


def test_particles_keep_index_identity_and_arc_length_density():
    assert resample_contour([[0,0],[1,0],[10,0]],6) == [[0,0],[2,0],[4,0],[6,0],[8,0],[10,0]]
    assert resample_contour([[2,2],[2,2]],3) == [[2,2]]*3
    assert len(resample_contour([[0,0],[10,0],[10,10]],6,closed=True))==6
    node={"id":"dots","type":"particles","width":160,"height":120,"x":120,"y":80,
          "points":[[20,30],[60,30]], "poses":[[2,[[40,70],[80,70]],"linear"]]}
    assert particle_positions(node,1,ease)==[[30,50],[70,50]]
    f=ProductFilm(film(node))
    assert np.array(f.frame_at(10))[70,70,0]>200
    f.frame_at(30)
    assert particle_positions(node,1,ease)==[[30,50],[70,50]]
    node["poses"][0][1]=[[40,70]]
    with pytest.raises(GilvyError,match="equal pose counts"): ProductFilm(film(node))


def test_measurement_import_converts_global_source_to_local_track():
    spec=film(scene(box(time_space="local",end=2)))
    report={"source":"study","tracks":[{"layer":"box","property":"x","samples":[
        {"time":31,"value":10,"status":"measured","confidence":.9},
        {"time":32,"value":50,"status":"measured","confidence":.9}]}]}
    result,provenance=apply_measured_tracks(spec,report,time_origin=30)
    assert result["layers"][0]["children"][0]["keyframes"]["x"]==[[0,10,"linear"],[1,50,"linear"]]
    assert provenance["tracks"][0]["track_origin"]==1


def test_nested_group_offsets_and_resolved_flow_spec_can_be_reused():
    child=box(time_space="local",start=.1,end=.8,
              keyframes={"opacity":[[0,0],[.5,1,"linear"]]})
    inner={"id":"inner","type":"group","width":40,"height":40,
           "time_space":"local","start":.4,"end":1.6,"children":[child]}
    outer=scene(inner,layout={"padding":10})
    f=ProductFilm(film(outer))
    assert f.timeline["box"].start==pytest.approx(1.5)
    assert f.state(child,1.75)["opacity"]==pytest.approx(.5)
    assert "x" not in f.spec["layers"][0]["children"][0]
    second=ProductFilm(f.spec)
    assert np.array_equal(f.frame_at(17),second.frame_at(17))


def test_preview_cache_invalidates_source_and_asset_and_bounds(tmp_path):
    asset=tmp_path/"asset.png"
    Image.new("RGB",(10,10),"red").save(asset)
    spec=film({**box(x=120,y=80),"type":"image","src":"asset.png"})
    path=save(tmp_path,spec)
    session=PreviewSession(path,cache_bytes=1024*1024)
    first=session.png(5)
    assert first==session.png(5)
    assert len(session.cache)==1
    Image.new("RGB",(10,10),"blue").save(asset)
    second=session.png(5)
    assert second!=first and len(session.cache)==1
    spec["layers"]=[box(x=10,y=10)]
    save(tmp_path,spec);asset.unlink()
    assert session.png(5)!=second
    result=inspect_product_frame(path,5,tmp_path/"frame.png")
    assert np.array_equal(np.array(Image.open(result["image"])),np.array(session.film.frame_at(5)))
    assert result["layers"][0]["quad_in_parent"]
    path.write_text("broken: spec")
    with pytest.raises(GilvyError):session.png(5)


def test_http_seek_and_cli_are_real_native_frames(tmp_path,capsys):
    path=save(tmp_path,film(box(x=80,y=80)))
    server=preview_server(path,0)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f"http://127.0.0.1:{server.server_port}"
    try:
        meta=json.load(urlopen(base+"/metadata"))
        assert meta["frames"]==40 and meta["audio_preview"] is False
        png=urlopen(base+"/frame?frame=12").read()
        assert Image.open(io.BytesIO(png)).size==(240,160)
        assert json.load(urlopen(base+"/inspect?frame=12"))["frame"]==12
        with pytest.raises(HTTPError):urlopen(base+"/frame?frame=40")
        assert b"Gilvy frame inspector" in urlopen(base).read()
    finally:server.shutdown();server.server_close();worker.join()
    assert run(["inspect-product",str(path),"--frame","12","--out",str(tmp_path/"cli.png")])==0
    assert json.loads(capsys.readouterr().out)["frame"]==12


def test_cancel_during_render_preserves_existing_video_and_cleans_encoder(tmp_path):
    path=save(tmp_path,film(box(x=80,y=80)))
    dest=tmp_path/"out.mp4";dest.write_bytes(b"existing video")
    class CancelAfterFrame(RenderControl):
        def frame_done(self,index,elapsed):
            super().frame_done(index,elapsed)
            self.cancelled.set()
    control=CancelAfterFrame()
    with pytest.raises(RenderCancelled):render_product(path,dest,control=control)
    assert dest.read_bytes()==b"existing video"
    assert not list(tmp_path.glob(".product-*"))
    assert not dest.with_suffix(".product.json").exists()


def test_job_queue_status_and_cancel_are_observable(tmp_path,monkeypatch):
    import gilvy.product_render
    path=save(tmp_path,film(box(x=80,y=80)))
    entered,release=threading.Event(),threading.Event()
    def render(*args,control,**kwargs):
        control.update("preparing");entered.set();release.wait(3);control.check()
        return {"video":"done"}
    monkeypatch.setattr(gilvy.product_render,"render_product",render)
    jobs=RenderJobs()
    try:
        first=jobs.start(path,tmp_path/"one.mp4")
        assert entered.wait(3)
        assert jobs.get(first["job_id"])["status"]=="preparing"
        with pytest.raises(GilvyError,match="owns"):jobs.start(path,tmp_path/"one.mp4")
        assert jobs.cancel(first["job_id"])["cancel_requested"]
        release.set()
    finally:release.set();jobs.executor.shutdown(wait=True)
    assert jobs.get(first["job_id"])["status"]=="cancelled"
    control=RenderControl();control.publish(lambda:None)
    assert control.snapshot()["status"]=="published"
    jobs.jobs["published"]={"output":"done","control":control}
    assert jobs.cancel("published")["cancel_requested"] is False


def test_mcp_job_reaches_completed_with_real_verified_video(tmp_path):
    import time
    from gilvy.mcp_server import start_product_render, product_render_status, cancel_product_render
    spec=film(box(x=80,y=80));spec["duration"]=.2
    path=save(tmp_path,spec)
    started=json.loads(start_product_render(str(path),str(tmp_path/"job.mp4")))
    assert started["ok"]
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        status=json.loads(product_render_status(started["job_id"]))
        if status["status"] in ("completed","failed","cancelled"):break
        time.sleep(.01)
    assert status["status"]=="completed",status
    assert status["rendered_frames"]==status["total_frames"]==2
    assert status["result"]["qc"]["ok"]
    assert not json.loads(cancel_product_render(started["job_id"]))["cancel_requested"]


def test_installed_notes_include_full_composition_contract(capsys):
    from gilvy.mcp_server import product_motion_notes
    notes=product_motion_notes()
    assert "## Timing contract" in notes and "## Observable product render jobs" in notes
    assert run(["product-notes"])==0
    assert capsys.readouterr().out.rstrip()==notes.rstrip()
