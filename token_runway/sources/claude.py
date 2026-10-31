"""Anthropic Claude usage harvester via Claude Code credentials and OAuth endpoint."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from token_runway.sources.base import ProviderReading, QuotaWindow, calculate_minutes_until

USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
USER_AGENT = "claude-code/2.1.5"
BETA_HEADER = "oauth-2025-04-20"
CACHE_PATH = Path.home() / ".cache" / "token-runway" / "claude_cache.json"
MAX_CACHE_AGE_SEC = 900  # 15 minutes


def find_claude_token() -> Optional[str]:
    """Discover active Claude Code OAuth token from standard paths or environment."""
    env_token = os.environ.get("CLAUDE_CODE_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    cfg_token = Path.home() / ".config" / "claude-usage-monitor" / "claude-token"
    if cfg_token.is_file():
        try:
            tok = cfg_token.read_text().strip()
            if tok and not any(c.isspace() for c in tok):
                return tok
        except Exception:
            pass

    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.is_file():
        try:
            data = json.loads(creds_path.read_text())
            tok = data.get("claudeAiOauth", {}).get("accessToken")
            if tok and isinstance(tok, str) and tok.strip():
                return tok.strip()
        except Exception:
            pass

    return None


def read_cached_reading() -> Optional[ProviderReading]:
    """Read last good Claude reading from local cache if fresh enough."""
    if not CACHE_PATH.is_file():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        saved_at = data.get("_saved_at", 0)
        if (time.time() - saved_at) < MAX_CACHE_AGE_SEC:
            return parse_claude_usage(data)
    except Exception:
        pass
    return None


def write_cached_reading(data: Dict[str, Any]) -> None:
    """Save last good response to cache."""
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        to_save = dict(data)
        to_save["_saved_at"] = time.time()
        CACHE_PATH.write_text(json.dumps(to_save), encoding="utf-8")
    except Exception:
        pass


def parse_claude_usage(data: Dict[str, Any]) -> ProviderReading:
    """Parse JSON body from `GET /api/oauth/usage`."""
    reading = ProviderReading(
        provider="claude",
        display_name="Anthropic Claude",
        available=True,
    )

    fh = data.get("five_hour")
    if isinstance(fh, dict):
        util = fh.get("utilization")
        resets_at = fh.get("resets_at")
        mins = calculate_minutes_until(resets_at)
        if util is not None:
            used_pct = max(0, min(100, int(round(float(util)))))
            rem_pct = round(max(0.0, 100.0 - float(util)), 1)
            st = "critical" if used_pct >= 95 else ("warning" if used_pct >= 80 else "ok")
            reading.windows.append(
                QuotaWindow(
                    name="Current (5-Hour)",
                    used_pct=used_pct,
                    remaining_pct=rem_pct,
                    resets_at=resets_at,
                    resets_in_minutes=mins,
                    status=st,
                )
            )

    sd = data.get("seven_day")
    if isinstance(sd, dict):
        util = sd.get("utilization")
        resets_at = sd.get("resets_at")
        mins = calculate_minutes_until(resets_at)
        if util is not None:
            used_pct = max(0, min(100, int(round(float(util)))))
            rem_pct = round(max(0.0, 100.0 - float(util)), 1)
            st = "critical" if used_pct >= 95 else ("warning" if used_pct >= 80 else "ok")
            reading.windows.append(
                QuotaWindow(
                    name="Weekly (7-Day)",
                    used_pct=used_pct,
                    remaining_pct=rem_pct,
                    resets_at=resets_at,
                    resets_in_minutes=mins,
                    status=st,
                )
            )

    return reading


def fetch_claude(timeout: float = 10.0) -> ProviderReading:
    """Fetch Claude usage from Anthropic's OAuth usage endpoint with cache fallback."""
    token = find_claude_token()
    if not token:
        return ProviderReading(
            provider="claude",
            display_name="Anthropic Claude",
            available=False,
            error_message="No Claude Code credentials found (~/.claude/.credentials.json)",
        )

    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": BETA_HEADER,
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            write_cached_reading(data)
            return parse_claude_usage(data)
    except urllib.error.HTTPError as e:
        status_code = e.code
        e.close()
        cached = read_cached_reading()
        if cached:
            return cached

        if status_code == 401:
            msg = "Claude OAuth token expired (open Claude Code or re-authenticate)"
        elif status_code == 429:
            msg = "Claude usage endpoint rate limited (HTTP 429; retry in a moment)"
        elif status_code == 403:
            msg = "Claude usage endpoint returned 403 Forbidden"
        else:
            msg = f"Anthropic API returned HTTP {status_code}"
        return ProviderReading(
            provider="claude",
            display_name="Anthropic Claude",
            available=False,
            error_message=msg,
        )
    except Exception as e:
        cached = read_cached_reading()
        if cached:
            return cached

        return ProviderReading(
            provider="claude",
            display_name="Anthropic Claude",
            available=False,
            error_message=f"Failed to fetch Claude usage: {e}",
        )
