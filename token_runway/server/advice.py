"""Meta-cognitive reasoning engine for assessing action feasibility against active quotas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from token_runway.sources.base import ProviderReading


def evaluate_action_feasibility(
    readings: Dict[str, ProviderReading],
    action_type: str = "general",
    intensity: str = "medium",  # "low", "medium", "high"
    target_provider: Optional[str] = None,
    max_budget: Optional[float] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Evaluate whether an agent should proceed with a resource-intensive action."""
    action_type = action_type.lower().strip()
    intensity = intensity.lower().strip()

    # If target_provider is specified, validate it exists in readings
    if target_provider:
        target_clean = target_provider.lower().strip()
        if target_clean not in readings:
            return {
                "verdict": "unknown",
                "max_utilization_pct": None,
                "bottleneck": None,
                "analysis": f"Requested provider '{target_provider}' was not found in discovered telemetry.",
                "preservation_strategies": [
                    f"Check spelling for '{target_provider}'.",
                    "Run 'check_runway' to see all active providers.",
                ],
                "action_type": action_type,
                "intensity": intensity,
            }
        providers_to_check = [target_clean]
    else:
        providers_to_check = list(readings.keys())

    # Identify primary active provider constraints
    highest_used_pct = -1
    most_constrained_provider = None
    most_constrained_window = None
    mins_to_reset = None
    has_valid_window = False

    for p_name in providers_to_check:
        reading = readings.get(p_name)
        if not reading or not reading.available:
            continue
        for w in reading.windows:
            if w.used_pct is not None:
                has_valid_window = True
                if w.used_pct > highest_used_pct:
                    highest_used_pct = w.used_pct
                    most_constrained_provider = reading.display_name
                    most_constrained_window = w.name
                    mins_to_reset = w.resets_in_minutes

    # If no providers were available or none reported usage windows, do NOT falsely report 0% healthy!
    if not has_valid_window or highest_used_pct < 0:
        err_msgs = [
            f"{r.display_name}: {r.error_message}"
            for r in readings.values()
            if not r.available and r.error_message
        ]
        detail = f" ({'; '.join(err_msgs[:2])})" if err_msgs else ""
        return {
            "verdict": "unknown",
            "max_utilization_pct": None,
            "bottleneck": None,
            "analysis": f"No active quota or rate-limit telemetry is currently available{detail}.",
            "preservation_strategies": [
                "Cannot verify quota headroom. Proceed conservatively with single-step operations.",
                "Run 'token-runway doctor' to verify provider tools and credentials.",
            ],
            "action_type": action_type,
            "intensity": intensity,
        }

    recommendation = "proceed"
    strategies: List[str] = []
    reasoning: str = ""

    # Check user-configured guardrail / spending cap first
    if max_budget is not None and highest_used_pct >= max_budget:
        if strict:
            recommendation = "reject"
            reasoning = (
                f"Strict safety guardrail triggered: {highest_used_pct}% utilization on {most_constrained_provider} "
                f"exceeds configured maximum budget threshold of {max_budget}%."
            )
            strategies.append("Action rejected by strict user guardrail. Prohibit execution.")
            strategies.append("Wait for quota window reset or switch to an alternate provider.")
        else:
            recommendation = "pause_or_downgrade"
            reasoning = (
                f"Configured budget threshold reached ({highest_used_pct}% >= {max_budget}% limit on {most_constrained_provider})."
            )
            strategies.append("Budget limit reached. Pause expensive background operations.")
            strategies.append("Downgrade task intensity to stay under the budget ceiling.")
    elif highest_used_pct >= 95:
        recommendation = "pause_or_downgrade"
        reasoning = (
            f"Quota is critically constrained ({highest_used_pct}% used on {most_constrained_provider} {most_constrained_window})."
        )
        if mins_to_reset is not None and mins_to_reset <= 30:
            strategies.append(
                f"Window resets in ~{mins_to_reset} minutes. Defer heavy work and perform lightweight local tasks."
            )
        strategies.append("Prohibit parallel subagent fan-outs; execute one step at a time.")
        strategies.append("Read narrow line ranges (under 100 lines) instead of loading full files into context.")
        strategies.append("Route subagent prompts to lightweight models (Flash/Haiku) if model selection is supported.")
    elif highest_used_pct >= 80:
        # Check action type sensitivity
        if action_type in ("subagent_fanout", "recursive_loop"):
            recommendation = "downgrade_strategy"
            reasoning = (
                f"Quota is tight ({highest_used_pct}% used on {most_constrained_provider}). "
                f"Action '{action_type}' multiplies token consumption across workers and risks immediate lockout."
            )
            strategies.append("Prohibit parallel subagents. Run steps sequentially on the main agent.")
        elif action_type in ("targeted_edit", "quick_query") and intensity != "high":
            # Targeted edits consume very few tokens
            recommendation = "proceed_with_caution"
            reasoning = (
                f"Headroom is tight ({highest_used_pct}% used on {most_constrained_provider}), "
                f"but '{action_type}' has low token footprint."
            )
            strategies.append("Targeted edits allowed. Avoid reading full files into context.")
        elif intensity == "high":
            recommendation = "downgrade_strategy"
            reasoning = (
                f"Quota headroom is tight ({highest_used_pct}% used on {most_constrained_provider}). High-intensity operations risk lockouts."
            )
            strategies.append("Downgrade multi-agent broad searches to targeted ripgrep / grep commands.")
            strategies.append("Summarize long context before launching further turns.")
        else:
            recommendation = "proceed_with_caution"
            reasoning = f"Headroom is moderate ({highest_used_pct}% used on {most_constrained_provider}). Standard actions permitted."
            strategies.append("Monitor token usage after this turn.")
    elif highest_used_pct >= 70 and action_type in ("subagent_fanout", "recursive_loop") and intensity == "high":
        # Action-type specific safeguard: high-intensity subagent fanouts at 70%+
        recommendation = "proceed_with_caution"
        reasoning = (
            f"Subagent fanouts multiply consumption quickly ({highest_used_pct}% used on {most_constrained_provider})."
        )
        strategies.append("Limit parallel subagent count to 2 max.")
    else:
        recommendation = "proceed"
        reasoning = f"Healthy headroom ({highest_used_pct}% maximum utilization on {most_constrained_provider})."
        strategies.append("Full operational capacity available for multi-agent workflows and deep research.")

    return {
        "verdict": recommendation,
        "max_utilization_pct": highest_used_pct,
        "bottleneck": {
            "provider": most_constrained_provider,
            "window": most_constrained_window,
            "resets_in_minutes": mins_to_reset,
        }
        if most_constrained_provider
        else None,
        "analysis": reasoning,
        "preservation_strategies": strategies,
        "action_type": action_type,
        "intensity": intensity,
    }
