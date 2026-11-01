"""MCP server. stdio transport for opencode, Claude Code, and Cursor."""

from __future__ import annotations

import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="Field 'lifespan' has an incomplete definition")

from mcp.server.fastmcp import FastMCP

from gilvy.episode import load_episode, resolve_output
from gilvy.errors import GilvyError
from gilvy.qc import qc_video
from gilvy.render import preview_episode, render_episode, preview_motion as _preview_motion
from gilvy.review import compare_versions as _compare_versions
from gilvy.scenes import catalog
from gilvy.elements import element_catalog, motion_reference_notes

_DIRECTING = Path(__file__).resolve().parent / "DIRECTING.md"

mcp = FastMCP(
    "gilvy",
    instructions=(
        "You direct a gilvy episode. You do not fill a scene-type form. "
        "Call directing_notes first and name an object, a physical verb, and what carries "
        "from the previous scene for every line. Pick a library type only when its verb "
        "is that verb. Otherwise write a python scene with the Ctx primitives. "
        "Use list_visual_elements for composable people, fire, nature, and infrastructure; "
        "motion_reference explains their API and the Bojonegoro motion study. "
        "Name the intended meaning and consequence as well. "
        "Then preview_frames and preview_motion; watch the clip before render_video. "
        "Use compare_versions to inspect approved material when extending a cut. "
        "QC is technical only and never creative approval. "
        "Green is one quantity. Captions stay white. Do not restyle the canvas."
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
    """Write the settled still, a motion strip, and a contact sheet.

    Each scene is grabbed at 12% (entrance), 45% (the verb), and 80% (the read).
    motion_sheet is those frames in order. The 80% still is also sNN.png, which
    is the color-rule measurement. Pass one delivery profile by setting format
    on the episode. This is the fast check before a full render.
    """
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
def qc_report(video_path: str, timeline: str = "", audio_mode: str = "") -> str:
    """Check green-ratio, silence gaps, and blank or dark frames. ok is false when a rule is broken."""
    try:
        report = qc_video(video_path, timeline or None, audio_mode or None)
        return json.dumps(report.to_dict())
    except GilvyError as exc:
        return _fail(exc)


@mcp.tool()
def directing_notes() -> str:
    """Return the directing method. Call this before list_scene_types or writing YAML.

    Name the object, the physical verb, and what carries from the previous scene.
    A library type is allowed only when its verb is that verb. Any other verb is a
    python scene. Checklist, bars, timeline, and jars are specific sentences, not
    the default shape of an explainer.
    """
    return _DIRECTING.read_text(encoding="utf-8")


@mcp.tool()
def list_scene_types() -> str:
    """List performances with the verb each one stages, plus the YAML parameters.

    Call directing_notes first. Match a type to the verb you wrote. The slide_if
    field is the misuse that makes a cut feel like a slide.
    """
    return json.dumps(catalog())


def serve() -> None:
    mcp.run(transport="stdio")


@mcp.tool()
def preview_motion(episode_path: str, output: str = "", start: float = 0,
                   duration: float = 8, tts: str = "fixture", workers: int = 0,
                   width: int = 540) -> str:
    """Render a short review clip (duration > 0 and <= 12 seconds) at the original timing and fps.

    Select a window spanning the important transformation or scene boundary.
    Defaults to fixture timing for offline review; fixture audio is a diagnostic
    tone, not publishable voice. Set audio_mode in YAML for ambient/silent cuts.
    Watch the resulting MP4. A still strip cannot establish rhythm or legibility.
    """
    try:
        episode = load_episode(episode_path)
        dest = Path(output).expanduser().resolve() if output else Path.cwd() / "out" / f"{episode.name}-motion.mp4"
        result = _preview_motion(episode, dest, start, duration, tts, workers, width)
        result["ok"] = True
        return json.dumps(result)
    except GilvyError as exc:
        return _fail(exc)


@mcp.tool()
def compare_versions(reference_video: str, candidate_video: str, output_dir: str = "",
                     reference_start: float = 0, candidate_start: float = 0,
                     duration: float = 8, sample_fps: float = 2) -> str:
    """Create paired frames and pixel differences for an approved clip and a revision.

    Use matching resolutions. Align the starts explicitly if the clip moved.
    Results are sampled evidence, not a creative score or proof of continuity.
    An approved sample's outro may intentionally differ in the full version;
    inspect that difference rather than hiding or automatically approving it.
    """
    try:
        dest = output_dir or str(Path.cwd() / "out" / "comparison")
        result = _compare_versions(reference_video, candidate_video, dest,
                                   reference_start, candidate_start, duration, sample_fps)
        result["ok"] = True
        return json.dumps(result)
    except GilvyError as exc:
        return _fail(exc)


@mcp.tool()
def list_visual_elements() -> str:
    """List drawable elements, physical verbs, usage, and misuse notes.

    These are components for python scenes, not YAML scene types. Direct a
    relationship before selecting a symbol. Human figures have no facial detail;
    environmental symbols do not establish causal claims or measured data.
    """
    return json.dumps(element_catalog())


@mcp.tool()
def motion_reference() -> str:
    """Read the element API and approved Bojonegoro motion study.

    Includes identity-preserving rearrangement, units, scale, timing, continuation,
    and examples to reproduce. Transfer the method, not its subject or numbers.
    """
    return motion_reference_notes()
