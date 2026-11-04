"""List the stills an image episode needs before it can render."""

from __future__ import annotations

from pathlib import Path

from gilvy.errors import GilvyError
from gilvy.presets import PHOTO_PRESETS, STYLE_PROMPTS


def _role(depth: float, count: int) -> str:
    if count == 1:
        return "still"
    if depth <= 0.34:
        return "background"
    if depth <= 0.67:
        return "midground"
    return "foreground"


def _relative(episode_dir: Path, src: str) -> str:
    path = Path(src)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(episode_dir).as_posix()
        except ValueError:
            return str(path)
    return path.as_posix()


def build_manifest(episode) -> dict:
    """Asset list for an episode. Missing files are reported, not created."""
    style = episode.style
    prefix = STYLE_PROMPTS.get(style, "")
    assets = []
    for index, scene in enumerate(episode.scenes, 1):
        if scene.type != "image":
            continue
        layers = scene.params.get("layers") or []
        for layer in layers:
            src = layer["src"]
            path = Path(src)
            if not path.is_absolute():
                path = episode.source_dir / path
            path = path.resolve()
            role = _role(float(layer.get("depth", 1)), len(layers))
            subject = " ".join(part for part in (scene.params.get("prompt") or "", layer.get("prompt") or "") if part)
            prompt = prefix
            if role != "still":
                prompt += f" This file is the {role} layer of a parallax stack."
            if subject:
                prompt += " " + subject
            assets.append({
                "scene_index": index,
                "scene_id": scene.id or f"s{index}",
                "role": role,
                "depth": layer.get("depth", 1),
                "src": _relative(episode.source_dir, src),
                "path": str(path),
                "exists": path.is_file(),
                "width": 1080,
                "height": 1920,
                "prompt": prompt.strip(),
            })
    return {
        "name": episode.name,
        "style": style,
        "style_prompt": prefix,
        "assets": assets,
        "missing": [item["src"] for item in assets if not item["exists"]],
    }


def require_assets(episode) -> None:
    """Fail render before encode when a referenced plate is not on disk."""
    if episode.style not in PHOTO_PRESETS:
        return
    manifest = build_manifest(episode)
    if not manifest["missing"]:
        return
    lines = []
    for item in manifest["assets"]:
        if not item["exists"]:
            lines.append(f"- scene {item['scene_index']} ({item['scene_id']}): {item['src']}")
    joined = "\n".join(lines)
    raise GilvyError(
        "missing image assets:\n"
        f"{joined}\n"
        "Generate each file from its prompt (`gilvy assets <episode>`), then render again."
    )
