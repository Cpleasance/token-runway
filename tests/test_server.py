import json
from token_runway.server.server import TokenRunwayServer
from token_runway.sources.base import ProviderReading, QuotaWindow


def test_server_initialize():
    server = TokenRunwayServer()
    resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "token-runway"


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
