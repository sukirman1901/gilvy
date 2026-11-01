def SC(c,i,u,D):
    C0=(CX,780)
    if i==0:
        a=eo(R(u,0,0.6)); c.line((180,780),(846,780),a*0.5,w=1.2)
        x=lerp((180,0),(600,0),eio(R(u,0.3,D-0.3)))[0]; c.dot((x,780),7,a); c.line((560,750),(560,810),a*0.6,w=1.4); c.label((560,840),"jan 1",a*0.6,sz=22)
    elif i==1:
        for d in range(14):
            r,col=divmod(d,7); x=213+col*100; y=700+r*100; a=eo(R(u,d*0.05,0.4+d*0.05))
            c.rect(x-38,y-38,x+38,y+38,a*0.5,w=1); c.check((x,y),a,eio(R(u,0.6+d*0.06,0.9+d*0.06)),sz=8)
    elif i==2:
        for k in range(3):
            x=300+k*213; y=860; a=eo(R(u,k*0.15,0.5+k*0.15))
            c.poly([(x-60,y-90),(x-52,y+80),(x+52,y+80),(x+60,y-90)],a,w=1.5); c.fillrect(x-52,y-80,x+52,y+78,eio(R(u,0.5,1.6))*(0.5+0.15*k),a,k=0.2)
    elif i==3:
        for k,h in enumerate([200,150,110,70]):
            x=270+k*162; a=eo(R(u,k*0.1,0.5+k*0.1)); hl=k==0
            c.rect(x-40,1000-h,x+40,1000,a*(1 if hl else 0.35),w=1.4)
        a=eo(R(u,0.8,1.3)); c.line((270,690),(270,770),a,w=2); c.poly([(255,755),(270,775),(285,755)],a,w=2); c.glow((270,900),80,a*0.5)
    elif i==4:
        m=eio(R(u,0.2,1.8)); pts=[(300,700),(726,700),(300,960),(726,960)]
        for k,p in enumerate(pts):
            xy=lerp(p,C0,m); a=1-m*0.8
            if k==0: c.coin(xy,a,r=20)
            elif k==1: c.poly([(xy[0]-24,xy[1]-24),(xy[0]-20,xy[1]+24),(xy[0]+20,xy[1]+24),(xy[0]+24,xy[1]-24)],a,w=1.4)
            elif k==2: c.rect(xy[0]-40,xy[1]-8,xy[0]+40,xy[1]+8,a,w=1.4)
            else: c.circ(xy,22,a,w=1.4)
        c.glow(C0,140*m,m*0.7); c.circ(C0,55,m,w=2)
    else:
        a=eo(R(u,0,0.6)); c.glow(C0,150,a*0.7); c.circ(C0,55,1,w=2); c.coin(C0,a,r=22)
        coins_flow(c,(CX,520),C0,u,0.4,D-0.4,3,stag=0.5,trav=1.0)
