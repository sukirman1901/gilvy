"""Directed continuation. Each chart retains its own unit and denominator.

Bumi: reservoir line feeds a rising droplet; visible resource, not household pay.
Pisah: same workers settle below; a separate public-funds ring draws above.
Dana: the ring counts reported DBH, not a conversion from worker dots.
Manfaat: that ring branches to services; illustration, not measured allocation.
Kemajuan: separate zero-based poverty bars; no causal claim about DBH.
Tanya: the region's circle opens around people; the question becomes human scale.
Sources and exact definitions live in SOURCES.md. Historical snapshot, 2025.
"""
import math
from gilvy.easing import R,eio,eo,lerp
def classified_position(i):
    if i < 45:
        row,col=divmod(i,5)
        return (310+col*34,644+row*34)
    row,col=divmod(i-45,5)
    return (582+col*34,610+row*34)
C=(513,780)

def label(ctx,xy,t,a=1,sz=24,w='Regular'):
    ctx.label(xy,t,a,sz=sz,w=w)

def head(ctx,t,a=1):
    label(ctx,(513,370),t,a*.7,22,'Medium')

def foot(ctx,a,b='',alpha=1):
    label(ctx,(513,1480),a,alpha*.8,23)
    if b: label(ctx,(513,1518),b,alpha*.65,21)

def people(ctx,y=1040,a=1):
    for i in range(15):
        x=303+i*30
        ctx.circ((x,y),4.5,a,fill=.8)

def ring(ctx,center=C,r=105,a=1,p=1):
    ctx.circ(center,r,a*.8,w=1.6,p=p)

