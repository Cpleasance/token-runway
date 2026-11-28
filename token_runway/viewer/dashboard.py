"""Zero-dependency local web dashboard for Token Runway."""

from __future__ import annotations

import json
import socket
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

from token_runway.server.advice import evaluate_action_feasibility
from token_runway.server.server import SUPPORTED_PROVIDERS
from token_runway.sources import fetch_all_runways
from token_runway.sources.base import ProviderReading

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark">
  <title>Token Runway · Usage &amp; Limits</title>
  <style>
    :root {
      --bg: #0a0a0a;
      --surface: #111111;
      --surface-hover: #161616;
      --border: #222222;
      --border-strong: #333333;
      --text: #ededed;
      --text-muted: #888888;
      --text-faint: #555555;
      --track: #1c1c1c;

      --green: #45a557;
      --amber: #d39b2b;
      --red: #e5484d;

      --radius: 5px;
      --mono: ui-monospace, "SF Mono", "Geist Mono", Menlo, Consolas, monospace;
      --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body {
      height: 100vh;
      overflow: hidden;
      background: var(--bg);
      color: var(--text);
      font: 12px/1.4 var(--sans);
      font-feature-settings: "tnum", "cv11";
      -webkit-font-smoothing: antialiased;
    }

    body {
      display: flex;
      flex-direction: column;
    }

    header {
      height: 38px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      flex-shrink: 0;
    }
    .crumbs { display: flex; align-items: center; gap: 6px; font-size: 12px; }
    .crumbs .name { font-weight: 600; letter-spacing: -0.01em; color: var(--text); }
    .crumbs .tag {
      font-family: var(--mono);
      font-size: 10px;
      color: var(--text-muted);
      border: 1px solid var(--border);
      border-radius: 3px;
      padding: 0 4px;
      line-height: 15px;
    }
    .crumbs .sep { color: var(--text-faint); }
    .header-right { display: flex; align-items: center; gap: 10px; }
    .sync-text { font-size: 11px; color: var(--text-muted); font-family: var(--mono); }

    .btn {
      height: 22px;
      padding: 0 7px;
      border-radius: var(--radius);
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      font-size: 11px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .btn:hover { background: var(--surface-hover); border-color: var(--border-strong); }
    kbd {
      font-family: var(--mono);
      font-size: 9px;
      color: var(--text-muted);
      border: 1px solid var(--border);
      border-radius: 2px;
      padding: 0 3px;
      line-height: 12px;
    }

    main {
      flex: 1;
      width: 100%;
      max-width: 1280px;
      margin: 0 auto;
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      overflow: hidden;
    }

    .head-row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      flex-shrink: 0;
    }
    .head-row h1 { font-size: 13px; font-weight: 600; letter-spacing: -0.01em; }
    .head-row p { font-size: 11px; color: var(--text-muted); font-family: var(--mono); }

    .provider-columns {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
      overflow-y: auto;
      max-height: calc(100vh - 90px);
    }
    .provider-columns::-webkit-scrollbar { width: 5px; height: 5px; }
    .provider-columns::-webkit-scrollbar-track { background: var(--bg); }
    .provider-columns::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

    .prov-col {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      transition: border-color 0.12s ease;
    }
    .prov-col:hover { border-color: var(--border-strong); }

    .prov-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .prov-identity { display: flex; align-items: center; gap: 7px; min-width: 0; }
    .prov-tag {
      width: 22px; height: 18px;
      border-radius: 3px;
      border: 1px solid var(--border-strong);
      background: #171717;
      display: grid;
      place-items: center;
      font: 600 9px/1 var(--mono);
      color: var(--text);
      flex-shrink: 0;
    }
    .prov-name {
      font-weight: 500;
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .prov-sub {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      font-size: 10px;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      padding-bottom: 8px;
    }

    .pill {
      display: inline-block;
      font-size: 10px;
      line-height: 16px;
      padding: 0 5px;
      border-radius: 999px;
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-family: var(--mono);
      max-width: 140px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .window-stack {
      display: flex;
      flex-direction: column;
      gap: 9px;
    }

    .window-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .window-top {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 11px;
    }
    .window-name { color: var(--text); font-weight: 400; }
    .window-fraction { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }

    .meter {
      height: 4px;
      border-radius: 2px;
      background: var(--track);
      overflow: hidden;
    }
    .meter-fill { display: block; height: 100%; background: var(--text); border-radius: 2px; }
    .meter-fill.warn { background: var(--amber); }
    .meter-fill.crit { background: var(--red); }

    .window-bottom {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 10px;
      color: var(--text-muted);
      font-family: var(--mono);
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 10px;
      color: var(--text);
      font-family: var(--mono);
    }
    .badge::before {
      content: "";
      width: 5px; height: 5px;
      border-radius: 50%;
      background: var(--text-faint);
    }
    .badge.ok::before { background: var(--green); }
    .badge.warn::before { background: var(--amber); }
    .badge.crit::before { background: var(--red); }
    .badge.neutral { color: var(--text-muted); }

    .note-text { color: var(--text-muted); font-size: 11px; line-height: 1.4; padding: 4px 0; }
    .empty-state { padding: 18px 12px; text-align: center; color: var(--text-muted); font-size: 11px; }

    footer {
      height: 28px;
      border-top: 1px solid var(--border);
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 10px;
      color: var(--text-faint);
      font-family: var(--mono);
      flex-shrink: 0;
    }
  </style>
</head>
<body>
  <header>
    <div class="crumbs">
      <span class="name">Token Runway</span>
      <span class="tag">v0.2.4</span>
      <span class="sep">/</span>
      <span style="color: var(--text-muted);">Usage</span>
    </div>
    <div class="header-right">
      <span class="sync-text" id="sync-label">Connecting…</span>
      <button class="btn" id="refresh-btn" type="button" onclick="manualRefresh()" title="Refresh (R)">Refresh <kbd>R</kbd></button>
    </div>
  </header>

  <main>
    <div class="head-row">
      <h1>Active Quotas &amp; Limits</h1>
      <p id="fleet-summary">Checking providers…</p>
    </div>

    <div class="provider-columns" id="provider-columns">
      <div class="empty-state">Loading active rate limits…</div>
    </div>
  </main>

  <footer>
    <span id="host-label">Loopback only</span>
    <span>Zero external telemetry sent</span>
  </footer>

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

    const TAGS = {
      copilot: "CP",
      gemini: "GM",
      colab: "CO",
      claude: "CL",
      antigravity: "AG",
      openai: "OA",
      openrouter: "OR"
    };

    function getTag(key) {
      const k = (key || '').toLowerCase();
      for (const [prefix, tag] of Object.entries(TAGS)) {
        if (k.includes(prefix)) return tag;
      }
      return (key || 'AI').slice(0, 2).toUpperCase();
    }

    function formatReset(mins) {
      if (mins == null) return '—';
      const rounded = Math.round(mins);
      if (rounded < 1) return '< 1m';
      const d = Math.floor(rounded / 1440);
      const h = Math.floor((rounded % 1440) / 60);
      const m = rounded % 60;
      if (d > 0) return `${d}d ${h}h`;
      if (h > 0) return `${h}h ${m}m`;
      return `${m}m`;
    }

    async function loadStatus() {
      try {
        const res = await fetch('/api/status');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        renderColumns(data.readings || {});
        document.getElementById('sync-label').innerText = new Date().toLocaleTimeString();
      } catch (err) {
        document.getElementById('sync-label').innerText = 'Offline (' + err.message + ')';
      }
    }

    function renderColumns(readings) {
      const container = document.getElementById('provider-columns');
      const entries = Object.entries(readings);
      if (entries.length === 0) {
        container.innerHTML = '<div class="empty-state">No providers configured.</div>';
        return;
      }

      let colsHtml = '';
      let onlineCount = 0;
      let totalWindows = 0;

      for (const [key, r] of entries) {
        const provName = escapeHtml(r.display_name || key);
        const tag = getTag(key);
        const plan = r.plan ? `<span class="pill" title="${escapeHtml(r.plan)}">${escapeHtml(r.plan)}</span>` : '<span class="note-text">—</span>';

        let statusBadge = '<span class="badge neutral">Offline</span>';
        let windowsHtml = '';

        if (!r.available) {
          const errMsg = escapeHtml(r.error_message || 'Unavailable');
          windowsHtml = `<div class="note-text">${errMsg}</div>`;
        } else if (!r.windows || r.windows.length === 0) {
          onlineCount++;
          statusBadge = '<span class="badge ok">Normal</span>';
          windowsHtml = `<div class="note-text">Online · No consumable quota reported</div>`;
        } else {
          onlineCount++;
          let highestPct = -1;
          let isDepleted = false;
          windowsHtml = '<div class="window-stack">';

          for (const w of r.windows) {
            totalWindows++;
            const hasUsed = w.used_pct != null;
            const pct = hasUsed ? Math.min(100, Math.max(0, Math.round(w.used_pct))) : null;
            if (pct != null && pct > highestPct) highestPct = pct;
            if (w.remaining_count === 0 || (pct != null && pct >= 100)) isDepleted = true;

            let fillClass = '';
            if (hasUsed) {
              if (pct >= 90) fillClass = 'crit';
              else if (pct >= 70) fillClass = 'warn';
            }

            let fractionStr = '';
            if (w.remaining_count != null && w.total_entitlement != null) {
              const used = w.total_entitlement - w.remaining_count;
              fractionStr = `${used}/${w.total_entitlement}`;
            } else if (w.remaining_count != null) {
              fractionStr = `${w.remaining_count} rem`;
            }

            windowsHtml += `
              <div class="window-item">
                <div class="window-top">
                  <span class="window-name">${escapeHtml(w.name)}</span>
                  <span class="window-fraction">${fractionStr}</span>
                </div>
                <div class="meter"><span class="meter-fill ${fillClass}" style="width: ${hasUsed ? pct : 0}%"></span></div>
                <div class="window-bottom">
                  <span>${hasUsed ? pct + '%' : '—'}</span>
                  <span>${formatReset(w.resets_in_minutes)}</span>
                </div>
              </div>
            `;
          }
          windowsHtml += '</div>';

          if (isDepleted) statusBadge = '<span class="badge crit">Depleted</span>';
          else if (highestPct >= 90) statusBadge = '<span class="badge crit">Near limit</span>';
          else if (highestPct >= 70) statusBadge = '<span class="badge warn">High</span>';
          else if (highestPct >= 0) statusBadge = '<span class="badge ok">Normal</span>';
          else statusBadge = '<span class="badge neutral">Unknown</span>';
        }

        const limitsCount = r.available ? (r.windows ? r.windows.length : 0) : 0;
        const limitsText = r.available ? (limitsCount + ' limit' + (limitsCount === 1 ? '' : 's')) : 'Offline';

        colsHtml += `
          <div class="prov-col">
            <div class="prov-header">
              <div class="prov-identity">
                <span class="prov-tag">${tag}</span>
                <span class="prov-name" title="${provName}">${provName}</span>
              </div>
              ${statusBadge}
            </div>
            <div class="prov-sub">
              ${plan}
              <span>${limitsText}</span>
            </div>
            ${windowsHtml}
          </div>
        `;
      }

      container.innerHTML = colsHtml;
      document.getElementById('fleet-summary').innerText = `${onlineCount} of ${entries.length} providers online · ${totalWindows} limits tracked`;
    }

    function manualRefresh() {
      loadStatus();
    }

    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key === 'r' || e.key === 'R') {
        e.preventDefault();
        manualRefresh();
      }
    });

    const hostEl = document.getElementById('host-label');
    if (hostEl && window.location.host) {
      hostEl.innerText = window.location.host + ' · Loopback only';
    }

    let pollTimer = null;
    function startPolling() {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(() => {
        if (!document.hidden) loadStatus();
      }, 5000);
    }

    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) loadStatus();
    });

    loadStatus();
    startPolling();
  </script>
