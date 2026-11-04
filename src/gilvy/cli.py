"""Command line: render, preview, qc, new, mcp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gilvy.assets import build_manifest
from gilvy.episode import load_episode, resolve_output
from gilvy.errors import GilvyError
from gilvy.formats import get_profile
from gilvy.qc import qc_video
from gilvy.render import output_paths, preview_episode, render_episode, preview_motion
from gilvy.review import compare_versions
from gilvy.reference import analyze_reference
from gilvy.reference_download import download_reference
from gilvy.product_render import render_product, preview_product
from gilvy.elements import element_catalog, motion_reference_notes

_TEMPLATE = """\
# 9:16 faceless explainer. Voice-over first, then captions, then a scene type.
#   gilvy preview {name}/{name}.yaml --tts fixture
#   gilvy render {name}/{name}.yaml
#   gilvy qc out/{name}.mp4
# Green is one number. Caption words, including key words, stay white.

name: {name}
language: en-US
voice: en-US-AndrewNeural
rate: "-8%"
poster: 0

scenes:
  - id: hook
    type: bowl_hook
    caption:
      - "start with one"
      - "number."
    key: ["number."]
    vo: "Start with one number."
    min: 3.2
    price: "$25"
    note: example

  - id: close
    type: bowl_cta
    caption:
      - "what is yours?"
    key: ["yours?"]
    vo: "What is yours? Leave it in the comments."
    min: 3.4
    label: comment yours

# Custom drawing, when no scene type fits. Same green rule.
#  - id: custom
#    type: python
#    entry: custom_scene.py:draw
#    caption: ["one figure."]
#    key: ["figure."]
#    vo: "One figure."
#    min: 3.0
#    price: "$25"
"""

_CUSTOM = '''\
"""Custom scene. Called as draw(ctx, u, duration, params).

