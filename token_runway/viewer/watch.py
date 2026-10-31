"""Live updating terminal HUD for AI token runway telemetry (top / htop for tokens)."""

from __future__ import annotations

import datetime
import sys
import time
from typing import Dict, Optional

from token_runway.server.server import SUPPORTED_PROVIDERS
from token_runway.sources import fetch_all_runways
from token_runway.sources.base import ProviderReading


def render_bar(used_pct: Optional[int], width: int = 16) -> str:
    """Render a colored ANSI terminal progress bar."""
    if used_pct is None:
        return "\033[90m" + "░" * width + "\033[0m"

    pct = max(0, min(100, used_pct))
    filled = int(round((pct / 100.0) * width))
    empty = width - filled

    if pct >= 90:
        color = "\033[91m"  # Red
    elif pct >= 75:
        color = "\033[93m"  # Yellow
    else:
        color = "\033[92m"  # Green

    bar = f"{color}{'█' * filled}\033[90m{'░' * empty}\033[0m"
    return bar


def format_minutes_short(minutes: Optional[int]) -> str:
    """Format minutes into human-friendly short string like '1h 14m' or '23m'."""
    if minutes is None:
        return ""
    if minutes < 0:
        return "now"
    hours = minutes // 60
    rem_min = minutes % 60
    if hours >= 24:
        days = hours // 24
        rem_hours = hours % 24
        return f"{days}d {rem_hours}h"
    if hours > 0:
        return f"{hours}h {rem_min}m"
    return f"{rem_min}m"


def build_hud_text(readings: Dict[str, ProviderReading]) -> str:
    """Assemble a formatted terminal dashboard snapshot."""
    now_str = datetime.datetime.now().strftime("%H:%M:%S")
    header = f"\033[1;36m=== Token Runway: Live HUD ===\033[0m  \033[90m[{now_str}] (Ctrl+C to exit)\033[0m\n"
    lines = [header]

    for _key, r in readings.items():
        title = f"\033[1;37m{r.display_name}\033[0m"
        if r.plan:
            title += f" \033[90m[{r.plan}]\033[0m"
        lines.append(title)

        if not r.available:
            lines.append(f"  \033[90mUnavailable: {r.error_message}\033[0m")
            continue

        if not r.windows:
            lines.append("  \033[90mNo active quota windows reported.\033[0m")
            continue

        for w in r.windows:
            bar = render_bar(w.used_pct, width=14)
            pct_str = f"{w.used_pct:>3}%" if w.used_pct is not None else "  -"
            reset_str = ""
            if w.resets_in_minutes is not None:
                reset_str = f"\033[90m(resets in {format_minutes_short(w.resets_in_minutes)})\033[0m"
            elif w.remaining_count is not None and w.total_entitlement is not None:
                reset_str = f"\033[90m[{int(w.remaining_count)}/{int(w.total_entitlement)}]\033[0m"
            elif w.remaining_count is not None:
                reset_str = f"\033[90m[{w.remaining_count}]\033[0m"

            line = f"  • {w.name:<24} {bar} {pct_str}  {reset_str}"
            lines.append(line)

        lines.append("")

    return "\n".join(lines)


def run_watch_loop(
    interval: float = 5.0,
    max_iterations: Optional[int] = None,
    provider: Optional[str] = None,
) -> None:
    """Run interactive terminal watch loop."""
    iteration = 0
    prov_filter = provider.lower().strip() if provider else None
    if prov_filter and prov_filter not in SUPPORTED_PROVIDERS:
        print(
            f"\033[91m✖ Error:\033[0m Unknown provider '{provider}'. "
            f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}.",
            file=sys.stderr,
        )
        return
    try:
        while True:
            readings = fetch_all_runways(provider=prov_filter)
            if prov_filter:
                readings = {k: v for k, v in readings.items() if k == prov_filter}
            hud = build_hud_text(readings)

            # Clear screen and place cursor at row 1, col 1
            if sys.stdout.isatty():
                sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(hud)
            sys.stdout.flush()

            iteration += 1
            if max_iterations is not None and iteration >= max_iterations:
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\nToken Runway watch stopped.")
