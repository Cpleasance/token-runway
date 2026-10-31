"""Command-line interface for Token Runway."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from token_runway import __version__
from token_runway.injector.config_injector import get_ide_config_targets, inject_into_file
from token_runway.server.server import SUPPORTED_PROVIDERS, TokenRunwayServer
from token_runway.sources import fetch_all_runways
from token_runway.sources.claude import find_claude_token
from token_runway.sources.openai_source import find_openai_key
from token_runway.sources.openrouter import find_openrouter_key


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def should_use_color(no_color_flag: bool = False) -> bool:
    """Determine whether ANSI color output should be emitted."""
    if no_color_flag or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def format_status_badge(status: str, use_color: bool = True) -> str:
    """Format status badge with optional ANSI color."""
    if not use_color:
        return f"[{status.upper()}]"
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


def cmd_check(
    as_json: bool = False,
    provider: Optional[str] = None,
    no_color: bool = False,
) -> int:
    """Print active AI provider quotas as a table or JSON."""
    color = should_use_color(no_color)

    if provider:
        prov_clean = provider.lower().strip()
        if prov_clean not in SUPPORTED_PROVIDERS:
            err_msg = f"Unknown provider '{provider}'. Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
            if color:
                print(f"\033[91m✖ Error:\033[0m {err_msg}", file=sys.stderr)
            else:
                print(f"Error: {err_msg}", file=sys.stderr)
            return 1
    else:
        prov_clean = None

    readings = fetch_all_runways(provider=prov_clean)
    if prov_clean:
        readings = {k: v for k, v in readings.items() if k == prov_clean}

    if as_json:
        data = {k: v.to_dict() for k, v in readings.items()}
        print(json.dumps(data, indent=2))
        return 0

    header = "\n=== Token Runway: Live Quota Telemetry ===\n"
    if color:
        print("\n\033[1m=== Token Runway: Live Quota Telemetry ===\033[0m\n")
    else:
        print(header)

    if not readings:
        print(f"No telemetry found for provider '{provider}'.\n")
        return 0

    for _key, r in readings.items():
        title = r.display_name
        if color:
            title = f"\033[1;34m{r.display_name}\033[0m"
            if r.plan:
                title += f" \033[90m(Plan: {r.plan})\033[0m"
        else:
            if r.plan:
                title += f" (Plan: {r.plan})"
        print(title)

        if not r.available:
            msg = f"  Unavailable: {r.error_message}\n"
            if color:
                msg = f"  \033[90mUnavailable: {r.error_message}\033[0m\n"
            print(msg)
            continue

        if not r.windows:
            msg = "  No active quota windows reported.\n"
            if color:
                msg = f"  \033[90m{msg.strip()}\033[0m\n"
            print(msg)
            continue

        for w in r.windows:
            badge = format_status_badge(w.status, use_color=color)
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

        print("")
    return 0


def cmd_doctor(provider: Optional[str] = None, no_color: bool = False) -> int:
    """Diagnose local CLI tools, credentials, and network connectivity."""
    color = should_use_color(no_color)
    header = "\n=== Token Runway: Doctor ===\n"
    print("\n\033[1m=== Token Runway: Doctor ===\033[0m\n" if color else header)

    prov_filter = provider.lower().strip() if provider else None
    if prov_filter and prov_filter not in SUPPORTED_PROVIDERS:
        err_msg = f"Unknown provider '{provider}'. Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
        if color:
            print(f"\033[91m✖ Error:\033[0m {err_msg}", file=sys.stderr)
        else:
            print(f"Error: {err_msg}", file=sys.stderr)
        return 1

    # 1. Claude
    if not prov_filter or prov_filter == "claude":
        token = find_claude_token()
        if token:
            msg = "  \033[92m✔ Claude Code:\033[0m Credentials found" if color else "  ✔ Claude Code: Credentials found"
        else:
            msg = (
                "  \033[93m▲ Claude Code: No credentials found (log in via `claude`)\033[0m"
                if color
                else "  ▲ Claude Code: No credentials found (log in via `claude`)"
            )
        print(msg)

    # 2. Antigravity CLI (`agy`)
    if not prov_filter or prov_filter in ("gemini", "antigravity"):
        found = shutil.which("agy") is not None
        if found:
            msg = "  \033[92m✔ Antigravity CLI (`agy`):\033[0m Found in PATH" if color else "  ✔ Antigravity CLI: Found in PATH"
        else:
            msg = "  \033[90m- Antigravity CLI (`agy`):\033[0m Not installed" if color else "  - Antigravity CLI: Not installed"
        print(msg)

    # 3. GitHub CLI (`gh`)
    if not prov_filter or prov_filter == "copilot":
        found = shutil.which("gh") is not None
        if found:
            msg = "  \033[92m✔ GitHub CLI (`gh`):\033[0m Found in PATH" if color else "  ✔ GitHub CLI (`gh`): Found in PATH"
        else:
            msg = "  \033[90m- GitHub CLI (`gh`):\033[0m Not installed" if color else "  - GitHub CLI (`gh`): Not installed"
        print(msg)

    # 4. Google Colab CLI (`colab`)
    if not prov_filter or prov_filter == "colab":
        found = shutil.which("colab") is not None
        if found:
            msg = "  \033[92m✔ Google Colab (`colab`):\033[0m Found in PATH" if color else "  ✔ Google Colab: Found in PATH"
        else:
            msg = "  \033[90m- Google Colab (`colab`):\033[0m Not installed" if color else "  - Google Colab: Not installed"
        print(msg)

    # 5. OpenRouter API Key
    if not prov_filter or prov_filter == "openrouter":
        if find_openrouter_key():
            msg = "  \033[92m✔ OpenRouter:\033[0m Key configured" if color else "  ✔ OpenRouter: Key configured"
        else:
            msg = "  \033[90m- OpenRouter:\033[0m Key not set (optional)" if color else "  - OpenRouter: Key not set"
        print(msg)

    # 6. OpenAI API Key
    if not prov_filter or prov_filter == "openai":
        if find_openai_key():
            msg = "  \033[92m✔ OpenAI API:\033[0m Key configured" if color else "  ✔ OpenAI API: Key configured"
        else:
            msg = "  \033[90m- OpenAI API:\033[0m Key not set (optional)" if color else "  - OpenAI API: Key not set"
        print(msg)

    check_header = "\nChecking live endpoints..."
    print("\n\033[1mChecking live endpoints...\033[0m" if color else check_header)
    readings = fetch_all_runways(provider=prov_filter)
    if prov_filter:
        readings = {k: v for k, v in readings.items() if k == prov_filter}

    for _name, r in readings.items():
        if r.available:
            cached_suffix = f" (cached {r.cache_age_seconds}s ago)" if r.is_cached else ""
            msg = f"  ✔ {r.display_name}: Connected ({len(r.windows)} quota windows active){cached_suffix}"
            print(f"  \033[92m{msg.strip()}\033[0m" if color else msg)
        else:
            msg = f"  ▲ {r.display_name}: {r.error_message}"
            print(f"  \033[93m{msg.strip()}\033[0m" if color else msg)

    print("\nDoctor check completed.\n")
    return 0


def cmd_init_rules(path: str = ".", targets: Optional[List[str]] = None, dry_run: bool = False) -> int:
    """Generate or update rule files with Token Runway self-governance instructions."""
    from token_runway.injector.rules_generator import generate_rules

    root = Path(path).resolve()
    print("\n\033[1m=== Token Runway: Rules Generator ===\033[0m\n")
    print(f"Target Directory: {root}\n")

    results = generate_rules(root, targets=targets, dry_run=dry_run)
    for _name, fpath, created in results:
        action = "Created" if created else "Updated"
        if dry_run:
            print(f"  \033[96m[Dry-Run]\033[0m Would {action.lower()}: {fpath.name}")
        else:
            print(f"  \033[92m✔ {action}:\033[0m {fpath.name}")

    prefix = "Would configure" if dry_run else "Configured"
    print(f"\n{prefix} Token Runway self-governance across {len(results)} rule file(s).\n")
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
    run_parser = subparsers.add_parser("run", help="Run stdio MCP server (default when no command given).")
    run_parser.add_argument(
        "--max-budget",
        type=float,
        default=None,
        help="Maximum allowed percentage before advising pause.",
    )
    run_parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Strictly reject actions if budget is exceeded.",
    )

    check_parser = subparsers.add_parser("check", help="Print terminal table or JSON of active quotas.")
    check_parser.add_argument("--json", action="store_true", default=False, help="Emit output as JSON for scripting.")
    check_parser.add_argument("--provider", "-p", default=None, help="Filter to a specific provider.")
    check_parser.add_argument("--no-color", action="store_true", default=False, help="Disable ANSI color codes.")

    doctor_parser = subparsers.add_parser("doctor", help="Check local tools, credentials, and API connectivity.")
    doctor_parser.add_argument("--provider", "-p", default=None, help="Diagnose a specific provider.")
    doctor_parser.add_argument("--no-color", action="store_true", default=False, help="Disable ANSI color codes.")

    watch_parser = subparsers.add_parser(
        "watch",
        help="Live-updating terminal HUD showing token runway and reset timers.",
    )
    watch_parser.add_argument("--interval", "-i", type=float, default=5.0, help="Refresh interval in seconds (default: 5.0).")
    watch_parser.add_argument("--provider", "-p", default=None, help="Filter to a specific provider.")

    inject_parser = subparsers.add_parser("inject", help="Auto-inject MCP server into Claude Desktop, Cursor, etc.")
    inject_parser.add_argument(
        "--mode",
        choices=["auto", "uvx", "pip"],
        default="auto",
        help="Command launch mode in IDE configs (default: auto).",
    )

    rules_parser = subparsers.add_parser(
        "init-rules",
        help="Embed Token Runway self-governance rules into repository (CLAUDE.md, .cursorrules, etc.).",
    )
    rules_parser.add_argument("--path", "-p", default=".", help="Root directory of the project (default: current directory).")
    rules_parser.add_argument(
        "--target",
        "-t",
        choices=["all", "claude", "cursor", "windsurf", "agents"],
        default="all",
        help="Target rule file(s) to configure (default: all).",
    )
    rules_parser.add_argument("--dry-run", action="store_true", default=False, help="Show proposed changes without writing.")

    dashboard_parser = subparsers.add_parser("dashboard", help="Start local Web HUD dashboard on localhost.")
    dashboard_parser.add_argument("--port", "-p", type=int, default=7890, help="Port to listen on (default: 7890).")
    dashboard_parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1).")
    dashboard_parser.add_argument("--no-open", action="store_true", default=False, help="Do not open browser automatically.")

    args = parser.parse_args(argv)

    if getattr(args, "provider", None):
        prov_clean = args.provider.lower().strip()
        if prov_clean not in SUPPORTED_PROVIDERS:
            err_msg = f"Unknown provider '{args.provider}'. Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
            if should_use_color(getattr(args, "no_color", False)):
                print(f"\033[91m✖ Error:\033[0m {err_msg}", file=sys.stderr)
            else:
                print(f"Error: {err_msg}", file=sys.stderr)
            return 1

    if args.command == "check":
        return cmd_check(as_json=args.json, provider=args.provider, no_color=args.no_color)
    elif args.command == "doctor":
        return cmd_doctor(provider=args.provider, no_color=args.no_color)
    elif args.command == "watch":
        from token_runway.viewer.watch import run_watch_loop
        run_watch_loop(interval=args.interval, provider=args.provider)
        return 0
    elif args.command == "dashboard":
        from token_runway.viewer.dashboard import start_dashboard
        try:
            start_dashboard(host=args.host, port=args.port, open_browser=not args.no_open)
            return 0
        except ValueError as e:
            print(f"\033[91m✖ Security Error:\033[0m {e}", file=sys.stderr)
            return 1
    elif args.command == "inject":
        return cmd_inject(mode=args.mode)
    elif args.command == "init-rules":
        targets = None if args.target == "all" else [args.target]
        return cmd_init_rules(path=args.path, targets=targets, dry_run=args.dry_run)
    else:
        # Default behavior: run MCP stdio server
        max_budget = getattr(args, "max_budget", None)
        strict = getattr(args, "strict", False)
        server = TokenRunwayServer(max_budget=max_budget, strict=strict)
        try:
            server.run_stdio()
            return 0
        except (KeyboardInterrupt, BrokenPipeError):
            return 0


if __name__ == "__main__":
    sys.exit(main())