</body>
</html>
"""

HTML_PAGE = _HTML_TEMPLATE

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
MAX_REQUEST_BODY_SIZE = 64 * 1024  # 64 KB maximum payload limit


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP request handler for the Token Runway dashboard."""

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

    def _is_safe_request(self) -> bool:
        """Validate Host and Origin headers to protect against DNS rebinding and cross-origin attacks."""
        host_header = self.headers.get("Host", "")
        host_name = host_header.split(":")[0].strip().lower()
        if host_name and host_name not in LOOPBACK_HOSTS:
            return False

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
        if not self._is_safe_request():
            self.send_error(403, "Forbidden: Invalid Host or Origin header.")
            return

        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(_HTML_TEMPLATE.encode("utf-8"))
            return

        if parsed.path == "/api/status":
            readings = self._get_cached_readings()
            payload = {
                "readings": {k: v.to_dict() for k, v in readings.items()},
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        if not self._is_safe_request():
            self.send_error(403, "Forbidden: Invalid Host or Origin header.")
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
                action_type=action_type.lower().strip(),
                intensity=intensity.lower().strip(),
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

    server_cls = ThreadingHTTPServer
    if ":" in host:
        class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
            address_family = socket.AF_INET6
        server_cls = IPv6ThreadingHTTPServer

    server = server_cls((host, port), DashboardRequestHandler)
    url = f"http://{host}:{port}/"
    print("\n\033[1;36m=== Token Runway: Dashboard ===\033[0m")
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
