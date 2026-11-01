"""Pixel oracle. Drawing math is the proven renderer; only the font prefix and build directory are overridable."""
import numpy as np, subprocess, math, sys, os, wave
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from multiprocessing import Pool
W,H,FPS,S=1080,1920,60,2
FD=os.environ.get("GILVY_FONT_PREFIX","/usr/share/fonts/truetype/sand-box/google/Poppins/Poppins-")
_fc={}
def F(w,sz):
    k=(w,sz)
    if k not in _fc: _fc[k]=ImageFont.truetype(FD+w+".ttf",int(sz*S))
    return _fc[k]
BG=(10,10,10); WH=(236,236,236); GR=(218,255,89)  # was (43,182,115); #daff59
CX=513; PAD=0.4; LEAD=0.2; XF=0.45; MIN=2.8
def cl(x): return 0.0 if x<0 else 1.0 if x>1 else x
def eio(x): x=cl(x); return 4*x*x*x if x<.5 else 1-(-2*x+2)**3/2
def eo(x): x=cl(x); return 1-(1-x)**3
def eexp(x):
    x=cl(x)
    if x in(0,1): return x
    return 2**(20*x-10)/2 if x<.5 else (2-2**(-20*x+10))/2
def R(u,a,b): return cl((u-a)/(b-a))
def mix(c,a): a=cl(a); return tuple(int(BG[i]+(c[i]-BG[i])*a) for i in range(3))
def lerp(a,b,p): return (a[0]+(b[0]-a[0])*p,a[1]+(b[1]-a[1])*p)
class Ctx:
    def __init__(s):
        s.im=Image.new("RGB",(W*S,H*S),BG); s.d=ImageDraw.Draw(s.im)
        s.g=Image.new("L",(W//4,H//4),0); s.gd=ImageDraw.Draw(s.g)
    def line(s,a,b,al,p=1.0,w=1.6,col=WH,k=0.55):
        if al<=0 or p<=0: return
        e=lerp(a,b,p); s.d.line([a[0]*S,a[1]*S,e[0]*S,e[1]*S],fill=mix(col,al*k),width=max(1,int(w*S)))
    def poly(s,pts,al,p=1.0,w=1.6,k=0.7):
        # draw-on polyline by arclength
        if al<=0 or p<=0: return
        L=[math.dist(pts[i],pts[i+1]) for i in range(len(pts)-1)]; tot=sum(L); goal=tot*p; acc=0
        for i,l in enumerate(L):
            if acc>=goal: break
            q=min(1,(goal-acc)/l) if l else 1; s.line(pts[i],pts[i+1],al,p=q,w=w,k=k); acc+=l
    def circ(s,c,r,al,w=1.6,p=1.0,fill=None,col=WH,start=-90):
        if al<=0 or r<=0: return
        bb=[(c[0]-r)*S,(c[1]-r)*S,(c[0]+r)*S,(c[1]+r)*S]
        if fill is not None: s.d.ellipse(bb,fill=mix(col,al*fill))
        if p>=1: s.d.ellipse(bb,outline=mix(col,al),width=max(1,int(w*S)))
        elif p>0: s.d.arc(bb,start,start+360*p,fill=mix(col,al),width=max(1,int(w*S)))
    def arc(s,c,r,a0,a1,al,w=2,col=WH):
        if al<=0 or a1<=a0: return
        bb=[(c[0]-r)*S,(c[1]-r)*S,(c[0]+r)*S,(c[1]+r)*S]; s.d.arc(bb,a0,a1,fill=mix(col,al),width=max(1,int(w*S)))
    def rect(s,x0,y0,x1,y1,al,w=1.6,fill=None,p=1.0,k=0.8):
        if al<=0: return
        if fill is not None: s.d.rectangle([x0*S,y0*S,x1*S,y1*S],fill=mix(WH,al*fill))
        if w: s.poly([(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)],al,p=p,w=w,k=k)
    def glow(s,c,r,al):
        q=4; s.gd.ellipse([(c[0]-r)/q,(c[1]-r)/q,(c[0]+r)/q,(c[1]+r)/q],fill=int(90*cl(al)))
    def dot(s,c,r,al,glow=True):
        if al<=0: return
        s.circ(c,r,al,fill=1.0)
        if glow: s.glow(c,r*2.2,al)
    def text(s,xy,t,font,al,col=WH,anchor="mm"):
        if al<=0: return
        s.d.text((xy[0]*S,xy[1]*S),t,font=font,fill=mix(col,al),anchor=anchor)
    def coin(s,c,al,r=15):
        if al<=0: return
        s.circ(c,r,al,w=1.8,fill=0.10); s.text(c,"$",F("Medium",int(r*1.13)),al)
        s.gd.ellipse([(c[0]-r*1.6)/4,(c[1]-r*1.6)/4,(c[0]+r*1.6)/4,(c[1]+r*1.6)/4],fill=int(45*cl(al)))
    def bar(s,x,y,w,lvl,al,h=5,k=0.9):
        if al<=0: return
        s.d.rectangle([(x-w/2)*S,y*S,(x+w/2)*S,(y+h)*S],fill=mix(WH,al*0.15))
        if lvl>0: s.d.rectangle([(x-w/2)*S,y*S,(x-w/2+w*cl(lvl))*S,(y+h)*S],fill=mix(WH,al*k))
    def fillrect(s,x0,y0,x1,y1,lvl,al,k=0.16):
        if al<=0 or lvl<=0: return
        top=y1-(y1-y0)*cl(lvl); s.d.rectangle([x0*S,top*S,x1*S,y1*S],fill=mix(WH,al*k))
    def fillcirc(s,c,r,lvl,al):
        if al<=0 or lvl<=0: return
        m=Image.new("L",(int(2*r*S),int(2*r*S)),0); md=ImageDraw.Draw(m)
        md.ellipse([0,0,2*r*S-1,2*r*S-1],fill=int(255*0.16*al)); md.rectangle([0,0,2*r*S,int(2*r*S*(1-lvl))],fill=0)
        s.im.paste(Image.new("RGB",m.size,WH),(int((c[0]-r)*S),int((c[1]-r)*S)),m)
    def check(s,c,al,p,sz=12):
        s.poly([(c[0]-sz,c[1]),(c[0]-sz*0.3,c[1]+sz*0.7),(c[0]+sz,c[1]-sz*0.8)],al,p=p,w=2.2,k=1)
    def money(s,xy,val,al,sz=34,ex=True,anchor="mm",exdy=34):
        s.text(xy,val,F("Medium",sz),al,col=GR,anchor=anchor)
        if ex: s.text((xy[0],xy[1]+exdy),"example",F("Light",20),al*0.6,anchor=anchor)
    def label(s,xy,t,al,sz=22,w="Regular",anchor="mm"): s.text(xy,t,F(w,sz),al*0.85,anchor=anchor)
def grid(c,al=1):
    for x in range(108,920,81): c.d.line([x*S,330*S,x*S,1420*S],fill=mix(WH,al*0.05),width=1)
    for y in range(330,1421,81): c.d.line([108*S,y*S,918*S,y*S],fill=mix(WH,al*0.05),width=1)
def coins_flow(c,a,b,u,t0,t1,n,al=1,stag=0.4,trav=1.0,r=15,path=None):
    for k in range(n):
        s0=t0+k*stag
        if s0>t1: break
        p=R(u,s0,s0+trav)
        if 0<p<1: c.coin(lerp(a,b,eio(p)) if path is None else path(eio(p)),al*min(1,p*6,(1-p)*6),r=r)
def caption(c,lines,keys,u):
    wi=0
    for li,ln in enumerate(lines):
        y=1290+li*78; words=ln.split(" ")
        fonts=[F("SemiBold",52) if (w in keys) else F("Light",52) for w in words]
        sp=F("Light",52).getlength(" ")/S
        ws=[f.getlength(w)/S for f,w in zip(fonts,words)]; tot=sum(ws)+sp*(len(words)-1)
        assert tot<780 and len(words)<=5, ln
        x=CX-tot/2
        for w,f,wd in zip(words,fonts,ws):
            a=eo(R(u,LEAD+wi*0.16,LEAD+wi*0.16+0.5))
            c.text((x,y+14*(1-a)),w,f,a,col=GR if w.startswith("$") else WH,anchor="ls"); x+=wd+sp; wi+=1
class Video:
    def __init__(s,name,scenes,scene_fn,poster=None):
        s.name=name; s.sc=scenes; s.fn=scene_fn; s.dir=os.environ.get("GILVY_BUILD_DIR", f"/tmp/gilvy-oracle-build/{name}"); os.makedirs(s.dir,exist_ok=True)
        s.poster=poster
    def tts(s):
        for i,sc in enumerate(s.sc):
            f=f"{s.dir}/vo{i+1}.mp3"; txtf=f+".txt"
            if os.path.exists(f) and os.path.getsize(f)>2000 and os.path.exists(txtf) and open(txtf).read()==sc["vo"]: continue
            for _ in range(5):
                r=subprocess.run(["edge-tts","--voice","en-US-AndrewNeural","--rate=-8%","--text",sc["vo"],"--write-media",f],capture_output=True)
                if subprocess.run(["ffprobe","-v","error",f],capture_output=True).returncode==0 and os.path.getsize(f)>2000: break
                import time; time.sleep(3)
            open(txtf,"w").write(sc["vo"])
        s.vod=[float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f"{s.dir}/vo{i+1}.mp3"],capture_output=True,text=True).stdout) for i in range(len(s.sc))]
        s.durs=[max(s.sc[i].get("min",MIN),d+PAD+LEAD) for i,d in enumerate(s.vod)]
        s.starts=np.cumsum([0]+s.durs); s.T=float(s.starts[-1])
    def scene(s,i,u):
        c=Ctx(); grid(c); s.fn(c,i,u,s.durs[i]); caption(c,s.sc[i]["text"],s.sc[i].get("key",[]),u); return c
    def compose(s,c):
        im=c.im.resize((W,H),Image.LANCZOS); g=c.g.filter(ImageFilter.GaussianBlur(5)).resize((W,H),Image.BILINEAR)
        return np.clip(np.asarray(im,np.float32)+np.asarray(g,np.float32)[...,None]*0.55,0,255)
    def frame(s,n):
        t=n/FPS; i=min(int(np.searchsorted(s.starts,t,side='right')-1),len(s.durs)-1); u=t-s.starts[i]
        A=s.compose(s.scene(i,u))
        if i+1<len(s.durs) and u>s.durs[i]-XF:
            k=eio((u-(s.durs[i]-XF))/XF); A=A*(1-k)+s.compose(s.scene(i+1,u-s.durs[i]))*k
        if t<0.3: A=A*cl(t/0.3)+np.array(BG)*(1-cl(t/0.3))
        if t>s.T-0.6: q=cl((s.T-t)/0.6); A=A*q+np.array(BG)*(1-q)
        return A.astype(np.uint8).tobytes()
    def still(s,t,path): Image.frombytes("RGB",(W,H),s.frame(int(t*FPS))).save(path)
    def render(s):
        N=int(round(s.T*FPS)); vid=f"{s.dir}/vid.mp4"
        p=subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","17","-preset","medium",vid],stdin=subprocess.PIPE)
        with Pool(8) as pool:
            for b in pool.imap(s.frame,range(N),chunksize=8): p.stdin.write(b)
        p.stdin.close(); p.wait()
    def audio(s):
        sr=48000; t=np.arange(int(sr*s.T))/sr; a=np.zeros_like(t)
        for f,amp in [(110,.5),(164.81,.32),(220,.28),(277.18,.16),(329.63,.14)]:
            a+=amp*np.sin(2*np.pi*f*t)*(0.65+0.35*np.sin(2*np.pi*0.08*t+f))
        a=a/np.abs(a).max()*0.25*np.minimum(1,t/2)*np.minimum(1,(s.T-t)/2.5); st=np.stack([a,np.roll(a,400)],1)
        with wave.open(f"{s.dir}/pad.wav","wb") as w: w.setnchannels(2);w.setsampwidth(2);w.setframerate(sr);w.writeframes((st*32767).astype(np.int16).tobytes())
        n=len(s.sc); ins=[]; fl=""
        for i in range(n):
            d=int((s.starts[i]+LEAD)*1000); ins+=["-i",f"{s.dir}/vo{i+1}.mp3"]; fl+=f"[{i+1}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={d}|{d}[v{i}];"
        fl+="".join(f"[v{i}]" for i in range(n))+f"amix=inputs={n}:normalize=0,apad,asplit[vo][sc];[0:a][sc]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck];[duck][vo]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.9[out]"
        subprocess.run(["ffmpeg","-v","error","-y","-i",f"{s.dir}/pad.wav"]+ins+["-filter_complex",fl,"-map","[out]","-t",f"{s.T:.3f}",f"{s.dir}/mix.wav"],check=True)
        out=f"/tmp/gilvy-oracle-out/{s.name}.mp4"
        subprocess.run(["ffmpeg","-v","error","-y","-i",f"{s.dir}/vid.mp4","-i",f"{s.dir}/mix.wav","-c:v","copy","-c:a","aac","-b:a","160k","-t",f"{s.T:.3f}","-movflags","+faststart",out],check=True)
        return out
    def verify(s,out):
        info=subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_name,width,height,r_frame_rate,duration","-of","compact",out],capture_output=True,text=True).stdout
        mids=[s.starts[i]+s.durs[i]*0.7 for i in range(len(s.durs))]
        for k,t in enumerate(mids): subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{t:.2f}","-i",out,"-frames:v","1","-vf","scale=270:-1",f"{s.dir}/m{k}.png"])
        subprocess.run(["ffmpeg","-v","error","-y"]+sum([["-i",f"{s.dir}/m{k}.png"] for k in range(len(mids))],[])+["-filter_complex",f"hstack={len(mids)}",f"{s.dir}/sheet.png"])
        raw=subprocess.run(f"ffmpeg -v error -i {out} -vf scale=270:480,format=gray -f rawvideo -",shell=True,capture_output=True).stdout
        a=np.frombuffer(raw,np.uint8).reshape(-1,480,270).astype(np.float32); d=np.abs(np.diff(a,axis=0)).mean((1,2))
        # VO-only onset check
        ins=[];fl=""
        for i in range(len(s.sc)):
            dd=int((s.starts[i]+LEAD)*1000); ins+=["-i",f"{s.dir}/vo{i+1}.mp3"]; fl+=f"[{i}:a]adelay={dd}|{dd}[v{i}];"
        fl+="".join(f"[v{i}]" for i in range(len(s.sc)))+f"amix=inputs={len(s.sc)}:normalize=0"
        subprocess.run(["ffmpeg","-v","error","-y"]+ins+["-filter_complex",fl,f"{s.dir}/voonly.wav"])
        sd=subprocess.run(["ffmpeg","-i",f"{s.dir}/voonly.wav","-af","silencedetect=n=-40dB:d=0.3","-f","null","-"],capture_output=True,text=True).stderr
        import re; ends=[float(x) for x in re.findall(r"silence_end: ([\d.]+)",sd)]
        ons=[min([e for e in ends if e>=s.starts[i]-0.05] or [-1]) for i in range(len(s.sc))]
        if s.poster is not None: subprocess.run(["ffmpeg","-v","error","-y","-ss",f"{s.starts[s.poster]+s.durs[s.poster]*0.75:.2f}","-i",out,"-frames:v","1",f"/tmp/gilvy-oracle-out/{s.name}_poster.png"])
        print(info); print("T",round(s.T,2),"maxdiff",round(float(d.max()),2),"mean",round(float(d.mean()),3))
        print("scene starts",[round(x,2) for x in s.starts[:-1]]); print("vo onsets",[round(x,2) for x in ons])
    def main(s):
        s.tts()
        if len(sys.argv)>1 and sys.argv[1]=="stills":
            for k,tt in enumerate(sys.argv[2:]): s.still(float(tt),f"{s.dir}/st{k}.png")
            print("T",s.T,[round(x,2) for x in s.starts]); return
        s.render(); out=s.audio(); s.verify(out)
