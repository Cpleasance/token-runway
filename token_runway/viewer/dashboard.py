"""Zero-dependency local Web HUD dashboard for Token Runway."""

from __future__ import annotations

import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from token_runway.server.advice import evaluate_action_feasibility
from token_runway.sources import fetch_all_runways

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Token Runway 🛫 Live HUD</title>
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #3fb950;
      --yellow: #d29922;
      --red: #f85149;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 24px;
      line-height: 1.5;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .title {
      font-size: 24px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .status-badge {
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 12px;
      background: rgba(63, 185, 80, 0.15);
      color: var(--green);
      font-weight: 600;
      border: 1px solid var(--green);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .card:hover {
      border-color: #58a6ff55;
    }
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 16px;
    }
    .card-title {
      font-size: 18px;
      font-weight: 600;
      color: #fff;
    }
    .card-plan {
      font-size: 12px;
      color: var(--text-muted);
      background: #21262d;
      padding: 2px 8px;
      border-radius: 6px;
    }
    .window-item {
      margin-bottom: 14px;
    }
    .window-item:last-child {
      margin-bottom: 0;
    }
    .window-meta {
      display: flex;
      justify-content: space-between;
      font-size: 13px;
      margin-bottom: 6px;
    }
    .window-name {
      font-weight: 500;
    }
    .window-val {
      font-weight: 600;
    }
    .progress-bar-bg {
      background: #21262d;
      border-radius: 4px;
      height: 8px;
      overflow: hidden;
    }
    .progress-bar-fill {
      height: 100%;
      border-radius: 4px;
      transition: width 0.4s ease;
    }
    .bg-green { background: var(--green); }
    .bg-yellow { background: var(--yellow); }
    .bg-red { background: var(--red); }
    .bg-gray { background: #484f58; }
    .countdown {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 4px;
    }
    .advisor-section {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 24px;
    }
    .advisor-title {
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .advisor-form {
      display: flex;
      gap: 12px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    select, input, button {
      background: #21262d;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 14px;
    }
    button {
      background: #238636;
      color: #fff;
      font-weight: 600;
      cursor: pointer;
      border: none;
    }
    button:hover {
      background: #2ea043;
    }
    .verdict-box {
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 16px;
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 13px;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">
      <span>🛫 Token Runway</span>
      <span class="status-badge" id="live-indicator">LIVE POLLING (5s)</span>
    </div>
    <div style="font-size: 13px; color: var(--text-muted);" id="last-updated">Updating...</div>
  </div>

  <div class="grid" id="providers-grid">
    <div style="color: var(--text-muted); padding: 20px;">Harvesting active token runways...</div>
  </div>

  <div class="advisor-section">
    <div class="advisor-title">🧠 Assess Action Simulator</div>
    <div class="advisor-form">
      <select id="action-type">
        <option value="subagent_fanout">Subagent Fanout (Parallel Workers)</option>
        <option value="large_file_dump">Large File Context Ingestion</option>
        <option value="deep_research">Deep Multi-turn Research</option>
        <option value="targeted_edit">Targeted File Edit (Lightweight)</option>
      </select>
      <select id="action-intensity">
        <option value="low">Low Intensity</option>
        <option value="medium" selected>Medium Intensity</option>
        <option value="high">High Intensity</option>
      </select>
      <button onclick="runAssessAction()">Assess Feasibility</button>
    </div>
    <div class="verdict-box" id="verdict-result">
      Select an action and click "Assess Feasibility" to test Token Runway advice.
    </div>
  </div>

  <script>
    async function loadStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        renderDashboard(data);
      } catch (err) {
        document.getElementById('last-updated').innerText = 'Connection error: ' + err.message;
      }
    }

    function renderDashboard(data) {
      document.getElementById('last-updated').innerText = 'Last refreshed: ' + new Date().toLocaleTimeString();
      const grid = document.getElementById('providers-grid');
      grid.innerHTML = '';

      const readings = data.readings || {};
      for (const [key, r] of Object.entries(readings)) {
        const card = document.createElement('div');
        card.className = 'card';

        let windowsHtml = '';
        if (!r.available) {
          const err = r.error_message || 'Unavailable';
          windowsHtml = `<div style="color: var(--text-muted); font-size: 13px;">${err}</div>`;
        } else if (!r.windows || r.windows.length === 0) {
          windowsHtml = '<div style="color: var(--text-muted); font-size: 13px;">No active quotas reported.</div>';
        } else {
          for (const w of r.windows) {
            const pct = w.used_pct != null ? w.used_pct : 0;
            let barColor = 'bg-green';
            if (pct >= 90) barColor = 'bg-red';
            else if (pct >= 75) barColor = 'bg-yellow';

            let countInfo = '';
            if (w.remaining_count != null && w.total_entitlement != null) {
              countInfo = ` [${w.remaining_count}/${w.total_entitlement}]`;
            } else if (w.remaining_count != null) {
              countInfo = ` [${w.remaining_count}]`;
            }

            let countdownStr = '';
            if (w.resets_in_minutes != null) {
              const hrs = Math.floor(w.resets_in_minutes / 60);
              const mins = w.resets_in_minutes % 60;
              countdownStr = `<div class="countdown">Resets in ${hrs > 0 ? hrs + 'h ' : ''}${mins}m</div>`;
            }

            windowsHtml += `
              <div class="window-item">
                <div class="window-meta">
                  <span class="window-name">${w.name}</span>
                  <span class="window-val">${w.used_pct != null ? w.used_pct + '%' : '-'}${countInfo}</span>
                </div>
                <div class="progress-bar-bg">
                  <div class="progress-bar-fill ${barColor}" style="width: ${pct}%"></div>
                </div>
                ${countdownStr}
              </div>
            `;
          }
        }

        card.innerHTML = `
          <div class="card-header">
            <span class="card-title">${r.display_name}</span>
            ${r.plan ? `<span class="card-plan">${r.plan}</span>` : ''}
          </div>
          ${windowsHtml}
        `;
        grid.appendChild(card);
      }
    }

    async function runAssessAction() {
      const type = document.getElementById('action-type').value;
      const intensity = document.getElementById('action-intensity').value;
      const out = document.getElementById('verdict-result');
      out.innerText = 'Evaluating against live quotas...';

      try {
        const res = await fetch('/api/assess', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action_type: type, intensity: intensity })
        });
        const result = await res.json();
        out.innerText = JSON.stringify(result, null, 2);
      } catch (err) {
        out.innerText = 'Error assessing action: ' + err.message;
      }
    }

    loadStatus();
    setInterval(loadStatus, 5000);
  </script>
</body>
</html>
"""


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP request handler for the Token Runway Web HUD."""

    server_version = "TokenRunway/0.2.2"

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard HTTP server access logs to keep terminal quiet."""
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if parsed.path == "/api/status":
            readings = fetch_all_runways()
            payload = {
                "readings": {k: v.to_dict() for k, v in readings.items()},
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/assess":
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                data = {}

            readings = fetch_all_runways()
            advice = evaluate_action_feasibility(
                readings,
                action_type=data.get("action_type", "general"),
                intensity=data.get("intensity", "medium"),
                target_provider=data.get("provider"),
            )

            body = json.dumps(advice).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")


def start_dashboard(host: str = "127.0.0.1", port: int = 7890, open_browser: bool = True) -> None:
    """Start web dashboard server."""
    server = HTTPServer((host, port), DashboardRequestHandler)
    url = f"http://{host}:{port}/"
    print("\n\033[1;36m=== Token Runway: Web HUD ===\033[0m")
    print(f"Dashboard running at: \033[1;32m{url}\033[0m")
    print("Press Ctrl+C to stop.\n")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard server.")
    finally:
        server.server_close()
