"""Fetch one recorded reference from supported sites or direct HTTP(S) media.

This is acquisition, not visual analysis. yt-dlp runs in a separate process
with a wall-clock deadline; downloaded bytes are checked before publication.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from gilvy.errors import GilvyError


def _source_url(url: str) -> str:
    """Keep source identity without persisting signed download query tokens."""
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query)
                       if parts.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com') and k == 'v'])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))


def _download_error(stderr: str) -> GilvyError:
    message = stderr.lower()
    if any(x in message for x in ('sign in', 'login', 'private video', 'authentication', 'cookies', 'not a bot')):
        reason = 'the site requires authentication or a bot check'
    elif any(x in message for x in ('unsupported url', 'unsupported site', 'no video formats', 'no video could')):
        reason = 'this URL/site does not expose a supported video'
    elif any(x in message for x in ('drm', 'protected content')):
        reason = 'the video is protected and cannot be retrieved by this downloader'
    elif any(x in message for x in ('403', 'forbidden', 'geo-restricted', 'not available', 'unavailable')):
        reason = 'the host denies access or the video is unavailable in this environment'
    elif any(x in message for x in ('max-filesize', 'larger than max', 'too large')):
        reason = 'the video exceeds the download size limit'
    else:
        reason = 'extraction or transfer failed; check the link, network access and yt-dlp version'
    # Site errors may include expiring signed URLs. Do not echo them into MCP logs.
    return GilvyError(f'reference download failed: {reason}. Supply a local video to analyze-reference instead.')


def _kill(proc):
    if os.name == 'posix':
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        proc.kill()
    proc.communicate()


def _run(args, deadline, disk_dir=None, disk_limit=None):
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, start_new_session=os.name == 'posix')
    except OSError as exc:
        raise GilvyError('could not start reference downloader') from exc
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill(proc)
            raise GilvyError('reference download timed out; retry with a larger timeout or supply a local video')
        try:
            stdout, stderr = proc.communicate(timeout=min(1, remaining))
            break
        except subprocess.TimeoutExpired:
            size = 0
            if disk_dir:
                for path in Path(disk_dir).rglob('*'):
                    try:
                        if path.is_file(): size += path.stat().st_size
                    except FileNotFoundError:
                        pass  # yt-dlp can remove merged fragments during polling.
            if disk_dir and size > disk_limit:
                _kill(proc)
                raise GilvyError('reference download exceeded the temporary disk budget')
    if proc.returncode:
        raise _download_error(stderr)
    return stdout


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def download_reference(url: str, output_dir: str | Path, max_height: int = 1080,
                       max_duration: float = 600, max_size_mb: int = 512,
                       timeout: float = 300) -> dict:
    """Download one supported-site/direct video into a NEW directory.

    No browser login, cookies, credentials, playlists, DRM bypass, thumbnail
    extraction or automatic creative review. Returns a local video path suitable
    for analyze_reference. Source title/site metadata remains untrusted data.
    """
    if not isinstance(url, str) or any(ord(c) < 32 for c in url):
        raise GilvyError('reference URL must be an HTTP(S) URL')
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
            raise ValueError()
        _ = parts.port
    except ValueError as exc:
        raise GilvyError('reference URL must be HTTP(S) without embedded credentials') from exc
    if (type(max_height) is not int or not 160 <= max_height <= 2160
        or not _number(max_duration) or not 0 < max_duration <= 600
        or type(max_size_mb) is not int or not 1 <= max_size_mb <= 2048
        or not _number(timeout) or not 1 <= timeout <= 1800):
        raise GilvyError('download limits: height 160..2160, duration >0..600s, size 1..2048MiB, timeout 1..1800s')
    dest = Path(output_dir).expanduser().resolve()
    if dest.exists():
        raise GilvyError('download output already exists; choose a new directory')
    if importlib.util.find_spec('yt_dlp') is None:
        raise GilvyError('URL downloads need yt-dlp: install gilvy[download] in the same environment as the MCP server')
    if any(shutil.which(x) is None for x in ('ffmpeg', 'ffprobe')):
        raise GilvyError('ffmpeg and ffprobe are required for reference downloads')
    deadline = time.monotonic() + timeout
    limit = max_size_mb * 1024 * 1024
    common = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-playlist',
              '--no-warnings', '--quiet', '--socket-timeout', '15', '--retries', '1',
              '--fragment-retries', '1', '--extractor-retries', '1', '--no-cache-dir', '--playlist-end', '1']
    try:
        metadata = json.loads(_run(common + ['--dump-single-json', '--skip-download',
                    '--flat-playlist', '--', url], deadline))
    except (json.JSONDecodeError, TypeError) as exc:
        raise GilvyError('downloader did not return valid video metadata') from exc
    if not isinstance(metadata, dict) or metadata.get('_type') in ('playlist', 'multi_video') or 'entries' in metadata:
        raise GilvyError('provide a single video URL, not a playlist or channel')
    if metadata.get('is_live') or metadata.get('live_status') in ('is_live', 'is_upcoming'):
        raise GilvyError('reference download requires a recorded video, not a live/upcoming stream')
    if metadata.get('has_drm'):
        raise GilvyError('protected video cannot be retrieved by this downloader')
    duration = metadata.get('duration')
    if duration is not None and (not _number(duration) or not 0 < duration <= max_duration):
        raise GilvyError(f'reference exceeds the {max_duration:g}s duration limit')
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='.gilvy-download-', dir=dest.parent) as temp:
            stage = Path(temp)
            # Fixed basename: third-party titles never become filesystem paths.
            selector = f'bv*[height<=?{max_height}]+ba/b[height<=?{max_height}]'
            _run(common + ['--format', selector, '--merge-output-format', 'mkv',
                 '--max-filesize', str(limit), '--output', str(stage / 'source.%(ext)s'),
                 '--no-write-info-json', '--no-write-thumbnail', '--no-write-subs', '--', url],
                 deadline, stage, 2 * limit)
            candidates = [p for p in stage.glob('source.*')
                          if p.is_file() and p.suffix.lower() in ('.mp4', '.mkv', '.webm', '.mov', '.avi', '.flv', '.ts', '.m4v')]
            if len(candidates) != 1:
                raise GilvyError('download did not produce one complete video; it may be unsupported or exceed the size limit')
            media = candidates[0]
            if not 0 < media.stat().st_size <= limit:
                raise GilvyError('downloaded video is empty or exceeds the size limit')
            try:
                probe = json.loads(_run(['ffprobe', '-v', 'error', '-show_entries',
                    'format=duration:stream=codec_type,width,height,duration', '-of', 'json', str(media)], deadline))
                video = next(s for s in probe.get('streams', []) if s.get('codec_type') == 'video')
                actual_duration = float(video.get('duration') or probe.get('format', {}).get('duration', 0))
                width, height = int(video['width']), int(video['height'])
                if not math.isfinite(actual_duration) or not 0 < actual_duration <= max_duration or min(width,height) <= 0 or height > max_height:
                    raise ValueError()
            except (ValueError, TypeError, KeyError, StopIteration) as exc:
                raise GilvyError('downloaded media is not a valid video within the requested duration/resolution limits') from exc
            result = {'schema_version': 1, 'source_url': _source_url(url),
                'source_query_redacted': bool(parts.query and _source_url(url) != urlunsplit((parts.scheme,parts.netloc,parts.path,parts.query,''))),
                'title': str(metadata.get('title') or '')[:2000], 'source_id': str(metadata.get('id') or '')[:200],
                'extractor': str(metadata.get('extractor_key') or metadata.get('extractor') or '')[:200],
                'video': str(dest / media.name), 'manifest': str(dest / 'download.json'),
                'duration': actual_duration, 'width': width, 'height': height,
                'bytes': media.stat().st_size, 'audio_present': any(s.get('codec_type') == 'audio' for s in probe.get('streams', [])),
                'next_step': 'analyze_reference(video, a_new_output_directory)', 'creative_review': 'not_performed',
                'limits': {'max_height':max_height,'max_duration':max_duration,'max_size_mb':max_size_mb,'timeout':timeout}}
            # Reserve the final directory without overwriting an existing one.
            dest.mkdir()
            try:
                media.replace(dest / media.name)
                (dest / 'download.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            except OSError:
                shutil.rmtree(dest)
                raise
            return result
    except FileExistsError as exc:
        raise GilvyError('download output already exists; choose a new directory') from exc
    except OSError as exc:
        raise GilvyError('could not store downloaded reference') from exc
