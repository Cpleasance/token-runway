import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from token_runway.viewer.dashboard import DashboardRequestHandler, start_dashboard


def test_dashboard_http_endpoints():
    # Bind to ephemeral port 0
    server = HTTPServer(("127.0.0.1", 0), DashboardRequestHandler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # 1. GET /
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "Token Runway" in content
            assert "Assess Action Simulator" in content
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"

        # 2. GET /api/status (loopback safe origin)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status") as resp:
            assert resp.status == 200
            assert resp.headers.get("Access-Control-Allow-Origin") is None
            data = json.loads(resp.read().decode("utf-8"))
            assert "readings" in data

        # 3. GET /api/status from untrusted external Origin -> 403 Forbidden
        bad_req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/status",
            headers={"Origin": "https://malicious.example.com"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_req)
        assert exc_info.value.code == 403
        exc_info.value.close()

        # 4. POST /api/assess (valid)
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/assess",
            data=json.dumps({"action_type": "targeted_edit", "intensity": "low"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            advice = json.loads(resp.read().decode("utf-8"))
            assert "verdict" in advice
            assert advice["verdict"] in (
                "proceed",
                "proceed_with_caution",
                "downgrade_strategy",
                "pause_or_downgrade",
                "unknown",
                "reject",
            )

        # 5. POST /api/assess with malformed JSON -> 400
        req_bad_json = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/assess",
            data=b"not valid json {{{",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_bad_json)
        assert exc_info.value.code == 400
        exc_info.value.close()

        # 6. POST /api/assess with non-dict JSON -> 400
        req_arr_json = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/assess",
            data=json.dumps([1, 2, 3]).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_arr_json)
        assert exc_info.value.code == 400
        exc_info.value.close()

        # 7. POST /api/assess with invalid intensity -> 400
        req_bad_int = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/assess",
            data=json.dumps({"intensity": "extreme"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_bad_int)
        assert exc_info.value.code == 400
        exc_info.value.close()

        # 8. POST /api/assess with unknown provider -> 400
        req_bad_prov = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/assess",
            data=json.dumps({"provider": "unknown_ai"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_bad_prov)
        assert exc_info.value.code == 400
        exc_info.value.close()

        # 9. POST /api/assess with oversized body (>64KB) -> 413
        oversized_data = b"x" * (65 * 1024)
        req_huge = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/assess",
            data=oversized_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_huge)
        assert exc_info.value.code == 413
        exc_info.value.close()

    finally:
        server.shutdown()
        server.server_close()


def test_dashboard_loopback_restriction():
    with pytest.raises(ValueError) as exc:
        start_dashboard(host="0.0.0.0")
    assert "prohibited for security" in str(exc.value)