Use Ctx primitives. Green (`ctx.money`, or `col=ctx.theme.green`) is one quantity.
Everything else stays white.
"""

from gilvy.easing import R, eio, eo, lerp


def draw(ctx, u, duration, params):
    appear = eo(R(u, 0, 0.6))
    travel = eio(R(u, 0.3, max(1.4, duration * 0.65)))
    center = (ctx.theme.cx, 780)
    ctx.glow(center, 150, appear * 0.55)
    ctx.coin(lerp((ctx.theme.cx, 420), center, travel), appear, r=18)
    ctx.money((ctx.theme.cx, 980), str(params.get("price", "$25")), eo(R(u, duration * 0.35, max(1.6, duration * 0.65))), sz=34, ex=True)
'''


def _cmd_new(name: str) -> int:
    dest = Path(name)
    if dest.exists():
        raise GilvyError(f"{dest} already exists")
    dest.mkdir(parents=True)
    stem = dest.name
    (dest / f"{stem}.yaml").write_text(_TEMPLATE.format(name=stem), encoding="utf-8")
    (dest / "custom_scene.py").write_text(_CUSTOM, encoding="utf-8")
    print(dest / f"{stem}.yaml")
    return 0


def _formats(episode, requested: list[str] | None) -> list[str]:
    names = requested or [episode.format]
    try:
        for name in names:
            get_profile(name)
    except KeyError as exc:
        raise GilvyError(str(exc)) from exc
    return names


def _cmd_preview(args: argparse.Namespace) -> int:
    episode = load_episode(args.episode)
    names = _formats(episode, args.format)
    if len(names) != 1:
        raise GilvyError("preview takes one --format")
    episode = episode.with_format(names[0])
    out = Path(args.out).resolve() if args.out else None
    result = preview_episode(episode, out, args.tts, args.fraction)
    print(result["sheet"])
    print(result["motion_sheet"])
    print(f"{result['format']} {result['width']}x{result['height']}")
    print(f"duration {result['duration']:.2f}s  stills {result['scenes']}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    episode = load_episode(args.episode)
    names = _formats(episode, args.format)
    base = resolve_output(episode, args.out)
    failed = False
    for name, dest in zip(names, output_paths(base, names)):
        result = render_episode(episode.with_format(name), dest, args.tts, args.workers)
        print(result["video"])
        print(f"duration {result['duration']:.2f}s")
        print(result["sheet"])
        if result["poster"]:
            print(result["poster"])
        report = result["qc"]
        print(f"QC {'PASS' if report['ok'] else 'FAIL'} (technical only; creative review not evaluated)")
        for item in report["violations"]:
            print(f"- {item}")
        failed = failed or not report["ok"]
    return 1 if failed else 0


def _cmd_qc(args: argparse.Namespace) -> int:
    report = qc_video(args.video, args.timeline, args.audio_mode)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.text())
    return 0 if report.ok else 1


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gilvy", description="Faceless 9:16 explainer videos.")
    sub = parser.add_subparsers(dest="command", required=True)

    render = sub.add_parser("render", help="render an episode to mp4")
    render.add_argument("episode")
    render.add_argument("--out", "-o", help="mp4 path (default out/<name>.mp4)")
    render.add_argument("--tts", choices=("edge", "fixture"), default="edge")
    render.add_argument("--workers", type=int, default=0, help="0 uses up to 8 cores")
    render.add_argument("--format", action="append", help="delivery profile, repeatable. Default is the episode format.")

    preview = sub.add_parser("preview", help="stills and a contact sheet")
    preview.add_argument("episode")
    preview.add_argument("--out", "-o", help="directory for pngs")
    preview.add_argument("--tts", choices=("edge", "fixture"), default="edge")
    preview.add_argument("--fraction", type=float, default=0.8)
    preview.add_argument("--format", action="append", help="one delivery profile")

    qc = sub.add_parser("qc", help="green ratio, silence, blank and dark frames")
    qc.add_argument("video")
    qc.add_argument("--timeline", help="timeline json (default: next to the video)")
    qc.add_argument("--json", action="store_true")
    qc.add_argument("--audio-mode", choices=("voiceover", "ambient", "silent"), help="override audio expectations when no sidecar is available")

    new = sub.add_parser("new", help="scaffold an episode directory")
    new.add_argument("name", help="directory slug, for example ep02")

    motion = sub.add_parser("preview-motion", help="render a short motion-review clip")
    motion.add_argument("episode")
    motion.add_argument("--out", "-o")
    motion.add_argument("--start", type=float, default=0)
    motion.add_argument("--duration", type=float, default=8)
    motion.add_argument("--width", type=int, default=540)
    motion.add_argument("--tts", choices=("edge", "fixture"), default="fixture")
    motion.add_argument("--workers", type=int, default=0)

    compare = sub.add_parser("compare", help="paired video frames and pixel evidence")
    compare.add_argument("reference")
    compare.add_argument("candidate")
    compare.add_argument("--out", default="out/comparison")
    compare.add_argument("--reference-start", type=float, default=0)
    compare.add_argument("--candidate-start", type=float, default=0)
    compare.add_argument("--duration", type=float, default=8)
    compare.add_argument("--sample-fps", type=float, default=2)

    download = sub.add_parser("download-reference", help="fetch one supported-site or direct HTTP(S) video")
    download.add_argument("url")
    download.add_argument("--out", required=True, help="new download directory")
    download.add_argument("--max-height", type=int, default=1080)
    download.add_argument("--max-duration", type=float, default=600)
    download.add_argument("--max-size-mb", type=int, default=512)
    download.add_argument("--timeout", type=float, default=300)

    reference = sub.add_parser("analyze-reference", help="extract local reference video into scene evidence")
    reference.add_argument("video")
    reference.add_argument("--out", required=True, help="new output directory")
    reference.add_argument("--threshold", type=float, default=.3)
    reference.add_argument("--min-scene", type=float, default=.8)
    reference.add_argument("--boundaries", type=float, nargs="*", default=None,
                           help="manual interior scene times; empty means one scene")
    reference.add_argument("--clip-seconds", type=float, default=8)
    reference.add_argument("--width", type=int, default=640)

    product = sub.add_parser("render-product", help="render an opt-in product motion film")
    product.add_argument("spec")
    product.add_argument("--out", required=True)
    product.add_argument("--start", type=float, default=0)
    product.add_argument("--duration", type=float)
    pp = sub.add_parser("preview-product", help="timestamped stills of a product film")
    pp.add_argument("spec")
    pp.add_argument("--out", required=True)
    pp.add_argument("--times", nargs="+", type=float)
    inspect = sub.add_parser("inspect-product", help="native frame and layer timing/state")
    inspect.add_argument("spec")
    inspect.add_argument("--frame", type=int, required=True)
    inspect.add_argument("--out", required=True)
    serve_product = sub.add_parser("serve-product", help="local frame-seeking viewer (silent)")
    serve_product.add_argument("spec")
    serve_product.add_argument("--port", type=int, default=8765)
    sub.add_parser("product-notes", help="read product motion schema and directing guidance")

    sub.add_parser("elements", help="list composable visual elements and their verbs")
    sub.add_parser("motion-reference", help="read visual vocabulary and Bojonegoro motion study")
    sub.add_parser("reference-styles", help="measured vox-explainer and history-story directing guide")
    assets = sub.add_parser("assets", help="list image plates an episode must generate before render")
    assets.add_argument("episode")
    sub.add_parser("mcp", help="MCP server on stdio")

    args = parser.parse_args(argv)
    try:
        if args.command == "download-reference":
            print(json.dumps(download_reference(args.url,args.out,args.max_height,args.max_duration,
                                                args.max_size_mb,args.timeout),indent=2))
            return 0
        if args.command == "inspect-product":
            from gilvy.product_preview import inspect_product_frame
            print(json.dumps(inspect_product_frame(args.spec,args.frame,args.out),indent=2))
            return 0
        if args.command == "serve-product":
            from gilvy.product_preview import preview_server
            try:
                server = preview_server(args.spec,args.port)
            except OSError as exc:
                raise GilvyError(f"could not start local preview: {exc}") from exc
            print(f"Gilvy preview: http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        if args.command == "product-notes":
            from gilvy.product import product_notes
            print(product_notes())
            return 0
        if args.command == "render-product":
            print(json.dumps(render_product(args.spec,args.out,args.start,args.duration),indent=2))
            return 0
        if args.command == "preview-product":
            print(json.dumps(preview_product(args.spec,args.out,args.times),indent=2))
            return 0
        if args.command == "analyze-reference":
            print(json.dumps(analyze_reference(args.video, args.out, args.threshold, args.min_scene,
                                              args.boundaries, args.clip_seconds, args.width), indent=2))
            return 0
        if args.command == "elements":
            print(json.dumps(element_catalog(), indent=2))
            return 0
        if args.command == "motion-reference":
            print(motion_reference_notes())
            return 0
        if args.command == "reference-styles":
            print(Path(__file__).resolve().parent.joinpath("REFERENCE_STYLES.md").read_text(encoding="utf-8"))
            return 0
        if args.command == "assets":
            print(json.dumps(build_manifest(load_episode(args.episode)), indent=2))
            return 0
        if args.command == "new":
            return _cmd_new(args.name)
        if args.command == "preview":
            return _cmd_preview(args)
        if args.command == "render":
            return _cmd_render(args)
        if args.command == "qc":
            return _cmd_qc(args)
        if args.command == "preview-motion":
            episode = load_episode(args.episode)
            out = Path(args.out).expanduser().resolve() if args.out else Path.cwd() / "out" / f"{episode.name}-motion.mp4"
            print(json.dumps(preview_motion(episode, out, args.start, args.duration,
                                           args.tts, args.workers, args.width), indent=2))
            return 0
        if args.command == "compare":
            print(json.dumps(compare_versions(args.reference, args.candidate, args.out,
                                              args.reference_start, args.candidate_start,
                                              args.duration, args.sample_fps), indent=2))
            return 0
        if args.command == "mcp":
            from gilvy.mcp_server import serve

            serve()
            return 0
    except GilvyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


def main() -> None:
    sys.exit(run())
