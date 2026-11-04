"""Faceless 9:16 explainers with a locked look and a declarative episode file."""

__version__ = "0.1.0"

__all__ = [
    "Ctx",
    "R",
    "Theme",
    "bundled_fonts",
    "cl",
    "coins_flow",
    "compose",
    "eexp",
    "eio",
    "eo",
    "grid",
    "lerp",
]


def __getattr__(name):
    """Keep diagnostics importable before rendering dependencies are installed."""
    from importlib import import_module

    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = (
        "draw" if name in {"Ctx", "coins_flow", "compose", "grid"}
        else "theme" if name in {"Theme", "bundled_fonts"}
        else "easing"
    )
    value = getattr(import_module(f"gilvy.{module}"), name)
    globals()[name] = value
    return value
