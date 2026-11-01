"""Composable line elements. Absolute-time poses, no state, RNG, or theme changes.

Elements supply geometry and local motion. A custom scene still directs the
meaning, position, timing, counted unit, and transitions between objects.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from gilvy.easing import cl, lerp
from gilvy.errors import GilvyError


def _curve(a, b, c, d, n=24):
    return [tuple((1-t)**3*a[j] + 3*(1-t)**2*t*b[j] + 3*(1-t)*t*t*c[j] + t**3*d[j]
                  for j in (0, 1)) for t in (i/n for i in range(n+1))]


@dataclass
class _Pen:
    ctx: object
    center: tuple
    size: float
    progress: float
    phase: float
    activity: float
    alpha: float
    col: tuple
    smooth: bool = False

    def xy(self, p):
        return self.center[0]+p[0]*self.size, self.center[1]+p[1]*self.size

    def path(self, pts, alpha=1, reveal=None):
        pts = [self.xy(p) for p in pts]
        if self.smooth:
            self.ctx.stroke(pts,self.alpha*alpha,
                            p=self.progress if reveal is None else cl(reveal),col=self.col)
            return
        lengths = [math.dist(a,b) for a,b in zip(pts,pts[1:])]
        remaining = sum(lengths)*(self.progress if reveal is None else cl(reveal))
        for a,b,length in zip(pts,pts[1:],lengths):
            if remaining <= 0:
                break
            if length > 0:
                self.ctx.line(a,b,self.alpha*alpha,p=min(1,remaining/length),w=1.6,col=self.col,k=1)
            remaining -= length

    def circle(self, c, r, alpha=1, fill=None, reveal=None):
        if self.smooth and fill is None:
            pts=[(c[0]+r*math.cos(-math.pi/2+i*math.tau/128),
                  c[1]+r*math.sin(-math.pi/2+i*math.tau/128)) for i in range(129)]
            self.path(pts,alpha=alpha,reveal=reveal)
            return
        self.ctx.circ(self.xy(c),r*self.size,self.alpha*alpha,w=1.6,
                      p=self.progress if reveal is None else cl(reveal),fill=fill,col=self.col)


def _walk_pose(phase, activity):
    """Right-facing side view. Each thigh/shin has fixed length 0.225.

    During stance the foot stays on the floor relative to the walking body;
    during return it lifts. Both knees flex forward, arms counter-swing.
    """
    angle=phase*math.tau
    hip_x=-.015*activity
    ankles=[]
    for side in (-1,1):
        t=angle+(math.pi if side<0 else 0)
        q=(t/math.tau)%1
        if q<.5:
            x=.16-.64*q; lift=0
        else:
            swing=(q-.5)*2
            x=-.16+.32*(-4*swing**3+6*swing*swing-swing)
            lift=.065*math.sin(math.pi*swing)**2
        ankles.append((hip_x+side*.015*(1-activity)+x*activity,.47-lift*activity))
    # Derive pelvis height from reach, rather than holding it too low and
    # forcing the planted knee into a crouch. Both legs retain the same length.
    hip_y=max(y-math.sqrt(.4495**2-(x-hip_x)**2) for x,y in ankles)
    hip=(hip_x,hip_y)
    shoulder=(hip[0]+.025*activity,hip[1]-.30)
    legs=[]; arms=[]
    for side,ankle in zip((-1,1),ankles):
        t=angle+(math.pi if side<0 else 0)
        dx,dy=ankle[0]-hip[0],ankle[1]-hip[1]
        distance=math.hypot(dx,dy)
        half=distance*.5
        bend=math.sqrt(max(0,.225**2-half*half))
        knee=((hip[0]+ankle[0])*.5+dy/distance*bend,
              (hip[1]+ankle[1])*.5-dx/distance*bend)
        legs.append((hip,knee,ankle))
        # Elbows flex toward the direction of travel; no sideways diamonds.
        a=-.50*math.cos(t)*activity
        elbow=(shoulder[0]+.16*math.sin(a),shoulder[1]+.16*math.cos(a))
        b=a+.30
        wrist=(elbow[0]+.145*math.sin(b),elbow[1]+.145*math.cos(b))
        arms.append((shoulder,elbow,wrist))
    return hip,shoulder,legs,arms


def _person(p):
    hip,shoulder,legs,arms=_walk_pose(p.phase,p.activity)
    # Far limbs first, clear fore/back depth. All shoe tips face right.
    for i in (0,1):
        p.path(arms[i],alpha=.38 if i==0 else .9)
        leg=legs[i]
        ankle=leg[-1]
        p.path([*leg,(ankle[0]+.045,ankle[1]+.015)],alpha=.4 if i==0 else 1)
    p.path([(shoulder[0],shoulder[1]-.055),shoulder,hip])
    p.circle((shoulder[0]+.012,shoulder[1]-.155),.078)


def _crowd_person(p):
    # Preserve the previously accepted compact group glyph. Its small-size
    # geometry is intentionally independent of the larger articulated person.
    stride = math.sin(p.phase*math.tau)*p.activity
    lift = (1-math.cos(p.phase*math.tau*2))*.008*p.activity
    p.circle((0,-.39-lift),.095)
    p.path([(0,-.27-lift),(0,.10-lift)])
    for side in (-1,1):
        p.path([(0,-.19-lift),(side*.15,-.02),(-side*.18*stride,.12)])
        p.path([(0,.10-lift),(side*.10*stride,.29),(side*.22*stride+side*.045,.49)])


def _people(p):
    # An illustrative group, not a measured population.
    for i in range(5):
        child = _Pen(p.ctx,p.xy(((i-2)*.24,0)),p.size*.36,p.progress,
                     p.phase+i*.08,p.activity,p.alpha,p.col)
        _crowd_person(child)


def _contour(a,b,c,d):
    return _curve(a,b,c,d,n=96)


def _flame(p):
    # Two tongues, a round fixed base, and a closed inner flame distinguish
    # fire from water. Local motion moves the tips, never stretches the base.
    sway=.026*math.sin(p.phase*2.8)*p.activity
    tip=(.10+sway,-.46+.012*math.sin(p.phase*3.4)*p.activity)
    pts=_contour((0,.47),(-.24,.47),(-.38,.21),(-.27,.02))
    pts+=_contour(pts[-1],(-.22,-.06),(-.17,-.13),(-.16,-.24))[1:]
    pts+=_contour(pts[-1],(-.09,-.15),(-.09,-.04),(-.05,0))[1:]
    pts+=_contour(pts[-1],(.08+sway,-.12),(.15+sway,-.29),tip)[1:]
    pts+=_contour(tip,(.35+sway,-.24),(.37,.04),(.28,.25))[1:]
    pts+=_contour(pts[-1],(.22,.40),(.12,.47),(0,.47))[1:]
    p.path(pts)
    inner=_contour((0,.35),(-.17,.31),(-.09,.19),(.025,.065))
    inner+=_contour(inner[-1],(.015,.20),(.18,.30),(0,.35))[1:]
    p.path(inner,alpha=.5,reveal=cl(p.progress*1.5-.5))


def _smoke(p):
    for i in range(3):
        sway=.045*math.sin(p.phase*1.7+i*.8)*p.activity
        x=(i-1)*.17
        p.path(_curve((x,.45),(x-.13+sway,.17),(x+.14+sway,-.15),(x+sway,-.45)),
               alpha=.5-i*.09,reveal=cl(p.progress*1.3-i*.12))


def _drop(p):
    # Symmetric tip into a circular lower bowl with horizontal bottom tangent.
    # A single clean contour avoids reading as the flame's inner tongue.
    tip=(0,-.47)
    pts=_contour(tip,(-.08,-.30),(-.32,-.07),(-.32,.15))
    pts+=_contour(pts[-1],(-.32,.327),(-.177,.47),(0,.47))[1:]
    pts+=_contour(pts[-1],(.177,.47),(.32,.327),(.32,.15))[1:]
    pts+=_contour(pts[-1],(.32,-.07),(.08,-.30),tip)[1:]
    p.path(pts)


def _tree(p):
    sway=.025*math.sin(p.phase*1.5)*p.activity
    p.path([(0,.49),(0,-.17)])
    canopy=_curve((0,.12),(-.48,.18),(-.49,-.18),(-.25,-.24))
    canopy+=_curve(canopy[-1],(-.22,-.58),(.20+sway,-.57),(.26+sway,-.26))[1:]
    canopy+=_curve(canopy[-1],(.49+sway,-.23),(.48,.17),(0,.12))[1:]
    p.path(canopy,reveal=cl(p.progress*1.6-.6))
    p.path([(-.15,-.04),(0,.10),(.15,-.09)],alpha=.6,reveal=cl(p.progress*2-1))


def _sprout(p):
    sway=.025*math.sin(p.phase*1.8)*p.activity
    p.path([(0,.48),(sway,-.13)])
    for side in (-1,1):
        a=(sway,.05); b=(side*.38,-.24)
        pts=_curve(a,(side*.03,-.26),b,b)
        pts+=_curve(b,(side*.29,.07),(side*.10,.14),a)[1:]
        p.path(pts,reveal=cl(p.progress*1.7-.7))
    p.path([(-.27,.49),(.27,.49)],alpha=.4)


def _house(p):
    p.path([(-.44,-.04),(0,-.42),(.44,-.04)])
    p.path([(-.34,-.12),(-.34,.43),(.34,.43),(.34,-.12)])
    p.path([(-.09,.43),(-.09,.12),(.09,.12),(.09,.43)],reveal=cl(p.progress*1.5-.5))


def _building(p):
    p.path([(-.32,.49),(-.32,-.49),(.32,-.49),(.32,.49),(-.32,.49)])
    for y in (-.29,-.04,.21):
        for x in (-.13,.13):
            p.path([(x-.035,y),(x+.035,y)],reveal=cl(p.progress*1.6-.6))
    p.path([(-.07,.49),(-.07,.33),(.07,.33),(.07,.49)],reveal=cl(p.progress*2-1))


def _pipe(p):
    p.path([(-.5,.33),(.10,.33),(.10,-.34),(.5,-.34)])
    p.path([(-.5,.47),(.24,.47),(.24,-.20),(.5,-.20)])
    p.path([(-.36,.25),(-.36,.55)],alpha=.55)
    p.path([(.31,-.42),(.31,-.12)],alpha=.55)


def _flow(p):
    # Particles fade at the endpoints; wrapping introduces no hard appearance.
    path=_curve((-.5,.36),(.15,.36),(-.15,-.36),(.5,-.36))
    p.path(path,alpha=.3)
    # Visible beads are illustrative flow, never a data counter.
    for i in range(4):
        q=(p.phase*.22*p.activity+i/4)%1
        at=q*(len(path)-1); lo=min(int(at),len(path)-2)
        pos=lerp(path[lo],path[lo+1],at-lo)
        p.circle(pos,.026,alpha=math.sin(math.pi*q)**2*p.progress,fill=1,reveal=1)


def _sun(p):
    p.circle((0,0),.23)
    for i in range(8):
        angle=i*math.tau/8
        length=.46+.015*math.sin(p.phase*1.8+i*.4)*p.activity
        p.path([(.33*math.cos(angle),.33*math.sin(angle)),
                (length*math.cos(angle),length*math.sin(angle))],reveal=cl(p.progress*1.5-.5))


def _book(p):
    # Open leaves: activity turns the right leaf about the spine, no camera zoom.
    turn=(1-math.cos(p.phase*1.4))*.5*p.activity
    p.path([(0,-.23),(-.43,-.37),(-.43,.32),(0,.46),(.43,.32),(.43,-.37),(0,-.23),(0,.46)])
    p.path([(0,.46),(.43*(1-2*turn),.32),( .43*(1-2*turn),-.37),(0,-.23)],alpha=.6)
    p.path([(-.34,-.11),(-.10,-.03)],alpha=.4)
    p.path([(-.34,.04),(-.10,.12)],alpha=.4)


def _road(p):
    p.path([(-.25,.5),(-.25,-.5)])
    p.path([(.25,.5),(.25,-.5)])
    # Dash opacity reaches zero at wrap boundaries.
    for i in range(5):
        q=(i/5+p.phase*.17*p.activity)%1
        y=.5-q
        p.path([(0,y),(0,max(-.5,y-.10))],alpha=math.sin(math.pi*q)**2,
               reveal=p.progress)


# The verbs and misuse notes are part of the discoverable API, not a taste score.
_SPECS = {
    'person': (_person,'human',['stand','walk'],'Right-facing side view; fixed-length limbs and a stance/return gait.','Sync phase to distance/(0.64*size) for travel; do not use as a front-view walker.'),
    'people': (_people,'human',['gather','walk'],'Five illustrative people with staggered gait.','Five figures are not automatically a measured share.'),
    'flame': (_flame,'environment',['ignite','sway'],'A bounded flame contour; reveal then let its tip move.','Not evidence of temperature, pollution, or causation.'),
    'smoke': (_smoke,'environment',['rise','drift'],'Three restrained drifting wisps.','Do not decorate every industrial scene with unverified emissions.'),
    'drop': (_drop,'resource',['form','fall'],'A droplet outline; direct its travel in the scene.','Oil and water require an explicit label or context.'),
    'tree': (_tree,'environment',['grow','sway'],'Trunk first, canopy second, small local sway.','Growth is illustration unless tied to a measured quantity.'),
    'sprout': (_sprout,'environment',['grow','unfold'],'Stem draws upward before two leaves unfold.','Not a quantitative crop-yield chart.'),
    'house': (_house,'place',['build','shelter'],'Roof, walls, then door.','Do not swap symbols merely because the caption mentions housing.'),
    'building': (_building,'place',['build','open'],'Outline builds before windows and entrance.','Use context to distinguish an office, school, or institution.'),
    'pipe': (_pipe,'infrastructure',['connect','draw'],'Two consistent elbow rails and collars.','The structure alone does not establish flow direction.'),
    'flow': (_flow,'infrastructure',['flow','transfer'],'Four beads follow one curved path, fading at endpoints.','Illustrative beads have no implied volume or exchange rate.'),
    'sun': (_sun,'environment',['radiate','warm'],'Disk draws before eight gently moving rays.','A sun is not a thermometer or a causal heat claim.'),
    'book': (_book,'service',['open','turn'],'An open book with a leaf turning about its spine.','Page turning is support; access or learning needs a directed action.'),
    'road': (_road,'infrastructure',['draw','travel'],'Fixed rails and drifting dashed lane markings.','This is a road, not a default chart axis.'),
}


def element_catalog() -> list[dict]:
    """JSON-safe entries shared by CLI and MCP; names are draw_element names."""
    return [dict(name=name,category=category,verbs=list(verbs),meaning=meaning,avoid=avoid,
                 usage=f'draw_element(ctx, "{name}", center=(513, 780), size=120, progress=appear, phase=u, activity=0.3)')
            for name,(_,category,verbs,meaning,avoid) in _SPECS.items()]


def draw_element(ctx, name: str, *, center=(513,780), size=120, progress=1,
                 phase=0, activity=0, alpha=1, col=None) -> None:
    """Draw one composed element using Ctx only.

    center/size use design pixels (1080x1920), independent of output profile.
    size is a nominal bounding square; pipe collars extend to 0.55*size.
    progress is a draw-on fraction, phase is absolute seconds, activity is the
    amount of local cycling. All bounded controls are in [0,1]. White by default.
    Set col=ctx.theme.green only for the scene's single measured quantity.
    This function does not move the whole object or alter the scene clock.
    """
    if name not in _SPECS:
        raise GilvyError(f'unknown visual element {name!r}; use element_catalog()')
    try:
        finite = len(center)==2 and all(math.isfinite(v) for v in (*center,size,progress,phase,activity,alpha))
    except (TypeError,ValueError):
        finite = False
    if not finite or size <= 0:
        raise GilvyError('element center, size, and controls must be finite; size must be > 0')
    if any(not 0 <= v <= 1 for v in (progress,activity,alpha)):
        raise GilvyError('element progress, activity, and alpha must be in [0, 1]')
    if col is not None and (not isinstance(col,(tuple,list)) or len(col)!=3 or
                            any(type(v) is not int or not 0<=v<=255 for v in col)):
        raise GilvyError('element col must be an RGB triple of integers in [0, 255]')
    if progress==0 or alpha==0:
        return
    pen=_Pen(ctx,tuple(center),size,progress,phase,activity,alpha,col if col is not None else ctx.theme.white,
             smooth=name in ('person','flame','drop'))
    _SPECS[name][0](pen)


def motion_reference_notes() -> str:
    """Packaged visual vocabulary and the approved Bojonegoro directing study."""
    from pathlib import Path
    return Path(__file__).with_name("MOTION_REFERENCE.md").read_text(encoding="utf-8")
