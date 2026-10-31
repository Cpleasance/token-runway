import json
from token_runway.injector.config_injector import (
    build_mcp_entry,
    get_ide_config_targets,
    inject_into_file,
)


def test_build_mcp_entry():
    entry_uvx = build_mcp_entry("uvx")
    assert entry_uvx["command"] == "uvx"
    assert entry_uvx["args"] == ["token-runway"]


def test_inject_into_file(tmp_path):
    target = tmp_path / "claude_desktop_config.json"

    # 1. Inject into fresh file
    assert inject_into_file(target, entry_name="token-runway", mode="uvx")
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "token-runway" in data["mcpServers"]
    assert data["mcpServers"]["token-runway"]["command"] == "uvx"

    # 2. Existing config preservation
    data["mcpServers"]["custom-server"] = {"command": "custom"}
    target.write_text(json.dumps(data), encoding="utf-8")

    assert inject_into_file(target, entry_name="token-runway", mode="uvx")
    updated = json.loads(target.read_text(encoding="utf-8"))
    assert "token-runway" in updated["mcpServers"]
    assert "custom-server" in updated["mcpServers"]
