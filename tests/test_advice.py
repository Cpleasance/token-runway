from token_runway.server.advice import evaluate_action_feasibility
from token_runway.sources.base import ProviderReading, QuotaWindow


def test_evaluate_action_healthy():
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=25)],
        )
    }
    advice = evaluate_action_feasibility(readings, action_type="subagent_fanout", intensity="high")
    assert advice["verdict"] == "proceed"
    assert advice["max_utilization_pct"] == 25


def test_evaluate_action_warning():
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=85)],
        )
    }
    advice = evaluate_action_feasibility(readings, action_type="subagent_fanout", intensity="high")
    assert advice["verdict"] == "downgrade_strategy"
    assert len(advice["preservation_strategies"]) > 0


def test_evaluate_action_critical():
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=98, resets_in_minutes=15)],
        )
    }
    advice = evaluate_action_feasibility(readings, action_type="general", intensity="low")
    assert advice["verdict"] == "pause_or_downgrade"
    assert any("resets in ~15 minutes" in s for s in advice["preservation_strategies"])


def test_evaluate_action_guardrail_budget():
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=75)],
        )
    }
    # Under limit (75 < 80) -> proceed
    under = evaluate_action_feasibility(readings, max_budget=80)
    assert under["verdict"] == "proceed"

    # Exceeding budget without strict (75 >= 70) -> pause_or_downgrade
    over = evaluate_action_feasibility(readings, max_budget=70, strict=False)
    assert over["verdict"] == "pause_or_downgrade"

    # Exceeding budget with strict (75 >= 70) -> reject
    strict_rej = evaluate_action_feasibility(readings, max_budget=70, strict=True)
    assert strict_rej["verdict"] == "reject"
    assert "Strict safety guardrail triggered" in strict_rej["analysis"]


def test_evaluate_action_unavailable_telemetry():
    # When no readings exist or all are unavailable, do NOT falsely report 0% healthy
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            available=False,
            error_message="Not logged in",
        )
    }
    advice = evaluate_action_feasibility(readings, action_type="subagent_fanout")
    assert advice["verdict"] == "unknown"
    assert advice["max_utilization_pct"] is None
    assert "No active quota" in advice["analysis"]


def test_evaluate_action_unknown_provider():
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=25)],
        )
    }
    advice = evaluate_action_feasibility(readings, target_provider="unknown_provider")
    assert advice["verdict"] == "unknown"
    assert "not found" in advice["analysis"]


def test_evaluate_action_action_type_sensitivity():
    readings = {
        "claude": ProviderReading(
            provider="claude",
            display_name="Claude",
            windows=[QuotaWindow(name="5h", used_pct=82)],
        )
    }
    # subagent_fanout at 82% triggers downgrade_strategy
    fanout = evaluate_action_feasibility(readings, action_type="subagent_fanout")
    assert fanout["verdict"] == "downgrade_strategy"
    assert any("Prohibit parallel subagents" in s for s in fanout["preservation_strategies"])

    # targeted_edit at 82% is permitted with caution
    edit = evaluate_action_feasibility(readings, action_type="targeted_edit", intensity="low")
    assert edit["verdict"] == "proceed_with_caution"
    assert any("Targeted edits allowed" in s for s in edit["preservation_strategies"])
