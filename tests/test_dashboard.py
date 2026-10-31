import json
import threading
import urllib.request
from http.server import HTTPServer

from token_runway.viewer.dashboard import DashboardRequestHandler


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

        # 2. GET /api/status
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status") as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "readings" in data

        # 3. POST /api/assess
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

    finally:
        server.shutdown()
        server.server_close()
