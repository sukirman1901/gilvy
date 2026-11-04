"""A trail folds into the very boundary that prevents a return.

Object: one traveller and its trail. Verbs: advance, fold, enclose, resist.
Carry: each of fourteen trail strokes survives the entire transformation.
"""
import math
from gilvy.easing import R, eio, eo, lerp

N=14
C=(540,790)
RADIUS=206

def track(q):
    return (285+490*q, 800-48*math.sin(math.pi*q))

def ring(q):
    theta=math.pi + q*2*math.pi
    return (C[0]+RADIUS*math.cos(theta),C[1]+RADIUS*math.sin(theta))

def draw(ctx,u,duration,params):
    t=u+float(params.get('offset',0))
    appear=eo(R(t,0,.42))
    advance=eio(R(t,.32,2.45))
    fold=eio(R(t,2.52,4.75))
    resist=eio(R(t,4.85,6.38))

    for i in range(N):
        lo=(i+.08)/N
        hi=(i+.92)/N
        # Closely staggered strokes still behave as one bending ribbon.
        shift=eio(R(t,2.52+i*.025,4.42+i*.025))
        pts=[lerp(track(lo+(hi-lo)*j/8),ring(lo+(hi-lo)*j/8),shift)
             for j in range(9)]
        bright=eo(R(advance,(i-.3)/N,(i+.5)/N))
        ctx.poly(pts,appear*(.12+.88*bright),w=2,k=.88)

    end=track(advance)
    center_arrival=eio(R(t,2.52,4.65))
    dot=lerp(end,C,center_arrival)
    dot=(dot[0]-188*resist,dot[1])

    # A short trailing halo arrives after the hero; it is never another subject.
    trailing=track(eio(R(t,.46,2.59)))
    trailing=lerp(trailing,C,center_arrival)
    trailing=(trailing[0]-188*eio(R(t,4.99,6.5)),trailing[1])
    ctx.glow(trailing,28,appear*.25)
    ctx.glow(dot,46,appear*(.38+.025*math.sin(t*2)))
    ctx.circ(dot,15,appear*.35,w=1.2)
    ctx.dot(dot,8,appear,glow=False)

    # Pressure becomes visible only where the hero meets its own old trail.
    contact=eo(R(t,5.85,6.4))
    ctx.arc(C,RADIUS,166,194,contact*.8,w=2.5)
    ctx.glow((C[0]-RADIUS,C[1]),22,contact*.3)
    # Local life in the landed pose, without camera or shape scaling.
    ctx.circ(dot,22,contact*(.14+.04*math.sin(t*2.2)),w=1.2,
             p=eo(R(t,6.1,6.65)))
