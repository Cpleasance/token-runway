"""Google Colab compute-unit harvester via Google Colab CLI (`colab`)."""

from __future__ import annotations

import re
import shutil
import subprocess

from token_runway.sources.base import ProviderReading, QuotaWindow


def parse_colab_text(text: str) -> ProviderReading:
    """Parse text output of `colab usage`."""
    reading = ProviderReading(provider="colab", display_name="Google Colab", available=True)

    # Patterns:
    # Current balance: 499.46 compute units
    # Usage rate: 0.00/hr
    # Active assignments: 0
    balance_match = re.search(r"Current balance:\s*([0-9.]+)", text, re.IGNORECASE)
    rate_match = re.search(r"Usage rate:\s*([0-9.]+)", text, re.IGNORECASE)
    active_match = re.search(r"Active assignments:\s*([0-9]+)", text, re.IGNORECASE)

    if balance_match:
        balance = float(balance_match.group(1))
        rate = float(rate_match.group(1)) if rate_match else 0.0
        active = int(active_match.group(1)) if active_match else 0

        reading.windows.append(
            QuotaWindow(
                name="Compute Units Balance",
                remaining_count=balance,
                status="ok" if balance > 50.0 else ("warning" if balance > 10.0 else "critical"),
            )
        )
        reading.windows.append(
            QuotaWindow(
                name="Burn Rate (/hr)",
                remaining_count=rate,
                status="ok",
            )
        )
        reading.windows.append(
            QuotaWindow(
                name="Active Runtimes",
                remaining_count=float(active),
                status="ok" if active == 0 else "active",
            )
        )
    else:
        reading.available = False
        reading.error_message = "Could not parse Colab usage output"

    return reading


def fetch_colab(timeout: float = 8.0) -> ProviderReading:
    """Fetch Colab compute units via `colab usage`."""
    bin_path = shutil.which("colab")
    if not bin_path:
        return ProviderReading(
            provider="colab",
            display_name="Google Colab",
            available=False,
            error_message="Colab CLI (`colab`) not installed",
        )

    try:
        proc = subprocess.run(
            ["colab", "usage"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip() or proc.stdout.strip()
            return ProviderReading(
                provider="colab",
                display_name="Google Colab",
                available=False,
                error_message=f"colab command failed: {err}",
            )
        return parse_colab_text(proc.stdout)
    except subprocess.TimeoutExpired:
        return ProviderReading(
            provider="colab",
            display_name="Google Colab",
            available=False,
            error_message="colab command timed out",
        )
    except Exception as e:
        return ProviderReading(
            provider="colab",
            display_name="Google Colab",
            available=False,
            error_message=f"Failed to fetch Colab usage: {e}",
        )
