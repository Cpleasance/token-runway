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
from token_runway.sources.openai_source import find_openai_key
from token_runway.sources.openrouter import find_openrouter_key

__version__ = "0.2.0"


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
        print("  \033[93m▲ Claude Code:\033[0m No credentials found (log in via `claude` or set CLAUDE_CODE_TOKEN / ANTHROPIC_ACCESS_TOKEN)")

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

    # 5. OpenRouter API Key
    if find_openrouter_key():
        print("  \033[92m✔ OpenRouter:\033[0m OPENROUTER_API_KEY configured")
    else:
        print("  \033[90m- OpenRouter:\033[0m OPENROUTER_API_KEY not set (optional)")

    # 6. OpenAI API Key
    if find_openai_key():
        print("  \033[92m✔ OpenAI API:\033[0m OPENAI_API_KEY configured")
    else:
        print("  \033[90m- OpenAI API:\033[0m OPENAI_API_KEY not set (optional)")

    print("\nChecking live endpoints...")
    readings = fetch_all_runways()
    for name, r in readings.items():
        if r.available:
            print(f"  \033[92m✔ {r.display_name}:\033[0m Connected ({len(r.windows)} quota windows active)")
        else:
            print(f"  \033[93m▲ {r.display_name}:\033[0m {r.error_message}")

    print("\nDoctor check completed.\n")
    return 0


def cmd_init_rules(path: str = ".", targets: Optional[List[str]] = None, dry_run: bool = False) -> int:
    """Generate or update rule files with Token Runway self-governance instructions."""
    from token_runway.injector.rules_generator import generate_rules

    root = Path(path).resolve()
    print(f"\n\033[1m=== Token Runway: Rules Generator ===\033[0m\n")
    print(f"Target Directory: {root}\n")

    results = generate_rules(root, targets=targets, dry_run=dry_run)
    for name, fpath, created in results:
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
    run_parser.add_argument("--max-budget", type=float, default=None, help="Maximum allowed percentage before advising pause.")
    run_parser.add_argument("--strict", action="store_true", default=False, help="Strictly reject actions if budget is exceeded.")

    subparsers.add_parser("check", help="Print terminal table of active quotas.")
    subparsers.add_parser("doctor", help="Check local tools, credentials, and API connectivity.")

    watch_parser = subparsers.add_parser("watch", help="Live-updating terminal HUD showing token runway and reset timers.")
    watch_parser.add_argument("--interval", "-i", type=float, default=5.0, help="Refresh interval in seconds (default: 5.0).")

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

    if args.command == "check":
        return cmd_check()
    elif args.command == "doctor":
        return cmd_doctor()
    elif args.command == "watch":
        from token_runway.viewer.watch import run_watch_loop
        run_watch_loop(interval=args.interval)
        return 0
    elif args.command == "dashboard":
        from token_runway.viewer.dashboard import start_dashboard
        start_dashboard(host=args.host, port=args.port, open_browser=not args.no_open)
        return 0
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
