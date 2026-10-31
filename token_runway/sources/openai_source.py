"""OpenAI API quota and connectivity harvester via standard library."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from token_runway.sources.base import ProviderReading, QuotaWindow

OPENAI_MODELS_URL = "https://api.openai.com/v1/models"


def find_openai_key() -> Optional[str]:
    """Discover OpenAI API key from environment or standard config files."""
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    for p in [
        Path.home() / ".config" / "openai" / "key",
        Path.home() / ".openai" / "key",
    ]:
        if p.is_file():
            try:
                k = p.read_text().strip()
                if k:
                    return k
            except Exception:
                pass
    return None


def fetch_openai(key: Optional[str] = None) -> ProviderReading:
    """Validate OpenAI API key connectivity and access."""
    api_key = key or find_openai_key()
    if not api_key:
        return ProviderReading(
            provider="openai",
            display_name="OpenAI API",
            available=False,
            error_message="OPENAI_API_KEY not found in environment or ~/.config/openai/key.",
        )

    req = urllib.request.Request(
        OPENAI_MODELS_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "token-runway/0.1.1",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            has_gpt4 = any("gpt-4" in m.get("id", "") or "o1" in m.get("id", "") for m in models)

            windows = [
                QuotaWindow(
                    name="API Key Access",
                    used_pct=0,
                    remaining_pct=100.0,
                    resets_in_minutes=None,
                    resets_at=None,
                    status="ok",
                    remaining_count=float(len(models)),
                    total_entitlement=None,
                )
            ]

            return ProviderReading(
                provider="openai",
                display_name="OpenAI API",
                available=True,
                plan="Tier / Pay-as-you-go (GPT-4/o1 available)" if has_gpt4 else "Standard Tier",
                windows=windows,
            )
    except urllib.error.HTTPError as e:
        status_code = e.code
        e.close()
        if status_code == 401:
            return ProviderReading(
                provider="openai",
                display_name="OpenAI API",
                available=False,
                error_message="Invalid OpenAI API key (HTTP 401 Unauthorized).",
            )
        return ProviderReading(
            provider="openai",
            display_name="OpenAI API",
            available=False,
            error_message=f"OpenAI HTTP Error: {status_code}",
        )
    except Exception as e:
        return ProviderReading(
            provider="openai",
            display_name="OpenAI API",
            available=False,
            error_message=f"Failed to query OpenAI: {e}",
        )
