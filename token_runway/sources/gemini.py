"""Gemini & Antigravity quota harvester via Antigravity CLI (`agy`)."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Dict, List, Tuple

from token_runway.sources.base import ProviderReading, QuotaWindow, calculate_minutes_until


def parse_agy_json(data: Dict[str, Any]) -> Tuple[ProviderReading, ProviderReading]:
    """Parse JSON output of `agy -p /usage --output-format json`.

    Returns a tuple of (gemini_reading, antigravity_reading).
    """
    gemini = ProviderReading(provider="gemini", display_name="Google Gemini", available=True)
    agy = ProviderReading(provider="antigravity", display_name="Antigravity (Claude + GPT)", available=True)

    groups = data.get("command", {}).get("data", {}).get("groups", [])
    if not groups and "groups" in data:
        groups = data["groups"]

    for group in groups:
        gname = group.get("name", "").lower()
        buckets = group.get("buckets", [])

        if "gemini models" in gname:
            for b in buckets:
                rem_frac = b.get("remaining_fraction")
                reset_t = b.get("reset_time")
                mins = calculate_minutes_until(reset_t)
                window_id = b.get("window", "")

                if rem_frac is not None:
                    rem_pct = round(rem_frac * 100.0, 1)
                    used_pct = max(0, min(100, int(round(100.0 - rem_pct))))
                    st = "ok"
                    if used_pct >= 95:
                        st = "critical"
                    elif used_pct >= 80:
                        st = "warning"

                    name = "Flash/Pro 5-Hour" if "5h" in window_id else "Flash/Pro Weekly"
                    gemini.windows.append(
                        QuotaWindow(
                            name=name,
                            used_pct=used_pct,
                            remaining_pct=rem_pct,
                            resets_at=reset_t,
                            resets_in_minutes=mins,
                            status=st,
                        )
                    )

        elif "gemini" in gname and "argon" in gname:
            for b in buckets:
                rem_frac = b.get("remaining_fraction")
                reset_t = b.get("reset_time")
                mins = calculate_minutes_until(reset_t)

                if rem_frac is not None:
                    rem_pct = round(rem_frac * 100.0, 1)
                    used_pct = max(0, min(100, int(round(100.0 - rem_pct))))
                    st = "critical" if used_pct >= 100 else ("warning" if used_pct >= 80 else "ok")

                    gemini.windows.append(
                        QuotaWindow(
                            name="Argon Weekly",
                            used_pct=used_pct,
                            remaining_pct=rem_pct,
                            resets_at=reset_t,
                            resets_in_minutes=mins,
                            status=st,
                        )
                    )

        elif "claude and gpt" in gname or "3p" in gname:
            for b in buckets:
                rem_frac = b.get("remaining_fraction")
                reset_t = b.get("reset_time")
                mins = calculate_minutes_until(reset_t)
                window_id = b.get("window", "")

                if rem_frac is not None:
                    rem_pct = round(rem_frac * 100.0, 1)
                    used_pct = max(0, min(100, int(round(100.0 - rem_pct))))
                    st = "ok"
                    if used_pct >= 95:
                        st = "critical"
                    elif used_pct >= 80:
                        st = "warning"

                    name = "Current (5-Hour)" if "5h" in window_id else "Weekly"
                    agy.windows.append(
                        QuotaWindow(
                            name=name,
                            used_pct=used_pct,
                            remaining_pct=rem_pct,
                            resets_at=reset_t,
                            resets_in_minutes=mins,
                            status=st,
                        )
                    )

    return gemini, agy


def fetch_gemini_and_antigravity(timeout: float = 12.0) -> List[ProviderReading]:
    """Fetch Gemini and Antigravity quotas via `agy -p /usage --output-format json`."""
    if not shutil.which("agy"):
        msg = "Antigravity CLI (`agy`) not installed or not in PATH"
        return [
            ProviderReading(provider="gemini", display_name="Google Gemini", available=False, error_message=msg),
            ProviderReading(
                provider="antigravity",
                display_name="Antigravity (Claude + GPT)",
                available=False,
                error_message=msg,
            ),
        ]

    cmd = ["agy", "-p", "/usage", "--output-format", "json"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            msg = f"agy failed (exit {proc.returncode}): {err}"
            return [
                ProviderReading(provider="gemini", display_name="Google Gemini", available=False, error_message=msg),
                ProviderReading(
                    provider="antigravity",
                    display_name="Antigravity (Claude + GPT)",
                    available=False,
                    error_message=msg,
                ),
            ]

        data = json.loads(proc.stdout)
        gem, agy = parse_agy_json(data)
        return [gem, agy]
    except subprocess.TimeoutExpired:
        msg = "agy timed out after 12s"
        return [
            ProviderReading(provider="gemini", display_name="Google Gemini", available=False, error_message=msg),
            ProviderReading(
                provider="antigravity",
                display_name="Antigravity (Claude + GPT)",
                available=False,
                error_message=msg,
            ),
        ]
    except Exception as e:
        msg = f"Failed to fetch Antigravity usage: {e}"
        return [
            ProviderReading(provider="gemini", display_name="Google Gemini", available=False, error_message=msg),
            ProviderReading(
                provider="antigravity",
                display_name="Antigravity (Claude + GPT)",
                available=False,
                error_message=msg,
            ),
        ]
