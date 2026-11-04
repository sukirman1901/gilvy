"""Read-only, standard-library-only installation diagnostics.

Discovery is not execution: no imports of optional packages, model loading,
subprocesses, downloads, cache creation, or network requests occur here.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import sys
from pathlib import Path


def capability_report() -> dict:
    """Return schema v1; ``ok`` means required discovery checks passed only.

    Checks have stable ids, required/status/verification/detail/suggestion fields.
    Status is present, missing, unknown (inspection failed), or unverified
    (deliberately not tested). Optional failures do not change ``ok``.
    """
    checks = []

    def add(key, required, status, verification, detail, suggestion=""):
        checks.append(dict(id=key, required=required, status=status,
                           verification=verification, detail=detail,
                           suggestion=suggestion))

    supported = sys.version_info >= (3, 11)
    add("python", True, "present" if supported else "missing", "version_check",
        f"Python {platform.python_version()} ({platform.machine()}); {sys.executable}",
        "" if supported else "Use Python 3.11 or newer.")
    for name in ("ffmpeg", "ffprobe"):
        path = shutil.which(name)
        add(f"binary.{name}", True, "present" if path else "missing", "path_lookup_only",
            path or f"{name} not found on PATH; execution was not tested.",
            "" if path else f"Install FFmpeg including {name}, and put it on PATH.")

    modules = {
        "PIL": None, "numpy": None, "yaml": None, "edge_tts": None, "mcp": None,
        "yt_dlp": "download", "rembg": "cutout", "onnxruntime": "cutout",
    }
    for name, extra in modules.items():
        try:
            status = "present" if importlib.util.find_spec(name) is not None else "missing"
            detail = f"{name}: module discovery only; import and runtime compatibility unverified."
        except (ImportError, ValueError, OSError) as exc:
            status, detail = "unknown", f"{name}: module discovery failed: {exc}"
        install = f"gilvy[{extra}]" if extra else "gilvy"
        add(f"module.{name}", extra is None, status, "module_discovery_only", detail,
            "" if status == "present" else f"Install/repair {install} in this Python environment.")

    resources = (
        "DIRECTING.md", "MOTION_REFERENCE.md", "PRODUCT_MOTION.md",
        "COMPOSITION_RUNTIME.md", "REFERENCE_STYLES.md", "COLLAGE.md",
        "fonts/Poppins-Light.ttf", "fonts/Poppins-Regular.ttf",
        "fonts/Poppins-Medium.ttf", "fonts/Poppins-SemiBold.ttf",
        "fonts/LiberationSerif-Regular.ttf",
    )
    root = Path(__file__).resolve().parent
    model = Path(os.environ.get("U2NET_HOME", str(Path.home() / ".u2net"))).expanduser() / "u2net.onnx"
    for key, path, required in [
        *((f"resource.{name}", root / name, True) for name in resources),
        ("cutout.model", model, False),
    ]:
        try:
            status = "present" if path.is_file() else "missing"
            detail = f"{path}; file presence only, contents unverified."
        except OSError as exc:
            status, detail = "unknown", f"Cannot inspect {path}: {exc}"
        suggestion = ("Repair the Gilvy installation to restore bundled resources." if required
                      else "Provision u2net.onnx in U2NET_HOME (default ~/.u2net) before offline cutout use.")
        add(key, required, status, "file_presence_only", detail,
            "" if status == "present" else suggestion)
    add("cutout.inference", False, "unverified", "not_run",
        "No model loaded or inference executed; a present model may be corrupt or incompatible.",
        "Validate a local cutout separately to establish inference readiness.")
    return {
        "schema_version": 1,
        "ok": all(item["status"] == "present" for item in checks if item["required"]),
        "read_only": True,
        "checks": checks,
    }
