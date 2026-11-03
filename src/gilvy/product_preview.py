"""Local frame viewer and MCP still inspector, both backed by ProductFilm."""
from collections import OrderedDict
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

from gilvy.errors import GilvyError
from gilvy.product import load_product
from gilvy.timeline import describe_timeline


class PreviewSession:
    def __init__(self, spec_path, cache_bytes=16*1024*1024):
        self.path = Path(spec_path).expanduser().resolve()
        self.limit = cache_bytes
        self.cache = OrderedDict()
        self.bytes = 0
        self.film = None
        self.signature = None
        self.refresh()

    def fingerprint(self):
        paths = {self.path, *Path(__file__).parent.glob("*.py"),
                 *Path(__file__).with_name("fonts").glob("*.ttf")}
        if self.film:
            def walk(nodes):
                for node in nodes:
                    for key in ("src", "font"):
                        if key in node: paths.add(Path(node[key]))
                    if node["type"] == "group": walk(node["children"])
            walk(self.film.spec["layers"])
        digest = hashlib.sha256()
        for path in sorted(paths):
            digest.update(str(path).encode())
            try:
                digest.update(path.read_bytes())
            except FileNotFoundError:
                digest.update(b"missing")
        return digest.hexdigest()

    def refresh(self):
        current = self.fingerprint()
        if current != self.signature:
            # A failed reload must never fall back silently to the old scene.
            from gilvy.product_primitives import typeface
            from gilvy.product_ui import font
            from gilvy.product_design import _font, _part_cached
            typeface.cache_clear()
            font.cache_clear()
            _font.cache_clear()
            _part_cached.cache_clear()
            film = load_product(self.path)
            self.film = film
            self.signature = self.fingerprint()
            self.cache.clear()
            self.bytes = 0

    def metadata(self):
        self.refresh()
        return {**describe_timeline(self.film), "size": self.film.size,
                "revision": self.signature, "audio_preview": False,
                "quality": "native kernel; optional downscaled display"}

    def png(self, index, width=None):
        self.refresh()
        if width is not None and (type(width) is not int or not 80 <= width <= 1920):
            raise GilvyError("preview width must be 80..1920")
        key = (index, width)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        image = self.film.frame_at(index)
        if width is not None and width < image.width:
            image = image.resize((width, round(width*image.height/image.width)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        data = buf.getvalue()
        if len(data) <= self.limit:
            while self.cache and self.bytes+len(data) > self.limit:
                self.bytes -= len(self.cache.popitem(last=False)[1])
            self.cache[key] = data
            self.bytes += len(data)
        return data


def inspect_product_frame(spec_path, frame, output):
    session = PreviewSession(spec_path)
    dest = Path(output).expanduser().resolve()
    if dest.exists() or dest.suffix.lower() != ".png":
        raise GilvyError("frame output must be a new .png path")
    data = session.png(frame)
    inspection = session.film.inspect(frame)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"image": str(dest), "quality": "native", **inspection,
            "timeline": describe_timeline(session.film)}


VIEWER = """<!doctype html><meta charset=utf-8><title>Gilvy frame inspector</title>
<style>body{margin:24px;background:#101113;color:#eee;font:14px system-ui}main{display:grid;grid-template-columns:minmax(240px,2fr) minmax(240px,1fr);gap:24px}img{width:100%;max-height:75vh;object-fit:contain;background:#000}input{width:100%}button,select{padding:8px;margin:8px 8px 8px 0}pre{white-space:pre-wrap;max-height:75vh;overflow:auto}#error{color:#ff9d9d}@media(max-width:700px){main{display:block}}</style>
<h1>Gilvy frame inspector</h1><p>Silent frame preview · same native renderer as export · Refresh reloads source and assets.</p>
<p id=error role=alert></p><main><section><img id=picture alt="Composition frame"><input id=seek type=range min=0 value=0 step=1 aria-label="Frame"><div><button id=prev>Previous</button><button id=next>Next</button><button id=refresh>Refresh</button><label><input id=native type=checkbox style="width:auto">Native</label><span id=position></span></div></section><section><label>Layer <select id=layers></select></label><pre id=detail></pre></section></main>
<script>
const $=id=>document.getElementById(id);let meta,serial=0,inspection;
async function request(url){let r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(await r.text());return r.json()}
function details(){let layer=inspection?.layers.find(x=>x.id===$('layers').value);$('detail').textContent=JSON.stringify(layer||inspection,null,2)}
async function show(){let ticket=++serial,n=Number($('seek').value);try{let info=await request('/inspect?frame='+n);if(ticket!==serial)return;inspection=info;$('picture').src='/frame?frame='+n+($('native').checked?'':'&width=640')+'&revision='+meta.revision;$('position').textContent=`Frame ${n} / ${meta.frames-1} · ${(n/meta.fps).toFixed(3)}s`;$('error').textContent='';details()}catch(e){$('error').textContent=e.message;$('picture').removeAttribute('src')}}
async function init(){try{meta=await request('/metadata');$('seek').max=meta.frames-1;let selected=$('layers').value;$('layers').replaceChildren(...meta.layers.map(l=>{let o=document.createElement('option');o.value=l.id;o.textContent=l.id;return o}));if(meta.layers.some(l=>l.id===selected))$('layers').value=selected;await show()}catch(e){$('error').textContent=e.message;$('picture').removeAttribute('src')}}
$('picture').onerror=()=>{$('error').textContent='Frame failed to render. Refresh to reload source.';$('picture').removeAttribute('src')};
$('seek').oninput=show;$('layers').onchange=details;$('native').onchange=show;$('refresh').onclick=init;
for(let [id,delta] of [['prev',-1],['next',1]])$(id).onclick=()=>{$('seek').value=Math.max(0,Math.min(meta.frames-1,Number($('seek').value)+delta));show()};init();
</script>"""


def preview_server(spec_path, port=8765):
    if type(port) is not int or not 0 <= port <= 65535:
        raise GilvyError("invalid preview port")
    session = PreviewSession(spec_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                args = parse_qs(parsed.query)
                if parsed.path == "/":
                    data, mime = VIEWER.encode(), "text/html; charset=utf-8"
                elif parsed.path == "/metadata":
                    data, mime = json.dumps(session.metadata()).encode(), "application/json"
                elif parsed.path in ("/frame", "/inspect"):
                    index = int(args.get("frame", ["0"])[0])
                    if parsed.path == "/frame":
                        width = int(args["width"][0]) if "width" in args else None
                        data, mime = session.png(index, width), "image/png"
                    else:
                        session.refresh()
                        data, mime = json.dumps(session.film.inspect(index)).encode(), "application/json"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
            except (GilvyError, OSError, ValueError) as exc:
                self.send_response(400)
                data, mime = str(exc).encode(), "text/plain; charset=utf-8"
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    return HTTPServer(("127.0.0.1", port), Handler)
