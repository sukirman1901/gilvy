"""MCP server. stdio transport for opencode, Claude Code, and Cursor."""

from __future__ import annotations

import json
import warnings

warnings.filterwarnings("ignore", message="Field 'lifespan' has an incomplete definition")

from mcp.server.fastmcp import FastMCP

from gilvy.episode import load_episode, resolve_output
from gilvy.errors import GilvyError
from gilvy.qc import qc_video
from gilvy.render import preview_episode, render_episode
from gilvy.scenes import catalog

mcp = FastMCP(
    "gilvy",
    instructions=(
        "gilvy renders faceless 9:16 explainer videos from a YAML episode. "
        "Write the voice-over first, pick a scene type per beat, call preview_frames, "
        "then render_video, then read qc_report. Green marks one number only. "
        "Caption key words stay white. Do not edit the drawing engine to fix a scene."
    ),
)


def _fail(exc: GilvyError) -> str:
    return json.dumps({"ok": False, "error": str(exc)})


@mcp.tool()
def render_video(episode_path: str, output: str = "", tts: str = "edge", workers: int = 0) -> str:
    """Render a YAML episode to a 1080x1920 H.264/AAC mp4 and run QC.

    tts is "edge" for the neural voice or "fixture" for an offline tone used to check layout.
    output defaults to out/<name>.mp4. A non-ok QC report means fix the YAML and render again.
    """
    try:
        episode = load_episode(episode_path)
        dest = resolve_output(episode, output or None)
        result = render_episode(episode, dest, tts, workers)
        result["ok"] = bool(result["qc"]["ok"])
        return json.dumps(result)
    except GilvyError as exc:
        return _fail(exc)


@mcp.tool()
def preview_frames(episode_path: str, output_dir: str = "", tts: str = "edge", fraction: float = 0.8) -> str:
    """Write one still per scene (at 80% by default) and a contact sheet. This is the fast check before a full render."""
    try:
        episode = load_episode(episode_path)
        dest = output_dir or None
        from pathlib import Path

        result = preview_episode(episode, Path(dest) if dest else None, tts, fraction)
        result["ok"] = True
        return json.dumps(result)
    except GilvyError as exc:
        return _fail(exc)


@mcp.tool()
def qc_report(video_path: str, timeline: str = "") -> str:
    """Check green-ratio, silence gaps, and blank or dark frames. ok is false when a rule is broken."""
    try:
        report = qc_video(video_path, timeline or None)
        return json.dumps(report.to_dict())
    except GilvyError as exc:
        return _fail(exc)


@mcp.tool()
def list_scene_types() -> str:
    """List scene types, the green role of each, and the YAML parameters they take."""
    return json.dumps(catalog())


def serve() -> None:
    mcp.run(transport="stdio")
