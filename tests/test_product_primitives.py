"""Behavioral regressions for general tools rather than specific UI templates."""
import copy

import numpy as np
import pytest
from PIL import Image, ImageDraw

from gilvy.errors import GilvyError
from gilvy.product import ProductFilm, validate, interpolate, DEFAULTS, project
from gilvy.product_primitives import filter_plane, counter_text, text_plane
from gilvy.product_tracks import apply_measured_tracks
from gilvy.theme import bundled_fonts


def spec(layer):
    return {'style':'product','size':[240,160],'fps':30,'duration':2,
            'background':{'base':'#000000'},'layers':[layer]}


def box(**kwargs):
    return {'id':'box','type':'rect','width':100,'height':100,'x':120,'y':80,
            'radius':0,'fill':'#ffffff',**kwargs}


def test_group_mask_reveals_without_changing_child_scale():
    child=box(id='child',width=10,height=10,x=50,y=25)
    group={'id':'group','type':'group','width':100,'height':100,'x':120,'y':80,
           'children':[child], 'keyframes':{'clip_height':[[0,0],[1,1,'linear']]}}
    film=ProductFilm(spec(group))
    assert np.array(film.frame(0)).max()==0
    assert np.array(film.frame(.1)).max()==0
    for t in (.4,.8):
        mask=np.array(film.frame(t))[:,:,0]>200
        yy,xx=np.where(mask)
        assert (xx.min(),xx.max(),yy.min(),yy.max())==(115,124,50,59)
    # Cached planes must not be damaged by applying a mask at an earlier time.
    assert np.array_equal(np.array(film.frame(.8)),np.array(ProductFilm(spec(group)).frame(.8)))


def test_type_layout_reveal_keeps_baseline_and_left_edge(tmp_path):
    custom=tmp_path/'custom.ttf';custom.write_bytes((bundled_fonts()/'Poppins-Regular.ttf').read_bytes())
    node={'id':'text','type':'text','width':220,'height':100,'font':str(custom),
          'text':'Ticket analyzed','size':22,'align':'left','padding':8,'baseline':50,
          'color':'white','reveal':'characters','overflow':'error'}
    a=text_plane(node,progress=.45).getbbox();b=text_plane(node,progress=1).getbbox()
    assert a[0]==b[0] and a[1]==b[1] and a[2]<b[2]
    film=ProductFilm(spec({**node,'x':120,'y':80}),tmp_path)
    assert film.spec['layers'][0]['font']==str(custom)
    with pytest.raises(GilvyError,match='font not found'):
        ProductFilm(spec({**node,'font':'missing.ttf'}),tmp_path)
    with pytest.raises(GilvyError,match='overflows'):
        text_plane({**node,'width':20})


def test_counter_is_independent_and_locale_is_explicit():
    assert counter_text({'prefix':'Rp ','suffix':' T','decimals':2,'decimal_separator':','},1.94)=='Rp 1,94 T'
    counter={'id':'number','type':'counter','width':150,'height':60,'x':120,'y':80,
             'size':30,'color':'white','suffix':'%','align':'right','padding':8,
             'progress':.1,'keyframes':{'value':[[0,21],[2,44,'linear']]}}
    film=ProductFilm(spec(counter))
    assert film.state(counter,1)['value']==32.5
    assert not np.array_equal(np.array(film.frame(0)),np.array(film.frame(1)))
    assert film.state(counter,1)['progress']==.1


def test_word_reveal_preserves_authored_line_breaks():
    node={'id':'words','type':'text','width':220,'height':100,'text':'One two\nThree four',
          'size':22,'align':'left','baseline':30,'color':'white','reveal':'words'}
    a=text_plane(node,progress=.5).getbbox();b=text_plane(node,progress=.75).getbbox()
    assert b[3]>a[3]+15  # Third word occupies the authored second line.


def test_custom_curve_pivot_scale_and_dynamic_background():
    keys=[[0,0],[1,100,[.42,0,.58,1]]]
    assert interpolate(keys,.5)==pytest.approx(50,abs=.0001)
    assert interpolate(keys,.25)<25
    p=project((100,80),{**DEFAULTS,'x':20,'y':30,'pivot_x':0,'pivot_y':0,'scale_x':2})
    assert np.allclose(p,[[20,30],[220,30],[220,110],[20,110]])
    s=spec(box(opacity=0));s['background']={'base':'#ffffff','lights':[
        {'x':0,'y':.5,'radius':.3,'color':'#0088ff','keyframes':{'x':[[0,0],[2,1,'linear']], 'red':[[0,0],[2,100,'linear']]}}]}
    f=ProductFilm(s)
    assert np.array(f.frame(0))[80,0,0]<40
    assert np.array(f.frame(1.9))[80,0,0]>230


