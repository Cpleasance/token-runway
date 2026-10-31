"""OpenRouter quota and credit balance harvester via OpenRouter Key API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from token_runway import __version__
from token_runway.sources.base import ProviderReading, QuotaWindow

OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/auth/key"


def find_openrouter_key() -> Optional[str]:
    """Discover OpenRouter API key from environment or standard config files."""
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    for p in [
        Path.home() / ".config" / "openrouter" / "key",
        Path.home() / ".openrouter" / "key",
    ]:
        if p.is_file():
            try:
                k = p.read_text().strip()
                if k:
                    return k
            except Exception:
                pass
    return None


def parse_openrouter_data(data: Dict[str, Any]) -> ProviderReading:
    """Parse raw JSON response from OpenRouter /api/v1/auth/key into ProviderReading."""
    key_info = data.get("data", {})
    label = key_info.get("label") or "OpenRouter Key"
    usage = float(key_info.get("usage", 0.0) or 0.0)
    limit = key_info.get("limit")
    is_free = bool(key_info.get("is_free_tier", False))
    rate_limit = key_info.get("rate_limit", {})

    windows = []

    if limit is not None:
        limit_val = float(limit)
        remaining = max(0.0, limit_val - usage)
        used_pct = round((usage / limit_val) * 100.0) if limit_val > 0 else 100
        used_pct = min(100, max(0, used_pct))
        rem_pct = round(100.0 - (usage / limit_val * 100.0), 1) if limit_val > 0 else 0.0

        if used_pct >= 90:
            status = "critical"
        elif used_pct >= 75:
            status = "warning"
        else:
            status = "ok"

        windows.append(
            QuotaWindow(
                name="Credit Limit",
                used_pct=used_pct,
                remaining_pct=max(0.0, rem_pct),
                resets_in_minutes=None,
                resets_at=None,
                status=status,
                remaining_count=round(remaining, 4),
                total_entitlement=limit_val,
            )
        )
    else:
        # Unlimited key - track total usage without false quota assumptions
        windows.append(
            QuotaWindow(
                name="Cumulative Spend",
                used_pct=None,
                remaining_pct=None,
                resets_in_minutes=None,
                resets_at=None,
                status="unlimited",
                remaining_count=round(usage, 4),
                total_entitlement=None,
                is_quota=False,
            )
        )

    if rate_limit and isinstance(rate_limit, dict):
        reqs = rate_limit.get("requests")
        interval = rate_limit.get("interval")
        if reqs:
            windows.append(
                QuotaWindow(
                    name=f"Rate Limit ({interval})",
                    used_pct=None,
                    remaining_pct=None,
                    resets_in_minutes=None,
                    resets_at=None,
                    status="ok",
                    remaining_count=float(reqs),
                    total_entitlement=float(reqs),
                    is_quota=False,
                )
            )

    return ProviderReading(
        provider="openrouter",
        display_name="OpenRouter",
        available=True,
        account=label,
        plan="Free Tier" if is_free else "Pay-as-you-go",
        windows=windows,
    )


def fetch_openrouter(key: Optional[str] = None) -> ProviderReading:
    """Query OpenRouter API key quota and spend balance."""
    api_key = key or find_openrouter_key()
    if not api_key:
        return ProviderReading(
            provider="openrouter",
            display_name="OpenRouter",
            available=False,
            error_message="OPENROUTER_API_KEY not found in environment or ~/.config/openrouter/key.",
        )

    req = urllib.request.Request(
        OPENROUTER_KEY_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": f"token-runway/{__version__}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return parse_openrouter_data(data)
    except urllib.error.HTTPError as e:
        status_code = e.code
        e.close()
        if status_code == 401:
            return ProviderReading(
                provider="openrouter",
                display_name="OpenRouter",
                available=False,
                error_message="Invalid OpenRouter API key (HTTP 401 Unauthorized).",
            )
        return ProviderReading(
            provider="openrouter",
            display_name="OpenRouter",
            available=False,
            error_message=f"OpenRouter HTTP Error: {status_code}",
        )
    except Exception as e:
        return ProviderReading(
            provider="openrouter",
            display_name="OpenRouter",
            available=False,
            error_message=f"Failed to query OpenRouter: {e}",
        )
