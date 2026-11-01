"""Load the vendored renderer and run its scene functions on either backend."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from gilvy.draw import coins_flow, load_font
from gilvy.easing import R, cl, eexp, eio, eo, lerp
from gilvy.theme import BG, CX, GREEN, WHITE, bundled_fonts

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_original():
    path = FIXTURES / "original_lib.py"
    spec = importlib.util.spec_from_file_location("gilvy_original_lib", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._fc.clear()
    return module


def _gilvy_font(weight, size):
    return load_font(str(bundled_fonts()), weight, size, 2)


def namespace(original=None) -> dict:
    if original is not None:
        return {
            "eo": original.eo,
            "eio": original.eio,
            "eexp": original.eexp,
            "R": original.R,
            "cl": original.cl,
            "lerp": original.lerp,
            "F": original.F,
            "CX": original.CX,
            "GR": original.GR,
            "WH": original.WH,
            "BG": original.BG,
            "coins_flow": original.coins_flow,
            "math": original.math,
        }
    import math

    return {
        "eo": eo,
        "eio": eio,
        "eexp": eexp,
        "R": R,
        "cl": cl,
        "lerp": lerp,
        "F": _gilvy_font,
        "CX": CX,
        "GR": GREEN,
        "WH": WHITE,
        "BG": BG,
        "coins_flow": coins_flow,
        "math": math,
    }


def load_scene(name: str, ns: dict):
    source = (FIXTURES / name).read_text(encoding="utf-8")
    scope = dict(ns)
    exec(source, scope)
    return scope["SC"]