def test_directional_blur_has_no_black_halo_and_layer_shutter_is_local():
    im=Image.new('RGBA',(100,100));ImageDraw.Draw(im).rectangle((45,45,54,54),fill=(255,0,0,255))
    blurred=filter_plane(im,length=30)
    a=np.array(blurred);ys,xs=np.where(a[:,:,3]>5)
    assert (xs.max()-xs.min())>(ys.max()-ys.min())*2
    assert a[50,35,0]>=250 and a[50,35,3]>0
    s=spec(box(width=10,height=10,samples=7,shutter=1,
               keyframes={'x':[[0,30],[2,210,'linear']]}))
    s['layers'].append(box(id='static',width=10,height=10,x=120,y=30))
    frame=np.array(ProductFilm(s).frame(1))[:,:,0]
    assert (frame[30]>200).sum()==10
    assert (frame[80]>5).sum()>10


def test_paths_reveal_and_ellipses_are_general_shapes():
    node={'id':'path','type':'path','width':120,'height':80,'x':120,'y':80,
          'commands':[['M',5,40],['C',30,0,70,80,115,40]],'stroke':'white','stroke_width':3,
          'keyframes':{'progress':[[0,0],[2,1,'linear']]}}
    film=ProductFilm(spec(node))
    assert np.array(film.frame(0)).max()==0
    assert (np.array(film.frame(1))>0).sum()<(np.array(film.frame(1.9))>0).sum()
    ellipse={**box(),'type':'ellipse','stroke':'#00ff00'}
    assert ProductFilm(spec(ellipse)).frame(0).getbbox()


def test_measurement_import_preserves_uncertainty_and_caller():
    s=spec(box());original=copy.deepcopy(s)
    report={'source':'reviewed frame study','tracks':[{'layer':'box','property':'x','samples':[
        {'time':30,'value':10,'status':'measured','confidence':.95},
        {'time':32,'value':100,'status':'reviewed','confidence':.9}]}]}
    out,audit=apply_measured_tracks(s,report,30)
    assert s==original and out['layers'][0]['keyframes']['x']==[[0,10,'linear'],[2,100,'linear']]
    assert audit['tracks'][0]['estimated_samples']==0
    sample=report['tracks'][0]['samples'][1];sample['status']='estimated'
    with pytest.raises(GilvyError,match='review before import'):apply_measured_tracks(s,report,30)
    _,audit=apply_measured_tracks(s,report,30,allow_estimated=True)
    assert audit['tracks'][0]['estimated_samples']==1
    sample['confidence']=.2
    with pytest.raises(GilvyError):apply_measured_tracks(s,report,30,allow_estimated=True)


def test_mcp_import_does_not_write_and_reports_bad_measurements(tmp_path):
    import json
    from gilvy.mcp_server import import_product_tracks
    path=tmp_path/'film.json';path.write_text(json.dumps(spec(box())))
    data=tmp_path/'measurements.json'
    data.write_text(json.dumps({'source':'manual review','tracks':[
        {'layer':'box','property':'x','samples':[{'time':30,'value':44,'status':'reviewed','confidence':.9}]}]}))
    result=json.loads(import_product_tracks(str(path),str(data),30))
    assert result['ok'] and result['spec']['layers'][0]['keyframes']['x'][0][1]==44
    assert 'keyframes' not in json.loads(path.read_text())['layers'][0]
    data.write_text('[]')
    assert not json.loads(import_product_tracks(str(path),str(data)))['ok']


@pytest.mark.parametrize('fields',[
    {'font':'https://example.com/font.ttf'}, {'align':'diagonal'}, {'decimals':True},
    {'samples':9}, {'keyframes':{'x':[[0,0],[2,100,[2,0,1,1]]]}},
    {'clip_width':-1}, {'type':'path','commands':[['L',1,2],['Z']]},
    {'type':'path','commands':[['M',0,0],['C',1,2]]},
])
def test_invalid_tools_rejected(fields):
    with pytest.raises(GilvyError):validate(spec(box(**fields)))
