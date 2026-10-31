"""Zero-dependency local Web HUD dashboard for Token Runway."""

from __future__ import annotations

import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from token_runway.server.advice import evaluate_action_feasibility
from token_runway.server.server import SUPPORTED_PROVIDERS
from token_runway.sources import fetch_all_runways
from token_runway.sources.base import ProviderReading

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
    <div>
      <div class="title">
        <span>🛫 Token Runway</span>
        <span class="status-badge" id="live-indicator">LIVE POLLING (5s)</span>
      </div>
      <div style="font-size: 13px; color: var(--text-muted); margin-top: 4px;">
        Real-time provider rate-limit windows, quotas & credit limits. (Does not tally session token volume).
      </div>
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
    function escapeHtml(str) {
      if (str == null) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

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
          const err = escapeHtml(r.error_message || 'Unavailable');
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
              countInfo = ` [${escapeHtml(w.remaining_count)}/${escapeHtml(w.total_entitlement)}]`;
            } else if (w.remaining_count != null) {
              countInfo = ` [${escapeHtml(w.remaining_count)}]`;
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
                  <span class="window-name">${escapeHtml(w.name)}</span>
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
            <span class="card-title">${escapeHtml(r.display_name)}</span>
            ${r.plan ? `<span class="card-plan">${escapeHtml(r.plan)}</span>` : ''}
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


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_REQUEST_BODY_SIZE = 64 * 1024  # 64 KB maximum payload limit


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP request handler for the Token Runway Web HUD."""

    server_version = "TokenRunway/0.2.4"
    _cached_readings: Optional[Dict[str, ProviderReading]] = None
    _cache_timestamp: float = 0.0
    _cache_ttl: float = 4.0

    @classmethod
    def _get_cached_readings(cls, max_age: float = 4.0) -> Dict[str, ProviderReading]:
        """Serve cached snapshot to avoid flooding provider CLIs/APIs on rapid polling."""
        now = time.time()
        if cls._cached_readings is not None and (now - cls._cache_timestamp) < max_age:
            return cls._cached_readings
        cls._cached_readings = fetch_all_runways()
        cls._cache_timestamp = now
        return cls._cached_readings

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard HTTP server access logs to keep terminal quiet."""
        pass

    def _is_safe_origin(self) -> bool:
        """Protect against unauthorized cross-origin access from external websites."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            parsed = urllib.parse.urlparse(origin)
            return parsed.hostname in LOOPBACK_HOSTS
        except Exception:
            return False

    def _send_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _send_json_error(self, code: int, message: str) -> None:
        """Return standardized JSON error response."""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))

    def do_GET(self) -> None:
        if not self._is_safe_origin():
            self.send_error(403, "Forbidden: Cross-origin access from external origins is blocked.")
            return

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        if parsed.path == "/api/status":
            readings = self._get_cached_readings()
            payload = {
                "readings": {k: v.to_dict() for k, v in readings.items()},
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        if not self._is_safe_origin():
            self.send_error(403, "Forbidden: Cross-origin access from external origins is blocked.")
            return

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/assess":
            # 1. Enforce content-length limits
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                self._send_json_error(400, "Invalid Content-Length header.")
                return

            if length < 0:
                self._send_json_error(400, "Invalid Content-Length header.")
                return

            if length > MAX_REQUEST_BODY_SIZE:
                self._send_json_error(413, "Payload exceeds maximum allowed size (64KB).")
                return

            raw_body = self.rfile.read(length) if length > 0 else b"{}"

            # 2. Validate JSON syntax and structure
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                self._send_json_error(400, "Malformed JSON payload.")
                return

            if not isinstance(data, dict):
                self._send_json_error(400, "Request body must be a JSON object.")
                return

            # 3. Validate parameter types and values
            action_type = data.get("action_type", "general")
            if not isinstance(action_type, str) or not action_type.strip():
                self._send_json_error(400, "Field 'action_type' must be a non-empty string.")
                return

            intensity = data.get("intensity", "medium")
            if not isinstance(intensity, str) or intensity.lower() not in ("low", "medium", "high"):
                self._send_json_error(400, "Field 'intensity' must be one of: 'low', 'medium', 'high'.")
                return

            provider = data.get("provider")
            if provider is not None:
                if not isinstance(provider, str) or not provider.strip():
                    self._send_json_error(400, "Field 'provider' must be a non-empty string.")
                    return
                prov_clean = provider.lower().strip()
                if prov_clean not in SUPPORTED_PROVIDERS:
                    self._send_json_error(
                        400,
                        f"Unknown provider '{provider}'. Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}.",
                    )
                    return
            else:
                prov_clean = None

            readings = self._get_cached_readings()
            advice = evaluate_action_feasibility(
                readings,
                action_type=action_type,
                intensity=intensity,
                target_provider=prov_clean,
            )

            body = json.dumps(advice).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")


def start_dashboard(host: str = "127.0.0.1", port: int = 7890, open_browser: bool = True) -> None:
    """Start web dashboard server bound strictly to loopback."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            f"Binding dashboard to '{host}' is prohibited for security. "
            "The Token Runway dashboard has no authentication mechanism and must run loopback-only (127.0.0.1 / localhost)."
        )

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
