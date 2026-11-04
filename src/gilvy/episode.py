"""YAML episodes. One file is a video: voice, captions, and a scene type per beat."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

from gilvy.errors import EpisodeError
from gilvy.formats import get_profile
from gilvy.image_scene import parse_image_params
from gilvy.presets import HOUSE, PRESETS, RULES
from gilvy.scenes import DOT_CAP, SCENES
from gilvy.theme import BG, GREEN, MIN_DURATION, WHITE

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$")
_RATE = re.compile(r"^[+-]\d+%$")
_VOICES = {
    "en-US": "en-US-AndrewNeural",
    "id-ID": "id-ID-ArdiNeural",
}
_RESERVED = {"type", "caption", "text", "key", "vo", "min", "entry", "green", "id", "vo_overrun"}
_GREEN = {"none", "focus", "any"}
_INTS = {"count", "count_from", "total", "highlight", "index"}


@dataclass
class Scene:
    type: str
    caption: list[str]
    key: list[str]
    vo: str
    min: float | None
    params: dict
    entry: str | None = None
    green: str | None = None
    id: str | None = None
    vo_overrun: bool = False
    impl: object | None = field(default=None, repr=False, compare=False)

    @property
    def green_role(self) -> str:
        if self.green:
            return self.green
        if self.type == "python":
            return "any"
        if self.type == "image":
            return "none"
        return SCENES[self.type].green


@dataclass
class Episode:
    name: str
    language: str
    voice: str
    rate: str
    scenes: list[Scene]
    source_dir: Path
    source_path: Path
    poster: int | None = None
    output: str | None = None
    font_dir: str | None = None
    bg: tuple[int, int, int] = BG
    white: tuple[int, int, int] = WHITE
    green: tuple[int, int, int] = GREEN
    format: str = "vertical_9x16"
    audio_mode: str = "voiceover"
    style: str = HOUSE
    vo_overrun: bool = False
    music: str | None = None
    loudness: float | None = None
    spoken_seconds: list[float] | None = None

    def with_format(self, name: str) -> Episode:
        get_profile(name)
        return replace(self, format=name)

    @property
    def min_duration(self) -> float:
        return MIN_DURATION


def _rgb(value, label: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise EpisodeError(f"palette.{label} must be three integers 0-255")
    out = []
    for channel in value:
        if isinstance(channel, bool) or not isinstance(channel, int) or not 0 <= channel <= 255:
            raise EpisodeError(f"palette.{label} channels must be integers 0-255")
        out.append(channel)
    return (out[0], out[1], out[2])


def _caption(raw, index: int) -> list[str]:
    if isinstance(raw, str):
        raise EpisodeError(f"scene {index}: caption must be a list of lines, not one string")
    if not isinstance(raw, list) or not raw or not all(isinstance(line, str) and line.strip() for line in raw):
        raise EpisodeError(f"scene {index}: caption needs one or more non-empty lines")
    lines = []
    for line in raw:
        words = line.split(" ")
        if len(words) > 5:
            raise EpisodeError(
                f"scene {index}: {line!r} has {len(words)} words. Use at most 5 per line "
                "and keep punctuation stuck to the word (lebih. not lebih)."
            )
        lines.append(line)
    return lines


def _keys(raw, lines: list[str], index: int) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise EpisodeError(f"scene {index}: key must be a list of caption words, copied exactly")
    words = {word for line in lines for word in line.split(" ")}
    for key in raw:
        if key not in words:
            raise EpisodeError(
                f"scene {index}: key {key!r} is not a whole caption word. "
                "Copy it with its comma or period, or it will not go SemiBold."
            )
    return list(raw)


def _scene(raw, index: int, audio_mode: str = "voiceover", style: str = HOUSE, vo_overrun: bool = False) -> Scene:
    if not isinstance(raw, dict):
        raise EpisodeError(f"scene {index} must be a mapping")
    typ = raw.get("type")
    if not isinstance(typ, str) or not typ:
        raise EpisodeError(f"scene {index}: missing type")
    caption = _caption(raw.get("caption", raw.get("text")), index)
    keys = _keys(raw.get("key"), caption, index)
    vo = raw.get("vo", "")
    if not isinstance(vo, str) or (audio_mode == "voiceover" and not vo.strip()):
        raise EpisodeError(f"scene {index}: vo is the spoken line and cannot be empty")
    minimum = raw.get("min")
    if minimum is not None:
        if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or not math.isfinite(minimum) or minimum <= 0:
            raise EpisodeError(f"scene {index}: min must be a positive number of seconds")
        minimum = float(minimum)
    if audio_mode != "voiceover" and minimum is None:
        raise EpisodeError(f"scene {index}: set min explicitly for {audio_mode} reading time")
    green = raw.get("green")
    if green is not None:
        if not isinstance(green, str) or green not in _GREEN:
            raise EpisodeError(f"scene {index}: green must be one of none, focus, any")
    entry = raw.get("entry")
    overrun = raw.get("vo_overrun", vo_overrun)
    if not isinstance(overrun, bool):
        raise EpisodeError(f"scene {index}: vo_overrun must be true or false")
    params = {}
    for key, value in raw.items():
        if key in _RESERVED:
            continue
        if key in _INTS:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise EpisodeError(f"scene {index}: {key} must be a finite number", field=f"scenes[{index - 1}].{key}")
            value = int(value)
        params[key] = value
    if typ == "python":
        if not isinstance(entry, str) or ":" not in entry:
            raise EpisodeError(f"scene {index}: python scenes need entry: file.py:function")
    elif typ == "image":
        params = parse_image_params(raw, index, style, timing_final=audio_mode != "voiceover" or overrun)
        if minimum is not None:
            rules = RULES[style]
            if not rules["shot_min"] <= minimum <= rules["shot_max"]:
                raise EpisodeError(
                    f"scene {index}: min {minimum:.2f}s is outside the {style} shot range "
                    f"{rules['shot_min']:.2f}–{rules['shot_max']:.2f}s"
                )
    elif typ not in SCENES:
        known = ", ".join([*SCENES.keys(), "python"])
        raise EpisodeError(f"scene {index}: unknown type {typ!r}. Known types: {known}")
    else:
        if entry:
            raise EpisodeError(f"scene {index}: entry is only for type python")
        for name in SCENES[typ].required:
            if name not in params:
                raise EpisodeError(f"scene {index} ({typ}): missing {name}")
        for name in ("count", "count_from", "total", "highlight"):
            if name in params and params[name] > DOT_CAP:
                raise EpisodeError(f"scene {index}: {name} must be <= {DOT_CAP}, the dot grid")
        if typ == "compare" and params["highlight"] > params["total"]:
            raise EpisodeError(f"scene {index}: highlight cannot be larger than total")
    ident = raw.get("id")
    if ident is not None and not isinstance(ident, str):
        raise EpisodeError(f"scene {index}: id must be a string")
    return Scene(typ, caption, keys, vo, minimum, params, entry if isinstance(entry, str) else None, green, ident, overrun)


def load_episode(path: str | Path) -> Episode:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise EpisodeError(f"episode not found: {source}")
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise EpisodeError(f"could not parse {source.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise EpisodeError(f"{source.name} must be a YAML mapping")
    version = data.get("version", 1)
    if version != 1:
        raise EpisodeError("only episode version 1 is supported")
    audio_mode = str(data.get("audio_mode", "voiceover"))
    if audio_mode not in {"voiceover", "ambient", "silent"}:
        raise EpisodeError("audio_mode must be voiceover, ambient, or silent")
    style = str(data.get("style") or HOUSE)
    if style not in PRESETS:
        raise EpisodeError("style must be house, vox-explainer, or history-story")
    language = str(data.get("language") or "en-US")
    voice = data.get("voice") or _VOICES.get(language, "")
    if not isinstance(voice, str) or (audio_mode == "voiceover" and not voice.strip()):
        raise EpisodeError("set voice (for example id-ID-ArdiNeural) or a known language (en-US, id-ID)")
    rate = str(data.get("rate") or "-8%")
    if not _RATE.fullmatch(rate):
        raise EpisodeError(f"rate must be a signed percentage such as -8% or +0%, got {rate!r}", field="rate")
    name = str(data.get("name") or source.stem)
    if not _NAME.match(name):
        raise EpisodeError("name must be letters, numbers, hyphens, and underscores")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list) or not raw_scenes:
        raise EpisodeError("scenes must be a non-empty list")
    episode_overrun = data.get("vo_overrun", False)
    if not isinstance(episode_overrun, bool):
        raise EpisodeError("vo_overrun must be true or false")
    scenes = [_scene(item, i + 1, audio_mode, style, episode_overrun) for i, item in enumerate(raw_scenes)]
    poster = data.get("poster")
    if poster is not None:
        if isinstance(poster, bool) or not isinstance(poster, int) or not 0 <= poster < len(scenes):
            raise EpisodeError(f"poster must be a scene index from 0 to {len(scenes) - 1}")
    font_dir = data.get("font_dir")
    if font_dir is not None:
        font_path = Path(str(font_dir))
        if not font_path.is_absolute():
            font_path = source.parent / font_path
        if not font_path.is_dir():
            raise EpisodeError(f"font_dir not found: {font_path}")
        font_dir = str(font_path.resolve())
    bg, white, green = BG, WHITE, GREEN
    palette = data.get("palette")
    if palette is not None:
        if not isinstance(palette, dict):
            raise EpisodeError("palette must be a mapping of bg, white, green")
        if "bg" in palette:
            bg = _rgb(palette["bg"], "bg")
        if "white" in palette:
            white = _rgb(palette["white"], "white")
        if "green" in palette:
            green = _rgb(palette["green"], "green")
    output = data.get("output")
    if output is not None and not isinstance(output, str):
        raise EpisodeError("output must be a file path")
    music = data.get("music")
    if music is not None:
        if not isinstance(music, str) or not music.strip():
            raise EpisodeError("music must be a path to an audio file")
        music_path = Path(music)
        if not music_path.is_absolute():
            music_path = source.parent / music_path
        if not music_path.is_file():
            raise EpisodeError(f"music not found: {music_path}")
        music = str(music_path.resolve())
    if "loudness" in data:
        loudness = data.get("loudness")
        if loudness is not None:
            if isinstance(loudness, bool) or not isinstance(loudness, (int, float)) or not math.isfinite(loudness):
                raise EpisodeError("loudness must be a LUFS number, for example -21")
            if not -40 <= float(loudness) <= -5:
                raise EpisodeError("loudness must be between -40 and -5 LUFS")
            loudness = float(loudness)
    else:
        loudness = RULES.get(style, {}).get("loudness")
    delivery = str(data.get("format") or "vertical_9x16")
    try:
        get_profile(delivery)
    except KeyError as exc:
        raise EpisodeError(str(exc)) from exc
    return Episode(
        name=name,
        language=language,
        voice=voice.strip(),
        rate=rate,
        scenes=scenes,
        source_dir=source.parent,
        source_path=source,
        poster=poster,
        output=output,
        font_dir=font_dir,
        bg=bg,
        white=white,
        green=green,
        format=delivery,
        audio_mode=audio_mode,
        style=style,
        vo_overrun=episode_overrun,
        music=music,
        loudness=loudness,
    )


def resolve_output(episode: Episode, override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    if episode.output:
        path = Path(episode.output)
        if not path.is_absolute():
            path = episode.source_dir / path
        return path.resolve()
    return (Path.cwd() / "out" / f"{episode.name}.mp4").resolve()
