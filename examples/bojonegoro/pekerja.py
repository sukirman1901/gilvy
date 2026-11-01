"""One population unfolds, then sorts without changing its denominator.

Object: 100 equal dots. Verb: assemble, count, separate. Carry: all 100 dots.
Meaning: agriculture is a substantial employment group, not oil income.
Consequence: 45 highlighted dots remain beside 55 other employed people.
The displayed 45 is a rounded depiction of 44.625972%, not 45 literal workers.
"""
import math
from gilvy.easing import R, eio, eo, lerp

ORIGIN = (513,780)
DOT_RADIUS = 5.5

def grid_position(i):
    row,col=divmod(i,10)
    return (288+col*50,555+row*50)

def classified_position(i):
    if i<45:
        row,col=divmod(i,5)
        return (310+col*34,644+row*34)
    row,col=divmod(i-45,5)
    return (582+col*34,610+row*34)

def draw(ctx,u,duration,params):
    classify=params['phase']=='classify'
    appear=1 if classify else eo(R(u,0,.5))
    selected=45*eio(R(u,.35,2.9)) if classify else 0

    # The denominator is introduced before the classification.
    ctx.label((513,370),'BOJONEGORO',appear*.65,sz=22,w='Medium')
    number_alpha=1 if classify else eo(R(u,1.2,2.4))
    number=str(min(45,int(selected+1e-6))) if classify else '100'
    ctx.text((513,455),number,ctx.font('Medium',44),number_alpha)
    ctx.label((513,503),'dari 100 pekerja' if classify else 'pekerja',number_alpha*.8,sz=24)

    for i in range(100):
        end=grid_position(i)
        if classify:
            # Sorting preserves identities and spacing; no particles are added.
            lag=(i%10)*.025+(i//10)*.012
            move=eio(R(u,.35+lag,3.25+lag))
            point=lerp(end,classified_position(i),move)
            focus=eo(R(selected,i,min(45,i+1))) if i<45 else 0
            if i<45:
                color=tuple(round(a+(b-a)*focus) for a,b in zip(ctx.theme.white,ctx.theme.green))
                alpha=1
            else:
                color=ctx.theme.white
                alpha=1-.48*eio(R(u,.4,3.3))
        else:
            # A local expansion with a gentle arcing path, not 100 unrelated entrances.
            lag=(i%10)*.025+(i//10)*.06
            move=eio(R(u,.2+lag,1.85+lag))
            point=lerp(ORIGIN,end,move)
            point=(point[0],point[1]-20*math.sin(math.pi*move))
            color=ctx.theme.white
            alpha=appear
        ctx.circ(point,DOT_RADIUS,alpha,w=1.2,fill=.88,col=color)

    if classify:
        labels=eo(R(u,2.5,3.5))
        # Neutral labels; only the counted agricultural dots use the accent.
        ctx.label((378,1048),'pertanian',labels,sz=25,w='Medium')
        ctx.label((650,1048),'lainnya',labels*.7,sz=25)
        underline=eo(R(u,2.68,3.68))
        ctx.line((310,1082),(446,1082),labels*.4,p=underline,w=1.2)
        source=eo(R(u,.7,1.5))
        ctx.label((513,1480),'BPS | Agustus 2025',source*.8,sz=24)
        ctx.label((513,1518),'44,63%, dibulatkan menjadi 45%',source*.7,sz=22)

