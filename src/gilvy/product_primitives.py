"""General product drawing tools, independent of any application/UI template."""
from functools import lru_cache
import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter

from gilvy.errors import GilvyError
from gilvy.theme import bundled_fonts


@lru_cache(maxsize=128)
def typeface(path, size, weight):
    path = path or str(bundled_fonts() / f'Poppins-{weight}.ttf')
    try:
        return ImageFont.truetype(path, max(1, round(size)))
    except (OSError, ValueError) as exc:
        raise GilvyError(f'could not load product font: {path}') from exc


def counter_text(node, value):
    # An explicit decimal separator avoids process-locale-dependent renders.
    digits = node.get('decimals', 0)
    result = f'{value:.{digits}f}'
    if node.get('decimal_separator', '.') == ',':
        result = result.replace('.', ',')
    return node.get('prefix', '') + result + node.get('suffix', '')


def text_layout(node, full):
    """Measure full content with final font, including actual glyph ink bounds."""
    w, h = node['width'], node['height']
    size = round(node.get('size', 48))
    pad, spacing = node.get('padding', 0), node.get('letter_spacing', 0)
    policy = node.get('overflow', 'clip')
    def calculate(size):
        face = typeface(node.get('font'), size, node.get('weight', 'Regular'))
        def length(line):
            return face.getlength(line)+max(0,len(line)-1)*spacing
        lines = full.split('\n')
        if policy == 'wrap':
            lines = []
            for paragraph in full.split('\n'):
                line = ''
                for word in paragraph.split():
                    candidate = line+' '+word if line else word
                    if line and length(candidate)>w-2*pad:
                        lines.append(line); line=word
                    else: line=candidate
                lines.append(line)
        ascent, descent = face.getmetrics()
        step = size*node.get('line_height',1.3)
        block_h = ascent+descent+step*(len(lines)-1)
        top = {'top':pad,'center':(h-block_h)/2,'bottom':h-pad-block_h}[node.get('valign','center')]
        first = node.get('baseline',top+ascent)
        rows=[];fits=len(lines)<=node.get('max_lines',100)
        for i,line in enumerate(lines):
            width=length(line)
            x={'left':pad,'center':(w-width)/2,'right':w-pad-width}[node.get('align','center')]
            y=first+i*step
            if spacing and line:
                boxes=[]
                for j,ch in enumerate(line):
                    advance=face.getlength(line[:j+1])-face.getlength(ch)+j*spacing
                    box=face.getbbox(ch,anchor='ls')
                    boxes.append((x+advance+box[0],y+box[1],x+advance+box[2],y+box[3]))
                ink=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
            else:
                box=face.getbbox(line,anchor='ls')
                ink=[x+box[0],y+box[1],x+box[2],y+box[3]]
            if line and (x<pad or x+width>w-pad or ink[0]<pad or ink[2]>w-pad or ink[1]<pad or ink[3]>h-pad):
                fits=False
            rows.append({'text':line,'x':x,'baseline':y,'width':width,'ink':ink})
        return face,rows,fits
    face,rows,fits=calculate(size)
    if policy=='fit' and not fits:
        # Fit is explicitly requested. Never change legacy/clip text sizing.
        low=max(1,math.ceil(node.get('min_size',1))); high=size-1; best=None
        while low<=high:
            mid=(low+high)//2
            trial=calculate(mid)
            if trial[2]:best=(mid,trial);low=mid+1
            else:high=mid-1
        if best is not None:size,(face,rows,fits)=best
    if policy!='clip' and not fits:
        raise GilvyError(f"text overflows layer {node.get('id','')}: {policy} cannot satisfy bounds/max_lines/min_size")
    return face, {'size':size,'lines':rows,'fits':fits,'overflow':policy}


def text_plane(node, value=None, progress=1):
    full=counter_text(node,value) if value is not None else node.get('text','')
    face,layout=text_layout(node,full)
    im=Image.new('RGBA',(node['width'],node['height']));draw=ImageDraw.Draw(im)
    # Reveal uses final line layout, retaining spacing as content appears.
    joined='\n'.join(row['text'] for row in layout['lines'])
    limit=len(joined)
    if node.get('reveal')=='characters':limit=int(limit*progress+1e-8)
    elif node.get('reveal')=='words':
        words=list(re.finditer(r'\S+',joined));count=int(len(words)*progress+1e-8)
        limit=words[count-1].end() if count else 0
    offset=0;spacing=node.get('letter_spacing',0)
    for row in layout['lines']:
        part=row['text'][:max(0,limit-offset)];offset+=len(row['text'])+1
        x,y=row['x'],row['baseline']
        if not spacing:
            draw.text((x,y),part,font=face,fill=node.get('color','#101e2f'),anchor='ls')
        else:
            for j,ch in enumerate(part):
                advance=face.getlength(part[:j+1])-face.getlength(ch)+j*spacing
                draw.text((x+advance,y),ch,font=face,fill=node.get('color','#101e2f'),anchor='ls')
    return im


