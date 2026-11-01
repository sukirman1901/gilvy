"""Command line: render, preview, qc, new, mcp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gilvy.episode import load_episode, resolve_output
from gilvy.errors import GilvyError
from gilvy.qc import qc_video
from gilvy.render import preview_episode, render_episode

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

from gilvy.easing import R, eo


def draw(ctx, u, duration, params):
    alpha = eo(R(u, 0, 0.6))
    center = (ctx.theme.cx, 780)
    ctx.glow(center, 150, alpha * 0.55)
    ctx.circ(center, 70, alpha, w=2)
    ctx.money(center, str(params.get("price", "$25")), alpha, sz=34, ex=True)
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


def _cmd_preview(args: argparse.Namespace) -> int:
    episode = load_episode(args.episode)
    out = Path(args.out).resolve() if args.out else None
    result = preview_episode(episode, out, args.tts, args.fraction)
    print(result["sheet"])
    print(f"duration {result['duration']:.2f}s  stills {result['scenes']}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    episode = load_episode(args.episode)
    dest = resolve_output(episode, args.out)
    result = render_episode(episode, dest, args.tts, args.workers)
    print(result["video"])
    print(f"duration {result['duration']:.2f}s")
    print(result["sheet"])
    if result["poster"]:
        print(result["poster"])
    report = result["qc"]
    print(f"QC {'PASS' if report['ok'] else 'FAIL'}")
    for item in report["violations"]:
        print(f"- {item}")
    return 0 if report["ok"] else 1


def _cmd_qc(args: argparse.Namespace) -> int:
    report = qc_video(args.video, args.timeline)
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

    preview = sub.add_parser("preview", help="stills and a contact sheet")
    preview.add_argument("episode")
    preview.add_argument("--out", "-o", help="directory for pngs")
    preview.add_argument("--tts", choices=("edge", "fixture"), default="edge")
    preview.add_argument("--fraction", type=float, default=0.8)

    qc = sub.add_parser("qc", help="green ratio, silence, blank and dark frames")
    qc.add_argument("video")
    qc.add_argument("--timeline", help="timeline json (default: next to the video)")
    qc.add_argument("--json", action="store_true")

    new = sub.add_parser("new", help="scaffold an episode directory")
    new.add_argument("name", help="directory slug, for example ep02")

    sub.add_parser("mcp", help="MCP server on stdio")

    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            return _cmd_new(args.name)
        if args.command == "preview":
            return _cmd_preview(args)
        if args.command == "render":
            return _cmd_render(args)
        if args.command == "qc":
            return _cmd_qc(args)
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
