"""Unified quota discovery and extraction across all supported AI providers."""

from __future__ import annotations

import concurrent.futures
from typing import Dict, List, Optional

from token_runway.sources.base import ProviderReading
from token_runway.sources.claude import fetch_claude
from token_runway.sources.colab import fetch_colab
from token_runway.sources.copilot import fetch_copilot
from token_runway.sources.gemini import fetch_gemini_and_antigravity


def fetch_all_runways(timeout: float = 12.0) -> Dict[str, ProviderReading]:
    """Fetch usage telemetry concurrently across all providers."""
    readings: Dict[str, ProviderReading] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f_claude = executor.submit(fetch_claude, timeout)
        f_copilot = executor.submit(fetch_copilot, timeout)
        f_gemini = executor.submit(fetch_gemini_and_antigravity, timeout)
        f_colab = executor.submit(fetch_colab, timeout)

        # Claude
        try:
            r = f_claude.result()
            readings["claude"] = r
        except Exception as e:
            readings["claude"] = ProviderReading(
                provider="claude", display_name="Anthropic Claude", available=False, error_message=str(e)
            )

        # Copilot
        try:
            r = f_copilot.result()
            readings["copilot"] = r
        except Exception as e:
            readings["copilot"] = ProviderReading(
                provider="copilot", display_name="GitHub Copilot", available=False, error_message=str(e)
            )

        # Gemini & Antigravity
        try:
            gem_list = f_gemini.result()
            for g in gem_list:
                readings[g.provider] = g
        except Exception as e:
            readings["gemini"] = ProviderReading(
                provider="gemini", display_name="Google Gemini", available=False, error_message=str(e)
            )
            readings["antigravity"] = ProviderReading(
                provider="antigravity",
                display_name="Antigravity (Claude + GPT)",
                available=False,
                error_message=str(e),
            )

        # Colab
        try:
            r = f_colab.result()
            readings["colab"] = r
        except Exception as e:
            readings["colab"] = ProviderReading(
                provider="colab", display_name="Google Colab", available=False, error_message=str(e)
            )

    return readings
