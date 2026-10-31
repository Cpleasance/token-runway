"""GitHub Copilot quota harvester via GitHub CLI (`gh`)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict

from token_runway.sources.base import ProviderReading, QuotaWindow, calculate_minutes_until


def parse_copilot_data(data: Dict[str, Any]) -> ProviderReading:
    """Parse raw JSON output from `gh api /copilot_internal/user`."""
    reading = ProviderReading(
        provider="copilot",
        display_name="GitHub Copilot",
        available=True,
        account=data.get("login"),
        plan=data.get("access_type_sku") or data.get("copilot_plan") or "unknown",
    )

    reset_utc = data.get("quota_reset_date_utc") or data.get("quota_reset_date")
    mins_until_reset = calculate_minutes_until(reset_utc)

    snapshots = data.get("quota_snapshots") or {}
    if not snapshots and "login" not in data:
        reading.available = False
        reading.error_message = "Unexpected Copilot user response format"
        return reading

    # 1. Chat Monthly
    chat = snapshots.get("chat")
    if chat:
        unlimited = chat.get("unlimited", False)
        entitlement = chat.get("entitlement")
        remaining = chat.get("remaining")
        pr = chat.get("percent_remaining")

        if unlimited:
            reading.windows.append(
                QuotaWindow(
                    name="Chat Monthly",
                    status="unlimited",
                    resets_at=reset_utc,
                    resets_in_minutes=mins_until_reset,
                )
            )
        elif entitlement == 0 or pr is None:
            reading.windows.append(
                QuotaWindow(
                    name="Chat Monthly",
                    status="not_on_plan",
                    total_entitlement=0,
                )
            )
        else:
            used_pct = max(0, min(100, int(round(100.0 - float(pr)))))
            st = "ok"
            if used_pct >= 95:
                st = "critical"
            elif used_pct >= 80:
                st = "warning"
            reading.windows.append(
                QuotaWindow(
                    name="Chat Monthly",
                    used_pct=used_pct,
                    remaining_pct=round(float(pr), 1),
                    remaining_count=remaining,
                    total_entitlement=entitlement,
                    resets_at=reset_utc,
                    resets_in_minutes=mins_until_reset,
                    status=st,
                )
            )

    # 2. Completions Monthly
    completions = snapshots.get("completions")
    if completions:
        unlimited = completions.get("unlimited", False)
        entitlement = completions.get("entitlement")
        remaining = completions.get("remaining")
        pr = completions.get("percent_remaining")

        if unlimited:
            reading.windows.append(
                QuotaWindow(
                    name="Completions Monthly",
                    status="unlimited",
                    resets_at=reset_utc,
                    resets_in_minutes=mins_until_reset,
                )
            )
        elif entitlement == 0 or pr is None:
            reading.windows.append(
                QuotaWindow(
                    name="Completions Monthly",
                    status="not_on_plan",
                    total_entitlement=0,
                )
            )
        else:
            used_pct = max(0, min(100, int(round(100.0 - float(pr)))))
            st = "ok"
            if used_pct >= 95:
                st = "critical"
            elif used_pct >= 80:
                st = "warning"
            reading.windows.append(
                QuotaWindow(
                    name="Completions Monthly",
                    used_pct=used_pct,
                    remaining_pct=round(float(pr), 1),
                    remaining_count=remaining,
                    total_entitlement=entitlement,
                    resets_at=reset_utc,
                    resets_in_minutes=mins_until_reset,
                    status=st,
                )
            )

    # 3. Premium Interactions Monthly
    premium = snapshots.get("premium_interactions")
    if premium:
        entitlement = premium.get("entitlement", 0)
        remaining = premium.get("remaining", 0)
        pr = premium.get("percent_remaining")
        has_quota = premium.get("has_quota", True)

        if not has_quota or entitlement == 0:
            reading.windows.append(
                QuotaWindow(
                    name="Premium Monthly",
                    status="not_on_plan",
                    total_entitlement=0,
                )
            )
        elif pr is not None:
            used_pct = max(0, min(100, int(round(100.0 - float(pr)))))
            st = "ok"
            if used_pct >= 95:
                st = "critical"
            elif used_pct >= 80:
                st = "warning"
            reading.windows.append(
                QuotaWindow(
                    name="Premium Monthly",
                    used_pct=used_pct,
                    remaining_pct=round(float(pr), 1),
                    remaining_count=remaining,
                    total_entitlement=entitlement,
                    resets_at=reset_utc,
                    resets_in_minutes=mins_until_reset,
                    status=st,
                )
            )

    return reading


def fetch_copilot(timeout: float = 10.0) -> ProviderReading:
    """Fetch current GitHub Copilot usage via `gh api /copilot_internal/user`."""
    if not shutil.which("gh"):
        return ProviderReading(
            provider="copilot",
            display_name="GitHub Copilot",
            available=False,
            error_message="GitHub CLI (`gh`) not installed or not in PATH",
        )

    cmd = ["gh", "api", "/copilot_internal/user"]
    env = dict(os.environ)
    env.update({"GH_PROMPT_DISABLED": "1", "NO_COLOR": "1"})
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if proc.returncode != 0:
            err = proc.stderr.strip()
            if "auth login" in err.lower() or "not logged in" in err.lower():
                msg = "gh not logged in (run: gh auth login)"
            elif "404" in err or "Not Found" in proc.stdout:
                msg = "No Copilot subscription on this account"
            else:
                msg = f"gh api failed (exit {proc.returncode}): {err}"
            return ProviderReading(
                provider="copilot",
                display_name="GitHub Copilot",
                available=False,
                error_message=msg,
            )

        data = json.loads(proc.stdout)
        return parse_copilot_data(data)
    except subprocess.TimeoutExpired:
        return ProviderReading(
            provider="copilot",
            display_name="GitHub Copilot",
            available=False,
            error_message="gh api timed out after 10s",
        )
    except Exception as e:
        return ProviderReading(
            provider="copilot",
            display_name="GitHub Copilot",
            available=False,
            error_message=f"Failed to fetch copilot usage: {e}",
        )
