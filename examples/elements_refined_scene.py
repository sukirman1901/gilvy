"""One corrected element at a time, at a useful review size.

Person: right-facing side view, advances at the exact planted-foot speed.
Drop and flame: separately authored, joined, supersampled vector contours.
"""
from gilvy.elements import draw_element
from gilvy.easing import R,eo


def draw(ctx,u,duration,params):
    name=params['element']
    ctx.label((513,370),'GILVY | CONTOUR & GAIT STUDY',.7,sz=22,w='Medium')
    appear=eo(R(u,0,.55))
    if name=='person':
        t=max(0,u-.3)
        size=240
        draw_element(ctx,name,center=(280+.64*size*t,780),size=size,
                     progress=appear,phase=t,activity=1)
        ctx.line((230,780+.485*size),(800,780+.485*size),.24)
        ctx.label((513,1060),'menghadap kanan',appear*.8,sz=25)
    else:
        draw_element(ctx,name,center=(513,780),size=270,progress=appear,
                     phase=u,activity=.55)
