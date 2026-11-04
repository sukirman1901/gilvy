"""Vocabulary specimen: draw-on, secondary parts, then restrained local life.

This catalog intentionally compares multiple components. An editorial episode
should choose one hero and a relationship, not reuse the specimen grid.
"""
from gilvy.elements import draw_element
from gilvy.easing import R,eo

PAGES = [
    [('person','manusia'),('people','warga'),('house','rumah'),('building','gedung')],
    [('flame','api'),('smoke','asap'),('drop','tetes'),('flow','aliran')],
    [('tree','pohon'),('sprout','tunas'),('sun','matahari')],
    [('book','buku'),('road','jalan'),('pipe','pipa')],
]

def draw(ctx,u,duration,params):
    page=int(params['page'])
    ctx.label((513,370),f'GILVY | VISUAL VOCABULARY {page+1}/4',.7,sz=22,w='Medium')
    for i,(name,label) in enumerate(PAGES[page]):
        x=355+(i%2)*316; y=650+(i//2)*350
        appear=eo(R(u,.08+i*.10,1.4+i*.10))
        activity=.75 if name in ('person','people','book','road','flow') else .45
        draw_element(ctx,name,center=(x,y),size=140,progress=appear,
                     phase=u+i*.14,activity=activity)
        ctx.label((x,y+120),label,eo(R(u,.7+i*.10,1.5+i*.10)),sz=25)
