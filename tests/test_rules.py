from pathlib import Path

from token_runway.injector.rules_generator import (
    START_MARKER,
    generate_rules,
    inject_rules_into_content,
)


def test_inject_rules_into_empty():
    res = inject_rules_into_content("")
    assert START_MARKER in res
    assert "Token Runway Meta-Cognitive Self-Governance" in res


def test_inject_rules_into_existing_content():
    orig = "# My Project\n\nExisting guidelines."
    res = inject_rules_into_content(orig)
    assert orig in res
    assert START_MARKER in res

    # Idempotent re-injection replaces block cleanly
    re_injected = inject_rules_into_content(res)
    assert re_injected.count(START_MARKER) == 1
    assert orig in re_injected


def test_generate_rules_filesystem(tmp_path: Path):
    # Test dry run
    dry_results = generate_rules(tmp_path, targets=["claude", "cursor"], dry_run=True)
    assert len(dry_results) == 2
    assert not (tmp_path / "CLAUDE.md").exists()

    # Test actual write
    results = generate_rules(tmp_path, targets=["claude", "cursor"], dry_run=False)
    assert len(results) == 2
    claude_file = tmp_path / "CLAUDE.md"
    assert claude_file.exists()
    assert "Token Runway" in claude_file.read_text()
