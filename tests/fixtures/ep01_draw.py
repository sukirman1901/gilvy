def bowl(c,xy,a,steam=0,sc=1.0,chop=1.0):
    x,y=xy; r=62*sc
    c.arc((x,y-6*sc),r,0,180,a,w=1.8)                       # bowl = lower half ring
    c.line((x-r-10*sc,y-6*sc),(x+r+10*sc,y-6*sc),a,w=1.6,k=0.9)  # rim
    c.line((x-24*sc,y+r-4*sc),(x+24*sc,y+r-4*sc),a,w=1.6,k=0.7)  # foot
    if chop>0:                                               # chopsticks hairline
        c.line((x+8*sc,y-14*sc),(x+86*sc,y-96*sc),a,p=chop,w=1.2,k=0.8); c.line((x+22*sc,y-12*sc),(x+98*sc,y-86*sc),a,p=chop,w=1.2,k=0.8)
    for j,dx in enumerate((-26,-6,14)):                      # steam rising, looping
        ph=(steam*0.45+j*0.33)%1.0
        if steam<=0: continue
        y0=y-20*sc-ph*40*sc; al=a*0.6*math.sin(math.pi*ph)
        pts=[(x+dx*sc+7*sc*math.sin(q*1.6+j+steam*1.5),y0-q*14*sc) for q in range(5)]
        c.poly(pts,al,w=1.1,k=0.7)
COLS,ROWS,SP=22,26,24; GX=CX-(COLS-1)*SP/2; GY=520
def dots(c,n_on,al,n_hi=0,fade=1.0):
    for k in range(COLS*ROWS):
        r_,q=divmod(k,COLS); xy=(GX+q*SP,GY+r_*SP)
        if k<n_hi: c.circ(xy,3.2,al,fill=1.0,col=GR)
        elif k<n_on: c.circ(xy,3.2,al,fill=1.0)
        else: c.circ(xy,2.2,al*0.18*fade,fill=1.0)
def SC(c,i,u,D):
    C0=(CX,780)
    if i==0:   # hook: bowl draws on, chopsticks slide in, steam rises
        a=eo(R(u,0,0.6)); c.glow(C0,150,a*0.55); bowl(c,C0,a,steam=u,chop=eio(R(u,0.5,1.3)))
        aa=eo(R(u,1.0,1.5)); c.money((CX,C0[1]+120),"Rp10rb",aa,sz=34,ex=False); c.text((CX,C0[1]+152),"contoh",F("Light",20),aa*0.6)
    elif i==1: # one coin drops into the bowl = one bowl
        bowl(c,C0,1,steam=u+3); p=R(u,0.3,1.3)
        if 0<p<1: c.coin((CX,420+(C0[1]-30-420)*eexp(p)),min(1,(1-p)*6),r=18)
        c.glow(C0,140,eo(R(u,1.2,1.6))*0.6*(1-eo(R(u,1.6,D))))
        aa=eo(R(u,1.2,1.7)); c.text((CX,C0[1]+120),"1 koin Rp10rb = 1 mangkok",F("Regular",22),aa*0.85)
    elif i==2: # salary ring drains into dot grid of bowls (268)
        p=eio(R(u,0.6,D-0.8)); rc=(CX,400); a=eo(R(u,0,0.5))
        c.circ(rc,44,a*0.25,w=1.2); c.circ(rc,44,a,w=2,p=1-p); c.text((CX+64,rc[1]-8),"UMK Bojonegoro",F("Regular",20),a*0.7,anchor="lm"); c.money((CX+64,rc[1]+20),"Rp2.685.983",a,sz=24,ex=False,anchor="lm")
        dots(c,int(268*p),a); c.money((CX,GY+ROWS*SP+40),f"{int(268*p)} mangkok",a*cl(p*4),sz=30,ex=False)
    elif i==3: # jakarta keeps filling to 572, bojonegoro portion stays visible
        p=eio(R(u,0.6,D-0.8)); rc=(CX,400); a=1
        c.circ(rc,44,0.25,w=1.2); c.circ(rc,44,1,w=2,p=1-p); c.text((CX+64,rc[1]-8),"UMP DKI Jakarta",F("Regular",20),0.7,anchor="lm"); c.money((CX+64,rc[1]+20),"Rp5.729.876",1,sz=24,ex=False,anchor="lm")
        dots(c,int(268+(572-268)*p),1); c.money((CX,GY+ROWS*SP+40),f"{int(268+(572-268)*p)} mangkok",1,sz=30,ex=False)
    elif i==4: # same bowl, 2x: bojonegoro share highlights green, rest stays white
        h=eio(R(u,0.3,1.3)); dots(c,572,1,n_hi=int(268*h))
        a=eo(R(u,1.2,1.7)); yb=GY+ROWS*SP+40
        c.text((GX,yb),"bojonegoro 268",F("Regular",22),a*0.85,col=GR,anchor="lm"); c.text((GX+(COLS-1)*SP,yb),"jakarta 572",F("Regular",22),a*0.85,anchor="rm")
    else:      # CTA: bowl with steam
        a=eo(R(u,0,0.6)); c.glow(C0,150,a*0.6); bowl(c,C0,a,steam=u,chop=1)
        c.label((CX,C0[1]+120),"tulis di komentar",eo(R(u,0.6,1.1))*0.7,sz=20)
