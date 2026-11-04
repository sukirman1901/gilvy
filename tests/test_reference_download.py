"""Acquisition is bounded, preserves provenance and feeds local analysis."""
import functools
import http.server
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import pytest

from gilvy.cli import run
from gilvy.errors import GilvyError
from gilvy.mcp_server import download_reference as mcp_download
from gilvy.reference import analyze_reference
from gilvy import reference_download as dl


@pytest.fixture
def video(tmp_path):
    path=tmp_path/'fixture.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:s=160x120:r=5:d=1.2',
        '-f','lavfi','-i','sine=frequency=440:duration=1.2','-c:v','libx264','-threads','2',
        '-pix_fmt','yuv420p','-c:a','aac','-shortest',str(path)],check=True)
    return path


@pytest.fixture
def fake_worker(monkeypatch, video):
    original_run=dl._run;original_find=importlib.util.find_spec
    monkeypatch.setattr(dl.importlib.util,'find_spec',lambda name: object() if name=='yt_dlp' else original_find(name))
    metadata={'id':'sample','title':'Untrusted source title','extractor_key':'Vimeo','duration':1.2}
    calls=[]
    def worker(args,deadline,disk_dir=None,disk_limit=None):
        calls.append(args)
        if args[0]=='ffprobe':return original_run(args,deadline)
        if '--dump-single-json' in args:return json.dumps(metadata)
        target=Path(args[args.index('--output')+1].replace('%(ext)s','mp4'))
        shutil.copyfile(video,target)
        return ''
    monkeypatch.setattr(dl,'_run',worker)
    return metadata,calls


@pytest.mark.parametrize("url,expect", [
    ("https://www.youtube.com/watch?v=awUYikrGsKk", True),
    ("https://m.youtube.com/watch?v=awUYikrGsKk", True),
    ("https://youtu.be/awUYikrGsKk", True),
    ("https://youtube.com/watch?v=awUYikrGsKk", True),
    ("https://vimeo.com/12345", False),
    ("https://cdn.example.com/video.mp4", False),
])
def test_youtube_sets_node_js_runtime_when_node_exists(fake_worker, monkeypatch, tmp_path, url, expect):
    monkeypatch.setattr(dl.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else f"/usr/bin/{name}")
    dl.download_reference(url, tmp_path / "download", max_height=160)
    _, calls = fake_worker
    yt_dlp_calls = [args for args in calls if args and args[0] != "ffprobe"]
    assert yt_dlp_calls
    for args in yt_dlp_calls:
        if expect:
            assert args[args.index("--js-runtimes") + 1] == "node:/usr/bin/node"
        else:
            assert "--js-runtimes" not in args


def test_youtube_skips_js_runtime_when_node_is_missing(fake_worker, monkeypatch, tmp_path):
    monkeypatch.setattr(dl.shutil, "which", lambda name: None if name == "node" else f"/usr/bin/{name}")
    dl.download_reference("https://youtu.be/awUYikrGsKk", tmp_path / "download", max_height=160)
    _, calls = fake_worker
    for args in calls:
        assert "--js-runtimes" not in args


def test_publication_manifest_and_query_redaction(fake_worker,tmp_path):
    _,calls=fake_worker
    url='https://cdn.example.com/video.mp4?token=private-value'
    dest=tmp_path/'download';result=dl.download_reference(url,dest,max_height=160)
    assert Path(result['video']).is_file() and result['audio_present']
    assert result['duration']==pytest.approx(1.2)
    assert result['source_url']=='https://cdn.example.com/video.mp4' and result['source_query_redacted']
    assert 'private-value' not in Path(result['manifest']).read_text()
    assert result['creative_review']=='not_performed'
    for args in calls[:2]:
        assert '--ignore-config' in args and '--no-playlist' in args and args[-2:]==['--',url]
    assert not list(tmp_path.glob('.gilvy-download-*'))
    with pytest.raises(GilvyError,match='already exists'):dl.download_reference(url,dest)


@pytest.mark.parametrize('url',[
    'https://www.youtube.com/watch?v=awUYikrGsKk&list=example',
    'https://vimeo.com/12345','https://www.instagram.com/reel/example/',
    'https://www.tiktok.com/@example/video/12345','https://example.org/embedded-video-page',
])
def test_site_urls_are_not_limited_to_youtube(fake_worker,tmp_path,url):
    result=dl.download_reference(url,tmp_path/'download')
    assert Path(result['video']).is_file()
    if 'youtube.com' in url:assert result['source_url']=='https://www.youtube.com/watch?v=awUYikrGsKk'


