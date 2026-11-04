"""The MCP adapter preserves the capability agent's shared read-only contract."""
import json


def test_mcp_doctor_preserves_shared_read_only_contract(monkeypatch):
    from gilvy import mcp_server
    from gilvy import capabilities
    expected = {"schema_version": 1, "ok": False, "read_only": True, "checks": [
        {"id": "binary.ffmpeg", "status": "missing", "required": True},
        {"id": "cutout.inference", "status": "unverified", "verification": "not_run", "required": False}]}
    calls = []
    def report():
        calls.append(1)
        return expected
    monkeypatch.setattr(capabilities, "capability_report", report)
    assert json.loads(mcp_server.doctor()) == expected
    assert calls == [1]
