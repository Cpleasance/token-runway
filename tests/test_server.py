from token_runway import __version__
from token_runway.server.server import TokenRunwayServer
from token_runway.sources.base import ProviderReading, QuotaWindow


def test_server_initialize():
    server = TokenRunwayServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "token-runway"
    assert resp["result"]["serverInfo"]["version"] == __version__


def test_server_reject_invalid_arguments():
    server = TokenRunwayServer()
    server._cached_readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=10)],
        )
    }

    # 1. Invalid refresh type (string instead of boolean)
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "check_runway", "arguments": {"refresh": "false"}},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32602
    assert "refresh' must be a boolean" in resp["error"]["message"]

    # 2. Unknown provider name in check_runway
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {"name": "check_runway", "arguments": {"provider": "unknown_ai"}},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32602
    assert "Unknown provider" in resp["error"]["message"]

    # 3. Invalid intensity in assess_action
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 12,
        "method": "tools/call",
        "params": {"name": "assess_action", "arguments": {"intensity": "extreme"}},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32602
    assert "Invalid intensity" in resp["error"]["message"]

    # 4. Invalid strict argument type (string "false" instead of boolean false)
    resp = server.handle_request({
        "jsonrpc": "2.0",
        "id": 13,
        "method": "tools/call",
        "params": {"name": "assess_action", "arguments": {"strict": "false"}},
    })
    assert "error" in resp
    assert resp["error"]["code"] == -32602
    assert "Argument 'strict' must be a boolean" in resp["error"]["message"]


def test_server_tools_list():
    server = TokenRunwayServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "check_runway" in tool_names
    assert "assess_action" in tool_names


def test_server_resources_and_prompts():
    server = TokenRunwayServer()
    # Mock cached reading
    server._cached_readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=10)],
        )
    }
    server._cache_time = 9999999999.0

    # Resource list
    r_list = server.handle_request({"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}})
    assert len(r_list["result"]["resources"]) == 1

    # Resource read
    r_read = server.handle_request(
        {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "runway://status"}}
    )
    assert r_read["result"]["contents"][0]["mimeType"] == "application/json"

    # Prompt list & get
    p_list = server.handle_request({"jsonrpc": "2.0", "id": 5, "method": "prompts/list", "params": {}})
    assert len(p_list["result"]["prompts"]) == 1

    p_get = server.handle_request(
        {"jsonrpc": "2.0", "id": 6, "method": "prompts/get", "params": {"name": "runway_governance"}}
    )
    assert "messages" in p_get["result"]