@pytest.mark.parametrize('url,options',[
    ('file:///etc/passwd',{}),('ftp://example.com/video.mp4',{}),
    ('https://user:password@example.com/video',{}),('not a URL',{}),
    ('https://example.com/\nvideo',{}),('https://example.com:bad/video',{}),
    ('https://example.com/video',{'max_height':True}),
    ('https://example.com/video',{'max_duration':float('nan')}),
    ('https://example.com/video',{'max_size_mb':0}),
    ('https://example.com/video',{'timeout':0}),
])
def test_invalid_inputs_do_not_create_destination(tmp_path,url,options):
    with pytest.raises(GilvyError):dl.download_reference(url,tmp_path/'bad',**options)
    assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('fields',[
    {'_type':'playlist','entries':[]},{'is_live':True},{'live_status':'is_upcoming'},
    {'has_drm':True},{'duration':601},
])
def test_unusable_source_metadata_rejected_before_transfer(fake_worker,tmp_path,fields):
    metadata,calls=fake_worker;metadata.update(fields)
    with pytest.raises(GilvyError):dl.download_reference('https://example.com/video',tmp_path/'bad')
    assert len(calls)==1 and not (tmp_path/'bad').exists()


def test_transfer_failure_cleans_partials_and_does_not_publish(fake_worker,monkeypatch,tmp_path):
    original=dl._run
    def failing(args,deadline,disk_dir=None,disk_limit=None):
        if '--dump-single-json' in args:return original(args,deadline)
        (Path(disk_dir)/'source.mp4.part').write_bytes(b'partial')
        raise dl._download_error('ERROR: HTTP Error 403: https://cdn.example.com/?token=SECRET')
    monkeypatch.setattr(dl,'_run',failing)
    with pytest.raises(GilvyError) as error:dl.download_reference('https://example.com/video',tmp_path/'bad')
    assert 'SECRET' not in str(error.value) and 'denies access' in str(error.value)
    assert not (tmp_path/'bad').exists() and not list(tmp_path.glob('.gilvy-download-*'))


def test_actual_size_and_probe_are_authoritative(fake_worker,monkeypatch,tmp_path):
    original=dl._run
    def invalid(args,deadline,disk_dir=None,disk_limit=None):
        if '--dump-single-json' in args:return original(args,deadline)
        if args[0]=='ffprobe':return json.dumps({'streams':[],'format':{'duration':1}})
        (Path(disk_dir)/'source.mp4').write_bytes(b'not a video')
        return ''
    monkeypatch.setattr(dl,'_run',invalid)
    with pytest.raises(GilvyError,match='not a valid video'):dl.download_reference('https://example.com/video',tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_missing_optional_dependency_has_install_hint(monkeypatch,tmp_path):
    monkeypatch.setattr(dl.importlib.util,'find_spec',lambda name: None)
    with pytest.raises(GilvyError,match=r'gilvy\[download\]'):
        dl.download_reference('https://example.com/video',tmp_path/'missing')
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('size',[0,1024*1024+1])
def test_empty_or_oversized_file_never_published(fake_worker,monkeypatch,tmp_path,size):
    original=dl._run
    def transfer(args,deadline,disk_dir=None,disk_limit=None):
        if '--dump-single-json' in args:return original(args,deadline)
        (Path(disk_dir)/'source.mp4').write_bytes(b'x'*size)
        return ''
    monkeypatch.setattr(dl,'_run',transfer)
    with pytest.raises(GilvyError,match='empty or exceeds'):
        dl.download_reference('https://example.com/video',tmp_path/'bad',max_size_mb=1)
    assert not (tmp_path/'bad').exists() and not list(tmp_path.glob('.gilvy-download-*'))


def test_real_worker_deadline_kills_process():
    before=time.monotonic()
    with pytest.raises(GilvyError,match='timed out'):
        dl._run([sys.executable,'-c','import time; time.sleep(10)'],time.monotonic()+.1)
    assert time.monotonic()-before<3


def test_cli_mcp_return_local_path_and_do_not_auto_review(fake_worker,tmp_path,capsys):
    assert run(['download-reference','https://vimeo.com/123','--out',str(tmp_path/'cli')])==0
    assert Path(json.loads(capsys.readouterr().out)['video']).is_file()
    result=json.loads(mcp_download('https://example.com/video.mp4',str(tmp_path/'mcp')))
    assert result['ok'] and result['creative_review']=='not_performed'
    assert not json.loads(mcp_download('file:///etc/passwd',str(tmp_path/'bad')))['ok']


def test_real_direct_http_download_then_reference_analysis(video,tmp_path):
    pytest.importorskip('yt_dlp')
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    handler=functools.partial(QuietHandler,directory=str(tmp_path))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}/{video.name}?token=sample'
        result=dl.download_reference(url,tmp_path/'real',max_height=160,timeout=30)
        assert result['audio_present'] and result['bytes']>0
        study=analyze_reference(result['video'],tmp_path/'study',width=160)
        assert study['scenes'] and Path(study['manifest']).is_file()
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
