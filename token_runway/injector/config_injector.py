"""Multi-IDE configuration detector and one-click injector for Token Runway."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def get_ide_config_targets() -> List[Tuple[str, Path]]:
    """Return a list of known (IDE_Name, config_path) tuples for the current OS."""
    targets = []
    home = Path.home()

    # 1. Claude Desktop
    if sys.platform == "darwin":
        targets.append(("Claude Desktop", home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"))
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            targets.append(("Claude Desktop", Path(appdata) / "Claude" / "claude_desktop_config.json"))
    else:
        targets.append(("Claude Desktop", home / ".config" / "Claude" / "claude_desktop_config.json"))

    # 2. Cursor
    targets.append(("Cursor", home / ".cursor" / "mcp.json"))

    # 3. Claude Code
    targets.append(("Claude Code", home / ".claude" / "mcp.json"))

    # 4. Antigravity
    targets.append(("Antigravity", home / ".gemini" / "antigravity-cli" / "mcp_config.json"))

    # 5. Windsurf
    targets.append(("Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json"))

    return targets


def build_mcp_entry(mode: str = "auto") -> Dict[str, Any]:
    """Generate the MCP server entry dictionary."""
    if mode == "uvx" or (mode == "auto" and shutil.which("uvx")):
        return {
            "command": "uvx",
            "args": ["token-runway"],
            "env": {"PYTHONUNBUFFERED": "1"},
        }
    else:
        python_exe = sys.executable
        return {
            "command": python_exe,
            "args": ["-m", "token_runway"],
            "env": {"PYTHONUNBUFFERED": "1"},
        }


def inject_into_file(path: Path, entry_name: str = "token-runway", mode: str = "auto") -> bool:
    """Inject or update the token-runway MCP server definition into target config."""
    path.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    # Root key is typically "mcpServers"
    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}

    data["mcpServers"][entry_name] = build_mcp_entry(mode)

    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return True