def draw(ctx,u,duration,params):
    phase=params['phase']
    if phase=='bumi':
        a=eo(R(u,0,.6)); head(ctx,'BOJONEGORO | POTRET 2025',a)
        ctx.line((295,920),(731,920),a*.4,p=eo(R(u,.2,1.3)))
        # Quiet reservoir stratum, a drawn well, then one drop rises.
        ctx.poly([(335,990),(400,982),(470,990),(545,980),(620,990),(690,984)],a*.25,p=eo(R(u,.45,1.6)))
        ctx.line((513,982),(513,660),a*.65,p=eio(R(u,.8,2.5)))
        rise=eio(R(u,1.6,3.35)); y=lerp((0,910),(0,650),rise)[1]
        da=eo(R(u,1.5,1.9))
        ctx.poly([(513,y-23),(499,y+1),(500,y+14),(513,y+20),(526,y+14),(527,y+1),(513,y-23)],da,w=1.8)
        label(ctx,(513,1090),'hasil bumi',eo(R(u,2.5,3.3))*.8,25)
    elif phase=='pisah':
        move=eio(R(u,.15,2.9)); head(ctx,'DUA JALUR YANG BERBEDA')
        for i in range(100):
            dest=(315+(i%20)*21,990+(i//20)*22)
            pos=lerp(classified_position(i),dest,move)
            ctx.circ(pos,5.5-1.5*move,.7,fill=.8)
        label(ctx,(513,1150),'pekerjaan warga',eo(R(u,1.8,2.7))*.8,24)
        ring(ctx,(513,680),100,eo(R(u,.6,1.4)),eio(R(u,.6,3.2)))
        label(ctx,(513,680),'Rp',eo(R(u,1.5,2.4)),40,'Medium')
        label(ctx,(513,830),'penerimaan daerah',eo(R(u,2.4,3.3))*.85,24)
    elif phase=='dana':
        head(ctx,'DANA BAGI HASIL MIGAS | 2025')
        q=eio(R(u,.45,3.8))
        ring(ctx,(513,680),100,1,.999)
        # Ring opens into a measuring rail; money has its own unit.
        f=eio(R(u,.2,2.7))
        ctx.line((293,930),(733,930),.35,p=f)
        x=293+440*q
        ctx.line((293,930),(x,930),1,w=5,col=ctx.theme.green,k=1)
        ctx.circ((x,930),5,1,fill=1,col=ctx.theme.green)
        ctx.text((513,665),'Rp '+f'{1.94*q:.2f}'.replace('.',','),ctx.font('Medium',49),1)
        label(ctx,(513,723),'triliun',1,28)
        label(ctx,(293,985),'0',.65,22)
        label(ctx,(733,985),'1,94',.8,22)
        label(ctx,(513,1080),'diterima pemerintah daerah',eo(R(u,2.8,3.8)),25)
        foot(ctx,'Sumber: Pemkab Bojonegoro','Realisasi DBH migas 2025')
    elif phase=='manfaat':
        head(ctx,'DARI PENERIMAAN KE MANFAAT')
        ring(ctx,(513,600),75,1)
        label(ctx,(513,600),'daerah',1,26,'Medium')
        branch=eio(R(u,.3,3.5))
        ctx.line((513,675),(513,780),.7,p=branch)
        ctx.line((303,780),(723,780),.6,p=branch)
        for i,(x,t) in enumerate(((303,'sekolah'),(513,'kesehatan'),(723,'jalan'))):
            f=eo(R(u,.8+i*.15,2.7+i*.15))
            ctx.line((x,780),(x,865),.65,p=f)
            ring(ctx,(x,900),34,f,p=f)
            label(ctx,(x,974),t,f,23)
        # No distribution percentages: qualitative channels named by Pemkab.
        a=eo(R(u,3.0,4.0)); people(ctx,1100,a)
        ctx.line((303,1035),(723,1035),a*.35,p=eo(R(u,3.0,4.7)))
        foot(ctx,'Jalur manfaat, bukan pembagian nominal','Sumber: Pemkab Bojonegoro')
    elif phase=='kemajuan':
        head(ctx,'PENDUDUK MISKIN | BOJONEGORO')
        # Honest zero baseline: a 0.20 percentage-point decline is small.
        q=eio(R(u,.6,3.8)); current=11.69-.2*q
        baseline=1040; scale=28
        ctx.line((293,baseline),(733,baseline),.45)
        for v in (0,5,10,15):
            y=baseline-v*scale
            label(ctx,(258,y),str(v),.55,20)
            ctx.line((283,y),(733,y),.15)
        x1,x2=390,636
        top1=baseline-11.69*scale; top2=baseline-current*scale
        ctx.line((x1,baseline),(x1,top1),.7,w=9,k=1)
        ctx.line((x2,baseline),(x2,top2),1,w=9,col=ctx.theme.green,k=1)
        ctx.line((x1,top1),(x2,top2),.4,p=q)
        label(ctx,(x1,top1-48),'11,69%',1,35,'Medium')
        label(ctx,(x2,top2-48),f'{current:.2f}%'.replace('.',','),1,35,'Medium')
        label(ctx,(x1,1100),'2024',1,25)
        label(ctx,(x2,1100),'2025',1,25)
        foot(ctx,'BPS | Maret 2024–Maret 2025','Turun 0,20 poin persentase')
    elif phase=='tanya':
        a=eo(R(u,0,.6)); head(ctx,'BOJONEGORO | POTRET 2025',a)
        q=eio(R(u,.4,4.0))
        # Regional outline expands to enclose the people, without inventing a share.
        radius=105+85*q
        ring(ctx,(513,780),radius,a,p=eo(R(u,0,1.0)))
        for i in range(21):
            row,col=divmod(i,7)
            dest=(423+col*30,747+row*33)
            pos=lerp((513,780),dest,q)
            ctx.circ(pos,4.5,a*eo(R(u,.6,1.6)),fill=.9)
        label(ctx,(513,1058),'ukur dari hidup warga',eo(R(u,3.0,4.3)),26)
        foot(ctx,'Kekayaan alam → manfaat publik','Pekerjaan, layanan, dan kesejahteraan')
