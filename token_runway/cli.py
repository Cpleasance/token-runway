"""Command-line interface for Token Runway."""

from __future__ import annotations

import argparse
import shutil
import sys
from typing import List, Optional

from token_runway.injector import get_ide_config_targets, inject_into_file
from token_runway.server import TokenRunwayServer
from token_runway.sources import fetch_all_runways
from token_runway.sources.claude import find_claude_token

__version__ = "0.1.0"


def format_status_badge(status: str) -> str:
    """Simple ANSI terminal color badge."""
    if status == "critical":
        return "\033[91m● CRITICAL\033[0m"
    if status == "warning":
        return "\033[93m▲ WARNING\033[0m"
    if status == "ok":
        return "\033[92m✔ OK\033[0m"
    if status == "unlimited":
        return "\033[96m∞ UNLIMITED\033[0m"
    if status == "not_on_plan":
        return "\033[90m- NOT ON PLAN\033[0m"
    return status.upper()


def cmd_check() -> int:
    """Print a terminal table of active token quotas across all providers."""
    print("\n\033[1m=== Token Runway: Live Quota Telemetry ===\033[0m\n")
    readings = fetch_all_runways()

    for key, r in readings.items():
        title = f"\033[1;34m{r.display_name}\033[0m"
        if r.plan:
            title += f" \033[90m(Plan: {r.plan})\033[0m"
        print(title)

        if not r.available:
            print(f"  \033[90mUnavailable: {r.error_message}\033[0m\n")
            continue

        if not r.windows:
            print("  \033[90mNo active quota windows reported.\033[0m\n")
            continue

        for w in r.windows:
            badge = format_status_badge(w.status)
            line = f"  • {w.name:<26} {badge:<22}"

            if w.used_pct is not None:
                line += f" Used: {w.used_pct:>3}%"
            if w.remaining_pct is not None:
                line += f"  (Remaining: {w.remaining_pct:>5}%)"
            if w.remaining_count is not None:
                if w.total_entitlement is not None:
                    line += f"  [{w.remaining_count}/{w.total_entitlement}]"
                else:
                    line += f"  [{w.remaining_count}]"
            if w.resets_in_minutes is not None:
                if w.resets_in_minutes < 60:
                    line += f"  (Resets in {w.resets_in_minutes}m)"
                elif w.resets_in_minutes < 1440:
                    line += f"  (Resets in {w.resets_in_minutes // 60}h {w.resets_in_minutes % 60}m)"
                else:
                    line += f"  (Resets in {w.resets_in_minutes // 1440}d {(w.resets_in_minutes % 1440) // 60}h)"

            print(line)
        print()

    return 0


def cmd_doctor() -> int:
    """Diagnose local CLI tools, credentials, and network connectivity."""
    print("\n\033[1m=== Token Runway: Doctor ===\033[0m\n")

    # 1. Claude
    token = find_claude_token()
    if token:
        print("  \033[92m✔ Claude Code:\033[0m Credentials found")
    else:
        print("  \033[93m▲ Claude Code:\033[0m No credentials found in ~/.claude/.credentials.json")

    # 2. Antigravity CLI (`agy`)
    if shutil.which("agy"):
        print("  \033[92m✔ Antigravity CLI (`agy`):\033[0m Found in PATH")
    else:
        print("  \033[90m- Antigravity CLI (`agy`):\033[0m Not installed or not in PATH")

    # 3. GitHub CLI (`gh`)
    if shutil.which("gh"):
        print("  \033[92m✔ GitHub CLI (`gh`):\033[0m Found in PATH")
    else:
        print("  \033[90m- GitHub CLI (`gh`):\033[0m Not installed or not in PATH")

    # 4. Google Colab CLI (`colab`)
    if shutil.which("colab"):
        print("  \033[92m✔ Google Colab CLI (`colab`):\033[0m Found in PATH")
    else:
        print("  \033[90m- Google Colab CLI (`colab`):\033[0m Not installed or not in PATH")

    print("\nChecking live endpoints...")
    readings = fetch_all_runways()
    for name, r in readings.items():
        if r.available:
            print(f"  \033[92m✔ {r.display_name}:\033[0m Connected ({len(r.windows)} quota windows active)")
        else:
            print(f"  \033[93m▲ {r.display_name}:\033[0m {r.error_message}")

    print("\nDoctor check completed.\n")
    return 0


def cmd_inject(mode: str = "auto") -> int:
    """Inject Token Runway into detected AI IDE configuration files."""
    print("\n\033[1m=== Token Runway: IDE Injector ===\033[0m\n")
    targets = get_ide_config_targets()
    injected_count = 0

    for ide_name, path in targets:
        try:
            inject_into_file(path, mode=mode)
            print(f"  \033[92m✔ {ide_name}:\033[0m Injected configuration into {path}")
            injected_count += 1
        except Exception as e:
            print(f"  \033[91m✖ {ide_name}:\033[0m Failed to update {path}: {e}")

    print(f"\nInjected token-runway entry into {injected_count} IDE configuration(s).\n")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="token-runway",
        description="Model Context Protocol (MCP) server for real-time token runway & quota awareness.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"token-runway {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # Subcommands
    subparsers.add_parser("run", help="Run stdio MCP server (default when no command given).")
    subparsers.add_parser("check", help="Print terminal table of active quotas.")
    subparsers.add_parser("doctor", help="Check local tools, credentials, and API connectivity.")

    inject_parser = subparsers.add_parser("inject", help="Auto-inject MCP server into Claude Desktop, Cursor, etc.")
    inject_parser.add_argument(
        "--mode",
        choices=["auto", "uvx", "pip"],
        default="auto",
        help="Command launch mode in IDE configs (default: auto).",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        return cmd_check()
    elif args.command == "doctor":
        return cmd_doctor()
    elif args.command == "inject":
        return cmd_inject(mode=args.mode)
    else:
        # Default behavior: run MCP stdio server
        server = TokenRunwayServer()
        try:
            server.run_stdio()
            return 0
        except (KeyboardInterrupt, BrokenPipeError):
            return 0


if __name__ == "__main__":
    sys.exit(main())
