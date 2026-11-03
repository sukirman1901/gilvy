"""Build two proofs using only reusable Gilvy product layers.

Numtera study: source 30..35s, manual object IDs + thresholded measurements.
No source screenshots, source audio or special renderer callbacks are used.
Metric exercise: unrelated composition proving the tools are not ticket-specific.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import ImageFont

from gilvy.product import ProductFilm
from gilvy.product_render import render_product, preview_product
from gilvy.product_tracks import apply_measured_tracks

HERE=Path(__file__).resolve().parent
FONT=HERE/'fonts/NimbusSans-Regular.otf'
BOLD=HERE/'fonts/NimbusSans-Bold.otf'
MONO=HERE/'fonts/NimbusMonoPS-Bold.otf'
BLUE='#0e92fc'


def rect(id,w,h,x,y,fill,radius=0,**more):
    return dict(id=id,type='rect',width=round(w),height=round(h),x=x,y=y,
                pivot_x=0,pivot_y=0,fill=fill,radius=radius,**more)


def text(id,value,x,y,w=600,h=50,size=24,font=FONT,**more):
    return dict(id=id,type='text',width=w,height=h,x=x,y=y,pivot_x=0,pivot_y=0,
                text=value,size=size,font=str(font),align='left',valign='top',**more)


def fitted_word(id,value,x,y,w,h,font=FONT):
    face=ImageFont.truetype(str(font),100)
    b=face.getbbox(value,anchor='ls');asc,desc=face.getmetrics()
    sx=w/(b[2]-b[0]);sy=h/(b[3]-b[1])
    node=text(id,value,x-sx*b[0],y-sy*(asc+b[1]),w=math.ceil(face.getlength(value))+5,
              h=asc+desc+5,size=100,font=font,baseline=asc,scale_x=sx,scale_y=sy,
              color=BLUE if id=='learning-word' else '#000000')
    return node,sx*b[0]


def study():
    rows=json.loads((HERE/'measurements.json').read_text())['frames']
    layers=[];tracks=[]
    def track(layer,prop,samples,status='measured'):
        tracks.append({'layer':layer,'property':prop,'samples':[
            {'time':t,'value':v,'status':status,'confidence':.9 if status!='estimated' else .8}
            for t,v in samples]})
    for word,w,h,y in [('Agent',258,84,498),('Approves',412,84,498),('it',49,70,497),('as',97,54,514)]:
        visible=[r for r in rows if word in r['black_words_x']]
        node,offset=fitted_word('word-'+word,word,visible[0]['black_words_x'][word],y,w,h)
        node['end']=(visible[-1]['source_frame']-900+1)/30
        layers.append(node);track(node['id'],'x',[(r['time'],r['black_words_x'][word]-offset) for r in visible])
        for sample in tracks[-1]['samples']:
            if sample['value']<0:sample.update(status='estimated',confidence=.8)
    visible=[r for r in rows if r['blue_word_visible_bbox']]
    node,offset=fitted_word('learning-word','{ learning }',1186,493,477,89,BOLD)
    node['end']=1.4;layers.append(node)
    track(node['id'],'x',[(r['time'],r['blue_word_visible_bbox'][0]-offset) for r in visible])
    geometry=[]
    for r in rows:
        b=r['bar_visible_bbox']
        if not b:continue
        left,top,right,bottom=b;h=bottom-top
        width=right-left if left>0 and right<1920 else h*11.65
        status='measured' if left>0 and right<1920 else 'estimated'
        if left==0:
            label=r['mono_label_visible_bbox']
            left=label[2]-h*1.94-h*.32 if label else float(np.interp(r['time'],[32.9,33,33.1,33.2,33.266667],[-220,-500,-900,-850,-30]))
        f=r['white_fill_visible_interval'];pad=.32*h
        fill=np.clip((f[1]-left-pad)/max(1,width-2*pad),0,1) if f else .1
        geometry.append((r['time'],left,top,width,h,float(fill),status))
    basew=3355;baseh=288;pad=92
    children=[rect('bar-surface',basew,baseh,0,0,BLUE,46),
              rect('track',basew-2*pad,37,pad,199,'#000000',18),
              rect('fill',basew-2*pad,33,pad+1,201,'#ffffff',16),
              text('bar-label','learning...',pad,62,w=620,h=90,size=70,font=MONO,color='white',
                   keyframes={'blur_length':[[1.4,96],[1.65,96],[1.9,0],[2.7,0],[3.1,100],[3.45,12],[3.8,0]]}),
              dict(id='percentage',type='counter',width=440,height=100,x=basew-pad,y=55,
                   pivot_x=1,pivot_y=0,size=80,font=str(FONT),align='right',valign='top',color='white',suffix='%',
                   keyframes={'value':[[3.2333,18],[3.4667,21],[3.6333,24],[3.8,26],[3.9667,29],
                                       [4.1333,32],[4.3,34],[4.4667,37],[4.6333,39],[4.8,42],[4.966667,44]]})]
    bar=dict(id='bar',type='group',width=basew,height=baseh,x=0,y=0,pivot_x=0,pivot_y=0,start=1.4,children=children)
    layers.append(bar)
    for prop,index,div in [('x',1,1),('y',2,1),('scale_x',3,basew),('scale_y',4,baseh)]:
        for_status=[]
        for g in geometry:
            for_status.append({'time':g[0],'value':g[index]/div,'status':g[6],'confidence':.9 if g[6]=='measured' else .8})
        tracks.append({'layer':'bar','property':prop,'samples':for_status})
    track('fill','clip_width',[(g[0],g[5]) for g in geometry],'estimated')
    panel=[rect('carrier',744,440,0,0,'#edf2ff',24,border='#cbd8e8'),
           rect('ticket',704,164,20,17,'#ffffff',11,border='#9c9fa6'),
           dict(id='mark',type='ellipse',width=52,height=60,x=44,y=62,pivot_x=0,pivot_y=0,fill='#e0ef30',stroke='#e0ef30'),
           dict(id='mark-cutout',type='ellipse',width=42,height=42,x=63,y=48,pivot_x=0,pivot_y=0,fill='#ffffff',stroke='#ffffff'),
           text('ticket-id','#442',127,40,w=60,h=35,size=18,font=BOLD,color='#1887d3'),
           rect('support-pill',83,27,191,42,'#b0ddfa',13),text('support','Support',205,44,w=74,h=30,size=14,font=BOLD,color='#208bcc'),
           rect('status-pill',124,27,280,42,'#f3cbd1',13),text('status','Status: Ingested',301,48,w=110,h=24,size=10,color='#d97180'),
           text('ticket-title','Asset #882-X: Thermal Interlock Triggered — Operations\nBlocked',127,79,w=590,h=64,size=20,font=BOLD,color='#252b35'),
           text('ticket-subtitle','Customers unable to access...',127,140,w=570,h=38,size=17,color='#9299a1'),
           text('log','Numtera analyzing the solved ticket...',28,260,w=700,h=38,size=24,font=MONO,color='black',reveal='characters',
                keyframes={'progress':[[4.1,0],[4.55,1,'linear']]}),
           text('log-next','Tracing underlying context...',28,297,w=700,h=38,size=24,font=MONO,color='black',reveal='characters',
                keyframes={'progress':[[4.87,0],[5, .4,'linear']]})]
    for child in panel[1:]:
        child['opacity']=0;child.setdefault('keyframes',{})['opacity']=[[3.9,0],[4.05,1,'linear']]
    panel_node=dict(id='panel',type='group',width=744,height=440,x=588,y=600,pivot_x=0,pivot_y=0,start=3.73,
                    children=panel,clip_radius=24,keyframes={'clip_height':[[3.73,0],[3.83,70/440],[3.93,170/440],
                    [4.03,230/440],[4.2,280/440],[4.5,332/440],[4.83,332/440],[4.966667,360/440]]})
    layers.append(panel_node)
    track('panel','y',[(g[0],g[2]+g[4]+39) for g in geometry],'estimated')
    scans=[r for r in rows if r['scanline_visible_bbox']]
    for id,height,fill,blur in [('scan-glow',28,'#6ef8ff70',12),('scanline',3,'#16a2e8',0)]:
        node=rect(id,900,height,0,0,fill,2,start=scans[0]['time']-30,blur=blur)
        layers.append(node)
        for prop,get in [('x',lambda b:b[0]),('y',lambda b:b[1]-(height-3)/2),('scale_x',lambda b:(b[2]-b[0])/900)]:
            track(id,prop,[(r['time'],get(r['scanline_visible_bbox'])) for r in scans])
    film=dict(style='product',size=[1920,1080],fps=30,duration=5,samples=1,
              background={'base':'#ffffff','lights':[{'x':1.2,'y':.6,'radius':.4,'color':'#ffffff',
              'keyframes':{'x':[[0,1.2],[3.55,1.2],[5,1.1,'linear']],
              'red':[[0,255],[3.55,255],[4.2,183],[5,161]],
              'green':[[0,255],[3.55,255],[4.2,220],[5,211]]}}]},layers=layers)
    for key in children[-1]['keyframes']['value']:
        key.append('linear')
    return apply_measured_tracks(film,{'source':'Numtera source 30..35 seconds; see measurements.json limitations','tracks':tracks},30,allow_estimated=True)


def metric_exercise():
    # Fictional values, no local economic or financial claim.
    children=[rect('metric-surface',680,340,0,0,'#16191d',24),
        text('metric-title','Data contoh / kapasitas terpakai',40,32,w=590,h=40,size=22,color='#a8aeb5'),
        dict(id='metric-number',type='counter',width=590,height=95,x=40,y=86,pivot_x=0,pivot_y=0,
             font=str(FONT),size=68,color='white',align='left',valign='top',suffix='%',
             keyframes={'value':[[.8,0],[3.7,72,[.2,0,.2,1]]]}),
        dict(id='metric-curve',type='path',width=600,height=120,x=40,y=195,pivot_x=0,pivot_y=0,
             commands=[['M',0,95],['C',90,95,95,65,180,65],['C',300,65,300,15,420,15],['L',590,15]],
             stroke='#b9e879',stroke_width=3,keyframes={'progress':[[1,0],[3.7,1,[.2,0,.2,1]]]})]
    return dict(style='product',size=[1280,720],fps=30,duration=5,background={'base':'#080a0c'},layers=[
        dict(id='metric',type='group',width=680,height=340,x=640,y=360,children=children,
             keyframes={'clip_height':[[0,0],[.8,1,[.2,0,.2,1]]],'y':[[0,390],[.8,360,'out_cubic']]})])


def build(out,render=False,font_dir=None):
    global FONT,BOLD,MONO
    if font_dir is None:
        raise ValueError('Pass --font-dir containing NimbusSans-Regular.otf, NimbusSans-Bold.otf and NimbusMonoPS-Bold.otf. Fonts are not redistributed by this example.')
    font_dir=Path(font_dir).resolve()
    FONT=font_dir/'NimbusSans-Regular.otf';BOLD=font_dir/'NimbusSans-Bold.otf';MONO=font_dir/'NimbusMonoPS-Bold.otf'
    for font in (FONT,BOLD,MONO):
        if not font.is_file():raise FileNotFoundError(font)
    out=Path(out).resolve()
    if out.exists():raise FileExistsError('Choose a new output directory to avoid mixing evidence runs')
    out.mkdir(parents=True)
    film,audit=study();(out/'study.provenance.json').write_text(json.dumps(audit,indent=2))
    results=[]
    for name,spec in [('numtera-study',film),('metric-exercise',metric_exercise())]:
        # Make fonts portable in the generated spec folder.
        import shutil
        (out/'fonts').mkdir(exist_ok=True)
        for font in (FONT,BOLD,MONO):shutil.copyfile(font,out/'fonts'/font.name)
        def relative(nodes):
            for n in nodes:
                if 'font' in n:n['font']='fonts/'+Path(n['font']).name
                if n['type']=='group':relative(n['children'])
        relative(spec['layers'])
        path=out/f'{name}.json';path.write_text(json.dumps(spec,indent=2))
        ProductFilm(spec,out)  # fail asset/spec checks before any encoding
        results.append(preview_product(path,out/f'{name}-stills',[0,1.4,2.5,3.5,4,4.5,4.9666667]))
        if render:results.append(render_product(path,out/f'{name}.mp4'))
    (out/'build-results.json').write_text(json.dumps(results,indent=2))
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='out/primitive-study');parser.add_argument('--render',action='store_true')
    parser.add_argument('--font-dir',required=True,help='Local directory containing the three Nimbus OTF fonts; see README')
    args=parser.parse_args();print(json.dumps(build(args.out,args.render,args.font_dir),indent=2))
