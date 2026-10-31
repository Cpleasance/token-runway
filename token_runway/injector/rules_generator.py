"""Project rules generator for embedding Token Runway self-governance into repositories."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

START_MARKER = "<!-- token-runway:start -->"
END_MARKER = "<!-- token-runway:end -->"

RUNWAY_RULE_TEXT = f"""{START_MARKER}
## 🛫 Token Runway Meta-Cognitive Self-Governance

Before taking any of the following high-consumption actions, you MUST invoke the `assess_action` tool from Token Runway:
1. Spawning or fanning out parallel subagents or background worker tasks.
2. Ingesting large files (>200 lines) or dumping full repository directory listings into context.
3. Embarking on extensive multi-turn deep research sweeps or unbounded retry loops.

### Governance Behavior:
- If `assess_action` verdict is **`proceed`**: Full operational capacity is permitted.
- If `assess_action` verdict is **`proceed_with_caution`**: Avoid redundant file reads and monitor tokens.
- If `assess_action` verdict is **`downgrade_strategy`**: Use targeted tools (e.g. `grep` / narrow line ranges) instead of reading full files. Do NOT spawn parallel subagents.
- If `assess_action` verdict is **`pause_or_downgrade`** or **`reject`**: Quota is exhausted or restricted. Pause heavy actions, defer to the user, or downgrade to lightweight models (Flash/Haiku) until the reset window opens.
{END_MARKER}"""

TARGET_FILES: Dict[str, str] = {
    "claude": "CLAUDE.md",
    "cursor": ".cursorrules",
    "windsurf": ".windsurfrules",
    "agents": "AGENTS.md",
}


def inject_rules_into_content(existing_content: str) -> str:
    """Inject or update managed Token Runway block in markdown/rule content."""
    if START_MARKER in existing_content and END_MARKER in existing_content:
        # Replace existing managed block
        pre = existing_content.split(START_MARKER)[0].rstrip()
        post = existing_content.split(END_MARKER)[1].lstrip()
        parts = []
        if pre:
            parts.append(pre)
        parts.append(RUNWAY_RULE_TEXT)
        if post:
            parts.append(post)
        return "\n\n".join(parts) + "\n"

    # Append to existing
    cleaned = existing_content.rstrip()
    if cleaned:
        return f"{cleaned}\n\n{RUNWAY_RULE_TEXT}\n"
    return f"{RUNWAY_RULE_TEXT}\n"


def generate_rules(
    root_dir: Path,
    targets: Optional[List[str]] = None,
    dry_run: bool = False,
) -> List[Tuple[str, Path, bool]]:
    """
    Generate or update rule files in target directory.
    Returns list of (target_name, path, is_created).
    """
    selected_targets = targets or ["claude", "cursor", "windsurf", "agents"]
    results = []

    for name in selected_targets:
        filename = TARGET_FILES.get(name)
        if not filename:
            continue
        file_path = root_dir / filename
        created = not file_path.exists()

        existing = file_path.read_text(encoding="utf-8") if file_path.is_file() else ""
        updated = inject_rules_into_content(existing)

        if not dry_run:
            file_path.write_text(updated, encoding="utf-8")

        results.append((name, file_path, created))

    return results
