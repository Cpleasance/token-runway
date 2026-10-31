"""Unified quota discovery and extraction across all supported AI providers."""

from __future__ import annotations

import concurrent.futures
from typing import Dict, Optional

from token_runway.sources.base import ProviderReading
from token_runway.sources.claude import fetch_claude
from token_runway.sources.colab import fetch_colab
from token_runway.sources.copilot import fetch_copilot
from token_runway.sources.gemini import fetch_gemini_and_antigravity
from token_runway.sources.openai_source import fetch_openai, find_openai_key
from token_runway.sources.openrouter import fetch_openrouter, find_openrouter_key


def fetch_all_runways(
    timeout: float = 12.0,
    provider: Optional[str] = None,
) -> Dict[str, ProviderReading]:
    """Fetch usage telemetry across all providers, or a single targeted provider."""
    readings: Dict[str, ProviderReading] = {}
    target = provider.lower().strip() if provider else None

    # Single provider targeted fast path
    if target:
        if target == "claude":
            try:
                readings["claude"] = fetch_claude(timeout)
            except Exception as e:
                readings["claude"] = ProviderReading(
                    provider="claude", display_name="Anthropic Claude", available=False, error_message=str(e)
                )
            return readings

        if target == "copilot":
            try:
                readings["copilot"] = fetch_copilot(timeout)
            except Exception as e:
                readings["copilot"] = ProviderReading(
                    provider="copilot", display_name="GitHub Copilot", available=False, error_message=str(e)
                )
            return readings

        if target in ("gemini", "antigravity"):
            try:
                for g in fetch_gemini_and_antigravity(timeout):
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
            return readings

        if target == "colab":
            try:
                readings["colab"] = fetch_colab(timeout)
            except Exception as e:
                readings["colab"] = ProviderReading(
                    provider="colab", display_name="Google Colab", available=False, error_message=str(e)
                )
            return readings

        if target == "openrouter":
            try:
                readings["openrouter"] = fetch_openrouter()
            except Exception as e:
                readings["openrouter"] = ProviderReading(
                    provider="openrouter", display_name="OpenRouter", available=False, error_message=str(e)
                )
            return readings

        if target == "openai":
            try:
                readings["openai"] = fetch_openai()
            except Exception as e:
                readings["openai"] = ProviderReading(
                    provider="openai", display_name="OpenAI API", available=False, error_message=str(e)
                )
            return readings

    # Full concurrent fetch across all providers
    has_openrouter = find_openrouter_key() is not None
    has_openai = find_openai_key() is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        f_claude = executor.submit(fetch_claude, timeout)
        f_copilot = executor.submit(fetch_copilot, timeout)
        f_gemini = executor.submit(fetch_gemini_and_antigravity, timeout)
        f_colab = executor.submit(fetch_colab, timeout)
        f_openrouter = executor.submit(fetch_openrouter) if has_openrouter else None
        f_openai = executor.submit(fetch_openai) if has_openai else None

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

        # OpenRouter (if configured)
        if f_openrouter is not None:
            try:
                r = f_openrouter.result()
                readings["openrouter"] = r
            except Exception as e:
                readings["openrouter"] = ProviderReading(
                    provider="openrouter", display_name="OpenRouter", available=False, error_message=str(e)
                )

        # OpenAI (if configured)
        if f_openai is not None:
            try:
                r = f_openai.result()
                readings["openai"] = r
            except Exception as e:
                readings["openai"] = ProviderReading(
                    provider="openai", display_name="OpenAI API", available=False, error_message=str(e)
                )

    return readings
