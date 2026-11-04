"""Read-only doctor contract, including incomplete installations."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def doctor():
    assert importlib.util.find_spec("gilvy.capabilities") is not None, "shared doctor API is missing"
    return importlib.import_module("gilvy.capabilities").capability_report


@pytest.fixture
def installed(monkeypatch, tmp_path):
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}")
    original = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: original(name) if name.startswith("gilvy") else object())
    monkeypatch.setenv("U2NET_HOME", str(tmp_path / "models"))
    return tmp_path / "models"


def indexed(report):
    return {check["id"]: check for check in report["checks"]}


def test_present_prerequisites_do_not_claim_inference_readiness(installed):
    installed.mkdir()
    (installed / "u2net.onnx").write_bytes(b"not a valid model")
    report = doctor()()
    checks = indexed(report)
    assert report["schema_version"] == 1
    assert report["ok"] is True
    assert checks["cutout.model"]["status"] == "present"
    assert checks["cutout.inference"]["status"] == "unverified"
    assert checks["module.rembg"]["status"] == "present"
    assert checks["module.rembg"]["verification"] == "module_discovery_only"
    assert json.loads(json.dumps(report)) == report


def test_missing_optional_dependencies_do_not_fail_core(installed, monkeypatch):
    report_fn = doctor()
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None if name in {"yt_dlp", "rembg", "onnxruntime"} else object())
    report = report_fn()
    checks = indexed(report)
    assert report["ok"] is True
    for name in ("yt_dlp", "rembg", "onnxruntime"):
        assert checks[f"module.{name}"]["status"] == "missing"
        assert checks[f"module.{name}"]["suggestion"]
    assert checks["cutout.model"]["status"] == "missing"
    assert not installed.exists(), "doctor must not create the model cache"


def test_missing_core_tools_modules_and_resources_are_actionable(installed, monkeypatch):
    report_fn = doctor()
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda path: False)
    report = report_fn()
    checks = indexed(report)
    assert report["ok"] is False
    for key in ("binary.ffmpeg", "binary.ffprobe", "module.PIL", "resource.fonts/Poppins-Medium.ttf", "resource.DIRECTING.md"):
        assert checks[key]["required"] is True
        assert checks[key]["status"] == "missing"
        assert checks[key]["suggestion"]


@pytest.mark.parametrize("command", [["doctor"], ["doctor", "--json"]])
def test_cli_json_and_exit_code_match_shared_report(installed, capsys, command):
    expected = doctor()()
    from gilvy.cli import run
    assert run(command) == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_cli_missing_core_exits_one_with_valid_json(installed, monkeypatch, capsys):
    doctor()
    from gilvy.cli import run
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert run(["doctor", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_doctor_runs_without_site_packages_or_runtime_imports(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src"
    script = '''
import sys
from gilvy.cli import run
code = run(["doctor", "--json"])
assert not any(name in sys.modules for name in ("gilvy.render", "gilvy.assets", "rembg", "onnxruntime", "yt_dlp"))
raise SystemExit(code)
'''
    result = subprocess.run([sys.executable, "-S", "-c", script], env={**os.environ, "PYTHONPATH": str(source), "U2NET_HOME": str(tmp_path / "absent")}, capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert result.stdout.strip(), f"doctor failed before emitting JSON: {result.stderr}"
    report = json.loads(result.stdout)
    assert report["ok"] is False
    assert indexed(report)["module.PIL"]["status"] == "missing"
    assert not (tmp_path / "absent").exists()


def test_public_exports_remain_compatible_in_fresh_process():
    script = '''
import gilvy
assert "Ctx" not in vars(gilvy), "drawing exports should load lazily"
from gilvy import Ctx, Theme, eo
from gilvy.draw import Ctx as DrawingContext
from gilvy.theme import Theme as DrawingTheme
from gilvy.easing import eo as ease_out
assert (Ctx, Theme, eo) == (DrawingContext, DrawingTheme, ease_out)
assert gilvy.Ctx is Ctx
namespace = {}
exec("from gilvy import *", namespace)
assert set(gilvy.__all__).issubset(namespace)
assert all(namespace[name] is getattr(gilvy, name) for name in gilvy.__all__)
assert gilvy.__version__ == "0.1.0"
assert not hasattr(gilvy, "nonexistent_export")
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