def path_points(commands):
    """Flatten M/L/Q/C/Z commands into independently stroked contours."""
    contours=[]; points=[]; current=(0,0)
    for cmd in commands:
        op=cmd[0]
        if op == 'M':
            if points: contours.append(points)
            current=tuple(cmd[1:]); points=[current]
        elif op == 'L':
            current=tuple(cmd[1:]); points.append(current)
        elif op in ('Q', 'C'):
            p0=np.array(current, float); end=np.array(cmd[-2:], float)
            for t in np.linspace(0,1,33)[1:]:
                if op == 'Q':
                    p=(1-t)**2*p0+2*(1-t)*t*np.array(cmd[1:3])+t*t*end
                else:
                    p=(1-t)**3*p0+3*(1-t)**2*t*np.array(cmd[1:3])+3*(1-t)*t*t*np.array(cmd[3:5])+t**3*end
                points.append(tuple(p))
            current=tuple(end)
        else:
            points.append(points[0]); current=points[0]
    if points: contours.append(points)
    return contours


def shape_plane(node, progress):
    w,h=node['width'],node['height']; aa=2
    im=Image.new('RGBA',(w*aa,h*aa)); d=ImageDraw.Draw(im)
    fill=node.get('fill'); stroke=node.get('stroke', node.get('color', '#101e2f'))
    sw=max(1,round(node.get('stroke_width',1)*aa))
    if node['type'] == 'ellipse':
        d.ellipse((sw/2,sw/2,w*aa-1-sw/2,h*aa-1-sw/2),fill=fill,outline=stroke,width=sw)
    else:
        contours=path_points(node['commands'])
        total=sum(math.dist(a,b) for pts in contours for a,b in zip(pts,pts[1:]))
        remaining=total*progress
        for pts in contours:
            scaled=[(x*aa,y*aa) for x,y in pts]
            if fill and len(pts)>2 and pts[0] == pts[-1]: d.polygon(scaled,fill=fill)
            for a,b in zip(pts,pts[1:]):
                distance=math.dist(a,b)
                if remaining<=0:break
                ratio=min(1,remaining/max(distance,1e-9))
                end=(a[0]+(b[0]-a[0])*ratio,a[1]+(b[1]-a[1])*ratio)
                d.line((a[0]*aa,a[1]*aa,end[0]*aa,end[1]*aa),fill=stroke,width=sw)
                remaining-=distance
    return im.resize((w,h),Image.Resampling.LANCZOS)


def clip_plane(image, state):
    """Clip in local coordinates before projection; child text is never scaled."""
    if all(state[k] == v for k,v in [('clip_x',0),('clip_y',0),('clip_width',1),('clip_height',1),('clip_radius',0)]):
        return image
    w,h=image.size; x=state['clip_x']*w; y=state['clip_y']*h
    right=min(w,x+state['clip_width']*w); bottom=min(h,y+state['clip_height']*h)
    mask=Image.new('L',image.size)
    if right-x>=1 and bottom-y>=1:
        ImageDraw.Draw(mask).rounded_rectangle((x,y,right-1,bottom-1),radius=state['clip_radius'],fill=255)
    result=image.copy();result.putalpha(ImageChops.multiply(image.getchannel('A'),mask));return result


def filter_plane(image, radius=0, length=0, angle=0):
    # Filter premultiplied channels: transparent black must not darken colored edges.
    premul=image.convert('RGBa')
    if radius:premul=premul.filter(ImageFilter.GaussianBlur(radius))
    if length:
        acc=np.zeros((image.height,image.width,4),np.float32)
        steps=min(65,max(3,math.ceil(length)+1))
        for offset in np.linspace(-length/2,length/2,steps):
            dx=offset*math.cos(math.radians(angle));dy=offset*math.sin(math.radians(angle))
            shifted=premul.transform(image.size,Image.Transform.AFFINE,(1,0,dx,0,1,dy),Image.Resampling.BICUBIC)
            acc+=np.asarray(shifted,dtype=np.float32)/steps
        premul=Image.fromarray(np.clip(np.rint(acc),0,255).astype('uint8'),'RGBa')
    return premul.convert('RGBA')


def average_planes(images):
    """Average transparent motion samples in premultiplied linear light."""
    acc=np.zeros((images[0].height,images[0].width,4),np.float32)
    for im in images:
        a=np.asarray(im,dtype=np.float32)/255
        rgb=np.where(a[:,:,:3]<=.04045,a[:,:,:3]/12.92,((a[:,:,:3]+.055)/1.055)**2.4)
        acc[:,:,:3]+=rgb*a[:,:,3:4]/len(images);acc[:,:,3:]+=a[:,:,3:]/len(images)
    alpha=acc[:,:,3:];rgb=np.divide(acc[:,:,:3],alpha,out=np.zeros_like(acc[:,:,:3]),where=alpha>0)
    rgb=np.where(rgb<=.0031308,rgb*12.92,1.055*np.maximum(rgb,0)**(1/2.4)-.055)
    return Image.fromarray(np.clip(np.rint(np.concatenate([rgb,alpha],axis=2)*255),0,255).astype('uint8'))
