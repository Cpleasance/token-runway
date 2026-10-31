import json

from token_runway.injector.config_injector import (
    build_mcp_entry,
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


def test_inject_rejects_malformed_json_safely(tmp_path):
    target = tmp_path / "corrupted_config.json"
    corrupted_content = '{\n  "mcpServers": { "bad": \n'
    target.write_text(corrupted_content, encoding="utf-8")

    # Must raise ValueError and NOT overwrite the original content
    try:
        inject_into_file(target, entry_name="token-runway", mode="uvx")
        assert False, "Should have raised ValueError on malformed JSON"
    except ValueError as e:
        assert "Refusing to overwrite malformed JSON" in str(e)

    assert target.read_text(encoding="utf-8") == corrupted_content


def test_inject_creates_backup_and_rejects_non_dict(tmp_path):
    # Non-dict root
    target = tmp_path / "array_config.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    try:
        inject_into_file(target, entry_name="token-runway", mode="uvx")
        assert False, "Should have raised ValueError on non-dict root"
    except ValueError as e:
        assert "must have a JSON object at its root" in str(e)

    # Valid existing file creates backup
    valid_target = tmp_path / "valid_config.json"
    initial_content = '{"mcpServers": {"old": {"command": "old"}}}'
    valid_target.write_text(initial_content, encoding="utf-8")

    assert inject_into_file(valid_target, entry_name="token-runway", mode="uvx")
    backup = valid_target.with_suffix(".json.bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == initial_content
