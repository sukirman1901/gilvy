# T2 read-only capability doctor

## Contract

`gilvy doctor` and `gilvy doctor --json` emit the same JSON object.
`gilvy.capabilities.capability_report()` is the shared, serializable API.
Schema version 1 has `schema_version`, `ok`, `read_only`, and `checks`.
Each check has stable `id`, `required`, `status`, `verification`, `detail`, and
`suggestion` fields. Status values are `present`, `missing`, `unknown` (inspection
failed), and `unverified` (deliberately not exercised).

Exit 0 / `ok: true` means required discovery checks passed. Exit 1 means a
required check is missing/unknown; optional failures do not fail the installation.
This does not certify rendering, downloading, neural TTS, or inference.

Checks cover Python >=3.11, FFmpeg/ffprobe on PATH, core Python modules, bundled
fonts and guidance, optional yt-dlp/rembg/onnxruntime module discovery, and the
default u2net model path (`U2NET_HOME/u2net.onnx`, default `~/.u2net/u2net.onnx`).
Discovery intentionally does not import optional modules: import compatibility
is unverified, even when a module is discoverable. File presence is not model
integrity. Inference always reports `unverified`. No network calls, subprocesses,
model loading, cache creation, installs, or downloads occur inside the API.

## Installation evidence, not universal requirements

The parent audit recorded a successful installation on this Intel environment
using **numba 0.61.2 / llvmlite 0.44.0**, and a successful real u2net CPU inference
with 128x128 RGBA output. Those are observed compatibility pins for this host,
not universal package requirements. This change does not alter dependency pins.
Doctor does not repeat that inference or treat historical evidence as current
runtime readiness.

## Resolved package import blocker

`src/gilvy/__init__.py` previously imported `draw` eagerly, which imported Pillow
before the CLI or shared doctor module could load. Ownership was expanded to
this file and the exports are now lazy, enabling diagnostics in an installation
missing Pillow/NumPy. `__version__` and `__all__` are preserved; the resolver is:

```python
def __getattr__(name):
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
```

`tests/test_capabilities.py::test_doctor_runs_without_site_packages_or_runtime_imports`
is the passing fresh-process `python -S` regression for this blocker. A second
fresh-process test verifies normal `from gilvy import Ctx, Theme, eo` identity,
all wildcard exports, cached access, version, and unknown-attribute behavior.

## Proposed MCP wrapper (controller/engine owner only)

Add to `src/gilvy/mcp_server.py`, following its existing JSON-string convention:

```python
@mcp.tool()
def doctor() -> str:
    """Read-only local prerequisites; presence does not verify runtime readiness."""
    from gilvy.capabilities import capability_report

    return json.dumps(capability_report(), indent=2)
```

Proposed focused wrapper test (controller-owned MCP tests):

```python
def test_mcp_doctor_preserves_shared_report(monkeypatch):
    import json
    from gilvy import capabilities, mcp_server

    for ok in (True, False):
        expected = {
            "schema_version": 1, "ok": ok, "read_only": True,
            "checks": [{"id": "cutout.inference", "required": False,
                        "status": "unverified", "verification": "not_run",
                        "detail": "No inference executed.", "suggestion": ""}],
        }
        monkeypatch.setattr(capabilities, "capability_report", lambda: expected)
        assert json.loads(mcp_server.doctor()) == expected
```

In the controller's fresh MCP smoke, assert `doctor` is listed and that calling
it returns JSON with `schema_version == 1` and `cutout.inference` unverified.
The existing MCP module itself still imports rendering dependencies; full MCP
startup in a broken core environment is outside this wrapper's guarantee.

## TDD evidence

- Initial RED: ` .venv/bin/python -m pytest tests/test_capabilities.py -q`:
  7 failed (shared API absent; CLI could not emit dependency-free JSON).
- Initial implementation: 6 passed, 1 failed, exposing the package-import blocker.
- Expanded-ownership RED: 6 passed, 2 failed, including the new lazy public-export
  compatibility regression.
- Final GREEN: `.venv/bin/python -m pytest tests/test_capabilities.py -q`:
  **8 passed in 0.29s**, including both fresh-process import checks.
- Installed CLI smoke: exit 0, `ok: true`, 24 checks, with cutout inference
  explicitly `unverified`.
- Focused coverage: simulated present/missing dependencies, actionable missing
  core/resources, optional absence not failing core, fake model presence not
  proving inference, JSON round-trip and CLI parity/exit codes, dependency-free
  fresh process. No broad suite or inference was run by this writer.
